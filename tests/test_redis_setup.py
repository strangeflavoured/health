from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch

import pytest
import redis
from redis.exceptions import ResponseError

from src.redis_setup import (
    _INDICES,
    create_index,
    drop_index,
    ensure_ts_key,
    index_exists,
    print_status,
    records_labels,
    setup_indexes,
    upsert_ts_labels,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_client():
    client = MagicMock(spec=redis.Redis)
    client.ft = MagicMock()
    client.ts = MagicMock()
    return client


# ===========================================================================
# TestIndexExists
# ===========================================================================


class TestIndexExists:
    def test_returns_true_when_info_succeeds(self):
        client = _make_client()
        client.ft.return_value.info.return_value = {}
        assert index_exists(client, "idx:workouts") is True

    def test_returns_false_when_response_error(self):
        client = _make_client()
        client.ft.return_value.info.side_effect = ResponseError("Unknown index")
        assert index_exists(client, "idx:workouts") is False

    def test_passes_index_name_to_ft(self):
        client = _make_client()
        client.ft.return_value.info.return_value = {}
        index_exists(client, "idx:activities")
        client.ft.assert_called_with("idx:activities")

    def test_does_not_swallow_other_redis_errors(self):
        client = _make_client()
        client.ft.return_value.info.side_effect = redis.ConnectionError("gone")
        with pytest.raises(redis.ConnectionError):
            index_exists(client, "idx:workouts")


# ===========================================================================
# TestDropIndex
# ===========================================================================


class TestDropIndex:
    def test_calls_dropindex_when_not_dry_run(self):
        client = _make_client()
        drop_index(client, "idx:workouts", dry_run=False)
        client.ft.return_value.dropindex.assert_called_once()

    def test_does_not_call_dropindex_in_dry_run(self):
        client = _make_client()
        drop_index(client, "idx:workouts", dry_run=True)
        client.ft.return_value.dropindex.assert_not_called()

    def test_passes_correct_index_name(self):
        client = _make_client()
        drop_index(client, "idx:correlations", dry_run=False)
        client.ft.assert_called_with("idx:correlations")

    def test_logs_dry_run_message(self, caplog):
        client = _make_client()
        with caplog.at_level(logging.INFO):
            drop_index(client, "idx:workouts", dry_run=True)
        assert "dry-run" in caplog.text
        assert "idx:workouts" in caplog.text

    def test_logs_dropped_message(self, caplog):
        client = _make_client()
        with caplog.at_level(logging.INFO):
            drop_index(client, "idx:workouts", dry_run=False)
        assert "dropped" in caplog.text


# ===========================================================================
# TestCreateIndex
# ===========================================================================


class TestCreateIndex:
    def test_calls_create_index_when_not_dry_run(self):
        client = _make_client()
        create_index(client, _INDICES[0], dry_run=False)
        client.ft.return_value.create_index.assert_called_once()

    def test_does_not_call_create_index_in_dry_run(self):
        client = _make_client()
        create_index(client, _INDICES[0], dry_run=True)
        client.ft.return_value.create_index.assert_not_called()

    def test_passes_correct_prefix(self):
        client = _make_client()
        spec = _INDICES[0]
        create_index(client, spec, dry_run=False)
        _, kwargs = client.ft.return_value.create_index.call_args
        assert spec.prefix in kwargs["definition"].args

    def test_uses_json_index_type(self):
        client = _make_client()
        create_index(client, _INDICES[0], dry_run=False)
        _, kwargs = client.ft.return_value.create_index.call_args
        assert "JSON" in kwargs["definition"].args

    def test_passes_fields_to_create_index(self):
        client = _make_client()
        spec = _INDICES[0]
        create_index(client, spec, dry_run=False)
        positional_args, _ = client.ft.return_value.create_index.call_args
        assert positional_args[0] is spec.fields

    def test_logs_dry_run_message_with_spec_name(self, caplog):
        client = _make_client()
        spec = _INDICES[0]
        with caplog.at_level(logging.INFO):
            create_index(client, spec, dry_run=True)
        assert "dry-run" in caplog.text
        assert spec.name in caplog.text

    def test_logs_created_message(self, caplog):
        client = _make_client()
        with caplog.at_level(logging.INFO):
            create_index(client, _INDICES[0], dry_run=False)
        assert "created" in caplog.text


# ===========================================================================
# TestSetupIndexes
# ===========================================================================


class TestSetupIndexes:
    def _patch_exists(self, exists_map):
        import src.redis_setup as m

        return patch.object(
            m, "index_exists", side_effect=lambda _c, n: exists_map.get(n, False)
        )

    def test_creates_all_indexes_when_none_exist(self):
        import src.redis_setup as m

        client = _make_client()
        with (
            self._patch_exists({s.name: False for s in _INDICES}),
            patch.object(m, "create_index") as mock_create,
            patch.object(m, "drop_index") as mock_drop,
        ):
            setup_indexes(client, dry_run=False, force=False)
        assert mock_create.call_count == len(_INDICES)
        mock_drop.assert_not_called()

    def test_skips_existing_indexes_without_force(self):
        import src.redis_setup as m

        client = _make_client()
        with (
            self._patch_exists({s.name: True for s in _INDICES}),
            patch.object(m, "create_index") as mock_create,
            patch.object(m, "drop_index") as mock_drop,
        ):
            setup_indexes(client, dry_run=False, force=False)
        mock_create.assert_not_called()
        mock_drop.assert_not_called()

    def test_drops_and_recreates_with_force(self):
        import src.redis_setup as m

        client = _make_client()
        with (
            self._patch_exists({s.name: True for s in _INDICES}),
            patch.object(m, "create_index") as mock_create,
            patch.object(m, "drop_index") as mock_drop,
        ):
            setup_indexes(client, dry_run=False, force=True)
        assert mock_drop.call_count == len(_INDICES)
        assert mock_create.call_count == len(_INDICES)

    def test_partial_existence(self):
        import src.redis_setup as m

        names = [s.name for s in _INDICES]
        client = _make_client()
        with (
            self._patch_exists({names[0]: True, names[1]: False, names[2]: False}),
            patch.object(m, "create_index") as mock_create,
            patch.object(m, "drop_index") as mock_drop,
        ):
            setup_indexes(client, dry_run=False, force=False)
        assert mock_create.call_count == 2
        mock_drop.assert_not_called()

    def test_propagates_dry_run_to_create(self):
        import src.redis_setup as m

        client = _make_client()
        with (
            self._patch_exists({s.name: False for s in _INDICES}),
            patch.object(m, "create_index") as mock_create,
        ):
            setup_indexes(client, dry_run=True, force=False)
        for c in mock_create.call_args_list:
            assert c.kwargs["dry_run"] is True

    def test_propagates_dry_run_to_drop(self):
        import src.redis_setup as m

        client = _make_client()
        with (
            self._patch_exists({s.name: True for s in _INDICES}),
            patch.object(m, "drop_index") as mock_drop,
            patch.object(m, "create_index"),
        ):
            setup_indexes(client, dry_run=True, force=True)
        for c in mock_drop.call_args_list:
            assert c.kwargs["dry_run"] is True

    def test_logs_skip_message_when_existing_no_force(self, caplog):
        import src.redis_setup as m

        client = _make_client()
        with (
            self._patch_exists({s.name: True for s in _INDICES}),
            patch.object(m, "create_index"),
            patch.object(m, "drop_index"),
            caplog.at_level(logging.INFO),
        ):
            setup_indexes(client, dry_run=False, force=False)
        assert "skipping" in caplog.text


# ===========================================================================
# TestPrintStatus
# ===========================================================================


class TestPrintStatus:
    def test_logs_doc_count_for_existing_index(self, caplog):
        import src.redis_setup as m

        client = _make_client()
        client.ft.return_value.info.return_value = {"num_docs": 42, "indexing": "0"}
        with (
            patch.object(m, "index_exists", return_value=True),
            caplog.at_level(logging.INFO),
        ):
            print_status(client)
        assert "42" in caplog.text

    def test_logs_indexing_when_background_pass_active(self, caplog):
        import src.redis_setup as m

        client = _make_client()
        client.ft.return_value.info.return_value = {"num_docs": 0, "indexing": "1"}
        with (
            patch.object(m, "index_exists", return_value=True),
            caplog.at_level(logging.INFO),
        ):
            print_status(client)
        assert "indexing" in caplog.text

    def test_logs_missing_for_absent_index(self, caplog):
        import src.redis_setup as m

        client = _make_client()
        with (
            patch.object(m, "index_exists", return_value=False),
            caplog.at_level(logging.INFO),
        ):
            print_status(client)
        assert "missing" in caplog.text

    def test_logs_all_index_names(self, caplog):
        import src.redis_setup as m

        client = _make_client()
        client.ft.return_value.info.return_value = {"num_docs": 0, "indexing": "0"}
        with (
            patch.object(m, "index_exists", return_value=True),
            caplog.at_level(logging.INFO),
        ):
            print_status(client)
        for spec in _INDICES:
            assert spec.name in caplog.text


# ===========================================================================
# TestUpsertTsLabels
# ===========================================================================


class TestUpsertTsLabels:
    def _ts(self, client):
        return client.ts.return_value

    def test_calls_alter_when_key_exists(self):
        client = _make_client()
        upsert_ts_labels(client, [("ts:HR:start", {"unit": "bpm"})], dry_run=False)
        self._ts(client).alter.assert_called_once_with(
            "ts:HR:start", labels={"unit": "bpm"}
        )

    def test_falls_back_to_create_when_alter_raises(self):
        client = _make_client()
        self._ts(client).alter.side_effect = redis.ResponseError("not found")
        upsert_ts_labels(client, [("ts:HR:start", {"unit": "bpm"})], dry_run=False)
        self._ts(client).create.assert_called_once_with(
            "ts:HR:start", labels={"unit": "bpm"}
        )

    def test_dry_run_skips_all_writes(self):
        client = _make_client()
        upsert_ts_labels(client, [("ts:HR:start", {}), ("ts:HR:end", {})], dry_run=True)
        self._ts(client).alter.assert_not_called()
        self._ts(client).create.assert_not_called()

    def test_dry_run_logs_each_key(self, caplog):
        client = _make_client()
        with caplog.at_level(logging.INFO):
            upsert_ts_labels(
                client, [("ts:HR:start", {}), ("ts:HR:end", {})], dry_run=True
            )
        assert "ts:HR:start" in caplog.text
        assert "ts:HR:end" in caplog.text

    def test_processes_multiple_pairs(self):
        client = _make_client()
        pairs = [("ts:A:start", {}), ("ts:A:end", {}), ("ts:B:start", {})]
        upsert_ts_labels(client, pairs, dry_run=False)
        assert self._ts(client).alter.call_count == 3

    def test_empty_list_is_noop(self):
        client = _make_client()
        upsert_ts_labels(client, [], dry_run=False)
        self._ts(client).alter.assert_not_called()
        self._ts(client).create.assert_not_called()

    def test_create_not_called_when_alter_succeeds(self):
        client = _make_client()
        upsert_ts_labels(client, [("ts:HR:start", {})], dry_run=False)
        self._ts(client).create.assert_not_called()


# ===========================================================================
# TestEnsureTsKey
# ===========================================================================


class TestEnsureTsKey:
    def _ts(self, client):
        return client.ts.return_value

    def test_does_not_create_when_key_exists(self):
        client = _make_client()
        self._ts(client).info.return_value = {}
        ensure_ts_key(client, "ts:HR:start", {"unit": "bpm"})
        self._ts(client).create.assert_not_called()

    def test_creates_key_when_absent(self):
        client = _make_client()
        self._ts(client).info.side_effect = redis.ResponseError("not found")
        ensure_ts_key(client, "ts:HR:start", {"unit": "bpm"})
        self._ts(client).create.assert_called_once_with(
            "ts:HR:start", labels={"unit": "bpm"}
        )

    def test_passes_labels_verbatim(self):
        client = _make_client()
        self._ts(client).info.side_effect = redis.ResponseError("gone")
        labels = {
            "unit": "count/min",
            "identifier": "HR",
            "group": "vitals",
            "event_type": "start",
        }
        ensure_ts_key(client, "ts:HR:start", labels)
        self._ts(client).create.assert_called_once_with("ts:HR:start", labels=labels)

    def test_info_called_with_correct_key(self):
        client = _make_client()
        self._ts(client).info.return_value = {}
        ensure_ts_key(client, "ts:SpO2:end", {})
        self._ts(client).info.assert_called_once_with("ts:SpO2:end")


# ===========================================================================
# TestRecordsLabels
# ===========================================================================


class TestRecordsLabels:
    def test_returns_two_entries_per_registry_type(self):
        from src.model import HKTypeIdentifierRegistry
        from src.redis_setup import records_labels

        assert len(records_labels()) == len(HKTypeIdentifierRegistry) * 2

    def test_start_and_end_keys_present_for_each_type(self):
        from src.model import HKTypeIdentifierRegistry

        keys = [k for k, _ in records_labels()]
        for name in HKTypeIdentifierRegistry:
            assert f"ts:{name}:start" in keys
            assert f"ts:{name}:end" in keys

    def test_event_type_label_is_start_or_end(self):
        for _, labels in records_labels():
            assert labels["event_type"] in {"start", "end"}

    def test_start_key_has_event_type_start(self):
        for key, labels in records_labels():
            if key.endswith(":start"):
                assert labels["event_type"] == "start"

    def test_end_key_has_event_type_end(self):
        for key, labels in records_labels():
            if key.endswith(":end"):
                assert labels["event_type"] == "end"

    def test_unit_populated_for_quantity_type(self):
        for key, labels in records_labels():
            if "HeartRate" in key:
                assert labels["unit"] == "count/min"

    def test_unit_is_none_for_category_type_without_unit(self):
        for key, labels in records_labels():
            if "SleepAnalysis" in key:
                assert labels["unit"] == "Categorical"

    def test_identifier_label_matches_key_name(self):
        for key, labels in records_labels():
            assert labels["identifier"] == key.split(":")[1]

    def test_group_label_present(self):
        for _, labels in records_labels():
            assert "group" in labels

    def test_group_label_correct_for_quantity_type(self):
        for key, labels in records_labels():
            if "HeartRate" in key:
                assert labels["group"] == "vitals"

    def test_base_labels_not_mutated_across_start_end(self):
        by_name: dict = {}
        for key, labels in records_labels():
            parts = key.split(":")
            by_name[(parts[1], parts[2])] = labels
        from src.model import HKTypeIdentifierRegistry

        for name in HKTypeIdentifierRegistry:
            s = by_name[(name, "start")]
            e = by_name[(name, "end")]
            for field in ("unit", "identifier", "group"):
                assert s[field] == e[field]
            assert s["event_type"] != e["event_type"]

    def test_returns_list_of_tuples(self):
        result = records_labels()
        assert isinstance(result, list)
        for key, labels in result:
            assert isinstance(key, str)
            assert isinstance(labels, dict)
