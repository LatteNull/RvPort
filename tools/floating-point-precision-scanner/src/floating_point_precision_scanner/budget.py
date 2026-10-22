"""统一、可注入且确定性的扫描预算协调。"""

from __future__ import annotations

import os
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ResourceSample:
    cpu_seconds: float
    rss_bytes: int


@dataclass(frozen=True, slots=True)
class BudgetFrontier:
    budget: str
    limit: int | float
    used: int | float
    scope: str
    frontier: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "budget": self.budget,
            "limit": self.limit,
            "used": self.used,
            "scope": self.scope,
            "frontier": self.frontier,
        }


class BudgetExceeded(RuntimeError):
    def __init__(self, item: BudgetFrontier) -> None:
        self.item = item
        super().__init__(item.budget)


def resource_limits_supported() -> bool:
    """Whether child CPU/address-space limits can be enforced on this platform."""
    return os.name != "nt"


def _sample_process() -> ResourceSample:
    rss = 0
    try:
        resource_module: Any = __import__("resource")
        own = resource_module.getrusage(resource_module.RUSAGE_SELF)
        children = resource_module.getrusage(resource_module.RUSAGE_CHILDREN)
        rss = max(int(own.ru_maxrss), int(children.ru_maxrss))
        # Linux reports KiB, macOS reports bytes. The locked validation host is Linux.
        if rss and rss < 1 << 40:
            rss *= 1024
        cpu = float(own.ru_utime + own.ru_stime + children.ru_utime + children.ru_stime)
    except (ImportError, OSError, ValueError):
        rss = 0
        cpu = time.process_time()
    return ResourceSample(cpu, rss)


class BudgetCoordinator:
    """One request-wide deadline plus deterministic logical counters."""

    def __init__(
        self,
        limits: Mapping[str, int | float],
        *,
        clock: Callable[[], float] = time.monotonic,
        sampler: Callable[[], ResourceSample] = _sample_process,
    ) -> None:
        self.limits = dict(limits)
        self._clock = clock
        self._sampler = sampler
        self._started = clock()
        self._initial = sampler()
        self._used: dict[str, int | float] = {}
        self._frontiers: dict[str, BudgetFrontier] = {}

    def remaining_wall(self, fallback: float) -> float:
        limit = float(self.limits.get("wall_seconds", fallback))
        remaining = limit - (self._clock() - self._started)
        if remaining <= 0:
            self._raise("wall_seconds", limit, limit, "request", None)
        return min(fallback, remaining)

    def remaining_cpu(self, fallback: float) -> float:
        if "cpu_seconds" not in self.limits:
            return fallback
        used = max(0.0, self._sampler().cpu_seconds - self._initial.cpu_seconds)
        limit = float(self.limits["cpu_seconds"])
        remaining = limit - used
        if remaining <= 0:
            self._raise("cpu_seconds", limit, limit, "request", None)
        return min(fallback, remaining)

    def check_resources(self, scope: str, frontier: str | None = None) -> None:
        if "wall_seconds" in self.limits:
            elapsed = self._clock() - self._started
            limit = float(self.limits["wall_seconds"])
            if elapsed >= limit:
                self._raise("wall_seconds", limit, limit, scope, frontier)
        sample = self._sampler()
        if "cpu_seconds" in self.limits:
            used = max(0.0, sample.cpu_seconds - self._initial.cpu_seconds)
            limit = float(self.limits["cpu_seconds"])
            if used > limit:
                self._raise("cpu_seconds", limit, limit, scope, frontier)
        if "max_memory_bytes" in self.limits and sample.rss_bytes:
            limit = int(self.limits["max_memory_bytes"])
            if sample.rss_bytes > limit:
                self._raise("max_memory_bytes", limit, limit, scope, frontier)

    def consume(
        self,
        budget: str,
        amount: int | float = 1,
        *,
        scope: str,
        frontier: str | None = None,
    ) -> int | float:
        used = self._used.get(budget, 0) + amount
        self._used[budget] = used
        limit = self.limits.get(budget)
        if limit is not None and used > limit:
            self._raise(budget, limit, used, scope, frontier)
        return used

    def record_frontier(
        self,
        budget: str,
        *,
        scope: str,
        frontier: str | None,
        used: int | float | None = None,
    ) -> BudgetFrontier:
        limit = self.limits[budget]
        item = BudgetFrontier(budget, limit, used if used is not None else limit, scope, frontier)
        self._frontiers[budget] = item
        return item

    def snapshot(self) -> dict[str, Any]:
        stable_limits = {
            key: self.limits[key]
            for key in sorted(self.limits)
            if key not in {"wall_seconds", "cpu_seconds", "max_memory_bytes"}
        }
        resource_limits = {
            key: self.limits[key]
            for key in ("wall_seconds", "cpu_seconds", "max_memory_bytes")
            if key in self.limits
        }
        return {
            "limits": {**resource_limits, **stable_limits},
            "logical_used": {key: self._used[key] for key in sorted(self._used)},
            "frontiers": [self._frontiers[key].to_dict() for key in sorted(self._frontiers)],
        }

    def _raise(
        self,
        budget: str,
        limit: int | float,
        used: int | float,
        scope: str,
        frontier: str | None,
    ) -> None:
        item = BudgetFrontier(budget, limit, used, scope, frontier)
        self._frontiers[budget] = item
        raise BudgetExceeded(item)
