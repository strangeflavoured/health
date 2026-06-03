from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch

import pytest
import redis
from redis.exceptions import ResponseError

import src.redis_setup as redis_setup
from src.redis_setup import (
    _INDICES,
    create_index,
    drop_index,
    ensure_ts_key,
    index_exists,
    print_status,
    setup_indexes,
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
        return patch.object(
            redis_setup,
            "index_exists",
            side_effect=lambda _c, n: exists_map.get(n, False),
        )

    def test_creates_all_indexes_when_none_exist(self):
        client = _make_client()
        with (
            self._patch_exists({s.name: False for s in _INDICES}),
            patch.object(redis_setup, "create_index") as mock_create,
            patch.object(redis_setup, "drop_index") as mock_drop,
        ):
            setup_indexes(client, dry_run=False, force=False)
        assert mock_create.call_count == len(_INDICES)
        mock_drop.assert_not_called()

    def test_skips_existing_indexes_without_force(self):
        client = _make_client()
        with (
            self._patch_exists({s.name: True for s in _INDICES}),
            patch.object(redis_setup, "create_index") as mock_create,
            patch.object(redis_setup, "drop_index") as mock_drop,
        ):
            setup_indexes(client, dry_run=False, force=False)
        mock_create.assert_not_called()
        mock_drop.assert_not_called()

    def test_drops_and_recreates_with_force(self):
        client = _make_client()
        with (
            self._patch_exists({s.name: True for s in _INDICES}),
            patch.object(redis_setup, "create_index") as mock_create,
            patch.object(redis_setup, "drop_index") as mock_drop,
        ):
            setup_indexes(client, dry_run=False, force=True)
        assert mock_drop.call_count == len(_INDICES)
        assert mock_create.call_count == len(_INDICES)

    def test_partial_existence(self):
        names = [s.name for s in _INDICES]
        # One existing, the rest missing — should create everything that's
        # missing and never drop.
        existence = {names[0]: True}
        for n in names[1:]:
            existence[n] = False

        client = _make_client()
        with (
            self._patch_exists(existence),
            patch.object(redis_setup, "create_index") as mock_create,
            patch.object(redis_setup, "drop_index") as mock_drop,
        ):
            setup_indexes(client, dry_run=False, force=False)
        assert mock_create.call_count == len(_INDICES) - 1
        mock_drop.assert_not_called()

    def test_propagates_dry_run_to_create(self):
        client = _make_client()
        with (
            self._patch_exists({s.name: False for s in _INDICES}),
            patch.object(redis_setup, "create_index") as mock_create,
        ):
            setup_indexes(client, dry_run=True, force=False)
        for c in mock_create.call_args_list:
            assert c.kwargs["dry_run"] is True

    def test_propagates_dry_run_to_drop(self):
        client = _make_client()
        with (
            self._patch_exists({s.name: True for s in _INDICES}),
            patch.object(redis_setup, "drop_index") as mock_drop,
            patch.object(redis_setup, "create_index"),
        ):
            setup_indexes(client, dry_run=True, force=True)
        for c in mock_drop.call_args_list:
            assert c.kwargs["dry_run"] is True

    def test_logs_skip_message_when_existing_no_force(self, caplog):
        client = _make_client()
        with (
            self._patch_exists({s.name: True for s in _INDICES}),
            patch.object(redis_setup, "create_index"),
            patch.object(redis_setup, "drop_index"),
            caplog.at_level(logging.INFO),
        ):
            setup_indexes(client, dry_run=False, force=False)
        assert "skipping" in caplog.text


# ===========================================================================
# TestPrintStatus
# ===========================================================================


class TestPrintStatus:
    def test_logs_doc_count_for_existing_index(self, caplog):
        client = _make_client()
        client.ft.return_value.info.return_value = {"num_docs": 42, "indexing": "0"}
        with (
            patch.object(redis_setup, "index_exists", return_value=True),
            caplog.at_level(logging.INFO),
        ):
            print_status(client)
        assert "42" in caplog.text

    def test_logs_indexing_when_background_pass_active(self, caplog):
        client = _make_client()
        client.ft.return_value.info.return_value = {"num_docs": 0, "indexing": "1"}
        with (
            patch.object(redis_setup, "index_exists", return_value=True),
            caplog.at_level(logging.INFO),
        ):
            print_status(client)
        assert "indexing" in caplog.text

    def test_logs_missing_for_absent_index(self, caplog):
        client = _make_client()
        with (
            patch.object(redis_setup, "index_exists", return_value=False),
            caplog.at_level(logging.INFO),
        ):
            print_status(client)
        assert "missing" in caplog.text

    def test_logs_all_index_names(self, caplog):
        client = _make_client()
        client.ft.return_value.info.return_value = {"num_docs": 0, "indexing": "0"}
        with (
            patch.object(redis_setup, "index_exists", return_value=True),
            caplog.at_level(logging.INFO),
        ):
            print_status(client)
        for spec in _INDICES:
            assert spec.name in caplog.text


# ===========================================================================
# TestEnsureTsKey
# ===========================================================================


class TestEnsureTsKey:
    labels = {"unit": "bpm"}
    info_return_value = {"labels": labels, "duplicate_policy": "FIRST"}

    def _ts(self, client):
        return client.ts.return_value

    def test_does_not_create_when_key_exists(self):
        client = _make_client()
        self._ts(client).info.return_value = self.info_return_value
        ensure_ts_key(client, "ts:HR:start", labels=self.labels)
        self._ts(client).create.assert_not_called()

    def test_raises_when_labels_dont_match(self):
        client = _make_client()
        labels = {"unit": "%"}
        self._ts(client).info.return_value = self.info_return_value
        with pytest.raises(ValueError, match="labels don't match: expected"):
            ensure_ts_key(client, "ts:HR:start", labels=labels)

    def test_alters_existing_key_duplicate_policy(self):
        """When the key already exists the policy must be updated via TS.ALTER."""
        client = _make_client()
        self._ts(client).info.return_value = self.info_return_value
        ensure_ts_key(
            client, "ts:HR:start", labels=self.labels, duplicate_policy="LAST"
        )
        self._ts(client).alter.assert_called_once_with(
            "ts:HR:start", duplicate_policy="LAST"
        )

    def test_creates_key_when_absent(self):
        client = _make_client()
        self._ts(client).info.side_effect = redis.ResponseError("not found")
        ensure_ts_key(client, "ts:HR:start", self.labels)
        self._ts(client).create.assert_called_once_with(
            "ts:HR:start",
            labels=self.labels,
            duplicate_policy="FIRST",
        )

    def test_creates_key_with_supplied_duplicate_policy(self):
        client = _make_client()
        self._ts(client).info.side_effect = redis.ResponseError("gone")
        ensure_ts_key(client, "ts:HR:start", {}, duplicate_policy="LAST")
        self._ts(client).create.assert_called_once_with(
            "ts:HR:start", labels={}, duplicate_policy="LAST"
        )

    def test_does_not_alter_when_creating(self):
        """TS.ALTER must not be called when the key is newly created."""
        client = _make_client()
        self._ts(client).info.side_effect = redis.ResponseError("gone")
        ensure_ts_key(client, "ts:HR:start", {})
        self._ts(client).alter.assert_not_called()

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
        self._ts(client).create.assert_called_once_with(
            "ts:HR:start", labels=labels, duplicate_policy="FIRST"
        )

    def test_info_called_with_correct_key(self):
        client = _make_client()
        self._ts(client).info.return_value = self.info_return_value
        ensure_ts_key(client, "ts:SpO2:end", self.labels)
        self._ts(client).info.assert_called_once_with("ts:SpO2:end")

    def test_default_policy_is_first(self):
        client = _make_client()
        self._ts(client).info.side_effect = redis.ResponseError("gone")
        ensure_ts_key(client, "ts:HR:start", {})
        _, kwargs = self._ts(client).create.call_args
        assert kwargs["duplicate_policy"] == "FIRST"
