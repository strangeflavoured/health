"""Tests for src/importer/parser.py — XML parsing and security (XXE, zip-slip)."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pandas as pd
import pytest

from src.importer.parser import parse_apple_health, NoHealthDataError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_VALID_XML = """<?xml version="1.0" encoding="UTF-8"?>
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


def _make_zip(
    xml_content: str, filename: str = "apple_health_export/export.xml"
) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(filename, xml_content)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Basic functionality
# ---------------------------------------------------------------------------


class TestParseAppleHealth:
    def test_returns_dataframe(self, tmp_path):
        zip_path = tmp_path / "export.zip"
        zip_path.write_bytes(_make_zip(_VALID_XML))
        df = parse_apple_health(zip_path)
        assert isinstance(df, pd.DataFrame)

    def test_correct_row_count(self, tmp_path):
        zip_path = tmp_path / "export.zip"
        zip_path.write_bytes(_make_zip(_VALID_XML))
        df = parse_apple_health(zip_path)
        assert len(df) == 2

    def test_expected_columns_present(self, tmp_path):
        zip_path = tmp_path / "export.zip"
        zip_path.write_bytes(_make_zip(_VALID_XML))
        df = parse_apple_health(zip_path)
        for col in (
            "type",
            "sourceName",
            "unit",
            "value",
            "startDate",
            "endDate",
            "creationDate",
        ):
            assert col in df.columns

    def test_accepts_path_object(self, tmp_path):
        zip_path = tmp_path / "export.zip"
        zip_path.write_bytes(_make_zip(_VALID_XML))
        df = parse_apple_health(Path(zip_path))
        assert len(df) == 2

    def test_accepts_string_path(self, tmp_path):
        zip_path = tmp_path / "export.zip"
        zip_path.write_bytes(_make_zip(_VALID_XML))
        df = parse_apple_health(str(zip_path))
        assert len(df) == 2

    def test_empty_health_data(self, tmp_path):
        xml = '<?xml version="1.0"?><HealthData locale="en_US"></HealthData>'
        zip_path = tmp_path / "export.zip"
        zip_path.write_bytes(_make_zip(xml))
        with pytest.raises(NoHealthDataError):
            parse_apple_health(zip_path)

    def test_missing_export_xml_raises(self, tmp_path):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("wrong_path/data.xml", "<HealthData/>")
        zip_path = tmp_path / "export.zip"
        zip_path.write_bytes(buf.getvalue())
        with pytest.raises(KeyError):
            parse_apple_health(zip_path)

    def test_nonexistent_zip_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            parse_apple_health(tmp_path / "nonexistent.zip")


# ---------------------------------------------------------------------------
# Security: XXE prevention
# ---------------------------------------------------------------------------


class TestXXESecurity:
    def test_xxe_entity_expansion_blocked(self, tmp_path):
        """defusedxml must block DOCTYPE/ENTITY XXE attacks."""
        xxe_xml = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE foo [
  <!ENTITY xxe SYSTEM "file:///etc/passwd">
]>
<HealthData locale="en_US">
  <Record type="HK" sourceName="&xxe;" sourceVersion="1"
    device="d" unit="bpm"
    creationDate="2024-01-01 00:00:00 +0000"
    startDate="2024-01-01 00:00:00 +0000"
    endDate="2024-01-01 00:01:00 +0000" value="1"/>
</HealthData>
"""
        zip_path = tmp_path / "export.zip"
        zip_path.write_bytes(_make_zip(xxe_xml))
        with pytest.raises(Exception):
            parse_apple_health(zip_path)

    def test_billion_laughs_blocked(self, tmp_path):
        """defusedxml must block entity expansion DoS attacks."""
        bl_xml = """<?xml version="1.0"?>
<!DOCTYPE lolz [
  <!ENTITY lol "lol">
  <!ENTITY lol2 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">
  <!ENTITY lol3 "&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;">
]>
<HealthData locale="en_US">&lol3;</HealthData>
"""
        zip_path = tmp_path / "export.zip"
        zip_path.write_bytes(_make_zip(bl_xml))
        with pytest.raises(Exception):
            parse_apple_health(zip_path)

    def test_malformed_xml_raises(self, tmp_path):
        zip_path = tmp_path / "export.zip"
        zip_path.write_bytes(_make_zip("<HealthData><Unclosed>"))
        with pytest.raises(Exception):
            parse_apple_health(zip_path)


# ---------------------------------------------------------------------------
# Large export performance
# ---------------------------------------------------------------------------


class TestParserPerformance:
    def test_large_export_under_time_limit(self, tmp_path):
        import time

        n = 100_000
        records = "\n".join(
            f'<Record type="HKQuantityTypeIdentifierHeartRate" sourceName="Watch" '
            f'sourceVersion="1" device="d" unit="count/min" '
            f'creationDate="2024-01-01 00:00:00 +0000" '
            f'startDate="2024-01-{1 + ((n // 60) // 60) // 24:02d} {((i // 60) // 60) % 24:02d}:{(i // 60) % 60:02d}:{i % 60:02d} +0000" '
            f'endDate="2024-01-{1 + ((n // 60) // 60) // 24:02d} {((i // 60) // 60) % 24:02d}:{(i // 60) % 60:02d}:{i % 60:02d} +0000" '
            f'value="{60 + i % 40}"/>'
            for i in range(n)
        )
        xml = f'<?xml version="1.0"?><HealthData locale="en_US">{records}</HealthData>'
        zip_path = tmp_path / "export.zip"
        zip_path.write_bytes(_make_zip(xml))
        start = time.perf_counter()
        df = parse_apple_health(zip_path)
        elapsed = time.perf_counter() - start
        assert len(df) == n
        assert elapsed < 30.0
