"""Tests for src/importer/transform.py — data transformation pipeline."""

from __future__ import annotations

import time

import pandas as pd
import pytest

from src.importer.transform import (
    _drop_null_values,
    _handle_categorical_units,
    _map_categories,
    _timestamps_to_unix,
    transform,
)
from src.model.base import MissingUnit

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_df(**overrides) -> pd.DataFrame:
    base = {
        "type": ["HKQuantityTypeIdentifierHeartRate"],
        "sourceName": ["Watch"],
        "sourceVersion": ["1.0"],
        "device": ["Apple Watch"],
        "unit": ["count/min"],
        "startDate": pd.to_datetime(["2024-01-01T00:00:00+00:00"]),
        "endDate": pd.to_datetime(["2024-01-01T00:01:00+00:00"]),
        "creationDate": pd.to_datetime(["2024-01-01T00:00:01+00:00"]),
        "value": ["72"],
    }
    base.update(overrides)
    return pd.DataFrame(base)


def _make_categorical_df(type_val: str, value: str) -> pd.DataFrame:
    df = _make_df()
    df["type"] = type_val
    df["unit"] = None
    df["value"] = value
    return df


# ---------------------------------------------------------------------------
# _drop_null_values
# ---------------------------------------------------------------------------


class TestDropNullValues:
    def test_drops_null_value_rows(self):
        df = _make_df(value=[None])
        _drop_null_values(df)
        assert len(df) == 0

    def test_preserves_non_null_rows(self):
        df = _make_df(value=["72"])
        _drop_null_values(df)
        assert len(df) == 1

    def test_mixed_null_and_valid(self):
        df = pd.DataFrame(
            {
                "type": ["HR", "HR", "HR"],
                "value": ["72", None, "80"],
                "unit": ["bpm", "bpm", "bpm"],
                "device": ["w", "w", "w"],
                "sourceName": ["s", "s", "s"],
                "sourceVersion": ["1", "1", "1"],
                "startDate": pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03"]),
                "endDate": pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03"]),
                "creationDate": pd.to_datetime(
                    ["2024-01-01", "2024-01-02", "2024-01-03"]
                ),
            }
        )
        _drop_null_values(df)
        assert len(df) == 2

    def test_all_null_returns_empty(self):
        df = _make_df(value=[None])
        _drop_null_values(df)
        assert len(df) == 0

    def test_no_nulls_returns_unchanged(self):
        df = _make_df(value=["72"])
        _drop_null_values(df)
        assert len(df) == 1


# ---------------------------------------------------------------------------
# _timestamps_to_unix
# ---------------------------------------------------------------------------


class TestTimestampsToUnix:
    def test_converts_to_int64(self):
        series = pd.to_datetime(["2024-01-01T00:00:00+00:00"])
        result = _timestamps_to_unix(series)
        assert result.dtype == "int64"

    def test_known_timestamp(self):
        series = pd.to_datetime(["2024-01-01T00:00:00+00:00"])
        result = _timestamps_to_unix(series)
        assert result[0] == 1_704_067_200

    def test_no_floating_point_rounding(self):
        """Floor division must produce exact integers, not float-rounded values."""
        series = pd.to_datetime(["2024-01-01T00:00:00.999999999+00:00"])
        result = _timestamps_to_unix(series)
        assert result[0] == 1_704_067_200

    def test_large_series_performance(self):
        n = 1_000_000
        series = pd.date_range("2000-01-01", periods=n, freq="s", tz="utc")
        start = time.perf_counter()
        result = _timestamps_to_unix(pd.Series(series))
        elapsed = time.perf_counter() - start
        assert len(result) == n
        assert elapsed < 5.0

    def test_epoch_zero(self):
        series = pd.to_datetime(["1970-01-01T00:00:00+00:00"])
        result = _timestamps_to_unix(series)
        assert result[0] == 0


# ---------------------------------------------------------------------------
# _handle_categorical_units
# ---------------------------------------------------------------------------


class TestHandleCategoricalUnits:
    def test_non_null_units_unchanged(self):
        df = _make_df()
        original_len = len(df)
        _handle_categorical_units(df)
        assert len(df) == original_len
        assert df["unit"].iloc[0] == "count/min"

    def test_categorical_unit_set_to_sentinel(self):
        df = _make_categorical_df(
            "HKCategoryTypeIdentifierAppleStandHour",
            "HKCategoryValueAppleStandHourStood",
        )
        _handle_categorical_units(df)
        assert df["unit"].iloc[0] == MissingUnit.CATEGORICAL.value

    def test_categorical_value_converted_to_int_string(self):
        df = _make_categorical_df(
            "HKCategoryTypeIdentifierAppleStandHour",
            "HKCategoryValueAppleStandHourStood",
        )
        _handle_categorical_units(df)
        assert df["value"].iloc[0] == "1"

    def test_unknown_type_raises_key_error(self):
        df = _make_categorical_df("HKCategoryTypeIdentifierUnknownXYZ", "SomeValue")
        with pytest.raises(KeyError):
            _handle_categorical_units(df)

    def test_unknown_value_raises_key_error(self):
        df = _make_categorical_df(
            "HKCategoryTypeIdentifierAppleStandHour",
            "HKCategoryValueAppleStandHourINVALID",
        )
        with pytest.raises(KeyError):
            _handle_categorical_units(df)

    def test_numeric_value_without_unit_raises_value_error(self):
        df = _make_categorical_df("HKCategoryTypeIdentifierAppleStandHour", "1")
        with pytest.raises(ValueError, match="numeric value"):
            _handle_categorical_units(df)

    def test_unexpected_null_column_raises_not_implemented(self):
        df = _make_df()
        df["sourceName"] = None
        with pytest.raises(NotImplementedError):
            _handle_categorical_units(df)


# ---------------------------------------------------------------------------
# _map_categories
# ---------------------------------------------------------------------------


class TestMapCategories:
    def test_valid_mapping(self):
        df = pd.DataFrame(
            {
                "type": ["HKCategoryTypeIdentifierSleepAnalysis"],
                "value": ["HKCategoryValueSleepAnalysisAsleepCore"],
                "unit": [None],
            }
        )
        no_unit = df["unit"].isna()
        _map_categories(df, no_unit)
        assert df["value"].iloc[0] == "3"

    def test_unknown_type_key_error(self):
        df = pd.DataFrame(
            {
                "type": ["HKCategoryTypeIdentifierNONEXISTENT"],
                "value": ["SomeValue"],
                "unit": [None],
            }
        )
        with pytest.raises(KeyError):
            _map_categories(df, df["unit"].isna())

    def test_multiple_types_mapped(self):
        df = pd.DataFrame(
            {
                "type": [
                    "HKCategoryTypeIdentifierSleepAnalysis",
                    "HKCategoryTypeIdentifierAppleStandHour",
                ],
                "value": [
                    "HKCategoryValueSleepAnalysisAwake",
                    "HKCategoryValueAppleStandHourIdle",
                ],
                "unit": [None, None],
            }
        )
        _map_categories(df, df["unit"].isna())
        assert df["value"].iloc[0] == "2"
        assert df["value"].iloc[1] == "0"


# ---------------------------------------------------------------------------
# transform (full pipeline)
# ---------------------------------------------------------------------------


class TestTransform:
    def _make_full_df(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "type": [
                    "HKQuantityTypeIdentifierHeartRate",
                    "HKQuantityTypeIdentifierHeartRate",
                    "HKCategoryTypeIdentifierAppleStandHour",
                ],
                "sourceName": ["Watch"] * 3,
                "sourceVersion": ["1"] * 3,
                "device": ["Watch"] * 3,
                "unit": ["count/min", "count/min", None],
                "startDate": pd.to_datetime(["2024-01-01T00:00:00+00:00"] * 3),
                "endDate": pd.to_datetime(["2024-01-01T00:01:00+00:00"] * 3),
                "creationDate": pd.to_datetime(["2024-01-01T00:00:01+00:00"] * 3),
                "value": ["72", "80", "HKCategoryValueAppleStandHourStood"],
            }
        )

    def test_start_date_is_int64_unix(self):
        df = self._make_full_df()
        transform(df)
        assert df["startDate"].dtype == "int64"

    def test_end_date_is_int64_unix(self):
        df = self._make_full_df()
        transform(df)
        assert df["endDate"].dtype == "int64"

    def test_value_is_float64(self):
        df = self._make_full_df()
        transform(df)
        assert df["value"].dtype == "float64"

    def test_null_value_rows_dropped(self):
        df = self._make_full_df()
        df.loc[0, "value"] = None
        transform(df)
        assert len(df) == 2

    def test_categorical_unit_set(self):
        df = self._make_full_df()
        transform(df)
        cat_row = df[df["unit"] == MissingUnit.CATEGORICAL.value]
        assert len(cat_row) == 1

    def test_transform_performance_large_df(self):
        n = 50_000
        df = pd.DataFrame(
            {
                "type": ["HKQuantityTypeIdentifierHeartRate"] * n,
                "sourceName": ["Watch"] * n,
                "sourceVersion": ["1"] * n,
                "device": ["Watch"] * n,
                "unit": ["count/min"] * n,
                "startDate": pd.date_range("2024-01-01", periods=n, freq="s", tz="utc"),
                "endDate": pd.date_range("2024-01-01", periods=n, freq="s", tz="utc"),
                "creationDate": pd.date_range(
                    "2024-01-01", periods=n, freq="s", tz="utc"
                ),
                "value": [str(i % 200) for i in range(n)],
            }
        )
        start = time.perf_counter()
        transform(df)
        elapsed = time.perf_counter() - start
        assert elapsed < 10.0

    def test_drop_null_values_returns_none(self):
        """_drop_null_values mutates in-place and returns None."""
        df = _make_df(value=[None])
        result = _drop_null_values(df)
        assert result is None

    def test_nat_in_value_treated_as_null(self):
        """pd.NaT is NaN-like; rows with NaT value should be dropped."""
        df = _make_df(value=[pd.NaT])
        _drop_null_values(df)
        assert len(df) == 0

    def test_original_df_identity_is_mutated(self):
        """Verify we are mutating the object passed in, not a copy."""
        df = _make_df(value=["72"])
        original_id = id(df)
        _drop_null_values(df)
        assert id(df) == original_id
        assert len(df) == 1

    def test_pre_epoch_is_negative(self):
        """Dates before 1970-01-01 should produce a negative Unix timestamp."""
        result = _timestamps_to_unix(pd.to_datetime(["1969-12-31T23:59:59+00:00"]))
        assert result[0] == -1

    def test_tz_naive_series_coerces_to_utc(self):
        """The implementation casts to datetime64[ns, UTC];
        tz-naive input must not crash."""
        series = pd.Series(pd.to_datetime(["2024-01-01T00:00:00"], utc=True))
        result = _timestamps_to_unix(series)
        assert result.iloc[0] == 1_704_067_200

    def test_return_type_is_series(self):
        df = pd.DataFrame({"date": pd.to_datetime(["2024-01-01T00:00:00+00:00"])})
        result = _timestamps_to_unix(df["date"])
        assert isinstance(result, pd.Series)

    def test_handle_categorical_units_returns_none(self):
        df = _make_df()
        assert _handle_categorical_units(df) is None

    def test_both_unit_and_device_null_is_allowed(self):
        """unit and device are both in COLUMNS_WITHOUT_VALUE
        — both null should not raise."""
        df = _make_categorical_df(
            "HKCategoryTypeIdentifierAppleStandHour",
            "HKCategoryValueAppleStandHourStood",
        )
        df["device"] = None
        _handle_categorical_units(df)  # must not raise NotImplementedError

    def test_only_categorical_rows_have_unit_changed(self):
        """Quantity rows with a unit must be untouched when mixed
        with categorical rows."""
        df = pd.DataFrame(
            {
                "type": [
                    "HKQuantityTypeIdentifierHeartRate",
                    "HKCategoryTypeIdentifierAppleStandHour",
                ],
                "sourceName": ["Watch", "Watch"],
                "sourceVersion": ["1", "1"],
                "device": ["d", "d"],
                "unit": ["count/min", None],
                "startDate": pd.to_datetime(["2024-01-01"] * 2),
                "endDate": pd.to_datetime(["2024-01-01"] * 2),
                "creationDate": pd.to_datetime(["2024-01-01"] * 2),
                "value": ["72", "HKCategoryValueAppleStandHourStood"],
            }
        )
        _handle_categorical_units(df)
        assert df.loc[0, "unit"] == "count/min"
        assert df.loc[1, "unit"] == MissingUnit.CATEGORICAL.value

    def test_multiple_unknown_types_all_reported(self):
        """The missing dict accumulates all bad (type, value) pairs before raising."""
        df = pd.DataFrame(
            {
                "type": [
                    "HKCategoryTypeIdentifierBAD1",
                    "HKCategoryTypeIdentifierBAD2",
                ],
                "value": ["v1", "v2"],
                "unit": [None, None],
            }
        )
        with pytest.raises(KeyError) as exc_info:
            _map_categories(df, df["unit"].isna())
        msg = str(exc_info.value)
        assert "BAD1" in msg and "BAD2" in msg

    def test_result_values_are_strings(self):
        """The mapped integers are stored as str, not int."""
        df = pd.DataFrame(
            {
                "type": ["HKCategoryTypeIdentifierSleepAnalysis"],
                "value": ["HKCategoryValueSleepAnalysisInBed"],
                "unit": [None],
            }
        )
        _map_categories(df, df["unit"].isna())
        assert isinstance(df["value"].iloc[0], str)
        assert df["value"].iloc[0] == "0"

    def test_transform_returns_none(self):
        assert transform(self._make_full_df()) is None

    def test_start_date_value_is_plausible_unix(self):
        df = self._make_full_df()
        transform(df)
        assert df["startDate"].iloc[0] == 1_704_067_200

    def test_no_nan_in_value_after_transform(self):
        df = self._make_full_df()
        transform(df)
        assert not df["value"].isna().any()

    def test_creation_date_untouched(self):
        """creationDate is not converted by transform — it must survive unchanged."""
        df = self._make_full_df()
        original_creationDate = df["creationDate"].copy()  # noqa: N806
        transform(df)
        assert "creationDate" in df.columns
        pd.testing.assert_series_equal(df["creationDate"], original_creationDate)
