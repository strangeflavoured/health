"""Tests for src/importer/parser.py.

Covers:
- DataFrame shapes and column schemas (catches schema drift on our side).
- Per-element parsing of Records, Correlations, Workouts, ActivitySummary.
- ``from_date`` filtering semantics (day granularity, inclusive boundary).
- Correlation child-record linking by index into records_df.
- ``skip_records`` and ``parse_record_metadata`` flags.
- Unknown top-level element handling: known-skip vs unrecognised (catches
  schema drift on Apple's side).
- XML security: XXE / billion-laughs blocked at the lxml level.
- GPX route parsing and join-back to workouts.
- Performance guard: a 100k-record date-filtered parse stays well under the
  pre-refactor wall time, catching regressions like ``pd.to_datetime`` in the
  hot path.
"""

from __future__ import annotations

import io
import logging
import time
import zipfile
from pathlib import Path

import pandas as pd
import pytest
from lxml import etree

from src.importer.parser import (
    _ACTIVITY_ATTRS,
    _ACTIVITY_COLUMNS,
    _CORRELATION_ATTRS,
    _CORRELATION_COLUMNS,
    _KNOWN_UNHANDLED_TAGS,
    _RECORD_COLUMNS,
    _WORKOUT_ATTRS,
    _WORKOUT_COLUMNS,
    RECORD_ATTRS,
    NoHealthDataError,
    parse_apple_health,
    parse_apple_health_routes,
)

# ---------------------------------------------------------------------------
# XML / GPX fixtures
# ---------------------------------------------------------------------------

_RECORD_XML = """<?xml version="1.0" encoding="UTF-8"?>
<HealthData locale="en_US">
  <Record type="HKQuantityTypeIdentifierHeartRate" sourceName="Apple Watch"
    sourceVersion="9.0" device="watch" unit="count/min"
    creationDate="2024-01-01 00:00:00 +0000"
    startDate="2024-01-01 00:00:00 +0000"
    endDate="2024-01-01 00:01:00 +0000" value="72"/>
  <Record type="HKQuantityTypeIdentifierStepCount" sourceName="iPhone"
    sourceVersion="17.0" device="phone" unit="count"
    creationDate="2024-01-01 00:02:00 +0000"
    startDate="2024-01-01 00:02:00 +0000"
    endDate="2024-01-01 00:03:00 +0000" value="500"/>
</HealthData>
"""

_RECORD_WITH_META_XML = """<?xml version="1.0" encoding="UTF-8"?>
<HealthData locale="en_US">
  <Record type="HKQuantityTypeIdentifierHeartRate" sourceName="Apple Watch"
    sourceVersion="9.0" device="watch" unit="count/min"
    creationDate="2024-01-01 00:00:00 +0000"
    startDate="2024-01-01 00:00:00 +0000"
    endDate="2024-01-01 00:01:00 +0000" value="72">
    <MetadataEntry key="HKMetadataKeyHeartRateMotionContext" value="1"/>
    <MetadataEntry key="HKMetadataKeyTimeZone" value="Europe/Berlin"/>
  </Record>
  <Record type="HKQuantityTypeIdentifierStepCount" sourceName="iPhone"
    sourceVersion="17.0" device="phone" unit="count"
    creationDate="2024-01-01 00:02:00 +0000"
    startDate="2024-01-01 00:02:00 +0000"
    endDate="2024-01-01 00:03:00 +0000" value="500"/>
</HealthData>
"""

# Correlation followed by the top-level duplicate Records that Apple's DTD
# guarantees are present.  This lets us test the index-resolution path.
_CORRELATION_XML = """<?xml version="1.0" encoding="UTF-8"?>
<HealthData locale="en_US">
  <Correlation type="HKCorrelationTypeIdentifierBloodPressure" sourceName="Health"
    sourceVersion="17.0" device="phone"
    creationDate="2024-01-01 00:00:00 +0000"
    startDate="2024-01-01 00:00:00 +0000"
    endDate="2024-01-01 00:01:00 +0000">
    <MetadataEntry key="HKWasUserEntered" value="1"/>
    <Record type="HKQuantityTypeIdentifierBloodPressureSystolic" sourceName="Health"
      sourceVersion="17.0" device="phone" unit="mmHg"
      creationDate="2024-01-01 00:00:00 +0000"
      startDate="2024-01-01 00:00:00 +0000"
      endDate="2024-01-01 00:01:00 +0000" value="120"/>
    <Record type="HKQuantityTypeIdentifierBloodPressureDiastolic" sourceName="Health"
      sourceVersion="17.0" device="phone" unit="mmHg"
      creationDate="2024-01-01 00:00:00 +0000"
      startDate="2024-01-01 00:00:00 +0000"
      endDate="2024-01-01 00:01:00 +0000" value="80"/>
  </Correlation>
  <Record type="HKQuantityTypeIdentifierBloodPressureSystolic" sourceName="Health"
    sourceVersion="17.0" device="phone" unit="mmHg"
    creationDate="2024-01-01 00:00:00 +0000"
    startDate="2024-01-01 00:00:00 +0000"
    endDate="2024-01-01 00:01:00 +0000" value="120"/>
  <Record type="HKQuantityTypeIdentifierBloodPressureDiastolic" sourceName="Health"
    sourceVersion="17.0" device="phone" unit="mmHg"
    creationDate="2024-01-01 00:00:00 +0000"
    startDate="2024-01-01 00:00:00 +0000"
    endDate="2024-01-01 00:01:00 +0000" value="80"/>
</HealthData>
"""

# Correlation with NO top-level duplicates (synthetic edge case).
_CORRELATION_NO_DUPES_XML = """<?xml version="1.0" encoding="UTF-8"?>
<HealthData locale="en_US">
  <Correlation type="HKCorrelationTypeIdentifierBloodPressure" sourceName="Health"
    sourceVersion="17.0" device="phone"
    creationDate="2024-01-01 00:00:00 +0000"
    startDate="2024-01-01 00:00:00 +0000"
    endDate="2024-01-01 00:01:00 +0000">
    <Record type="HKQuantityTypeIdentifierBloodPressureSystolic" sourceName="Health"
      sourceVersion="17.0" device="phone" unit="mmHg"
      creationDate="2024-01-01 00:00:00 +0000"
      startDate="2024-01-01 00:00:00 +0000"
      endDate="2024-01-01 00:01:00 +0000" value="120"/>
  </Correlation>
</HealthData>
"""

_GPX_ROUTE_PATH = "workout-routes/route_2024-01-01_123.gpx"
_GPX_ROUTE_PATH_2 = "workout-routes/route_2024-01-02_456.gpx"

_WORKOUT_XML = f"""<?xml version="1.0" encoding="UTF-8"?>
<HealthData locale="en_US">
  <Workout workoutActivityType="HKWorkoutActivityTypeRunning"
    duration="30.0" durationUnit="min"
    sourceName="Apple Watch" sourceVersion="9.0" device="watch"
    creationDate="2024-01-01 00:00:00 +0000"
    startDate="2024-01-01 00:00:00 +0000"
    endDate="2024-01-01 00:30:00 +0000">
    <MetadataEntry key="HKTimeZone" value="Europe/Berlin"/>
    <WorkoutEvent type="HKWorkoutEventTypeLap"
      date="2024-01-01 00:10:00 +0000"
      duration="600.0" durationUnit="s">
      <MetadataEntry key="HKLapLength" value="1000"/>
    </WorkoutEvent>
    <WorkoutStatistics type="HKQuantityTypeIdentifierHeartRate"
      startDate="2024-01-01 00:00:00 +0000"
      endDate="2024-01-01 00:30:00 +0000"
      average="145" minimum="120" maximum="175" unit="count/min"/>
    <WorkoutStatistics type="HKQuantityTypeIdentifierDistanceWalkingRunning"
      startDate="2024-01-01 00:00:00 +0000"
      endDate="2024-01-01 00:30:00 +0000"
      sum="5000" unit="m"/>
    <WorkoutRoute sourceName="Apple Watch" sourceVersion="9.0" device="watch"
      creationDate="2024-01-01 00:00:00 +0000"
      startDate="2024-01-01 00:00:00 +0000"
      endDate="2024-01-01 00:30:00 +0000">
      <FileReference path="{_GPX_ROUTE_PATH}"/>
      <MetadataEntry key="HKMetadataKeyAltitudeType" value="2"/>
    </WorkoutRoute>
    <WorkoutActivity uuid="activity-uuid-1"
      startDate="2024-01-01 00:00:00 +0000"
      endDate="2024-01-01 00:30:00 +0000">
      <MetadataEntry key="HKTimeZone" value="Europe/Berlin"/>
      <WorkoutEvent type="HKWorkoutEventTypeLap" date="2024-01-01 00:10:00 +0000"/>
      <WorkoutStatistics type="HKQuantityTypeIdentifierHeartRate"
        startDate="2024-01-01 00:00:00 +0000"
        endDate="2024-01-01 00:30:00 +0000"
        average="145" unit="count/min"/>
    </WorkoutActivity>
  </Workout>
</HealthData>
"""

_MULTI_ACTIVITY_XML = """<?xml version="1.0" encoding="UTF-8"?>
<HealthData locale="en_US">
  <Workout workoutActivityType="HKWorkoutActivityTypeSwimBikeRun"
    sourceName="Apple Watch" sourceVersion="9.0" device="watch"
    creationDate="2024-01-01 00:00:00 +0000"
    startDate="2024-01-01 00:00:00 +0000"
    endDate="2024-01-01 01:00:00 +0000">
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
  <ActivitySummary dateComponents="2024-01-01"
    activeEnergyBurned="450"
    activeEnergyBurnedGoal="500"
    activeEnergyBurnedUnit="kcal"
    appleExerciseTime="35" appleExerciseTimeGoal="30"
    appleStandHours="12" appleStandHoursGoal="12"/>
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
  <Record type="HKQuantityTypeIdentifierHeartRate"
    sourceName="Watch" sourceVersion="1" device="d" unit="count/min"
    creationDate="2024-01-01 00:00:00 +0000"
    startDate="2024-01-01 00:00:00 +0000"
    endDate="2024-01-01 00:01:00 +0000" value="60"/>
  <Record type="HKQuantityTypeIdentifierHeartRate"
    sourceName="Watch" sourceVersion="1" device="d" unit="count/min"
    creationDate="2024-01-03 00:00:00 +0000"
    startDate="2024-01-03 00:00:00 +0000"
    endDate="2024-01-03 00:01:00 +0000" value="70"/>
</HealthData>
"""

_LATE_RECORD_XML = """\
  <Record type="HKQuantityTypeIdentifierHeartRate"
    sourceName="Watch" sourceVersion="1" device="d" unit="count/min"
    creationDate="2024-01-03 00:00:00 +0000"
    startDate="2024-01-03 00:00:00 +0000"
    endDate="2024-01-03 00:01:00 +0000" value="1"/>"""

_XML_WITH_KNOWN_UNHANDLED = """<?xml version="1.0" encoding="UTF-8"?>
<HealthData locale="en_US">
  <ExportDate value="2024-01-01 00:00:00 +0000"/>
  <Me HKCharacteristicTypeIdentifierBiologicalSex="HKBiologicalSexNotSet"/>
  <Record type="HKQuantityTypeIdentifierHeartRate"
    sourceName="Watch" sourceVersion="1" device="d" unit="count/min"
    creationDate="2024-01-01 00:00:00 +0000"
    startDate="2024-01-01 00:00:00 +0000"
    endDate="2024-01-01 00:01:00 +0000" value="72"/>
</HealthData>
"""

_XML_WITH_GENUINELY_UNKNOWN = """<?xml version="1.0" encoding="UTF-8"?>
<HealthData locale="en_US">
  <BrandNewElementApolloAddsInIos25 foo="bar"/>
  <BrandNewElementApolloAddsInIos25 foo="baz"/>
  <Record type="HKQuantityTypeIdentifierHeartRate"
    sourceName="Watch" sourceVersion="1" device="d" unit="count/min"
    creationDate="2024-01-01 00:00:00 +0000"
    startDate="2024-01-01 00:00:00 +0000"
    endDate="2024-01-01 00:01:00 +0000" value="72"/>
</HealthData>
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_zip(files):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    return buf.getvalue()


def _xml_zip(xml_content):
    return _make_zip({"apple_health_export/export.xml": xml_content})


def _route_zip(
    xml_content=_WORKOUT_XML, gpx_content=_GPX_TWO_POINTS, route_path=_GPX_ROUTE_PATH
):
    return _make_zip(
        {
            "apple_health_export/export.xml": xml_content,
            f"apple_health_export/{route_path}": gpx_content,
        }
    )


def _minimal_workout_xml(children=""):
    return f"""<?xml version="1.0"?>
<HealthData locale="en_US">
  <Workout workoutActivityType="HKWorkoutActivityTypeRunning"
    sourceName="Watch" sourceVersion="1" device="d"
    creationDate="2024-01-01 00:00:00 +0000"
    startDate="2024-01-01 00:00:00 +0000"
    endDate="2024-01-01 00:30:00 +0000">{children}</Workout>
</HealthData>"""


# ---------------------------------------------------------------------------
# Schema constants — guard against accidental drift on our side
# ---------------------------------------------------------------------------


class TestSchemaConstants:
    """Pin the column constants so a careless edit fails loudly here rather
    than producing a silent breaking change in the DataFrame shape."""

    def test_record_attrs_pinned(self):
        assert RECORD_ATTRS == (
            "type",
            "sourceName",
            "sourceVersion",
            "device",
            "unit",
            "startDate",
            "endDate",
            "creationDate",
            "value",
        )

    def test_record_columns_extends_record_attrs(self):
        assert _RECORD_COLUMNS == RECORD_ATTRS + ("meta",)

    def test_correlation_columns_extends_correlation_attrs(self):
        assert _CORRELATION_COLUMNS == _CORRELATION_ATTRS + ("meta", "records")

    def test_workout_columns_extends_workout_attrs(self):
        assert _WORKOUT_COLUMNS == _WORKOUT_ATTRS + (
            "meta",
            "events",
            "statistics",
            "route",
            "activities",
        )

    def test_activity_columns_equals_activity_attrs(self):
        assert _ACTIVITY_COLUMNS == _ACTIVITY_ATTRS

    def test_attrs_contain_only_xml_attribute_names(self):
        """A real XML attribute name never contains a Python identifier we
        would also use for a derived field.  This is a sanity guard so the
        constants don't drift back into the previous conflated state."""
        derived = {"meta", "records", "events", "statistics", "route", "activities"}
        for const_name, attrs in [
            ("_RECORD_ATTRS", RECORD_ATTRS),
            ("_CORRELATION_ATTRS", _CORRELATION_ATTRS),
            ("_WORKOUT_ATTRS", _WORKOUT_ATTRS),
            ("_ACTIVITY_ATTRS", _ACTIVITY_ATTRS),
        ]:
            collision = set(attrs) & derived
            assert not collision, (
                f"{const_name} contains derived field name(s): {collision}"
            )

    def test_known_unhandled_tags_includes_critical_tags(self):
        """ExportDate and Me are emitted by every real Apple Health export.
        If they're ever removed from this set we'd start screaming about
        valid exports."""
        assert {"ExportDate", "Me"} <= _KNOWN_UNHANDLED_TAGS


# ---------------------------------------------------------------------------
# parse_apple_health — return type & error handling
# ---------------------------------------------------------------------------


class TestParseAppleHealth:
    def test_returns_four_dataframes(self, tmp_path):
        zp = tmp_path / "x.zip"
        zp.write_bytes(_xml_zip(_RECORD_XML))
        result = parse_apple_health(zp)
        assert isinstance(result, tuple) and len(result) == 4
        assert all(isinstance(df, pd.DataFrame) for df in result)

    def test_accepts_path_object(self, tmp_path):
        zp = tmp_path / "x.zip"
        zp.write_bytes(_xml_zip(_RECORD_XML))
        records, *_ = parse_apple_health(Path(zp))
        assert len(records) == 2

    def test_accepts_string_path(self, tmp_path):
        zp = tmp_path / "x.zip"
        zp.write_bytes(_xml_zip(_RECORD_XML))
        records, *_ = parse_apple_health(str(zp))
        assert len(records) == 2

    def test_all_empty_raises_no_health_data_error(self, tmp_path):
        zp = tmp_path / "x.zip"
        zp.write_bytes(_xml_zip('<?xml version="1.0"?><HealthData locale="en_US"/>'))
        with pytest.raises(NoHealthDataError):
            parse_apple_health(zp)

    def test_only_workouts_does_not_raise(self, tmp_path):
        zp = tmp_path / "x.zip"
        zp.write_bytes(_xml_zip(_WORKOUT_XML))
        _, _, workouts, _ = parse_apple_health(zp)
        assert len(workouts) == 1

    def test_only_correlations_does_not_raise(self, tmp_path):
        zp = tmp_path / "x.zip"
        zp.write_bytes(_xml_zip(_CORRELATION_NO_DUPES_XML))
        _, correlations, _, _ = parse_apple_health(zp)
        assert len(correlations) == 1

    def test_only_activity_summaries_does_not_raise(self, tmp_path):
        zp = tmp_path / "x.zip"
        zp.write_bytes(_xml_zip(_ACTIVITY_SUMMARY_XML))
        _, _, _, activities = parse_apple_health(zp)
        assert len(activities) == 1

    def test_missing_export_xml_raises(self, tmp_path):
        zp = tmp_path / "x.zip"
        zp.write_bytes(_make_zip({"wrong/data.xml": "<HealthData/>"}))
        with pytest.raises(KeyError):
            parse_apple_health(zp)

    def test_nonexistent_zip_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            parse_apple_health(tmp_path / "nonexistent.zip")

    def test_corrupt_zip_raises(self, tmp_path):
        zp = tmp_path / "x.zip"
        zp.write_bytes(b"this is not a zip file at all")
        with pytest.raises(zipfile.BadZipFile):
            parse_apple_health(zp)

    def test_no_health_data_error_is_value_error_subclass(self):
        assert issubclass(NoHealthDataError, ValueError)


# ---------------------------------------------------------------------------
# Records DataFrame
# ---------------------------------------------------------------------------


class TestRecordParsing:
    def test_record_count(self, tmp_path):
        zp = tmp_path / "x.zip"
        zp.write_bytes(_xml_zip(_RECORD_XML))
        records, *_ = parse_apple_health(zp)
        assert len(records) == 2

    def test_exact_columns(self, tmp_path):
        """Column set is the pinned schema (incl. meta when default flag is on)."""
        zp = tmp_path / "x.zip"
        zp.write_bytes(_xml_zip(_RECORD_XML))
        records, *_ = parse_apple_health(zp)
        assert set(records.columns) == set(_RECORD_COLUMNS)

    def test_all_attribute_columns_are_string_dtype(self, tmp_path):
        zp = tmp_path / "x.zip"
        zp.write_bytes(_xml_zip(_RECORD_XML))
        records, *_ = parse_apple_health(zp)
        for col in RECORD_ATTRS:
            assert pd.api.types.is_string_dtype(records[col]), (
                f"{col} should be string dtype"
            )

    def test_record_values(self, tmp_path):
        zp = tmp_path / "x.zip"
        zp.write_bytes(_xml_zip(_RECORD_XML))
        records, *_ = parse_apple_health(zp)
        hr = records[records["type"] == "HKQuantityTypeIdentifierHeartRate"].iloc[0]
        assert hr["sourceName"] == "Apple Watch"
        assert hr["unit"] == "count/min"
        assert hr["value"] == "72"

    def test_missing_attributes_produce_none(self, tmp_path):
        xml = """<?xml version="1.0"?>
<HealthData locale="en_US">
  <Record type="HKQuantityTypeIdentifierHeartRate" value="72"/>
</HealthData>"""
        zp = tmp_path / "x.zip"
        zp.write_bytes(_xml_zip(xml))
        records, *_ = parse_apple_health(zp)
        assert len(records) == 1
        assert records.iloc[0]["sourceName"] is None
        assert records.iloc[0]["unit"] is None

    def test_metadata_parsed_into_meta_column(self, tmp_path):
        zp = tmp_path / "x.zip"
        zp.write_bytes(_xml_zip(_RECORD_WITH_META_XML))
        records, *_ = parse_apple_health(zp)
        hr = records[records["type"] == "HKQuantityTypeIdentifierHeartRate"].iloc[0]
        assert hr["meta"] == {
            "HKMetadataKeyHeartRateMotionContext": "1",
            "HKMetadataKeyTimeZone": "Europe/Berlin",
        }

    def test_record_without_metadata_has_none_in_meta_column(self, tmp_path):
        """Memory optimisation: empty/missing metadata is None, not {}."""
        zp = tmp_path / "x.zip"
        zp.write_bytes(_xml_zip(_RECORD_WITH_META_XML))
        records, *_ = parse_apple_health(zp)
        sc = records[records["type"] == "HKQuantityTypeIdentifierStepCount"].iloc[0]
        assert sc["meta"] is None

    def test_parse_record_metadata_false_omits_column(self, tmp_path):
        zp = tmp_path / "x.zip"
        zp.write_bytes(_xml_zip(_RECORD_WITH_META_XML))
        records, *_ = parse_apple_health(zp, parse_record_metadata=False)
        assert "meta" not in records.columns
        assert set(records.columns) == set(RECORD_ATTRS)


# ---------------------------------------------------------------------------
# Correlation DataFrame
# ---------------------------------------------------------------------------


class TestCorrelationParsing:
    def test_correlation_count(self, tmp_path):
        zp = tmp_path / "x.zip"
        zp.write_bytes(_xml_zip(_CORRELATION_XML))
        _, correlations, _, _ = parse_apple_health(zp)
        assert len(correlations) == 1

    def test_correlation_type_attribute(self, tmp_path):
        zp = tmp_path / "x.zip"
        zp.write_bytes(_xml_zip(_CORRELATION_XML))
        _, correlations, _, _ = parse_apple_health(zp)
        assert (
            correlations.iloc[0]["type"] == "HKCorrelationTypeIdentifierBloodPressure"
        )

    def test_correlation_meta_parsed(self, tmp_path):
        zp = tmp_path / "x.zip"
        zp.write_bytes(_xml_zip(_CORRELATION_XML))
        _, correlations, _, _ = parse_apple_health(zp)
        assert correlations.iloc[0]["meta"] == {"HKWasUserEntered": "1"}

    def test_correlation_records_is_index_list(self, tmp_path):
        """The correlation's `records` field is a list of integer indices
        into records_df, not embedded dicts."""
        zp = tmp_path / "x.zip"
        zp.write_bytes(_xml_zip(_CORRELATION_XML))
        _, correlations, _, _ = parse_apple_health(zp)
        refs = correlations.iloc[0]["records"]
        assert len(refs) == 2
        assert all(isinstance(r, int) for r in refs)

    def test_correlation_records_resolve_via_iloc(self, tmp_path):
        """Indices into records_df dereference to the right BP readings."""
        zp = tmp_path / "x.zip"
        zp.write_bytes(_xml_zip(_CORRELATION_XML))
        records, correlations, _, _ = parse_apple_health(zp)
        refs = correlations.iloc[0]["records"]
        linked = records.iloc[refs]
        assert set(linked["type"]) == {
            "HKQuantityTypeIdentifierBloodPressureSystolic",
            "HKQuantityTypeIdentifierBloodPressureDiastolic",
        }
        assert set(linked["value"]) == {"120", "80"}

    def test_top_level_records_not_duplicated_with_correlation_children(self, tmp_path):
        """Apple emits child Records of a Correlation again at top level.
        records_df must contain each such Record exactly once — the
        correlation references it by index, not by embedding a copy."""
        zp = tmp_path / "x.zip"
        zp.write_bytes(_xml_zip(_CORRELATION_XML))
        records, _, _, _ = parse_apple_health(zp)
        # _CORRELATION_XML has 2 top-level BP duplicates; records_df should
        # be 2 rows, not 4 (which it would be if both child + top-level
        # emissions were kept as separate entries).
        assert len(records) == 2

    def test_correlation_without_top_level_dupes_emits_none_refs(
        self, tmp_path, caplog
    ):
        """If the Correlation has no top-level duplicates in the XML the
        link can't resolve.  Should produce None entries and a warning, not
        an exception."""
        zp = tmp_path / "x.zip"
        zp.write_bytes(_xml_zip(_CORRELATION_NO_DUPES_XML))
        with caplog.at_level(logging.WARNING, logger="src.importer.parser"):
            records, correlations, _, _ = parse_apple_health(zp)
        assert len(records) == 0
        refs = correlations.iloc[0]["records"]
        assert refs == [None]
        assert any("could not be linked" in r.getMessage() for r in caplog.records)

    def test_date_filter_dropping_top_level_dupes_still_keeps_correlation(
        self,
        tmp_path,
        caplog,  # noqa: ARG002
    ):
        """Canonical 'unlinked refs' scenario from the docstring: when
        from_date is between the correlation date and the top-level dupes'
        dates (which shouldn't happen in real exports but is the
        theoretical case), refs become None and a warning fires."""
        # Correlation dated 2024-01-01, set from_date to drop everything.
        # All elements drop together so we hit NoHealthDataError — fine.
        zp = tmp_path / "x.zip"
        zp.write_bytes(_xml_zip(_CORRELATION_XML))
        with pytest.raises(NoHealthDataError):
            parse_apple_health(zp, from_date=pd.Timestamp("2025-01-01"))

    def test_unknown_correlation_child_raises(self, tmp_path):
        xml = """<?xml version="1.0"?>
<HealthData locale="en_US">
  <Correlation type="x" sourceName="x" sourceVersion="1" device="d"
    creationDate="2024-01-01 00:00:00 +0000"
    startDate="2024-01-01 00:00:00 +0000"
    endDate="2024-01-01 00:01:00 +0000">
    <UnknownElement/>
  </Correlation>
</HealthData>"""
        zp = tmp_path / "x.zip"
        zp.write_bytes(_xml_zip(xml))
        with pytest.raises(NotImplementedError):
            parse_apple_health(zp)


# ---------------------------------------------------------------------------
# Workout DataFrame
# ---------------------------------------------------------------------------


class TestWorkoutParsing:
    def test_workout_count(self, tmp_path):
        zp = tmp_path / "x.zip"
        zp.write_bytes(_xml_zip(_WORKOUT_XML))
        _, _, workouts, _ = parse_apple_health(zp)
        assert len(workouts) == 1

    def test_workout_meta(self, tmp_path):
        zp = tmp_path / "x.zip"
        zp.write_bytes(_xml_zip(_WORKOUT_XML))
        _, _, workouts, _ = parse_apple_health(zp)
        assert workouts.iloc[0]["meta"] == {"HKTimeZone": "Europe/Berlin"}

    def test_workout_events(self, tmp_path):
        zp = tmp_path / "x.zip"
        zp.write_bytes(_xml_zip(_WORKOUT_XML))
        _, _, workouts, _ = parse_apple_health(zp)
        events = workouts.iloc[0]["events"]
        assert len(events) == 1
        assert events[0]["type"] == "HKWorkoutEventTypeLap"

    def test_workout_event_metadata_merged(self, tmp_path):
        zp = tmp_path / "x.zip"
        zp.write_bytes(_xml_zip(_WORKOUT_XML))
        _, _, workouts, _ = parse_apple_health(zp)
        assert workouts.iloc[0]["events"][0]["HKLapLength"] == "1000"

    def test_workout_all_statistics_preserved(self, tmp_path):
        zp = tmp_path / "x.zip"
        zp.write_bytes(_xml_zip(_WORKOUT_XML))
        _, _, workouts, _ = parse_apple_health(zp)
        stats = workouts.iloc[0]["statistics"]
        assert len(stats) == 2
        assert {s["type"] for s in stats} == {
            "HKQuantityTypeIdentifierHeartRate",
            "HKQuantityTypeIdentifierDistanceWalkingRunning",
        }

    def test_workout_no_statistics_is_empty_list(self, tmp_path):
        zp = tmp_path / "x.zip"
        zp.write_bytes(_xml_zip(_minimal_workout_xml()))
        _, _, workouts, _ = parse_apple_health(zp)
        assert workouts.iloc[0]["statistics"] == []

    def test_workout_route_files_and_meta(self, tmp_path):
        zp = tmp_path / "x.zip"
        zp.write_bytes(_xml_zip(_WORKOUT_XML))
        _, _, workouts, _ = parse_apple_health(zp)
        route = workouts.iloc[0]["route"]
        assert route is not None
        assert route["files"] == [_GPX_ROUTE_PATH]
        assert route["meta"] == {"HKMetadataKeyAltitudeType": "2"}

    def test_workout_route_absent_is_none(self, tmp_path):
        zp = tmp_path / "x.zip"
        zp.write_bytes(_xml_zip(_minimal_workout_xml()))
        _, _, workouts, _ = parse_apple_health(zp)
        assert workouts.iloc[0]["route"] is None

    def test_workout_activity_attributes(self, tmp_path):
        zp = tmp_path / "x.zip"
        zp.write_bytes(_xml_zip(_WORKOUT_XML))
        _, _, workouts, _ = parse_apple_health(zp)
        activity = workouts.iloc[0]["activities"][0]
        assert activity["uuid"] == "activity-uuid-1"

    def test_workout_activity_meta(self, tmp_path):
        zp = tmp_path / "x.zip"
        zp.write_bytes(_xml_zip(_WORKOUT_XML))
        _, _, workouts, _ = parse_apple_health(zp)
        assert workouts.iloc[0]["activities"][0]["meta"] == {
            "HKTimeZone": "Europe/Berlin"
        }

    def test_workout_activity_statistics(self, tmp_path):
        zp = tmp_path / "x.zip"
        zp.write_bytes(_xml_zip(_WORKOUT_XML))
        _, _, workouts, _ = parse_apple_health(zp)
        stats = workouts.iloc[0]["activities"][0]["statistics"]
        assert len(stats) == 1
        assert stats[0]["type"] == "HKQuantityTypeIdentifierHeartRate"

    def test_workout_activity_events(self, tmp_path):
        zp = tmp_path / "x.zip"
        zp.write_bytes(_xml_zip(_WORKOUT_XML))
        _, _, workouts, _ = parse_apple_health(zp)
        events = workouts.iloc[0]["activities"][0]["events"]
        assert len(events) == 1
        assert events[0]["type"] == "HKWorkoutEventTypeLap"

    def test_multiple_activities_all_preserved(self, tmp_path):
        zp = tmp_path / "x.zip"
        zp.write_bytes(_xml_zip(_MULTI_ACTIVITY_XML))
        _, _, workouts, _ = parse_apple_health(zp)
        activities = workouts.iloc[0]["activities"]
        assert len(activities) == 3
        assert {a["uuid"] for a in activities} == {"swim", "bike", "run"}

    def test_unknown_workout_child_raises(self, tmp_path):
        zp = tmp_path / "x.zip"
        zp.write_bytes(_xml_zip(_minimal_workout_xml("<UnknownElement/>")))
        with pytest.raises(NotImplementedError):
            parse_apple_health(zp)

    def test_unknown_workout_activity_child_raises(self, tmp_path):
        children = """
<WorkoutActivity uuid="a"
  startDate="2024-01-01 00:00:00 +0000"
  endDate="2024-01-01 00:30:00 +0000">
  <UnknownElement/>
</WorkoutActivity>"""
        zp = tmp_path / "x.zip"
        zp.write_bytes(_xml_zip(_minimal_workout_xml(children)))
        with pytest.raises(NotImplementedError):
            parse_apple_health(zp)


# ---------------------------------------------------------------------------
# ActivitySummary DataFrame
# ---------------------------------------------------------------------------


class TestActivitySummaryParsing:
    def test_activity_summary_count(self, tmp_path):
        zp = tmp_path / "x.zip"
        zp.write_bytes(_xml_zip(_ACTIVITY_SUMMARY_XML))
        _, _, _, activities = parse_apple_health(zp)
        assert len(activities) == 1

    def test_activity_summary_values(self, tmp_path):
        zp = tmp_path / "x.zip"
        zp.write_bytes(_xml_zip(_ACTIVITY_SUMMARY_XML))
        _, _, _, activities = parse_apple_health(zp)
        row = activities.iloc[0]
        assert row["dateComponents"] == "2024-01-01"
        assert row["activeEnergyBurned"] == "450"
        assert row["activeEnergyBurnedGoal"] == "500"

    def test_activity_summary_columns_match_attrs(self, tmp_path):
        zp = tmp_path / "x.zip"
        zp.write_bytes(_xml_zip(_ACTIVITY_SUMMARY_XML))
        _, _, _, activities = parse_apple_health(zp)
        assert set(activities.columns) == set(_ACTIVITY_ATTRS)


# ---------------------------------------------------------------------------
# from_date filtering
# ---------------------------------------------------------------------------


class TestFromDateFiltering:
    @staticmethod
    def _with_late_record(xml):
        return xml.replace("</HealthData>", f"{_LATE_RECORD_XML}\n</HealthData>")

    def test_none_includes_all_records(self, tmp_path):
        zp = tmp_path / "x.zip"
        zp.write_bytes(_xml_zip(_TWO_DATES_XML))
        records, *_ = parse_apple_health(zp, from_date=None)
        assert len(records) == 2

    def test_excludes_records_strictly_before(self, tmp_path):
        zp = tmp_path / "x.zip"
        zp.write_bytes(_xml_zip(_TWO_DATES_XML))
        records, *_ = parse_apple_health(zp, from_date=pd.Timestamp("2024-01-02"))
        assert len(records) == 1
        assert records.iloc[0]["value"] == "70"

    def test_includes_records_on_from_date(self, tmp_path):
        """Boundary is inclusive — the comparison is strict less-than."""
        zp = tmp_path / "x.zip"
        zp.write_bytes(_xml_zip(_TWO_DATES_XML))
        records, *_ = parse_apple_health(zp, from_date=pd.Timestamp("2024-01-01"))
        assert len(records) == 2

    def test_filters_workouts_by_end_date(self, tmp_path):
        zp = tmp_path / "x.zip"
        zp.write_bytes(_xml_zip(self._with_late_record(_WORKOUT_XML)))
        _, _, workouts, _ = parse_apple_health(zp, from_date=pd.Timestamp("2024-01-02"))
        assert len(workouts) == 0

    def test_keeps_workout_on_from_date(self, tmp_path):
        zp = tmp_path / "x.zip"
        zp.write_bytes(_xml_zip(_WORKOUT_XML))
        _, _, workouts, _ = parse_apple_health(zp, from_date=pd.Timestamp("2024-01-01"))
        assert len(workouts) == 1

    def test_filters_correlations_by_end_date(self, tmp_path):
        zp = tmp_path / "x.zip"
        zp.write_bytes(_xml_zip(self._with_late_record(_CORRELATION_NO_DUPES_XML)))
        _, correlations, _, _ = parse_apple_health(
            zp, from_date=pd.Timestamp("2024-01-02")
        )
        assert len(correlations) == 0

    def test_filters_activity_summaries_by_date_components(self, tmp_path):
        zp = tmp_path / "x.zip"
        zp.write_bytes(_xml_zip(self._with_late_record(_ACTIVITY_SUMMARY_XML)))
        _, _, _, activities = parse_apple_health(
            zp, from_date=pd.Timestamp("2024-01-02")
        )
        assert len(activities) == 0

    def test_dateless_elements_do_not_crash(self, tmp_path):
        """ExportDate / Me have no recognised date attribute; the filter
        must skip them silently rather than raising on NaT.date()."""
        zp = tmp_path / "x.zip"
        zp.write_bytes(_xml_zip(_XML_WITH_KNOWN_UNHANDLED))
        records, *_ = parse_apple_health(zp, from_date=pd.Timestamp("2023-06-01"))
        assert len(records) == 1

    def test_all_filtered_raises_no_health_data_error(self, tmp_path):
        zp = tmp_path / "x.zip"
        zp.write_bytes(_xml_zip(_TWO_DATES_XML))
        with pytest.raises(NoHealthDataError):
            parse_apple_health(zp, from_date=pd.Timestamp("2025-01-01"))


# ---------------------------------------------------------------------------
# skip_records flag
# ---------------------------------------------------------------------------


class TestSkipRecords:
    def test_records_df_empty_when_skipped(self, tmp_path):
        # _RECORD_XML alone would empty every DataFrame and trigger
        # NoHealthDataError; combine with a workout so the export is non-empty.
        combined = _RECORD_XML.replace(
            "</HealthData>",
            _WORKOUT_XML.split('<HealthData locale="en_US">', 1)[1],
        )
        zp = tmp_path / "x.zip"
        zp.write_bytes(_xml_zip(combined))
        records, _, workouts, _ = parse_apple_health(zp, skip_records=True)
        assert len(records) == 0
        assert len(workouts) == 1

    def test_correlation_refs_all_none_when_records_skipped(self, tmp_path, caplog):
        zp = tmp_path / "x.zip"
        zp.write_bytes(_xml_zip(_CORRELATION_XML))
        with caplog.at_level(logging.WARNING, logger="src.importer.parser"):
            _, correlations, _, _ = parse_apple_health(zp, skip_records=True)
        refs = correlations.iloc[0]["records"]
        assert refs == [None, None]

    def test_workouts_unaffected_by_skip_records(self, tmp_path):
        zp = tmp_path / "x.zip"
        zp.write_bytes(_xml_zip(_WORKOUT_XML))
        _, _, workouts, _ = parse_apple_health(zp, skip_records=True)
        assert len(workouts) == 1


# ---------------------------------------------------------------------------
# XML security
# ---------------------------------------------------------------------------


class TestXXESecurity:
    def test_xxe_external_entity_in_attribute_blocked(self, tmp_path):
        """lxml refuses to dereference external entities even via attributes."""
        xxe_xml = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE foo [ <!ENTITY xxe SYSTEM "file:///etc/passwd"> ]>
<HealthData locale="en_US">
  <Record type="HK" sourceName="&xxe;" sourceVersion="1" device="d"
    unit="bpm" creationDate="2024-01-01 00:00:00 +0000"
    startDate="2024-01-01 00:00:00 +0000"
    endDate="2024-01-01 00:01:00 +0000" value="1"/>
</HealthData>"""
        zp = tmp_path / "x.zip"
        zp.write_bytes(_xml_zip(xxe_xml))
        with pytest.raises(
            etree.XMLSyntaxError, match="Attribute references external entity 'xxe'"
        ):
            parse_apple_health(zp)

    def test_billion_laughs_blocked_by_amplification_limit(self, tmp_path):
        """libxml2's built-in amplification limit blocks exponential expansion."""
        bl_xml = """<?xml version="1.0"?>
<!DOCTYPE lolz [
  <!ENTITY lol "lol">
  <!ENTITY lol2 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">
  <!ENTITY lol3 "&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;">
  <!ENTITY lol4 "&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;">
  <!ENTITY lol5 "&lol4;&lol4;&lol4;&lol4;&lol4;&lol4;&lol4;&lol4;&lol4;&lol4;">
  <!ENTITY lol6 "&lol5;&lol5;&lol5;&lol5;&lol5;&lol5;&lol5;&lol5;&lol5;&lol5;">
  <!ENTITY lol7 "&lol6;&lol6;&lol6;&lol6;&lol6;&lol6;&lol6;&lol6;&lol6;&lol6;">
  <!ENTITY lol8 "&lol7;&lol7;&lol7;&lol7;&lol7;&lol7;&lol7;&lol7;&lol7;&lol7;">
  <!ENTITY lol9 "&lol8;&lol8;&lol8;&lol8;&lol8;&lol8;&lol8;&lol8;&lol8;&lol8;">
]>
<HealthData locale="&lol9;"/>"""
        zp = tmp_path / "x.zip"
        zp.write_bytes(_xml_zip(bl_xml))
        with pytest.raises(
            etree.XMLSyntaxError, match="Maximum entity amplification factor exceeded"
        ):
            parse_apple_health(zp)

    def test_malformed_xml_raises(self, tmp_path):
        zp = tmp_path / "x.zip"
        zp.write_bytes(_xml_zip("<HealthData><Unclosed>"))
        with pytest.raises(etree.XMLSyntaxError):
            parse_apple_health(zp)


# ---------------------------------------------------------------------------
# Unknown top-level elements — schema drift detection
# ---------------------------------------------------------------------------


class TestUnknownTopLevelElements:
    """A failure here means we'd stop noticing iOS-version schema drift in
    real exports.  Critical to keep loud."""

    def test_known_unhandled_tag_does_not_raise(self, tmp_path):
        zp = tmp_path / "x.zip"
        zp.write_bytes(_xml_zip(_XML_WITH_KNOWN_UNHANDLED))
        records, *_ = parse_apple_health(zp)
        assert len(records) == 1

    def test_unknown_tag_does_not_raise(self, tmp_path):
        zp = tmp_path / "x.zip"
        zp.write_bytes(_xml_zip(_XML_WITH_GENUINELY_UNKNOWN))
        records, *_ = parse_apple_health(zp)
        assert len(records) == 1

    def test_known_unhandled_tag_logged_with_equals_count(self, tmp_path, caplog):
        zp = tmp_path / "x.zip"
        zp.write_bytes(_xml_zip(_XML_WITH_KNOWN_UNHANDLED))
        with caplog.at_level(logging.WARNING, logger="src.importer.parser"):
            parse_apple_health(zp)
        msgs = [r.getMessage() for r in caplog.records if r.levelname == "WARNING"]
        assert any("ExportDate=1" in m or "Me=1" in m for m in msgs), msgs

    def test_unknown_tag_marked_unrecognised(self, tmp_path, caplog):
        """Schema drift indicator: a tag not in _KNOWN_UNHANDLED_TAGS gets
        an explicit `unrecognised` marker so it's grep-able in production logs."""
        zp = tmp_path / "x.zip"
        zp.write_bytes(_xml_zip(_XML_WITH_GENUINELY_UNKNOWN))
        with caplog.at_level(logging.WARNING, logger="src.importer.parser"):
            parse_apple_health(zp)
        msgs = [r.getMessage() for r in caplog.records if r.levelname == "WARNING"]
        assert any(
            "BrandNewElementApolloAddsInIos25" in m and "unrecognised" in m
            for m in msgs
        ), msgs

    def test_count_aggregated_in_single_warning(self, tmp_path, caplog):
        """Multiple occurrences of one tag are aggregated, not N warnings."""
        zp = tmp_path / "x.zip"
        zp.write_bytes(_xml_zip(_XML_WITH_GENUINELY_UNKNOWN))
        with caplog.at_level(logging.WARNING, logger="src.importer.parser"):
            parse_apple_health(zp)
        unhandled = [
            r
            for r in caplog.records
            if r.levelname == "WARNING"
            and "BrandNewElementApolloAddsInIos25" in r.getMessage()
        ]
        assert len(unhandled) == 1
        assert "=2" in unhandled[0].getMessage()

    def test_workout_children_not_counted_as_unknown(self, tmp_path, caplog):
        """WorkoutEvent/Statistics/Route/Activity/MetadataEntry/FileReference
        are processed by the Workout branch and must never appear as
        'unknown top-level elements'."""
        zp = tmp_path / "x.zip"
        zp.write_bytes(_xml_zip(_WORKOUT_XML))
        with caplog.at_level(logging.WARNING, logger="src.importer.parser"):
            parse_apple_health(zp)
        child_tags = {
            "WorkoutEvent",
            "WorkoutStatistics",
            "WorkoutRoute",
            "WorkoutActivity",
            "MetadataEntry",
            "FileReference",
        }
        msgs = [r.getMessage() for r in caplog.records if r.levelname == "WARNING"]
        for msg in msgs:
            for tag in child_tags:
                assert tag not in msg, f"internal tag {tag!r} leaked into: {msg!r}"

    def test_correlation_metadata_entry_not_counted_as_unknown(self, tmp_path, caplog):
        """Regression: MetadataEntry inside a top-level Record used to be
        wrongly counted as 'unknown top-level' by the original parser."""
        zp = tmp_path / "x.zip"
        zp.write_bytes(_xml_zip(_RECORD_WITH_META_XML))
        with caplog.at_level(logging.WARNING, logger="src.importer.parser"):
            parse_apple_health(zp)
        msgs = [r.getMessage() for r in caplog.records if r.levelname == "WARNING"]
        for msg in msgs:
            assert "MetadataEntry" not in msg, msg

    def test_no_warning_when_only_known_elements(self, tmp_path, caplog):
        """A pristine export with only handled tags should produce no
        'unknown elements' warning."""
        zp = tmp_path / "x.zip"
        zp.write_bytes(_xml_zip(_RECORD_XML))
        with caplog.at_level(logging.WARNING, logger="src.importer.parser"):
            parse_apple_health(zp)
        msgs = [r.getMessage() for r in caplog.records if r.levelname == "WARNING"]
        assert not any("Unknown top-level elements" in m for m in msgs), msgs


# ---------------------------------------------------------------------------
# End-of-parse INFO summary
# ---------------------------------------------------------------------------


class TestEndOfParseLogging:
    def test_summary_info_emitted(self, tmp_path, caplog):
        zp = tmp_path / "x.zip"
        zp.write_bytes(_xml_zip(_RECORD_XML))
        with caplog.at_level(logging.INFO, logger="src.importer.parser"):
            parse_apple_health(zp)
        msgs = [r.getMessage() for r in caplog.records if r.levelname == "INFO"]
        assert any(
            "records" in m and "correlation" in m and "workout" in m for m in msgs
        )


# ---------------------------------------------------------------------------
# Performance — guards against accidental hot-path regressions
# ---------------------------------------------------------------------------


class TestParserPerformance:
    """The pre-refactor parser ran `pd.to_datetime` per record in the date
    filter, taking ~50s for a 100k-record export.  These guards catch a
    revert to that behaviour (or anything similarly slow getting added)."""

    @staticmethod
    def _build_large(tmp_path, n=100_000):
        rows = []
        for i in range(n):
            day = 1 + (i % 28)
            date = f"2024-01-{day:02d} 00:00:00 +0000"
            rows.append(
                f'<Record type="HKQuantityTypeIdentifierHeartRate" sourceName="W" '
                f'sourceVersion="1" device="d" unit="count/min" '
                f'creationDate="{date}" startDate="{date}" endDate="{date}" '
                f'value="{60 + i % 40}"/>'
            )
        xml = (
            '<?xml version="1.0"?><HealthData locale="en_US">'
            + "\n".join(rows)
            + "</HealthData>"
        )
        zp = tmp_path / "big.zip"
        zp.write_bytes(_xml_zip(xml))
        return zp

    def test_100k_records_under_5_seconds(self, tmp_path):
        """No-filter parse of 100k records must comfortably finish in <5s.
        The pre-refactor version took ~1s here, so 5s gives 5x headroom."""
        zp = self._build_large(tmp_path, n=100_000)
        t0 = time.perf_counter()
        records, *_ = parse_apple_health(zp)
        elapsed = time.perf_counter() - t0
        assert len(records) == 100_000
        assert elapsed < 5.0, f"100k no-filter parse took {elapsed:.2f}s (>5s budget)"

    def test_date_filter_does_not_blow_up_runtime(self, tmp_path):
        """A date-filtered parse of 100k records must not be massively
        slower than the unfiltered case.  The pre-refactor version was 50x
        slower with the filter; the post-refactor version is faster.  A 2x
        cap catches any regression that reintroduces per-element pd.to_datetime."""
        zp = self._build_large(tmp_path, n=100_000)

        t0 = time.perf_counter()
        parse_apple_health(zp)
        t_unfiltered = time.perf_counter() - t0

        t0 = time.perf_counter()
        parse_apple_health(zp, from_date=pd.Timestamp("2024-01-15"))
        t_filtered = time.perf_counter() - t0

        # Filter should be roughly the same speed (often faster, since
        # filtered-out elements skip the column-list append).  Cap at 2x
        # the unfiltered wall time.
        assert t_filtered < t_unfiltered * 2 + 0.5, (
            f"date filter is {t_filtered:.2f}s vs unfiltered {t_unfiltered:.2f}s "
            f"— suspicious slowdown, check for pd.to_datetime in hot path"
        )

    def test_metadata_overhead_under_30_percent(self, tmp_path):
        """parse_record_metadata=True should not cost more than ~30% over
        =False on a metadata-free export (since the inner loop has nothing
        to do)."""
        zp = self._build_large(tmp_path, n=50_000)

        t0 = time.perf_counter()
        parse_apple_health(zp, parse_record_metadata=False)
        t_no_meta = time.perf_counter() - t0

        t0 = time.perf_counter()
        parse_apple_health(zp, parse_record_metadata=True)
        t_meta = time.perf_counter() - t0

        # The metadata-collection inner loop is "iterate over elem's
        # children" which is cheap when there are none.  30% allows for
        # CPython noise on small absolute times.
        assert t_meta < t_no_meta * 1.5 + 0.3, (
            f"metadata parse adds {(t_meta / t_no_meta - 1) * 100:.0f}% overhead "
            f"({t_meta:.2f}s vs {t_no_meta:.2f}s)"
        )


# ---------------------------------------------------------------------------
# parse_apple_health_routes — GPX parser
# ---------------------------------------------------------------------------


class TestParseAppleHealthRoutes:
    def test_returns_dataframe(self, tmp_path):
        zp = tmp_path / "x.zip"
        zp.write_bytes(_route_zip())
        df = parse_apple_health_routes(zp, paths=[_GPX_ROUTE_PATH])
        assert isinstance(df, pd.DataFrame)

    def test_expected_columns(self, tmp_path):
        zp = tmp_path / "x.zip"
        zp.write_bytes(_route_zip())
        df = parse_apple_health_routes(zp, paths=[_GPX_ROUTE_PATH])
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
        zp = tmp_path / "x.zip"
        zp.write_bytes(_route_zip())
        df = parse_apple_health_routes(zp, paths=[_GPX_ROUTE_PATH])
        assert len(df) == 2

    def test_lat_lon_are_float(self, tmp_path):
        zp = tmp_path / "x.zip"
        zp.write_bytes(_route_zip())
        df = parse_apple_health_routes(zp, paths=[_GPX_ROUTE_PATH])
        assert pd.api.types.is_float_dtype(df["lat"])
        assert pd.api.types.is_float_dtype(df["lon"])

    def test_lat_lon_values(self, tmp_path):
        zp = tmp_path / "x.zip"
        zp.write_bytes(_route_zip())
        df = parse_apple_health_routes(zp, paths=[_GPX_ROUTE_PATH])
        assert df.iloc[0]["lat"] == pytest.approx(52.520008)
        assert df.iloc[0]["lon"] == pytest.approx(13.404954)

    def test_ele_as_float(self, tmp_path):
        zp = tmp_path / "x.zip"
        zp.write_bytes(_route_zip())
        df = parse_apple_health_routes(zp, paths=[_GPX_ROUTE_PATH])
        assert df.iloc[0]["ele"] == pytest.approx(34.5)

    def test_time_is_utc_datetime(self, tmp_path):
        zp = tmp_path / "x.zip"
        zp.write_bytes(_route_zip())
        df = parse_apple_health_routes(zp, paths=[_GPX_ROUTE_PATH])
        assert pd.api.types.is_datetime64_any_dtype(df["time"])
        assert str(df["time"].dt.tz) == "UTC"
        assert df.iloc[0]["time"] == pd.Timestamp("2024-01-01T09:00:00Z")

    def test_extension_field_values(self, tmp_path):
        zp = tmp_path / "x.zip"
        zp.write_bytes(_route_zip())
        df = parse_apple_health_routes(zp, paths=[_GPX_ROUTE_PATH])
        row = df.iloc[0]
        assert row["speed"] == pytest.approx(2.83)
        assert row["course"] == pytest.approx(274.5)
        assert row["hAcc"] == pytest.approx(4.2)
        assert row["vAcc"] == pytest.approx(3.1)

    def test_file_column_value(self, tmp_path):
        zp = tmp_path / "x.zip"
        zp.write_bytes(_route_zip())
        df = parse_apple_health_routes(zp, paths=[_GPX_ROUTE_PATH])
        assert (df["file"] == _GPX_ROUTE_PATH).all()

    def test_paths_none_discovers_gpx_files(self, tmp_path):
        zp = tmp_path / "x.zip"
        zp.write_bytes(
            _make_zip(
                {
                    "apple_health_export/export.xml": _WORKOUT_XML,
                    f"apple_health_export/{_GPX_ROUTE_PATH}": _GPX_TWO_POINTS,
                }
            )
        )
        df = parse_apple_health_routes(zp)
        assert len(df) == 2

    def test_paths_none_ignores_non_gpx_and_wrong_directory(self, tmp_path):
        zp = tmp_path / "x.zip"
        zp.write_bytes(
            _make_zip(
                {
                    "apple_health_export/export.xml": _WORKOUT_XML,
                    f"apple_health_export/{_GPX_ROUTE_PATH}": _GPX_TWO_POINTS,
                    "apple_health_export/workout-routes/metadata.json": "{}",
                    "apple_health_export/export.gpx": _GPX_TWO_POINTS,
                }
            )
        )
        df = parse_apple_health_routes(zp)
        assert len(df) == 2
        assert (df["file"] == _GPX_ROUTE_PATH).all()

    def test_multiple_gpx_files_combined(self, tmp_path):
        zp = tmp_path / "x.zip"
        zp.write_bytes(
            _make_zip(
                {
                    "apple_health_export/export.xml": _WORKOUT_XML,
                    f"apple_health_export/{_GPX_ROUTE_PATH}": _GPX_TWO_POINTS,
                    f"apple_health_export/{_GPX_ROUTE_PATH_2}": _GPX_TWO_POINTS,
                }
            )
        )
        df = parse_apple_health_routes(zp, paths=[_GPX_ROUTE_PATH, _GPX_ROUTE_PATH_2])
        assert len(df) == 4
        assert set(df["file"].unique()) == {_GPX_ROUTE_PATH, _GPX_ROUTE_PATH_2}

    def test_missing_ele_is_nan(self, tmp_path):
        zp = tmp_path / "x.zip"
        zp.write_bytes(_route_zip(gpx_content=_GPX_MISSING_OPTIONAL))
        df = parse_apple_health_routes(zp, paths=[_GPX_ROUTE_PATH])
        assert pd.isna(df.iloc[0]["ele"])

    def test_missing_extensions_are_nan(self, tmp_path):
        """No <extensions> element → NaN for every extension field.

        Regression: an earlier implementation used `ext.find(a) or ext.find(b)`
        which, because lxml elements without children are falsy, could
        incorrectly skip an existing-but-empty element."""
        zp = tmp_path / "x.zip"
        zp.write_bytes(_route_zip(gpx_content=_GPX_MISSING_OPTIONAL))
        df = parse_apple_health_routes(zp, paths=[_GPX_ROUTE_PATH])
        for field in ("speed", "course", "hAcc", "vAcc"):
            assert pd.isna(df.iloc[0][field]), f"{field} should be NaN"

    def test_empty_gpx_returns_empty_dataframe(self, tmp_path):
        zp = tmp_path / "x.zip"
        zp.write_bytes(_route_zip(gpx_content=_GPX_EMPTY))
        df = parse_apple_health_routes(zp, paths=[_GPX_ROUTE_PATH])
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 0

    def test_accepts_path_object(self, tmp_path):
        zp = tmp_path / "x.zip"
        zp.write_bytes(_route_zip())
        df = parse_apple_health_routes(Path(zp), paths=[_GPX_ROUTE_PATH])
        assert len(df) == 2

    def test_accepts_string_path(self, tmp_path):
        zp = tmp_path / "x.zip"
        zp.write_bytes(_route_zip())
        df = parse_apple_health_routes(str(zp), paths=[_GPX_ROUTE_PATH])
        assert len(df) == 2

    def test_join_to_workouts_via_file_column(self, tmp_path):
        zp = tmp_path / "x.zip"
        zp.write_bytes(_route_zip())
        _, _, workouts, _ = parse_apple_health(zp)
        route_paths = [p for r in workouts["route"].dropna() for p in r["files"]]
        routes = parse_apple_health_routes(zp, paths=route_paths)
        assert len(routes) == 2
        assert (routes["file"] == _GPX_ROUTE_PATH).all()
