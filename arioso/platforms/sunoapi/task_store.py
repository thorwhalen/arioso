"""Local task store for Suno API requests.

Provides a ``collections.abc.Mapping`` interface over locally-persisted task
records, so you can list, filter, and retrieve past Suno generation requests
without depending on a (non-existent) "list all" API endpoint.

Each task is stored as a JSON file keyed by ``taskId``.  The store records
request parameters, status, timestamps, and the full API response.

Typical usage::

    from arioso.platforms.sunoapi.task_store import SunoTasks

    tasks = SunoTasks()           # uses default data dir
    tasks['5c79...be8e']          # get one task record
    list(tasks)                   # all task IDs
    len(tasks)                    # how many tasks

    # Filtered views (return new Mapping objects):
    tasks.last(20)                # last 20 by creation time
    tasks.since(hours=24)         # created in last 24 hours
    tasks.status('SUCCESS')       # only successful tasks
    tasks.status('PENDING')       # only pending tasks
    tasks.failed()                # all failed tasks
"""

import json
import time
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


# ---------------------------------------------------------------------------
# Task record helpers
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    """Return current UTC time as ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


def _make_record(
    task_id: str,
    *,
    operation: str = "",
    request_params: dict | None = None,
    status: str = "PENDING",
    response: dict | None = None,
) -> dict:
    """Create a fresh task record dict."""
    return {
        "task_id": task_id,
        "operation": operation,
        "status": status,
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
        "request_params": request_params or {},
        "response": response or {},
    }


def _update_record(record: dict, *, status: str = "", response: dict | None = None):
    """Mutate *record* in place with new status/response and bump updated_at."""
    if status:
        record["status"] = status
    if response is not None:
        record["response"] = response
    record["updated_at"] = _now_iso()


# ---------------------------------------------------------------------------
# Data directory
# ---------------------------------------------------------------------------


def _default_data_dir(*, ensure_exists: bool = True) -> Path:
    """Return ``~/.local/share/arioso/suno_tasks``."""
    from config2py import get_app_data_folder

    folder = (
        Path(get_app_data_folder("arioso", ensure_exists=ensure_exists)) / "suno_tasks"
    )
    if ensure_exists:
        folder.mkdir(parents=True, exist_ok=True)
    return folder


# ---------------------------------------------------------------------------
# Filtered view
# ---------------------------------------------------------------------------


class _FilteredTaskView(Mapping):
    """A read-only, lazily-evaluated filtered view over task records.

    Iterates the parent store and keeps only records satisfying *predicate*.
    Optionally limits the result count via *limit*.
    """

    def __init__(self, parent: "SunoTasks", predicate, *, limit: int = 0):
        self._parent = parent
        self._predicate = predicate
        self._limit = limit

    # -- internal: resolve matching keys (sorted newest-first) ---------------

    def _matching_keys(self) -> list[str]:
        keys = [k for k in self._parent if self._predicate(self._parent[k])]
        # Sort newest-first by created_at (ISO strings sort lexicographically)
        keys.sort(key=lambda k: self._parent[k].get("created_at", ""), reverse=True)
        if self._limit:
            keys = keys[: self._limit]
        return keys

    def __getitem__(self, key: str) -> dict:
        if key in self._parent and self._predicate(self._parent[key]):
            return self._parent[key]
        raise KeyError(key)

    def __iter__(self) -> Iterator[str]:
        return iter(self._matching_keys())

    def __len__(self) -> int:
        return len(self._matching_keys())

    def __repr__(self) -> str:
        n = len(self)
        return f"<SunoTasks filtered view ({n} tasks)>"


# ---------------------------------------------------------------------------
# Main store
# ---------------------------------------------------------------------------


class SunoTasks(Mapping):
    """A ``Mapping[str, dict]`` of Suno task records persisted as JSON files.

    Keys are task IDs, values are task-record dicts with fields::

        task_id, operation, status, created_at, updated_at,
        request_params, response

    The store is backed by individual ``.json`` files in *root_dir*.
    """

    def __init__(self, root_dir: str | Path | None = None):
        if root_dir is None:
            root_dir = _default_data_dir()
        self._root = Path(root_dir)
        self._root.mkdir(parents=True, exist_ok=True)

    # -- Mapping interface ---------------------------------------------------

    def __getitem__(self, task_id: str) -> dict:
        path = self._path_for(task_id)
        if not path.is_file():
            raise KeyError(task_id)
        return json.loads(path.read_text())

    def __iter__(self) -> Iterator[str]:
        for p in self._root.glob("*.json"):
            yield p.stem

    def __len__(self) -> int:
        return sum(1 for _ in self._root.glob("*.json"))

    def __contains__(self, task_id) -> bool:
        return self._path_for(task_id).is_file()

    def __repr__(self) -> str:
        return f"SunoTasks({str(self._root)!r}, n={len(self)})"

    # -- Write operations (used by the adapter, not by the user) -------------

    def save(self, record: dict) -> None:
        """Persist a task record (create or overwrite)."""
        task_id = record["task_id"]
        self._path_for(task_id).write_text(json.dumps(record, indent=2))

    def update(self, task_id: str, *, status: str = "", response: dict | None = None):
        """Update an existing record's status and/or response."""
        record = self[task_id]  # raises KeyError if missing
        _update_record(record, status=status, response=response)
        self.save(record)

    # -- Filtered views ------------------------------------------------------

    def last(self, n: int = 20) -> _FilteredTaskView:
        """Return a view of the most recent *n* tasks (newest first)."""
        return _FilteredTaskView(self, predicate=lambda _: True, limit=n)

    def since(self, *, hours: float = 0, minutes: float = 0) -> _FilteredTaskView:
        """Return tasks created within the last *hours* + *minutes*."""
        total_seconds = hours * 3600 + minutes * 60
        cutoff = datetime.now(timezone.utc).timestamp() - total_seconds

        def _recent(record):
            ts = record.get("created_at", "")
            if not ts:
                return False
            try:
                created = datetime.fromisoformat(ts).timestamp()
            except (ValueError, TypeError):
                return False
            return created >= cutoff

        return _FilteredTaskView(self, predicate=_recent)

    def status(self, status_value: str) -> _FilteredTaskView:
        """Return tasks matching *status_value* (case-insensitive)."""
        target = status_value.upper()
        return _FilteredTaskView(
            self,
            predicate=lambda r: r.get("status", "").upper() == target,
        )

    def failed(self) -> _FilteredTaskView:
        """Return all tasks with an error status."""
        from arioso.platforms.sunoapi.adapter import _ERROR_STATUSES

        return _FilteredTaskView(
            self,
            predicate=lambda r: r.get("status", "").upper() in _ERROR_STATUSES,
        )

    def pending(self) -> _FilteredTaskView:
        """Return all tasks that are still pending or in progress."""
        _in_progress = {"PENDING", "TEXT_SUCCESS", "FIRST_SUCCESS"}
        return _FilteredTaskView(
            self,
            predicate=lambda r: r.get("status", "").upper() in _in_progress,
        )

    def succeeded(self) -> _FilteredTaskView:
        """Return all tasks that completed successfully."""
        return self.status("SUCCESS")

    # -- Helpers -------------------------------------------------------------

    def _path_for(self, task_id: str) -> Path:
        # Sanitize: replace characters that aren't safe in filenames
        safe = task_id.replace("/", "_").replace("\\", "_")
        return self._root / f"{safe}.json"
