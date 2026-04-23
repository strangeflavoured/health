"""Apple Health DataFrame transformation pipeline.

Provides public function `transform` that handles necessary transformations
of raw Apple Health export data.

All public and private functions in this module accept a ``df`` argument that
refers to the same underlying :class:`~pandas.DataFrame` and mutate it
in-place.  No copies are created, keeping peak RAM proportional to the
export size rather than a multiple of it.
"""

import logging

import pandas as pd

from ..model import CATEGORICAL_IDENTIFIER_MAPS
from ..model.base import MissingUnit

logger = logging.getLogger(__name__)

# these columns are expected to contain entries without value
COLUMNS_WITHOUT_VALUE = ["unit", "device"]


def transform(df: pd.DataFrame) -> None:
    """Clean and reshape *df* in-place for upload to Redis TimeSeries.

    Applies the following steps in order:

    1. Drop rows whose ``value`` field is ``NaN`` (:func:`_drop_null_values`).
    2. Resolve categorical string values to signed integers or NaN and assign the
       ``"Categorical"`` sentinel unit (:func:`_handle_categorical_units`).
    3. Convert ``startDate`` and ``endDate`` from ``datetime64`` to Unix
       timestamps in whole seconds (:func:`_timestamps_to_unix`).

    Note:
        Not thread-safe -- all mutations are applied directly to the shared
        DataFrame without locking.

    Args:
        df: The raw health records DataFrame as produced by the extract step;
            mutated in-place.

    Example::

        transform(df)
        # df["startDate"] and df["endDate"] are now int64 Unix timestamps

    """
    logger.info("Transforming export data...")
    _drop_null_values(df)
    _handle_categorical_units(df)
    df["value"] = df["value"].astype("float64")
    df["startDate"] = _timestamps_to_unix(df["startDate"])
    df["endDate"] = _timestamps_to_unix(df["endDate"])


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
        df = df.drop(index=df.index[null_mask])
        logger.warning("Dropped %d rows with missing 'value'.", n_dropped)

    return df


def _handle_categorical_units(df: pd.DataFrame) -> None:
    """Assign integer values and a sentinel unit to categorical records.

    Rows without a ``unit`` value are treated as categorical.  Their string ``value``
    is resolved to a signed integer/NaN via
    :data:`~.categorical.categorical_identifiers`, and their ``unit`` is set to
    :attr:`~.categorical.MissingUnit.CATEGORICAL`.

    Note:
        A warning is logged (and the row left unmodified) if a ``type`` or
        ``value`` string is absent from the categorical registry.

    Args:
        df: Health records DataFrame; the ``value`` and ``unit`` columns are
            mutated in-place for categorical rows.

    Raises:
        NotImplementedError: If ``NaN`` values are found in any column other
            than ``unit``, indicating an unexpected schema change.

        ValueError: If a row without a unit has a numeric ``value``; only
            categorical string values are expected in that position.

    Example::

        _handle_categorical_units(df)
        # Categorical rows now have integer values and unit == "Categorical"

    """
    null_columns: pd.Index = df.columns[df.isna().any()]
    if not null_columns.isin(COLUMNS_WITHOUT_VALUE).all():
        unexpected = null_columns.difference(COLUMNS_WITHOUT_VALUE).tolist()
        raise NotImplementedError(
            f"Unexpected columns NaN (schema may have changed): {unexpected}"
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

    _map_categories(df, no_unit)
    df.loc[no_unit, "unit"] = MissingUnit.CATEGORICAL.value


def _timestamps_to_unix(series: pd.Series) -> pd.Series:
    """Convert a ``datetime64`` Series to Unix timestamps in whole seconds.

    Divides the nanosecond epoch integer representation by 10⁹ using integer
    floor division to avoid floating-point rounding errors.

    Args:
        series: A ``datetime64[ns]`` pandas Series.

    Returns:
        An ``int64`` Series of Unix timestamps in **seconds**.

    Example::

        unix_ts = _timestamps_to_unix(df["startDate"])
        # unix_ts.dtype == int64

    """
    return (series.astype("int64") // 1_000_000_000).astype("int64")


def _map_categories(df: pd.DataFrame, no_unit: pd.Series) -> None:
    """Replace categorical string values with signed integer values in-place.

    Note:
        The :meth:`~pd.DataFrame.groupby` call creates a temporary copy of the
        categorical slice; the slice size is expected to be small relative
        to the full DataFrame.

    Args:
        df: Health records DataFrame; the ``value`` column is mutated in-place
            for rows selected by *no_unit*.
        no_unit: Boolean mask selecting categorical rows (those with no
            ``unit`` value).

    Raises:
        KeyError: If a ``type`` string is absent from
            :data:`~categorical.categorical_identifier_maps`, or if a ``value``
            string is not a valid member name of the corresponding
            :class:`~categorical.HKCategoryTypeIdentifier`.

    Example::

        _map_categories(df, df["unit"].isna())
        # df.loc[no_unit, "value"] now contains signed numbers

    """
    categorical_slice = df.loc[no_unit, ["type", "value"]]

    result: list[str] = []
    missing: dict[str, set[str]] = {}
    for type_, value in zip(
        categorical_slice["type"], categorical_slice["value"], strict=True
    ):
        try:
            result.append(str(CATEGORICAL_IDENTIFIER_MAPS[type_][value]))
        except KeyError:
            missing.setdefault(type_, set()).add(value)
            result.append("")  # placeholder, unused if raising below

    if missing:
        raise KeyError(f"Unknown value(s) for type(s): {missing}")

    df.loc[categorical_slice.index, "value"] = result
