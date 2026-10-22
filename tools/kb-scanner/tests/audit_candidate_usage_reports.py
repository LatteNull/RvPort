"""在独立容器生成用途能力开关对照工件；不自动批准或更新 golden。"""
from contextlib import ExitStack
import copy
import hashlib
import json
from pathlib import Path
import sys
from unittest.mock import patch

from kb_scanner.cli import main
from kb_scanner.core import StageResult


ROOT = Path(__file__).resolve().parents[1]


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def differences(before, after, path=""):
    if type(before) is not type(after):
        return [{"path": path, "before": before, "after": after}]
    if isinstance(before, dict):
        result = [{"path": path + "/" + key, "before": before.get(key), "after": after.get(key)}
                  for key in sorted(before.keys() ^ after.keys())]
        return result + [item for key in sorted(before.keys() & after.keys())
                         for item in differences(before[key], after[key], path + "/" + key)]
    if isinstance(before, list):
        if len(before) != len(after):
            return [{"path": path + "/length", "before": len(before), "after": len(after)}]
        return [item for index, (left, right) in enumerate(zip(before, after))
                for item in differences(left, right, path + "/" + str(index))]
    return [] if before == after else [{"path": path, "before": before, "after": after}]


def audit(output):
    output.mkdir(parents=True, exist_ok=False)
    result = {}
    for fixture in ("source-evidence-chain", "architecture-enum", "architecture-candidate-noise", "rpm-architecture"):
        result[fixture] = {}
        for version in ("1.0", "2.0"):
            reports, artifacts, metrics = [], [], []
            for enabled in (False, True):
                target = output / fixture / version / ("enabled" if enabled else "disabled")
                with ExitStack() as guards:
                    guards.enter_context(patch("subprocess.run", side_effect=AssertionError("不得执行项目命令")))
                    if not enabled:
                        guards.enter_context(patch("kb_scanner.pipeline.composite.CompositeProjectFrontend.analyze_with_knowledge",
                            lambda frontend, context, workspace, knowledge: frontend.analyze(context, workspace)))
                        guards.enter_context(patch("kb_scanner.frontends.cpp.tree_sitter_adapter.collect_usage", return_value=()))
                        guards.enter_context(patch("kb_scanner.analyzers.candidate_usage.analysis.CandidateUsageAnalyzer.analyze",
                            side_effect=lambda context, facts, knowledge, base: StageResult(base)))
                    code = main(["scan", "--input", str(ROOT / "tests/fixtures" / fixture),
                        "--rules", str(ROOT / "rulesets/riscv-porting"), "--output", str(target), "--schema-version", version])
                if code:
                    raise RuntimeError((fixture, version, enabled, code))
                data = {name: (target / name).read_bytes() for name in ("scan-result.json", "scan-report.html", "scan.log")}
                report = json.loads(data["scan-result.json"])
                stripped = copy.deepcopy(report)
                if version == "2.0":
                    for finding in stripped["findings"]:
                        finding["conclusion"].pop("suggestion")
                        finding["conclusion"].pop("suggestion_en")
                metrics.append({"after": digest(report), "logSha256": hashlib.sha256(data["scan.log"]).hexdigest(),
                    "strippedSha256": digest(stripped) if version == "2.0" else None})
                reports.append(report)
                artifacts.append(data)
            changes = differences(*reports)
            result[fixture][version] = {"disabled": metrics[0], "enabled": metrics[1], "differences": changes,
                "htmlEqual": artifacts[0]["scan-report.html"] == artifacts[1]["scan-report.html"],
                "logEqual": artifacts[0]["scan.log"] == artifacts[1]["scan.log"]}
            print(json.dumps({"fixture": fixture, "version": version, "metrics": metrics,
                "paths": [item["path"] for item in changes], "htmlEqual": result[fixture][version]["htmlEqual"],
                "logEqual": result[fixture][version]["logEqual"]}, ensure_ascii=False), flush=True)
    (output / "audit.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    audit(Path(sys.argv[1]))
