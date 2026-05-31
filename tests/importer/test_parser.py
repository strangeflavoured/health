"""Tests for src/importer/parser.py — XML parsing and security (XXE, zip-slip)."""

from __future__ import annotations

import io
import logging
import time
import xml
import zipfile
from pathlib import Path

import defusedxml
import pandas as pd
import pytest

from src.importer.parser import (
    NoHealthDataError,
    parse_apple_health,
    parse_apple_health_routes,
)

# ---------------------------------------------------------------------------
# XML / GPX fixtures
# ---------------------------------------------------------------------------

_RECORD_XML = """<?xml version="1.0" encoding="UTF-8"?>
<HealthData locale="en_US">
  <Record
    type="HKQuantityTypeIdentifierHeartRate"
    sourceName="Apple Watch"
    sourceVersion="9.0"
    device="watch"
    unit="count/min"
    creationDate="2024-01-01 00:00:00 +0000"
    startDate="2024-01-01 00:00:00 +0000"
    endDate="2024-01-01 00:01:00 +0000"
    value="72"
  />
  <Record
    type="HKQuantityTypeIdentifierStepCount"
    sourceName="iPhone"
    sourceVersion="17.0"
    device="phone"
    unit="count"
    creationDate="2024-01-01 00:02:00 +0000"
    startDate="2024-01-01 00:02:00 +0000"
    endDate="2024-01-01 00:03:00 +0000"
    value="500"
  />
</HealthData>
"""

_CORRELATION_XML = """<?xml version="1.0" encoding="UTF-8"?>
<HealthData locale="en_US">
  <Correlation
    type="HKCorrelationTypeIdentifierBloodPressure"
    sourceName="Health"
    sourceVersion="17.0"
    device="phone"
    creationDate="2024-01-01 00:00:00 +0000"
    startDate="2024-01-01 00:00:00 +0000"
    endDate="2024-01-01 00:01:00 +0000"
  >
    <MetadataEntry key="HKWasUserEntered" value="1"/>
    <Record
      type="HKQuantityTypeIdentifierBloodPressureSystolic"
      sourceName="Health" sourceVersion="17.0" device="phone"
      unit="mmHg" creationDate="2024-01-01 00:00:00 +0000"
      startDate="2024-01-01 00:00:00 +0000"
      endDate="2024-01-01 00:01:00 +0000"
      value="120"
    />
    <Record
      type="HKQuantityTypeIdentifierBloodPressureDiastolic"
      sourceName="Health" sourceVersion="17.0" device="phone"
      unit="mmHg" creationDate="2024-01-01 00:00:00 +0000"
      startDate="2024-01-01 00:00:00 +0000"
      endDate="2024-01-01 00:01:00 +0000"
      value="80"
    />
  </Correlation>
</HealthData>
"""

_GPX_ROUTE_PATH = "workout-routes/route_2024-01-01_123.gpx"
_GPX_ROUTE_PATH_2 = "workout-routes/route_2024-01-02_456.gpx"

_WORKOUT_XML = f"""<?xml version="1.0" encoding="UTF-8"?>
<HealthData locale="en_US">
  <Workout
    workoutActivityType="HKWorkoutActivityTypeRunning"
    duration="30.0" durationUnit="min"
    sourceName="Apple Watch" sourceVersion="9.0" device="watch"
    creationDate="2024-01-01 00:00:00 +0000"
    startDate="2024-01-01 00:00:00 +0000"
    endDate="2024-01-01 00:30:00 +0000"
  >
    <MetadataEntry key="HKTimeZone" value="Europe/Berlin"/>
    <WorkoutEvent
      type="HKWorkoutEventTypeLap"
      date="2024-01-01 00:10:00 +0000"
      duration="600.0" durationUnit="s"
    >
      <MetadataEntry key="HKLapLength" value="1000"/>
    </WorkoutEvent>
    <WorkoutStatistics
      type="HKQuantityTypeIdentifierHeartRate"
      startDate="2024-01-01 00:00:00 +0000"
      endDate="2024-01-01 00:30:00 +0000"
      average="145" minimum="120" maximum="175" unit="count/min"
    />
    <WorkoutStatistics
      type="HKQuantityTypeIdentifierDistanceWalkingRunning"
      startDate="2024-01-01 00:00:00 +0000"
      endDate="2024-01-01 00:30:00 +0000"
      sum="5000" unit="m"
    />
    <WorkoutRoute
      sourceName="Apple Watch" sourceVersion="9.0" device="watch"
      creationDate="2024-01-01 00:00:00 +0000"
      startDate="2024-01-01 00:00:00 +0000"
      endDate="2024-01-01 00:30:00 +0000"
    >
      <FileReference path="{_GPX_ROUTE_PATH}"/>
      <MetadataEntry key="HKMetadataKeyAltitudeType" value="2"/>
    </WorkoutRoute>
    <WorkoutActivity
      uuid="activity-uuid-1"
      startDate="2024-01-01 00:00:00 +0000"
      endDate="2024-01-01 00:30:00 +0000"
    >
      <MetadataEntry key="HKTimeZone" value="Europe/Berlin"/>
      <WorkoutEvent type="HKWorkoutEventTypeLap" date="2024-01-01 00:10:00 +0000"/>
      <WorkoutStatistics
        type="HKQuantityTypeIdentifierHeartRate"
        startDate="2024-01-01 00:00:00 +0000"
        endDate="2024-01-01 00:30:00 +0000"
        average="145" unit="count/min"
      />
    </WorkoutActivity>
  </Workout>
</HealthData>
"""

_MULTI_ACTIVITY_XML = """<?xml version="1.0" encoding="UTF-8"?>
<HealthData locale="en_US">
  <Workout
    workoutActivityType="HKWorkoutActivityTypeSwimBikeRun"
    sourceName="Apple Watch" sourceVersion="9.0" device="watch"
    creationDate="2024-01-01 00:00:00 +0000"
    startDate="2024-01-01 00:00:00 +0000"
    endDate="2024-01-01 01:00:00 +0000"
  >
    <WorkoutActivity uuid="swim"
      startDate="2024-01-01 00:00:00 +0000"
      endDate="2024-01-01 00:20:00 +0000"/>
    <WorkoutActivity uuid="bike"
      startDate="2024-01-01 00:20:00 +0000"
      endDate="2024-01-01 00:50:00 +0000"/>
    <WorkoutActivity uuid="run"
      startDate="2024-01-01 00:50:00 +0000"
      endDate="2024-01-01 01:00:00 +0000"/>
  </Workout>
</HealthData>
"""

_ACTIVITY_SUMMARY_XML = """<?xml version="1.0" encoding="UTF-8"?>
<HealthData locale="en_US">
  <ActivitySummary
    dateComponents="2024-01-01"
    activeEnergyBurned="450"
    activeEnergyBurnedGoal="500"
    activeEnergyBurnedUnit="kcal"
    appleExerciseTime="35"
    appleExerciseTimeGoal="30"
    appleStandHours="12"
    appleStandHoursGoal="12"
  />
</HealthData>
"""

_GPX_TWO_POINTS = """<?xml version="1.0" encoding="UTF-8"?>
<gpx xmlns="http://www.topografix.com/GPX/1/1" version="1.1" creator="Apple Health">
  <trk><trkseg>
    <trkpt lat="52.520008" lon="13.404954">
      <ele>34.5</ele>
      <time>2024-01-01T09:00:00Z</time>
      <extensions>
        <speed>2.83</speed><course>274.5</course>
        <hAcc>4.2</hAcc><vAcc>3.1</vAcc>
      </extensions>
    </trkpt>
    <trkpt lat="52.520100" lon="13.405000">
      <ele>35.0</ele>
      <time>2024-01-01T09:00:01Z</time>
      <extensions>
        <speed>3.00</speed><course>275.0</course>
        <hAcc>4.0</hAcc><vAcc>3.0</vAcc>
      </extensions>
    </trkpt>
  </trkseg></trk>
</gpx>
"""

_GPX_MISSING_OPTIONAL = """<?xml version="1.0" encoding="UTF-8"?>
<gpx xmlns="http://www.topografix.com/GPX/1/1" version="1.1">
  <trk><trkseg>
    <trkpt lat="52.520008" lon="13.404954">
      <time>2024-01-01T09:00:00Z</time>
    </trkpt>
  </trkseg></trk>
</gpx>
"""

_GPX_EMPTY = """<?xml version="1.0" encoding="UTF-8"?>
<gpx xmlns="http://www.topografix.com/GPX/1/1" version="1.1">
  <trk><trkseg/></trk>
</gpx>
"""

_TWO_DATES_XML = """<?xml version="1.0" encoding="UTF-8"?>
<HealthData locale="en_US">
  <Record
    type="HKQuantityTypeIdentifierHeartRate"
    sourceName="Watch" sourceVersion="1" device="d" unit="count/min"
    creationDate="2024-01-01 00:00:00 +0000"
    startDate="2024-01-01 00:00:00 +0000"
    endDate="2024-01-01 00:01:00 +0000"
    value="60"
  />
  <Record
    type="HKQuantityTypeIdentifierHeartRate"
    sourceName="Watch" sourceVersion="1" device="d" unit="count/min"
    creationDate="2024-01-03 00:00:00 +0000"
    startDate="2024-01-03 00:00:00 +0000"
    endDate="2024-01-03 00:01:00 +0000"
    value="70"
  />
</HealthData>
"""

_LATE_RECORD_XML = """\
  <Record
    type="HKQuantityTypeIdentifierHeartRate"
    sourceName="Watch" sourceVersion="1" device="d" unit="count/min"
    creationDate="2024-01-03 00:00:00 +0000"
    startDate="2024-01-03 00:00:00 +0000"
    endDate="2024-01-03 00:01:00 +0000"
    value="1"
/>"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_zip(files: dict[str, str | bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    return buf.getvalue()


def _xml_zip(xml_content: str) -> bytes:
    """Zip containing only the standard export.xml."""
    return _make_zip({"apple_health_export/export.xml": xml_content})


def _route_zip(
    xml_content: str = _WORKOUT_XML,
    gpx_content: str = _GPX_TWO_POINTS,
    route_path: str = _GPX_ROUTE_PATH,
) -> bytes:
    """Zip containing export.xml and one GPX route file."""
    return _make_zip(
        {
            "apple_health_export/export.xml": xml_content,
            f"apple_health_export/{route_path}": gpx_content,
        }
    )


def _minimal_workout_xml(children: str = "") -> str:
    return f"""<?xml version="1.0"?>
<HealthData locale="en_US">
  <Workout workoutActivityType="HKWorkoutActivityTypeRunning"
    sourceName="Watch" sourceVersion="1" device="d"
    creationDate="2024-01-01 00:00:00 +0000"
    startDate="2024-01-01 00:00:00 +0000"
    endDate="2024-01-01 00:30:00 +0000"
  >{children}</Workout>
</HealthData>"""


# ---------------------------------------------------------------------------
# parse_apple_health — return type and error handling
# ---------------------------------------------------------------------------


class TestParseAppleHealth:
    def test_returns_four_dataframes(self, tmp_path):
        zip_path = tmp_path / "export.zip"
        zip_path.write_bytes(_xml_zip(_RECORD_XML))
        result = parse_apple_health(zip_path)
        assert isinstance(result, tuple) and len(result) == 4
        assert all(isinstance(df, pd.DataFrame) for df in result)

    def test_accepts_path_object(self, tmp_path):
        zip_path = tmp_path / "export.zip"
        zip_path.write_bytes(_xml_zip(_RECORD_XML))
        records, *_ = parse_apple_health(Path(zip_path))
        assert len(records) == 2

    def test_accepts_string_path(self, tmp_path):
        zip_path = tmp_path / "export.zip"
        zip_path.write_bytes(_xml_zip(_RECORD_XML))
        records, *_ = parse_apple_health(str(zip_path))
        assert len(records) == 2

    def test_all_empty_raises_no_health_data_error(self, tmp_path):
        zip_path = tmp_path / "export.zip"
        zip_path.write_bytes(
            _xml_zip('<?xml version="1.0"?><HealthData locale="en_US"/>')
        )
        with pytest.raises(NoHealthDataError):
            parse_apple_health(zip_path)

    def test_only_workouts_does_not_raise(self, tmp_path):
        """NoHealthDataError must not fire when records are empty but
        workouts are present."""
        zip_path = tmp_path / "export.zip"
        zip_path.write_bytes(_xml_zip(_WORKOUT_XML))
        _, _, workouts, _ = parse_apple_health(zip_path)
        assert len(workouts) == 1

    def test_only_correlations_does_not_raise(self, tmp_path):
        zip_path = tmp_path / "export.zip"
        zip_path.write_bytes(_xml_zip(_CORRELATION_XML))
        _, correlations, _, _ = parse_apple_health(zip_path)
        assert len(correlations) == 1

    def test_only_activity_summaries_does_not_raise(self, tmp_path):
        zip_path = tmp_path / "export.zip"
        zip_path.write_bytes(_xml_zip(_ACTIVITY_SUMMARY_XML))
        _, _, _, activities = parse_apple_health(zip_path)
        assert len(activities) == 1

    def test_missing_export_xml_raises(self, tmp_path):
        zip_path = tmp_path / "export.zip"
        zip_path.write_bytes(_make_zip({"wrong_path/data.xml": "<HealthData/>"}))
        with pytest.raises(KeyError):
            parse_apple_health(zip_path)

    def test_nonexistent_zip_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            parse_apple_health(tmp_path / "nonexistent.zip")

    def test_corrupt_zip_raises(self, tmp_path):
        zip_path = tmp_path / "export.zip"
        zip_path.write_bytes(b"this is not a zip file at all")
        with pytest.raises(zipfile.BadZipFile):
            parse_apple_health(zip_path)

    def test_no_health_data_error_is_value_error_subclass(self):
        assert issubclass(NoHealthDataError, ValueError)


# ---------------------------------------------------------------------------
# parse_apple_health — Records DataFrame
# ---------------------------------------------------------------------------


class TestRecordParsing:
    def test_record_count(self, tmp_path):
        zip_path = tmp_path / "export.zip"
        zip_path.write_bytes(_xml_zip(_RECORD_XML))
        records, *_ = parse_apple_health(zip_path)
        assert len(records) == 2

    def test_exact_columns(self, tmp_path):
        zip_path = tmp_path / "export.zip"
        zip_path.write_bytes(_xml_zip(_RECORD_XML))
        records, *_ = parse_apple_health(zip_path)
        assert set(records.columns) == {
            "type",
            "sourceName",
            "sourceVersion",
            "device",
            "unit",
            "startDate",
            "endDate",
            "creationDate",
            "value",
        }

    def test_all_columns_are_string_dtype(self, tmp_path):
        zip_path = tmp_path / "export.zip"
        zip_path.write_bytes(_xml_zip(_RECORD_XML))
        records, *_ = parse_apple_health(zip_path)
        for col in records.columns:
            assert pd.api.types.is_string_dtype(records[col]), (
                f"{col} should be string dtype"
            )

    def test_record_values(self, tmp_path):
        zip_path = tmp_path / "export.zip"
        zip_path.write_bytes(_xml_zip(_RECORD_XML))
        records, *_ = parse_apple_health(zip_path)
        hr = records[records["type"] == "HKQuantityTypeIdentifierHeartRate"].iloc[0]
        assert hr["sourceName"] == "Apple Watch"
        assert hr["unit"] == "count/min"
        assert hr["value"] == "72"

    def test_missing_attributes_produce_none(self, tmp_path):
        xml_content = """<?xml version="1.0"?>
<HealthData locale="en_US">
  <Record type="HKQuantityTypeIdentifierHeartRate" value="72"/>
</HealthData>"""
        zip_path = tmp_path / "export.zip"
        zip_path.write_bytes(_xml_zip(xml_content))
        records, *_ = parse_apple_health(zip_path)
        assert len(records) == 1
        assert records.iloc[0]["sourceName"] is None
        assert records.iloc[0]["unit"] is None


# ---------------------------------------------------------------------------
# parse_apple_health — Correlations DataFrame
# ---------------------------------------------------------------------------


class TestCorrelationParsing:
    def test_correlation_count(self, tmp_path):
        zip_path = tmp_path / "export.zip"
        zip_path.write_bytes(_xml_zip(_CORRELATION_XML))
        _, correlations, _, _ = parse_apple_health(zip_path)
        assert len(correlations) == 1

    def test_correlation_type_attribute(self, tmp_path):
        zip_path = tmp_path / "export.zip"
        zip_path.write_bytes(_xml_zip(_CORRELATION_XML))
        _, correlations, _, _ = parse_apple_health(zip_path)
        assert (
            correlations.iloc[0]["type"] == "HKCorrelationTypeIdentifierBloodPressure"
        )

    def test_correlation_meta_parsed(self, tmp_path):
        zip_path = tmp_path / "export.zip"
        zip_path.write_bytes(_xml_zip(_CORRELATION_XML))
        _, correlations, _, _ = parse_apple_health(zip_path)
        assert correlations.iloc[0]["meta"] == {"HKWasUserEntered": "1"}

    def test_correlation_nested_record_count(self, tmp_path):
        zip_path = tmp_path / "export.zip"
        zip_path.write_bytes(_xml_zip(_CORRELATION_XML))
        _, correlations, _, _ = parse_apple_health(zip_path)
        assert len(correlations.iloc[0]["records"]) == 2

    def test_correlation_nested_record_attributes(self, tmp_path):
        zip_path = tmp_path / "export.zip"
        zip_path.write_bytes(_xml_zip(_CORRELATION_XML))
        _, correlations, _, _ = parse_apple_health(zip_path)
        rec = next(
            r
            for r in correlations.iloc[0]["records"]
            if r["type"] == "HKQuantityTypeIdentifierBloodPressureSystolic"
        )
        assert rec["value"] == "120"
        assert rec["unit"] == "mmHg"

    def test_records_inside_correlation_excluded_from_records_df(self, tmp_path):
        """Records that are children of a Correlation must not appear in the
        records DataFrame."""
        zip_path = tmp_path / "export.zip"
        zip_path.write_bytes(_xml_zip(_CORRELATION_XML))
        records, correlations, _, _ = parse_apple_health(zip_path)
        assert len(records) == 0
        assert len(correlations) == 1

    def test_unknown_correlation_child_raises(self, tmp_path):
        xml_content = """<?xml version="1.0"?>
<HealthData locale="en_US">
  <Correlation type="HKCorrelationTypeIdentifierBloodPressure"
    sourceName="Health" sourceVersion="1" device="d"
    creationDate="2024-01-01 00:00:00 +0000"
    startDate="2024-01-01 00:00:00 +0000"
    endDate="2024-01-01 00:01:00 +0000"
  >
    <UnknownElement/>
  </Correlation>
</HealthData>"""
        zip_path = tmp_path / "export.zip"
        zip_path.write_bytes(_xml_zip(xml_content))
        with pytest.raises(NotImplementedError):
            parse_apple_health(zip_path)


# ---------------------------------------------------------------------------
# parse_apple_health — Workouts DataFrame
# ---------------------------------------------------------------------------


class TestWorkoutParsing:
    def test_workout_count(self, tmp_path):
        zip_path = tmp_path / "export.zip"
        zip_path.write_bytes(_xml_zip(_WORKOUT_XML))
        _, _, workouts, _ = parse_apple_health(zip_path)
        assert len(workouts) == 1

    def test_workout_meta(self, tmp_path):
        zip_path = tmp_path / "export.zip"
        zip_path.write_bytes(_xml_zip(_WORKOUT_XML))
        _, _, workouts, _ = parse_apple_health(zip_path)
        assert workouts.iloc[0]["meta"] == {"HKTimeZone": "Europe/Berlin"}

    def test_workout_events(self, tmp_path):
        zip_path = tmp_path / "export.zip"
        zip_path.write_bytes(_xml_zip(_WORKOUT_XML))
        _, _, workouts, _ = parse_apple_health(zip_path)
        events = workouts.iloc[0]["events"]
        assert len(events) == 1
        assert events[0]["type"] == "HKWorkoutEventTypeLap"

    def test_workout_event_metadata_merged(self, tmp_path):
        """MetadataEntry children of WorkoutEvent must be merged
        into the event dict."""
        zip_path = tmp_path / "export.zip"
        zip_path.write_bytes(_xml_zip(_WORKOUT_XML))
        _, _, workouts, _ = parse_apple_health(zip_path)
        assert workouts.iloc[0]["events"][0]["HKLapLength"] == "1000"

    def test_workout_all_statistics_preserved(self, tmp_path):
        """All WorkoutStatistics children must be collected — not just the last."""
        zip_path = tmp_path / "export.zip"
        zip_path.write_bytes(_xml_zip(_WORKOUT_XML))
        _, _, workouts, _ = parse_apple_health(zip_path)
        stats = workouts.iloc[0]["statistics"]
        assert len(stats) == 2
        assert {s["type"] for s in stats} == {
            "HKQuantityTypeIdentifierHeartRate",
            "HKQuantityTypeIdentifierDistanceWalkingRunning",
        }

    def test_workout_no_statistics_is_empty_list(self, tmp_path):
        zip_path = tmp_path / "export.zip"
        zip_path.write_bytes(_xml_zip(_minimal_workout_xml()))
        _, _, workouts, _ = parse_apple_health(zip_path)
        assert workouts.iloc[0]["statistics"] == []

    def test_workout_route_files_and_meta(self, tmp_path):
        zip_path = tmp_path / "export.zip"
        zip_path.write_bytes(_xml_zip(_WORKOUT_XML))
        _, _, workouts, _ = parse_apple_health(zip_path)
        route = workouts.iloc[0]["route"]
        assert route is not None
        assert route["files"] == [_GPX_ROUTE_PATH]
        assert route["meta"] == {"HKMetadataKeyAltitudeType": "2"}

    def test_workout_route_absent_is_none(self, tmp_path):
        zip_path = tmp_path / "export.zip"
        zip_path.write_bytes(_xml_zip(_minimal_workout_xml()))
        _, _, workouts, _ = parse_apple_health(zip_path)
        assert workouts.iloc[0]["route"] is None

    def test_workout_activity_attributes(self, tmp_path):
        zip_path = tmp_path / "export.zip"
        zip_path.write_bytes(_xml_zip(_WORKOUT_XML))
        _, _, workouts, _ = parse_apple_health(zip_path)
        activity = workouts.iloc[0]["activities"][0]
        assert activity["uuid"] == "activity-uuid-1"

    def test_workout_activity_meta(self, tmp_path):
        zip_path = tmp_path / "export.zip"
        zip_path.write_bytes(_xml_zip(_WORKOUT_XML))
        _, _, workouts, _ = parse_apple_health(zip_path)
        assert workouts.iloc[0]["activities"][0]["meta"] == {
            "HKTimeZone": "Europe/Berlin"
        }

    def test_workout_activity_statistics(self, tmp_path):
        zip_path = tmp_path / "export.zip"
        zip_path.write_bytes(_xml_zip(_WORKOUT_XML))
        _, _, workouts, _ = parse_apple_health(zip_path)
        stats = workouts.iloc[0]["activities"][0]["statistics"]
        assert len(stats) == 1
        assert stats[0]["type"] == "HKQuantityTypeIdentifierHeartRate"

    def test_workout_activity_events(self, tmp_path):
        zip_path = tmp_path / "export.zip"
        zip_path.write_bytes(_xml_zip(_WORKOUT_XML))
        _, _, workouts, _ = parse_apple_health(zip_path)
        events = workouts.iloc[0]["activities"][0]["events"]
        assert len(events) == 1
        assert events[0]["type"] == "HKWorkoutEventTypeLap"

    def test_multiple_activities_all_preserved(self, tmp_path):
        """All WorkoutActivity children must be collected — not just
        the last."""
        zip_path = tmp_path / "export.zip"
        zip_path.write_bytes(_xml_zip(_MULTI_ACTIVITY_XML))
        _, _, workouts, _ = parse_apple_health(zip_path)
        activities = workouts.iloc[0]["activities"]
        assert len(activities) == 3
        assert {a["uuid"] for a in activities} == {"swim", "bike", "run"}

    def test_unknown_workout_child_raises(self, tmp_path):
        zip_path = tmp_path / "export.zip"
        zip_path.write_bytes(_xml_zip(_minimal_workout_xml("<UnknownElement/>")))
        with pytest.raises(NotImplementedError):
            parse_apple_health(zip_path)

    def test_unknown_workout_activity_child_raises(self, tmp_path):
        children = """
<WorkoutActivity uuid="a"
  startDate="2024-01-01 00:00:00 +0000"
  endDate="2024-01-01 00:30:00 +0000"
>
  <UnknownElement/>
</WorkoutActivity>"""
        zip_path = tmp_path / "export.zip"
        zip_path.write_bytes(_xml_zip(_minimal_workout_xml(children)))
        with pytest.raises(NotImplementedError):
            parse_apple_health(zip_path)


# ---------------------------------------------------------------------------
# parse_apple_health — ActivitySummary DataFrame
# ---------------------------------------------------------------------------


class TestActivitySummaryParsing:
    def test_activity_summary_count(self, tmp_path):
        zip_path = tmp_path / "export.zip"
        zip_path.write_bytes(_xml_zip(_ACTIVITY_SUMMARY_XML))
        _, _, _, activities = parse_apple_health(zip_path)
        assert len(activities) == 1

    def test_activity_summary_values(self, tmp_path):
        zip_path = tmp_path / "export.zip"
        zip_path.write_bytes(_xml_zip(_ACTIVITY_SUMMARY_XML))
        _, _, _, activities = parse_apple_health(zip_path)
        row = activities.iloc[0]
        assert row["dateComponents"] == "2024-01-01"
        assert row["activeEnergyBurned"] == "450"
        assert row["activeEnergyBurnedGoal"] == "500"


# ---------------------------------------------------------------------------
# parse_apple_health — from_date filtering
# ---------------------------------------------------------------------------


class TestFromDateFiltering:
    """Tests for the from_date parameter of parse_apple_health.

    The filter is *inclusive*: an element whose date equals from_date must be
    kept.  Only elements whose date falls *strictly before* from_date are
    dropped.  Elements that carry no recognisable date attribute (ExportDate,
    Me, the root HealthData tag) must be passed through without error.
    """

    @staticmethod
    def _with_late_record(xml: str) -> str:
        """Inject _LATE_RECORD_XML inside an existing <HealthData> document."""
        return xml.replace("</HealthData>", f"{_LATE_RECORD_XML}\n</HealthData>")

    def test_none_includes_all_records(self, tmp_path):
        """from_date=None is the default and must leave all records intact."""
        zip_path = tmp_path / "export.zip"
        zip_path.write_bytes(_xml_zip(_TWO_DATES_XML))
        records, *_ = parse_apple_health(zip_path, from_date=None)
        assert len(records) == 2

    def test_excludes_records_strictly_before(self, tmp_path):
        """Records whose endDate day is before from_date must be dropped."""
        zip_path = tmp_path / "export.zip"
        zip_path.write_bytes(_xml_zip(_TWO_DATES_XML))
        records, *_ = parse_apple_health(zip_path, from_date=pd.Timestamp("2024-01-02"))
        assert len(records) == 1
        assert records.iloc[0]["value"] == "70"

    def test_includes_records_on_from_date(self, tmp_path):
        """A record whose endDate equals from_date at day granularity must be kept
        (boundary is inclusive — the condition is strict less-than)."""
        zip_path = tmp_path / "export.zip"
        zip_path.write_bytes(_xml_zip(_TWO_DATES_XML))
        records, *_ = parse_apple_health(zip_path, from_date=pd.Timestamp("2024-01-01"))
        assert len(records) == 2

    def test_filters_workouts_by_end_date(self, tmp_path):
        """Workouts whose endDate falls before from_date must be excluded."""
        zip_path = tmp_path / "export.zip"
        zip_path.write_bytes(
            _xml_zip(self._with_late_record(_WORKOUT_XML))
        )  # endDate 2024-01-01 00:30
        _, _, workouts, _ = parse_apple_health(
            zip_path, from_date=pd.Timestamp("2024-01-02")
        )
        assert len(workouts) == 0

    def test_keeps_workout_on_from_date(self, tmp_path):
        zip_path = tmp_path / "export.zip"
        zip_path.write_bytes(_xml_zip(_WORKOUT_XML))
        _, _, workouts, _ = parse_apple_health(
            zip_path, from_date=pd.Timestamp("2024-01-01")
        )
        assert len(workouts) == 1

    def test_filters_correlations_by_end_date(self, tmp_path):
        """Correlations whose endDate falls before from_date must be excluded."""
        zip_path = tmp_path / "export.zip"
        zip_path.write_bytes(
            _xml_zip(self._with_late_record(_CORRELATION_XML))
        )  # endDate 2024-01-01
        _, correlations, _, _ = parse_apple_health(
            zip_path, from_date=pd.Timestamp("2024-01-02")
        )
        assert len(correlations) == 0

    def test_keeps_correlation_on_from_date(self, tmp_path):
        zip_path = tmp_path / "export.zip"
        zip_path.write_bytes(_xml_zip(_CORRELATION_XML))
        _, correlations, _, _ = parse_apple_health(
            zip_path, from_date=pd.Timestamp("2024-01-01")
        )
        assert len(correlations) == 1

    def test_filters_activity_summaries_by_date_components(self, tmp_path):
        """ActivitySummary carries its date in dateComponents, not endDate.
        The fallback attribute chain must reach it and filter correctly."""
        zip_path = tmp_path / "export.zip"
        zip_path.write_bytes(
            _xml_zip(self._with_late_record(_ACTIVITY_SUMMARY_XML))
        )  # dateComponents 2024-01-01
        _, _, _, activities = parse_apple_health(
            zip_path, from_date=pd.Timestamp("2024-01-02")
        )
        assert len(activities) == 0

    def test_keeps_activity_summary_on_from_date(self, tmp_path):
        zip_path = tmp_path / "export.zip"
        zip_path.write_bytes(_xml_zip(_ACTIVITY_SUMMARY_XML))
        _, _, _, activities = parse_apple_health(
            zip_path, from_date=pd.Timestamp("2024-01-01")
        )
        assert len(activities) == 1

    def test_dateless_elements_do_not_crash(self, tmp_path):
        """Elements with no endDate/date/dateComponents (ExportDate, Me) must
        be silently passed through when from_date is set — previously this
        caused a ValueError from NaT.date()."""
        zip_path = tmp_path / "export.zip"
        # _XML_WITH_KNOWN_UNHANDLED contains ExportDate and Me alongside a Record.
        # Use a from_date before the record so the result is non-empty.
        zip_path.write_bytes(_xml_zip(_XML_WITH_KNOWN_UNHANDLED))
        records, *_ = parse_apple_health(zip_path, from_date=pd.Timestamp("2023-06-01"))
        assert len(records) == 1

    def test_all_filtered_raises_no_health_data_error(self, tmp_path):
        """If from_date discards every element, NoHealthDataError must still fire."""
        zip_path = tmp_path / "export.zip"
        zip_path.write_bytes(_xml_zip(_TWO_DATES_XML))
        with pytest.raises(NoHealthDataError):
            parse_apple_health(zip_path, from_date=pd.Timestamp("2025-01-01"))


# ---------------------------------------------------------------------------
# Security: XXE prevention
# ---------------------------------------------------------------------------


class TestXXESecurity:
    def test_xxe_entity_expansion_blocked(self, tmp_path):
        """Defusedxml must block DOCTYPE/ENTITY XXE attacks."""
        xxe_xml = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE foo [ <!ENTITY xxe SYSTEM "file:///etc/passwd"> ]>
<HealthData locale="en_US">
  <Record type="HK" sourceName="&xxe;" sourceVersion="1" device="d"
    unit="bpm" creationDate="2024-01-01 00:00:00 +0000"
    startDate="2024-01-01 00:00:00 +0000"
    endDate="2024-01-01 00:01:00 +0000" value="1"/>
</HealthData>
"""
        zip_path = tmp_path / "export.zip"
        zip_path.write_bytes(_xml_zip(xxe_xml))
        with pytest.raises(defusedxml.common.EntitiesForbidden):
            parse_apple_health(zip_path)

    def test_billion_laughs_blocked(self, tmp_path):
        """Defusedxml must block entity expansion DoS attacks."""
        bl_xml = """<?xml version="1.0"?>
<!DOCTYPE lolz [
  <!ENTITY lol "lol">
  <!ENTITY lol2 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">
  <!ENTITY lol3 "&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;">
]>
<HealthData locale="en_US">&lol3;</HealthData>
"""
        zip_path = tmp_path / "export.zip"
        zip_path.write_bytes(_xml_zip(bl_xml))
        with pytest.raises(defusedxml.common.EntitiesForbidden):
            parse_apple_health(zip_path)

    def test_malformed_xml_raises(self, tmp_path):
        zip_path = tmp_path / "export.zip"
        zip_path.write_bytes(_xml_zip("<HealthData><Unclosed>"))
        with pytest.raises(xml.etree.ElementTree.ParseError):
            parse_apple_health(zip_path)


# ---------------------------------------------------------------------------
# Performance
# ---------------------------------------------------------------------------


class TestParserPerformance:
    def test_large_export_under_time_limit(self, tmp_path):
        n = 100_000
        rows = "\n".join(
            f'<Record type="HKQuantityTypeIdentifierHeartRate" sourceName="Watch" '
            f'sourceVersion="1" device="d" unit="count/min" '
            f'creationDate="2024-01-01 00:00:00 +0000" '
            f'startDate="2024-01-{1 + ((i // 60) // 60) // 24:02d} '
            f'{((i // 60) // 60) % 24:02d}:{(i // 60) % 60:02d}:{i % 60:02d} +0000" '
            f'endDate="2024-01-{1 + ((i // 60) // 60) // 24:02d} '
            f'{((i // 60) // 60) % 24:02d}:{(i // 60) % 60:02d}:{i % 60:02d} +0000" '
            f'value="{60 + i % 40}"/>'
            for i in range(n)
        )
        xml_content = (
            f'<?xml version="1.0"?><HealthData locale="en_US">{rows}</HealthData>'
        )
        zip_path = tmp_path / "export.zip"
        zip_path.write_bytes(_xml_zip(xml_content))
        start = time.perf_counter()
        records, *_ = parse_apple_health(zip_path)
        elapsed = time.perf_counter() - start
        assert len(records) == n
        assert elapsed < 30.0


# ---------------------------------------------------------------------------
# parse_apple_health_routes
# ---------------------------------------------------------------------------


class TestParseAppleHealthRoutes:
    def test_returns_dataframe(self, tmp_path):
        zip_path = tmp_path / "export.zip"
        zip_path.write_bytes(_route_zip())
        df = parse_apple_health_routes(zip_path, paths=[_GPX_ROUTE_PATH])
        assert isinstance(df, pd.DataFrame)

    def test_expected_columns(self, tmp_path):
        zip_path = tmp_path / "export.zip"
        zip_path.write_bytes(_route_zip())
        df = parse_apple_health_routes(zip_path, paths=[_GPX_ROUTE_PATH])
        assert set(df.columns) == {
            "file",
            "lat",
            "lon",
            "ele",
            "time",
            "speed",
            "course",
            "hAcc",
            "vAcc",
        }

    def test_trackpoint_count(self, tmp_path):
        zip_path = tmp_path / "export.zip"
        zip_path.write_bytes(_route_zip())
        df = parse_apple_health_routes(zip_path, paths=[_GPX_ROUTE_PATH])
        assert len(df) == 2

    def test_lat_lon_are_float(self, tmp_path):
        zip_path = tmp_path / "export.zip"
        zip_path.write_bytes(_route_zip())
        df = parse_apple_health_routes(zip_path, paths=[_GPX_ROUTE_PATH])
        assert pd.api.types.is_float_dtype(df["lat"])
        assert pd.api.types.is_float_dtype(df["lon"])

    def test_lat_lon_values(self, tmp_path):
        zip_path = tmp_path / "export.zip"
        zip_path.write_bytes(_route_zip())
        df = parse_apple_health_routes(zip_path, paths=[_GPX_ROUTE_PATH])
        assert df.iloc[0]["lat"] == pytest.approx(52.520008)
        assert df.iloc[0]["lon"] == pytest.approx(13.404954)

    def test_ele_as_float(self, tmp_path):
        zip_path = tmp_path / "export.zip"
        zip_path.write_bytes(_route_zip())
        df = parse_apple_health_routes(zip_path, paths=[_GPX_ROUTE_PATH])
        assert df.iloc[0]["ele"] == pytest.approx(34.5)

    def test_time_is_utc_datetime(self, tmp_path):
        zip_path = tmp_path / "export.zip"
        zip_path.write_bytes(_route_zip())
        df = parse_apple_health_routes(zip_path, paths=[_GPX_ROUTE_PATH])
        assert pd.api.types.is_datetime64_any_dtype(df["time"])
        assert str(df["time"].dt.tz) == "UTC"
        assert df.iloc[0]["time"] == pd.Timestamp("2024-01-01T09:00:00Z")

    def test_extension_field_values(self, tmp_path):
        zip_path = tmp_path / "export.zip"
        zip_path.write_bytes(_route_zip())
        df = parse_apple_health_routes(zip_path, paths=[_GPX_ROUTE_PATH])
        row = df.iloc[0]
        assert row["speed"] == pytest.approx(2.83)
        assert row["course"] == pytest.approx(274.5)
        assert row["hAcc"] == pytest.approx(4.2)
        assert row["vAcc"] == pytest.approx(3.1)

    def test_file_column_value(self, tmp_path):
        zip_path = tmp_path / "export.zip"
        zip_path.write_bytes(_route_zip())
        df = parse_apple_health_routes(zip_path, paths=[_GPX_ROUTE_PATH])
        assert (df["file"] == _GPX_ROUTE_PATH).all()

    def test_paths_none_discovers_gpx_files(self, tmp_path):
        """paths=None must discover all GPX files under workout-routes/."""
        zip_path = tmp_path / "export.zip"
        zip_path.write_bytes(
            _make_zip(
                {
                    "apple_health_export/export.xml": _WORKOUT_XML,
                    f"apple_health_export/{_GPX_ROUTE_PATH}": _GPX_TWO_POINTS,
                }
            )
        )
        df = parse_apple_health_routes(zip_path)
        assert len(df) == 2

    def test_paths_none_ignores_non_gpx_and_wrong_directory(self, tmp_path):
        """Non-.gpx files and GPX files outside workout-routes/ must be ignored."""
        zip_path = tmp_path / "export.zip"
        zip_path.write_bytes(
            _make_zip(
                {
                    "apple_health_export/export.xml": _WORKOUT_XML,
                    f"apple_health_export/{_GPX_ROUTE_PATH}": _GPX_TWO_POINTS,
                    "apple_health_export/workout-routes/metadata.json": "{}",
                    "apple_health_export/export.gpx": _GPX_TWO_POINTS,
                }
            )
        )
        df = parse_apple_health_routes(zip_path)
        assert len(df) == 2
        assert (df["file"] == _GPX_ROUTE_PATH).all()

    def test_multiple_gpx_files_combined(self, tmp_path):
        zip_path = tmp_path / "export.zip"
        zip_path.write_bytes(
            _make_zip(
                {
                    "apple_health_export/export.xml": _WORKOUT_XML,
                    f"apple_health_export/{_GPX_ROUTE_PATH}": _GPX_TWO_POINTS,
                    f"apple_health_export/{_GPX_ROUTE_PATH_2}": _GPX_TWO_POINTS,
                }
            )
        )
        df = parse_apple_health_routes(
            zip_path, paths=[_GPX_ROUTE_PATH, _GPX_ROUTE_PATH_2]
        )
        assert len(df) == 4
        assert set(df["file"].unique()) == {_GPX_ROUTE_PATH, _GPX_ROUTE_PATH_2}

    def test_missing_ele_is_nan(self, tmp_path):
        zip_path = tmp_path / "export.zip"
        zip_path.write_bytes(_route_zip(gpx_content=_GPX_MISSING_OPTIONAL))
        df = parse_apple_health_routes(zip_path, paths=[_GPX_ROUTE_PATH])
        assert pd.isna(df.iloc[0]["ele"])

    def test_missing_extensions_are_nan(self, tmp_path):
        """A trackpoint with no <extensions> element must produce NaN for
        all extension fields."""
        zip_path = tmp_path / "export.zip"
        zip_path.write_bytes(_route_zip(gpx_content=_GPX_MISSING_OPTIONAL))
        df = parse_apple_health_routes(zip_path, paths=[_GPX_ROUTE_PATH])
        for field in ("speed", "course", "hAcc", "vAcc"):
            assert pd.isna(df.iloc[0][field]), (
                f"{field} should be NaN when extensions are absent"
            )

    def test_empty_gpx_returns_empty_dataframe(self, tmp_path):
        zip_path = tmp_path / "export.zip"
        zip_path.write_bytes(_route_zip(gpx_content=_GPX_EMPTY))
        df = parse_apple_health_routes(zip_path, paths=[_GPX_ROUTE_PATH])
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 0

    def test_accepts_path_object(self, tmp_path):
        zip_path = tmp_path / "export.zip"
        zip_path.write_bytes(_route_zip())
        df = parse_apple_health_routes(Path(zip_path), paths=[_GPX_ROUTE_PATH])
        assert len(df) == 2

    def test_accepts_string_path(self, tmp_path):
        zip_path = tmp_path / "export.zip"
        zip_path.write_bytes(_route_zip())
        df = parse_apple_health_routes(str(zip_path), paths=[_GPX_ROUTE_PATH])
        assert len(df) == 2

    def test_join_to_workouts_via_file_column(self, tmp_path):
        """Route file column must match paths extracted from the workouts DataFrame."""
        zip_path = tmp_path / "export.zip"
        zip_path.write_bytes(_route_zip())
        _, _, workouts, _ = parse_apple_health(zip_path)
        route_paths = [
            path for route in workouts["route"].dropna() for path in route["files"]
        ]
        routes = parse_apple_health_routes(zip_path, paths=route_paths)
        assert len(routes) == 2
        assert (routes["file"] == _GPX_ROUTE_PATH).all()


# ---------------------------------------------------------------------------
# Unknown top-level elements — should WARN, not crash, not be silent
# ---------------------------------------------------------------------------


_XML_WITH_KNOWN_UNHANDLED = """<?xml version="1.0" encoding="UTF-8"?>
<HealthData locale="en_US">
  <ExportDate value="2024-01-01 00:00:00 +0000"/>
  <Me
    HKCharacteristicTypeIdentifierDateOfBirth=""
    HKCharacteristicTypeIdentifierBiologicalSex="HKBiologicalSexNotSet"/>
  <Record
    type="HKQuantityTypeIdentifierHeartRate"
    sourceName="Watch" sourceVersion="1" device="d" unit="count/min"
    creationDate="2024-01-01 00:00:00 +0000"
    startDate="2024-01-01 00:00:00 +0000"
    endDate="2024-01-01 00:01:00 +0000"
    value="72"/>
</HealthData>"""


_XML_WITH_GENUINELY_UNKNOWN = """<?xml version="1.0" encoding="UTF-8"?>
<HealthData locale="en_US">
  <BrandNewElementApolloAddsInIos25 foo="bar"/>
  <BrandNewElementApolloAddsInIos25 foo="baz"/>
  <Record
    type="HKQuantityTypeIdentifierHeartRate"
    sourceName="Watch" sourceVersion="1" device="d" unit="count/min"
    creationDate="2024-01-01 00:00:00 +0000"
    startDate="2024-01-01 00:00:00 +0000"
    endDate="2024-01-01 00:01:00 +0000"
    value="72"/>
</HealthData>"""


class TestUnknownTopLevelElements:
    def test_known_unhandled_tag_does_not_raise(self, tmp_path):
        """ExportDate / Me are known but unhandled — they must not crash."""
        zip_path = tmp_path / "export.zip"
        zip_path.write_bytes(_xml_zip(_XML_WITH_KNOWN_UNHANDLED))
        records, *_ = parse_apple_health(zip_path)
        assert len(records) == 1

    def test_unknown_tag_does_not_raise(self, tmp_path):
        zip_path = tmp_path / "export.zip"
        zip_path.write_bytes(_xml_zip(_XML_WITH_GENUINELY_UNKNOWN))
        records, *_ = parse_apple_health(zip_path)
        assert len(records) == 1

    def test_known_unhandled_tag_logged_as_warning(self, tmp_path, caplog):
        """A WARNING should be emitted naming each unhandled tag and its count."""
        zip_path = tmp_path / "export.zip"
        zip_path.write_bytes(_xml_zip(_XML_WITH_KNOWN_UNHANDLED))
        with caplog.at_level(logging.WARNING, logger="src.importer.parser"):
            parse_apple_health(zip_path)

        warnings = [r for r in caplog.records if r.levelname == "WARNING"]
        assert any(
            "ExportDate=1" in r.getMessage() or "Me=1" in r.getMessage()
            for r in warnings
        )

    def test_unknown_tag_marked_as_unrecognised_in_log(self, tmp_path, caplog):
        """Truly unknown tags get a "(unrecognised)" marker so operators
        can distinguish them from known-but-skipped ones."""
        zip_path = tmp_path / "export.zip"
        zip_path.write_bytes(_xml_zip(_XML_WITH_GENUINELY_UNKNOWN))
        with caplog.at_level(logging.WARNING, logger="src.importer.parser"):
            parse_apple_health(zip_path)

        warning_msgs = [
            r.getMessage() for r in caplog.records if r.levelname == "WARNING"
        ]
        assert any(
            "BrandNewElementApolloAddsInIos25" in m and "unrecognised" in m
            for m in warning_msgs
        )

    def test_count_aggregated_in_single_warning(self, tmp_path, caplog):
        """Multiple occurrences of one tag → one warning with count, not N warnings."""
        zip_path = tmp_path / "export.zip"
        zip_path.write_bytes(_xml_zip(_XML_WITH_GENUINELY_UNKNOWN))
        with caplog.at_level(logging.WARNING, logger="src.importer.parser"):
            parse_apple_health(zip_path)

        # Only one WARNING is emitted summarising unhandled elements.
        unhandled_warnings = [
            r
            for r in caplog.records
            if r.levelname == "WARNING"
            and "BrandNewElementApolloAddsInIos25" in r.getMessage()
        ]
        assert len(unhandled_warnings) == 1
        # And the count "=2" appears in that one warning.
        assert "=2" in unhandled_warnings[0].getMessage()

    def test_workout_children_not_counted_as_unknown(self, tmp_path, caplog):
        """WorkoutEvent, WorkoutStatistics, WorkoutRoute, WorkoutActivity,
        MetadataEntry, and FileReference are all processed inside the Workout
        branch and must never appear in the unknown-elements warning.

        Before the fix, every child's 'end' event fell through to case _: and
        inflated unknown_counts with internal tag names.
        """
        zip_path = tmp_path / "export.zip"
        zip_path.write_bytes(_xml_zip(_WORKOUT_XML))
        with caplog.at_level(logging.WARNING, logger="src.importer.parser"):
            parse_apple_health(zip_path)

        child_tags = {
            "WorkoutEvent",
            "WorkoutStatistics",
            "WorkoutRoute",
            "WorkoutActivity",
            "MetadataEntry",
            "FileReference",
        }
        warning_msgs = [
            r.getMessage() for r in caplog.records if r.levelname == "WARNING"
        ]
        for msg in warning_msgs:
            for tag in child_tags:
                assert tag not in msg, (
                    f"Internal tag {tag!r} must not appear in the unknown-elements"
                    f" warning; got: {msg!r}"
                )

    def test_correlation_children_not_counted_as_unknown(self, tmp_path, caplog):
        """MetadataEntry and Record children of a Correlation must not appear
        in the unknown-elements warning.

        Record is already guarded by the inside_complex flag; this test ensures
        MetadataEntry (which has no dedicated top-level case) is also excluded.
        """
        zip_path = tmp_path / "export.zip"
        zip_path.write_bytes(_xml_zip(_CORRELATION_XML))
        with caplog.at_level(logging.WARNING, logger="src.importer.parser"):
            parse_apple_health(zip_path)

        child_tags = {"MetadataEntry", "Record"}
        warning_msgs = [
            r.getMessage() for r in caplog.records if r.levelname == "WARNING"
        ]
        for msg in warning_msgs:
            for tag in child_tags:
                assert tag not in msg, (
                    f"Internal tag {tag!r} must not appear in the unknown-elements"
                    f" warning; got: {msg!r}"
                )


class TestEndOfParseLogging:
    def test_records_count_logged(self, tmp_path, caplog):
        """The parser emits a summary INFO line at end-of-parse."""
        zip_path = tmp_path / "export.zip"
        zip_path.write_bytes(_xml_zip(_RECORD_XML))
        with caplog.at_level(logging.INFO, logger="src.importer.parser"):
            parse_apple_health(zip_path)

        info_msgs = [r.getMessage() for r in caplog.records if r.levelname == "INFO"]
        # Look for the summary that mentions records/correlations/workouts/activities.
        assert any(
            "records" in m and "correlation" in m and "workout" in m for m in info_msgs
        )
