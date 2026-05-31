"""Redis TimeSeries pipeline upload helpers.

All TimeSeries writes go through a single
:class:`~redis.commands.timeseries.Pipeline` per data-type batch, reducing
round-trips to one network exchange per type regardless of row count.

Importantly :meth:`~redis.commands.timeseries.Pipeline.execute` is called
with ``raise_on_error=False``. This means individual ``TS.ADD`` command
failures are surfaced as :class:`~redis.exceptions.ResponseError` *objects*
inside the response list rather than raised as exceptions, allowing the
response-inspection loop in :func:`_resolve_failures` to produce granular
:class:`~.response.RowFailure` entries instead of collapsing an entire batch
into a single :class:`~.response.BatchFailure` for even a single failure.

A :class:`~.response.BatchFailure` is still produced when the pipeline
itself raises a :class:`~redis.exceptions.RedisError` (connection loss,
auth failure, etc.) — in that case no per-row response is available.

Performance
-----------
:func:`upload_batch` precomputes the two Redis key strings
(``ts:<type>:start`` and ``ts:<type>:end``) **once per batch** and iterates
the dataframe via raw numpy arrays — avoiding per-row f-string formatting
and the overhead of :meth:`pandas.DataFrame.itertuples`'s namedtuple
construction.  On a 5M-row export this is typically a 2-3× speedup of the
load step.

Provides :func:`upload_batch` for public use.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd
from redis import ResponseError
from redis.commands.timeseries import Pipeline, TimeSeries

from .response import DuplicatePolicy, RowFailure

logger = logging.getLogger(__name__)


def _queue_row(
    pipe: Pipeline,
    start_key: str,
    end_key: str,
    start_ts: int,
    end_ts: int,
    value: float,
    policy: str,
) -> None:
    """Queue a single record's start and end ``TS.ADD`` commands on *pipe*.

    Two commands are issued per record:

    * ``<type>:start`` — timestamped at ``start_ts``
    * ``<type>:end``   — timestamped at ``end_ts``

    The commands are not executed until
    :meth:`~redis.commands.timeseries.Pipeline.execute` is called by the
    caller, so this function is always O(1) and performs no network I/O.

    Args:
        pipe: An open Redis TimeSeries pipeline.
        start_key: Precomputed ``ts:<type>:start`` key.
        end_key: Precomputed ``ts:<type>:end`` key.
        start_ts: Unix timestamp in seconds for the start TS.ADD.
        end_ts: Unix timestamp in seconds for the end TS.ADD.
        value: Numeric record value to write to both series.
        policy: Resolved duplicate-policy string (``"FIRST"`` or ``"LAST"``).

    """
    pipe.add(key=start_key, timestamp=start_ts, value=value, duplicate_policy=policy)
    pipe.add(key=end_key, timestamp=end_ts, value=value, duplicate_policy=policy)


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
            Length must equal ``2 * len(df)``.
        df: Health records DataFrame for the batch the response belongs to.
            Used for the ``type`` and per-row index reported in failures.

    Returns:
        List of :class:`~.response.RowFailure` objects.  Empty on full
        success.

    Raises:
        IndexError: if response and df don't have matching length.

    """
    if len(response) != 2 * len(df):
        raise IndexError("response must contain two elements per df row.")

    row_failures: list[RowFailure] = []
    indices = df.index.to_numpy()
    types = df["type"].to_numpy()

    for pos in range(len(df)):
        start_resp = response[pos * 2]
        end_resp = response[pos * 2 + 1]
        start_ok = not isinstance(start_resp, ResponseError)
        end_ok = not isinstance(end_resp, ResponseError)

        if start_ok and end_ok:
            continue

        idx = indices[pos]
        failure = RowFailure(
            data_type=str(types[pos]),
            row_index=idx.item() if hasattr(idx, "item") else idx,
            start_error=None if start_ok else str(start_resp),
            end_error=None if end_ok else str(end_resp),
        )
        row_failures.append(failure)
        logger.info("\tRow %s failed — %s", idx, failure)

    return row_failures


def upload_batch(
    rts: TimeSeries,
    df: pd.DataFrame,
    duplicate_policy: DuplicatePolicy = DuplicatePolicy.FIRST,
) -> list[RowFailure]:
    """Upload a single-type slice to Redis TimeSeries via one pipeline.

    All rows in *df* must share the same ``type`` value; the caller (the
    importer's load step) is responsible for the per-type grouping.  This
    function precomputes the two Redis keys once per call rather than once
    per row and iterates the relevant columns as raw numpy arrays.

    ``Pipeline.execute`` is called with ``raise_on_error=False`` so that
    individual command failures are returned as
    :class:`~redis.exceptions.ResponseError` objects in the response list,
    enabling granular :class:`~.response.RowFailure` reporting.

    Failure semantics:

    * **Connection-level failure** (:class:`~redis.exceptions.RedisError`
      raised by :meth:`Pipeline.execute`): propagated to the caller, which
      wraps it in a :class:`~.response.BatchFailure`.
    * **Command-level failure** (:class:`~redis.exceptions.ResponseError`
      objects in the response list): one :class:`~.response.RowFailure` per
      affected row, with the error message(s) for its start and/or end
      command.

    Response mapping (two ``TS.ADD`` commands per row):

    .. code-block:: text

        response[2i]   → start command for row i
        response[2i+1] → end command for row i

    Args:
        rts: Redis TimeSeries client.
        df: Health records slice for **one** ``type`` value.
        duplicate_policy: Per-command write-conflict strategy forwarded to
            every ``pipe.add()`` call.

    Returns:
        List of :class:`~.response.RowFailure` objects.  Empty on full
        success or empty input.

    Example::

        rts = client.ts()
        row_failures = upload_batch(rts, df_heart_rate)

    """
    if df.empty:
        return []

    # All rows in this batch share a single ``type``; resolve keys once.
    data_type = df["type"].iloc[0]
    start_key = f"ts:{data_type}:start"
    end_key = f"ts:{data_type}:end"
    policy = duplicate_policy.value

    # Pull columns into numpy arrays to skip Series-level overhead in the
    # hot loop. ``.to_numpy()`` is a no-copy view when dtype permits.
    starts = df["startDate"].to_numpy()
    ends = df["endDate"].to_numpy()
    values = df["value"].to_numpy()

    pipe: Pipeline = rts.pipeline()
    for s, e, v in zip(starts, ends, values, strict=True):
        # Cast through ``.item()`` for numpy scalar → Python int / float so
        # redis-py serialises a clean RESP integer instead of "np.int64(…)".
        _queue_row(
            pipe,
            start_key,
            end_key,
            int(s) if isinstance(s, (np.integer, np.int64)) else s,
            int(e) if isinstance(e, (np.integer, np.int64)) else e,
            float(v) if isinstance(v, (np.floating, np.float64)) else v,
            policy,
        )

    response: list[Any] = pipe.execute(raise_on_error=False)

    return _resolve_failures(response=response, df=df)
