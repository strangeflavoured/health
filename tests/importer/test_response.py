"""Tests for src/importer/response.py — failure models and JSON persistence."""

from __future__ import annotations

import json

import pytest

from src.importer.response import (
    BatchFailure,
    DuplicatePolicy,
    RowFailure,
    UploadFailure,
    failures_from_json,
    failures_to_json,
)

# ---------------------------------------------------------------------------
# DuplicatePolicy
# ---------------------------------------------------------------------------


class TestDuplicatePolicy:
    def test_first_value(self):
        assert DuplicatePolicy.FIRST.value == "FIRST"

    def test_last_value(self):
        assert DuplicatePolicy.LAST.value == "LAST"

    def test_only_two_members(self):
        assert len(list(DuplicatePolicy)) == 2


# ---------------------------------------------------------------------------
# RowFailure
# ---------------------------------------------------------------------------


class TestRowFailure:
    def test_default_errors_are_none(self):
        f = RowFailure(data_type="HR", row_index=0)
        assert f.start_error is None
        assert f.end_error is None

    def test_str_with_errors(self):
        f = RowFailure(
            data_type="HR", row_index=5, start_error="TSDB: Dup", end_error="timeout"
        )
        s = str(f)
        assert "HR" in s
        assert "5" in s
        assert "TSDB: Dup" in s
        assert "timeout" in s

    def test_str_with_no_errors(self):
        f = RowFailure(data_type="HR", row_index=0)
        s = str(f)
        assert "errors=[]" in s

    def test_to_dict_structure(self):
        f = RowFailure(data_type="HR", row_index=42, start_error="err")
        d = f.to_dict()
        assert d["kind"] == "row"
        assert d["data_type"] == "HR"
        assert d["row_index"] == 42
        assert d["start_error"] == "err"
        assert d["end_error"] is None

    def test_from_dict_roundtrip(self):
        original = RowFailure(data_type="Steps", row_index=99, end_error="oops")
        restored = RowFailure.from_dict(original.to_dict())
        assert restored.data_type == original.data_type
        assert restored.row_index == original.row_index
        assert restored.end_error == original.end_error
        assert restored.start_error is None

    def test_from_dict_missing_optional_keys(self):
        d = {"data_type": "X", "row_index": 1}
        f = RowFailure.from_dict(d)
        assert f.start_error is None
        assert f.end_error is None

    def test_row_index_can_be_string(self):
        f = RowFailure(data_type="HR", row_index="abc-123")
        assert f.row_index == "abc-123"

    def test_very_long_error_message(self):
        long_err = "X" * 100_000
        f = RowFailure(data_type="HR", row_index=0, start_error=long_err)
        d = f.to_dict()
        assert d["start_error"] == long_err

    def test_special_chars_in_data_type(self):
        f = RowFailure(data_type="<script>alert(1)</script>", row_index=0)
        d = f.to_dict()
        assert d["data_type"] == "<script>alert(1)</script>"


# ---------------------------------------------------------------------------
# BatchFailure
# ---------------------------------------------------------------------------


class TestBatchFailure:
    def test_str_output(self):
        f = BatchFailure(data_type="HR", error="Connection reset")
        s = str(f)
        assert "HR" in s
        assert "Connection reset" in s

    def test_to_dict_structure(self):
        f = BatchFailure(data_type="Steps", error="timeout")
        d = f.to_dict()
        assert d["kind"] == "batch"
        assert d["data_type"] == "Steps"
        assert d["error"] == "timeout"

    def test_from_dict_roundtrip(self):
        original = BatchFailure(data_type="Calories", error="auth failed")
        restored = BatchFailure.from_dict(original.to_dict())
        assert restored.data_type == original.data_type
        assert restored.error == original.error

    def test_empty_error_string(self):
        f = BatchFailure(data_type="HR", error="")
        assert f.error == ""

    def test_unicode_in_error(self):
        f = BatchFailure(data_type="HR", error="Fehler: Verbindung getrennt 🔌")
        d = f.to_dict()
        assert "🔌" in d["error"]


# ---------------------------------------------------------------------------
# failures_to_json / failures_from_json
# ---------------------------------------------------------------------------


class TestFailuresJson:
    def _sample_failures(self) -> list[UploadFailure]:
        return [
            RowFailure("HR", 0, start_error="dup"),
            BatchFailure("Steps", "timeout"),
            RowFailure("Weight", 99, end_error="overflow"),
        ]

    def test_roundtrip(self):
        failures = self._sample_failures()
        text = failures_to_json(failures)
        restored = failures_from_json(text)
        assert len(restored) == 3
        assert isinstance(restored[0], RowFailure)
        assert isinstance(restored[1], BatchFailure)

    def test_output_is_valid_json(self):
        text = failures_to_json(self._sample_failures())
        parsed = json.loads(text)
        assert isinstance(parsed, list)

    def test_empty_list_roundtrip(self):
        text = failures_to_json([])
        restored = failures_from_json(text)
        assert restored == []

    def test_unknown_kind_raises_value_error(self):
        bad_json = json.dumps([{"kind": "unknown", "data_type": "HR", "error": "x"}])
        with pytest.raises(ValueError, match="Unknown failure kind"):
            failures_from_json(bad_json)

    def test_missing_kind_key_raises(self):
        bad_json = json.dumps([{"data_type": "HR", "error": "x"}])
        with pytest.raises(ValueError):
            failures_from_json(bad_json)

    def test_injection_in_kind_raises(self):
        bad_json = json.dumps(
            [{"kind": "'; DROP TABLE failures;--", "data_type": "HR"}]
        )
        with pytest.raises(ValueError):
            failures_from_json(bad_json)

    def test_large_batch_roundtrip(self):
        failures: list[UploadFailure] = [
            RowFailure(f"Type{i}", i, start_error=f"err{i}") for i in range(10_000)
        ]
        text = failures_to_json(failures)
        restored = failures_from_json(text)
        assert len(restored) == 10_000
        assert restored[9999].row_index == 9999

    def test_pretty_printed_output(self):
        text = failures_to_json([BatchFailure("HR", "err")])
        assert "\n" in text

    def test_invalid_json_raises(self):
        with pytest.raises(json.JSONDecodeError):
            failures_from_json("not json at all {{{")

    def test_null_json_input_raises(self):
        with pytest.raises(TypeError):
            failures_from_json("null")

    def test_row_failure_to_dict_return_type(self):
        assert isinstance(RowFailure("HR", 0).to_dict(), dict)

    def test_from_dict_missing_data_type_raises(self):
        with pytest.raises(KeyError):
            RowFailure.from_dict({"row_index": 0})

    def test_row_index_int_survives_json_roundtrip_as_int(self):
        """JSON round-trip must not silently coerce int row_index to float."""
        original = RowFailure(data_type="HR", row_index=42)
        restored = RowFailure.from_dict(json.loads(json.dumps(original.to_dict())))
        assert restored.row_index == 42
        assert isinstance(restored.row_index, int)

    def test_non_serialisable_row_index_raises(self):
        import pandas as pd

        f = RowFailure(data_type="HR", row_index=pd.Timestamp("2024-01-01"))
        with pytest.raises(TypeError):
            failures_to_json([f])

    def test_batch_failure_to_dict_return_type(self):
        assert isinstance(BatchFailure("HR", "e").to_dict(), dict)

    def test_from_dict_missing_error_raises(self):
        with pytest.raises(KeyError):
            BatchFailure.from_dict({"data_type": "HR"})

    def test_output_is_str(self):
        assert isinstance(failures_to_json(self._sample_failures()), str)

    def test_return_type_is_list(self):
        assert isinstance(
            failures_from_json(failures_to_json(self._sample_failures())), list
        )

    def test_pretty_printed_output_uses_indent_2(self):
        text = failures_to_json([BatchFailure("HR", "err")])
        assert "  " in text

    def test_non_dict_entry_raises(self):
        with pytest.raises((AttributeError, TypeError, ValueError)):
            failures_from_json(json.dumps([1, "string"]))
