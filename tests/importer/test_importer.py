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


def _empty_parse_return(records: pd.DataFrame | None = None):
    """5-tuple suitable for mocking parse_apple_health."""
    if records is None:
        records = pd.DataFrame({"type": ["HR"]})
    return (records, pd.DataFrame(), pd.DataFrame(), pd.DataFrame())


def _empty_extract_return(records: pd.DataFrame | None = None):
    """5-tuple suitable for mocking _extract (includes routes)."""
    if records is None:
        records = pd.DataFrame({"type": ["HR"]})
    return (records, pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame())


def _make_transformed_df(type_val="HR", n=2) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "type": [type_val] * n,
            "sourceName": ["Watch"] * n,
            "unit": ["bpm"] * n,
            "value": [72.0] * n,
            "startDate": [1_700_000_000 + i for i in range(n)],
            "endDate": [1_700_000_060 + i for i in range(n)],
            "group": ["vital_signs"] * n,
        }
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

    def test_sibling_cache_paths_exist_under_data_dir(self, importer, data_dir):
        """All five cache paths must live inside data_dir regardless of format."""
        for attr in (
            "output_file",
            "workouts_file",
            "correlations_file",
            "activities_file",
            "routes_file",
        ):
            assert getattr(importer, attr).parent == data_dir

    def test_sibling_cache_paths_share_stem(self, importer):
        stem = importer.output_file.stem
        assert stem in importer.workouts_file.name
        assert stem in importer.correlations_file.name
        assert stem in importer.activities_file.name
        assert stem in importer.routes_file.name

    def test_path_traversal_in_data_dir_is_contained(self, tmp_path, mock_redis):
        (tmp_path / "data").mkdir()
        imp = HealthDataImporter(
            connection=mock_redis,
            working_dir=tmp_path,
            data_dir="data",
        )
        assert str(tmp_path) in str(imp.data_dir)


# ---------------------------------------------------------------------------
# Feather encode / decode helpers
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# _all_caches_exist / _write_all_caches / _read_all_caches
# ---------------------------------------------------------------------------


class TestFeatherCacheHelpers:
    def test_all_caches_exist_false_when_none_present(self, importer):
        assert importer._all_caches_exist() is False

    def test_all_caches_exist_false_when_partial(self, importer):
        importer.output_file.touch()
        importer.workouts_file.touch()
        assert importer._all_caches_exist() is False

    def test_all_caches_exist_true_when_all_present(self, importer):
        for p in (
            importer.output_file,
            importer.workouts_file,
            importer.correlations_file,
            importer.activities_file,
            importer.routes_file,
        ):
            p.touch()
        assert importer._all_caches_exist() is True

    def test_workouts_and_correlations_use_pkl_extension(self, importer):
        """The tables with nested objects must use .pkl, not .feather."""
        assert importer.workouts_file.suffix == ".pkl"
        assert importer.correlations_file.suffix == ".pkl"

    def test_records_activities_routes_use_feather_extension(self, importer):
        assert importer.output_file.suffix == ".feather"
        assert importer.activities_file.suffix == ".feather"
        assert importer.routes_file.suffix == ".feather"

    def _simple_records(self) -> pd.DataFrame:
        return pd.DataFrame({"type": ["HR"], "value": ["72"]})

    def _simple_workouts(self) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "workoutActivityType": "HKWorkoutActivityTypeRunning",
                    "sourceName": "Watch",
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

    def _simple_correlations(self) -> pd.DataFrame:
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

    def _simple_activities(self) -> pd.DataFrame:
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

    def _simple_routes(self) -> pd.DataFrame:
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
                }
            ]
        )

    def test_write_all_caches_creates_five_files(self, importer):
        importer._write_all_caches(
            self._simple_records(),
            self._simple_correlations(),
            self._simple_workouts(),
            self._simple_activities(),
            self._simple_routes(),
        )
        assert importer.output_file.exists()  # records  (.feather)
        assert importer.workouts_file.exists()  # workouts (.pkl)
        assert importer.correlations_file.exists()  # correlations (.pkl)
        assert importer.activities_file.exists()  # activities (.feather)
        assert importer.routes_file.exists()  # routes (.feather)

    def test_read_all_caches_returns_five_dataframes(self, importer):
        importer._write_all_caches(
            self._simple_records(),
            self._simple_correlations(),
            self._simple_workouts(),
            self._simple_activities(),
            self._simple_routes(),
        )
        result = importer._read_all_caches()
        assert isinstance(result, tuple) and len(result) == 5
        assert all(isinstance(df, pd.DataFrame) for df in result)

    def test_read_all_caches_round_trips_records(self, importer):
        records = self._simple_records()
        importer._write_all_caches(
            records,
            self._simple_correlations(),
            self._simple_workouts(),
            self._simple_activities(),
            self._simple_routes(),
        )
        loaded_records, _, _, _, _ = importer._read_all_caches()
        assert list(loaded_records["type"]) == list(records["type"])

    def test_workout_complex_cols_survive_round_trip(self, importer):
        """Native Python dicts/lists must be restored without any encode step."""
        importer._write_all_caches(
            self._simple_records(),
            self._simple_correlations(),
            self._simple_workouts(),
            self._simple_activities(),
            self._simple_routes(),
        )
        _, _, workouts, _, _ = importer._read_all_caches()
        assert isinstance(workouts.iloc[0]["meta"], dict)
        assert workouts.iloc[0]["meta"] == {"HKTimeZone": "Europe/Berlin"}
        assert isinstance(workouts.iloc[0]["events"], list)

    def test_correlation_complex_cols_survive_round_trip(self, importer):
        importer._write_all_caches(
            self._simple_records(),
            self._simple_correlations(),
            self._simple_workouts(),
            self._simple_activities(),
            self._simple_routes(),
        )
        _, correlations, _, _, _ = importer._read_all_caches()
        assert isinstance(correlations.iloc[0]["meta"], dict)
        assert correlations.iloc[0]["meta"] == {"HKWasUserEntered": "1"}

    def test_none_route_field_survives_round_trip(self, importer):
        """None in a complex column must not become a JSON string or NaN."""
        workouts = self._simple_workouts()
        assert workouts.iloc[0]["route"] is None
        importer._write_all_caches(
            self._simple_records(),
            self._simple_correlations(),
            workouts,
            self._simple_activities(),
            self._simple_routes(),
        )
        _, _, loaded_workouts, _, _ = importer._read_all_caches()
        assert loaded_workouts.iloc[0]["route"] is None

    def test_read_all_caches_round_trips_routes(self, importer):
        routes = self._simple_routes()
        importer._write_all_caches(
            self._simple_records(),
            self._simple_correlations(),
            self._simple_workouts(),
            self._simple_activities(),
            routes,
        )
        _, _, _, _, loaded_routes = importer._read_all_caches()
        assert len(loaded_routes) == 1
        assert loaded_routes.iloc[0]["lat"] == pytest.approx(52.52)

    def test_read_all_caches_preserves_route_timestamps(self, importer):
        routes = self._simple_routes()
        importer._write_all_caches(
            self._simple_records(),
            self._simple_correlations(),
            self._simple_workouts(),
            self._simple_activities(),
            routes,
        )
        _, _, _, _, loaded_routes = importer._read_all_caches()
        assert pd.api.types.is_datetime64_any_dtype(loaded_routes["time"])


# ---------------------------------------------------------------------------
# _extract
# ---------------------------------------------------------------------------


class TestExtract:
    def test_reads_from_all_caches_when_all_present(self, importer, data_dir):  # noqa: ARG002
        for p in (
            importer.output_file,
            importer.workouts_file,
            importer.correlations_file,
            importer.activities_file,
            importer.routes_file,
        ):
            p.touch()

        with patch.object(
            importer, "_read_all_caches", return_value=_empty_extract_return()
        ) as mock_read:
            importer._extract(write_feather=False, no_cache=False)
        mock_read.assert_called_once()

    def test_skips_cache_when_partial(self, importer):
        """Partial cache (missing some files) must fall through to ZIP parse."""

        importer.output_file.touch()
        importer.workouts_file.touch()
        # activities / correlations / routes NOT created
        with (
            patch(
                "src.importer.importer.parse_apple_health",
                return_value=_empty_parse_return(),
            ),
            patch.object(importer, "_parse_routes", return_value=pd.DataFrame()),
        ):
            importer.zip_file.touch()
            result = importer._extract(write_feather=False, no_cache=False)

        assert isinstance(result, tuple) and len(result) == 5

    def test_raises_when_no_zip_and_no_caches(self, importer):  # noqa: ARG002
        with pytest.raises(FileNotFoundError):
            importer._extract(write_feather=False, no_cache=False)

    def test_parses_zip_when_no_caches(self, importer):  # noqa: ARG002
        with (
            patch(
                "src.importer.importer.parse_apple_health",
                return_value=_empty_parse_return(),
            ) as mock_parse,
            patch.object(importer, "_parse_routes", return_value=pd.DataFrame()),
        ):
            importer.zip_file.touch()
            result = importer._extract(write_feather=False, no_cache=False)
        mock_parse.assert_called_once()
        assert len(result) == 5

    def test_write_feather_calls_write_all_caches(self, importer):  # noqa: ARG002
        with (
            patch(
                "src.importer.importer.parse_apple_health",
                return_value=_empty_parse_return(),
            ),
            patch.object(importer, "_parse_routes", return_value=pd.DataFrame()),
            patch.object(importer, "_write_all_caches") as mock_write,
        ):
            importer.zip_file.touch()
            importer._extract(write_feather=True, no_cache=False)
        mock_write.assert_called_once()

    def test_no_cache_bypasses_complete_cache(self, importer):
        """no_cache=True must bypass even a complete set of caches."""
        for p in (
            importer.output_file,
            importer.workouts_file,
            importer.correlations_file,
            importer.activities_file,
            importer.routes_file,
        ):
            p.touch()
        with (
            patch(
                "src.importer.importer.parse_apple_health",
                return_value=_empty_parse_return(),
            ) as mock_parse,
            patch.object(importer, "_parse_routes", return_value=pd.DataFrame()),
            patch.object(importer, "_read_all_caches") as mock_read,
        ):
            importer.zip_file.touch()
            importer._extract(write_feather=False, no_cache=True)
        mock_parse.assert_called_once()
        mock_read.assert_not_called()

    def test_returns_five_dataframes(self, importer):
        with (
            patch(
                "src.importer.importer.parse_apple_health",
                return_value=_empty_parse_return(),
            ),
            patch.object(importer, "_parse_routes", return_value=pd.DataFrame()),
        ):
            importer.zip_file.touch()
            result = importer._extract(write_feather=False, no_cache=False)
        assert isinstance(result, tuple) and len(result) == 5
        assert all(isinstance(df, pd.DataFrame) for df in result)

    def test_parse_routes_called_after_parse(self, importer):
        with (
            patch(
                "src.importer.importer.parse_apple_health",
                return_value=_empty_parse_return(),
            ),
            patch.object(
                importer, "_parse_routes", return_value=pd.DataFrame()
            ) as mock_routes,
        ):
            importer.zip_file.touch()
            importer._extract(write_feather=False, no_cache=False)
        mock_routes.assert_called_once()


# ---------------------------------------------------------------------------
# _extract_records_only
# ---------------------------------------------------------------------------


class TestExtractRecordsOnly:
    def test_uses_records_feather_alone(self, importer):
        """Must succeed with only the records feather, even when others are absent."""
        expected = pd.DataFrame({"type": ["HR"]})
        with patch("src.importer.importer.feather.read_feather", return_value=expected):
            importer.output_file.touch()
            result = importer._extract_records_only(no_cache=False)
        assert list(result["type"]) == ["HR"]

    def test_parses_zip_when_no_records_feather(self, importer):
        with patch(
            "src.importer.importer.parse_apple_health",
            return_value=_empty_parse_return(),
        ) as mock_parse:
            importer.zip_file.touch()
            importer._extract_records_only(no_cache=False)
        mock_parse.assert_called_once()

    def test_no_cache_true_bypasses_records_feather(self, importer):
        with (
            patch(
                "src.importer.importer.parse_apple_health",
                return_value=_empty_parse_return(),
            ) as mock_parse,
            patch("src.importer.importer.feather.read_feather") as mock_feather,
        ):
            importer.output_file.touch()
            importer.zip_file.touch()
            importer._extract_records_only(no_cache=True)
        mock_parse.assert_called_once()
        mock_feather.assert_not_called()

    def test_raises_when_no_feather_and_no_zip(self, importer):
        with pytest.raises(FileNotFoundError):
            importer._extract_records_only(no_cache=False)

    def test_returns_dataframe_not_tuple(self, importer):
        expected = pd.DataFrame({"type": ["HR"]})
        with patch("src.importer.importer.feather.read_feather", return_value=expected):
            importer.output_file.touch()
            result = importer._extract_records_only(no_cache=False)
        assert isinstance(result, pd.DataFrame)


# ---------------------------------------------------------------------------
# _parse_routes (instance method)
# ---------------------------------------------------------------------------


class TestParseRoutes:
    def _workout_with_route(self, gpx_path="workout-routes/r.gpx") -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "workoutActivityType": "HKWorkoutActivityTypeRunning",
                    "startDate": "2024-01-01 00:00:00 +0000",
                    "endDate": "2024-01-01 00:30:00 +0000",
                    "route": {"files": [gpx_path], "meta": {}},
                }
            ]
        )

    def test_empty_workout_df_returns_empty(self, importer):
        result = importer._parse_routes(pd.DataFrame())
        assert result.empty

    def test_workout_with_no_route_returns_empty(self, importer):
        df = pd.DataFrame([{"route": None, "workoutActivityType": "run"}])
        result = importer._parse_routes(df)
        assert result.empty

    def test_workout_with_empty_files_returns_empty(self, importer):
        df = pd.DataFrame([{"route": {"files": [], "meta": {}}}])
        result = importer._parse_routes(df)
        assert result.empty

    def test_calls_parse_apple_health_routes_with_paths(self, importer):
        df = self._workout_with_route()
        with patch(
            "src.importer.importer.parse_apple_health_routes",
            return_value=pd.DataFrame(),
        ) as mock_routes:
            importer.zip_file.touch()
            importer._parse_routes(df)
        mock_routes.assert_called_once()
        _, kwargs = mock_routes.call_args
        # paths kwarg must contain the GPX path
        assert "workout-routes/r.gpx" in mock_routes.call_args[1].get(
            "paths",
            mock_routes.call_args[0][1] if len(mock_routes.call_args[0]) > 1 else [],
        )

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
        ) as mock_routes:
            importer.zip_file.touch()
            importer._parse_routes(df)
        all_args = mock_routes.call_args
        # Flatten all paths passed
        called_paths = all_args[1].get("paths") or (
            all_args[0][1] if len(all_args[0]) > 1 else []
        )
        assert set(called_paths) == {"r1.gpx", "r2.gpx", "r3.gpx"}


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

    def test_read_failures_file_returns_correct_types(self, importer):
        failures = [RowFailure("HR", 5, start_error="e"), BatchFailure("Steps", 0, "t")]
        importer._write_failures_file(failures)
        restored = importer._read_failures_file()
        assert isinstance(restored[0], RowFailure)
        assert isinstance(restored[1], BatchFailure)


# ---------------------------------------------------------------------------
# _parse_hk_timestamp / _sanitize_doc helpers
# ---------------------------------------------------------------------------


class TestDocumentHelpers:
    def test_parse_hk_timestamp_none(self):
        assert _parse_hk_timestamp(None) is None

    def test_parse_hk_timestamp_utc(self):
        assert _parse_hk_timestamp("2024-01-01 00:00:00 +0000") == 1_704_067_200

    def test_parse_hk_timestamp_with_offset(self):
        ts_utc = _parse_hk_timestamp("2024-01-01 01:00:00 +0100")
        assert ts_utc == 1_704_067_200

    def test_parse_hk_timestamp_returns_int(self):
        assert isinstance(_parse_hk_timestamp("2024-01-01 00:00:00 +0000"), int)

    def test_sanitize_doc_replaces_nan_with_none(self):
        doc = {"a": 1, "b": float("nan"), "c": "hello"}
        sanitized = _sanitize_doc(doc)
        assert sanitized["b"] is None

    def test_sanitize_doc_preserves_non_nan(self):
        doc = {"x": 42, "y": "text", "z": [1, 2]}
        assert _sanitize_doc(doc) == doc

    def test_sanitize_doc_empty(self):
        assert _sanitize_doc({}) == {}


# ---------------------------------------------------------------------------
# _load_documents
# ---------------------------------------------------------------------------


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
        key = mock_redis.json.return_value.set.call_args[0][0]
        assert key.startswith("workout:")

    def test_workout_start_date_is_integer(self, mock_redis):
        _load_documents(self._workout_df(), pd.DataFrame(), pd.DataFrame(), mock_redis)
        doc = mock_redis.json.return_value.set.call_args[0][2]
        assert isinstance(doc["startDate"], int)

    def test_workout_metakeys_extracted(self, mock_redis):
        _load_documents(self._workout_df(), pd.DataFrame(), pd.DataFrame(), mock_redis)
        doc = mock_redis.json.return_value.set.call_args[0][2]
        assert "HKTimeZone" in doc["metaKeys"]

    def test_correlation_key_prefix(self, mock_redis):
        _load_documents(
            pd.DataFrame(), self._correlation_df(), pd.DataFrame(), mock_redis
        )
        key = mock_redis.json.return_value.set.call_args[0][0]
        assert key.startswith("correlation:")

    def test_correlation_metakeys_extracted(self, mock_redis):
        _load_documents(
            pd.DataFrame(), self._correlation_df(), pd.DataFrame(), mock_redis
        )
        doc = mock_redis.json.return_value.set.call_args[0][2]
        assert "HKWasUserEntered" in doc["metaKeys"]

    def test_activity_key_uses_date_components(self, mock_redis):
        _load_documents(pd.DataFrame(), pd.DataFrame(), self._activity_df(), mock_redis)
        key = mock_redis.json.return_value.set.call_args[0][0]
        assert "2024-01-01" in key

    def test_activity_doc_has_date_integer_field(self, mock_redis):
        _load_documents(pd.DataFrame(), pd.DataFrame(), self._activity_df(), mock_redis)
        doc = mock_redis.json.return_value.set.call_args[0][2]
        assert isinstance(doc["date"], int)

    def test_nan_sanitized_to_none(self, mock_redis):
        df = self._activity_df()
        df.loc[0, "appleMoveTime"] = float("nan")
        _load_documents(pd.DataFrame(), pd.DataFrame(), df, mock_redis)
        doc = mock_redis.json.return_value.set.call_args[0][2]
        assert doc["appleMoveTime"] is None

    def test_mixed_upload_counts(self, mock_redis):
        _load_documents(
            self._workout_df(), self._correlation_df(), self._activity_df(), mock_redis
        )
        assert mock_redis.json.return_value.set.call_count == 3


# ---------------------------------------------------------------------------
# _upload_routes
# ---------------------------------------------------------------------------


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

    def test_route_stored_with_correct_key_prefix(self, mock_redis):
        _upload_routes(self._routes_df(), self._workouts_df(), mock_redis)
        key = mock_redis.json.return_value.set.call_args[0][0]
        assert key.startswith("route:")

    def test_route_key_contains_activity_type(self, mock_redis):
        _upload_routes(self._routes_df(), self._workouts_df(), mock_redis)
        key = mock_redis.json.return_value.set.call_args[0][0]
        assert "HKWorkoutActivityTypeRunning" in key

    def test_route_key_contains_start_timestamp(self, mock_redis):
        _upload_routes(self._routes_df(), self._workouts_df(), mock_redis)
        key = mock_redis.json.return_value.set.call_args[0][0]
        assert "1704067200" in key

    def test_route_doc_has_workout_key_field(self, mock_redis):
        _upload_routes(self._routes_df(), self._workouts_df(), mock_redis)
        doc = mock_redis.json.return_value.set.call_args[0][2]
        assert "workoutKey" in doc
        assert doc["workoutKey"].startswith("workout:")

    def test_route_doc_has_trackpoints_list(self, mock_redis):
        _upload_routes(self._routes_df(), self._workouts_df(), mock_redis)
        doc = mock_redis.json.return_value.set.call_args[0][2]
        assert "trackpoints" in doc
        assert isinstance(doc["trackpoints"], list)

    def test_trackpoint_count_matches_routes(self, mock_redis):
        _upload_routes(self._routes_df(), self._workouts_df(), mock_redis)
        doc = mock_redis.json.return_value.set.call_args[0][2]
        assert len(doc["trackpoints"]) == 2

    def test_trackpoint_time_is_integer(self, mock_redis):
        _upload_routes(self._routes_df(), self._workouts_df(), mock_redis)
        doc = mock_redis.json.return_value.set.call_args[0][2]
        for tp in doc["trackpoints"]:
            assert isinstance(tp["time"], int)

    def test_trackpoint_lat_lon_preserved(self, mock_redis):
        _upload_routes(self._routes_df(), self._workouts_df(), mock_redis)
        doc = mock_redis.json.return_value.set.call_args[0][2]
        assert doc["trackpoints"][0]["lat"] == pytest.approx(52.52)
        assert doc["trackpoints"][0]["lon"] == pytest.approx(13.40)

    def test_trackpoint_nan_sanitized_to_none(self, mock_redis):
        routes = self._routes_df().copy()
        routes.loc[0, "ele"] = float("nan")
        _upload_routes(routes, self._workouts_df(), mock_redis)
        doc = mock_redis.json.return_value.set.call_args[0][2]
        assert doc["trackpoints"][0]["ele"] is None

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

    def test_multiple_workouts_multiple_routes(self, mock_redis):
        routes = pd.DataFrame(
            [
                {
                    "file": "r1.gpx",
                    "lat": 1.0,
                    "lon": 1.0,
                    "ele": None,
                    "time": pd.Timestamp("2024-01-01T09:00:00Z"),
                    "speed": None,
                    "course": None,
                    "hAcc": None,
                    "vAcc": None,
                },
                {
                    "file": "r2.gpx",
                    "lat": 2.0,
                    "lon": 2.0,
                    "ele": None,
                    "time": pd.Timestamp("2024-01-02T09:00:00Z"),
                    "speed": None,
                    "course": None,
                    "hAcc": None,
                    "vAcc": None,
                },
            ]
        )

        workouts = pd.DataFrame(
            [
                {
                    "workoutActivityType": "Run",
                    "startDate": "2024-01-01 00:00:00 +0000",
                    "endDate": "2024-01-01 01:00:00 +0000",
                    "route": {"files": ["r1.gpx"], "meta": {}},
                },
                {
                    "workoutActivityType": "Cycle",
                    "startDate": "2024-01-02 00:00:00 +0000",
                    "endDate": "2024-01-02 01:00:00 +0000",
                    "route": {"files": ["r2.gpx"], "meta": {}},
                },
            ]
        )
        _upload_routes(routes, workouts, mock_redis)
        assert mock_redis.json.return_value.set.call_count == 2

    def test_uses_json_set_dollar_path(self, mock_redis):
        _upload_routes(self._routes_df(), self._workouts_df(), mock_redis)
        path_arg = mock_redis.json.return_value.set.call_args[0][1]
        assert path_arg == "$"


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
                "group": ["vital_signs"] * n,
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
        assert _load(df, mock_redis) == []

    def test_redis_error_creates_batch_failure(self, mock_redis):
        df = self._make_df()
        mock_redis.ts.return_value.pipeline.return_value.execute.side_effect = (
            redis.RedisError("conn lost")
        )
        result = _load(df, mock_redis)
        assert isinstance(result[0], BatchFailure)

    def test_empty_df_returns_empty(self, mock_redis):
        assert _load(self._make_df(n=0), mock_redis) == []

    def test_multiple_types_processed_separately(self, mock_redis):
        df = pd.DataFrame(
            {
                "type": ["HR", "HR", "Steps", "Steps"],
                "sourceName": ["W"] * 4,
                "unit": ["bpm", "bpm", "count", "count"],
                "value": [72.0, 80.0, 500.0, 600.0],
                "startDate": [1_000_000 + i for i in range(4)],
                "endDate": [1_000_060 + i for i in range(4)],
                "group": ["vital_signs"] * 4,
            }
        )
        mock_redis.ts.return_value.pipeline.return_value.execute.return_value = [
            1,
            2,
            3,
            4,
        ]
        _load(df, mock_redis)
        assert mock_redis.ts.return_value.pipeline.call_count == 2

    def test_ensure_ts_key_called_for_each_type(self, mock_redis):
        df = self._make_df()
        mock_redis.ts.return_value.pipeline.return_value.execute.return_value = [
            1,
            2,
            3,
            4,
        ]
        with patch("src.importer.importer.ensure_ts_key") as mock_ensure:
            _load(df, mock_redis)
        assert mock_ensure.call_count == 2

    def test_ensure_ts_key_labels_use_batch_unit_and_group(self, mock_redis):
        df = self._make_df(type_val="HR")
        mock_redis.ts.return_value.pipeline.return_value.execute.return_value = [
            1,
            2,
            3,
            4,
        ]
        with patch("src.importer.importer.ensure_ts_key") as mock_ensure:
            _load(df, mock_redis)
        calls = {c[0][1]: c[0][2] for c in mock_ensure.call_args_list}
        labels = calls["ts:HR:start"]
        assert labels["unit"] == "bpm"
        assert labels["group"] == "vital_signs"
        assert labels["event_type"] == "start"

    def test_index_error_creates_batch_failure(self, mock_redis):
        with patch("src.importer.importer.upload_batch", side_effect=IndexError("x")):
            result = _load(self._make_df(), mock_redis)
        assert isinstance(result[0], BatchFailure)

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
        assert mock_upload.call_args[1]["duplicate_policy"] == DuplicatePolicy.LAST


# ---------------------------------------------------------------------------
# etl
# ---------------------------------------------------------------------------


class TestEtl:
    def test_etl_sets_failures_on_success(self, importer):
        df = _make_transformed_df()
        with (
            patch.object(importer, "_extract", return_value=_empty_extract_return(df)),
            patch("src.importer.importer.transform"),
            patch("src.importer.importer._load", return_value=[]),
            patch("src.importer.importer._load_documents"),
            patch("src.importer.importer._upload_routes"),
            patch.object(importer, "_update_failures_file"),
        ):
            importer.etl()
        assert importer.failures == []

    def test_etl_calls_load_documents(self, importer):
        df = _make_transformed_df()
        with (
            patch.object(importer, "_extract", return_value=_empty_extract_return(df)),
            patch("src.importer.importer.transform"),
            patch("src.importer.importer._load", return_value=[]),
            patch("src.importer.importer._load_documents") as mock_doc,
            patch("src.importer.importer._upload_routes"),
            patch.object(importer, "_update_failures_file"),
        ):
            importer.etl()
        mock_doc.assert_called_once()

    def test_etl_calls_upload_routes(self, importer):
        df = _make_transformed_df()
        with (
            patch.object(importer, "_extract", return_value=_empty_extract_return(df)),
            patch("src.importer.importer.transform"),
            patch("src.importer.importer._load", return_value=[]),
            patch("src.importer.importer._load_documents"),
            patch("src.importer.importer._upload_routes") as mock_routes,
            patch.object(importer, "_update_failures_file"),
        ):
            importer.etl()
        mock_routes.assert_called_once()

    def test_etl_persist_failures_true_calls_update(self, importer):
        df = _make_transformed_df()
        with (
            patch.object(importer, "_extract", return_value=_empty_extract_return(df)),
            patch("src.importer.importer.transform"),
            patch("src.importer.importer._load", return_value=[]),
            patch("src.importer.importer._load_documents"),
            patch("src.importer.importer._upload_routes"),
            patch.object(importer, "_update_failures_file") as mock_upd,
        ):
            importer.etl(persist_failures=True)
        mock_upd.assert_called_once()

    def test_etl_persist_failures_false_skips_update(self, importer):
        df = _make_transformed_df()
        with (
            patch.object(importer, "_extract", return_value=_empty_extract_return(df)),
            patch("src.importer.importer.transform"),
            patch("src.importer.importer._load", return_value=[]),
            patch("src.importer.importer._load_documents"),
            patch("src.importer.importer._upload_routes"),
            patch.object(importer, "_update_failures_file") as mock_upd,
        ):
            importer.etl(persist_failures=False)
        mock_upd.assert_not_called()

    def test_etl_no_cache_forwarded(self, importer):
        df = _make_transformed_df()
        with (
            patch.object(
                importer, "_extract", return_value=_empty_extract_return(df)
            ) as mock_extract,
            patch("src.importer.importer.transform"),
            patch("src.importer.importer._load", return_value=[]),
            patch("src.importer.importer._load_documents"),
            patch("src.importer.importer._upload_routes"),
            patch.object(importer, "_update_failures_file"),
        ):
            importer.etl(no_cache=True)
        assert mock_extract.call_args[1]["no_cache"] is True

    def test_etl_uses_duplicate_policy_first(self, importer):
        df = _make_transformed_df()
        with (
            patch.object(importer, "_extract", return_value=_empty_extract_return(df)),
            patch("src.importer.importer.transform"),
            patch("src.importer.importer._load", return_value=[]) as mock_load,
            patch("src.importer.importer._load_documents"),
            patch("src.importer.importer._upload_routes"),
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
    def test_update_uses_duplicate_policy_last(self, importer):
        df = _make_transformed_df()
        with (
            patch.object(importer, "_extract", return_value=_empty_extract_return(df)),
            patch("src.importer.importer.transform"),
            patch("src.importer.importer._load", return_value=[]) as mock_load,
            patch("src.importer.importer._load_documents"),
            patch("src.importer.importer._upload_routes"),
            patch.object(importer, "_update_failures_file"),
        ):
            importer.update()
        _, kwargs = mock_load.call_args
        assert kwargs["duplicate_policy"] == DuplicatePolicy.LAST

    def test_update_calls_upload_routes(self, importer):
        df = _make_transformed_df()
        with (
            patch.object(importer, "_extract", return_value=_empty_extract_return(df)),
            patch("src.importer.importer.transform"),
            patch("src.importer.importer._load", return_value=[]),
            patch("src.importer.importer._load_documents"),
            patch("src.importer.importer._upload_routes") as mock_routes,
            patch.object(importer, "_update_failures_file"),
        ):
            importer.update()
        mock_routes.assert_called_once()

    def test_update_no_cache_forwarded(self, importer):
        df = _make_transformed_df()
        with (
            patch.object(
                importer, "_extract", return_value=_empty_extract_return(df)
            ) as mock_extract,
            patch("src.importer.importer.transform"),
            patch("src.importer.importer._load", return_value=[]),
            patch("src.importer.importer._load_documents"),
            patch("src.importer.importer._upload_routes"),
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

    def test_retry_uses_extract_records_only(self, importer):
        """retry_failed must call _extract_records_only, not _extract."""
        df = _make_transformed_df(n=1)
        self._write_failures(importer, [RowFailure("HR", 0)])
        with (
            patch.object(
                importer, "_extract_records_only", return_value=df
            ) as mock_rec,
            patch.object(importer, "_extract") as mock_full,
            patch("src.importer.importer.transform"),
            patch("src.importer.importer._load", return_value=[]),
            patch.object(importer, "_update_failures_file"),
        ):
            importer.retry_failed()
        mock_rec.assert_called_once()
        mock_full.assert_not_called()

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
        assert (loaded_df["type"] == "HR").all() and len(loaded_df) == 3

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
