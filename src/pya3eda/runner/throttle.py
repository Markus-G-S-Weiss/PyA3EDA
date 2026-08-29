"""CPU-core budget policy and throttler for batch job submission.

A run submits many jobs, but a host (or a politeness cap on a cluster) has a
core budget. This module is the single source of truth for that budget:
:func:`resolve_budget` turns the user's ``--max-cores`` (or its absence) into
a backend-aware budget, :func:`ensure_job_fits` rejects an impossible
options/budget pair before anything is submitted, and :class:`Throttler`
tracks each active job's core demand, blocking new submissions until the
budget allows. Polling delegates to a caller-supplied ``is_finished`` callable
(DIP) so it works for both local processes and SLURM job IDs, and so tests can
inject a fake.

Ported from ChemRefine's two-resource throttler, reduced to the single CPU
budget pya3eda needs (Q-Chem has no GPU path).
"""

from __future__ import annotations

import logging
import os
import time
from collections.abc import Callable

from pya3eda.errors import RunOptionError, ThrottleTimeoutError

log = logging.getLogger(__name__)

IsFinishedFn = Callable[[str], bool]


def _usable_cpus() -> int:
    """CPUs this process may actually use (affinity/cgroup-aware fallback chain)."""
    try:
        return len(os.sched_getaffinity(0))
    except (AttributeError, OSError):
        return os.cpu_count() or 1


def resolve_budget(max_cores: int | None, *, backend_name: str) -> int | None:
    """Resolve ``--max-cores`` into a core budget for *backend_name*.

    An explicit value is validated (>= 1) and used as-is. Without one, the
    local backend is capped at the host's usable cores (running unbounded
    would oversubscribe the machine), while SLURM gets ``None`` — no cap —
    because the scheduler manages cluster resources and the submitting host's
    core count says nothing about them.
    """
    if max_cores is not None:
        if max_cores < 1:
            raise RunOptionError(f"max_cores must be >= 1; got {max_cores}")
        return max_cores
    return _usable_cpus() if backend_name == "local" else None


def ensure_job_fits(cores_needed: int, budget: int | None) -> None:
    """Reject up front a single job that could never fit inside *budget*.

    Cores-per-job is fixed by the run options, so an oversized job is a
    contradictory option pair — failing here means zero jobs are submitted,
    instead of raising mid-run or silently oversubscribing.
    """
    if budget is not None and cores_needed > budget:
        raise RunOptionError(
            f"a single job needs {cores_needed} cores but the budget is {budget}; "
            f"raise --max-cores or lower --cpus/--parallel"
        )


class Throttler:
    """Track active jobs against a CPU-core budget (``None`` = unbounded)."""

    def __init__(self, *, max_cores: int | None, poll_interval: float = 10.0) -> None:
        """Create a throttler with a ``max_cores`` budget and poll cadence.

        ``max_cores=None`` disables the cap: the throttler then only tracks
        in-flight jobs (for :meth:`poll` / :meth:`wait_all`) without ever
        blocking a submission.
        """
        if max_cores is not None and max_cores < 1:
            raise RunOptionError(f"max_cores must be >= 1; got {max_cores}")
        self.max_cores = max_cores
        self.poll_interval = poll_interval
        self._active: dict[str, int] = {}  # job_id -> cores

    @property
    def cores_in_use(self) -> int:
        """Sum of the core demand of all currently active jobs."""
        return sum(self._active.values())

    @property
    def active_jobs(self) -> tuple[str, ...]:
        """Snapshot of active job IDs."""
        return tuple(self._active)

    def register(self, job_id: str, cores: int) -> None:
        """Mark a newly-submitted job as active, charging ``cores``."""
        if cores < 1:
            raise RunOptionError(f"cores must be >= 1; got {cores}")
        self._active[job_id] = cores

    def has_room(self, cores: int) -> bool:
        """Whether ``cores`` more can be allocated right now without waiting."""
        return self.max_cores is None or self.cores_in_use + cores <= self.max_cores

    def wait_for_room(
        self,
        cores_needed: int,
        *,
        is_finished: IsFinishedFn,
        max_wait_seconds: float | None = None,
    ) -> None:
        """Block until ``cores_needed`` cores can be allocated.

        Reaps finished jobs each iteration via ``is_finished``; sleeps
        ``poll_interval`` between checks. Raises :class:`ThrottleTimeoutError`
        if ``max_wait_seconds`` elapses first. The over-budget check is an
        invariant guard — callers reject an oversized job up front via
        :func:`ensure_job_fits` before submitting anything.
        """
        if self.max_cores is not None and cores_needed > self.max_cores:
            raise RunOptionError(
                f"requested {cores_needed} cores exceeds the total budget {self.max_cores}"
            )
        deadline = time.monotonic() + max_wait_seconds if max_wait_seconds is not None else None
        while True:
            self.poll(is_finished)
            if self.has_room(cores_needed):
                return
            if deadline is not None and time.monotonic() >= deadline:
                raise ThrottleTimeoutError(
                    f"timed out after {max_wait_seconds}s waiting for {cores_needed} cores"
                )
            log.debug(
                "waiting on budget: %d+%d/%d", self.cores_in_use, cores_needed, self.max_cores
            )
            time.sleep(self.poll_interval)

    def wait_all(
        self,
        *,
        is_finished: IsFinishedFn,
        max_wait_seconds: float | None = None,
    ) -> None:
        """Block until every active job has finished."""
        deadline = time.monotonic() + max_wait_seconds if max_wait_seconds is not None else None
        while self._active:
            self.poll(is_finished)
            if not self._active:
                return
            if deadline is not None and time.monotonic() >= deadline:
                raise ThrottleTimeoutError(
                    f"timed out after {max_wait_seconds}s waiting for all jobs to finish"
                )
            time.sleep(self.poll_interval)

    def poll(self, is_finished: IsFinishedFn) -> list[str]:
        """Reap every active job that ``is_finished`` reports done; return their ids.

        Frees each finished job's cores. Used by the dependency-aware pipeline to
        react to completions; ``wait_for_room`` / ``wait_all`` call it internally.
        """
        finished: list[str] = []
        for jid in list(self._active):
            if is_finished(jid):
                cores = self._active.pop(jid)
                finished.append(jid)
                log.info("job %s finished, freed %d cores", jid, cores)
        return finished
