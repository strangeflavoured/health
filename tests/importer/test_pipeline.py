"""Tests for src/importer/pipeline.py — TS.MADD upload helpers."""

from __future__ import annotations

import time
from typing import Any
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from redis import ResponseError

from src.importer.pipeline import (
    _build_madd_args,
    _resolve_failures,
    upload_batch,
)
from src.importer.response import RowFailure

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_df(
    n: int = 3, type_val: str = "HKQuantityTypeIdentifierHeartRate"
) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "type": [type_val] * n,
            "sourceName": [f"source_{i}" for i in range(n)],
            "unit": ["count/min"] * n,
            "value": [float(60 + i) for i in range(n)],
            "startDate": [1_700_000_000 + i * 60 for i in range(n)],
            "endDate": [1_700_000_060 + i * 60 for i in range(n)],
            "group": ["fitness"] * n,
        }
    )


# ---------------------------------------------------------------------------
# _build_madd_args
# ---------------------------------------------------------------------------


class TestBuildMaddArgs:
    def test_returns_two_triples_per_row(self):
        args = _build_madd_args(_make_df(3))
        assert len(args) == 6

    def test_empty_df_returns_empty_list(self):
        assert _build_madd_args(_make_df(0)) == []

    def test_start_key_format(self):
        args = _build_madd_args(_make_df(1, "HKQuantityTypeIdentifierStepCount"))
        assert args[0][0] == "ts:HKQuantityTypeIdentifierStepCount:start"

    def test_end_key_format(self):
        args = _build_madd_args(_make_df(1, "HKQuantityTypeIdentifierStepCount"))
        assert args[1][0] == "ts:HKQuantityTypeIdentifierStepCount:end"

    def test_interleaving_start_before_end(self):
        """For each row start must immediately precede end."""
        args = _build_madd_args(_make_df(3))
        for i in range(3):
            assert args[i * 2][0].endswith(":start")
            assert args[i * 2 + 1][0].endswith(":end")

    def test_start_timestamp_forwarded(self):
        df = _make_df(1)
        args = _build_madd_args(df)
        assert args[0][1] == df["startDate"].iloc[0]

    def test_end_timestamp_forwarded(self):
        df = _make_df(1)
        args = _build_madd_args(df)
        assert args[1][1] == df["endDate"].iloc[0]

    def test_value_forwarded_to_start(self):
        df = _make_df(1)
        args = _build_madd_args(df)
        assert args[0][2] == pytest.approx(df["value"].iloc[0])

    def test_value_forwarded_to_end(self):
        df = _make_df(1)
        args = _build_madd_args(df)
        assert args[1][2] == pytest.approx(df["value"].iloc[0])

    def test_returns_list_of_tuples(self):
        args = _build_madd_args(_make_df(2))
        assert all(isinstance(a, tuple) and len(a) == 3 for a in args)

    def test_no_labels_in_args(self):
        """Duplicate policy and labels are key-level; must not appear in MADD args."""
        args = _build_madd_args(_make_df(1))
        for triple in args:
            assert len(triple) == 3


# ---------------------------------------------------------------------------
# _resolve_failures
# ---------------------------------------------------------------------------


class TestResolveFailures:
    def test_all_success_returns_empty(self):
        df = _make_df(3)
        response = [100, 101, 200, 201, 300, 301]
        assert _resolve_failures(response, df) == []

    def test_start_error_detected(self):
        df = _make_df(2)
        err = ResponseError("TSDB: Duplicate sample")
        failures = _resolve_failures([err, 101, 200, 201], df)
        assert len(failures) == 1
        assert failures[0].start_error is not None
        assert failures[0].end_error is None

    def test_end_error_detected(self):
        df = _make_df(2)
        err = ResponseError("TSDB: Duplicate sample")
        failures = _resolve_failures([100, err, 200, 201], df)
        assert len(failures) == 1
        assert failures[0].end_error is not None
        assert failures[0].start_error is None

    def test_both_errors_on_same_row(self):
        df = _make_df(1)
        err1 = ResponseError("start err")
        err2 = ResponseError("end err")
        failures = _resolve_failures([err1, err2], df)
        assert len(failures) == 1
        assert failures[0].start_error is not None
        assert failures[0].end_error is not None

    def test_mismatched_length_raises_index_error(self):
        with pytest.raises(IndexError):
            _resolve_failures([1, 2], _make_df(3))

    def test_odd_length_response_raises_index_error(self):
        with pytest.raises(IndexError):
            _resolve_failures([1, 2, 3, 4, 5], _make_df(2))

    def test_empty_df_empty_response(self):
        assert _resolve_failures([], _make_df(0)) == []

    def test_non_response_error_value_treated_as_success(self):
        assert _resolve_failures([12345, 67890], _make_df(1)) == []

    def test_large_batch_performance(self):
        """`_resolve_failures` on 10k rows should be quick (< 2 s)."""
        n = 10_000
        df = _make_df(n)
        response = list(range(n * 2))
        t0 = time.perf_counter()
        failures = _resolve_failures(response, df)
        assert time.perf_counter() - t0 < 2.0
        assert failures == []

    def test_failure_data_type_matches_row(self):
        df = pd.DataFrame(
            {
                "type": ["TypeA", "TypeB"],
                "sourceName": ["s", "s"],
                "unit": ["u", "u"],
                "value": [1.0, 2.0],
                "startDate": [1000, 2000],
                "endDate": [1001, 2001],
            }
        )
        failures = _resolve_failures(
            [ResponseError("fail"), ResponseError("fail"), 200, 201], df
        )
        assert failures[0].data_type == "TypeA"

    def test_row_index_preserved(self):
        df = _make_df(2)
        df.index = [10, 20]
        failures = _resolve_failures([ResponseError("x"), 1, 2, 3], df)
        assert failures[0].row_index == 10

    def test_failure_log_uses_row_type_not_index(self):
        """ "Regression: log line must show the HK type string, not the row index."""
        df = pd.DataFrame(
            {
                "type": ["HKQuantityTypeIdentifierHeartRate"],
                "sourceName": ["Watch"],
                "unit": ["bpm"],
                "value": [72.0],
                "startDate": [1_000_000],
                "endDate": [1_000_060],
            }
        )
        with patch("src.importer.pipeline.logger") as mock_log:
            _resolve_failures([ResponseError("TSDB: Duplicate"), 1], df)
        assert "HKQuantityTypeIdentifierHeartRate" in str(mock_log.info.call_args[0])

    def test_returns_list_type(self):
        assert isinstance(_resolve_failures([1, 2], _make_df(1)), list)

    def test_non_response_error_treated_as_success(self):
        assert _resolve_failures([12345, 67890], _make_df(1)) == []

    def test_start_error_string_matches_response_error_message(self):
        failures = _resolve_failures(
            [ResponseError("TSDB: Duplicate sample"), 101], _make_df(1)
        )
        start_error = failures[0].start_error
        assert isinstance(start_error, str)
        assert "TSDB: Duplicate sample" in start_error

    def test_end_error_string_matches_response_error_message(self):
        failures = _resolve_failures(
            [100, ResponseError("TSDB: Duplicate sample")], _make_df(1)
        )
        end_error = failures[0].end_error
        assert isinstance(end_error, str)
        assert "TSDB: Duplicate sample" in end_error


# ---------------------------------------------------------------------------
# upload_batch
# ---------------------------------------------------------------------------


class TestUploadBatch:
    def _mock_rts(self, response: list[Any]) -> MagicMock:
        rts = MagicMock()
        rts.madd.return_value = response
        return rts

    def test_returns_empty_on_success(self):
        rts = self._mock_rts([100, 101, 200, 201])
        assert upload_batch(rts, _make_df(2)) == []

    def test_returns_failures_on_error_response(self):
        rts = self._mock_rts([ResponseError("TSDB: Duplicate"), 101])
        result = upload_batch(rts, _make_df(1))
        assert len(result) == 1
        assert isinstance(result[0], RowFailure)

    def test_calls_madd_once(self):
        rts = self._mock_rts([1, 2, 3, 4])
        upload_batch(rts, _make_df(2))
        rts.madd.assert_called_once()

    def test_madd_receives_flat_arg_list(self):
        """madd must be called with the list of triples from _build_madd_args."""
        rts = self._mock_rts([1, 2])
        upload_batch(rts, _make_df(1))
        args_passed = rts.madd.call_args[0][0]
        assert isinstance(args_passed, list)
        assert len(args_passed) == 2  # 2 samples for 1 row

    def test_empty_df_no_madd_call(self):
        rts = self._mock_rts([])
        result = upload_batch(rts, _make_df(0))
        rts.madd.assert_not_called()
        assert result == []

    def test_return_type_is_list(self):
        assert isinstance(upload_batch(self._mock_rts([1, 2]), _make_df(1)), list)

    def test_no_duplicate_policy_param(self):
        """upload_batch must not accept duplicate_policy; policy is key-level."""
        import inspect

        sig = inspect.signature(upload_batch)
        assert "duplicate_policy" not in sig.parameters

    def test_timestamps_forwarded_correctly(self):
        """MADD args must carry the exact integer timestamps from the DataFrame."""
        rts = self._mock_rts([1, 2])
        df = _make_df(1)
        upload_batch(rts, df)
        args = rts.madd.call_args[0][0]
        assert args[0][1] == df["startDate"].iloc[0]
        assert args[1][1] == df["endDate"].iloc[0]
