"""Apple Health DataFrame transformation pipeline.

Provides public function `transform` that handles necessary transformations
of raw Apple Health export data.

All public and private functions in this module accept a ``df`` argument that
refers to the same underlying :class:`~pandas.DataFrame` and mutate it
in-place.  No copies are created, keeping peak RAM proportional to the
export size rather than a multiple of it.

Performance notes
-----------------
* :data:`_FLAT_CATEGORY_MAP` is built once at import time as a flat
  ``(type, value) → int`` dictionary, eliminating the two-level lookup that
  the old implementation performed on every categorical row.
* :func:`_handle_categorical_units` scans only the *non-nullable* columns when
  checking for unexpected ``NaN`` values, avoiding a full ``df.isna()``
  materialisation for each call.
* :func:`_timestamps_to_unix` uses :func:`pandas.to_datetime` rather than
  ``Series.astype`` so that both raw string inputs (from the XML parser) and
  already-parsed datetime inputs are handled correctly and without deprecation
  warnings from pandas 3.x.
"""

import logging

import pandas as pd

from ..model import CATEGORICAL_IDENTIFIER_MAPS
from ..model.base import HKGroup, MissingUnit
from .data_check import KNOWN_CATEGORY_TYPE_VIOLATIONS, check_export_data

logger = logging.getLogger(__name__)

# these columns are expected to contain entries without value
COLUMNS_WITHOUT_VALUE = ["unit", "device"]

# ---------------------------------------------------------------------------
# Module-level flat lookup built once at import time.
# Replaces the two-level CATEGORICAL_IDENTIFIER_MAPS[type][value] per-row
# lookup with a single O(1) dict access.
# ---------------------------------------------------------------------------

_FLAT_CATEGORY_MAP: dict[tuple[str, str], int] = {
    (type_name, value_name): int_val
    for type_name, value_map in CATEGORICAL_IDENTIFIER_MAPS.items()
    for value_name, int_val in value_map.items()
}


def transform(df: pd.DataFrame) -> None:
    """Clean and reshape *df* in-place for upload to Redis TimeSeries.

    Applies the following steps in order:

    0. Check input `df` sanity via :func:`~.data_check.check_export_data`.
    1. Drop rows whose ``value`` field is ``NaN``
       (:func:`_drop_null_values`).
    2. Resolve categorical string values to signed integers and assign the
       ``"Categorical"`` sentinel unit
       (:func:`_handle_categorical_units`).
    3. Cast ``value`` to ``float64``.
    4. Convert ``startDate`` and ``endDate`` from strings or timezone-aware
       datetimes to Unix timestamps in whole seconds
       (:func:`_timestamps_to_unix`).
    5. Add a ``group`` column derived from the type registry
       (:meth:`~src.model.base.HKGroup.map_members`).

    Note:
        Not thread-safe — all mutations are applied directly to the shared
        DataFrame without locking.

    Args:
        df: The raw health records DataFrame as produced by the extract step;
            mutated in-place.  ``startDate`` and ``endDate`` may be either
            Apple Health timestamp strings (``"2024-01-01 00:00:00 +0000"``)
            or pandas datetime objects.

    Example::

        transform(df)
        # df["startDate"] and df["endDate"] are now int64 Unix timestamps

    """
    check_export_data(df)

    logger.info("Transforming export data...")
    _drop_null_values(df)
    _handle_categorical_units(df)
    df["value"] = df["value"].astype("float64")
    df["startDate"] = _timestamps_to_unix(df["startDate"])
    df["endDate"] = _timestamps_to_unix(df["endDate"])
    df["group"] = df["type"].map(HKGroup.map_members())


def _drop_null_values(df: pd.DataFrame) -> None:
    """Drop rows with a ``NaN`` ``value`` field and log the count.

    Mutates *df* in-place.

    Note:
        If *all* rows have a ``NaN`` ``value``, *df* will be empty after
        this call.  Subsequent steps handle an empty DataFrame gracefully.

    Args:
        df: Health records DataFrame; rows with a ``NaN`` ``value`` are
            removed.

    Example::

        before = len(df)
        _drop_null_values(df)
        print(f"Dropped {before - len(df)} rows")

    """
    null_mask = pd.isna(df["value"])
    n_dropped = int(null_mask.sum())
    if n_dropped:
        df.drop(index=df.index[null_mask], inplace=True)  # noqa: PD002
        logger.warning("Dropped %d rows with missing 'value'.", n_dropped)


def _handle_categorical_units(df: pd.DataFrame) -> None:
    """Assign integer values and a sentinel unit to categorical records.

    Rows without a ``unit`` value are treated as categorical.  Their string
    ``value`` is resolved to a signed integer via :func:`_map_categories`, and
    their ``unit`` is set to :attr:`~model.base.MissingUnit.CATEGORICAL`.
    For ``type``/``value`` pairs in
    :const:`~.data_check.KNOWN_CATEGORY_TYPE_VIOLATIONS` the ``type`` is
    updated before mapping.

    This function only scans columns that are *not* in
    :data:`COLUMNS_WITHOUT_VALUE` for unexpected ``NaN`` values, avoiding a
    full ``df.isna()`` materialisation.

    Note:
        A warning is logged (and the row left unmodified) if a ``type`` or
        ``value`` string is absent from the categorical registry.

    Args:
        df: Health records DataFrame; the ``value`` and ``unit`` columns are
            mutated in-place for categorical rows.

    Raises:
        NotImplementedError: If ``NaN`` values are found in any column other
            than those listed in :data:`COLUMNS_WITHOUT_VALUE`, indicating an
            unexpected schema change.
        ValueError: If a row without a unit has a numeric ``value``; only
            categorical string values are expected in that position.

    Example::

        _handle_categorical_units(df)
        # Categorical rows now have integer values and unit == "Categorical"

    """
    # Targeted scan: only check columns that should never be null.
    unexpected = [
        col
        for col in df.columns
        if col not in COLUMNS_WITHOUT_VALUE and df[col].isna().any()
    ]
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

    Integer floor division by 10⁹ avoids floating-point rounding errors and
    ensures the result is always an exact ``int64``.

    Args:
        series: A pandas Series whose values are either Apple Health timestamp
            strings or ``datetime64`` objects.

    Returns:
        An ``int64`` Series of Unix timestamps in **seconds**.

    Example::

        unix_ts = _timestamps_to_unix(df["startDate"])
        # unix_ts.dtype == int64

    """
    return (pd.to_datetime(series, utc=True).astype("int64") // 1_000_000_000).astype(
        "int64"
    )


def _map_categories(df: pd.DataFrame, no_unit: pd.Series) -> None:
    """Replace categorical string values with integer values in-place.

    Uses the module-level :data:`_FLAT_CATEGORY_MAP` for a single O(1) dict
    lookup per row rather than the two-level
    ``CATEGORICAL_IDENTIFIER_MAPS[type][value]`` access.  All errors are
    accumulated before raising so the caller sees the complete set of unknown
    ``(type, value)`` pairs.

    Note:
        The categorical slice is expected to be small relative to the full
        DataFrame; the Python loop overhead is therefore acceptable.

    Args:
        df: Health records DataFrame; the ``value`` column is mutated in-place
            for rows selected by *no_unit*.
        no_unit: Boolean mask selecting categorical rows (those with no
            ``unit`` value).

    Raises:
        KeyError: If any ``(type, value)`` pair is absent from
            :data:`_FLAT_CATEGORY_MAP`.  The error message lists all unknown
            pairs grouped by type.

    Example::

        _map_categories(df, df["unit"].isna())
        # df.loc[no_unit, "value"] now contains signed integer strings

    """
    categorical_slice = df.loc[no_unit, ["type", "value"]]

    result: list[str] = []
    missing: dict[str, set[str]] = {}
    for type_, value in zip(
        categorical_slice["type"], categorical_slice["value"], strict=True
    ):
        key = (type_, value)
        if key in _FLAT_CATEGORY_MAP:
            result.append(str(_FLAT_CATEGORY_MAP[key]))
        else:
            missing.setdefault(type_, set()).add(value)

    if missing:
        raise KeyError(f"Unknown value(s) for type(s): {missing}")

    df.loc[categorical_slice.index, "value"] = result


def _replace_known_violations(df: pd.DataFrame) -> None:
    """Replace faulty category identifiers.

    Replaces ``type`` for :class:`~..model.base.HKCategoryTypeIdentifier`
    rows if the ``value`` better matches another identifier.
    Identifier/value combinations that should be replaced are kept in
    :const:`~.data_check.KNOWN_CATEGORY_TYPE_VIOLATIONS`.

    Args:
        df: Health records DataFrame; the ``type`` column is mutated in-place
            for rows whose ``(type, value)`` pair is listed as a known
            violation.

    """
    for faulty_type, (
        value_list,
        correct_type,
    ) in KNOWN_CATEGORY_TYPE_VIOLATIONS.items():
        df.loc[(df["type"] == faulty_type) & (df["value"].isin(value_list)), "type"] = (
            correct_type
        )
