"""Tests for arioso.platforms.sunoapi.task_store and adapter integration."""

import json
import time
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

import pytest

from arioso.platforms.sunoapi.task_store import (
    SunoTasks,
    _make_record,
    _update_record,
    _now_iso,
)
from arioso.platforms.sunoapi.config import PLATFORM_CONFIG
from arioso.platforms.sunoapi.adapter import Adapter

CALLBACK_URL = "https://example.com/webhook"


# ---------------------------------------------------------------------------
# SunoTasks store basics
# ---------------------------------------------------------------------------


class TestSunoTasksMapping:
    """Test SunoTasks as a collections.abc.Mapping."""

    def test_empty_store(self, tmp_path):
        store = SunoTasks(tmp_path / "tasks")
        assert len(store) == 0
        assert list(store) == []
        assert "nonexistent" not in store

    def test_save_and_getitem(self, tmp_path):
        store = SunoTasks(tmp_path / "tasks")
        record = _make_record("task-abc", operation="generate", status="PENDING")
        store.save(record)

        assert "task-abc" in store
        assert len(store) == 1
        got = store["task-abc"]
        assert got["task_id"] == "task-abc"
        assert got["operation"] == "generate"
        assert got["status"] == "PENDING"

    def test_getitem_missing_raises_keyerror(self, tmp_path):
        store = SunoTasks(tmp_path / "tasks")
        with pytest.raises(KeyError):
            store["missing"]

    def test_iter_yields_task_ids(self, tmp_path):
        store = SunoTasks(tmp_path / "tasks")
        for tid in ["aaa", "bbb", "ccc"]:
            store.save(_make_record(tid))
        assert set(store) == {"aaa", "bbb", "ccc"}

    def test_len(self, tmp_path):
        store = SunoTasks(tmp_path / "tasks")
        assert len(store) == 0
        store.save(_make_record("one"))
        assert len(store) == 1
        store.save(_make_record("two"))
        assert len(store) == 2

    def test_contains(self, tmp_path):
        store = SunoTasks(tmp_path / "tasks")
        store.save(_make_record("present"))
        assert "present" in store
        assert "absent" not in store

    def test_update_status(self, tmp_path):
        store = SunoTasks(tmp_path / "tasks")
        store.save(_make_record("task-1", status="PENDING"))
        store.update("task-1", status="SUCCESS")
        assert store["task-1"]["status"] == "SUCCESS"

    def test_update_response(self, tmp_path):
        store = SunoTasks(tmp_path / "tasks")
        store.save(_make_record("task-1"))
        store.update("task-1", response={"sunoData": [{"id": "clip-1"}]})
        assert store["task-1"]["response"]["sunoData"][0]["id"] == "clip-1"

    def test_update_bumps_updated_at(self, tmp_path):
        store = SunoTasks(tmp_path / "tasks")
        store.save(_make_record("task-1"))
        old_ts = store["task-1"]["updated_at"]
        time.sleep(0.01)
        store.update("task-1", status="SUCCESS")
        assert store["task-1"]["updated_at"] >= old_ts

    def test_repr(self, tmp_path):
        store = SunoTasks(tmp_path / "tasks")
        r = repr(store)
        assert "SunoTasks" in r
        assert "n=0" in r

    def test_persisted_as_json_files(self, tmp_path):
        root = tmp_path / "tasks"
        store = SunoTasks(root)
        store.save(_make_record("my-task"))
        files = list(root.glob("*.json"))
        assert len(files) == 1
        assert files[0].stem == "my-task"
        data = json.loads(files[0].read_text())
        assert data["task_id"] == "my-task"


# ---------------------------------------------------------------------------
# Filtered views
# ---------------------------------------------------------------------------


class TestSunoTasksFilteredViews:

    def _populate(self, store):
        """Add a mix of tasks with different statuses and times."""
        now = datetime.now(timezone.utc)
        records = [
            _make_record("t1", operation="generate", status="SUCCESS"),
            _make_record("t2", operation="generate", status="PENDING"),
            _make_record("t3", operation="upload_extend", status="CREATE_TASK_FAILED"),
            _make_record("t4", operation="generate", status="SUCCESS"),
            _make_record("t5", operation="upload_cover", status="GENERATE_AUDIO_FAILED"),
        ]
        # Stagger created_at so ordering is deterministic
        for i, rec in enumerate(records):
            rec["created_at"] = (now - timedelta(hours=len(records) - i)).isoformat()
        for rec in records:
            store.save(rec)

    def test_last_n(self, tmp_path):
        store = SunoTasks(tmp_path / "tasks")
        self._populate(store)
        view = store.last(3)
        keys = list(view)
        assert len(keys) == 3
        # newest first
        assert keys[0] == "t5"
        assert keys[1] == "t4"
        assert keys[2] == "t3"

    def test_last_more_than_total(self, tmp_path):
        store = SunoTasks(tmp_path / "tasks")
        self._populate(store)
        assert len(store.last(100)) == 5

    def test_status_filter(self, tmp_path):
        store = SunoTasks(tmp_path / "tasks")
        self._populate(store)
        successes = store.status("SUCCESS")
        assert set(successes) == {"t1", "t4"}

    def test_status_case_insensitive(self, tmp_path):
        store = SunoTasks(tmp_path / "tasks")
        self._populate(store)
        assert set(store.status("success")) == {"t1", "t4"}
        assert set(store.status("pending")) == {"t2"}

    def test_failed(self, tmp_path):
        store = SunoTasks(tmp_path / "tasks")
        self._populate(store)
        failed = store.failed()
        assert set(failed) == {"t3", "t5"}

    def test_pending(self, tmp_path):
        store = SunoTasks(tmp_path / "tasks")
        self._populate(store)
        assert set(store.pending()) == {"t2"}

    def test_succeeded(self, tmp_path):
        store = SunoTasks(tmp_path / "tasks")
        self._populate(store)
        assert set(store.succeeded()) == {"t1", "t4"}

    def test_since_hours(self, tmp_path):
        store = SunoTasks(tmp_path / "tasks")
        self._populate(store)
        # All tasks are within the last 6 hours
        assert len(store.since(hours=6)) == 5
        # t5 is 1h ago, t4 is 2h ago, t3 is 3h ago, etc.
        # Only t5 is strictly within 1.5 hours
        recent = store.since(hours=1, minutes=30)
        assert "t5" in recent
        assert "t3" not in recent

    def test_filtered_view_getitem(self, tmp_path):
        store = SunoTasks(tmp_path / "tasks")
        self._populate(store)
        successes = store.status("SUCCESS")
        assert successes["t1"]["status"] == "SUCCESS"
        with pytest.raises(KeyError):
            successes["t2"]  # t2 is PENDING, not SUCCESS

    def test_filtered_view_repr(self, tmp_path):
        store = SunoTasks(tmp_path / "tasks")
        self._populate(store)
        r = repr(store.failed())
        assert "filtered view" in r
        assert "2 tasks" in r


# ---------------------------------------------------------------------------
# Record helpers
# ---------------------------------------------------------------------------


class TestRecordHelpers:

    def test_make_record(self):
        r = _make_record(
            "tid-1",
            operation="generate",
            request_params={"prompt": "jazz"},
            status="PENDING",
        )
        assert r["task_id"] == "tid-1"
        assert r["operation"] == "generate"
        assert r["status"] == "PENDING"
        assert r["request_params"]["prompt"] == "jazz"
        assert r["created_at"]
        assert r["updated_at"]

    def test_update_record(self):
        r = _make_record("tid-1")
        old_ts = r["updated_at"]
        time.sleep(0.01)
        _update_record(r, status="SUCCESS", response={"data": 42})
        assert r["status"] == "SUCCESS"
        assert r["response"]["data"] == 42
        assert r["updated_at"] >= old_ts


# ---------------------------------------------------------------------------
# Adapter integration: automatic recording
# ---------------------------------------------------------------------------


class TestAdapterTaskRecording:
    """Test that Adapter methods automatically save/update the task store."""

    def _make_adapter(self, mock_make_session, tmp_path, *, response_json):
        mock_session = MagicMock()
        mock_resp = MagicMock()
        mock_resp.json.return_value = response_json
        mock_session.post.return_value = mock_resp
        mock_session.get.return_value = mock_resp
        mock_make_session.return_value = mock_session

        store = SunoTasks(tmp_path / "tasks")
        adapter = Adapter(PLATFORM_CONFIG, task_store=store)
        return adapter, store, mock_session

    @patch("arioso.platforms._base_adapter.make_session")
    def test_generate_records_task(self, mock_make_session, tmp_path):
        adapter, store, _ = self._make_adapter(
            mock_make_session,
            tmp_path,
            response_json={"code": 200, "data": {"taskId": "gen-001"}},
        )
        songs = adapter.generate("pop song", callback_url=CALLBACK_URL)
        assert len(songs) == 1
        assert songs[0].id == "gen-001"
        assert "gen-001" in store
        assert store["gen-001"]["operation"] == "generate"
        assert store["gen-001"]["status"] == "PENDING"

    @patch("arioso.platforms._base_adapter.make_session")
    def test_generate_no_taskid_skips_recording(self, mock_make_session, tmp_path):
        """When the API returns immediate results (no taskId), no store write."""
        adapter, store, _ = self._make_adapter(
            mock_make_session,
            tmp_path,
            response_json=[
                {"id": "s1", "audio_url": "https://cdn.example.com/s1.mp3"},
            ],
        )
        songs = adapter.generate("jazz", callback_url=CALLBACK_URL)
        assert len(songs) == 1
        assert len(store) == 0  # no task_id means no record

    @patch("arioso.platforms._base_adapter.make_session")
    def test_get_status_updates_store(self, mock_make_session, tmp_path):
        # First generate to create the record
        adapter, store, mock_session = self._make_adapter(
            mock_make_session,
            tmp_path,
            response_json={"code": 200, "data": {"taskId": "gen-002"}},
        )
        adapter.generate("rock", callback_url=CALLBACK_URL)
        assert store["gen-002"]["status"] == "PENDING"

        # Now mock get_status response
        status_resp = MagicMock()
        status_resp.json.return_value = {
            "code": 200,
            "data": {
                "taskId": "gen-002",
                "status": "SUCCESS",
                "response": {
                    "sunoData": [
                        {
                            "id": "clip-1",
                            "title": "Rock Song",
                            "audioUrl": "https://cdn.example.com/clip1.mp3",
                            "duration": 120.0,
                        }
                    ]
                },
            },
        }
        mock_session.get.return_value = status_resp

        songs = adapter.get_status("gen-002")
        assert len(songs) == 1
        assert songs[0].status == "complete"
        # Store should be updated
        assert store["gen-002"]["status"] == "SUCCESS"

    @patch("arioso.platforms._base_adapter.make_session")
    def test_upload_extend_records_task(self, mock_make_session, tmp_path):
        adapter, store, _ = self._make_adapter(
            mock_make_session,
            tmp_path,
            response_json={"code": 200, "data": {"taskId": "ext-001"}},
        )
        songs = adapter.upload_extend(
            "https://example.com/audio.mp3",
            callback_url=CALLBACK_URL,
        )
        assert "ext-001" in store
        assert store["ext-001"]["operation"] == "upload_extend"

    @patch("arioso.platforms._base_adapter.make_session")
    def test_upload_cover_records_task(self, mock_make_session, tmp_path):
        adapter, store, _ = self._make_adapter(
            mock_make_session,
            tmp_path,
            response_json={"code": 200, "data": {"taskId": "cov-001"}},
        )
        songs = adapter.upload_cover(
            "https://example.com/audio.mp3",
            callback_url=CALLBACK_URL,
        )
        assert "cov-001" in store
        assert store["cov-001"]["operation"] == "upload_cover"
