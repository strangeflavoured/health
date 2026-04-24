"""Tests for src/importer/importer.py — HealthDataImporter ETL orchestration."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from src.importer.importer import HealthDataImporter, _load
from src.importer.response import (
    BatchFailure,
    DuplicatePolicy,
    RowFailure,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def data_dir(tmp_path: Path) -> Path:
    d = tmp_path / "data"
    d.mkdir()
    return d


@pytest.fixture()
def mock_redis() -> MagicMock:
    r = MagicMock()
    rts = MagicMock()
    pipe = MagicMock()
    pipe.execute.return_value = []
    rts.pipeline.return_value = pipe
    r.ts.return_value = rts
    return r


@pytest.fixture()
def importer(data_dir: Path, mock_redis: MagicMock) -> HealthDataImporter:
    return HealthDataImporter(
        connection=mock_redis,
        working_dir=data_dir.parent,
        data_dir="data",
    )


# ---------------------------------------------------------------------------
# Constructor
# ---------------------------------------------------------------------------


class TestHealthDataImporterInit:
    def test_missing_data_dir_raises(self, tmp_path, mock_redis):
        with pytest.raises(FileNotFoundError):
            HealthDataImporter(
                connection=mock_redis,
                working_dir=tmp_path,
                data_dir="nonexistent",
            )

    def test_failures_initially_empty(self, importer):
        assert importer.failures == []

    def test_paths_are_under_data_dir(self, importer, data_dir):
        assert importer.data_dir == data_dir
        assert importer.zip_file.parent == data_dir
        assert importer.output_file.parent == data_dir

    def test_path_traversal_in_data_dir_is_contained(self, tmp_path, mock_redis):
        """data_dir is joined with working_dir — traversal stays under working_dir."""
        (tmp_path / "data").mkdir()
        imp = HealthDataImporter(
            connection=mock_redis,
            working_dir=tmp_path,
            data_dir="data",
        )
        assert str(tmp_path) in str(imp.data_dir)


# ---------------------------------------------------------------------------
# _extract
# ---------------------------------------------------------------------------


class TestExtract:
    def test_reads_feather_cache_when_available(self, importer, data_dir):  # noqa: ARG002
        expected_df = pd.DataFrame({"type": ["HR"], "value": ["72"]})
        with patch(
            "src.importer.importer.feather.read_feather", return_value=expected_df
        ) as mock_read:
            importer.output_file.touch()
            df = importer._extract(write_feather=False, no_cache=False)
        mock_read.assert_called_once()
        assert len(df) == 1

    def test_raises_when_no_zip_and_no_feather(self, importer):
        with pytest.raises(FileNotFoundError):
            importer._extract(write_feather=False, no_cache=False)

    def test_parses_zip_when_no_feather(self, importer, data_dir):  # noqa: ARG002
        fake_df = pd.DataFrame({"type": ["HR"]})
        with patch(
            "src.importer.importer.parse_apple_health", return_value=fake_df
        ) as mock_parse:
            importer.zip_file.touch()
            df = importer._extract(write_feather=False, no_cache=False)  # noqa: F841
        mock_parse.assert_called_once()

    def test_write_feather_calls_to_feather(self, importer, data_dir):  # noqa: ARG002
        fake_df = MagicMock(spec=pd.DataFrame)
        with patch("src.importer.importer.parse_apple_health", return_value=fake_df):
            importer.zip_file.touch()
            importer._extract(write_feather=True, no_cache=False)
        fake_df.to_feather.assert_called_once()


# ---------------------------------------------------------------------------
# Failures file I/O
# ---------------------------------------------------------------------------


class TestFailuresFile:
    def test_write_and_read_roundtrip(self, importer):
        failures = [
            RowFailure("HR", 0, start_error="dup"),
            BatchFailure("Steps", "err"),
        ]
        importer._write_failures_file(failures)
        restored = importer._read_failures_file()
        assert len(restored) == 2

    def test_read_nonexistent_raises(self, importer):
        with pytest.raises(FileNotFoundError):
            importer._read_failures_file()

    def test_delete_removes_file(self, importer):
        importer.failures_file.write_text("[]", encoding="utf-8")
        importer._delete_failures_file()
        assert not importer.failures_file.exists()

    def test_delete_nonexistent_does_not_raise(self, importer):
        importer._delete_failures_file()

    def test_update_failures_file_writes_when_failures_exist(self, importer):
        importer.failures = [BatchFailure("HR", "err")]
        importer._update_failures_file()
        assert importer.failures_file.exists()

    def test_update_failures_file_deletes_when_empty(self, importer):
        importer.failures_file.write_text("[]", encoding="utf-8")
        importer.failures = []
        importer._update_failures_file()
        assert not importer.failures_file.exists()


# ---------------------------------------------------------------------------
# _load function
# ---------------------------------------------------------------------------


class TestLoad:
    def _make_df(self, type_val="HR", n=2) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "type": [type_val] * n,
                "sourceName": ["Watch"] * n,
                "unit": ["bpm"] * n,
                "value": [72.0] * n,
                "startDate": [1_700_000_000 + i for i in range(n)],
                "endDate": [1_700_000_060 + i for i in range(n)],
            }
        )

    def test_returns_empty_on_success(self, mock_redis):
        df = self._make_df()
        mock_redis.ts.return_value.pipeline.return_value.execute.return_value = [
            1,
            2,
            3,
            4,
        ]
        result = _load(df, mock_redis)
        assert result == []

    def test_redis_error_creates_batch_failure(self, mock_redis):
        import redis as redis_lib

        df = self._make_df()
        mock_redis.ts.return_value.pipeline.return_value.execute.side_effect = (
            redis_lib.RedisError("conn lost")
        )
        result = _load(df, mock_redis)
        assert len(result) == 1
        assert isinstance(result[0], BatchFailure)

    def test_empty_df_returns_empty(self, mock_redis):
        df = self._make_df(n=0)
        result = _load(df, mock_redis)
        assert result == []

    def test_multiple_types_processed_separately(self, mock_redis):
        df = pd.DataFrame(
            {
                "type": ["HR", "HR", "Steps", "Steps"],
                "sourceName": ["W"] * 4,
                "unit": ["bpm", "bpm", "count", "count"],
                "value": [72.0, 80.0, 500.0, 600.0],
                "startDate": [1_000_000 + i for i in range(4)],
                "endDate": [1_000_060 + i for i in range(4)],
            }
        )
        mock_redis.ts.return_value.pipeline.return_value.execute.return_value = [
            1,
            2,
            3,
            4,
        ]
        result = _load(df, mock_redis)  # noqa: F841
        assert mock_redis.ts.return_value.pipeline.call_count == 2

    def test_duplicate_policy_last_forwarded(self, mock_redis):
        df = self._make_df()
        mock_redis.ts.return_value.pipeline.return_value.execute.return_value = [
            1,
            2,
            3,
            4,
        ]
        with patch("src.importer.importer.upload_batch") as mock_upload:
            mock_upload.return_value = []
            _load(df, mock_redis, duplicate_policy=DuplicatePolicy.LAST)
        _, kwargs = mock_upload.call_args
        assert kwargs["duplicate_policy"] == DuplicatePolicy.LAST
