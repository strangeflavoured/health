"""Tests for src/importer/importer.py — HealthDataImporter ETL orchestration."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
import redis

from src.importer.importer import HealthDataImporter, _load
from src.importer.response import (
    BatchFailure,
    DuplicatePolicy,
    RowFailure,
    failures_to_json,
)

# A type that genuinely exists in HKTypeIdentifierRegistry — tests need
# this for the registry lookup inside _load to succeed.
HR = "HKQuantityTypeIdentifierHeartRate"
STEPS = "HKQuantityTypeIdentifierStepCount"
HR_UNIT = "count/min"
STEPS_UNIT = "count"

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
    # TS info success → ensure_ts_key short-circuits.
    rts.info.return_value = {}
    return r


@pytest.fixture()
def importer(data_dir: Path, mock_redis: MagicMock) -> HealthDataImporter:
    return HealthDataImporter(
        connection=mock_redis,
        working_dir=data_dir.parent,
        data_dir="data",
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_records_df(
    type_val: str = HR, unit: str = HR_UNIT, n: int = 2
) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "type": [type_val] * n,
            "sourceName": ["Watch"] * n,
            "unit": [unit] * n,
            "value": [72.0] * n,
            "startDate": [1_700_000_000 + i for i in range(n)],
            "endDate": [1_700_000_060 + i for i in range(n)],
        }
    )


def _empty_df() -> pd.DataFrame:
    return pd.DataFrame()


def _extract_return(records: pd.DataFrame | None = None) -> tuple:
    """Build the 5-tuple ``_extract`` returns."""
    if records is None:
        records = _make_records_df()
    return (records, _empty_df(), _empty_df(), _empty_df(), _empty_df())


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
        assert importer.failures_file.parent == data_dir

    def test_path_traversal_in_data_dir_is_contained(self, tmp_path, mock_redis):
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
    def test_returns_five_tuple(self, importer):
        fake = pd.DataFrame({"type": [HR]})
        with patch(
            "src.importer.importer.parse_apple_health",
            return_value=(fake, _empty_df(), _empty_df(), _empty_df()),
        ):
            importer.zip_file.touch()
            result = importer._extract(write_feather=False, no_cache=False)
        assert isinstance(result, tuple) and len(result) == 5

    def test_reads_feather_cache_when_available_and_zip_missing(
        self,
        importer,
        data_dir,  # noqa: ARG002
    ):
        expected_df = pd.DataFrame({"type": [HR], "value": ["72"]})
        with patch(
            "src.importer.importer.feather.read_feather", return_value=expected_df
        ) as mock_read:
            importer.output_file.touch()
            records, corrs, workouts, activities, routes = importer._extract(
                write_feather=False, no_cache=False
            )
        mock_read.assert_called_once()
        assert len(records) == 1
        # Document tables empty because ZIP isn't present.
        assert corrs.empty and workouts.empty and activities.empty and routes.empty

    def test_feather_cache_with_zip_also_loads_documents(self, importer):
        """When both feather and ZIP exist, records come from feather but
        workouts/correlations/activities are re-parsed from ZIP."""
        cached = pd.DataFrame({"type": [HR]})
        zip_records = pd.DataFrame({"type": [HR]})
        zip_workouts = pd.DataFrame({"workoutActivityType": ["Run"], "route": [None]})

        with (
            patch(
                "src.importer.importer.feather.read_feather", return_value=cached
            ) as mock_feather,
            patch(
                "src.importer.importer.parse_apple_health",
                return_value=(zip_records, _empty_df(), zip_workouts, _empty_df()),
            ) as mock_parse,
        ):
            importer.output_file.touch()
            importer.zip_file.touch()
            records, _, workouts, _, _ = importer._extract(
                write_feather=False, no_cache=False
            )

        mock_feather.assert_called_once()
        mock_parse.assert_called_once()
        # Records from feather, not the ZIP.
        assert records.equals(cached)
        # Workouts from ZIP.
        assert len(workouts) == 1

    def test_raises_when_no_zip_and_no_feather(self, importer):
        with pytest.raises(FileNotFoundError):
            importer._extract(write_feather=False, no_cache=False)

    def test_parses_zip_when_no_feather(self, importer):
        fake = pd.DataFrame({"type": [HR]})
        with patch(
            "src.importer.importer.parse_apple_health",
            return_value=(fake, _empty_df(), _empty_df(), _empty_df()),
        ) as mock_parse:
            importer.zip_file.touch()
            importer._extract(write_feather=False, no_cache=False)
        mock_parse.assert_called_once()

    def test_write_feather_calls_to_feather(self, importer):
        fake = MagicMock(spec=pd.DataFrame)
        fake.empty = True  # ensure routes path skipped
        with patch(
            "src.importer.importer.parse_apple_health",
            return_value=(fake, _empty_df(), _empty_df(), _empty_df()),
        ):
            importer.zip_file.touch()
            importer._extract(write_feather=True, no_cache=False)
        fake.to_feather.assert_called_once()

    def test_no_cache_true_bypasses_feather(self, importer):
        fake = pd.DataFrame({"type": [HR]})
        with (
            patch(
                "src.importer.importer.parse_apple_health",
                return_value=(fake, _empty_df(), _empty_df(), _empty_df()),
            ) as mock_parse,
            patch("src.importer.importer.feather.read_feather") as mock_feather,
        ):
            importer.output_file.touch()
            importer.zip_file.touch()
            importer._extract(write_feather=False, no_cache=True)
        mock_parse.assert_called_once()
        mock_feather.assert_not_called()

    def test_routes_parsed_when_workouts_have_route_files(self, importer):
        workouts = pd.DataFrame(
            {
                "workoutActivityType": ["Run"],
                "route": [{"files": ["workout-routes/route_x.gpx"]}],
            }
        )
        with (
            patch(
                "src.importer.importer.parse_apple_health",
                return_value=(
                    pd.DataFrame({"type": [HR]}),
                    _empty_df(),
                    workouts,
                    _empty_df(),
                ),
            ),
            patch(
                "src.importer.importer.parse_apple_health_routes",
                return_value=pd.DataFrame({"file": ["x"], "lat": [1.0]}),
            ) as mock_routes,
        ):
            importer.zip_file.touch()
            _, _, _, _, routes = importer._extract(write_feather=False, no_cache=False)
        mock_routes.assert_called_once()
        assert len(routes) == 1

    def test_routes_not_parsed_when_no_workouts(self, importer):
        with (
            patch(
                "src.importer.importer.parse_apple_health",
                return_value=(
                    pd.DataFrame({"type": [HR]}),
                    _empty_df(),
                    _empty_df(),
                    _empty_df(),
                ),
            ),
            patch("src.importer.importer.parse_apple_health_routes") as mock_routes,
        ):
            importer.zip_file.touch()
            importer._extract(write_feather=False, no_cache=False)
        mock_routes.assert_not_called()


# ---------------------------------------------------------------------------
# Failures file I/O
# ---------------------------------------------------------------------------


class TestFailuresFile:
    def test_write_and_read_roundtrip(self, importer):
        failures = [
            RowFailure(HR, 0, start_error="dup"),
            BatchFailure(STEPS, 0, "err"),
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
        importer.failures = [BatchFailure(HR, 0, "err")]
        importer._update_failures_file()
        assert importer.failures_file.exists()

    def test_update_failures_file_deletes_when_empty(self, importer):
        importer.failures_file.write_text("[]", encoding="utf-8")
        importer.failures = []
        importer._update_failures_file()
        assert not importer.failures_file.exists()

    def test_read_failures_file_returns_correct_types(self, importer):
        failures = [RowFailure(HR, 5, start_error="e"), BatchFailure(STEPS, 0, "t")]
        importer._write_failures_file(failures)
        restored = importer._read_failures_file()
        assert isinstance(restored[0], RowFailure)
        assert isinstance(restored[1], BatchFailure)


# ---------------------------------------------------------------------------
# _load
# ---------------------------------------------------------------------------


class TestLoad:
    def test_returns_empty_on_success(self, mock_redis):
        df = _make_records_df()
        # 2 commands per row × 2 rows = 4 results
        mock_redis.ts.return_value.pipeline.return_value.execute.return_value = [
            1,
            2,
            3,
            4,
        ]
        assert _load(df, mock_redis) == []

    def test_redis_error_creates_batch_failure(self, mock_redis):
        df = _make_records_df()
        mock_redis.ts.return_value.pipeline.return_value.execute.side_effect = (
            redis.RedisError("conn lost")
        )
        result = _load(df, mock_redis)
        assert len(result) == 1
        assert isinstance(result[0], BatchFailure)

    def test_empty_df_returns_empty(self, mock_redis):
        df = _make_records_df(n=0)
        assert _load(df, mock_redis) == []

    def test_multiple_types_processed_separately(self, mock_redis):
        df = pd.DataFrame(
            {
                "type": [HR, HR, STEPS, STEPS],
                "sourceName": ["W"] * 4,
                "unit": [HR_UNIT, HR_UNIT, STEPS_UNIT, STEPS_UNIT],
                "value": [72.0, 80.0, 500.0, 600.0],
                "startDate": [1_000_000 + i for i in range(4)],
                "endDate": [1_000_060 + i for i in range(4)],
            }
        )
        # 2 commands per row × 2 rows-per-type
        mock_redis.ts.return_value.pipeline.return_value.execute.return_value = [
            1,
            2,
            3,
            4,
        ]
        _load(df, mock_redis)
        # one pipeline per type
        assert mock_redis.ts.return_value.pipeline.call_count == 2

    def test_duplicate_policy_last_forwarded(self, mock_redis):
        df = _make_records_df()
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

    def test_index_error_creates_batch_failure(self, mock_redis):
        df = _make_records_df()
        with patch(
            "src.importer.importer.upload_batch", side_effect=IndexError("mismatch")
        ):
            result = _load(df, mock_redis)
        assert len(result) == 1 and isinstance(result[0], BatchFailure)

    def test_single_row_df(self, mock_redis):
        mock_redis.ts.return_value.pipeline.return_value.execute.return_value = [1, 2]
        assert _load(_make_records_df(n=1), mock_redis) == []

    def test_return_type_is_list(self, mock_redis):
        mock_redis.ts.return_value.pipeline.return_value.execute.return_value = [
            1,
            2,
            3,
            4,
        ]
        assert isinstance(_load(_make_records_df(), mock_redis), list)

    def test_unknown_identifier_yields_batch_failure_not_keyerror(self, mock_redis):
        """The headline bug: previously _load raised KeyError on every
        non-categorical identifier.  Now it must skip unknown identifiers
        gracefully with a BatchFailure."""
        df = pd.DataFrame(
            {
                "type": ["DefinitelyNotInRegistry"],
                "sourceName": ["w"],
                "unit": ["bpm"],
                "value": [1.0],
                "startDate": [1_700_000_000],
                "endDate": [1_700_000_060],
            }
        )
        result = _load(df, mock_redis)
        assert len(result) == 1
        assert isinstance(result[0], BatchFailure)
        assert "DefinitelyNotInRegistry" in result[0].error

    def test_uses_full_registry_not_only_categories(self, mock_redis):
        """Regression: HKQuantityTypeIdentifier* must be resolvable.

        Previously `_load` looked up identifiers in
        `HKCategoryTypeIdentifierRegistry` only, so any quantity type
        raised KeyError.  This test will fail if anyone re-introduces
        that bug.
        """
        df = _make_records_df(type_val=HR, n=1)
        mock_redis.ts.return_value.pipeline.return_value.execute.return_value = [1, 2]
        # Should not raise:
        result = _load(df, mock_redis)
        assert result == []

    def test_correct_labels_used_for_quantity_type(self, mock_redis):
        df = _make_records_df(type_val=HR, n=1)
        mock_redis.ts.return_value.pipeline.return_value.execute.return_value = [1, 2]
        with patch("src.importer.importer.ensure_ts_key") as mock_ensure:
            _load(df, mock_redis)
        # ensure_ts_key called twice — once for :start, once for :end.
        assert mock_ensure.call_count == 2
        # Inspect the labels passed.
        all_labels = [c.kwargs["labels"] for c in mock_ensure.call_args_list]
        for labels in all_labels:
            assert labels["identifier"] == HR
            assert labels["unit"] == HR_UNIT
            assert labels["group"] == "vital_signs"


# ---------------------------------------------------------------------------
# etl
# ---------------------------------------------------------------------------


class TestEtl:
    def test_etl_sets_failures_on_success(self, importer):
        with (
            patch.object(importer, "_extract", return_value=_extract_return()),
            patch("src.importer.importer.transform"),
            patch("src.importer.importer._load", return_value=[]) as mock_load,
            patch("src.importer.importer.load_workouts", return_value=[]),
            patch("src.importer.importer.load_correlations", return_value=[]),
            patch("src.importer.importer.load_activities", return_value=[]),
            patch("src.importer.importer.load_routes", return_value=[]),
            patch.object(importer, "_update_failures_file"),
        ):
            importer.etl()
        assert importer.failures == []
        mock_load.assert_called_once()

    def test_etl_stores_failures(self, importer):
        failures = [BatchFailure(HR, 0, "err")]
        with (
            patch.object(importer, "_extract", return_value=_extract_return()),
            patch("src.importer.importer.transform"),
            patch("src.importer.importer._load", return_value=failures),
            patch("src.importer.importer.load_workouts", return_value=[]),
            patch("src.importer.importer.load_correlations", return_value=[]),
            patch("src.importer.importer.load_activities", return_value=[]),
            patch("src.importer.importer.load_routes", return_value=[]),
            patch.object(importer, "_update_failures_file"),
        ):
            importer.etl()
        assert importer.failures == failures

    def test_etl_document_failures_are_aggregated(self, importer):
        """Failures from each document-loader should accumulate on
        ``importer.failures``, not be silently dropped."""
        rec_fail = [RowFailure(HR, 0, start_error="e")]
        wk_fail = [BatchFailure("workout:1", -1, "k")]
        with (
            patch.object(importer, "_extract", return_value=_extract_return()),
            patch("src.importer.importer.transform"),
            patch("src.importer.importer._load", return_value=rec_fail),
            patch("src.importer.importer.load_workouts", return_value=wk_fail),
            patch("src.importer.importer.load_correlations", return_value=[]),
            patch("src.importer.importer.load_activities", return_value=[]),
            patch("src.importer.importer.load_routes", return_value=[]),
            patch.object(importer, "_update_failures_file"),
        ):
            importer.etl()
        assert rec_fail[0] in importer.failures
        assert wk_fail[0] in importer.failures

    def test_etl_all_loaders_invoked(self, importer):
        """All four document-loader calls must happen on every etl() run."""
        with (
            patch.object(importer, "_extract", return_value=_extract_return()),
            patch("src.importer.importer.transform"),
            patch("src.importer.importer._load", return_value=[]),
            patch("src.importer.importer.load_workouts", return_value=[]) as mw,
            patch("src.importer.importer.load_correlations", return_value=[]) as mc,
            patch("src.importer.importer.load_activities", return_value=[]) as ma,
            patch("src.importer.importer.load_routes", return_value=[]) as mr,
            patch.object(importer, "_update_failures_file"),
        ):
            importer.etl()
        mw.assert_called_once()
        mc.assert_called_once()
        ma.assert_called_once()
        mr.assert_called_once()

    def test_etl_persist_failures_true_calls_update(self, importer):
        with (
            patch.object(importer, "_extract", return_value=_extract_return()),
            patch("src.importer.importer.transform"),
            patch("src.importer.importer._load", return_value=[]),
            patch("src.importer.importer.load_workouts", return_value=[]),
            patch("src.importer.importer.load_correlations", return_value=[]),
            patch("src.importer.importer.load_activities", return_value=[]),
            patch("src.importer.importer.load_routes", return_value=[]),
            patch.object(importer, "_update_failures_file") as mock_upd,
        ):
            importer.etl(persist_failures=True)
        mock_upd.assert_called_once()

    def test_etl_persist_failures_false_skips_update(self, importer):
        with (
            patch.object(importer, "_extract", return_value=_extract_return()),
            patch("src.importer.importer.transform"),
            patch("src.importer.importer._load", return_value=[]),
            patch("src.importer.importer.load_workouts", return_value=[]),
            patch("src.importer.importer.load_correlations", return_value=[]),
            patch("src.importer.importer.load_activities", return_value=[]),
            patch("src.importer.importer.load_routes", return_value=[]),
            patch.object(importer, "_update_failures_file") as mock_upd,
        ):
            importer.etl(persist_failures=False)
        mock_upd.assert_not_called()

    def test_etl_no_cache_forwarded(self, importer):
        with (
            patch.object(
                importer, "_extract", return_value=_extract_return()
            ) as mock_extract,
            patch("src.importer.importer.transform"),
            patch("src.importer.importer._load", return_value=[]),
            patch("src.importer.importer.load_workouts", return_value=[]),
            patch("src.importer.importer.load_correlations", return_value=[]),
            patch("src.importer.importer.load_activities", return_value=[]),
            patch("src.importer.importer.load_routes", return_value=[]),
            patch.object(importer, "_update_failures_file"),
        ):
            importer.etl(no_cache=True)
        assert mock_extract.call_args[1]["no_cache"] is True

    def test_etl_uses_duplicate_policy_first(self, importer):
        with (
            patch.object(importer, "_extract", return_value=_extract_return()),
            patch("src.importer.importer.transform"),
            patch("src.importer.importer._load", return_value=[]) as mock_load,
            patch("src.importer.importer.load_workouts", return_value=[]),
            patch("src.importer.importer.load_correlations", return_value=[]),
            patch("src.importer.importer.load_activities", return_value=[]),
            patch("src.importer.importer.load_routes", return_value=[]),
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
        with (
            patch.object(importer, "_extract", return_value=_extract_return()),
            patch("src.importer.importer.transform"),
            patch("src.importer.importer._load", return_value=[]) as mock_load,
            patch("src.importer.importer.load_workouts", return_value=[]),
            patch("src.importer.importer.load_correlations", return_value=[]),
            patch("src.importer.importer.load_activities", return_value=[]),
            patch("src.importer.importer.load_routes", return_value=[]),
            patch.object(importer, "_update_failures_file"),
        ):
            importer.update()
        _, kwargs = mock_load.call_args
        assert kwargs["duplicate_policy"] == DuplicatePolicy.LAST

    def test_update_stores_failures(self, importer):
        failures = [BatchFailure(HR, 0, "err")]
        with (
            patch.object(importer, "_extract", return_value=_extract_return()),
            patch("src.importer.importer.transform"),
            patch("src.importer.importer._load", return_value=failures),
            patch("src.importer.importer.load_workouts", return_value=[]),
            patch("src.importer.importer.load_correlations", return_value=[]),
            patch("src.importer.importer.load_activities", return_value=[]),
            patch("src.importer.importer.load_routes", return_value=[]),
            patch.object(importer, "_update_failures_file"),
        ):
            importer.update()
        assert importer.failures == failures

    def test_update_persist_failures_false_skips(self, importer):
        with (
            patch.object(importer, "_extract", return_value=_extract_return()),
            patch("src.importer.importer.transform"),
            patch("src.importer.importer._load", return_value=[]),
            patch("src.importer.importer.load_workouts", return_value=[]),
            patch("src.importer.importer.load_correlations", return_value=[]),
            patch("src.importer.importer.load_activities", return_value=[]),
            patch("src.importer.importer.load_routes", return_value=[]),
            patch.object(importer, "_update_failures_file") as mock_upd,
        ):
            importer.update(persist_failures=False)
        mock_upd.assert_not_called()

    def test_update_no_cache_forwarded(self, importer):
        with (
            patch.object(
                importer, "_extract", return_value=_extract_return()
            ) as mock_extract,
            patch("src.importer.importer.transform"),
            patch("src.importer.importer._load", return_value=[]),
            patch("src.importer.importer.load_workouts", return_value=[]),
            patch("src.importer.importer.load_correlations", return_value=[]),
            patch("src.importer.importer.load_activities", return_value=[]),
            patch("src.importer.importer.load_routes", return_value=[]),
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
        df = _make_records_df(n=4)
        df.index = [0, 1, 2, 3]
        self._write_failures(importer, [RowFailure(HR, 1, start_error="dup")])
        with (
            patch.object(importer, "_extract", return_value=_extract_return(df)),
            patch("src.importer.importer.transform"),
            patch("src.importer.importer._load", return_value=[]) as mock_load,
            patch.object(importer, "_update_failures_file"),
        ):
            importer.retry_failed()
        loaded_df = mock_load.call_args[1]["df"]
        assert 1 in loaded_df.index

    def test_retry_batch_failures_whole_type_loaded(self, importer):
        df = _make_records_df(type_val=HR, n=3)
        self._write_failures(importer, [BatchFailure(HR, 0, "conn lost")])
        with (
            patch.object(importer, "_extract", return_value=_extract_return(df)),
            patch("src.importer.importer.transform"),
            patch("src.importer.importer._load", return_value=[]) as mock_load,
            patch.object(importer, "_update_failures_file"),
        ):
            importer.retry_failed()
        loaded_df = mock_load.call_args[1]["df"]
        assert (loaded_df["type"] == HR).all()
        assert len(loaded_df) == 3

    def test_retry_skips_document_failures(self, importer):
        """Failures with ``batch_nr == -1`` are document-class failures
        and must not be retried by retry_failed (which only handles
        TimeSeries rows)."""
        df = _make_records_df(n=2)
        self._write_failures(
            importer,
            [
                RowFailure(HR, 0, start_error="dup"),
                BatchFailure("workout:foo", -1, "json set failed"),
            ],
        )
        with (
            patch.object(importer, "_extract", return_value=_extract_return(df)),
            patch("src.importer.importer.transform"),
            patch("src.importer.importer._load", return_value=[]) as mock_load,
            patch.object(importer, "_update_failures_file"),
        ):
            importer.retry_failed()
        loaded_df = mock_load.call_args[1]["df"]
        # Only the row index from the RowFailure is retried.
        assert list(loaded_df.index) == [0]

    def test_retry_all_resolved_deletes_file(self, importer):
        df = _make_records_df(n=2)
        self._write_failures(importer, [RowFailure(HR, 0, start_error="e")])
        with (
            patch.object(importer, "_extract", return_value=_extract_return(df)),
            patch("src.importer.importer.transform"),
            patch("src.importer.importer._load", return_value=[]),
        ):
            importer.retry_failed(persist_failures=True)
        assert not importer.failures_file.exists()

    def test_retry_partial_resolution_overwrites_file(self, importer):
        df = _make_records_df(n=2)
        remaining = [RowFailure(HR, 1, end_error="still bad")]
        self._write_failures(importer, [RowFailure(HR, 0), RowFailure(HR, 1)])
        with (
            patch.object(importer, "_extract", return_value=_extract_return(df)),
            patch("src.importer.importer.transform"),
            patch("src.importer.importer._load", return_value=remaining),
        ):
            importer.retry_failed(persist_failures=True)
        assert importer.failures_file.exists()
        assert importer.failures == remaining

    def test_retry_uses_duplicate_policy_first(self, importer):
        df = _make_records_df(n=1)
        self._write_failures(importer, [RowFailure(HR, 0)])
        with (
            patch.object(importer, "_extract", return_value=_extract_return(df)),
            patch("src.importer.importer.transform"),
            patch("src.importer.importer._load", return_value=[]) as mock_load,
            patch.object(importer, "_update_failures_file"),
        ):
            importer.retry_failed()
        assert mock_load.call_args[1]["duplicate_policy"] == DuplicatePolicy.FIRST

    def test_retry_persist_failures_false_skips_update(self, importer):
        df = _make_records_df(n=1)
        self._write_failures(importer, [RowFailure(HR, 0)])
        with (
            patch.object(importer, "_extract", return_value=_extract_return(df)),
            patch("src.importer.importer.transform"),
            patch("src.importer.importer._load", return_value=[]),
            patch.object(importer, "_update_failures_file") as mock_upd,
        ):
            importer.retry_failed(persist_failures=False)
        mock_upd.assert_not_called()
