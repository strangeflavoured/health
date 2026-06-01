"""Apple Health DataFrame transformation pipeline.

Provides the public :func:`transform` function that prepares the raw records
DataFrame for upload to Redis TimeSeries.

All public and private functions in this module accept a ``df`` argument
that refers to the same underlying :class:`~pandas.DataFrame` and mutate
it in-place.  No copies are created, keeping peak RAM proportional to the
export size rather than a multiple of it.

Order of operations matters
---------------------------
:func:`transform` drops ``NaN``-value rows *before* running data-sanity
checks.  This avoids spurious "missing unit" errors on rows that would be
dropped anyway because their value is missing.

Performance notes
-----------------
* :data:`_FLAT_CATEGORY_MAP` is built once at import time as a flat
  ``(type, value) → int`` dictionary and exposed as a :class:`pandas.Series`
  with a MultiIndex so the per-row mapping in :func:`_map_categories` is
  fully vectorised.
* :func:`_handle_categorical_units` checks for unexpected ``NaN`` values
  using a single ``df[nullable].isna().any()`` call rather than a Python
  loop over columns.
* :func:`_timestamps_to_unix` uses :func:`pandas.to_datetime` so both raw
  Apple-Health timestamp strings and already-parsed ``datetime64`` columns
  are handled uniformly.
"""

from __future__ import annotations

import logging

import pandas as pd

from ..model import CATEGORY_MAP
from ..model.base import HKGroup, MissingUnit
from .data_check import (
    KNOWN_CATEGORY_TYPE_VIOLATIONS,
    KNOWN_UNIT_MISMATCHES,
    check_export_data,
)

logger = logging.getLogger(__name__)

# these columns are expected to contain entries without value
COLUMNS_WITHOUT_VALUE = ["unit", "device"]

# dt.dtype.unit is one of "s", "ms", "us", "ns" depending on pandas
# version and input precision.  Map it to ticks-per-second.
_UNIT_PER_SECOND = {"s": 1, "ms": 1_000, "us": 1_000_000, "ns": 1_000_000_000}

# ---------------------------------------------------------------------------
# Module-level flat lookups built once at import time.
#
# ``CATEGORY_MAP`` is the dict form used for membership checks and
# nice error reporting; ``_FLAT_CATEGORY_SERIES`` is the same data exposed
# as a MultiIndex-keyed Series so the per-row mapping in
# :func:`_map_categories` can be done with a single vectorised reindex.
# ---------------------------------------------------------------------------

_FLAT_CATEGORY_SERIES: pd.Series = pd.Series(
    list(CATEGORY_MAP.values()),
    index=pd.MultiIndex.from_tuples(list(CATEGORY_MAP.keys()), names=("type", "value")),
    dtype="int64",
)


def transform(df: pd.DataFrame) -> None:
    """Clean and reshape *df* in-place for upload to Redis TimeSeries.

    Applies the following steps in order:

    1. Drop rows whose ``value`` field is ``NaN``
       (:func:`_drop_null_values`).
    2. Run sanity checks against the model registries
       (:func:`~.data_check.check_export_data`).  Done after the null-drop
       so unit-check errors are not raised against rows that would be
       discarded anyway.
    3. Resolve categorical string values to signed integers and assign the
       ``"Categorical"`` sentinel unit
       (:func:`_handle_categorical_units`).
    4. Coerce ``value`` to ``float64``.
    5. Convert ``startDate`` and ``endDate`` from strings or timezone-aware
       datetimes to Unix timestamps in whole seconds
       (:func:`_timestamps_to_unix`).
    6. Add a ``group`` column derived from the type registry
       (:meth:`~src.model.base.HKGroup.map_members`).

    Note:
        Not thread-safe — all mutations are applied directly to the shared
        DataFrame without locking.

    Args:
        df: The raw health records DataFrame as produced by the extract
            step; mutated in-place.  ``startDate`` and ``endDate`` may be
            either Apple Health timestamp strings
            (``"2024-01-01 00:00:00 +0000"``) or pandas datetime objects.

    Example::

        transform(df)
        # df["startDate"] and df["endDate"] are now int64 Unix timestamps

    """
    logger.info("Transforming export data...")
    _drop_null_values(df)
    check_export_data(df)
    _handle_categorical_units(df)
    _replace_unit_mismatches(df)
    df["value"] = pd.to_numeric(df["value"]).astype("float64")
    df["startDate"] = _timestamps_to_unix(df["startDate"])
    df["endDate"] = _timestamps_to_unix(df["endDate"])
    df["group"] = df["type"].map(HKGroup.map_members())


def _drop_null_values(df: pd.DataFrame) -> None:
    """Drop rows with a ``NaN`` ``value`` field and log the count.

    Mutates *df* in-place.  If *all* rows have a ``NaN`` value, *df* will
    be empty after this call; subsequent steps handle an empty DataFrame
    gracefully.

    Args:
        df: Health records DataFrame; rows with a ``NaN`` ``value`` are
            removed.

    Example::

        before = len(df)
        _drop_null_values(df)
        print(f"Dropped {before - len(df)} rows")

    """
    before = len(df)
    df.dropna(subset=["value"], inplace=True)  # noqa: PD002
    n_dropped = before - len(df)
    if n_dropped:
        logger.warning("Dropped %d rows with missing 'value'.", n_dropped)


def _handle_categorical_units(df: pd.DataFrame) -> None:
    """Assign integer values and a sentinel unit to categorical records.

    Rows without a ``unit`` value are treated as categorical.  Their string
    ``value`` is resolved to a signed integer via :func:`_map_categories`,
    and their ``unit`` is set to :attr:`~model.base.MissingUnit.CATEGORICAL`.
    For ``type`` / ``value`` pairs in
    :const:`~.data_check.KNOWN_CATEGORY_TYPE_VIOLATIONS` the ``type`` is
    corrected before mapping.

    Uses a single ``df[nullable].isna().any()`` call to spot unexpected
    ``NaN`` values, rather than scanning each column with a Python loop.

    Args:
        df: Health records DataFrame; the ``value`` and ``unit`` columns
            are mutated in-place for categorical rows.

    Raises:
        NotImplementedError: If ``NaN`` values are found in any column
            other than those listed in :data:`COLUMNS_WITHOUT_VALUE`,
            indicating an unexpected schema change.
        ValueError: If a row without a unit has a numeric ``value``; only
            categorical string values are expected in that position.

    Example::

        _handle_categorical_units(df)
        # Categorical rows now have integer values and unit == "Categorical"

    """
    # Vectorised NaN scan — one C-level pass over the relevant columns.
    nullable_cols = df.columns.difference(COLUMNS_WITHOUT_VALUE)
    any_na = df[nullable_cols].isna().any()
    unexpected = list(any_na[any_na].index)
    if unexpected:
        raise NotImplementedError(
            f"Unexpected column(s) have NaN (schema may have changed): {unexpected}"
        )

    no_unit: pd.Series = df["unit"].isna()
    if not no_unit.any():
        return

    numeric_mask = pd.to_numeric(df.loc[no_unit, "value"], errors="coerce").notna()
    if numeric_mask.any():
        raise ValueError(
            "Some records without a unit have a numeric value; "
            "expected only categorical strings."
        )

    _replace_known_violations(df)
    _map_categories(df, no_unit)
    df.loc[no_unit, "unit"] = MissingUnit.CATEGORICAL.value


def _timestamps_to_unix(series: pd.Series) -> pd.Series:
    """Convert a date/time Series to Unix timestamps in whole seconds.

    Accepts both Apple Health timestamp strings
    (e.g. ``"2024-01-01 00:00:00 +0100"``) and already-parsed
    ``datetime64`` objects (tz-aware or tz-naive).  Uses
    :func:`pandas.to_datetime` with ``utc=True`` to guarantee correct UTC
    conversion regardless of the input timezone offset.

    Conversion via ``.view("int64")`` then dividing by the *unit-specific*
    factor avoids both floating-point rounding errors and the pandas 3.x
    pitfall where ``pd.to_datetime`` returns microsecond precision by
    default (10⁶ ticks per second) while older code assumed nanoseconds
    (10⁹).  The divisor is derived from the datetime dtype's resolution so
    the function is correct for any pandas precision.

    Args:
        series: A pandas Series whose values are either Apple Health
            timestamp strings or ``datetime64`` objects.

    Returns:
        An ``int64`` Series of Unix timestamps in **seconds**.

    Example::

        unix_ts = _timestamps_to_unix(df["startDate"])
        # unix_ts.dtype == int64

    """
    dt = pd.to_datetime(series, utc=True)

    ticks_per_second = _UNIT_PER_SECOND[dt.dtype.unit]

    return (dt.astype("int64") // ticks_per_second).astype("int64")


def _map_categories(df: pd.DataFrame, no_unit: pd.Series) -> None:
    """Replace categorical string values with integer values in-place.

    Fully vectorised via :data:`_FLAT_CATEGORY_SERIES` (a MultiIndex
    ``(type, value) → int`` Series): a single :meth:`pandas.Series.reindex`
    resolves every categorical row at C speed.  Unknown ``(type, value)``
    pairs surface as ``NaN`` in the reindex result and are collected into
    a grouped error message.

    Args:
        df: Health records DataFrame; the ``value`` column is mutated
            in-place for rows selected by *no_unit*.
        no_unit: Boolean mask selecting categorical rows (those with no
            ``unit`` value).

    Raises:
        KeyError: If any ``(type, value)`` pair is absent from
            :data:`_FLAT_CATEGORY_MAP`.  The error message lists all
            unknown pairs grouped by type.

    Example::

        _map_categories(df, df["unit"].isna())
        # df.loc[no_unit, "value"] now contains signed integer strings

    """
    sub = df.loc[no_unit, ["type", "value"]]
    if sub.empty:
        return

    keys = pd.MultiIndex.from_arrays(
        [sub["type"].to_numpy(), sub["value"].to_numpy()],
        names=("type", "value"),
    )
    mapped = _FLAT_CATEGORY_SERIES.reindex(keys)

    if mapped.isna().any():
        # Collect missing pairs into a {type: {values}} dict for the error.
        bad = sub[mapped.isna().to_numpy()]
        missing: dict[str, set[str]] = {}
        for t, v in zip(bad["type"], bad["value"], strict=True):
            missing.setdefault(t, set()).add(v)
        raise KeyError(f"Unknown value(s) for type(s): {missing}")

    # Store as string to remain compatible with the rest of the pipeline,
    # which converts ``value`` to ``float64`` after this function returns.
    df.loc[sub.index, "value"] = mapped.astype("int64").astype(str).to_numpy()


def _replace_known_violations(df: pd.DataFrame) -> None:
    """Replace faulty category identifiers.

    Replaces ``type`` for :class:`~..model.base.HKCategoryTypeIdentifier`
    rows whose ``value`` better matches another identifier.
    Identifier/value combinations that should be replaced are kept in
    :const:`~.data_check.KNOWN_CATEGORY_TYPE_VIOLATIONS`.

    Args:
        df: Health records DataFrame; the ``type`` column is mutated
            in-place for rows whose ``(type, value)`` pair is listed as a
            known violation.

    """
    for faulty_type, (
        value_list,
        correct_type,
    ) in KNOWN_CATEGORY_TYPE_VIOLATIONS.items():
        df.loc[(df["type"] == faulty_type) & (df["value"].isin(value_list)), "type"] = (
            correct_type
        )


def _replace_unit_mismatches(df: pd.DataFrame) -> None:
    """Replace known unit mismatches in-place."""
    keys = pd.MultiIndex.from_frame(df[["type", "unit"]])
    mask = keys.isin(KNOWN_UNIT_MISMATCHES.keys())
    df.loc[mask, "unit"] = keys[mask].map(KNOWN_UNIT_MISMATCHES)
