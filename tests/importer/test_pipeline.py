"""Tests for src/importer/pipeline.py — Redis TimeSeries pipeline helpers."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from redis import ResponseError

from src.importer.pipeline import (
    _add_row_to_pipeline,
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


def _make_row(
    type_val: str = "HKQuantityTypeIdentifierHeartRate",
    source: str = "Watch",
    unit: str = "count/min",
    value: float = 72.0,
    start: int = 1_700_000_000,
    end: int = 1_700_000_060,
):
    row = type(
        "Row",
        (),
        {
            "type": type_val,
            "sourceName": source,
            "unit": unit,
            "value": value,
            "startDate": start,
            "endDate": end,
        },
    )
    return row()


# ---------------------------------------------------------------------------
# _add_row_to_pipeline
# ---------------------------------------------------------------------------


class TestAddRowToPipeline:
    def test_calls_pipe_add_twice(self):
        pipe = MagicMock()
        row = _make_row()
        _add_row_to_pipeline(pipe, row)
        assert pipe.add.call_count == 2

    def test_start_key_format(self):
        pipe = MagicMock()
        row = _make_row(type_val="HKQuantityTypeIdentifierStepCount")
        _add_row_to_pipeline(pipe, row)
        calls = [  # noqa: F841
            c[1]["key"] if "key" in c[1] else c[0][0] for c in pipe.add.call_args_list
        ]
        keys = [
            pipe.add.call_args_list[0][1]["key"],
            pipe.add.call_args_list[1][1]["key"],
        ]
        assert keys[0] == "HKQuantityTypeIdentifierStepCount:start"
        assert keys[1] == "HKQuantityTypeIdentifierStepCount:end"

    def test_default_policy_is_first(self):
        pipe = MagicMock()
        _add_row_to_pipeline(pipe, _make_row())
        for c in pipe.add.call_args_list:
            assert c[1]["duplicate_policy"] == DuplicatePolicy.FIRST.value

    def test_last_policy_propagated(self):
        pipe = MagicMock()
        _add_row_to_pipeline(pipe, _make_row(), DuplicatePolicy.LAST)
        for c in pipe.add.call_args_list:
            assert c[1]["duplicate_policy"] == DuplicatePolicy.LAST.value

    def test_labels_contain_source_and_unit(self):
        pipe = MagicMock()
        row = _make_row(source="iPhone", unit="kg")
        _add_row_to_pipeline(pipe, row)
        for c in pipe.add.call_args_list:
            labels = c[1]["labels"]
            assert labels["sourceName"] == "iPhone"
            assert labels["unit"] == "kg"

    def test_value_forwarded(self):
        pipe = MagicMock()
        row = _make_row(value=99.5)
        _add_row_to_pipeline(pipe, row)
        for c in pipe.add.call_args_list:
            assert c[1]["value"] == 99.5


# ---------------------------------------------------------------------------
# _resolve_failures
# ---------------------------------------------------------------------------


class TestResolveFailures:
    def test_all_success_returns_empty(self):
        df = _make_df(3)
        response = [100, 101, 200, 201, 300, 301]
        failures = _resolve_failures(response, df)
        assert failures == []

    def test_start_error_detected(self):
        df = _make_df(2)
        err = ResponseError("TSDB: Duplicate sample")
        response = [err, 101, 200, 201]
        failures = _resolve_failures(response, df)
        assert len(failures) == 1
        assert failures[0].start_error is not None
        assert failures[0].end_error is None

    def test_end_error_detected(self):
        df = _make_df(2)
        err = ResponseError("TSDB: Duplicate sample")
        response = [100, err, 200, 201]
        failures = _resolve_failures(response, df)
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

    def test_empty_df_empty_response(self):
        df = _make_df(0)
        failures = _resolve_failures([], df)
        assert failures == []

    def test_large_batch_performance(self):
        """_resolve_failures on 10k rows should complete in under 5 seconds."""
        import time

        n = 10_000
        df = _make_df(n)
        response = [i for i in range(n * 2)]
        start = time.perf_counter()
        failures = _resolve_failures(response, df)
        elapsed = time.perf_counter() - start
        assert failures == []
        assert elapsed < 5.0

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
        result = upload_batch(rts, df)
        assert result == []

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

    def test_policy_forwarded(self):
        df = _make_df(1)
        rts = self._mock_rts([1, 2])
        with patch("src.importer.pipeline._add_row_to_pipeline") as mock_add:
            upload_batch(rts, df, duplicate_policy=DuplicatePolicy.LAST)
            _, kwargs = mock_add.call_args
            assert kwargs["duplicate_policy"] == DuplicatePolicy.LAST

    def test_empty_df_no_pipeline_adds(self):
        df = _make_df(0)
        rts = self._mock_rts([])
        result = upload_batch(rts, df)
        assert result == []
