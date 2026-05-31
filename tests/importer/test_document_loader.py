"""Tests for src/importer/document_loader.py — JSON document upload helpers."""

from __future__ import annotations

from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import pytest
from redis.exceptions import RedisError

from src.importer.document_loader import (
    _attach_meta_keys,
    _coerce_timestamps,
    _to_unix_seconds,
    load_activities,
    load_correlations,
    load_routes,
    load_workouts,
)
from src.importer.response import BatchFailure

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_redis() -> MagicMock:
    """Mock Redis client; pipe.execute returns one OK per queued command."""
    r = MagicMock()
    pipe = MagicMock()
    # Default: empty list — overwritten per test as needed.
    pipe.execute.return_value = []
    r.pipeline.return_value = pipe
    return r


def _setup_pipe_responses(mock_redis: MagicMock, n: int) -> None:
    """Pre-fill the mock pipe's execute response with *n* OK results."""
    mock_redis.pipeline.return_value.execute.return_value = ["OK"] * n


# ---------------------------------------------------------------------------
# _to_unix_seconds
# ---------------------------------------------------------------------------


class TestToUnixSeconds:
    def test_none_returns_none(self):
        assert _to_unix_seconds(None) is None

    def test_nan_returns_none(self):
        assert _to_unix_seconds(float("nan")) is None

    def test_iso_string_converted(self):
        # 2024-01-01 UTC == 1704067200
        assert _to_unix_seconds("2024-01-01 00:00:00 +0000") == 1_704_067_200

    def test_int_passthrough(self):
        # Already a Unix timestamp — must not be re-interpreted as ns.
        assert _to_unix_seconds(1_704_067_200) == 1_704_067_200

    def test_numpy_int_passthrough(self):
        assert _to_unix_seconds(np.int64(1_704_067_200)) == 1_704_067_200

    def test_datetime_object_converted(self):
        ts = pd.Timestamp("2024-01-01T00:00:00", tz="UTC")
        assert _to_unix_seconds(ts) == 1_704_067_200

    def test_invalid_string_returns_none(self):
        # `errors="coerce"` makes invalid strings → NaT → None.
        assert _to_unix_seconds("not a timestamp") is None

    def test_pd_nat_returns_none(self):
        assert _to_unix_seconds(pd.NaT) is None

    def test_boolean_is_not_treated_as_int(self):
        # ``bool`` is a subclass of int but is not a sensible timestamp.
        # The function passes it through int-pass-through; this is a
        # behavioural test so a future refactor doesn't break the contract.
        assert _to_unix_seconds(value=True) is None
        assert _to_unix_seconds(value=False) is None
        assert _to_unix_seconds(value=None) is None


# ---------------------------------------------------------------------------
# _coerce_timestamps
# ---------------------------------------------------------------------------


class TestCoerceTimestamps:
    def test_default_fields_coerced(self):
        d = {
            "startDate": "2024-01-01 00:00:00 +0000",
            "endDate": "2024-01-01 00:01:00 +0000",
            "creationDate": "2024-01-01 00:00:30 +0000",
            "other": "leave-me-alone",
        }
        _coerce_timestamps(d)
        assert d["startDate"] == 1_704_067_200
        assert d["endDate"] == 1_704_067_260
        assert d["creationDate"] == 1_704_067_230
        assert d["other"] == "leave-me-alone"

    def test_missing_fields_skipped(self):
        d = {"startDate": "2024-01-01 00:00:00 +0000"}
        _coerce_timestamps(d)  # endDate/creationDate absent — no error
        assert d == {"startDate": 1_704_067_200}

    def test_custom_fields(self):
        d = {"date": "2024-06-15 12:00:00 +0000", "startDate": "skipme"}
        _coerce_timestamps(d, fields=("date",))
        assert isinstance(d["date"], int)
        assert d["startDate"] == "skipme"

    def test_none_value_skipped(self):
        d = {"startDate": None}
        _coerce_timestamps(d)
        assert d["startDate"] is None


# ---------------------------------------------------------------------------
# _attach_meta_keys
# ---------------------------------------------------------------------------


class TestAttachMetaKeys:
    def test_meta_dict_to_keys_list(self):
        doc = {"meta": {"a": "1", "b": "2"}}
        _attach_meta_keys(doc)
        assert sorted(doc["metaKeys"]) == ["a", "b"]

    def test_missing_meta_gives_empty_list(self):
        doc = {}
        _attach_meta_keys(doc)
        assert doc["metaKeys"] == []

    def test_none_meta_gives_empty_list(self):
        doc = {"meta": None}
        _attach_meta_keys(doc)
        assert doc["metaKeys"] == []


# ---------------------------------------------------------------------------
# load_workouts
# ---------------------------------------------------------------------------


def _make_workouts_df(n: int = 1) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "sourceName": ["Watch"] * n,
            "workoutActivityType": ["HKWorkoutActivityTypeRunning"] * n,
            "duration": ["30.0"] * n,
            "durationUnit": ["min"] * n,
            "sourceVersion": ["9.0"] * n,
            "device": ["watch"] * n,
            "startDate": ["2024-01-01 00:00:00 +0000"] * n,
            "endDate": ["2024-01-01 00:30:00 +0000"] * n,
            "creationDate": ["2024-01-01 00:00:00 +0000"] * n,
            "meta": [{"HKTimeZone": "Europe/Berlin"}] * n,
            "events": [[]] * n,
            "statistics": [[]] * n,
            "route": [None] * n,
            "activities": [[]] * n,
        }
    )


class TestLoadWorkouts:
    def test_empty_df_returns_empty(self, mock_redis):
        assert load_workouts(mock_redis, pd.DataFrame()) == []

    def test_empty_df_does_not_open_pipeline(self, mock_redis):
        load_workouts(mock_redis, pd.DataFrame())
        mock_redis.pipeline.assert_not_called()

    def test_returns_empty_on_success(self, mock_redis):
        df = _make_workouts_df(n=2)
        _setup_pipe_responses(mock_redis, 2)
        assert load_workouts(mock_redis, df) == []

    def test_key_format_workout_prefix(self, mock_redis):
        df = _make_workouts_df(n=1)
        _setup_pipe_responses(mock_redis, 1)
        load_workouts(mock_redis, df)
        json_set = mock_redis.pipeline.return_value.json.return_value.set
        key = json_set.call_args.args[0]
        assert key.startswith("workout:")

    def test_timestamps_coerced_to_unix_seconds(self, mock_redis):
        df = _make_workouts_df(n=1)
        _setup_pipe_responses(mock_redis, 1)
        load_workouts(mock_redis, df)
        json_set = mock_redis.pipeline.return_value.json.return_value.set
        doc = json_set.call_args.args[2]
        assert doc["startDate"] == 1_704_067_200
        assert doc["endDate"] == 1_704_069_000

    def test_metakeys_attached(self, mock_redis):
        df = _make_workouts_df(n=1)
        _setup_pipe_responses(mock_redis, 1)
        load_workouts(mock_redis, df)
        json_set = mock_redis.pipeline.return_value.json.return_value.set
        doc = json_set.call_args.args[2]
        assert doc["metaKeys"] == ["HKTimeZone"]

    def test_redis_error_returns_batch_failure(self, mock_redis):
        df = _make_workouts_df(n=1)
        mock_redis.pipeline.return_value.execute.side_effect = RedisError("conn lost")
        failures = load_workouts(mock_redis, df)
        assert len(failures) == 1
        assert isinstance(failures[0], BatchFailure)
        assert failures[0].batch_nr == -1

    def test_per_document_response_error_creates_failure(self, mock_redis):
        df = _make_workouts_df(n=2)
        # First doc fails, second succeeds.
        mock_redis.pipeline.return_value.execute.return_value = [
            RedisError("denied"),
            "OK",
        ]
        failures = load_workouts(mock_redis, df)
        assert len(failures) == 1
        assert failures[0].batch_nr == -1

    def test_nested_event_timestamps_coerced(self, mock_redis):
        df = _make_workouts_df(n=1)
        df.loc[0, "events"] = [
            {"type": "Lap", "date": "2024-01-01 00:10:00 +0000", "duration": "60"}
        ]
        _setup_pipe_responses(mock_redis, 1)
        load_workouts(mock_redis, df)
        json_set = mock_redis.pipeline.return_value.json.return_value.set
        doc = json_set.call_args.args[2]
        assert doc["events"][0]["date"] == 1_704_067_800


# ---------------------------------------------------------------------------
# load_correlations
# ---------------------------------------------------------------------------


def _make_correlations_df(n: int = 1) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "sourceName": ["Health"] * n,
            "endDate": ["2024-01-01 00:01:00 +0000"] * n,
            "startDate": ["2024-01-01 00:00:00 +0000"] * n,
            "sourceVersion": ["17.0"] * n,
            "type": ["HKCorrelationTypeIdentifierBloodPressure"] * n,
            "creationDate": ["2024-01-01 00:00:00 +0000"] * n,
            "meta": [{"HKWasUserEntered": "1"}] * n,
            "records": [
                [
                    {
                        "type": "HKQuantityTypeIdentifierBloodPressureSystolic",
                        "value": "120",
                        "unit": "mmHg",
                        "startDate": "2024-01-01 00:00:00 +0000",
                        "endDate": "2024-01-01 00:01:00 +0000",
                        "creationDate": "2024-01-01 00:00:00 +0000",
                        "sourceName": "Health",
                        "sourceVersion": "17.0",
                        "device": "phone",
                    }
                ]
            ]
            * n,
        }
    )


class TestLoadCorrelations:
    def test_empty_df_returns_empty(self, mock_redis):
        assert load_correlations(mock_redis, pd.DataFrame()) == []

    def test_key_format_correlation_prefix(self, mock_redis):
        df = _make_correlations_df(n=1)
        _setup_pipe_responses(mock_redis, 1)
        load_correlations(mock_redis, df)
        json_set = mock_redis.pipeline.return_value.json.return_value.set
        key = json_set.call_args.args[0]
        assert key.startswith("correlation:")

    def test_top_level_timestamps_coerced(self, mock_redis):
        df = _make_correlations_df(n=1)
        _setup_pipe_responses(mock_redis, 1)
        load_correlations(mock_redis, df)
        json_set = mock_redis.pipeline.return_value.json.return_value.set
        doc = json_set.call_args.args[2]
        assert doc["startDate"] == 1_704_067_200
        assert doc["endDate"] == 1_704_067_260

    def test_nested_record_timestamps_coerced(self, mock_redis):
        df = _make_correlations_df(n=1)
        _setup_pipe_responses(mock_redis, 1)
        load_correlations(mock_redis, df)
        json_set = mock_redis.pipeline.return_value.json.return_value.set
        doc = json_set.call_args.args[2]
        rec = doc["records"][0]
        assert rec["startDate"] == 1_704_067_200
        assert rec["endDate"] == 1_704_067_260

    def test_metakeys_attached(self, mock_redis):
        df = _make_correlations_df(n=1)
        _setup_pipe_responses(mock_redis, 1)
        load_correlations(mock_redis, df)
        json_set = mock_redis.pipeline.return_value.json.return_value.set
        doc = json_set.call_args.args[2]
        assert doc["metaKeys"] == ["HKWasUserEntered"]

    def test_redis_error_returns_batch_failure(self, mock_redis):
        df = _make_correlations_df(n=1)
        mock_redis.pipeline.return_value.execute.side_effect = RedisError("x")
        failures = load_correlations(mock_redis, df)
        assert len(failures) == 1
        assert failures[0].batch_nr == -1


# ---------------------------------------------------------------------------
# load_activities
# ---------------------------------------------------------------------------


def _make_activities_df(n: int = 1) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "dateComponents": [f"2024-01-{i + 1:02d}" for i in range(n)],
            "appleExerciseTime": ["35"] * n,
            "appleMoveTime": [None] * n,
            "activeEnergyBurnedGoal": ["500"] * n,
            "activeEnergyBurnedUnit": ["kcal"] * n,
            "appleStandHoursGoal": ["12"] * n,
            "appleMoveTimeGoal": [None] * n,
            "appleStandHours": ["12"] * n,
            "activeEnergyBurned": ["450"] * n,
            "appleExerciseTimeGoal": ["30"] * n,
        }
    )


class TestLoadActivities:
    def test_empty_df_returns_empty(self, mock_redis):
        assert load_activities(mock_redis, pd.DataFrame()) == []

    def test_key_format_activity_prefix(self, mock_redis):
        df = _make_activities_df(n=1)
        _setup_pipe_responses(mock_redis, 1)
        load_activities(mock_redis, df)
        json_set = mock_redis.pipeline.return_value.json.return_value.set
        key = json_set.call_args.args[0]
        assert key == "activity:2024-01-01"

    def test_date_field_is_unix_seconds(self, mock_redis):
        df = _make_activities_df(n=1)
        _setup_pipe_responses(mock_redis, 1)
        load_activities(mock_redis, df)
        json_set = mock_redis.pipeline.return_value.json.return_value.set
        doc = json_set.call_args.args[2]
        assert doc["date"] == 1_704_067_200  # 2024-01-01 UTC

    def test_numeric_fields_coerced_to_float(self, mock_redis):
        df = _make_activities_df(n=1)
        _setup_pipe_responses(mock_redis, 1)
        load_activities(mock_redis, df)
        json_set = mock_redis.pipeline.return_value.json.return_value.set
        doc = json_set.call_args.args[2]
        assert doc["activeEnergyBurned"] == 450.0
        assert doc["activeEnergyBurnedGoal"] == 500.0
        assert doc["appleExerciseTime"] == 35.0

    def test_none_numeric_field_kept_as_none(self, mock_redis):
        df = _make_activities_df(n=1)
        _setup_pipe_responses(mock_redis, 1)
        load_activities(mock_redis, df)
        json_set = mock_redis.pipeline.return_value.json.return_value.set
        doc = json_set.call_args.args[2]
        assert doc["appleMoveTime"] is None

    def test_redis_error_returns_batch_failure(self, mock_redis):
        df = _make_activities_df(n=1)
        mock_redis.pipeline.return_value.execute.side_effect = RedisError("x")
        failures = load_activities(mock_redis, df)
        assert len(failures) == 1
        assert failures[0].batch_nr == -1


# ---------------------------------------------------------------------------
# load_routes
# ---------------------------------------------------------------------------


def _make_routes_df(n_files: int = 1, points_per_file: int = 2) -> pd.DataFrame:
    rows = []
    for f in range(n_files):
        file_path = f"workout-routes/route_{f}.gpx"
        for p in range(points_per_file):
            rows.append(
                {
                    "file": file_path,
                    "lat": 52.0 + p * 0.001,
                    "lon": 13.0 + p * 0.001,
                    "ele": 30.0 + p,
                    "time": pd.Timestamp("2024-01-01T00:00:00", tz="UTC")
                    + pd.Timedelta(seconds=p),
                    "speed": 2.5,
                    "course": 90.0,
                    "hAcc": 4.0,
                    "vAcc": 3.0,
                }
            )
    return pd.DataFrame(rows)


class TestLoadRoutes:
    def test_empty_df_returns_empty(self, mock_redis):
        assert load_routes(mock_redis, pd.DataFrame()) == []

    def test_one_doc_per_file(self, mock_redis):
        df = _make_routes_df(n_files=3, points_per_file=2)
        _setup_pipe_responses(mock_redis, 3)
        load_routes(mock_redis, df)
        json_set = mock_redis.pipeline.return_value.json.return_value.set
        # Three files → three JSON.SET calls.
        assert json_set.call_count == 3

    def test_key_format_route_prefix(self, mock_redis):
        df = _make_routes_df(n_files=1)
        _setup_pipe_responses(mock_redis, 1)
        load_routes(mock_redis, df)
        json_set = mock_redis.pipeline.return_value.json.return_value.set
        key = json_set.call_args.args[0]
        assert key.startswith("route:")

    def test_points_collected_into_list(self, mock_redis):
        df = _make_routes_df(n_files=1, points_per_file=5)
        _setup_pipe_responses(mock_redis, 1)
        load_routes(mock_redis, df)
        json_set = mock_redis.pipeline.return_value.json.return_value.set
        doc = json_set.call_args.args[2]
        assert len(doc["points"]) == 5
        assert doc["numPoints"] == 5

    def test_time_coerced_to_unix_seconds(self, mock_redis):
        df = _make_routes_df(n_files=1, points_per_file=1)
        _setup_pipe_responses(mock_redis, 1)
        load_routes(mock_redis, df)
        json_set = mock_redis.pipeline.return_value.json.return_value.set
        doc = json_set.call_args.args[2]
        assert doc["points"][0]["time"] == 1_704_067_200

    def test_start_end_date_match_first_last_point(self, mock_redis):
        df = _make_routes_df(n_files=1, points_per_file=3)
        _setup_pipe_responses(mock_redis, 1)
        load_routes(mock_redis, df)
        json_set = mock_redis.pipeline.return_value.json.return_value.set
        doc = json_set.call_args.args[2]
        assert doc["startDate"] == doc["points"][0]["time"]
        assert doc["endDate"] == doc["points"][-1]["time"]

    def test_workout_id_derived_from_filename(self, mock_redis):
        df = _make_routes_df(n_files=1, points_per_file=1)
        _setup_pipe_responses(mock_redis, 1)
        load_routes(mock_redis, df)
        json_set = mock_redis.pipeline.return_value.json.return_value.set
        doc = json_set.call_args.args[2]
        assert doc["workoutId"] == "route_0"

    def test_redis_error_returns_batch_failure(self, mock_redis):
        df = _make_routes_df(n_files=1)
        mock_redis.pipeline.return_value.execute.side_effect = RedisError("x")
        failures = load_routes(mock_redis, df)
        assert len(failures) == 1
        assert failures[0].batch_nr == -1
