# arioso.platforms.sunoapi.task_store

Local task store for Suno API requests.

Provides a `collections.abc.Mapping` interface over locally-persisted task
records, so you can list, filter, and retrieve past Suno generation requests
without depending on a (non-existent) “list all” API endpoint.

Each task is stored as a JSON file keyed by `taskId`.  The store records
request parameters, status, timestamps, and the full API response.

Typical usage:

```default
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
```

### Classes

| [`SunoTasks`](#arioso.platforms.sunoapi.task_store.SunoTasks)([root_dir])   | A `Mapping[str, dict]` of Suno task records persisted as JSON files.   |
|--------------------------------------------------------------------------|------------------------------------------------------------------------|

### *class* arioso.platforms.sunoapi.task_store.SunoTasks(root_dir=None)

Bases: [`Mapping`](https://docs.python.org/3/library/collections.abc.html#collections.abc.Mapping)

A `Mapping[str, dict]` of Suno task records persisted as JSON files.

Keys are task IDs, values are task-record dicts with fields:

```default
task_id, operation, status, created_at, updated_at,
request_params, response
```

The store is backed by individual `.json` files in *root_dir*.

#### failed()

Return all tasks with an error status.

* **Return type:**
  `_FilteredTaskView`

#### last(n=20)

Return a view of the most recent *n* tasks (newest first).

* **Return type:**
  `_FilteredTaskView`

#### pending()

Return all tasks that are still pending or in progress.

* **Return type:**
  `_FilteredTaskView`

#### save(record)

Persist a task record (create or overwrite).

* **Return type:**
  [`None`](https://docs.python.org/3/library/constants.html#None)

#### since(, hours=0, minutes=0)

Return tasks created within the last *hours* + *minutes*.

* **Return type:**
  `_FilteredTaskView`

#### status(status_value)

Return tasks matching *status_value* (case-insensitive).

* **Return type:**
  `_FilteredTaskView`

#### succeeded()

Return all tasks that completed successfully.

* **Return type:**
  `_FilteredTaskView`

#### update(task_id, , status='', response=None)

Update an existing record’s status and/or response.
