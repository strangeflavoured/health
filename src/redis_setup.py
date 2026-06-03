"""RediSearch index management and TimeSeries label provisioning for Apple Health data.

This module has two responsibilities:

1. **RediSearch indexes** — create and maintain JSON indexes over the four
   primary document namespaces written by the Apple Health importer:

   * ``workout:<id>``     — HKWorkout documents (events, statistics, activities)
   * ``correlation:<id>`` — HKCorrelation documents (blood-pressure pairs, etc.)
   * ``activity:<date>``  — ActivitySummary documents (one per calendar day)
   * ``route:<workoutId>`` — WorkoutRoute documents (GPX trackpoints per workout)

2. **RedisTimeSeries labels** — provision ``ts:<identifier>:start`` and
   ``ts:<identifier>:end`` keys for every type registered in
   :data:`~src.model.HKTypeIdentifierRegistry`, attaching metadata labels
   (``identifier``, ``unit``, ``group``, ``event_type``) that enable
   ``TS.MRANGE`` label-filter queries across the whole dataset.

Document/index schema contract
------------------------------
Every JSON document the importer writes carries a ``metaKeys`` field
(``list[str]``, the keys of its ``meta`` dict).  This makes
``$.metaKeys[*]`` a valid TagField path even though Apple's ``meta`` is
stored as an object.  Timestamp fields (``startDate``, ``endDate``,
``creationDate``, ``date``) are stored as **int64 Unix seconds**, matching
the TimeSeries values and giving the NumericField indexes the form
RediSearch expects.

Idempotency
-----------
All public functions are safe to call on a Redis instance that already
contains data or indexes:

* :func:`setup_indexes` skips indexes that already exist unless
  ``force=True``.  Dropping an index does **not** delete documents —
  RediSearch re-indexes existing JSON documents automatically after
  recreation.
* :func:`upsert_ts_labels` calls ``TS.ALTER`` on existing keys and falls
  back to ``TS.CREATE`` only when the key is absent.  Labels are therefore
  only written once at key-creation time during normal import; this
  function is intended as a one-off provisioning or migration tool, not as
  part of every import cycle.

Dry-run mode
------------
Every mutating function accepts a ``dry_run`` keyword argument.  When
``dry_run=True`` the function logs what it *would* do and returns without
touching Redis.  This is the default in the companion runner script so
that accidental executions are harmless.

Typical usage
-------------
Run directly from the project root::

    python scripts/setup-redis.py                # dry-run by default
    python scripts/setup-redis.py --execute      # actually write to Redis
    python scripts/setup-redis.py --force        # drop + recreate existing indexes

Or call programmatically::

    from src.redis_setup import setup_indexes, upsert_ts_labels, records_labels

    setup_indexes(client, dry_run=False, force=False)
    upsert_ts_labels(client, records_labels(), dry_run=False)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import redis
from redis.commands.search.field import Field, NumericField, TagField
from redis.commands.search.index_definition import IndexDefinition, IndexType
from redis.exceptions import ResponseError

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Index definitions
# ---------------------------------------------------------------------------


@dataclass
class IndexSpec:
    """Declarative description of a single RediSearch index.

    Attributes
    ----------
    name:
        The index name passed to ``FT.CREATE`` / ``FT.INFO`` / ``FT.DROPINDEX``
        (e.g. ``"idx:workouts"``).
    prefix:
        Key prefix that RediSearch monitors for documents belonging to this
        index (e.g. ``"workout:"``).  All Redis keys whose name starts with
        this string are automatically included.
    fields:
        Ordered list of :class:`redis.commands.search.field.Field` instances
        that define which JSON paths are indexed and under what query aliases.
    description:
        Human-readable summary shown in logs and dry-run output.  Not written
        to Redis.

    """

    name: str
    prefix: str
    fields: list[Field]
    description: str = ""


_INDICES: list[IndexSpec] = [
    IndexSpec(
        name="idx:workouts",
        prefix="workout:",
        description=(
            "HKWorkout documents with embedded events, statistics, and activities"
        ),
        fields=[
            TagField("$.workoutActivityType", as_name="activityType"),
            TagField("$.sourceName", as_name="sourceName"),
            NumericField("$.startDate", as_name="startDate", sortable=True),
            NumericField("$.endDate", as_name="endDate", sortable=True),
            TagField("$.metaKeys[*]", as_name="metaKeys"),
        ],
    ),
    IndexSpec(
        name="idx:correlations",
        prefix="correlation:",
        description="HKCorrelation documents with embedded records",
        fields=[
            TagField("$.type", as_name="type"),
            TagField("$.sourceName", as_name="sourceName"),
            NumericField("$.startDate", as_name="startDate", sortable=True),
            NumericField("$.endDate", as_name="endDate", sortable=True),
            TagField("$.metaKeys[*]", as_name="metaKeys"),
        ],
    ),
    IndexSpec(
        name="idx:activities",
        prefix="activity:",
        description="ActivitySummary documents — one per calendar day",
        fields=[
            NumericField("$.date", as_name="date", sortable=True),
            NumericField(
                "$.activeEnergyBurned", as_name="activeEnergyBurned", sortable=True
            ),
            NumericField(
                "$.activeEnergyBurnedGoal",
                as_name="activeEnergyBurnedGoal",
                sortable=True,
            ),
            NumericField(
                "$.appleExerciseTime", as_name="appleExerciseTime", sortable=True
            ),
            NumericField(
                "$.appleExerciseTimeGoal",
                as_name="appleExerciseTimeGoal",
                sortable=True,
            ),
            NumericField("$.appleStandHours", as_name="appleStandHours", sortable=True),
            NumericField(
                "$.appleStandHoursGoal", as_name="appleStandHoursGoal", sortable=True
            ),
        ],
    ),
    IndexSpec(
        name="idx:routes",
        prefix="route:",
        description=(
            "WorkoutRoute documents — one per workout with embedded trackpoints"
        ),
        fields=[
            TagField("$.workoutId", as_name="workoutId"),
            TagField("$.sourceName", as_name="sourceName"),
            NumericField("$.startDate", as_name="startDate", sortable=True),
            NumericField("$.endDate", as_name="endDate", sortable=True),
            NumericField("$.numPoints", as_name="numPoints", sortable=True),
        ],
    ),
]


# ---------------------------------------------------------------------------
# Index operations
# ---------------------------------------------------------------------------


def index_exists(client: redis.Redis, name: str) -> bool:
    """Return ``True`` if a RediSearch index with *name* exists.

    Uses ``FT.INFO`` as the existence probe.  Any
    :class:`~redis.exceptions.ResponseError` is treated as "index not found"
    — which is the error Redis returns for unknown index names.

    Parameters
    ----------
    client:
        Connected :class:`redis.Redis` instance.
    name:
        Fully-qualified index name, e.g. ``"idx:workouts"``.

    """
    try:
        client.ft(name).info()
        return True
    except ResponseError:
        return False


def drop_index(client: redis.Redis, name: str, *, dry_run: bool) -> None:
    """Drop a RediSearch index by name.

    Documents stored under the index's prefix are **not** deleted; RediSearch
    will re-index them automatically if a new index with the same prefix is
    created afterward.

    Parameters
    ----------
    client:
        Connected :class:`redis.Redis` instance.
    name:
        Fully-qualified index name, e.g. ``"idx:workouts"``.
    dry_run:
        When ``True``, log the intended operation and return without issuing
        any Redis commands.

    """
    if dry_run:
        logger.info("[dry-run] would drop   %s", name)
        return
    client.ft(name).dropindex()
    logger.info("dropped               %s", name)


def create_index(client: redis.Redis, spec: IndexSpec, *, dry_run: bool) -> None:
    """Create a RediSearch JSON index from an :class:`IndexSpec`.

    Issues ``FT.CREATE`` with ``ON JSON`` and the prefix and fields defined in
    *spec*.  The caller is responsible for ensuring the index does not already
    exist (or has been dropped) before calling this function.

    Parameters
    ----------
    client:
        Connected :class:`redis.Redis` instance.
    spec:
        Declarative description of the index to create.
    dry_run:
        When ``True``, log the intended operation (including field paths and
        aliases) and return without issuing any Redis commands.

    """
    field_names = [f.name for f in spec.fields]
    if dry_run:
        logger.info(
            "[dry-run] would create %s  prefix=%s  fields=%s",
            spec.name,
            spec.prefix,
            field_names,
        )
        return
    client.ft(spec.name).create_index(
        spec.fields,
        definition=IndexDefinition(
            prefix=[spec.prefix],
            index_type=IndexType.JSON,
        ),
    )
    logger.info(
        "created        %s  prefix=%s  fields=%s", spec.name, spec.prefix, field_names
    )


def setup_indexes(
    client: redis.Redis,
    *,
    dry_run: bool = False,
    force: bool = False,
) -> None:
    """Create all RediSearch indexes defined in :data:`_INDICES`.

    Iterates over the module-level index registry and creates any missing
    indexes.  Existing indexes are left untouched unless *force* is ``True``,
    in which case each existing index is dropped and recreated.

    This function is idempotent: calling it on a fully-provisioned Redis
    instance with ``force=False`` is a no-op (beyond logging).

    Parameters
    ----------
    client:
        Connected :class:`redis.Redis` instance.
    dry_run:
        When ``True``, log all intended operations and return without writing
        to Redis.  Propagated to :func:`drop_index` and :func:`create_index`.
    force:
        When ``True``, drop and recreate indexes that already exist.  Use this
        after changing field definitions in :data:`_INDICES`.  Has no effect
        on indexes that are absent (they are created normally).

    """
    for spec in _INDICES:
        exists = index_exists(client, spec.name)

        if exists and not force:
            logger.info(
                "exists  (skipping)    %s  — use --force to recreate",
                spec.name,
            )
            continue

        if exists and force:
            drop_index(client, spec.name, dry_run=dry_run)

        create_index(client, spec, dry_run=dry_run)


def print_status(client: redis.Redis) -> None:
    """Log a human-readable status table for all known indexes.

    For each index in :data:`_INDICES`, emits one log line showing either the
    document count (or ``"indexing…"`` if a background indexing pass is in
    progress) or ``"missing"`` if the index does not exist.

    Intended for post-setup verification and interactive debugging.  Output
    goes to the module logger at ``INFO`` level.

    Parameters
    ----------
    client:
        Connected :class:`redis.Redis` instance.

    """
    logger.info("─" * 60)
    logger.info("index status:")
    for spec in _INDICES:
        if index_exists(client, spec.name):
            info = client.ft(spec.name).info()
            doc_count = info.get("num_docs", "?")
            indexing = info.get("indexing", "0")
            status = "indexing…" if indexing == "1" else f"{doc_count} docs"
            logger.info("  %-30s  %s", spec.name, status)
        else:
            logger.info("  %-30s  missing", spec.name)


# ---------------------------------------------------------------------------
# TimeSeries label operations
# ---------------------------------------------------------------------------


def ensure_ts_key(
    client: redis.Redis,
    key: str,
    labels: dict[str, str],
    duplicate_policy: str = "FIRST",
) -> None:
    """Create or update a RedisTimeSeries key.

    If the key does not yet exist it is created with *labels* and
    *duplicate_policy*.  If it already exists, only the ``DUPLICATE_POLICY``
    is updated via ``TS.ALTER`` so that the policy for the current run (e.g.
    ``"FIRST"`` for :meth:`~.HealthDataImporter.etl` vs ``"LAST"`` for
    :meth:`~.HealthDataImporter.update`) takes effect before the first
    ``TS.MADD`` for that key. If the labels don't match ValueError is raised,
    it could be caused by data corruption or a schema drift.

    Labels are **not** updated on existing keys.

    Args:
        client:
            Connected :class:`redis.Redis` instance with RedisTimeSeries loaded.
        key:
            Full Redis key name, e.g. ``"ts:HKQuantityTypeIdentifierHeartRate:start"``.
        labels:
            Flat ``str → str`` metadata mapping attached at creation time.
        duplicate_policy:
            ``TS.MADD`` duplicate-conflict strategy for this key: ``"FIRST"``
            (keep the oldest value, used by :meth:`~.HealthDataImporter.etl`) or
            ``"LAST"`` (overwrite, used by :meth:`~.HealthDataImporter.update`).
            Accepts any string accepted by RedisTimeSeries.

    Raises:
        ValueError: If input labels and labels in redis don't match.

    """
    try:
        resp = client.ts().info(key)

        # raise if labels don't match
        if resp["labels"] != labels:
            raise ValueError(
                "Key %s: labels don't match: expected %s, got %s",
                key,
                resp["labels"],
                labels,
            )

        # update the policy so the current run's strategy applies.
        if resp["duplicate_policy"] != duplicate_policy:
            client.ts().alter(key, duplicate_policy=duplicate_policy)
            logging.debug("Altered  key=%s  duplicate_policy=%s", key, duplicate_policy)

    except redis.ResponseError:
        client.ts().create(key, labels=labels, duplicate_policy=duplicate_policy)
        logger.warning("Created  key=%s  labels=%s", key, labels)
