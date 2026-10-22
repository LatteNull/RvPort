"""真实默认管线的用途 producer 开关规模对照，只在独立测试容器运行。"""
import argparse
import hashlib
from contextlib import ExitStack
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import time
from unittest.mock import patch

from kb_scanner.cli import main
from kb_scanner.core import StageResult
from tests.performance.support import verify_limits
from tests.performance.observation import observe
from kb_scanner.pipeline.default import create_default_profile
from kb_scanner.projection.v2.renderers import render_json, render_json_chunks
from kb_scanner.projection.v2.mapper import V2FindingMapper
from kb_scanner.projection.v2.validation import V2ReferentialIntegrityValidator
from kb_scanner.projection.publisher import AtomicArtifactPublisher
from kb_scanner.analyzers.candidate_usage.analysis import CandidateUsageAnalyzer
from tests.performance.usage_acceptance import accept_pair


NAMESPACE = "org.rvport.kb-scanner.candidate-usage"


def source(references, density):
    # 每函数 25 次局部引用；稀疏时 100 个函数中只有一个含候选，其余为普通枚举。
    functions = []
    for number in range(references // 25):
        name = f"FORMAT_X86_{number}" if density == "dense" or number % 100 == 0 else f"FORMAT_LOCAL_{number}"
        functions.append(f"void f{number}() {{ enum Format{number} {{ {name}=1 }}; int kind={name};\n"
            + (f"  if (kind == {name}) {{}}\n" * 24) + "}\n")
    return "".join(functions)


def child(args):
    out = args.output
    out.mkdir(parents=True, exist_ok=False)
    project = out / "input"
    project.mkdir()
    text = source(args.references, args.density)
    (project / "scale.cpp").write_text(text)
    started = time.perf_counter()
    cpu_started = time.process_time()
    events = []
    captured = {}
    def capture_report(report, renderer=render_json):
        usage = (report.extensions or {}).get(NAMESPACE, {})
        captured.update(findings=len(report.findings), statistics=usage.get("statistics", {}),
            excludedCount=usage.get("excludedCount", 0), hasUsage=bool(usage),
            truncatedRoots=sum(root["analysisTruncated"] for finding in report.findings
                for root in (finding.fact.extensions or {}).get(NAMESPACE, {}).get("roots", ())))
        return renderer(report)
    def emit(event):
        events.append(event)
        with (out / "events.jsonl").open("a") as stream:
            stream.write(json.dumps(event) + "\n")
    def timed(name, method):
        def wrapped(*values, **kwargs):
            begin = time.perf_counter()
            emit({"stage": name, "event": "start"})
            result = method(*values, **kwargs)
            emit({"stage": name, "event": "end", "elapsedSeconds": time.perf_counter()-begin,
                  "maxRssKiB": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss})
            return result
        return wrapped
    with ExitStack() as guards:
        for owner, method in ((V2FindingMapper, 'map'), (V2ReferentialIntegrityValidator, 'validate'),
                              (AtomicArtifactPublisher, 'publish')):
            guards.enter_context(patch.object(owner, method, timed(owner.__name__, getattr(owner, method))))
        guards.enter_context(patch("kb_scanner.pipeline.default.create_default_profile",
            side_effect=lambda: observe(create_default_profile(), emit)))
        guards.enter_context(patch("subprocess.run", side_effect=AssertionError("不得执行项目命令")))
        guards.enter_context(patch("kb_scanner.projection.v2.projector.render_json", side_effect=capture_report))
        guards.enter_context(patch("kb_scanner.projection.v2.projector.render_json_chunks",
            side_effect=lambda report: capture_report(report, render_json_chunks)))
        if args.mode == "disabled":
            guards.enter_context(patch("kb_scanner.pipeline.composite.CompositeProjectFrontend.analyze_with_knowledge",
                lambda frontend, context, workspace, knowledge: frontend.analyze(context, workspace)))
            guards.enter_context(patch("kb_scanner.frontends.cpp.tree_sitter_adapter.collect_usage", return_value=()))
            guards.enter_context(patch("kb_scanner.analyzers.candidate_usage.analysis.CandidateUsageAnalyzer.analyze",
                side_effect=lambda c, f, k, b: StageResult(b)))
        else:
            guards.enter_context(patch.object(CandidateUsageAnalyzer, "analyze",
                timed("candidate_usage_index_and_query", CandidateUsageAnalyzer.analyze)))
        code = main(["scan", "--input", str(project), "--rules", "rulesets/riscv-porting", "--output", str(out / "report")])
    elapsed = time.perf_counter() - started
    cpu_elapsed = time.process_time() - cpu_started
    # 统计来自实际即将序列化的报告；不在 CLI 返回后把 GB 级 JSON 再加载一遍。
    # main 成功及三工件必须同时满足，避免“生成过模型”冒充发布成功。
    names = {file.name for file in (out / "report").iterdir()}
    if names != {"scan-result.json", "scan-report.html", "scan.log"}:
        code = 1
    result = {"mode": args.mode, "references": args.references, "density": args.density,
        "cpuAffinity": sorted(os.sched_getaffinity(0)),
        "seconds": elapsed, "cpuSeconds": cpu_elapsed,
        "maxRssKiB": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "artifactsBytes": {file.name: file.stat().st_size for file in (out / "report").iterdir()},
        "statistics": captured.get("statistics", {}), "excludedCount": captured.get("excludedCount", 0),
        "truncatedRoots": captured.get("truncatedRoots", 0), "findings": captured.get("findings", 0),
        "exitCode": code}
    result["stages"] = events
    functions = args.references // 25
    expected_roots = 24 * (functions if args.density == "dense" else (functions + 99) // 100)
    result["expectedRoots"] = expected_roots
    # 零候选不能冒充 producer 快速路径的性能验收。
    if not captured.get("findings") and not captured.get("excludedCount"):
        result["exitCode"] = 1
        result["reason"] = "规模样本未产生候选或排除审计"
    if args.mode == "enabled" and not captured.get("hasUsage"):
        result["exitCode"] = 1
        result["reason"] = "规模样本未触发用途分析"
    actual_roots = captured.get("statistics", {}).get("rootCount") if args.mode == "enabled" else captured.get("findings")
    if actual_roots != expected_roots:
        result["exitCode"] = 1
        result["reason"] = f"候选规模不符：预期 {expected_roots}，实际 {actual_roots}"
    (out / "metrics.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result), flush=True)
    return result["exitCode"]


def run(args):
    limits = verify_limits(lambda path: path.read_text())
    args.output.mkdir(parents=True, exist_ok=False)
    sources = {str(path): hashlib.sha256(path.read_bytes()).hexdigest()
               for path in sorted(Path('kb_scanner').rglob('*.py'))}
    source_digest = hashlib.sha256(json.dumps(sources, sort_keys=True).encode()).hexdigest()
    (args.output / 'runtime.json').write_text(json.dumps({'limits': limits, 'python': sys.version,
        'cpuAffinity': sorted(os.sched_getaffinity(0)),
        'sourceDigest': source_digest, 'sourceFiles': sources}, indent=2))
    results = []
    for references in (10000, 20000):
        for density in ("sparse", "dense"):
            pair = []
            for mode in ("disabled", "enabled"):
                target = args.output / f"{references}-{density}-{mode}"
                command = [sys.executable, "-m", "tests.run_usage_scale_tests", "--child", "--references", str(references),
                    "--density", density, "--mode", mode, "--output", str(target)]
                try:
                    outcome = subprocess.run(command, capture_output=True, text=True, timeout=300, check=False)
                    (args.output / f"{target.name}.log").write_text(outcome.stdout + outcome.stderr)
                    metrics = json.loads((target / "metrics.json").read_text()) if (target / "metrics.json").exists() else {"exitCode": outcome.returncode}
                    if outcome.returncode:
                        metrics["exitCode"] = outcome.returncode
                except subprocess.TimeoutExpired:
                    metrics = {"exitCode": 124, "reason": "规模扫描超时"}
                pair.append(metrics)
                print(json.dumps({"case": target.name, **metrics}), flush=True)
            results.append({"references": references, "density": density, "runs": pair,
                            **accept_pair(pair, references, density)})
            (args.output / "summary.json").write_text(json.dumps({
                "policy": "feature-cost-2026-09-24", "sourceDigest": source_digest,
                "relativeComparisonIsDiagnostic": True, "results": results,
                "passed": all(item["passed"] for item in results)}, indent=2))
            # 一组失败仍收集其余规模，不把未执行的密集场景隐藏在首个失败后。
    return 0 if all(item["passed"] for item in results) else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--child", action="store_true")
    parser.add_argument("--references", type=int)
    parser.add_argument("--density", choices=("sparse", "dense"))
    parser.add_argument("--mode", choices=("disabled", "enabled"))
    args = parser.parse_args()
    raise SystemExit(child(args) if args.child else run(args))
