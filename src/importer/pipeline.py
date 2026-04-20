"""Redis TimeSeries pipeline upload helpers.

All writes to Redis TimeSeries are batched through a single
:class:`~redis.commands.timeseries.Pipeline` per data-type call, reducing
round-trips to one network exchange per type regardless of row count.

Importantly :meth:`Pipeline.execute` is called with ``raise_on_error=False``.
This means individual ``TS.ADD`` command failures are surfaced as
:class:`~redis.exceptions.ResponseError` *objects* inside the response list
rather than raised as exceptions, allowing the response-inspection loop in
:func:`_resolve_failures` to produce granular :class:`~models.RowFailure`
entries instead of collapsing an entire batch into a single
:class:`~models.BatchFailure` for even a single failure.

A :class:`~models.BatchFailure` is still produced when the pipeline itself
raises a :class:`~redis.exceptions.RedisError` (connection loss, auth
failure, etc.) — in that case no per-row response is available.

Provides :func:`upload_batch` for public use.
"""

import logging
from collections.abc import Iterable
from typing import Any

import pandas as pd
from redis import ResponseError
from redis.commands.timeseries import Pipeline, TimeSeries

from importer.models import DuplicatePolicy, RowFailure

logger = logging.getLogger(__name__)


def _add_row_to_pipeline(
    pipe: Pipeline,
    row: Iterable[tuple[Any, ...]],
    duplicate_policy: DuplicatePolicy = DuplicatePolicy.FIRST,
) -> None:
    """Queue a single health record's start and end ``TS.ADD`` commands on *pipe*.

    Two commands are issued per record:

    * ``<type>:start`` — timestamped at ``startDate``
    * ``<type>:end``   — timestamped at ``endDate``

    The commands are not executed until :meth:`Pipeline.execute` is called by
    the caller, so this function is always O(1) and performs no network I/O.

    Args:
        pipe: An open Redis TimeSeries pipeline.
        row: A single ``itertuples`` row from the health records DataFrame.
            Expected named attributes: ``type``, ``startDate``, ``endDate``,
            ``value``, ``sourceName``, ``unit``.
        duplicate_policy: Per-command write-conflict strategy forwarded to
            every ``TS.ADD`` call.

    Example::

        pipe = rts.pipeline()
        for row in df.itertuples():
            _add_row_to_pipeline(pipe, row, DuplicatePolicy.FIRST)
        pipe.execute(raise_on_error=False)

    """
    labels = {"sourceName": row.sourceName, "unit": row.unit}
    common: dict[str, Any] = {
        "labels": labels,
        "duplicate_policy": duplicate_policy.value,
        "value": row.value,
    }
    pipe.add(key=f"{row.type}:start", timestamp=row.startDate, **common)
    pipe.add(key=f"{row.type}:end", timestamp=row.endDate, **common)


def _resolve_failures(
    response: list[Any],
    df: pd.DataFrame,
) -> list[RowFailure]:
    """Inspect a pipeline response and record per-row failures.

    Maps the flat *response* list back to individual rows using the
    ``response[2i] / response[2i+1]`` convention (start / end command per
    row *i*).  Successful commands return an ``int`` (the stored timestamp);
    failed commands return a :class:`~redis.exceptions.ResponseError` object
    when the pipeline was executed with ``raise_on_error=False``.

    Args:
        response: Flat list returned by ``pipe.execute(raise_on_error=False)``.
            Length must equal ``2 * len(indices)``.
        df: Health records DataFrame of batch belonging to input :arg:`response`.

    Returns:
        List of :class:`~models.RowFailure` objects.  Empty on full
        success.

    Raises:
        IndexError if response and df don't have the same length

    Example::

        pipe = rts.pipeline()
        # … queue commands …
        response = pipe.execute(raise_on_error=False)
        failures = _resolve_failures(response, df)

    """
    if len(response) != 2 * len(df):
        raise IndexError("response must contain two elements per df row.")

    row_failures: list[RowFailure] = []

    for pos, row in enumerate(df.itertuples()):
        idx = row.Index
        start_resp = response[pos * 2]
        end_resp = response[pos * 2 + 1]
        start_ok = not isinstance(start_resp, ResponseError)
        end_ok = not isinstance(end_resp, ResponseError)

        if start_ok and end_ok:
            continue

        failure = RowFailure(
            data_type=row.type,
            row_index=idx,
            start_error=None if start_ok else str(start_resp),
            end_error=None if end_ok else str(end_resp),
        )

        row_failures.append(failure)

        logger.info(
            "Row %s (type=%s startDate=%s endDate=%s) failed — %s",
            idx,
            row.Index,
            df.loc[idx, "startDate"],
            df.loc[idx, "endDate"],
            failure,
        )

    return row_failures


def upload_batch(
    rts: TimeSeries,
    df: pd.DataFrame,
    duplicate_policy: DuplicatePolicy = DuplicatePolicy.FIRST,
) -> list[RowFailure]:
    """Upload data slice to Redis TimeSeries via a single pipeline.

    All ``TS.ADD`` commands for the slice are batched into one
    :class:`~redis.commands.timeseries.Pipeline` and flushed in a single
    network round-trip.  :meth:`Pipeline.execute` is called with
    ``raise_on_error=False`` so that individual command failures are returned
    as :class:`~redis.exceptions.ResponseError` objects in the response list
    rather than raised as exceptions, enabling granular
    :class:`~models.RowFailure` reporting.

    Failure semantics:

    * **Connection-level failure** (:class:`~redis.exceptions.RedisError`
      raised by :meth:`Pipeline.execute`): Error is handled by caller.
    * **Command-level failure** (:class:`~redis.exceptions.ResponseError`
      objects in the response list): one :class:`~models.RowFailure` per
      affected row, with the error message(s) for its start and/or end
      command.

    Response mapping (two ``TS.ADD`` commands per row):

    .. code-block:: text

        response[2i]   → start command for row i
        response[2i+1] → end command for row i

    Args:
        rts: Redis TimeSeries client.
        df: Health records DataFrame for a batch.
        duplicate_policy: Per-command write-conflict strategy forwarded to
            every ``pipe.add()`` call.

    Returns:
        List of :class:`~models.RowFailure` objects.  Empty on full
        success.

    Example::

        r = redis_connect()
        rts = r.ts()
        row_failures = upload_batch(rts, df)

    """
    pipe: Pipeline = rts.pipeline()

    for row in df.itertuples():
        _add_row_to_pipeline(pipe, row, duplicate_policy=duplicate_policy)

    response: list[Any] = pipe.execute(raise_on_error=False)

    return _resolve_failures(
        response=response,
        df=df,
    )
