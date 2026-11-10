"""Measure a process's peak memory and the machine's available memory, with the standard library.

Comparing local models is a measurement, and the obvious tool misses most of it on Apple
Silicon: ``resource.getrusage().ru_maxrss`` counts resident pages, not the Metal (GPU)
allocations that hold a model's weights and activations. The figure that does count them is
the process's *physical footprint*, which ``/usr/bin/time -l`` prints as "peak memory
footprint". It comes from ``proc_pid_rusage`` in ``libproc``, called here through ``ctypes``
so it works on any live process, including the worker processes a local runtime keeps
(:mod:`arioso._isolated`), not only on a child that has exited.

- :func:`peak_memory`: the lifetime peak of one live process, in bytes (macOS: peak physical
  footprint; Linux: ``VmHWM``; elsewhere ``None``).
- :func:`descendants`: the live process ids under a process.
- :func:`available_memory`: what the machine can still give without swapping, in bytes.

Every function returns ``None`` rather than raising when the platform cannot say.
"""

from __future__ import annotations

import ctypes
import ctypes.util
import os
import re
import subprocess
import sys
from functools import lru_cache
from typing import Optional

#: ``RUSAGE_INFO_V4`` from ``<sys/resource.h>``: the first flavour carrying the lifetime peak.
_RUSAGE_INFO_V4 = 4


class _RusageInfoV4(ctypes.Structure):
    """``struct rusage_info_v4`` (``<sys/resource.h>``, macOS 10.14+)."""

    _fields_ = (
        [("ri_uuid", ctypes.c_uint8 * 16)]
        + [
            (name, ctypes.c_uint64)
            for name in (
                "ri_user_time",
                "ri_system_time",
                "ri_pkg_idle_wkups",
                "ri_interrupt_wkups",
                "ri_pageins",
                "ri_wired_size",
                "ri_resident_size",
                "ri_phys_footprint",
                "ri_proc_start_abstime",
                "ri_proc_exit_abstime",
                "ri_child_user_time",
                "ri_child_system_time",
                "ri_child_pkg_idle_wkups",
                "ri_child_interrupt_wkups",
                "ri_child_pageins",
                "ri_child_elapsed_abstime",
                "ri_diskio_bytesread",
                "ri_diskio_byteswritten",
                "ri_cpu_time_qos_default",
                "ri_cpu_time_qos_maintenance",
                "ri_cpu_time_qos_background",
                "ri_cpu_time_qos_utility",
                "ri_cpu_time_qos_legacy",
                "ri_cpu_time_qos_user_initiated",
                "ri_cpu_time_qos_user_interactive",
                "ri_billed_system_time",
                "ri_serviced_system_time",
                "ri_logical_writes",
                "ri_lifetime_max_phys_footprint",
                "ri_instructions",
                "ri_cycles",
                "ri_billed_energy",
                "ri_serviced_energy",
                "ri_interval_max_phys_footprint",
                "ri_runnable_time",
            )
        ]
        + [("ri_reserved", ctypes.c_uint64 * 11)]
    )


@lru_cache(maxsize=1)
def _libproc():
    path = ctypes.util.find_library("proc")
    return ctypes.CDLL(path) if path else None


def _darwin_peak(pid: int) -> Optional[int]:
    lib = _libproc()
    if lib is None:
        return None
    info = _RusageInfoV4()
    if lib.proc_pid_rusage(int(pid), _RUSAGE_INFO_V4, ctypes.byref(info)) != 0:
        return None  # no such process, or not ours to read
    return int(info.ri_lifetime_max_phys_footprint)


def _linux_peak(pid: int) -> Optional[int]:
    try:
        with open(f"/proc/{pid}/status") as f:
            status = f.read()
    except OSError:
        return None
    m = re.search(r"^VmHWM:\s+(\d+)\s+kB", status, re.MULTILINE)
    return int(m.group(1)) * 1024 if m else None


def peak_memory(pid: Optional[int] = None) -> Optional[int]:
    """The lifetime peak memory of a live process (default: this one), in bytes.

    On macOS this is the peak physical footprint, which includes Metal (GPU) allocations;
    on Linux the peak resident set (``VmHWM``). ``None`` when the platform cannot say or
    the process is gone.

    >>> isinstance(peak_memory(), (int, type(None)))
    True
    """
    pid = os.getpid() if pid is None else pid
    if sys.platform == "darwin":
        return _darwin_peak(pid)
    if sys.platform.startswith("linux"):
        return _linux_peak(pid)
    return None


def descendants(pid: Optional[int] = None) -> list[int]:
    """The live process ids below ``pid`` (default: this process), children first.

    Uses ``pgrep -P``, present on macOS and Linux; an empty list where it is missing.
    """
    pid = os.getpid() if pid is None else pid
    found, frontier = [], [pid]
    while frontier:
        parent = frontier.pop(0)
        try:
            out = subprocess.run(
                ["pgrep", "-P", str(parent)], capture_output=True, text=True
            ).stdout
        except OSError:
            return found
        children = [int(p) for p in out.split()]
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
    """The largest resident set of any waited-for child process, in bytes (0 if none or unknown)."""
    try:
        import resource
    except ImportError:  # Windows
        return 0

    rss = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    return rss if sys.platform == "darwin" else rss * 1024  # Linux reports kB


class PeakSampler:
    """Track the peak memory of this process and of the processes it starts, while in use.

    A model run in a short-lived child process (one process per take) has exited, and its
    peak is gone, by the time anyone asks. So a background thread samples, every
    ``interval`` seconds, the lifetime peaks of the live descendants and keeps the largest
    sum seen at one moment (the concurrent peak, not a sum over processes that never
    overlapped). Exited children's resident peaks (``RUSAGE_CHILDREN``, which misses Metal
    allocations) are a floor under it.

    >>> with PeakSampler(interval=0.05) as sampler:
    ...     _ = bytearray(10 * 2**20)
    >>> sampler.peak_self is None or sampler.peak_self > 0
    True
    """

    def __init__(self, *, interval: float = 0.25):
        self.interval = interval
        self.peak_self: Optional[int] = None
        self.peak_descendants: Optional[int] = None
        self._stop = None
        self._thread = None

    def sample(self) -> None:
        """Take one sample now (the thread calls this; so does ``__exit__``)."""
        kids = [peak_memory(pid) for pid in descendants()]
        total = sum(k for k in kids if k)
        if total and total > (self.peak_descendants or 0):
            self.peak_descendants = total

    def __enter__(self) -> "PeakSampler":
        import threading

        self._stop = threading.Event()

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
