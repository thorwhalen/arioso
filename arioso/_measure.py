"""Measure processes' memory and the machine's available memory, with the standard library.

Comparing local models is a measurement, and the obvious tool misses most of it on Apple
Silicon: ``resource.getrusage().ru_maxrss`` counts resident pages, not the Metal (GPU)
allocations that hold a model's weights and activations. The figure that does count them is
the process's *physical footprint*, which ``/usr/bin/time -l`` prints as "peak memory
footprint". It comes from ``proc_pid_rusage`` in ``libproc``, called here through ``ctypes``
so it works on any live process, including the worker processes a local runtime keeps
(:mod:`arioso._isolated`), not only on a child that has exited.

- :func:`peak_memory` / :func:`current_memory`: one live process's lifetime peak / current
  memory, in bytes (macOS: physical footprint; Linux: ``VmHWM`` / ``VmRSS``).
- :func:`descendants`: the live process ids under a process (``libproc`` on macOS, ``/proc``
  on Linux: no process is started to find them).
- :func:`available_memory`: what the machine can still give without swapping, in bytes.
- :class:`PeakSampler`: the peak memory of the processes a block of code starts, including
  short-lived ones.

Every function returns ``None`` (or an empty list) rather than raising when the platform
cannot say, as on Windows.
"""

from __future__ import annotations

import ctypes
import ctypes.util
import os
import re
import subprocess
import sys
import threading
from functools import lru_cache
from typing import Optional

#: ``RUSAGE_INFO_V4`` from ``<sys/resource.h>``: the first flavour carrying the lifetime peak.
_RUSAGE_INFO_V4 = 4


class _RusageInfoV4(ctypes.Structure):
    """``struct rusage_info_v4`` (``<sys/resource.h>``, macOS 10.14+), field for field."""

    _fields_ = [("ri_uuid", ctypes.c_uint8 * 16)] + [
        (name, ctypes.c_uint64)
        for name in (
            "ri_user_time", "ri_system_time", "ri_pkg_idle_wkups", "ri_interrupt_wkups",
            "ri_pageins", "ri_wired_size", "ri_resident_size", "ri_phys_footprint",
            "ri_proc_start_abstime", "ri_proc_exit_abstime", "ri_child_user_time",
            "ri_child_system_time", "ri_child_pkg_idle_wkups", "ri_child_interrupt_wkups",
            "ri_child_pageins", "ri_child_elapsed_abstime", "ri_diskio_bytesread",
            "ri_diskio_byteswritten", "ri_cpu_time_qos_default",
            "ri_cpu_time_qos_maintenance", "ri_cpu_time_qos_background",
            "ri_cpu_time_qos_utility", "ri_cpu_time_qos_legacy",
            "ri_cpu_time_qos_user_initiated", "ri_cpu_time_qos_user_interactive",
            "ri_billed_system_time", "ri_serviced_system_time", "ri_logical_writes",
            "ri_lifetime_max_phys_footprint", "ri_instructions", "ri_cycles",
            "ri_billed_energy", "ri_serviced_energy", "ri_interval_max_phys_footprint",
            "ri_runnable_time",
        )
    ]  # fmt: skip


@lru_cache(maxsize=1)
def _libproc():
    if sys.platform != "darwin":
        return None
    path = ctypes.util.find_library("proc")
    return ctypes.CDLL(path) if path else None


def _darwin_rusage(pid: int) -> Optional[_RusageInfoV4]:
    lib = _libproc()
    if lib is None:
        return None
    info = _RusageInfoV4()
    if lib.proc_pid_rusage(int(pid), _RUSAGE_INFO_V4, ctypes.byref(info)) != 0:
        return None  # no such process, or not ours to read
    return info


def _linux_status_kb(pid: int, field: str) -> Optional[int]:
    try:
        with open(f"/proc/{pid}/status") as f:
            status = f.read()
    except OSError:
        return None
    m = re.search(rf"^{field}:\s+(\d+)\s+kB", status, re.MULTILINE)
    return int(m.group(1)) * 1024 if m else None


def peak_memory(pid: Optional[int] = None) -> Optional[int]:
    """The lifetime peak memory of a live process (default: this one), in bytes.

    On macOS the peak physical footprint, which includes Metal (GPU) allocations; on Linux
    the peak resident set (``VmHWM``). ``None`` when the platform cannot say or the process
    is gone.

    >>> isinstance(peak_memory(), (int, type(None)))
    True
    """
    pid = os.getpid() if pid is None else pid
    if sys.platform == "darwin":
        info = _darwin_rusage(pid)
        return int(info.ri_lifetime_max_phys_footprint) if info else None
    if sys.platform.startswith("linux"):
        return _linux_status_kb(pid, "VmHWM")
    return None


def current_memory(pid: Optional[int] = None) -> Optional[int]:
    """The memory a live process holds now, in bytes (macOS: physical footprint; Linux: RSS)."""
    pid = os.getpid() if pid is None else pid
    if sys.platform == "darwin":
        info = _darwin_rusage(pid)
        return int(info.ri_phys_footprint) if info else None
    if sys.platform.startswith("linux"):
        return _linux_status_kb(pid, "VmRSS")
    return None


def _children(pid: int) -> list[int]:
    if sys.platform == "darwin":
        lib = _libproc()
        if lib is None:
            return []
        buf = (ctypes.c_int * 4096)()
        n = lib.proc_listchildpids(int(pid), buf, ctypes.sizeof(buf))
        return [p for p in buf[: max(n, 0)] if p > 0]
    if sys.platform.startswith("linux"):
        kids = []
        for entry in os.listdir("/proc"):
            if not entry.isdigit():
                continue
            try:
                with open(f"/proc/{entry}/stat") as f:
                    stat = f.read()
            except OSError:
                continue  # exited while we looked
            # the command name may hold spaces and parentheses: ppid follows the last ')'
            fields = stat[stat.rfind(")") + 2 :].split()
            if len(fields) > 1 and int(fields[1]) == pid:
                kids.append(int(entry))
        return kids
    return []


def descendants(pid: Optional[int] = None) -> list[int]:
    """The live process ids below ``pid`` (default: this process), children first.

    Starts no process: ``proc_listchildpids`` on macOS, ``/proc/*/stat`` on Linux; an empty
    list elsewhere.
    """
    pid = os.getpid() if pid is None else pid
    found, frontier = [], [pid]
    while frontier:
        children = _children(frontier.pop(0))
        found += children
        frontier += children
    return found


def available_memory() -> Optional[int]:
    """What the machine can hand out without swapping, in bytes (``None`` if unknown).

    macOS: free, inactive, speculative and purgeable pages from ``vm_stat``; Linux:
    ``MemAvailable`` from ``/proc/meminfo``.
    """
    if sys.platform == "darwin":
        try:
            out = subprocess.run(["vm_stat"], capture_output=True, text=True).stdout
        except OSError:
            return None
        page = re.search(r"page size of (\d+) bytes", out)
        pages = {
            k.strip().lower(): int(v)
            for k, v in re.findall(r"^(Pages [^:]+):\s+(\d+)\.", out, re.MULTILINE)
        }
        keys = ("pages free", "pages inactive", "pages speculative", "pages purgeable")
        if not page or not any(k in pages for k in keys):
            return None
        return int(page.group(1)) * sum(pages.get(k, 0) for k in keys)
    if sys.platform.startswith("linux"):
        try:
            with open("/proc/meminfo") as f:
                m = re.search(r"^MemAvailable:\s+(\d+)\s+kB", f.read(), re.MULTILINE)
        except OSError:
            return None
        return int(m.group(1)) * 1024 if m else None
    return None


def _children_maxrss() -> int:
    """The largest resident set of any waited-for child process, in bytes (0 if unknown)."""
    try:
        import resource
    except ImportError:  # Windows
        return 0
    rss = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    return rss if sys.platform == "darwin" else rss * 1024  # Linux reports kB


class PeakSampler:
    """The peak memory of this process and of the processes it starts, while in use.

    A model run in a short-lived child (one process per take) has exited, and its peak is
    gone, by the time anyone asks. So a background thread samples the live descendants
    every ``interval`` seconds, keeping two figures, and ``peak_descendants`` is the larger:

    - the largest lifetime peak of any one descendant (exact for that process, provided it
      was seen alive at least once);
    - the largest sum of the descendants' *current* memory at one tick (their concurrent
      use, as sampled; a spike between two ticks is missed).

    Exited children's resident peaks (``RUSAGE_CHILDREN``, which misses Metal allocations)
    are a floor under it. A sampling error is kept in ``errors`` and never raised.

    >>> with PeakSampler(interval=0.05) as sampler:
    ...     _ = bytearray(10 * 2**20)
    >>> sampler.peak_self is None or sampler.peak_self > 0
    True
    """

    def __init__(self, *, interval: float = 0.5):
        self.interval = interval
        self.peak_self: Optional[int] = None
        self.peak_descendants: Optional[int] = None
        self.errors: list[str] = []
        self._stop = threading.Event()
        self._thread = None

    def sample(self) -> None:
        """Take one sample now (the thread calls this; so does ``__exit__``)."""
        try:
            pids = descendants()
            now = sum(current_memory(p) or 0 for p in pids)
            single = max((peak_memory(p) or 0 for p in pids), default=0)
        except Exception as error:  # noqa: BLE001 - a measurement must not break the run
            if len(self.errors) < 10:
                self.errors.append(f"{type(error).__name__}: {error}")
            return
        best = max(now, single)
        if best and best > (self.peak_descendants or 0):
            self.peak_descendants = best

    def __enter__(self) -> PeakSampler:
        self._stop.clear()

        def run():
            while not self._stop.wait(self.interval):
                self.sample()

        self._thread = threading.Thread(target=run, name="PeakSampler", daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *exc) -> None:
        self._stop.set()
        self._thread.join()
        self.sample()
        floor = _children_maxrss()
        if floor > (self.peak_descendants or 0):
            self.peak_descendants = floor
        self.peak_self = peak_memory()
