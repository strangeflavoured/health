"""Tests for src/importer/importer.py — HealthDataImporter ETL orchestration."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
import redis

from src.importer.importer import (
    HealthDataImporter,
    _load,
    _load_documents,
    _parse_hk_timestamp,
    _sanitize_doc,
    _upload_routes,
)
from src.importer.response import (
    BatchFailure,
    DuplicatePolicy,
    RowFailure,
    failures_to_json,
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


def _make_transformed_df(type_val="HR", n=2) -> pd.DataFrame:
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
        with patch(
            "src.importer.importer.parse_apple_health",
            return_value=(
                pd.DataFrame({"type": ["HR"]}),
                pd.DataFrame(),
                pd.DataFrame(),
                pd.DataFrame(),
                pd.DataFrame(),
            ),
        ) as mock_parse:
            importer.zip_file.touch()
            records, _, _, _ = importer._extract(write_feather=False, no_cache=False)
        mock_parse.assert_called_once()
        assert len(records) == 1

    def test_write_feather_calls_to_feather(self, importer, data_dir):  # noqa: ARG002
        fake_records = MagicMock(spec=pd.DataFrame)
        with patch(
            "src.importer.importer.parse_apple_health",
            return_value=(
                fake_records,
                pd.DataFrame(),
                pd.DataFrame(),
                pd.DataFrame(),
                pd.DataFrame(),
                pd.DataFrame(),
            ),
        ):
            importer.zip_file.touch()
            importer._extract(write_feather=True, no_cache=False)
        fake_records.to_feather.assert_called_once()


# ---------------------------------------------------------------------------
# Failures file I/O
# ---------------------------------------------------------------------------


class TestFailuresFile:
    def test_write_and_read_roundtrip(self, importer):
        failures = [
            RowFailure("HR", 0, start_error="dup"),
            BatchFailure("Steps", 0, "err"),
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
        importer.failures = [BatchFailure("HR", 0, "err")]
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


class TestDocumentHelpers:
    def test_parse_hk_timestamp_none(self):
        assert _parse_hk_timestamp(None) is None

    def test_parse_hk_timestamp_utc(self):
        assert _parse_hk_timestamp("2024-01-01 00:00:00 +0000") == 1_704_067_200

    def test_parse_hk_timestamp_with_offset(self):
        assert _parse_hk_timestamp("2024-01-01 01:00:00 +0100") == 1_704_067_200

    def test_parse_hk_timestamp_returns_int(self):
        assert isinstance(_parse_hk_timestamp("2024-01-01 00:00:00 +0000"), int)

    def test_sanitize_doc_replaces_nan_with_none(self):
        assert _sanitize_doc({"b": float("nan")})["b"] is None

    def test_sanitize_doc_preserves_non_nan(self):
        assert _sanitize_doc({"x": 42, "y": "text"}) == {"x": 42, "y": "text"}

    def test_sanitize_doc_empty(self):
        assert _sanitize_doc({}) == {}


class TestLoadDocuments:
    def _workout_df(self):
        return pd.DataFrame(
            [
                {
                    "workoutActivityType": "HKWorkoutActivityTypeRunning",
                    "sourceName": "Apple Watch",
                    "startDate": "2024-01-01 00:00:00 +0000",
                    "endDate": "2024-01-01 00:30:00 +0000",
                    "duration": "30.0",
                    "durationUnit": "min",
                    "sourceVersion": "9.0",
                    "creationDate": "2024-01-01 00:00:00 +0000",
                    "device": "watch",
                    "meta": {"HKTimeZone": "Europe/Berlin"},
                    "events": [],
                    "statistics": [],
                    "route": None,
                    "activities": [],
                }
            ]
        )

    def _correlation_df(self):
        return pd.DataFrame(
            [
                {
                    "type": "HKCorrelationTypeIdentifierBloodPressure",
                    "sourceName": "Health",
                    "startDate": "2024-01-01 00:00:00 +0000",
                    "endDate": "2024-01-01 00:01:00 +0000",
                    "sourceVersion": "17.0",
                    "creationDate": "2024-01-01 00:00:00 +0000",
                    "meta": {"HKWasUserEntered": "1"},
                    "records": [],
                }
            ]
        )

    def _activity_df(self):
        return pd.DataFrame(
            [
                {
                    "dateComponents": "2024-01-01",
                    "activeEnergyBurned": "450",
                    "activeEnergyBurnedGoal": "500",
                    "activeEnergyBurnedUnit": "kcal",
                    "appleExerciseTime": "35",
                    "appleExerciseTimeGoal": "30",
                    "appleStandHours": "12",
                    "appleStandHoursGoal": "12",
                    "appleMoveTime": None,
                    "appleMoveTimeGoal": None,
                }
            ]
        )

    def test_empty_dfs_are_noop(self, mock_redis):
        _load_documents(pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), mock_redis)
        mock_redis.json.assert_not_called()

    def test_workout_key_prefix(self, mock_redis):
        _load_documents(self._workout_df(), pd.DataFrame(), pd.DataFrame(), mock_redis)
        assert mock_redis.json.return_value.set.call_args[0][0].startswith("workout:")

    def test_workout_start_date_is_integer(self, mock_redis):
        _load_documents(self._workout_df(), pd.DataFrame(), pd.DataFrame(), mock_redis)
        assert isinstance(
            mock_redis.json.return_value.set.call_args[0][2]["startDate"], int
        )

    def test_workout_metakeys_extracted(self, mock_redis):
        _load_documents(self._workout_df(), pd.DataFrame(), pd.DataFrame(), mock_redis)
        assert (
            "HKTimeZone" in mock_redis.json.return_value.set.call_args[0][2]["metaKeys"]
        )

    def test_correlation_key_prefix(self, mock_redis):
        _load_documents(
            pd.DataFrame(), self._correlation_df(), pd.DataFrame(), mock_redis
        )
        assert mock_redis.json.return_value.set.call_args[0][0].startswith(
            "correlation:"
        )

    def test_correlation_metakeys_extracted(self, mock_redis):
        _load_documents(
            pd.DataFrame(), self._correlation_df(), pd.DataFrame(), mock_redis
        )
        assert (
            "HKWasUserEntered"
            in mock_redis.json.return_value.set.call_args[0][2]["metaKeys"]
        )

    def test_activity_key_uses_date_components(self, mock_redis):
        _load_documents(pd.DataFrame(), pd.DataFrame(), self._activity_df(), mock_redis)
        assert "2024-01-01" in mock_redis.json.return_value.set.call_args[0][0]

    def test_activity_doc_has_date_integer_field(self, mock_redis):
        _load_documents(pd.DataFrame(), pd.DataFrame(), self._activity_df(), mock_redis)
        assert isinstance(mock_redis.json.return_value.set.call_args[0][2]["date"], int)

    def test_nan_sanitized_to_none(self, mock_redis):
        df = self._activity_df()
        df.loc[0, "appleMoveTime"] = float("nan")
        _load_documents(pd.DataFrame(), pd.DataFrame(), df, mock_redis)
        assert mock_redis.json.return_value.set.call_args[0][2]["appleMoveTime"] is None

    def test_mixed_upload_counts(self, mock_redis):
        _load_documents(
            self._workout_df(), self._correlation_df(), self._activity_df(), mock_redis
        )
        assert mock_redis.json.return_value.set.call_count == 3


class TestParseRoutes:
    def test_empty_workout_df_returns_empty(self, importer):
        assert importer._parse_routes(pd.DataFrame()).empty

    def test_workout_with_none_route_returns_empty(self, importer):
        assert importer._parse_routes(pd.DataFrame([{"route": None}])).empty

    def test_workout_with_empty_files_returns_empty(self, importer):
        assert importer._parse_routes(
            pd.DataFrame([{"route": {"files": [], "meta": {}}}])
        ).empty

    def test_calls_parse_routes_with_collected_paths(self, importer):
        df = pd.DataFrame(
            [
                {
                    "route": {"files": ["workout-routes/r.gpx"], "meta": {}},
                    "workoutActivityType": "Run",
                    "startDate": "2024-01-01 00:00:00 +0000",
                    "endDate": "2024-01-01 00:30:00 +0000",
                }
            ]
        )
        with patch(
            "src.importer.importer.parse_apple_health_routes",
            return_value=pd.DataFrame(),
        ) as mock_r:
            importer.zip_file.touch()
            importer._parse_routes(df)
        mock_r.assert_called_once()

    def test_multiple_workouts_all_paths_collected(self, importer):
        df = pd.DataFrame(
            [
                {"route": {"files": ["r1.gpx"], "meta": {}}},
                {"route": {"files": ["r2.gpx", "r3.gpx"], "meta": {}}},
            ]
        )
        with patch(
            "src.importer.importer.parse_apple_health_routes",
            return_value=pd.DataFrame(),
        ) as mock_r:
            importer.zip_file.touch()
            importer._parse_routes(df)
        called_paths = mock_r.call_args[1].get("paths") or mock_r.call_args[0][1]
        assert set(called_paths) == {"r1.gpx", "r2.gpx", "r3.gpx"}


class TestUploadRoutes:
    def _routes_df(self):
        return pd.DataFrame(
            [
                {
                    "file": "workout-routes/r.gpx",
                    "lat": 52.52,
                    "lon": 13.40,
                    "ele": 34.5,
                    "time": pd.Timestamp("2024-01-01T09:00:00Z"),
                    "speed": 2.83,
                    "course": 274.5,
                    "hAcc": 4.2,
                    "vAcc": 3.1,
                },
                {
                    "file": "workout-routes/r.gpx",
                    "lat": 52.521,
                    "lon": 13.401,
                    "ele": 35.0,
                    "time": pd.Timestamp("2024-01-01T09:00:01Z"),
                    "speed": 3.0,
                    "course": 275.0,
                    "hAcc": 4.0,
                    "vAcc": 3.0,
                },
            ]
        )

    def _workouts_df(self):
        return pd.DataFrame(
            [
                {
                    "workoutActivityType": "HKWorkoutActivityTypeRunning",
                    "startDate": "2024-01-01 00:00:00 +0000",
                    "endDate": "2024-01-01 00:30:00 +0000",
                    "route": {"files": ["workout-routes/r.gpx"], "meta": {}},
                }
            ]
        )

    def test_empty_routes_is_noop(self, mock_redis):
        _upload_routes(pd.DataFrame(), self._workouts_df(), mock_redis)
        mock_redis.json.assert_not_called()

    def test_empty_workouts_is_noop(self, mock_redis):
        _upload_routes(self._routes_df(), pd.DataFrame(), mock_redis)
        mock_redis.json.assert_not_called()

    def test_route_key_prefix(self, mock_redis):
        _upload_routes(self._routes_df(), self._workouts_df(), mock_redis)
        assert mock_redis.json.return_value.set.call_args[0][0].startswith("route:")

    def test_route_key_contains_activity_type(self, mock_redis):
        _upload_routes(self._routes_df(), self._workouts_df(), mock_redis)
        assert (
            "HKWorkoutActivityTypeRunning"
            in mock_redis.json.return_value.set.call_args[0][0]
        )

    def test_route_doc_has_trackpoints_list(self, mock_redis):
        _upload_routes(self._routes_df(), self._workouts_df(), mock_redis)
        doc = mock_redis.json.return_value.set.call_args[0][2]
        assert isinstance(doc["trackpoints"], list) and len(doc["trackpoints"]) == 2

    def test_trackpoint_time_is_integer(self, mock_redis):
        _upload_routes(self._routes_df(), self._workouts_df(), mock_redis)
        for tp in mock_redis.json.return_value.set.call_args[0][2]["trackpoints"]:
            assert isinstance(tp["time"], int)

    def test_trackpoint_nan_sanitized_to_none(self, mock_redis):
        routes = self._routes_df().copy()
        routes.loc[0, "ele"] = float("nan")
        _upload_routes(routes, self._workouts_df(), mock_redis)
        assert (
            mock_redis.json.return_value.set.call_args[0][2]["trackpoints"][0]["ele"]
            is None
        )

    def test_workout_without_route_skipped(self, mock_redis):
        workouts = pd.DataFrame(
            [
                {
                    "workoutActivityType": "Run",
                    "startDate": "2024-01-01 00:00:00 +0000",
                    "endDate": "2024-01-01 00:30:00 +0000",
                    "route": None,
                }
            ]
        )
        _upload_routes(self._routes_df(), workouts, mock_redis)
        mock_redis.json.assert_not_called()

    def test_uses_dollar_json_path(self, mock_redis):
        _upload_routes(self._routes_df(), self._workouts_df(), mock_redis)
        assert mock_redis.json.return_value.set.call_args[0][1] == "$"


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
        df = self._make_df()
        mock_redis.ts.return_value.pipeline.return_value.execute.side_effect = (
            redis.RedisError("conn lost")
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

    def test_feather_cache_returns_empty_other_dfs(self, importer):
        """Reading from the Feather cache must return empty DataFrames for
        correlations, workouts, and activities."""
        with patch(
            "src.importer.importer.feather.read_feather",
            return_value=pd.DataFrame({"type": ["HR"]}),
        ):
            importer.output_file.touch()
            _, correlations, workouts, activities, routes = importer._extract(
                write_feather=False, no_cache=False
            )
        assert (
            correlations.empty and workouts.empty and activities.empty and routes.empty
        )

    def test_returns_five_dataframes(self, importer):
        with patch(
            "src.importer.importer.parse_apple_health",
            return_value=(
                pd.DataFrame({"type": ["HR"]}),
                pd.DataFrame(),
                pd.DataFrame(),
                pd.DataFrame(),
                pd.DataFrame(),
            ),
        ):
            importer.zip_file.touch()
            result = importer._extract(write_feather=False, no_cache=False)

        assert isinstance(result, tuple) and len(result) == 5

    def test_no_cache_true_bypasses_feather(self, importer):
        """no_cache=True must skip the feather cache even when it exists."""
        with (
            patch(
                "src.importer.importer.parse_apple_health",
                return_value=(
                    pd.DataFrame({"type": ["HR"]}),
                    pd.DataFrame(),
                    pd.DataFrame(),
                    pd.DataFrame(),
                    pd.DataFrame(),
                ),
            ) as mock_parse,
            patch("src.importer.importer.feather.read_feather") as mock_feather,
        ):
            importer.output_file.touch()
            importer.zip_file.touch()
            importer._extract(write_feather=False, no_cache=True)
        mock_parse.assert_called_once()
        mock_feather.assert_not_called()

    def test_no_cache_false_uses_feather_when_present(self, importer):
        expected_df = pd.DataFrame({"type": ["HR"]})
        with patch(
            "src.importer.importer.feather.read_feather", return_value=expected_df
        ) as m:
            importer.output_file.touch()
            importer._extract(write_feather=False, no_cache=False)
        m.assert_called_once()

    def test_read_failures_file_returns_correct_types(self, importer):
        failures = [RowFailure("HR", 5, start_error="e"), BatchFailure("Steps", 0, "t")]
        importer._write_failures_file(failures)
        restored = importer._read_failures_file()
        assert isinstance(restored[0], RowFailure)
        assert isinstance(restored[1], BatchFailure)

    def test_index_error_creates_batch_failure(self, mock_redis):
        """_load catches IndexError from upload_batch and wraps it in BatchFailure."""
        with patch(
            "src.importer.importer.upload_batch", side_effect=IndexError("mismatch")
        ):
            result = _load(self._make_df(), mock_redis)
        assert len(result) == 1 and isinstance(result[0], BatchFailure)

    def test_single_row_df(self, mock_redis):
        mock_redis.ts.return_value.pipeline.return_value.execute.return_value = [1, 2]
        assert _load(self._make_df(n=1), mock_redis) == []

    def test_return_type_is_list(self, mock_redis):
        mock_redis.ts.return_value.pipeline.return_value.execute.return_value = [
            1,
            2,
            3,
            4,
        ]
        assert isinstance(_load(self._make_df(), mock_redis), list)


# ---------------------------------------------------------------------------
# etl
# ---------------------------------------------------------------------------


class TestEtl:
    def test_etl_sets_failures_on_success(self, importer):
        df = _make_transformed_df()
        with (
            patch.object(importer, "_extract_records_only", return_value=df),
            patch("src.importer.importer.transform"),
            patch("src.importer.importer._load", return_value=[]) as mock_load,
            patch.object(importer, "_update_failures_file"),
        ):
            importer.etl()
        assert importer.failures == []
        mock_load.assert_called_once()

    def test_etl_stores_failures(self, importer):
        df = _make_transformed_df()
        failures = [BatchFailure("HR", 0, "err")]
        with (
            patch.object(importer, "_extract_records_only", return_value=df),
            patch("src.importer.importer.transform"),
            patch("src.importer.importer._load", return_value=failures),
            patch.object(importer, "_update_failures_file"),
        ):
            importer.etl()
        assert importer.failures == failures

    def test_etl_calls_upload_routes(self, importer):
        df = _make_transformed_df()
        with (
            patch.object(
                importer,
                "_extract",
                return_value=(
                    df,
                    pd.DataFrame(),
                    pd.DataFrame(),
                    pd.DataFrame(),
                    pd.DataFrame(),
                ),
            ),
            patch("src.importer.importer.transform"),
            patch("src.importer.importer._load", return_value=[]),
            patch("src.importer.importer._load_documents"),
            patch("src.importer.importer._upload_routes") as mock_routes,
            patch.object(importer, "_update_failures_file"),
        ):
            importer.etl()
        mock_routes.assert_called_once()

    def test_etl_calls_load_documents(self, importer):
        df = _make_transformed_df()
        with (
            patch.object(importer, "_extract_records_only", return_value=df),
            patch("src.importer.importer.transform"),
            patch("src.importer.importer._load", return_value=[]),
            patch("src.importer.importer._load_documents") as mock_doc,
            patch.object(importer, "_update_failures_file"),
        ):
            importer.etl()
        mock_doc.assert_called_once()

    def test_etl_persist_failures_true_calls_update(self, importer):
        df = _make_transformed_df()
        with (
            patch.object(importer, "_extract_records_only", return_value=df),
            patch("src.importer.importer.transform"),
            patch("src.importer.importer._load", return_value=[]),
            patch.object(importer, "_update_failures_file") as mock_upd,
        ):
            importer.etl(persist_failures=True)
        mock_upd.assert_called_once()

    def test_etl_persist_failures_false_skips_update(self, importer):
        df = _make_transformed_df()
        with (
            patch.object(importer, "_extract_records_only", return_value=df),
            patch("src.importer.importer.transform"),
            patch("src.importer.importer._load", return_value=[]),
            patch.object(importer, "_update_failures_file") as mock_upd,
        ):
            importer.etl(persist_failures=False)
        mock_upd.assert_not_called()

    def test_etl_no_cache_forwarded(self, importer):
        df = _make_transformed_df()
        with (
            patch.object(
                importer, "_extract_records_only", return_value=df
            ) as mock_extract,
            patch("src.importer.importer.transform"),
            patch("src.importer.importer._load", return_value=[]),
            patch.object(importer, "_update_failures_file"),
        ):
            importer.etl(no_cache=True)
        assert mock_extract.call_args[1]["no_cache"] is True

    def test_etl_uses_duplicate_policy_first(self, importer):
        df = _make_transformed_df()
        with (
            patch.object(importer, "_extract_records_only", return_value=df),
            patch("src.importer.importer.transform"),
            patch("src.importer.importer._load", return_value=[]) as mock_load,
            patch.object(importer, "_update_failures_file"),
        ):
            importer.etl()
        _, kwargs = mock_load.call_args
        assert (
            kwargs.get("duplicate_policy", DuplicatePolicy.FIRST)
            == DuplicatePolicy.FIRST
        )


# ---------------------------------------------------------------------------
# update
# ---------------------------------------------------------------------------


class TestUpdate:
    def test_update_calls_upload_routes(self, importer):
        df = _make_transformed_df()
        with (
            patch.object(importer, "_extract_records_only", return_value=df),
            patch("src.importer.importer.transform"),
            patch("src.importer.importer._load", return_value=[]),
            patch("src.importer.importer._load_documents"),
            patch("src.importer.importer._upload_routes") as mock_routes,
            patch.object(importer, "_update_failures_file"),
        ):
            importer.update()
        mock_routes.assert_called_once()

    def test_update_uses_duplicate_policy_last(self, importer):
        df = _make_transformed_df()
        with (
            patch.object(importer, "_extract_records_only", return_value=df),
            patch("src.importer.importer.transform"),
            patch("src.importer.importer._load", return_value=[]) as mock_load,
            patch.object(importer, "_update_failures_file"),
        ):
            importer.update()
        _, kwargs = mock_load.call_args
        assert kwargs["duplicate_policy"] == DuplicatePolicy.LAST

    def test_update_stores_failures(self, importer):
        df = _make_transformed_df()
        failures = [BatchFailure("HR", 0, "err")]
        with (
            patch.object(importer, "_extract_records_only", return_value=df),
            patch("src.importer.importer.transform"),
            patch("src.importer.importer._load", return_value=failures),
            patch.object(importer, "_update_failures_file"),
        ):
            importer.update()
        assert importer.failures == failures

    def test_update_persist_failures_false_skips(self, importer):
        df = _make_transformed_df()
        with (
            patch.object(importer, "_extract_records_only", return_value=df),
            patch("src.importer.importer.transform"),
            patch("src.importer.importer._load", return_value=[]),
            patch.object(importer, "_update_failures_file") as mock_upd,
        ):
            importer.update(persist_failures=False)
        mock_upd.assert_not_called()

    def test_update_no_cache_forwarded(self, importer):
        df = _make_transformed_df()
        with (
            patch.object(
                importer, "_extract_records_only", return_value=df
            ) as mock_extract,
            patch("src.importer.importer.transform"),
            patch("src.importer.importer._load", return_value=[]),
            patch.object(importer, "_update_failures_file"),
        ):
            importer.update(no_cache=True)
        assert mock_extract.call_args[1]["no_cache"] is True


# ---------------------------------------------------------------------------
# retry_failed
# ---------------------------------------------------------------------------


class TestRetryFailed:
    def _write_failures(self, importer, failures):
        importer.failures_file.write_text(failures_to_json(failures), encoding="utf-8")

    def test_retry_raises_when_no_failures_file(self, importer):
        with pytest.raises(FileNotFoundError):
            importer.retry_failed()

    def test_retry_empty_file_deletes_file_and_returns(self, importer):
        self._write_failures(importer, [])
        importer.retry_failed()
        assert not importer.failures_file.exists()

    def test_retry_row_failures_subset_loaded(self, importer):
        df = _make_transformed_df(n=4)
        df.index = [0, 1, 2, 3]
        self._write_failures(importer, [RowFailure("HR", 1, start_error="dup")])
        with (
            patch.object(importer, "_extract_records_only", return_value=df),
            patch("src.importer.importer.transform"),
            patch("src.importer.importer._load", return_value=[]) as mock_load,
            patch.object(importer, "_update_failures_file"),
        ):
            importer.retry_failed()
        loaded_df = mock_load.call_args[1]["df"]
        assert 1 in loaded_df.index

    def test_retry_batch_failures_whole_type_loaded(self, importer):
        df = _make_transformed_df(type_val="HR", n=3)
        self._write_failures(importer, [BatchFailure("HR", 0, "conn lost")])
        with (
            patch.object(importer, "_extract_records_only", return_value=df),
            patch("src.importer.importer.transform"),
            patch("src.importer.importer._load", return_value=[]) as mock_load,
            patch.object(importer, "_update_failures_file"),
        ):
            importer.retry_failed()
        loaded_df = mock_load.call_args[1]["df"]
        assert (loaded_df["type"] == "HR").all()
        assert len(loaded_df) == 3

    def test_retry_does_not_call_load_documents(self, importer):
        df = _make_transformed_df(n=2)
        self._write_failures(importer, [RowFailure("HR", 0, start_error="e")])
        with (
            patch.object(importer, "_extract_records_only", return_value=df),
            patch("src.importer.importer.transform"),
            patch("src.importer.importer._load", return_value=[]),
            patch("src.importer.importer._load_documents") as mock_doc,
            patch("src.importer.importer._upload_routes") as mock_routes,
        ):
            importer.retry_failed(persist_failures=True)
        mock_doc.assert_not_called()
        mock_routes.assert_not_called()

    def test_retry_all_resolved_deletes_file(self, importer):
        df = _make_transformed_df(n=2)
        self._write_failures(importer, [RowFailure("HR", 0, start_error="e")])
        with (
            patch.object(importer, "_extract_records_only", return_value=df),
            patch("src.importer.importer.transform"),
            patch("src.importer.importer._load", return_value=[]),
        ):
            importer.retry_failed(persist_failures=True)
        assert not importer.failures_file.exists()

    def test_retry_partial_resolution_overwrites_file(self, importer):
        df = _make_transformed_df(n=2)
        remaining = [RowFailure("HR", 1, end_error="still bad")]
        self._write_failures(importer, [RowFailure("HR", 0), RowFailure("HR", 1)])
        with (
            patch.object(importer, "_extract_records_only", return_value=df),
            patch("src.importer.importer.transform"),
            patch("src.importer.importer._load", return_value=remaining),
        ):
            importer.retry_failed(persist_failures=True)
        assert importer.failures_file.exists()
        assert importer.failures == remaining

    def test_retry_uses_duplicate_policy_first(self, importer):
        df = _make_transformed_df(n=1)
        self._write_failures(importer, [RowFailure("HR", 0)])
        with (
            patch.object(importer, "_extract_records_only", return_value=df),
            patch("src.importer.importer.transform"),
            patch("src.importer.importer._load", return_value=[]) as mock_load,
            patch.object(importer, "_update_failures_file"),
        ):
            importer.retry_failed()
        assert mock_load.call_args[1]["duplicate_policy"] == DuplicatePolicy.FIRST

    def test_retry_persist_failures_false_skips_update(self, importer):
        df = _make_transformed_df(n=1)
        self._write_failures(importer, [RowFailure("HR", 0)])
        with (
            patch.object(importer, "_extract_records_only", return_value=df),
            patch("src.importer.importer.transform"),
            patch("src.importer.importer._load", return_value=[]),
            patch.object(importer, "_update_failures_file") as mock_upd,
        ):
            importer.retry_failed(persist_failures=False)
        mock_upd.assert_not_called()
