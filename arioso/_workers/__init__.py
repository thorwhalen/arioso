"""Worker files: run by :class:`arioso._isolated.Worker` inside a runtime's own environment.

Each ``<name>_worker.py`` is a :mod:`ps.isolated` adapter file: ``load(**init) -> state``
(the loaded model, or a cache of them) and one operation per kind of render,
``op(state, **request) -> dict``. They import nothing from arioso, since the environment
they run in need not have it, and this folder is put on the worker's ``sys.path``, so
their names end in ``_worker`` to shadow no library.
"""
