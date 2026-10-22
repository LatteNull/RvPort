"""在锁定容器中生成并执行 S/M/L 扫描 workload。"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import time
from collections.abc import Callable, Mapping
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from .application import Scanner
from .benchmark import BENCHMARK_ENVIRONMENT, BENCHMARK_TIERS, evaluate_benchmark
from .canonical import semantic_digest
from .frontend import ClangFrontend
from .output import serialize_json, write_atomic


def _resource_sample() -> tuple[float, int]:
    try:
        resource_module: Any = __import__("resource")
        own = resource_module.getrusage(resource_module.RUSAGE_SELF)
        children = resource_module.getrusage(resource_module.RUSAGE_CHILDREN)
        cpu = float(own.ru_utime + own.ru_stime + children.ru_utime + children.ru_stime)
        rss = max(int(own.ru_maxrss), int(children.ru_maxrss)) * 1024
        return cpu, rss
    except (ImportError, OSError, ValueError):
        return time.process_time(), 0


def _environment_applicable(
    *,
    system: Callable[[], str] = platform.system,
    machine: Callable[[], str] = platform.machine,
    cpu_count: Callable[[], int | None] = os.cpu_count,
    memory_limit: Path = Path("/sys/fs/cgroup/memory.max"),
) -> bool:
    if system().lower() != "linux" or machine().lower() not in {
        "x86_64",
        "amd64",
    }:
        return False
    if (cpu_count() or 0) < int(str(BENCHMARK_ENVIRONMENT["vcpus"])):
        return False
    if memory_limit.is_file():
        raw = memory_limit.read_text(encoding="utf-8").strip()
        if raw != "max" and int(raw) < int(str(BENCHMARK_ENVIRONMENT["memory_bytes"])):
            return False
    return True


def _create_workload(root: Path, tier: str) -> dict[str, Any]:
    specification = BENCHMARK_TIERS[tier]
    count = int(specification["translation_units"])
    lines_per_tu = int(specification["source_lines"]) // count
    units = []
    for index in range(count):
        name = f"unit-{index:04d}.c"
        source = root / name
        lines = [f"double fp_{index}(double a, double b) {{ return a + b * {index + 1}.0; }}"]
        lines.extend(
            f"// deterministic benchmark padding {index}:{line}" for line in range(1, lines_per_tu)
        )
        source.write_text("\n".join(lines) + "\n", encoding="utf-8")
        units.append(
            {
                "file": name,
                "directory": str(root),
                "arguments": ["clang", "-std=c17", "-c", name],
            }
        )
    cache_root = root / ".fp-cache"
    return {
        "kind": "FloatingPointPrecisionScanRequest",
        "schema_version": "1.4",
        "request_id": f"benchmark-{tier}",
        "project_root": str(root),
        "source_profile": "x86_64-linux-gnu-clang21@1.0",
        "target_profile": "riscv64-linux-gnu-lp64d-clang21@1.0",
        "input": {"translation_units": units},
        "rules": {"enabled": []},
        "cache": {"mode": "read-write", "root": str(cache_root)},
        "budgets": {
            "wall_seconds": specification["wall_seconds"],
            "cpu_seconds": specification["cpu_seconds"],
            "max_memory_bytes": specification["rss_bytes"],
            "max_files": count,
            "max_result_bytes": specification["result_bytes"],
        },
    }


def _semantic_projection(result: Mapping[str, Any]) -> dict[str, Any]:
    scan = result.get("scan")
    if not isinstance(scan, Mapping):
        raise ValueError("benchmark_result_scan_missing")
    return {
        "schemaVersion": result.get("schemaVersion"),
        "status": scan.get("status"),
        "semanticDigest": scan.get("semanticDigest"),
    }


def _run_once(scanner: Scanner, request: Mapping[str, Any]) -> tuple[dict[str, float], str]:
    cpu_before, _ = _resource_sample()
    wall_before = time.perf_counter()
    result = scanner.scan(request)
    wall = time.perf_counter() - wall_before
    cpu_after, rss = _resource_sample()
    scan = result.get("scan")
    status = scan.get("status") if isinstance(scan, Mapping) else "missing"
    if status != "complete":
        raise RuntimeError(f"benchmark_scan_{status}")
    encoded = serialize_json(result)
    return (
        {
            "wall_seconds": wall,
            "cpu_seconds": max(0.0, cpu_after - cpu_before),
            "rss_bytes": float(rss),
            "result_bytes": float(len(encoded)),
        },
        semantic_digest(_semantic_projection(result)),
    )


def run_benchmarks(
    clang: Path,
    *,
    baseline: Mapping[str, Any] | None = None,
    tiers: tuple[str, ...] = ("S", "M", "L"),
) -> dict[str, Any]:
    applicable = _environment_applicable()
    results = []
    with TemporaryDirectory(prefix="fp-scanner-benchmark-") as temporary:
        base = Path(temporary)
        for tier in tiers:
            root = base / tier
            root.mkdir()
            request = _create_workload(root, tier)
            scanner = Scanner(ClangFrontend(clang))
            cold: list[dict[str, float]] = []
            hot: list[dict[str, float]] = []
            semantic_digests: list[str] = []
            cache_root = Path(str(request["cache"]["root"]))
            for _ in range(3):
                if cache_root.exists():
                    shutil.rmtree(cache_root)
                sample, digest = _run_once(scanner, request)
                cold.append(sample)
                semantic_digests.append(digest)
            for _ in range(3):
                sample, digest = _run_once(scanner, request)
                hot.append(sample)
                semantic_digests.append(digest)
            relocated_root = base / f"{tier}-relocated"
            relocated_root.mkdir()
            relocated_request = _create_workload(relocated_root, tier)
            _, relocated_digest = _run_once(Scanner(ClangFrontend(clang)), relocated_request)
            semantic_digests.append(relocated_digest)
            baseline_item = baseline.get(tier) if isinstance(baseline, Mapping) else None
            workload_digest = semantic_digest(
                {
                    "generator": "deterministic-c-family-v1",
                    "tier": tier,
                    "translation_units": BENCHMARK_TIERS[tier]["translation_units"],
                    "source_lines": BENCHMARK_TIERS[tier]["source_lines"],
                }
            )
            baseline_matches = baseline_item is None or (
                isinstance(baseline_item, Mapping)
                and baseline_item.get("workload_digest") == workload_digest
            )
            result = evaluate_benchmark(
                tier,
                cold,
                hot,
                baseline=(baseline_item if isinstance(baseline_item, Mapping) else None),
                environment_applicable=applicable,
                semantic_equal=len(set(semantic_digests)) == 1 and baseline_matches,
            )
            result["workload_digest"] = workload_digest
            results.append(result)
    return {
        "kind": "FloatingPointScannerBenchmarkResult",
        "schema_version": "1.0",
        "environment": BENCHMARK_ENVIRONMENT,
        "tiers": results,
        "passed": len(results) == len(tiers) and all(item["gates"]["passed"] for item in results),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--clang", type=Path, default=Path("/usr/lib/llvm-21/bin/clang-21"))
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--tiers", nargs="*", choices=tuple(BENCHMARK_TIERS), default=None)
    args = parser.parse_args(argv)
    baseline: Mapping[str, Any] | None = None
    if args.baseline:
        loaded = json.loads(args.baseline.read_text(encoding="utf-8"))
        if isinstance(loaded, Mapping):
            baseline = loaded
    report = run_benchmarks(
        args.clang, baseline=baseline, tiers=tuple(args.tiers or BENCHMARK_TIERS)
    )
    write_atomic(report, args.output)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
