from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

from coverage import Coverage

from tests.frontend_coverage import evaluate_frontend_coverage


ROOT = Path(__file__).resolve().parents[1]
TEST_ROOT = ROOT / "tests"
UNIT_ROOT = TEST_ROOT / "unit" / "frontends" / "cpp"
INVENTORY_PATH = TEST_ROOT / "frontend-test-inventory.json"
COVERAGE_DATA = Path("/tmp/kb-scanner-frontend-unit.coverage")
COVERAGE_JSON = Path("/tmp/kb-scanner-frontend-unit-coverage.json")
KNOWLEDGE_UNIT_ROOT = TEST_ROOT / "unit" / "knowledge_detection"
KNOWLEDGE_INVENTORY_PATH = TEST_ROOT / "knowledge-detection-test-inventory.json"
KNOWLEDGE_COVERAGE_DATA = Path("/tmp/kb-scanner-knowledge-detection-unit.coverage")
KNOWLEDGE_COVERAGE_JSON = Path("/tmp/kb-scanner-knowledge-detection-unit-coverage.json")
PRODUCTION_UNIT_ROOT = TEST_ROOT / "unit" / "knowledge_production"
PRODUCTION_INVENTORY_PATH = TEST_ROOT / "knowledge-production-test-inventory.json"
PRODUCTION_COVERAGE_DATA = Path("/tmp/kb-scanner-knowledge-production-unit.coverage")
PRODUCTION_COVERAGE_JSON = Path("/tmp/kb-scanner-knowledge-production-unit-coverage.json")
GRAPH_UNIT_ROOT = TEST_ROOT / "unit" / "evidence_graph"
GRAPH_INVENTORY_PATH = TEST_ROOT / "evidence-graph-test-inventory.json"
GRAPH_COVERAGE_DATA = Path("/tmp/kb-scanner-evidence-graph-unit.coverage")
GRAPH_COVERAGE_JSON = Path("/tmp/kb-scanner-evidence-graph-unit-coverage.json")
BUILD_UNIT_ROOT = TEST_ROOT / "unit" / "build_selection"
BUILD_INVENTORY_PATH = TEST_ROOT / "build-selection-test-inventory.json"
BUILD_COVERAGE_DATA = Path("/tmp/kb-scanner-build-selection-unit.coverage")
BUILD_COVERAGE_JSON = Path("/tmp/kb-scanner-build-selection-unit-coverage.json")
CLASSIFICATION_INVENTORY_PATH = TEST_ROOT / "classification-assessment-test-inventory.json"
CLASSIFICATION_COVERAGE_DATA = Path("/tmp/kb-scanner-classification-assessment-unit.coverage")
CLASSIFICATION_COVERAGE_JSON = Path("/tmp/kb-scanner-classification-assessment-unit-coverage.json")
COMPATIBLE_INVENTORY_PATH = TEST_ROOT / "compatible-cutover-test-inventory.json"
COMPATIBLE_COVERAGE_DATA = Path("/tmp/kb-scanner-compatible-cutover-unit.coverage")
COMPATIBLE_COVERAGE_JSON = Path("/tmp/kb-scanner-compatible-cutover-unit-coverage.json")
PROJECTION_REACHABILITY_INVENTORY_PATH = TEST_ROOT / "projection-reachability-test-inventory.json"
PROJECTION_REACHABILITY_COVERAGE_DATA = Path("/tmp/kb-scanner-projection-reachability-unit.coverage")
PROJECTION_REACHABILITY_COVERAGE_JSON = Path("/tmp/kb-scanner-projection-reachability-unit-coverage.json")
SCHEMA_V2_INVENTORY_PATH = TEST_ROOT / "schema-v2-test-inventory.json"
SCHEMA_V2_PROJECTION_INVENTORY_PATH = TEST_ROOT / "schema-v2-projection-test-inventory.json"
SCHEMA_V2_PROJECTION_COVERAGE_DATA = Path("/tmp/kb-scanner-schema-v2-projection-unit.coverage")
SCHEMA_V2_PROJECTION_COVERAGE_JSON = Path("/tmp/kb-scanner-schema-v2-projection-unit-coverage.json")
ARCH_ENUM_INVENTORY_PATH = TEST_ROOT / "architecture-enum-test-inventory.json"
ARCH_ENUM_COVERAGE_DATA = Path("/tmp/kb-scanner-architecture-enum-unit.coverage")
ARCH_ENUM_COVERAGE_JSON = Path("/tmp/kb-scanner-architecture-enum-unit-coverage.json")
NATIVE_CRASH_UNIT_ROOT = TEST_ROOT / "unit" / "native_crash"
NATIVE_CRASH_INVENTORY_PATH = TEST_ROOT / "tree-sitter-native-crash-test-inventory.json"
NATIVE_CRASH_COVERAGE_DATA = Path("/tmp/kb-scanner-tree-sitter-native-crash-unit.coverage")
NATIVE_CRASH_COVERAGE_JSON = Path("/tmp/kb-scanner-tree-sitter-native-crash-unit-coverage.json")


def _run(suite: unittest.TestSuite, label: str) -> unittest.TestResult:
    print(f"\n=== {label} ===", flush=True)
    return unittest.TextTestRunner(verbosity=2).run(suite)


def _unit_gate() -> bool:
    inventory = json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))
    thresholds = inventory["coverageThresholds"]
    modules = tuple(
        f"kb_scanner/frontends/cpp/{name}" for name in sorted(inventory["modules"])
    )
    coverage = Coverage(
        data_file=str(COVERAGE_DATA),
        branch=True,
        source=["kb_scanner.frontends.cpp"],
        omit=["*/__init__.py"],
    )
    coverage.erase()
    coverage.start()
    suite = unittest.defaultTestLoader.discover(
        str(UNIT_ROOT),
        pattern="test_*.py",
        top_level_dir=str(ROOT),
    )
    for unit in sorted({item['unit'] for item in inventory['modules'].values()}):
        if not (ROOT / unit).is_relative_to(UNIT_ROOT):
            suite.addTests(unittest.defaultTestLoader.loadTestsFromName(unit.removesuffix('.py').replace('/', '.')))
    suite.addTests(unittest.defaultTestLoader.loadTestsFromName('tests.unit.test_function_clang_contract'))
    result = _run(suite, "frontend-unit")
    coverage.stop()
    coverage.save()
    coverage.json_report(outfile=str(COVERAGE_JSON), pretty_print=True)
    payload = json.loads(COVERAGE_JSON.read_text(encoding="utf-8"))
    gate = evaluate_frontend_coverage(
        payload,
        modules,
        line_threshold=float(thresholds["linePercent"]),
        branch_threshold=float(thresholds["branchPercent"]),
        enforce_module_thresholds=True,
    )
    print(
        f"frontend-unit coverage: lines={gate.line_percent:.2f}% "
        f"branches={gate.branch_percent:.2f}%",
        flush=True,
    )
    normalized_files = {
        path.replace("\\", "/"): details for path, details in payload.get("files", {}).items()
    }
    for module in modules:
        summary = normalized_files[module]["summary"]
        module_lines = (
            100.0
            if int(summary["num_statements"]) == 0
            else int(summary["covered_lines"]) * 100.0 / int(summary["num_statements"])
        )
        module_branches = (
            100.0
            if int(summary["num_branches"]) == 0
            else int(summary["covered_branches"]) * 100.0 / int(summary["num_branches"])
        )
        print(
            f"  {module.rsplit('/', 1)[-1]}: "
            f"lines={module_lines:.2f}% branches={module_branches:.2f}%",
            flush=True,
        )
    for failure in gate.failures:
        print(f"coverage gate failed: {failure}", file=sys.stderr, flush=True)
    return result.wasSuccessful() and gate.passed


def _knowledge_detection_unit_gate() -> bool:
    inventory = json.loads(KNOWLEDGE_INVENTORY_PATH.read_text(encoding="utf-8"))
    thresholds = inventory["coverageThresholds"]
    module_names = tuple(sorted(inventory["modules"]))
    modules = tuple(f"kb_scanner/{name}" for name in module_names)
    sources = tuple(f"kb_scanner.{name.removesuffix('.py').replace('/', '.')}" for name in module_names)
    coverage = Coverage(
        data_file=str(KNOWLEDGE_COVERAGE_DATA),
        branch=True,
        source=list(sources),
        omit=["*/__init__.py"],
    )
    coverage.erase()
    coverage.start()
    suite = unittest.defaultTestLoader.discover(
        str(KNOWLEDGE_UNIT_ROOT),
        pattern="test_*.py",
        top_level_dir=str(ROOT),
    )
    result = _run(suite, "knowledge-detection-unit")
    coverage.stop()
    coverage.save()
    coverage.json_report(outfile=str(KNOWLEDGE_COVERAGE_JSON), pretty_print=True)
    payload = json.loads(KNOWLEDGE_COVERAGE_JSON.read_text(encoding="utf-8"))
    gate = evaluate_frontend_coverage(
        payload,
        modules,
        line_threshold=float(thresholds["linePercent"]),
        branch_threshold=float(thresholds["branchPercent"]),
        enforce_module_thresholds=True,
    )
    print(
        f"knowledge-detection-unit coverage: lines={gate.line_percent:.2f}% "
        f"branches={gate.branch_percent:.2f}%",
        flush=True,
    )
    normalized_files = {path.replace("\\", "/"): details for path, details in payload.get("files", {}).items()}
    for module in modules:
        summary = normalized_files.get(module, {}).get("summary", {})
        statements = int(summary.get("num_statements", 0))
        branches = int(summary.get("num_branches", 0))
        module_lines = 0.0 if statements == 0 else int(summary.get("covered_lines", 0)) * 100.0 / statements
        module_branches = 100.0 if branches == 0 else int(summary.get("covered_branches", 0)) * 100.0 / branches
        print(f"  {module}: lines={module_lines:.2f}% branches={module_branches:.2f}%", flush=True)
    for failure in gate.failures:
        print(f"coverage gate failed: {failure}", file=sys.stderr, flush=True)
    return result.wasSuccessful() and gate.passed


def _knowledge_production_unit_gate() -> bool:
    inventory = json.loads(PRODUCTION_INVENTORY_PATH.read_text(encoding="utf-8"))
    thresholds = inventory["coverageThresholds"]
    module_names = tuple(sorted(inventory["modules"]))
    modules = tuple(f"kb_scanner/{name}" for name in module_names)
    sources = tuple(f"kb_scanner.{name.removesuffix('.py').replace('/', '.')}" for name in module_names)
    coverage = Coverage(
        data_file=str(PRODUCTION_COVERAGE_DATA), branch=True, source=list(sources), omit=["*/__init__.py"],
    )
    coverage.erase()
    coverage.start()
    suite = unittest.defaultTestLoader.discover(
        str(PRODUCTION_UNIT_ROOT), pattern="test_*.py", top_level_dir=str(ROOT),
    )
    result = _run(suite, "knowledge-production-unit")
    coverage.stop()
    coverage.save()
    coverage.json_report(outfile=str(PRODUCTION_COVERAGE_JSON), pretty_print=True)
    payload = json.loads(PRODUCTION_COVERAGE_JSON.read_text(encoding="utf-8"))
    gate = evaluate_frontend_coverage(
        payload, modules, line_threshold=float(thresholds["linePercent"]),
        branch_threshold=float(thresholds["branchPercent"]), enforce_module_thresholds=True,
    )
    print(
        f"knowledge-production-unit coverage: lines={gate.line_percent:.2f}% branches={gate.branch_percent:.2f}%",
        flush=True,
    )
    normalized_files = {path.replace("\\", "/"): details for path, details in payload.get("files", {}).items()}
    for module in modules:
        summary = normalized_files.get(module, {}).get("summary", {})
        statements = int(summary.get("num_statements", 0))
        branches = int(summary.get("num_branches", 0))
        line_percent = 0.0 if statements == 0 else int(summary.get("covered_lines", 0)) * 100.0 / statements
        branch_percent = 100.0 if branches == 0 else int(summary.get("covered_branches", 0)) * 100.0 / branches
        print(f"  {module}: lines={line_percent:.2f}% branches={branch_percent:.2f}%", flush=True)
    for failure in gate.failures:
        print(f"coverage gate failed: {failure}", file=sys.stderr, flush=True)
    return result.wasSuccessful() and gate.passed


def _evidence_graph_unit_gate() -> bool:
    inventory = json.loads(GRAPH_INVENTORY_PATH.read_text(encoding="utf-8"))
    thresholds = inventory["coverageThresholds"]
    module_names = tuple(sorted(inventory["modules"]))
    modules = tuple(f"kb_scanner/{name}" for name in module_names)
    sources = tuple(f"kb_scanner.{name.removesuffix('.py').replace('/', '.')}" for name in module_names)
    coverage = Coverage(
        data_file=str(GRAPH_COVERAGE_DATA), branch=True, source=list(sources), omit=["*/__init__.py"],
    )
    coverage.erase()
    coverage.start()
    suite = unittest.defaultTestLoader.discover(
        str(GRAPH_UNIT_ROOT), pattern="test_*.py", top_level_dir=str(ROOT),
    )
    result = _run(suite, "evidence-graph-unit")
    coverage.stop()
    coverage.save()
    coverage.json_report(outfile=str(GRAPH_COVERAGE_JSON), pretty_print=True)
    payload = json.loads(GRAPH_COVERAGE_JSON.read_text(encoding="utf-8"))
    gate = evaluate_frontend_coverage(
        payload, modules, line_threshold=float(thresholds["linePercent"]),
        branch_threshold=float(thresholds["branchPercent"]), enforce_module_thresholds=True,
    )
    print(
        f"evidence-graph-unit coverage: lines={gate.line_percent:.2f}% branches={gate.branch_percent:.2f}%",
        flush=True,
    )
    normalized_files = {path.replace("\\", "/"): details for path, details in payload.get("files", {}).items()}
    for module in modules:
        summary = normalized_files.get(module, {}).get("summary", {})
        statements = int(summary.get("num_statements", 0))
        branches = int(summary.get("num_branches", 0))
        line_percent = 0.0 if statements == 0 else int(summary.get("covered_lines", 0)) * 100.0 / statements
        branch_percent = 100.0 if branches == 0 else int(summary.get("covered_branches", 0)) * 100.0 / branches
        print(f"  {module}: lines={line_percent:.2f}% branches={branch_percent:.2f}%", flush=True)
    for failure in gate.failures:
        print(f"coverage gate failed: {failure}", file=sys.stderr, flush=True)
    return result.wasSuccessful() and gate.passed


def _build_selection_unit_gate() -> bool:
    inventory = json.loads(BUILD_INVENTORY_PATH.read_text(encoding="utf-8"))
    thresholds = inventory["coverageThresholds"]
    module_names = tuple(sorted(inventory["modules"]))
    modules = tuple(f"kb_scanner/{name}" for name in module_names)
    sources = tuple(f"kb_scanner.{name.removesuffix('.py').replace('/', '.')}" for name in module_names)
    coverage = Coverage(
        data_file=str(BUILD_COVERAGE_DATA), branch=True, source=list(sources), omit=["*/__init__.py"],
    )
    coverage.erase()
    coverage.start()
    suite = unittest.defaultTestLoader.discover(
        str(BUILD_UNIT_ROOT), pattern="test_*.py", top_level_dir=str(ROOT),
    )
    supporting_modules = sorted(
        {
            path.removesuffix(".py").replace("/", ".")
            for mapping in inventory["modules"].values()
            for path in mapping.get("supportingUnits", ())
        }
    )
    for module in supporting_modules:
        suite.addTests(unittest.defaultTestLoader.loadTestsFromName(module))
    result = _run(suite, "build-selection-unit")
    coverage.stop()
    coverage.save()
    coverage.json_report(outfile=str(BUILD_COVERAGE_JSON), pretty_print=True)
    payload = json.loads(BUILD_COVERAGE_JSON.read_text(encoding="utf-8"))
    gate = evaluate_frontend_coverage(
        payload, modules, line_threshold=float(thresholds["linePercent"]),
        branch_threshold=float(thresholds["branchPercent"]), enforce_module_thresholds=True,
    )
    print(
        f"build-selection-unit coverage: lines={gate.line_percent:.2f}% branches={gate.branch_percent:.2f}%",
        flush=True,
    )
    normalized_files = {path.replace("\\", "/"): details for path, details in payload.get("files", {}).items()}
    for module in modules:
        summary = normalized_files.get(module, {}).get("summary", {})
        statements = int(summary.get("num_statements", 0))
        branches = int(summary.get("num_branches", 0))
        line_percent = 0.0 if statements == 0 else int(summary.get("covered_lines", 0)) * 100.0 / statements
        branch_percent = 100.0 if branches == 0 else int(summary.get("covered_branches", 0)) * 100.0 / branches
        print(f"  {module}: lines={line_percent:.2f}% branches={branch_percent:.2f}%", flush=True)
    for failure in gate.failures:
        print(f"coverage gate failed: {failure}", file=sys.stderr, flush=True)
    return result.wasSuccessful() and gate.passed


def _classification_assessment_unit_gate() -> bool:
    inventory = json.loads(CLASSIFICATION_INVENTORY_PATH.read_text(encoding="utf-8"))
    thresholds = inventory["coverageThresholds"]
    module_names = tuple(sorted(inventory["modules"]))
    modules = tuple(f"kb_scanner/{name}" for name in module_names)
    sources = tuple(f"kb_scanner.{name.removesuffix('.py').replace('/', '.')}" for name in module_names)
    coverage = Coverage(
        data_file=str(CLASSIFICATION_COVERAGE_DATA), branch=True, source=list(sources), omit=["*/__init__.py"],
    )
    coverage.erase()
    coverage.start()
    suite = unittest.TestSuite()
    unit_modules = sorted(
        {
            path.removesuffix(".py").replace("/", ".")
            for mapping in inventory["modules"].values()
            for path in (mapping["unit"], *mapping.get("supportingUnits", ()))
        }
    )
    for module in unit_modules:
        suite.addTests(unittest.defaultTestLoader.loadTestsFromName(module))
    result = _run(suite, "classification-assessment-unit")
    coverage.stop()
    coverage.save()
    coverage.json_report(outfile=str(CLASSIFICATION_COVERAGE_JSON), pretty_print=True)
    payload = json.loads(CLASSIFICATION_COVERAGE_JSON.read_text(encoding="utf-8"))
    gate = evaluate_frontend_coverage(
        payload, modules, line_threshold=float(thresholds["linePercent"]),
        branch_threshold=float(thresholds["branchPercent"]), enforce_module_thresholds=True,
    )
    print(
        f"classification-assessment-unit coverage: lines={gate.line_percent:.2f}% branches={gate.branch_percent:.2f}%",
        flush=True,
    )
    normalized_files = {path.replace("\\", "/"): details for path, details in payload.get("files", {}).items()}
    for module in modules:
        summary = normalized_files.get(module, {}).get("summary", {})
        statements = int(summary.get("num_statements", 0))
        branches = int(summary.get("num_branches", 0))
        line_percent = 0.0 if statements == 0 else int(summary.get("covered_lines", 0)) * 100.0 / statements
        branch_percent = 100.0 if branches == 0 else int(summary.get("covered_branches", 0)) * 100.0 / branches
        print(f"  {module}: lines={line_percent:.2f}% branches={branch_percent:.2f}%", flush=True)
    for failure in gate.failures:
        print(f"coverage gate failed: {failure}", file=sys.stderr, flush=True)
    return result.wasSuccessful() and gate.passed


def _compatible_cutover_unit_gate() -> bool:
    inventory = json.loads(COMPATIBLE_INVENTORY_PATH.read_text(encoding="utf-8"))
    thresholds = inventory["coverageThresholds"]
    module_names = tuple(sorted(inventory["modules"]))
    modules = tuple(f"kb_scanner/{name}" for name in module_names)
    sources = tuple(f"kb_scanner.{name.removesuffix('.py').replace('/', '.')}" for name in module_names)
    coverage = Coverage(
        data_file=str(COMPATIBLE_COVERAGE_DATA), branch=True, source=list(sources), omit=["*/__init__.py"],
    )
    coverage.erase()
    coverage.start()
    suite = unittest.TestSuite()
    unit_modules = sorted(
        {
            path.removesuffix(".py").replace("/", ".")
            for mapping in inventory["modules"].values()
            for path in (mapping["unit"], *mapping.get("supportingUnits", ()))
        }
    )
    for module in unit_modules:
        suite.addTests(unittest.defaultTestLoader.loadTestsFromName(module))
    result = _run(suite, "compatible-cutover-unit")
    coverage.stop()
    coverage.save()
    coverage.json_report(outfile=str(COMPATIBLE_COVERAGE_JSON), pretty_print=True)
    payload = json.loads(COMPATIBLE_COVERAGE_JSON.read_text(encoding="utf-8"))
    gate = evaluate_frontend_coverage(
        payload, modules, line_threshold=float(thresholds["linePercent"]),
        branch_threshold=float(thresholds["branchPercent"]), enforce_module_thresholds=True,
    )
    print(
        f"compatible-cutover-unit coverage: lines={gate.line_percent:.2f}% branches={gate.branch_percent:.2f}%",
        flush=True,
    )
    normalized_files = {path.replace("\\", "/"): details for path, details in payload.get("files", {}).items()}
    for module in modules:
        summary = normalized_files.get(module, {}).get("summary", {})
        statements = int(summary.get("num_statements", 0))
        branches = int(summary.get("num_branches", 0))
        line_percent = 0.0 if statements == 0 else int(summary.get("covered_lines", 0)) * 100.0 / statements
        branch_percent = 100.0 if branches == 0 else int(summary.get("covered_branches", 0)) * 100.0 / branches
        print(f"  {module}: lines={line_percent:.2f}% branches={branch_percent:.2f}%", flush=True)
    for failure in gate.failures:
        print(f"coverage gate failed: {failure}", file=sys.stderr, flush=True)
    return result.wasSuccessful() and gate.passed


def _projection_reachability_unit_gate() -> bool:
    inventory = json.loads(PROJECTION_REACHABILITY_INVENTORY_PATH.read_text(encoding="utf-8"))
    thresholds = inventory["coverageThresholds"]
    module_names = tuple(sorted(inventory["modules"]))
    modules = tuple(f"kb_scanner/{name}" for name in module_names)
    sources = tuple(f"kb_scanner.{name.removesuffix('.py').replace('/', '.')}" for name in module_names)
    coverage = Coverage(
        data_file=str(PROJECTION_REACHABILITY_COVERAGE_DATA),
        branch=True,
        source=list(sources),
        omit=["*/__init__.py"],
    )
    coverage.erase()
    coverage.start()
    suite = unittest.defaultTestLoader.discover(
        str(TEST_ROOT / "unit" / "projection_reachability"),
        pattern="test_*.py",
        top_level_dir=str(ROOT),
    )
    supporting_modules = sorted(
        {
            path.removesuffix(".py").replace("/", ".")
            for mapping in inventory["modules"].values()
            for path in mapping.get("supportingUnits", ())
        }
    )
    for module in supporting_modules:
        suite.addTests(unittest.defaultTestLoader.loadTestsFromName(module))
    result = _run(suite, "projection-reachability-unit")
    coverage.stop()
    coverage.save()
    coverage.json_report(outfile=str(PROJECTION_REACHABILITY_COVERAGE_JSON), pretty_print=True)
    payload = json.loads(PROJECTION_REACHABILITY_COVERAGE_JSON.read_text(encoding="utf-8"))
    gate = evaluate_frontend_coverage(
        payload,
        modules,
        line_threshold=float(thresholds["linePercent"]),
        branch_threshold=float(thresholds["branchPercent"]),
        enforce_module_thresholds=True,
    )
    print(
        f"projection-reachability-unit coverage: lines={gate.line_percent:.2f}% "
        f"branches={gate.branch_percent:.2f}%",
        flush=True,
    )
    normalized_files = {path.replace("\\", "/"): details for path, details in payload.get("files", {}).items()}
    for module in modules:
        summary = normalized_files.get(module, {}).get("summary", {})
        statements = int(summary.get("num_statements", 0))
        branches = int(summary.get("num_branches", 0))
        line_percent = 0.0 if statements == 0 else int(summary.get("covered_lines", 0)) * 100.0 / statements
        branch_percent = 100.0 if branches == 0 else int(summary.get("covered_branches", 0)) * 100.0 / branches
        print(f"  {module}: lines={line_percent:.2f}% branches={branch_percent:.2f}%", flush=True)
    for failure in gate.failures:
        print(f"coverage gate failed: {failure}", file=sys.stderr, flush=True)
    return result.wasSuccessful() and gate.passed


def _schema_v2_contract_gate() -> bool:
    inventory = json.loads(SCHEMA_V2_INVENTORY_PATH.read_text(encoding="utf-8"))
    if inventory["productionModules"]:
        print("schema-v2 design contract must not register production modules", file=sys.stderr, flush=True)
        return False
    suite = unittest.defaultTestLoader.loadTestsFromName("tests.test_schema_v2_design_contract")
    return _run(suite, "schema-v2-design-contract").wasSuccessful()


def _schema_v2_projection_unit_gate() -> bool:
    inventory = json.loads(SCHEMA_V2_PROJECTION_INVENTORY_PATH.read_text(encoding="utf-8"))
    thresholds = inventory["coverageThresholds"]
    mapping = inventory["modules"]
    modules = tuple(f"kb_scanner/{name}" for name in sorted(mapping))
    unit_modules = sorted({
        path.removesuffix(".py").replace("/", ".")
        for item in mapping.values()
        for path in (item["unit"], *item.get("supportingUnits", ()))
    })
    missing = [name for name, item in mapping.items() if not (ROOT / item["unit"]).is_file()]
    if missing:
        print(f"schema-v2-projection inventory has missing isolated units: {missing}", file=sys.stderr)
        return False
    coverage = Coverage(
        data_file=str(SCHEMA_V2_PROJECTION_COVERAGE_DATA), branch=True,
        source=[f"kb_scanner.{name.removesuffix('.py').replace('/', '.')}" for name in mapping],
        omit=["*/__init__.py"],
    )
    coverage.erase()
    coverage.start()
    suite = unittest.TestSuite()
    for module in unit_modules:
        suite.addTests(unittest.defaultTestLoader.loadTestsFromName(module))
    result = _run(suite, "schema-v2-projection-unit")
    coverage.stop()
    coverage.save()
    coverage.json_report(outfile=str(SCHEMA_V2_PROJECTION_COVERAGE_JSON), pretty_print=True)
    payload = json.loads(SCHEMA_V2_PROJECTION_COVERAGE_JSON.read_text(encoding="utf-8"))
    gate = evaluate_frontend_coverage(
        payload, modules, line_threshold=float(thresholds["linePercent"]),
        branch_threshold=float(thresholds["branchPercent"]), enforce_module_thresholds=True,
    )
    print(
        f"schema-v2-projection-unit coverage: lines={gate.line_percent:.2f}% "
        f"branches={gate.branch_percent:.2f}%", flush=True,
    )
    for failure in gate.failures:
        print(f"coverage gate failed: {failure}", file=sys.stderr, flush=True)
    return result.wasSuccessful() and gate.passed


def _architecture_enum_unit_gate() -> bool:
    inventory = json.loads(ARCH_ENUM_INVENTORY_PATH.read_text(encoding="utf-8"))
    thresholds = inventory["coverageThresholds"]
    mapping = inventory["modules"]
    missing = [name for name, item in mapping.items() if not (ROOT / item["unit"]).is_file()]
    if missing:
        print(f"architecture-enum inventory has missing isolated units: {missing}", file=sys.stderr)
        return False
    modules = tuple(f"kb_scanner/{name}" for name in sorted(mapping))
    unit_modules = sorted({
        path.removesuffix(".py").replace("/", ".")
        for item in mapping.values()
        for path in (item["unit"], *item.get("supportingUnits", ()))
    })
    coverage = Coverage(
        data_file=str(ARCH_ENUM_COVERAGE_DATA), branch=True,
        source=[f"kb_scanner.{name.removesuffix('.py').replace('/', '.')}" for name in mapping],
        omit=["*/__init__.py"],
    )
    coverage.erase()
    coverage.start()
    suite = unittest.TestSuite()
    for module in unit_modules:
        suite.addTests(unittest.defaultTestLoader.loadTestsFromName(module))
    result = _run(suite, "architecture-enum-unit")
    coverage.stop()
    coverage.save()
    coverage.json_report(outfile=str(ARCH_ENUM_COVERAGE_JSON), pretty_print=True)
    payload = json.loads(ARCH_ENUM_COVERAGE_JSON.read_text(encoding="utf-8"))
    gate = evaluate_frontend_coverage(
        payload, modules, line_threshold=float(thresholds["linePercent"]),
        branch_threshold=float(thresholds["branchPercent"]), enforce_module_thresholds=True,
    )
    print(
        f"architecture-enum-unit coverage: lines={gate.line_percent:.2f}% "
        f"branches={gate.branch_percent:.2f}%", flush=True,
    )
    for failure in gate.failures:
        print(f"coverage gate failed: {failure}", file=sys.stderr, flush=True)
    return result.wasSuccessful() and gate.passed


def _tree_sitter_native_crash_unit_gate() -> bool:
    inventory = json.loads(NATIVE_CRASH_INVENTORY_PATH.read_text(encoding="utf-8"))
    thresholds = inventory["coverageThresholds"]
    missing = [
        name
        for name, item in inventory["modules"].items()
        if not (ROOT / item["unit"]).is_file()
    ]
    if missing:
        print(f"tree-sitter native-crash inventory has missing isolated units: {missing}", file=sys.stderr)
        return False
    coverage = Coverage(
        data_file=str(NATIVE_CRASH_COVERAGE_DATA),
        branch=True,
        source=["tests.tree_sitter_native_support"],
    )
    coverage.erase()
    coverage.start()
    from tests.tree_sitter_native_support import inspect_runtime, runtime_payload, validate_runtime

    runtime = inspect_runtime()
    print("tree-sitter-runtime=" + json.dumps(runtime_payload(runtime), sort_keys=True), flush=True)
    runtime_errors = validate_runtime(runtime)
    suite = unittest.defaultTestLoader.discover(
        str(NATIVE_CRASH_UNIT_ROOT), pattern="test_*.py", top_level_dir=str(ROOT)
    )
    result = _run(suite, "tree-sitter-native-crash-unit")
    coverage.stop()
    coverage.save()
    for error in runtime_errors:
        print(f"tree-sitter runtime gate failed: {error}", file=sys.stderr, flush=True)
    if runtime_errors:
        return False
    coverage.json_report(outfile=str(NATIVE_CRASH_COVERAGE_JSON), pretty_print=True)
    payload = json.loads(NATIVE_CRASH_COVERAGE_JSON.read_text(encoding="utf-8"))
    gate = evaluate_frontend_coverage(
        payload,
        ("tests/tree_sitter_native_support.py",),
        line_threshold=float(thresholds["linePercent"]),
        branch_threshold=float(thresholds["branchPercent"]),
        enforce_module_thresholds=True,
    )
    print(
        f"tree-sitter-native-crash-unit coverage: lines={gate.line_percent:.2f}% "
        f"branches={gate.branch_percent:.2f}%",
        flush=True,
    )
    for failure in gate.failures:
        print(f"coverage gate failed: {failure}", file=sys.stderr, flush=True)
    return result.wasSuccessful() and gate.passed


def _architecture_candidate_noise_unit_gate(inventory_name='architecture-candidate-noise-test-inventory.json', label='candidate-noise') -> bool:
    inventory = json.loads((TEST_ROOT / inventory_name).read_text())
    modules = tuple('kb_scanner/' + name for name in inventory['modules'])
    for mapping in inventory['modules'].values():
        if not (ROOT / mapping['unit']).is_file():
            return False
    coverage = Coverage(data_file=f'/tmp/kb-{label}.coverage', branch=True, source=[name.removesuffix('.py').replace('/', '.') for name in modules])
    coverage.erase()
    coverage.start()
    discovered = unittest.defaultTestLoader.discover(str(TEST_ROOT / 'unit'), top_level_dir=str(ROOT))
    selected = {}
    def collect(suite):
        for item in suite:
            if isinstance(item, unittest.TestSuite):
                collect(item)
            elif not any(marker in item.id() for marker in ('.ArchitectureEnumFrontendTests.', '.ArchitectureEnumProjectionTests.', '.PipelineContractTests.', '.CompositeTests.test_composite_frontend_normalizer_analyzer_detector_preserve_both_domains')):
                selected[item.id()] = item
    collect(discovered)
    from unittest.mock import patch
    from contextlib import ExitStack
    with ExitStack() as boundaries:
        boundaries.enter_context(patch('kb_scanner.frontends.cpp.tree_sitter_adapter.Parser', side_effect=AssertionError('real parser forbidden in isolated candidate unit gate')))
        if label == 'rpm-architecture':
            from types import SimpleNamespace
            # Older analyzer suites feed mixed fixtures through BuildFrontend. Their
            # unrelated RPM script boundary is a damaged empty fake, not real Bash.
            fake_tree = SimpleNamespace(root_node=SimpleNamespace(named_children=(), has_error=True))
            boundaries.enter_context(patch('kb_scanner.frontends.build.rpm.shell.Language'))
            boundaries.enter_context(patch('kb_scanner.frontends.build.rpm.shell.Parser',
                                           return_value=SimpleNamespace(parse=lambda _: fake_tree)))
        result = _run(unittest.TestSuite(selected[key] for key in sorted(selected)), f'{label}-isolated-unit')
    coverage.stop()
    coverage.save()
    path = f'/tmp/kb-{label}-coverage.json'
    coverage.json_report(outfile=path)
    payload = json.loads(Path(path).read_text())
    gate = evaluate_frontend_coverage(payload, modules, line_threshold=90.0, branch_threshold=80.0, enforce_module_thresholds=True)
    for name in modules:
        details = payload['files'][name]
        print(name, json.dumps(details['summary']), 'missing lines:', details['missing_lines'], flush=True)
    for failure in gate.failures:
        print(f'coverage gate failed: {failure}', file=sys.stderr, flush=True)
    return result.wasSuccessful() and gate.passed


def _full_regression() -> bool:
    suite = unittest.TestSuite()
    for path in sorted(TEST_ROOT.glob("test_*.py"), key=lambda item: item.name):
        suite.addTests(unittest.defaultTestLoader.loadTestsFromName(f"tests.{path.stem}"))
    return _run(suite, "full-regression").wasSuccessful()


def _performance_unit_gate() -> bool:
    inventory = json.loads((TEST_ROOT / "large-project-performance-test-inventory.json").read_text())
    modules = tuple(inventory["modules"])
    for suites in inventory["modules"].values():
        for suite in suites:
            if not (ROOT / (suite.replace(".", "/") + ".py")).is_file():
                raise ValueError("missing performance unit mapping: " + suite)
    coverage = Coverage(data_file="/tmp/kb-performance.coverage", branch=True,
                        source=[name.removesuffix(".py").replace("/", ".") for name in modules])
    coverage.start()
    discovered = unittest.defaultTestLoader.discover(str(TEST_ROOT / "unit"), top_level_dir=str(ROOT))
    selected = {}
    def collect(suite):
        for item in suite:
            if isinstance(item, unittest.TestSuite):
                collect(item)
            elif not any(marker in item.id() for marker in (
                ".ArchitectureEnumFrontendTests.", ".ArchitectureEnumProjectionTests.", ".PipelineContractTests.",
                ".CompositeTests.test_composite_frontend_normalizer_analyzer_detector_preserve_both_domains",
            )):
                selected[item.id()] = item
    collect(discovered)
    from unittest.mock import patch
    with patch("kb_scanner.frontends.cpp.tree_sitter_adapter.Parser", side_effect=AssertionError("real parser forbidden")):
        result = _run(unittest.TestSuite(selected[key] for key in sorted(selected)), "performance-isolated-unit")
    coverage.stop()
    coverage.json_report(outfile="/tmp/kb-performance-coverage.json")
    payload = json.loads(Path("/tmp/kb-performance-coverage.json").read_text())
    gate = evaluate_frontend_coverage(payload, modules, line_threshold=90, branch_threshold=80, enforce_module_thresholds=True)
    for name in modules:
        details = payload["files"][name]
        print(name, json.dumps(details["summary"]), "missing:", details["missing_lines"], details["missing_branches"], flush=True)
    for failure in gate.failures:
        print(failure, flush=True)
    return result.wasSuccessful() and gate.passed


def main() -> int:
    if len(sys.argv) == 2 and sys.argv[1] == '--regression-only':
        return 0 if _full_regression() else 1
    if len(sys.argv) == 2 and sys.argv[1] == '--source-evidence-chain-unit':
        return subprocess.run((sys.executable, str(TEST_ROOT / 'run_source_chain_unit_tests.py'),
                               '--output', '/tmp/kb-source-chain-unit'), check=False).returncode
    if len(sys.argv) == 2 and sys.argv[1] == '--rpm-architecture-unit':
        return 0 if _architecture_candidate_noise_unit_gate('rpm-architecture-test-inventory.json', 'rpm-architecture') else 1
    if len(sys.argv) == 2 and sys.argv[1] == "--candidate-semantic-admission-unit":
        return 0 if _architecture_candidate_noise_unit_gate('candidate-semantic-admission-test-inventory.json', 'candidate-semantic-admission') else 1
    if len(sys.argv) == 2 and sys.argv[1] == "--performance-unit":
        return 0 if _performance_unit_gate() else 1
    if len(sys.argv) == 2 and sys.argv[1] == '--architecture-candidate-noise-unit':
        return 0 if _architecture_candidate_noise_unit_gate() else 1
    if len(sys.argv) == 2 and sys.argv[1] == "--knowledge-production-unit":
        return 0 if _knowledge_production_unit_gate() else 1
    if len(sys.argv) == 2 and sys.argv[1] == "--knowledge-unit":
        return 0 if _knowledge_detection_unit_gate() else 1
    if len(sys.argv) == 2 and sys.argv[1] == "--frontend-unit":
        return 0 if _unit_gate() else 1
    if len(sys.argv) == 2 and sys.argv[1] == "--graph-unit":
        return 0 if _evidence_graph_unit_gate() else 1
    if len(sys.argv) == 2 and sys.argv[1] == "--build-selection-unit":
        return 0 if _build_selection_unit_gate() else 1
    if len(sys.argv) == 2 and sys.argv[1] == "--classification-assessment-unit":
        return 0 if _classification_assessment_unit_gate() else 1
    if len(sys.argv) == 2 and sys.argv[1] == "--compatible-cutover-unit":
        return 0 if _compatible_cutover_unit_gate() else 1
    if len(sys.argv) == 2 and sys.argv[1] == "--projection-reachability-unit":
        return 0 if _projection_reachability_unit_gate() else 1
    if len(sys.argv) == 2 and sys.argv[1] == "--schema-v2-contract":
        return 0 if _schema_v2_contract_gate() else 1
    if len(sys.argv) == 2 and sys.argv[1] == "--schema-v2-projection-unit":
        return 0 if _schema_v2_projection_unit_gate() else 1
    if len(sys.argv) == 2 and sys.argv[1] == "--architecture-enum-unit":
        return 0 if _architecture_enum_unit_gate() else 1
    if len(sys.argv) == 2 and sys.argv[1] == "--tree-sitter-native-crash-unit":
        return 0 if _tree_sitter_native_crash_unit_gate() else 1
    for mode in ("--source-evidence-chain-unit", "--rpm-architecture-unit", "--candidate-semantic-admission-unit", "--performance-unit", "--architecture-candidate-noise-unit", "--knowledge-production-unit", "--knowledge-unit", "--frontend-unit", "--tree-sitter-native-crash-unit", "--graph-unit", "--build-selection-unit", "--classification-assessment-unit", "--compatible-cutover-unit", "--projection-reachability-unit", "--schema-v2-contract", "--schema-v2-projection-unit", "--architecture-enum-unit"):
        completed = subprocess.run((sys.executable, str(Path(__file__).resolve()), mode), check=False)
        if completed.returncode != 0:
            return completed.returncode
    return 0 if _full_regression() else 1


if __name__ == "__main__":
    raise SystemExit(main())
