"""A Worker stand-in that runs a worker file's functions in this process.

It follows :class:`ps.isolated.Worker`'s contract: ``load(**init)`` on the first call, then
``op(state, **request)``, requests and results passed through JSON, ``None`` read as ``{}``.
So the real worker files run against fake upstream modules, with no subprocess.
"""

import contextlib
import importlib.util
import itertools
import json
import os
from pathlib import Path

_names = itertools.count()
_UNLOADED = object()


def load_worker_module(path):
    """The worker file at ``path``, imported under a fresh name (as a worker loads it)."""
    spec = importlib.util.spec_from_file_location(f"_test_worker_{next(_names)}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class InProcessWorker:
    """Records how it was built (``python``, ``adapter``, ``init``, ``env``, ``cwd``, ``stderr``)
    and what it was asked (``requests``: ``(op, request)`` pairs)."""

    def __init__(self, python, adapter, *, init=None, env=None, cwd=None, stderr="log"):
        self.python, self.adapter = str(python), Path(adapter)
        self.init, self.env, self.cwd, self.stderr = dict(init or {}), env, cwd, stderr
        self.module = load_worker_module(adapter)
        self.state, self.requests, self.closed = _UNLOADED, [], False

    def call(self, op, /, **request):
        request = json.loads(json.dumps(request))  # what can cross the pipe
        with self._in_cwd():
            if self.state is _UNLOADED:
                self.state = self.module.load(**self.init)
            self.requests.append((op, request))
            result = getattr(self.module, op)(self.state, **request)
        return json.loads(json.dumps({} if result is None else result))

    @contextlib.contextmanager
    def _in_cwd(self):
        """Run in the worker's working directory, as the real process does."""
        before = os.getcwd()
        if self.cwd:
            os.chdir(self.cwd)
        try:
            yield
        finally:
            os.chdir(before)

    def close(self):
        self.closed = True
