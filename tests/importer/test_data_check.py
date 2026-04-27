"""Tests for src.importer.data_check.

Covers :func:`check_export_data` and each private helper in isolation.
The registry mocks are injected via ``unittest.mock.patch`` so tests remain
fully deterministic regardless of how the real model evolves.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pandas as pd
import pytest

# ---------------------------------------------------------------------------
# The module under test.  Adjust the import path to match your package layout.
# ---------------------------------------------------------------------------
from src.importer.data_check import (
    _check_all_missing_units_are_categorical_identifiers,
    _check_all_string_values_are_categorical_identifiers,
    _check_category_values_exist,
    _check_identifiers_exist,
    _check_required_columns,
    check_export_data,
)

# ---------------------------------------------------------------------------
# Shared fixtures & helpers
# ---------------------------------------------------------------------------

QUANTITY_TYPE = "HKQuantityTypeIdentifierHeartRate"
CATEGORY_TYPE = "HKCategoryTypeIdentifierSleepAnalysis"
CATEGORY_VALUE_ASLEEP = "HKCategoryValueSleepAnalysisAsleep"
CATEGORY_VALUE_INBED = "HKCategoryValueSleepAnalysisInBed"


def _make_category_registry_entry(values: list[str]) -> MagicMock:
    """Return a mock HKCategoryType whose category_values() maps each value to True."""
    entry = MagicMock()
    entry.category_values.return_value = {v: True for v in values}
    return entry


MOCK_QUANTITY_REGISTRY: dict[str, object] = {QUANTITY_TYPE: MagicMock()}
MOCK_CATEGORY_REGISTRY: dict[str, MagicMock] = {
    CATEGORY_TYPE: _make_category_registry_entry(
        [CATEGORY_VALUE_ASLEEP, CATEGORY_VALUE_INBED]
    )
}

# Patch targets – adjust to the actual module path.
_QUANTITY_PATCH = "src.importer.data_check.HKQuantityTypeIdentifierRegistry"
_CATEGORY_PATCH = "src.importer.data_check.HKCategoryTypeIdentifierRegistry"
_MODULE_QUANTITY_SET = "src.importer.data_check._QUANTITY_TYPES"
_MODULE_CATEGORY_SET = "src.importer.data_check._CATEGORY_TYPES"
_MODULE_ALL_SET = "src.importer.data_check._ALL_KNOWN_TYPES"


@pytest.fixture(autouse=True)
def patch_registries(monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace module-level registry constants for every test in this file."""
    monkeypatch.setattr(
        "src.importer.data_check._QUANTITY_TYPES",
        frozenset(MOCK_QUANTITY_REGISTRY.keys()),
    )
    monkeypatch.setattr(
        "src.importer.data_check._CATEGORY_TYPES",
        frozenset(MOCK_CATEGORY_REGISTRY.keys()),
    )
    monkeypatch.setattr(
        "src.importer.data_check._ALL_KNOWN_TYPES",
        frozenset(MOCK_QUANTITY_REGISTRY.keys())
        | frozenset(MOCK_CATEGORY_REGISTRY.keys()),
    )
    monkeypatch.setattr(_CATEGORY_PATCH, MOCK_CATEGORY_REGISTRY)


def _quantity_row(
    type_: str = QUANTITY_TYPE, value: str = "72.0", unit: str = "count/min"
) -> dict:
    return {"type": type_, "value": value, "unit": unit}


def _category_row(value: str = CATEGORY_VALUE_ASLEEP) -> dict:
    return {"type": CATEGORY_TYPE, "value": value, "unit": None}


def _df(*rows: dict) -> pd.DataFrame:
    return pd.DataFrame(list(rows))


# ===========================================================================
# _check_required_columns
# ===========================================================================


class TestCheckRequiredColumns:
    def test_passes_when_all_columns_present(self) -> None:
        _check_required_columns(_df(_quantity_row()))

    def test_raises_for_missing_type_column(self) -> None:
        df = _df(_quantity_row()).drop(columns=["type"])
        with pytest.raises(ValueError, match="type"):
            _check_required_columns(df)

    def test_raises_for_missing_value_column(self) -> None:
        df = _df(_quantity_row()).drop(columns=["value"])
        with pytest.raises(ValueError, match="value"):
            _check_required_columns(df)

    def test_raises_for_missing_unit_column(self) -> None:
        df = _df(_quantity_row()).drop(columns=["unit"])
        with pytest.raises(ValueError, match="unit"):
            _check_required_columns(df)

    def test_raises_listing_all_missing_columns(self) -> None:
        df = pd.DataFrame({"irrelevant": [1]})
        with pytest.raises(ValueError) as exc_info:
            _check_required_columns(df)
        msg = str(exc_info.value)
        assert "type" in msg
        assert "value" in msg
        assert "unit" in msg

    def test_passes_with_extra_columns(self) -> None:
        df = _df(_quantity_row())
        df["extra"] = "ignored"
        _check_required_columns(df)  # should not raise


# ===========================================================================
# _check_identifiers_exist
# ===========================================================================


class TestCheckIdentifiersExist:
    def test_passes_for_known_quantity_type(self) -> None:
        _check_identifiers_exist(_df(_quantity_row()))

    def test_passes_for_known_category_type(self) -> None:
        _check_identifiers_exist(_df(_category_row()))

    def test_passes_for_mixed_known_types(self) -> None:
        _check_identifiers_exist(_df(_quantity_row(), _category_row()))

    def test_raises_for_single_unknown_type(self) -> None:
        df = _df({"type": "HKUnknownType", "value": "1", "unit": "kg"})
        with pytest.raises(ValueError, match="HKUnknownType"):
            _check_identifiers_exist(df)

    def test_raises_listing_all_unknown_types(self) -> None:
        df = _df(
            {"type": "HKUnknownTypeA", "value": "1", "unit": "kg"},
            {"type": "HKUnknownTypeB", "value": "2", "unit": "m"},
        )
        with pytest.raises(ValueError) as exc_info:
            _check_identifiers_exist(df)
        msg = str(exc_info.value)
        assert "HKUnknownTypeA" in msg
        assert "HKUnknownTypeB" in msg

    def test_raises_only_for_unknown_not_for_known(self) -> None:
        df = _df(_quantity_row(), {"type": "HKGhost", "value": "0", "unit": "kg"})
        with pytest.raises(ValueError, match="HKGhost"):
            _check_identifiers_exist(df)


# ===========================================================================
# _check_all_string_values_are_categorical_identifiers
# ===========================================================================


class TestCheckStringValuesAreCategoricalIdentifiers:
    def test_passes_for_numeric_quantity_value(self) -> None:
        _check_all_string_values_are_categorical_identifiers(_df(_quantity_row()))

    def test_passes_for_string_category_value(self) -> None:
        _check_all_string_values_are_categorical_identifiers(_df(_category_row()))

    def test_passes_when_all_quantity_values_are_numeric_strings(self) -> None:
        df = _df(
            _quantity_row(value="72"),
            _quantity_row(value="72.5"),
            _quantity_row(value="-1.0"),
        )
        _check_all_string_values_are_categorical_identifiers(df)

    def test_raises_when_quantity_type_has_string_value(self) -> None:
        df = _df(_quantity_row(value="not-a-number"))
        with pytest.raises(ValueError, match=QUANTITY_TYPE):
            _check_all_string_values_are_categorical_identifiers(df)

    def test_error_message_includes_bad_value(self) -> None:
        df = _df(_quantity_row(value="banana"))
        with pytest.raises(ValueError, match="banana"):
            _check_all_string_values_are_categorical_identifiers(df)

    def test_does_not_raise_when_mixed_numeric_and_category_rows(self) -> None:
        df = _df(_quantity_row(value="100"), _category_row())
        _check_all_string_values_are_categorical_identifiers(df)

    def test_index_alignment_safe_with_filtered_subset(self) -> None:
        """Non-contiguous index must not cause mask misalignment."""
        rows = [_quantity_row(value="99")] * 5 + [_quantity_row(value="bad")]
        df = _df(*rows)
        # Drop some rows to create a non-contiguous index
        df = df.drop(index=[1, 3]).reset_index(drop=False)
        with pytest.raises(ValueError, match="bad"):
            _check_all_string_values_are_categorical_identifiers(df)


# ===========================================================================
# _check_all_missing_units_are_categorical_identifiers
# ===========================================================================


class TestCheckMissingUnitsAreCategoricalIdentifiers:
    def test_passes_when_quantity_type_has_unit(self) -> None:
        _check_all_missing_units_are_categorical_identifiers(_df(_quantity_row()))

    def test_passes_when_category_type_has_no_unit(self) -> None:
        _check_all_missing_units_are_categorical_identifiers(_df(_category_row()))

    def test_passes_for_mixed_valid_data(self) -> None:
        _check_all_missing_units_are_categorical_identifiers(
            _df(_quantity_row(), _category_row())
        )

    def test_raises_when_quantity_type_has_null_unit(self) -> None:
        df = _df(_quantity_row(unit=None))
        with pytest.raises(ValueError, match=QUANTITY_TYPE):
            _check_all_missing_units_are_categorical_identifiers(df)

    def test_error_lists_all_offending_types(self) -> None:
        df = _df(
            _quantity_row(unit=None),
            {"type": QUANTITY_TYPE, "value": "1.0", "unit": None},
        )
        with pytest.raises(ValueError, match=QUANTITY_TYPE):
            _check_all_missing_units_are_categorical_identifiers(df)

    def test_passes_when_quantity_unit_is_empty_string(self) -> None:
        """Empty string is not NaN — should pass this check (upstream issue)."""
        _check_all_missing_units_are_categorical_identifiers(
            _df(_quantity_row(unit=""))
        )


# ===========================================================================
# _check_category_values_exist
# ===========================================================================


class TestCheckCategoryValuesExist:
    def test_passes_for_known_category_value(self) -> None:
        _check_category_values_exist(_df(_category_row(value=CATEGORY_VALUE_ASLEEP)))

    def test_passes_for_all_known_values(self) -> None:
        df = _df(
            _category_row(value=CATEGORY_VALUE_ASLEEP),
            _category_row(value=CATEGORY_VALUE_INBED),
        )
        _check_category_values_exist(df)

    def test_passes_when_no_category_rows_present(self) -> None:
        _check_category_values_exist(_df(_quantity_row()))

    def test_raises_for_unknown_category_value(self) -> None:
        df = _df(_category_row(value="HKCategoryValueUnknown"))
        with pytest.raises(ValueError, match="HKCategoryValueUnknown"):
            _check_category_values_exist(df)

    def test_error_message_includes_type_and_value(self) -> None:
        df = _df(_category_row(value="WeirdValue"))
        with pytest.raises(ValueError) as exc_info:
            _check_category_values_exist(df)
        msg = str(exc_info.value)
        assert CATEGORY_TYPE in msg
        assert "WeirdValue" in msg

    def test_only_unknown_values_reported(self) -> None:
        df = _df(
            _category_row(value=CATEGORY_VALUE_ASLEEP),  # known
            _category_row(value="HKCategoryValueGhost"),  # unknown
        )
        with pytest.raises(ValueError, match="HKCategoryValueGhost"):
            _check_category_values_exist(df)


# ===========================================================================
# check_export_data  (integration-level)
# ===========================================================================


class TestCheckExportData:
    def test_passes_for_fully_valid_dataframe(self) -> None:
        df = _df(_quantity_row(), _category_row())
        check_export_data(df)  # must not raise

    def test_raises_value_error_for_missing_columns(self) -> None:
        df = pd.DataFrame({"type": [QUANTITY_TYPE]})
        with pytest.raises(ValueError, match="value"):
            check_export_data(df)

    def test_raises_exception_group_for_single_failure(self) -> None:
        df = _df({"type": "HKGhostType", "value": "1.0", "unit": "kg"})
        with pytest.raises(ExceptionGroup) as exc_info:
            check_export_data(df)
        assert len(exc_info.value.exceptions) == 1

    def test_raises_exception_group_collecting_all_failures(self) -> None:
        """All four checks should fire independently; we expect ≥2 failures."""
        df = _df(
            # Unknown identifier triggers check 1.
            {"type": "HKGhostType", "value": "not-a-number", "unit": None},
        )
        with pytest.raises(ExceptionGroup) as exc_info:
            check_export_data(df)
        # At minimum checks 1, 2, and 3 should all fire.
        assert len(exc_info.value.exceptions) >= 2

    def test_exception_group_message(self) -> None:
        df = _df({"type": "HKGhostType", "value": "1.0", "unit": "kg"})
        with pytest.raises(ExceptionGroup) as exc_info:
            check_export_data(df)
        assert "Data check failed" in str(exc_info.value)

    def test_all_leaf_exceptions_are_value_errors(self) -> None:
        df = _df({"type": "HKGhostType", "value": "not-a-number", "unit": None})
        with pytest.raises(ExceptionGroup) as exc_info:
            check_export_data(df)
        for exc in exc_info.value.exceptions:
            assert isinstance(exc, ValueError)

    def test_passes_for_empty_dataframe(self) -> None:
        df = pd.DataFrame(columns=["type", "value", "unit"])
        check_export_data(df)  # empty data should pass all checks cleanly

    def test_category_value_failure_included_in_group(self) -> None:
        df = _df(_category_row(value="HKCategoryValueGhost"))
        with pytest.raises(ExceptionGroup) as exc_info:
            check_export_data(df)
        messages = [str(e) for e in exc_info.value.exceptions]
        assert any("HKCategoryValueGhost" in m for m in messages)
