"""固定三档工作负载的独立 benchmark telemetry 门禁。"""

from __future__ import annotations

import argparse
import json
import statistics
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

BENCHMARK_ENVIRONMENT = {
    "os": "linux",
    "architecture": "amd64",
    "clang_llvm": "21.1.8",
    "vcpus": 4,
    "memory_bytes": 4 * 1024**3,
    "network": "disabled",
}

BENCHMARK_TIERS = {
    "S": {
        "translation_units": 20,
        "source_lines": 10_000,
        "wall_seconds": 60.0,
        "cpu_seconds": 180.0,
        "rss_bytes": int(1.5 * 1024**3),
        "result_bytes": 16 * 1024**2,
    },
    "M": {
        "translation_units": 100,
        "source_lines": 50_000,
        "wall_seconds": 240.0,
        "cpu_seconds": 720.0,
        "rss_bytes": int(2.5 * 1024**3),
        "result_bytes": 64 * 1024**2,
    },
    "L": {
        "translation_units": 500,
        "source_lines": 250_000,
        "wall_seconds": 900.0,
        "cpu_seconds": 2700.0,
        "rss_bytes": int(3.5 * 1024**3),
        "result_bytes": 256 * 1024**2,
    },
}


def _median(samples: Sequence[Mapping[str, int | float]], field: str) -> float:
    if len(samples) != 3:
        raise ValueError("benchmark_requires_three_samples")
    values = [float(item[field]) for item in samples]
    if any(value < 0 for value in values):
        raise ValueError("invalid_benchmark_sample")
    return statistics.median(values)


def evaluate_benchmark(
    tier: str,
    cold: Sequence[Mapping[str, int | float]],
    hot: Sequence[Mapping[str, int | float]],
    *,
    baseline: Mapping[str, int | float] | None = None,
    environment_applicable: bool = True,
    semantic_equal: bool = True,
) -> dict[str, Any]:
    if tier not in BENCHMARK_TIERS:
        raise ValueError("unknown_benchmark_tier")
    limits = BENCHMARK_TIERS[tier]
    cold_medians = {
        name: _median(cold, name)
        for name in ("wall_seconds", "cpu_seconds", "rss_bytes", "result_bytes")
    }
    hot_medians = {
        name: _median(hot, name)
        for name in ("wall_seconds", "cpu_seconds", "rss_bytes", "result_bytes")
    }
    absolute = all(cold_medians[name] <= float(limits[name]) for name in cold_medians)
    hot_ratio = cold_medians["wall_seconds"] > 0 and (
        hot_medians["wall_seconds"] / cold_medians["wall_seconds"] <= 0.60
    )
    regression = True
    if baseline is not None:
        regression = all(
            float(baseline[name]) > 0 and cold_medians[name] / float(baseline[name]) <= 1.20
            for name in ("wall_seconds", "cpu_seconds", "rss_bytes")
        )
    passed = environment_applicable and semantic_equal and absolute and hot_ratio and regression
    return {
        "tier": tier,
        "environment_applicable": environment_applicable,
        "semantic_equal": semantic_equal,
        "cold_median": cold_medians,
        "hot_median": hot_medians,
        "gates": {
            "absolute": absolute,
            "hot_ratio": hot_ratio,
            "regression": regression,
            "passed": passed,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    document = json.loads(args.input.read_text(encoding="utf-8"))
    if not isinstance(document, Mapping):
        raise ValueError("benchmark_input_must_be_object")
    tiers = document.get("tiers")
    if not isinstance(tiers, Mapping):
        raise ValueError("benchmark_tiers_missing")
    results = []
    for tier in BENCHMARK_TIERS:
        item = tiers.get(tier)
        if not isinstance(item, Mapping):
            raise ValueError("benchmark_tier_missing")
        cold = item.get("cold")
        hot = item.get("hot")
        if not isinstance(cold, list) or not isinstance(hot, list):
            raise ValueError("benchmark_samples_missing")
        results.append(
            evaluate_benchmark(
                tier,
                cold,
                hot,
                baseline=(
                    item.get("baseline") if isinstance(item.get("baseline"), Mapping) else None
                ),
                environment_applicable=bool(item.get("environment_applicable", False)),
                semantic_equal=bool(item.get("semantic_equal", False)),
            )
        )
    report = {
        "kind": "FloatingPointScannerBenchmarkResult",
        "schema_version": "1.0",
        "environment": BENCHMARK_ENVIRONMENT,
        "tiers": results,
        "passed": all(item["gates"]["passed"] for item in results),
    }
    from .output import write_atomic

    write_atomic(report, args.output)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
