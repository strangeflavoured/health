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

from .model import HKTypeIdentifierRegistry
from .model.base import MissingUnit

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


def index_exists(client: redis.Redis[str], name: str) -> bool:
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
        client.ft(name).info()  # type: ignore[no-untyped-call]
        return True
    except ResponseError:
        return False


def drop_index(client: redis.Redis[str], name: str, *, dry_run: bool) -> None:
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


def create_index(client: redis.Redis[str], spec: IndexSpec, *, dry_run: bool) -> None:
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
        definition=IndexDefinition(  # type: ignore[no-untyped-call]
            prefix=[spec.prefix],
            index_type=IndexType.JSON,
        ),
    )
    logger.info(
        "created        %s  prefix=%s  fields=%s", spec.name, spec.prefix, field_names
    )


def setup_indexes(
    client: redis.Redis[str],
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


def print_status(client: redis.Redis[str]) -> None:
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
            info = client.ft(spec.name).info()  # type: ignore[no-untyped-call]
            doc_count = info.get("num_docs", "?")
            indexing = info.get("indexing", "0")
            status = "indexing…" if indexing == "1" else f"{doc_count} docs"
            logger.info("  %-30s  %s", spec.name, status)
        else:
            logger.info("  %-30s  missing", spec.name)


# ---------------------------------------------------------------------------
# TimeSeries label operations
# ---------------------------------------------------------------------------


def upsert_ts_labels(
    client: redis.Redis[str],
    key_labels: list[tuple[str, dict[str, str]]],
    *,
    dry_run: bool = False,
) -> None:
    """Provision RedisTimeSeries keys with metadata labels.

    For each ``(key, labels)`` pair, attempts ``TS.ALTER`` to update labels on
    an existing key.  Falls back to ``TS.CREATE`` when the key is absent.

    This function is designed as a **one-off provisioning or migration tool**,
    not as part of the hot import path.  During normal imports, keys are created
    on-demand via :func:`ensure_ts_key`; calling this function on every import
    would redundantly alter labels on every existing key.

    Parameters
    ----------
    client:
        Connected :class:`redis.Redis` instance with RedisTimeSeries loaded.
    key_labels:
        List of ``(key, labels)`` pairs as returned by :func:`records_labels`.
        Labels must be a flat ``str → str`` mapping; ``None`` values are
        permitted and are passed through to the TimeSeries module as-is.
    dry_run:
        When ``True``, log the intended operations and return without writing
        to Redis.

    """
    for key, labels in key_labels:
        if dry_run:
            logger.info("[dry-run] would upsert labels  %s  %s", key, labels)
            continue
        try:
            client.ts().alter(key, labels=labels)
            logger.info("altered        labels  %s  %s", key, labels)
        except redis.ResponseError:
            client.ts().create(key, labels=labels)
            logger.info("created        labels  %s  %s", key, labels)


def ensure_ts_key(
    client: redis.Redis[str],
    key: str,
    labels: dict[str, str],
) -> None:
    """Create a RedisTimeSeries key with labels if it does not already exist.

    Intended to be called by the importer immediately before the first
    ``TS.ADD`` for a given key within an import run.  If the key already exists
    (i.e. it was created during a previous import), the ``TS.INFO`` probe
    succeeds and this function returns without any writes.

    This is the preferred creation path during import; :func:`upsert_ts_labels`
    is reserved for bulk provisioning and schema migrations.

    Parameters
    ----------
    client:
        Connected :class:`redis.Redis` instance with RedisTimeSeries loaded.
    key:
        Full Redis key name, e.g. ``"ts:HKQuantityTypeIdentifierHeartRate:start"``.
    labels:
        Flat ``str → str`` metadata mapping attached to the key at creation
        time.  Labels are immutable after creation via this function; use
        :func:`upsert_ts_labels` (``TS.ALTER``) to change them later.

    """
    try:
        client.ts().info(key)  # type: ignore[no-untyped-call]
    except redis.ResponseError:
        client.ts().create(key, labels=labels)
        logger.warning("Created key=%s  labels=%s", key, labels)


def records_labels() -> list[tuple[str, dict[str, str]]]:
    """Build the full list of TimeSeries ``(key, labels)`` pairs from the type registry.

    Iterates over :data:`~src.model.HKTypeIdentifierRegistry` and produces
    entries for every registered type.  Quantity and category types receive
    two entries each — one ``:start`` series and one ``:end`` series, with
    the ``event_type`` label distinguishing them.  Correlation types do not
    get TimeSeries keys (correlations live as RediSearch JSON documents);
    they are filtered out here.

    The ``unit`` label is read from ``cls.unit`` and falls back to the
    categorical sentinel (``"Categorical"``) for types that have no
    canonical SI unit.

    Label schema per key
    --------------------
    ============  ==================================================
    Label         Value
    ============  ==================================================
    identifier    HKTypeIdentifier string, e.g.
                  ``"HKQuantityTypeIdentifierHeartRate"``
    unit          SI / Apple unit string, e.g. ``"count/min"``, or
                  ``"Categorical"`` for category types
    group         Logical grouping from the model, e.g. ``"vital_signs"``
    event_type    ``"start"`` or ``"end"``
    ============  ==================================================

    Using ``event_type`` as a single label (rather than separate boolean
    ``start`` / ``end`` labels) allows ``TS.MRANGE`` callers to filter on
    ``identifier=X`` alone to retrieve **both** series, or additionally on
    ``event_type=start`` to retrieve only one.

    Returns
    -------
    list[tuple[str, dict[str, str]]]
        Ordered list of ``(key, labels)`` pairs ready to be passed to
        :func:`upsert_ts_labels`.

    """
    key_labels: list[tuple[str, dict[str, str]]] = []
    for name, cls in HKTypeIdentifierRegistry.items():
        # Correlations are stored as JSON documents, not as TimeSeries.
        if cls.identifier_type == "correlation":
            continue

        unit = getattr(cls, "unit", MissingUnit.CATEGORICAL.value)
        base_labels: dict[str, str] = {
            "unit": unit,
            "identifier": name,
            "group": cls.group,
        }
        key_labels.append((f"ts:{name}:start", base_labels | {"event_type": "start"}))
        key_labels.append((f"ts:{name}:end", base_labels | {"event_type": "end"}))

    return key_labels
