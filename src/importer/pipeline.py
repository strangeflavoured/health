"""Redis TimeSeries pipeline upload helpers.

Writes health records to Redis TimeSeries using ``TS.MADD`` — a single command
that adds multiple samples in one round-trip.  Compared to pipelined ``TS.ADD``
calls, ``TS.MADD`` pays the Redis parse-and-dispatch overhead once per batch
rather than once per row, typically doubling throughput on a local instance.

The duplicate-conflict policy is **not** passed per-sample as it would be with
``TS.ADD``.  Instead it is set on the key itself by
:func:`~src.importer.importer.ensure_ts_key` before the first batch for each type,
and ``TS.MADD`` honours the key-level policy automatically.

``TS.MADD`` returns one reply per sample in the same order the samples were
submitted.  Successful samples return an ``int`` (the stored timestamp);
failed samples return a :class:`~redis.exceptions.ResponseError` object, which
:func:`_resolve_failures` maps back to the originating row.

Provides :func:`upload_batch` for public use.
"""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd
from redis import ResponseError
from redis.commands.timeseries import TimeSeries

from .response import RowFailure

logger = logging.getLogger(__name__)


def _build_madd_args(df: pd.DataFrame) -> list[tuple[str, int, float]]:
    """Build the ``TS.MADD`` argument triples for every row in *df*.

    Returns a flat list of ``(key, timestamp, value)`` tuples — two per row —
    interleaved so that the start sample immediately precedes the end sample
    for the same row:

    .. code-block:: text

        (ts:<type>:start, startDate₀, value₀),
        (ts:<type>:end,   endDate₀,   value₀),
        (ts:<type>:start, startDate₁, value₁),
        …

    This ordering is significant: :func:`_resolve_failures` maps the flat
    ``TS.MADD`` response back to rows using ``response[2i]`` (start) and
    ``response[2i+1]`` (end) for row *i*.

    Args:
        df: Batch of transformed health records with ``type``, ``startDate``,
            ``endDate``, and ``value`` columns.

    Returns:
        List of ``(key, timestamp, value)`` triples.  Empty when *df* is empty.

    Example::

        args = _build_madd_args(df)
        response = rts.madd(args)

    """
    args: list[tuple[str, int, float]] = []
    for row in df.itertuples():
        args.append((f"ts:{row.type}:start", int(row.startDate), float(row.value)))
        args.append((f"ts:{row.type}:end", int(row.endDate), float(row.value)))

    return args


def _resolve_failures(
    response: list[Any],
    df: pd.DataFrame,
) -> list[RowFailure]:
    """Inspect a ``TS.MADD`` response and record per-row failures.

    Maps the flat *response* list back to individual rows using the
    ``response[2i] / response[2i+1]`` convention (start / end sample per
    row *i*).  Successful samples return an ``int`` (the stored timestamp);
    failed samples return a :class:`~redis.exceptions.ResponseError` object.

    Args:
        response: Flat list returned by ``rts.madd()``.
            Length must equal ``2 * len(df)``.
        df: Health records DataFrame of the batch belonging to *response*.

    Returns:
        List of :class:`~.response.RowFailure` objects.  Empty on full success.

    Raises:
        IndexError: If ``len(response) != 2 * len(df)``.

    Example::

        args = _build_madd_args(df)
        response = rts.madd(args)
        failures = _resolve_failures(response, df)

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
) -> list[RowFailure]:
    """Upload a batch of records to Redis TimeSeries via a single ``TS.MADD`` command.

    The duplicate-conflict policy is **not** accepted here; it is set on each
    key by :func:`~src.importer.importer._upload_type` via
    :func:`~src.redis_setup.ensure_ts_key` before the first batch for that
    type, and ``TS.MADD`` honours the key-level policy automatically.

    Unlike the previous pipelined implementation, ``TS.MADD`` pays the Redis
    parse-and-dispatch overhead once per call regardless of batch size.

    Response mapping (two samples per row):

    .. code-block:: text

        response[2i]   → start sample for row i
        response[2i+1] → end sample for row i

    Args:
        rts: Redis TimeSeries client (e.g. ``r.ts()``).
        df: Batch of transformed health records.

    Returns:
        List of :class:`~.response.RowFailure` objects.  Empty on full success.

    Example::

        rts = client.ts()
        failures = upload_batch(rts, df)

    """
    if df.empty:
        return []

    args = _build_madd_args(df)
    response: list[Any] = rts.madd(args)

    return _resolve_failures(response, df)
