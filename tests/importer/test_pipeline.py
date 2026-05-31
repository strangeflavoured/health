"""Tests for src/importer/pipeline.py — Redis TimeSeries pipeline helpers."""

from __future__ import annotations

import time
from typing import Any
from unittest.mock import MagicMock

import pandas as pd
import pytest
from redis import ResponseError

from src.importer.pipeline import (
    _queue_row,
    _resolve_failures,
    upload_batch,
)
from src.importer.response import DuplicatePolicy, RowFailure

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
        }
    )


# ---------------------------------------------------------------------------
# _queue_row
# ---------------------------------------------------------------------------


class TestQueueRow:
    def test_calls_pipe_add_twice(self):
        pipe = MagicMock()
        _queue_row(pipe, "ts:HR:start", "ts:HR:end", 1, 2, 72.0, "FIRST")
        assert pipe.add.call_count == 2

    def test_start_call_uses_start_key_and_timestamp(self):
        pipe = MagicMock()
        _queue_row(pipe, "ts:HR:start", "ts:HR:end", 10, 20, 72.0, "FIRST")
        kwargs = pipe.add.call_args_list[0][1]
        assert kwargs["key"] == "ts:HR:start"
        assert kwargs["timestamp"] == 10
        assert kwargs["value"] == 72.0
        assert kwargs["duplicate_policy"] == "FIRST"

    def test_end_call_uses_end_key_and_timestamp(self):
        pipe = MagicMock()
        _queue_row(pipe, "ts:HR:start", "ts:HR:end", 10, 20, 72.0, "LAST")
        kwargs = pipe.add.call_args_list[1][1]
        assert kwargs["key"] == "ts:HR:end"
        assert kwargs["timestamp"] == 20
        assert kwargs["value"] == 72.0
        assert kwargs["duplicate_policy"] == "LAST"

    def test_returns_none(self):
        assert _queue_row(MagicMock(), "a", "b", 1, 2, 1.0, "FIRST") is None


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
        df = _make_df(3)
        with pytest.raises(IndexError):
            _resolve_failures([1, 2], df)

    def test_odd_length_response_raises_index_error(self):
        with pytest.raises(IndexError):
            _resolve_failures([1, 2, 3, 4, 5], _make_df(2))

    def test_empty_df_empty_response(self):
        df = _make_df(0)
        assert _resolve_failures([], df) == []

    def test_non_response_error_value_treated_as_success(self):
        assert _resolve_failures([12345, 67890], _make_df(1)) == []

    def test_large_batch_performance(self):
        """`_resolve_failures` on 10k rows should be quick (< 2 s)."""
        n = 10_000
        df = _make_df(n)
        response = list(range(n * 2))
        t0 = time.perf_counter()
        failures = _resolve_failures(response, df)
        assert failures == []
        assert time.perf_counter() - t0 < 2.0

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
        err = ResponseError("fail")
        failures = _resolve_failures([err, err, 200, 201], df)
        assert failures[0].data_type == "TypeA"

    def test_row_index_preserved(self):
        df = _make_df(2)
        df.index = [10, 20]
        err = ResponseError("x")
        failures = _resolve_failures([err, 1, 2, 3], df)
        assert failures[0].row_index == 10

    def test_returns_list_type(self):
        assert isinstance(_resolve_failures([1, 2], _make_df(1)), list)

    def test_start_error_string_matches_response_error_message(self):
        err = ResponseError("TSDB: Duplicate sample")
        failures = _resolve_failures([err, 101], _make_df(1))
        assert "TSDB: Duplicate sample" in failures[0].start_error

    def test_end_error_string_matches_response_error_message(self):
        err = ResponseError("TSDB: Duplicate sample")
        failures = _resolve_failures([100, err], _make_df(1))
        assert "TSDB: Duplicate sample" in failures[0].end_error


# ---------------------------------------------------------------------------
# upload_batch
# ---------------------------------------------------------------------------


class TestUploadBatch:
    def _mock_rts(self, response: list[Any]) -> MagicMock:
        pipe = MagicMock()
        pipe.execute.return_value = response
        rts = MagicMock()
        rts.pipeline.return_value = pipe
        return rts

    def test_returns_empty_on_success(self):
        df = _make_df(2)
        rts = self._mock_rts([100, 101, 200, 201])
        assert upload_batch(rts, df) == []

    def test_returns_failures_on_error(self):
        df = _make_df(1)
        err = ResponseError("TSDB: Duplicate")
        rts = self._mock_rts([err, 101])
        result = upload_batch(rts, df)
        assert len(result) == 1
        assert isinstance(result[0], RowFailure)

    def test_execute_called_once(self):
        df = _make_df(3)
        rts = self._mock_rts([1, 2, 3, 4, 5, 6])
        upload_batch(rts, df)
        rts.pipeline.return_value.execute.assert_called_once()

    def test_execute_raise_on_error_false(self):
        df = _make_df(1)
        rts = self._mock_rts([1, 2])
        upload_batch(rts, df)
        call_kwargs = rts.pipeline.return_value.execute.call_args[1]
        assert call_kwargs.get("raise_on_error") is False

    def test_policy_forwarded_to_pipe_add(self):
        df = _make_df(2)
        rts = self._mock_rts([1, 2, 3, 4])
        upload_batch(rts, df, duplicate_policy=DuplicatePolicy.LAST)
        for c in rts.pipeline.return_value.add.call_args_list:
            assert c.kwargs["duplicate_policy"] == "LAST"

    def test_default_policy_is_first(self):
        df = _make_df(1)
        rts = self._mock_rts([1, 2])
        upload_batch(rts, df)
        for c in rts.pipeline.return_value.add.call_args_list:
            assert c.kwargs["duplicate_policy"] == "FIRST"

    def test_keys_computed_once_per_batch(self):
        """All start commands must use the *same* key, all end commands must
        use the *same* key — proving the key string is not re-formatted per
        row.
        """
        df = _make_df(5, type_val="HKQuantityTypeIdentifierStepCount")
        rts = self._mock_rts([0] * 10)
        upload_batch(rts, df)

        calls = rts.pipeline.return_value.add.call_args_list
        start_keys = {calls[i].kwargs["key"] for i in range(0, len(calls), 2)}
        end_keys = {calls[i].kwargs["key"] for i in range(1, len(calls), 2)}
        assert start_keys == {"ts:HKQuantityTypeIdentifierStepCount:start"}
        assert end_keys == {"ts:HKQuantityTypeIdentifierStepCount:end"}

    def test_empty_df_returns_empty(self):
        df = _make_df(0)
        rts = self._mock_rts([])
        assert upload_batch(rts, df) == []

    def test_empty_df_does_not_open_pipeline(self):
        rts = self._mock_rts([])
        upload_batch(rts, _make_df(0))
        rts.pipeline.assert_not_called()

    def test_timestamp_forwarded(self):
        df = pd.DataFrame(
            {
                "type": ["HR"],
                "sourceName": ["w"],
                "unit": ["count/min"],
                "value": [72.0],
                "startDate": [1_234_567_890],
                "endDate": [1_234_567_950],
            }
        )
        rts = self._mock_rts([1, 2])
        upload_batch(rts, df)
        calls = rts.pipeline.return_value.add.call_args_list
        assert calls[0].kwargs["timestamp"] == 1_234_567_890
        assert calls[1].kwargs["timestamp"] == 1_234_567_950

    def test_value_forwarded(self):
        df = pd.DataFrame(
            {
                "type": ["HR"],
                "sourceName": ["w"],
                "unit": ["count/min"],
                "value": [99.5],
                "startDate": [1_700_000_000],
                "endDate": [1_700_000_060],
            }
        )
        rts = self._mock_rts([1, 2])
        upload_batch(rts, df)
        for c in rts.pipeline.return_value.add.call_args_list:
            assert c.kwargs["value"] == 99.5

    def test_numpy_scalars_unwrapped_to_python(self):
        """numpy ints/floats must be cast to plain Python scalars so
        redis-py serialises them cleanly.
        """
        df = _make_df(1)
        # int64 columns are produced by transform._timestamps_to_unix
        df["startDate"] = df["startDate"].astype("int64")
        df["endDate"] = df["endDate"].astype("int64")
        rts = self._mock_rts([1, 2])
        upload_batch(rts, df)

        for c in rts.pipeline.return_value.add.call_args_list:
            ts = c.kwargs["timestamp"]
            v = c.kwargs["value"]
            assert isinstance(ts, int) and not isinstance(ts, bool)
            assert isinstance(v, float)

    def test_return_type_is_list(self):
        assert isinstance(upload_batch(self._mock_rts([1, 2]), _make_df(1)), list)
