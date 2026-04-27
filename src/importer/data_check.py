"""Data sanity checks performed before uploading Apple Health export data to Redis.

This module validates a parsed Apple Health export DataFrame against the registered
type identifiers and category value mappings defined in :mod:`model`.  All four
checks are independent; :func:`check_export_data` collects every failure and raises
a single :class:`ExceptionGroup` so callers see the complete picture rather than
stopping at the first problem.

Typical usage::

    check_export_data(df)          # raises ExceptionGroup on any violation
"""

import logging
from types import MappingProxyType

import pandas as pd

from ..model import (
    HKCategoryTypeIdentifierRegistry,
    HKMiscTypeIdentifierRegistry,
    HKQuantityTypeIdentifierRegistry,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level constants – registries are iterated once at import time so that
# repeated calls to the check functions do not redundantly rebuild sets.
# ---------------------------------------------------------------------------

_CATEGORY_TYPES: frozenset[str] = frozenset(HKCategoryTypeIdentifierRegistry.keys())
_QUANTITY_TYPES: frozenset[str] = frozenset(HKQuantityTypeIdentifierRegistry.keys())
_MISC_TYPES: frozenset[str] = frozenset(HKMiscTypeIdentifierRegistry.keys())
_ALL_KNOWN_TYPES: frozenset[str] = _CATEGORY_TYPES | _QUANTITY_TYPES | _MISC_TYPES

# This is the source of truth to work around wrong category types
# key(str): faulty type
# value(tuple): first element is a list of faulty values for the type
# second element is the type that should be used instead
KNOWN_CATEGORY_TYPE_VIOLATIONS: MappingProxyType[str, tuple[list[str], str]] = (
    MappingProxyType(
        {
            "HKCategoryTypeIdentifierAudioExposureEvent": (
                ["HKCategoryValueEnvironmentalAudioExposureEventMomentaryLimit"],
                "HKCategoryTypeIdentifierEnvironmentalAudioExposureEvent",
            ),
        }
    )
)


class DataSanityError(ValueError):
    """Raised when data checks fail."""

    pass


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _check_required_columns(df: pd.DataFrame) -> None:
    """Verify that the DataFrame contains the columns expected by all checks.

    Args:
        df: The export DataFrame to validate.

    Raises:
        ValueError: If one or more required columns are absent.

    """
    required = {"type", "value", "unit"}
    missing = required - set(df.columns)
    if missing:
        raise DataSanityError(
            f"DataFrame is missing required column(s): {sorted(missing)}."
        )


def _check_identifiers_exist(df: pd.DataFrame) -> None:
    """Assert that every ``type`` value in *df* is a registered HK identifier.

    An identifier must appear in either :data:`HKQuantityTypeIdentifierRegistry`
    or :data:`HKCategoryTypeIdentifierRegistry`.  Unrecognised identifiers indicate
    that the model is out of date or that the export contains unexpected record types.

    Args:
        df: The export DataFrame.  Must contain a ``type`` column.

    Raises:
        ValueError: If one or more identifiers are not present in either registry.

    """
    identifiers = df["type"].unique()
    unknown_mask = ~pd.Index(identifiers).isin(_ALL_KNOWN_TYPES)
    if unknown_mask.any():
        unidentified = ", ".join(identifiers[unknown_mask])
        raise DataSanityError(
            f"Could not find the following identifiers in model: [{unidentified}]."
        )


def _check_all_string_values_are_categorical_identifiers(df: pd.DataFrame) -> None:
    """Assert that non-numeric ``value`` entries belong only to category-type rows.

    Numeric values are expected for quantity-type records.  A non-numeric value is
    acceptable only when the corresponding ``type`` is registered in
    :data:`HKCategoryTypeIdentifierRegistry`, or is NaN and entry can be dropped.

    Args:
        df: The export DataFrame.  Must contain ``type`` and ``value`` columns.

    Raises:
        ValueError: If any quantity-type row carries a non-numeric value, with a
            mapping of offending type → list of bad values included in the message.

    """
    df = df[~df["value"].isna()]
    is_non_numeric = pd.to_numeric(df["value"], errors="coerce").isna()
    non_numeric_df = df[is_non_numeric]

    non_numeric_types = non_numeric_df["type"].unique()
    is_category = pd.Index(non_numeric_types).isin(_CATEGORY_TYPES)

    if not is_category.all():
        bad_types = set(non_numeric_types[~is_category])
        bad_rows = df[is_non_numeric & df["type"].isin(bad_types)]
        bad_values: dict[str, list[str]] = {
            row.Index: list(row.unique)
            for row in bad_rows.groupby("type")["value"].agg(["unique"]).itertuples()
        }
        raise DataSanityError(
            f"The following non-category type(s) have non-numeric values: {bad_values}."
        )


def _check_all_missing_units_are_categorical_identifiers(df: pd.DataFrame) -> None:
    """Assert that only category-type rows may have a missing ``unit``.

    Quantity-type records are always expected to carry a unit string.  A ``NaN``
    unit on a quantity-type row indicates a parsing problem upstream.

    Args:
        df: The export DataFrame.  Must contain ``type`` and ``unit`` columns.

    Raises:
        ValueError: If any quantity-type row has a ``NaN`` unit value.

    """
    missing_unit_types = df.loc[df["unit"].isna(), "type"].unique()
    is_category = pd.Index(missing_unit_types).isin(_CATEGORY_TYPES)
    if not is_category.all():
        offending = list(missing_unit_types[~is_category])
        raise DataSanityError(
            f"The following non-category identifiers are missing a unit: {offending}."
        )


def _check_category_values_exist(df: pd.DataFrame) -> None:
    """Assert that every category-type ``value`` is a registered category value.

    Each category identifier maps to a fixed set of permitted string values defined
    in its :class:`~model.HKCategoryType` entry.  This check catches export data
    that references unknown enum-style values, which would be rejected during upload.

    Args:
        df: The export DataFrame.  Must contain ``type`` and ``value`` columns.

    Raises:
        ValueError: If any category-type row contains an unrecognised value, with a
            mapping of offending type → list of unknown values in the message.

    """
    categorical_df = df[df["type"].isin(_CATEGORY_TYPES)]
    unknown: dict[str, list[str]] = {}

    for row in categorical_df.groupby("type")["value"].agg(["unique"]).itertuples():
        known_values: set[str] = set(
            HKCategoryTypeIdentifierRegistry[row.Index].category_values().keys()
        )
        bad_mask = ~pd.Index(row.unique).isin(known_values)
        if bad_mask.any():
            bad_values = row.unique[bad_mask]

            # skip handled issues
            if KNOWN_CATEGORY_TYPE_VIOLATIONS.get(row.Index, None):
                bad_values = set(bad_values).difference(
                    KNOWN_CATEGORY_TYPE_VIOLATIONS[row.Index][0]
                )

            if bad_values:
                unknown[row.Index] = list(bad_values)

    if unknown:
        raise DataSanityError(
            f"Could not find the category value(s) for identifier(s): {unknown}."
        )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def check_export_data(df: pd.DataFrame) -> None:
    """Run all data sanity checks against an Apple Health export DataFrame.

    Executes four independent validation passes and collects every failure before
    raising, so the caller receives a complete picture of all problems rather than
    stopping at the first one.  The checks are:

    1. **Identifier existence** – every ``type`` value is a registered HK identifier.
    2. **String value legality** – non-numeric values only appear on category types.
    3. **Missing unit legality** – ``NaN`` units only appear on category types.
    4. **Category value existence** – every category value is in the known value set.

    Args:
        df: A parsed Apple Health export DataFrame with at minimum the columns
            ``type`` (str), ``value`` (str | numeric), and ``unit`` (str | NaN).

    Raises:
        ValueError: If required columns are absent from *df*.
        ExceptionGroup: Containing one :class:`ValueError` per failed check when
            one or more checks do not pass.  The group message is
            ``"Data check failed with the following exception(s):"``.

    Example::

        import pandas as pd
        from health_importer.sanity import check_export_data

        df = pd.read_parquet("export.parquet")
        check_export_data(df)   # raises ExceptionGroup if anything is wrong

    """
    logger.info("Checking export data...")
    _check_required_columns(df)

    checks = [
        _check_identifiers_exist,
        _check_all_string_values_are_categorical_identifiers,
        _check_all_missing_units_are_categorical_identifiers,
        _check_category_values_exist,
    ]

    exceptions: list[DataSanityError] = []
    for check in checks:
        try:
            check(df)
        except DataSanityError as exc:
            exceptions.append(exc)

    if exceptions:
        raise ExceptionGroup(
            "Data check failed with the following exception(s):", exceptions
        )
    else:
        logger.info("Data check finished successfully.")
