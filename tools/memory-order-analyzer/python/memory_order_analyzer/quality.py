"""Auditable unit-only coverage accounting and repeatable offline quality entry."""

import argparse
import json
from pathlib import Path
import subprocess
import sys

from .contracts import AnalysisError, canonical, file_hash

# Reviewed declaration-only headers. A content change invalidates the exemption;
# executable/new headers must appear in LLVM's report, even when never called.
DECLARATION_HEADERS = {
    "src/facts.h": "675ab1b58df4dbc92926ddea1b4aaf8623f86e66a24921fb1420cac089bc513c",
    "src/semantic.h": "a04626b8a2c7222223aa2316732fa0f9ac9f65eef4b262d2b302c1c9a8bca72f",
    "src/effect_interpreter.h": "0804a912d1218e382e82de8fbb9212bfa4493544e559163947259889fbae675e",
    "src/source_facts.h": "cca9bb961b84c98f259af180c3dc10175bdbb1ee76201822aa20e8b3cfabfd07",
    "src/provenance.h": "5d47eefb62ec54f4fa01a2011fa0f6259f994d7b4cf4dcdf6e98cfb725c43927",
}


def owned_sources(root):
    root = Path(root).resolve()
    python = sorted(root.joinpath("python").rglob("*.py"))
    cpp = sorted(p for p in root.joinpath("src").rglob("*") if p.suffix in (".cpp", ".cc", ".cxx", ".h", ".hpp", ".hxx", ".inc")
                 and file_hash(p) != DECLARATION_HEADERS.get(p.relative_to(root).as_posix()))
    return {"python": python, "cpp": cpp}


def metric(hit, total):
    if not isinstance(hit, int) or not isinstance(total, int) or hit < 0 or hit > total:
        raise AnalysisError("coverage_invalid", "Invalid hit/total counts")
    return {"hit": hit, "total": total, "percent": 100 * hit / total if total else None,
            "passed": total == 0 or hit * 100 >= total * 90}


def aggregate(items):
    return {dimension: metric(sum(item[dimension]["hit"] for item in items), sum(item[dimension]["total"] for item in items))
            for dimension in ("lines", "branches")}


def evaluate(root, python_report, cpp_report, *, exclusions=()):
    if exclusions:
        raise AnalysisError("coverage_exclusion", "Owned executable logic cannot be excluded")
    expected = owned_sources(root)
    try:
        python = json.loads(Path(python_report).read_text())["files"]
        cpp = json.loads(Path(cpp_report).read_text())["data"][0]["files"]
        cpp = {str(Path(item["filename"]).resolve()): item["summary"] for item in cpp}
        python = {str((Path(root) / name).resolve()): item["summary"] for name, item in python.items()}
        modules = {}
        for language, paths in expected.items():
            for path in paths:
                summary = (python if language == "python" else cpp)[str(path)]
                if language == "python":
                    lines = metric(summary["covered_lines"], summary["num_statements"])
                    branches = metric(summary["covered_branches"], summary["num_branches"])
                else:
                    lines = metric(summary["lines"]["covered"], summary["lines"]["count"])
                    branches = metric(summary["branches"]["covered"], summary["branches"]["count"])
                modules[str(path.relative_to(root))] = {"language": language, "lines": lines, "branches": branches}
    except (OSError, ValueError, KeyError, IndexError, TypeError) as exc:
        raise AnalysisError("coverage_missing", f"Missing/invalid report or owned source: {exc}") from exc
    languages = {language: aggregate([m for m in modules.values() if m["language"] == language]) for language in expected}
    overall = aggregate(list(modules.values()))
    passed = bool(modules) and all(value["passed"] for group in [overall, *languages.values(), *modules.values()]
                                   for key, value in group.items() if key in ("lines", "branches"))
    return {"schema_version": 1, "threshold": 90, "profile": "unit-only", "passed": passed,
            "overall": overall, "languages": languages, "modules": modules,
            "excluded": [{"path": "tests/**", "reason": "Test harness and pure test inputs, not production logic"},
                         {"path": "LLVM, GoogleTest, Python dependencies", "reason": "Third-party implementations"},
                         {"path": "src/protocol.h.in and generated/protocol.h", "reason": "Generated metadata only; no executable logic"},
                         {"path": "src/analysis_protocol.h.in and generated/analysis_protocol.h", "reason": "Generated P2 protocol metadata only; executable effects.h is covered"},
                         {"path": "src/thread_protocol.h.in and generated/thread_protocol.h", "reason": "Generated P3 protocol metadata only; executable threads.h is covered"},
                         {"path": "src/publication_protocol.h.in and generated/publication_protocol.h", "reason": "Generated P4 protocol metadata only; executable publication.h is covered"},
                         {"path": "src/provenance_protocol.h.in and generated/provenance_protocol.h", "reason": "Generated A5 protocol metadata only; executable provenance.cpp is covered"},
                         {"path": "src/demand_protocol.h.in and generated/demand_protocol.h", "reason": "Generated R3 protocol metadata only; executable demand_analysis.cpp is covered"},
                         *[{"path": p, "sha256": h, "reason": "Reviewed declaration-only header; changed content requires coverage"}
                           for p, h in DECLARATION_HEADERS.items()]]}


def check(command, *, cwd, env=None):
    subprocess.run(command, cwd=cwd, env=env, check=True)


def run_quality(root, output, *, integration=False, runner=check):
    import os
    root, output = Path(root).resolve(), Path(output).resolve()
    if output.exists():
        raise AnalysisError("output_exists", "Quality output must be a new directory; old profiles must not be mixed")
    output.mkdir(parents=True)
    build = output / "build"
    runner(["cmake", "-S", str(root), "-B", str(build), "-G", "Ninja", "-DCMAKE_C_COMPILER=clang", "-DCMAKE_CXX_COMPILER=clang++"], cwd=root)
    runner(["cmake", "--build", str(build), "-j", "2"], cwd=root)
    env = {**os.environ, "LLVM_PROFILE_FILE": str(output / "unit-cpp.profraw"), "MOA_WORKER": str(build / "moa-worker"),
           "COVERAGE_FILE": str(output / ".coverage"), "PYTHONPATH": str(root / "python"), "PYTHONDONTWRITEBYTECODE": "1"}
    runner([str(build / "moa-unit")], cwd=output, env=env)
    runner([sys.executable, "-m", "coverage", "run", "--branch", "--source=" + str(root / "python"),
            "-m", "pytest", "-q", "-p", "no:cacheprovider", str(root / "tests/unit")], cwd=root, env=env)
    runner([sys.executable, "-m", "coverage", "json", "-o", str(output / "python.json")], cwd=root, env=env)
    runner([sys.executable, "-m", "coverage", "html", "-d", str(output / "python-html")], cwd=root, env=env)
    runner(["llvm-profdata", "merge", "-sparse", str(output / "unit-cpp.profraw"), "-o", str(output / "unit.profdata")], cwd=root)
    export = ["llvm-cov", "export", str(build / "moa-unit"), "-instr-profile=" + str(output / "unit.profdata")]
    # Export is captured to its own file, never merged with integration profiles.
    with (output / "cpp.json").open("w") as stream:
        subprocess.run(export, cwd=root, stdout=stream, check=True)
    runner(["llvm-cov", "show", str(build / "moa-unit"), "-instr-profile=" + str(output / "unit.profdata"),
            "-format=html", "-output-dir=" + str(output / "cpp-html"), "-show-branches=count"], cwd=root)
    summary = evaluate(root, output / "python.json", output / "cpp.json")
    summary["commands"] = {"unit": "python3 -m memory_order_analyzer.quality --output <new-output>", "integration_separate": integration}
    (output / "coverage-summary.json").write_text(canonical(summary) + "\n")
    (output / "coverage-summary.html").write_text("<!doctype html><meta charset=utf-8><title>Unit coverage</title><pre>" +
                                               __import__("html").escape(json.dumps(summary, indent=2)) + "</pre>")
    if not summary["passed"]:
        raise AnalysisError("coverage_below_threshold", str(output / "coverage-summary.json"))
    if integration:
        env["LLVM_PROFILE_FILE"] = str(output / "integration-%p.profraw")
        runner([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", str(root / "tests/integration")], cwd=root, env=env)
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--integration", action="store_true")
    args = parser.parse_args(argv)
    result = run_quality(Path(__file__).resolve().parents[2], args.output, integration=args.integration)
    print(canonical(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
