"""Isolated scanner-wide 90/90 gate. Run inside kb-scanner-test only.

python tests/run_source_chain_unit_tests.py --output /out
"""
import argparse
import json
import unittest
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from coverage import Coverage


ROOT = Path(__file__).resolve().parents[1]
NON_UNIT = (".ArchitectureEnumFrontendTests.", ".ArchitectureEnumProjectionTests.",
            ".PipelineContractTests.",
            ".CompositeTests.test_composite_frontend_normalizer_analyzer_detector_preserve_both_domains")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    inventory = json.loads((ROOT / "tests/source-chain-test-inventory.json").read_text())
    coverage = Coverage(data_file=str(args.output / ".coverage"), branch=True,
                        source=[str(ROOT / name) for name in inventory["sources"]], config_file=False)
    coverage.set_option("report:exclude_lines", [])
    coverage.start()
    selected, excluded = {}, []

    def collect(suite):
        for item in suite:
            if isinstance(item, unittest.TestSuite):
                collect(item)
            elif any(marker in item.id() for marker in NON_UNIT):
                excluded.append(item.id())
            else:
                selected[item.id()] = item

    collect(unittest.defaultTestLoader.discover(str(ROOT / "tests/unit"), top_level_dir=str(ROOT)))
    collect(unittest.defaultTestLoader.loadTestsFromName("tests.test_core_pipeline"))
    with ExitStack() as boundaries:
        boundaries.enter_context(patch("kb_scanner.frontends.cpp.tree_sitter_adapter.Parser", side_effect=AssertionError("native C++ parser forbidden in unit gate")))
        boundaries.enter_context(patch("kb_scanner.frontends.build.make.Language"))
        boundaries.enter_context(patch("kb_scanner.frontends.build.make.Parser", return_value=SimpleNamespace(parse=lambda _: SimpleNamespace(root_node=SimpleNamespace(has_error=False)))))
        boundaries.enter_context(patch("kb_scanner.frontends.build.adapters.Parser", return_value=SimpleNamespace(parse=lambda _: SimpleNamespace(root_node=SimpleNamespace(has_error=False)))))
        fake = SimpleNamespace(root_node=SimpleNamespace(named_children=(), has_error=True))
        boundaries.enter_context(patch("kb_scanner.frontends.build.rpm.shell.Language"))
        boundaries.enter_context(patch("kb_scanner.frontends.build.rpm.shell.Parser", return_value=SimpleNamespace(parse=lambda _: fake)))
        boundaries.enter_context(patch("kb_scanner.frontends.build.autoconf.syntax.Parser", side_effect=RuntimeError("native Bash parser forbidden in unit gate")))
        boundaries.enter_context(patch("kb_scanner.frontends.build.cmake.syntax.Parser", side_effect=RuntimeError("native CMake parser forbidden in unit gate")))
        result = unittest.TextTestRunner(verbosity=1).run(unittest.TestSuite(selected[key] for key in sorted(selected)))
    coverage.stop()
    coverage.save()
    coverage.json_report(outfile=str(args.output / "coverage.json"), pretty_print=True)
    coverage.html_report(directory=str(args.output / "html"))
    payload = json.loads((args.output / "coverage.json").read_text())

    def percentages(summary):
        return {"line": 100 * summary["covered_lines"] / summary["num_statements"] if summary["num_statements"] else 100,
                "branch": 100 * summary["covered_branches"] / summary["num_branches"] if summary["num_branches"] else None}

    checks = {"overall": percentages(payload["totals"])}
    for module in inventory["modules"]:
        details = next((v for k, v in payload["files"].items() if k.replace("\\", "/").endswith(module)), None)
        checks[module] = percentages(details["summary"]) if details else {"line": 0, "branch": 0}
    failed = {name: values for name, values in checks.items() if values["line"] < 90 or values["branch"] is not None and values["branch"] < 90}
    summary = {"testsRun": result.testsRun, "failures": len(result.failures), "errors": len(result.errors),
               "checks": checks, "failedCoverage": failed, "sources": inventory["sources"],
               "excludedSourceCategories": inventory["excludedSourceCategories"], "excludedNonUnitCases": sorted(set(excluded)),
               "filesMeasured": len(payload["files"]), "passed": result.wasSuccessful() and not failed}
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
