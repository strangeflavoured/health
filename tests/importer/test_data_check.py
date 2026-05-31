"""Tests for src.importer.data_check.

Covers :func:`check_export_data` and each private helper in isolation.
The registry and unit-map mocks are injected via ``monkeypatch`` so tests
remain fully deterministic regardless of how the real model evolves.

Tests marked ``xfail`` document bugs in the production code; once the
underlying bug is fixed they will report ``XPASS`` (strict=True) and force
the marker to be removed.
"""

from __future__ import annotations

from types import MappingProxyType
from unittest.mock import MagicMock

import pandas as pd
import pytest

# ---------------------------------------------------------------------------
# The module under test.  Adjust the import path to match your package layout.
# ---------------------------------------------------------------------------
from src.importer.data_check import (
    DataSanityError,
    _check_all_missing_units_are_categorical_identifiers,
    _check_all_string_values_are_categorical_identifiers,
    _check_category_values_exist,
    _check_identifiers_exist,
    _check_required_columns,
    _check_units,
    check_export_data,
)

# MissingUnit lives in the model package; adjust if your layout differs.
from src.model.base import MissingUnit

CATEGORICAL = MissingUnit.CATEGORICAL.value

# ---------------------------------------------------------------------------
# Identifier constants
# ---------------------------------------------------------------------------

# Quantity types (multiple, to cover unit-map variety)
QUANTITY_TYPE = "HKQuantityTypeIdentifierHeartRate"  # primary; kept as alias
QUANTITY_TYPE_BODY_MASS = "HKQuantityTypeIdentifierBodyMass"
QUANTITY_TYPE_HEIGHT = "HKQuantityTypeIdentifierHeight"
QUANTITY_TYPE_STEP_COUNT = "HKQuantityTypeIdentifierStepCount"

# Category types
CATEGORY_TYPE = "HKCategoryTypeIdentifierSleepAnalysis"  # primary
CATEGORY_TYPE_MINDFUL = "HKCategoryTypeIdentifierMindfulSession"

# Misc types
MISC_TYPE = "HKWorkoutTypeIdentifier"

# Category values
CATEGORY_VALUE_ASLEEP = "HKCategoryValueSleepAnalysisAsleep"
CATEGORY_VALUE_INBED = "HKCategoryValueSleepAnalysisInBed"
CATEGORY_VALUE_MINDFUL = "HKCategoryValueMindful"
CATEGORY_VALUE_LEGACY_DREAMING = "HKCategoryValueLegacyDreaming"


# ---------------------------------------------------------------------------
# Shared fixtures & helpers
# ---------------------------------------------------------------------------


def _make_category_registry_entry(values: list[str]) -> MagicMock:
    """Return a mock HKCategoryType whose category_values() maps each value to True."""
    entry = MagicMock()
    entry.category_values.return_value = {v: True for v in values}
    return entry


MOCK_QUANTITY_REGISTRY: dict[str, object] = {
    QUANTITY_TYPE: MagicMock(),
    QUANTITY_TYPE_BODY_MASS: MagicMock(),
    QUANTITY_TYPE_HEIGHT: MagicMock(),
    QUANTITY_TYPE_STEP_COUNT: MagicMock(),
}
MOCK_CATEGORY_REGISTRY: dict[str, MagicMock] = {
    CATEGORY_TYPE: _make_category_registry_entry(
        [CATEGORY_VALUE_ASLEEP, CATEGORY_VALUE_INBED]
    ),
    CATEGORY_TYPE_MINDFUL: _make_category_registry_entry([CATEGORY_VALUE_MINDFUL]),
}
MOCK_MISC_REGISTRY: dict[str, object] = {MISC_TYPE: MagicMock()}

_DEFAULT_UNIT_MAP: dict[str, str] = {
    QUANTITY_TYPE: "count/min",
    QUANTITY_TYPE_BODY_MASS: "kg",
    QUANTITY_TYPE_HEIGHT: "cm",
    QUANTITY_TYPE_STEP_COUNT: "count",
    CATEGORY_TYPE: CATEGORICAL,
    CATEGORY_TYPE_MINDFUL: CATEGORICAL,
}


class _PermissiveUnitMap(dict):
    """UNIT_MAP stand-in that returns CATEGORICAL for missing keys.

    Used as the default so tests with ad-hoc unknown types ("HKGhostType")
    don't fall foul of the KeyError bug in ``_check_units``. Unknown types
    are treated as categorical, which makes them transparent to the unit
    check. Tests targeting the unit check explicitly use a strict dict via
    monkeypatch where needed.
    """

    def __getitem__(self, key: str) -> str:
        try:
            return super().__getitem__(key)
        except KeyError:
            return CATEGORICAL


@pytest.fixture(autouse=True)
def patch_registries(monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace module-level registry constants and UNIT_MAP for every test."""
    monkeypatch.setattr(
        "src.importer.data_check._QUANTITY_TYPES",
        frozenset(MOCK_QUANTITY_REGISTRY.keys()),
    )
    monkeypatch.setattr(
        "src.importer.data_check._CATEGORY_TYPES",
        frozenset(MOCK_CATEGORY_REGISTRY.keys()),
    )
    monkeypatch.setattr(
        "src.importer.data_check._MISC_TYPES",
        frozenset(MOCK_MISC_REGISTRY.keys()),
    )
    monkeypatch.setattr(
        "src.importer.data_check._ALL_KNOWN_TYPES",
        frozenset(MOCK_QUANTITY_REGISTRY.keys())
        | frozenset(MOCK_CATEGORY_REGISTRY.keys())
        | frozenset(MOCK_MISC_REGISTRY.keys()),
    )
    monkeypatch.setattr(
        "src.importer.data_check.HKCategoryTypeIdentifierRegistry",
        MOCK_CATEGORY_REGISTRY,
    )
    monkeypatch.setattr(
        "src.importer.data_check.UNIT_MAP",
        _PermissiveUnitMap(_DEFAULT_UNIT_MAP),
    )


@pytest.fixture
def violations_map(monkeypatch: pytest.MonkeyPatch) -> MappingProxyType:
    """Override KNOWN_CATEGORY_TYPE_VIOLATIONS with a small fake."""
    fake = MappingProxyType(
        {
            CATEGORY_TYPE: ([CATEGORY_VALUE_LEGACY_DREAMING], CATEGORY_TYPE_MINDFUL),
        }
    )
    monkeypatch.setattr("src.importer.data_check.KNOWN_CATEGORY_TYPE_VIOLATIONS", fake)
    return fake


def _quantity_row(
    type_: str = QUANTITY_TYPE, value: str = "72.0", unit: str = "count/min"
) -> dict:
    return {"type": type_, "value": value, "unit": unit}


def _category_row(
    value: str = CATEGORY_VALUE_ASLEEP, type_: str = CATEGORY_TYPE
) -> dict:
    return {"type": type_, "value": value, "unit": None}


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
        with pytest.raises(DataSanityError, match="type"):
            _check_required_columns(df)

    def test_raises_for_missing_value_column(self) -> None:
        df = _df(_quantity_row()).drop(columns=["value"])
        with pytest.raises(DataSanityError, match="value"):
            _check_required_columns(df)

    def test_raises_for_missing_unit_column(self) -> None:
        df = _df(_quantity_row()).drop(columns=["unit"])
        with pytest.raises(DataSanityError, match="unit"):
            _check_required_columns(df)

    def test_raises_listing_all_missing_columns(self) -> None:
        df = pd.DataFrame({"irrelevant": [1]})
        with pytest.raises(DataSanityError) as exc_info:
            _check_required_columns(df)
        msg = str(exc_info.value)
        assert "type" in msg
        assert "value" in msg
        assert "unit" in msg

    def test_passes_with_extra_columns(self) -> None:
        df = _df(_quantity_row())
        df["extra"] = "ignored"
        _check_required_columns(df)  # should not raise

    def test_passes_for_empty_dataframe_with_correct_columns(self) -> None:
        df = pd.DataFrame(columns=["type", "value", "unit"])
        _check_required_columns(df)  # empty data has all required columns

    def test_missing_columns_are_sorted_in_message(self) -> None:
        # sorted({"unit", "value"}) == ["unit", "value"] alphabetically.
        df = pd.DataFrame({"type": ["x"]})
        with pytest.raises(DataSanityError) as exc_info:
            _check_required_columns(df)
        msg = str(exc_info.value)
        assert msg.find("'unit'") < msg.find("'value'")


# ===========================================================================
# _check_identifiers_exist
# ===========================================================================


class TestCheckIdentifiersExist:
    def test_passes_for_known_quantity_type(self) -> None:
        _check_identifiers_exist(_df(_quantity_row()))

    def test_passes_for_known_category_type(self) -> None:
        _check_identifiers_exist(_df(_category_row()))

    def test_passes_for_known_misc_type(self) -> None:
        df = _df({"type": MISC_TYPE, "value": "x", "unit": "count"})
        _check_identifiers_exist(df)

    def test_passes_for_mixed_known_types(self) -> None:
        _check_identifiers_exist(_df(_quantity_row(), _category_row()))

    def test_raises_for_single_unknown_type(self) -> None:
        df = _df({"type": "HKUnknownType", "value": "1", "unit": "kg"})
        with pytest.raises(DataSanityError, match="HKUnknownType"):
            _check_identifiers_exist(df)

    def test_raises_listing_all_unknown_types(self) -> None:
        df = _df(
            {"type": "HKUnknownTypeA", "value": "1", "unit": "kg"},
            {"type": "HKUnknownTypeB", "value": "2", "unit": "m"},
        )
        with pytest.raises(DataSanityError) as exc_info:
            _check_identifiers_exist(df)
        msg = str(exc_info.value)
        assert "HKUnknownTypeA" in msg
        assert "HKUnknownTypeB" in msg

    def test_raises_only_for_unknown_not_for_known(self) -> None:
        df = _df(_quantity_row(), {"type": "HKGhost", "value": "0", "unit": "kg"})
        with pytest.raises(DataSanityError, match="HKGhost"):
            _check_identifiers_exist(df)

    def test_passes_for_empty_dataframe(self) -> None:
        df = pd.DataFrame({"type": [], "value": [], "unit": []})
        _check_identifiers_exist(df)

    def test_nan_type_raises_value_error_not_typeerror(self) -> None:
        df = _df({"type": float("nan"), "value": "1", "unit": "x"})
        with pytest.raises(DataSanityError):
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
        with pytest.raises(DataSanityError, match=QUANTITY_TYPE):
            _check_all_string_values_are_categorical_identifiers(df)

    def test_error_message_includes_bad_value(self) -> None:
        df = _df(_quantity_row(value="banana"))
        with pytest.raises(DataSanityError, match="banana"):
            _check_all_string_values_are_categorical_identifiers(df)

    def test_does_not_raise_when_mixed_numeric_and_category_rows(self) -> None:
        df = _df(_quantity_row(value="100"), _category_row())
        _check_all_string_values_are_categorical_identifiers(df)

    def test_index_alignment_safe_with_filtered_subset(self) -> None:
        """Non-contiguous index must not cause mask misalignment."""
        rows = [_quantity_row(value="99")] * 5 + [_quantity_row(value="bad")]
        df = _df(*rows)
        df = df.drop(index=[1, 3]).reset_index(drop=False)
        with pytest.raises(DataSanityError, match="bad"):
            _check_all_string_values_are_categorical_identifiers(df)

    def test_nan_values_are_filtered_before_check(self) -> None:
        # NaN quantity values are dropped first; not flagged as non-numeric.
        df = _df(
            _quantity_row(value=float("nan")),
            _quantity_row(value="72"),
        )
        _check_all_string_values_are_categorical_identifiers(df)

    def test_raises_for_misc_type_with_string_value(self) -> None:
        df = _df({"type": MISC_TYPE, "value": "some-string", "unit": "count"})
        with pytest.raises(DataSanityError, match=MISC_TYPE):
            _check_all_string_values_are_categorical_identifiers(df)

    def test_passes_for_empty_dataframe(self) -> None:
        df = pd.DataFrame({"type": [], "value": [], "unit": []})
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
        with pytest.raises(DataSanityError, match=QUANTITY_TYPE):
            _check_all_missing_units_are_categorical_identifiers(df)

    def test_error_lists_all_offending_types(self) -> None:
        df = _df(
            _quantity_row(unit=None),
            _quantity_row(type_=QUANTITY_TYPE_BODY_MASS, value="70", unit=None),
        )
        with pytest.raises(DataSanityError) as exc_info:
            _check_all_missing_units_are_categorical_identifiers(df)
        msg = str(exc_info.value)
        assert QUANTITY_TYPE in msg
        assert QUANTITY_TYPE_BODY_MASS in msg

    def test_passes_when_quantity_unit_is_empty_string(self) -> None:
        """Empty string is not NaN — should pass this check (upstream issue)."""
        _check_all_missing_units_are_categorical_identifiers(
            _df(_quantity_row(unit=""))
        )

    def test_raises_for_misc_type_with_null_unit(self) -> None:
        df = _df({"type": MISC_TYPE, "value": "x", "unit": None})
        with pytest.raises(DataSanityError, match=MISC_TYPE):
            _check_all_missing_units_are_categorical_identifiers(df)

    def test_passes_for_empty_dataframe(self) -> None:
        df = pd.DataFrame({"type": [], "value": [], "unit": []})
        _check_all_missing_units_are_categorical_identifiers(df)


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
        with pytest.raises(DataSanityError, match="HKCategoryValueUnknown"):
            _check_category_values_exist(df)

    def test_error_message_includes_type_and_value(self) -> None:
        df = _df(_category_row(value="WeirdValue"))
        with pytest.raises(DataSanityError) as exc_info:
            _check_category_values_exist(df)
        msg = str(exc_info.value)
        assert CATEGORY_TYPE in msg
        assert "WeirdValue" in msg

    def test_only_unknown_values_reported(self) -> None:
        df = _df(
            _category_row(value=CATEGORY_VALUE_ASLEEP),  # known
            _category_row(value="HKCategoryValueGhost"),  # unknown
        )
        with pytest.raises(DataSanityError, match="HKCategoryValueGhost"):
            _check_category_values_exist(df)

    def test_known_violations_are_suppressed(self, violations_map) -> None:  # noqa: ARG002
        df = _df(_category_row(value=CATEGORY_VALUE_LEGACY_DREAMING))
        _check_category_values_exist(df)  # should not raise

    def test_known_violations_do_not_mask_other_unknowns(self, violations_map) -> None:  # noqa: ARG002
        df = _df(
            _category_row(value=CATEGORY_VALUE_LEGACY_DREAMING),  # suppressed
            _category_row(value="HKCategoryValueTrulyUnknown"),  # still flagged
        )
        with pytest.raises(DataSanityError) as exc_info:
            _check_category_values_exist(df)
        msg = str(exc_info.value)
        assert "HKCategoryValueTrulyUnknown" in msg
        assert CATEGORY_VALUE_LEGACY_DREAMING not in msg

    def test_raises_for_multiple_category_types_with_unknown_values(self) -> None:
        df = _df(
            _category_row(value="HKCategoryValueDreaming"),
            _category_row(value="HKCategoryValueElated", type_=CATEGORY_TYPE_MINDFUL),
        )
        with pytest.raises(DataSanityError) as exc_info:
            _check_category_values_exist(df)
        msg = str(exc_info.value)
        assert CATEGORY_TYPE in msg
        assert CATEGORY_TYPE_MINDFUL in msg

    def test_passes_for_empty_dataframe(self) -> None:
        df = pd.DataFrame({"type": [], "value": [], "unit": []})
        _check_category_values_exist(df)


# ===========================================================================
# _check_units
# ===========================================================================


class TestCheckUnits:
    # -- Happy path ---------------------------------------------------------

    def test_passes_when_all_units_correct(self) -> None:
        df = _df(
            _quantity_row(),
            _quantity_row(type_=QUANTITY_TYPE_BODY_MASS, value="70", unit="kg"),
            _quantity_row(type_=QUANTITY_TYPE_HEIGHT, value="180", unit="cm"),
        )
        _check_units(df)

    def test_passes_for_empty_dataframe(self) -> None:
        df = pd.DataFrame({"type": [], "value": [], "unit": []})
        _check_units(df)

    def test_passes_for_many_rows_one_type(self) -> None:
        df = _df(
            *[
                _quantity_row(
                    type_=QUANTITY_TYPE_STEP_COUNT, value=str(i), unit="count"
                )
                for i in range(500)
            ]
        )
        _check_units(df)

    # -- Unit mismatch ------------------------------------------------------

    def test_raises_for_single_type_unit_mismatch(self) -> None:
        df = _df(
            _quantity_row(type_=QUANTITY_TYPE_BODY_MASS, value="70", unit="lb"),
            _quantity_row(type_=QUANTITY_TYPE_BODY_MASS, value="71", unit="lb"),
        )
        with pytest.raises(ExceptionGroup) as exc_info:
            _check_units(df)
        eg = exc_info.value
        assert len(eg.exceptions) == 1
        msg = str(eg.exceptions[0])
        assert QUANTITY_TYPE_BODY_MASS in msg
        assert "Expected: kg" in msg
        assert "got lb" in msg

    def test_aggregates_mismatches_for_multiple_types(self) -> None:
        df = _df(
            _quantity_row(type_=QUANTITY_TYPE_BODY_MASS, value="70", unit="lb"),
            _quantity_row(type_=QUANTITY_TYPE_HEIGHT, value="6", unit="ft"),
            _quantity_row(type_=QUANTITY_TYPE_STEP_COUNT, value="100", unit="steps"),
        )
        with pytest.raises(ExceptionGroup) as exc_info:
            _check_units(df)
        assert len(exc_info.value.exceptions) == 3

    def test_correct_types_alongside_mismatches_are_ignored(self) -> None:
        df = _df(
            _quantity_row(type_=QUANTITY_TYPE_BODY_MASS, value="70", unit="lb"),  # bad
            _quantity_row(),  # ok
            _quantity_row(
                type_=QUANTITY_TYPE_STEP_COUNT, value="1", unit="count"
            ),  # ok
        )
        with pytest.raises(ExceptionGroup) as exc_info:
            _check_units(df)
        assert len(exc_info.value.exceptions) == 1

    # -- Multiple units for one type ---------------------------------------

    def test_raises_for_two_units_on_one_type(self) -> None:
        df = _df(
            _quantity_row(type_=QUANTITY_TYPE_BODY_MASS, value="70", unit="kg"),
            _quantity_row(type_=QUANTITY_TYPE_BODY_MASS, value="155", unit="lb"),
        )
        with pytest.raises(ExceptionGroup) as exc_info:
            _check_units(df)
        eg = exc_info.value
        assert len(eg.exceptions) == 1
        msg = str(eg.exceptions[0])
        assert QUANTITY_TYPE_BODY_MASS in msg
        assert "more than one unit" in msg
        assert "kg" in msg
        assert "lb" in msg

    def test_raises_for_three_units_on_one_type(self) -> None:
        df = _df(
            _quantity_row(type_=QUANTITY_TYPE_HEIGHT, value="180", unit="cm"),
            _quantity_row(type_=QUANTITY_TYPE_HEIGHT, value="1.8", unit="m"),
            _quantity_row(type_=QUANTITY_TYPE_HEIGHT, value="71", unit="in"),
        )
        with pytest.raises(ExceptionGroup) as exc_info:
            _check_units(df)
        msg = str(exc_info.value.exceptions[0])
        for u in ("cm", "m", "in"):
            assert u in msg

    def test_multiple_units_with_correct_unit_present_still_raises(self) -> None:
        df = _df(
            _quantity_row(type_=QUANTITY_TYPE_BODY_MASS, value="70", unit="kg"),
            _quantity_row(type_=QUANTITY_TYPE_BODY_MASS, value="155", unit="lb"),
        )
        with pytest.raises(ExceptionGroup):
            _check_units(df)

    # -- NaN handling -------------------------------------------------------

    def test_passes_when_unit_is_nan_alone(self) -> None:
        # Single-unit NaN is treated as valid (ignored) — does NOT raise.
        df = _df(
            _quantity_row(type_=QUANTITY_TYPE_BODY_MASS, value="70", unit=float("nan")),
            _quantity_row(type_=QUANTITY_TYPE_BODY_MASS, value="71", unit=float("nan")),
        )
        _check_units(df)

    def test_nan_mixed_with_correct_unit_is_multiple_units(self) -> None:
        # NaN is still a distinct value in unique(), so this is "multiple units".
        df = _df(
            _quantity_row(type_=QUANTITY_TYPE_BODY_MASS, value="70", unit="kg"),
            _quantity_row(type_=QUANTITY_TYPE_BODY_MASS, value="71", unit=float("nan")),
        )
        with pytest.raises(ExceptionGroup) as exc_info:
            _check_units(df)
        assert "more than one unit" in str(exc_info.value.exceptions[0])

    def test_nan_mixed_with_wrong_unit_is_multiple_units(self) -> None:
        df = _df(
            _quantity_row(type_=QUANTITY_TYPE_BODY_MASS, value="70", unit="lb"),
            _quantity_row(type_=QUANTITY_TYPE_BODY_MASS, value="71", unit=float("nan")),
        )
        with pytest.raises(ExceptionGroup) as exc_info:
            _check_units(df)
        assert "more than one unit" in str(exc_info.value.exceptions[0])

    # -- Categorical exemption ---------------------------------------------

    def test_categorical_type_with_arbitrary_unit_passes(self) -> None:
        df = _df(
            {"type": CATEGORY_TYPE, "value": CATEGORY_VALUE_ASLEEP, "unit": "anything"},
            {"type": CATEGORY_TYPE, "value": CATEGORY_VALUE_INBED, "unit": "anything"},
        )
        _check_units(df)

    def test_categorical_type_with_nan_unit_passes(self) -> None:
        df = _df(
            _category_row(),  # unit=None
            _category_row(),
        )
        _check_units(df)

    def test_categorical_type_with_empty_string_unit_passes(self) -> None:
        df = _df(
            {"type": CATEGORY_TYPE, "value": CATEGORY_VALUE_ASLEEP, "unit": ""},
            {"type": CATEGORY_TYPE, "value": CATEGORY_VALUE_INBED, "unit": ""},
        )
        _check_units(df)

    def test_categorical_type_with_sentinel_value_passes(self) -> None:
        df = _df(
            {
                "type": CATEGORY_TYPE,
                "value": CATEGORY_VALUE_ASLEEP,
                "unit": CATEGORICAL,
            },
        )
        _check_units(df)

    def test_categorical_type_with_multiple_units_still_raises(self) -> None:
        # Exemption applies to mismatch check only, NOT consistency check.
        df = _df(
            {"type": CATEGORY_TYPE, "value": CATEGORY_VALUE_ASLEEP, "unit": "a"},
            {"type": CATEGORY_TYPE, "value": CATEGORY_VALUE_INBED, "unit": "b"},
        )
        with pytest.raises(ExceptionGroup) as exc_info:
            _check_units(df)
        assert "more than one unit" in str(exc_info.value.exceptions[0])

    def test_mix_of_categorical_and_correct_quantities_passes(self) -> None:
        df = _df(
            _category_row(),
            _quantity_row(),
            _quantity_row(type_=QUANTITY_TYPE_BODY_MASS, value="70", unit="kg"),
        )
        _check_units(df)

    # -- Mixed failure modes -----------------------------------------------

    def test_aggregates_mismatch_and_multiple_units(self) -> None:
        df = _df(
            _quantity_row(
                type_=QUANTITY_TYPE_BODY_MASS, value="70", unit="lb"
            ),  # mismatch
            _quantity_row(type_=QUANTITY_TYPE_HEIGHT, value="180", unit="cm"),
            _quantity_row(
                type_=QUANTITY_TYPE_HEIGHT, value="71", unit="in"
            ),  # multiple
            _quantity_row(),  # ok
            _category_row(),  # ok
        )
        with pytest.raises(ExceptionGroup) as exc_info:
            _check_units(df)
        eg = exc_info.value
        assert len(eg.exceptions) == 2
        messages = [str(e) for e in eg.exceptions]
        assert any(
            QUANTITY_TYPE_BODY_MASS in m and "doesn't match" in m for m in messages
        )
        assert any(
            QUANTITY_TYPE_HEIGHT in m and "more than one unit" in m for m in messages
        )

    def test_exception_group_message(self) -> None:
        df = _df(
            _quantity_row(type_=QUANTITY_TYPE_BODY_MASS, value="70", unit="lb"),
        )
        with pytest.raises(ExceptionGroup) as exc_info:
            _check_units(df)
        assert exc_info.value.message == "Data unit check failed:"

    def test_all_subexceptions_are_value_errors(self) -> None:
        df = _df(
            _quantity_row(type_=QUANTITY_TYPE_BODY_MASS, value="70", unit="lb"),
            _quantity_row(type_=QUANTITY_TYPE_HEIGHT, value="180", unit="cm"),
            _quantity_row(type_=QUANTITY_TYPE_HEIGHT, value="71", unit="in"),
        )
        with pytest.raises(ExceptionGroup) as exc_info:
            _check_units(df)
        for exc in exc_info.value.exceptions:
            assert isinstance(exc, DataSanityError)


# -- Parametrized coverage for _check_units --------------------------------


@pytest.mark.parametrize(
    "type_,unit",
    [
        (QUANTITY_TYPE, "count/min"),
        (QUANTITY_TYPE_BODY_MASS, "kg"),
        (QUANTITY_TYPE_HEIGHT, "cm"),
        (QUANTITY_TYPE_STEP_COUNT, "count"),
    ],
)
def test_each_known_type_passes_with_correct_unit(type_: str, unit: str) -> None:
    df = _df(
        _quantity_row(type_=type_, value="1", unit=unit),
        _quantity_row(type_=type_, value="2", unit=unit),
    )
    _check_units(df)


@pytest.mark.parametrize(
    "type_,wrong_unit,expected",
    [
        (QUANTITY_TYPE, "bpm", "count/min"),
        (QUANTITY_TYPE_BODY_MASS, "lb", "kg"),
        (QUANTITY_TYPE_HEIGHT, "in", "cm"),
        (QUANTITY_TYPE_STEP_COUNT, "steps", "count"),
    ],
)
def test_each_known_type_fails_with_wrong_unit(
    type_: str, wrong_unit: str, expected: str
) -> None:
    df = _df(_quantity_row(type_=type_, value="1", unit=wrong_unit))
    with pytest.raises(ExceptionGroup) as exc_info:
        _check_units(df)
    msg = str(exc_info.value.exceptions[0])
    assert f"Expected: {expected}" in msg
    assert f"got {wrong_unit}" in msg


@pytest.mark.parametrize("arbitrary_unit", ["asleep", "happy", "", "count", "kg"])
def test_categorical_passes_with_any_single_unit(arbitrary_unit: str) -> None:
    df = _df(
        {
            "type": CATEGORY_TYPE,
            "value": CATEGORY_VALUE_ASLEEP,
            "unit": arbitrary_unit,
        }
    )
    _check_units(df)


# ===========================================================================
# check_export_data  (integration-level)
# ===========================================================================


class TestCheckExportData:
    def test_passes_for_fully_valid_dataframe(self) -> None:
        df = _df(_quantity_row(), _category_row())
        check_export_data(df)  # must not raise

    def test_raises_value_error_for_missing_columns(self) -> None:
        df = pd.DataFrame({"type": [QUANTITY_TYPE]})
        with pytest.raises(DataSanityError, match="value"):
            check_export_data(df)

    def test_raises_exception_group_for_single_failure(self) -> None:
        df = _df({"type": "HKGhostType", "value": "1.0", "unit": "kg"})
        with pytest.raises(ExceptionGroup) as exc_info:
            check_export_data(df)
        assert len(exc_info.value.exceptions) == 1

    def test_raises_exception_group_collecting_all_failures(self) -> None:
        """All four early checks should fire independently; we expect ≥2 failures."""
        df = _df(
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
            assert isinstance(exc, DataSanityError)

    def test_passes_for_empty_dataframe(self) -> None:
        df = pd.DataFrame(columns=["type", "value", "unit"])
        check_export_data(df)  # empty data should pass all checks cleanly

    def test_category_value_failure_included_in_group(self) -> None:
        df = _df(_category_row(value="HKCategoryValueGhost"))
        with pytest.raises(ExceptionGroup) as exc_info:
            check_export_data(df)
        messages = [str(e) for e in exc_info.value.exceptions]
        assert any("HKCategoryValueGhost" in m for m in messages)

    def test_aggregates_failures_across_three_distinct_checks(self) -> None:
        # Three different checks should fire on three different rows.
        df = _df(
            _quantity_row(value="fast"),  # check 2
            _quantity_row(
                type_=QUANTITY_TYPE_BODY_MASS, value="70", unit=None
            ),  # check 3
            _category_row(value="HKCategoryValueDreaming"),  # check 4
        )
        with pytest.raises(ExceptionGroup) as exc_info:
            check_export_data(df)
        msgs = [str(e) for e in exc_info.value.exceptions]
        assert any(QUANTITY_TYPE in m for m in msgs)
        assert any(QUANTITY_TYPE_BODY_MASS in m for m in msgs)
        assert any("HKCategoryValueDreaming" in m for m in msgs)

    def test_passes_for_only_category_types(self) -> None:
        df = _df(
            _category_row(value=CATEGORY_VALUE_ASLEEP),
            _category_row(value=CATEGORY_VALUE_MINDFUL, type_=CATEGORY_TYPE_MINDFUL),
        )
        check_export_data(df)

    def test_unit_check_failure_does_not_drop_prior_exceptions(self) -> None:
        df = _df(
            _quantity_row(value="fast"),  # check 2 fails (string on quantity)
            _quantity_row(type_=QUANTITY_TYPE_BODY_MASS, value="70", unit="lb"),
            # check 5 fails (unit mismatch — expected kg, got lb)
        )
        with pytest.raises(ExceptionGroup) as exc_info:
            check_export_data(df)
        msgs = [str(e) for e in exc_info.value.exceptions]
        # Both errors should be surfaced; currently the HeartRate one disappears.
        assert any(QUANTITY_TYPE in m for m in msgs)
        assert any(QUANTITY_TYPE_BODY_MASS in m for m in msgs)
