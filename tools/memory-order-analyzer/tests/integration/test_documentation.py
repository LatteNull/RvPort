"""Content/evidence checks, deliberately separate from unit coverage."""
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import unquote

from memory_order_analyzer.validation_contracts import read_validation_document

ROOT = Path(__file__).resolve().parents[2]


def migration_digest(relative, historical):
    migrations = json.loads((ROOT / "tests/fixtures/migration-artifact-digests.json").read_text())
    if relative not in migrations:
        return historical
    entry = migrations[relative]
    assert entry["historical_sha256"] == historical, relative
    return entry["migration_sha256"]


def test_local_documentation_links():
    failures = []
    for path in [ROOT / "README.md", *ROOT.joinpath("doc").glob("*.md")]:
        for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", path.read_text()):
            if target.startswith(("https://", "http://", "mailto:", "#")):
                continue
            target = unquote(target.split("#")[0].strip("<>"))
            if not (path.parent / target).exists():
                failures.append(f"{path.relative_to(ROOT)} -> {target}")
    assert failures == []


def test_all_scenarios_have_acceptance_entries():
    mapping = (ROOT / "tests/fixtures/documentation/history.md").read_text()
    specs = ROOT / "openspec/changes/archive/2026-09-11-establish-llvm-analysis-foundation/specs"
    scenarios = [scenario for path in specs.glob("*/spec.md") for scenario in re.findall(r"^#### Scenario: (.+)$", path.read_text(), re.M)]
    assert len(scenarios) == 58
    assert all(scenario in mapping for scenario in scenarios)


def test_semantic_scenarios_have_acceptance_entries():
    mapping = (ROOT / "tests/fixtures/documentation/history.md").read_text()
    active = ROOT / "openspec/changes/enrich-ir-semantic-facts/specs"
    specs = active if active.exists() else next(ROOT.joinpath("openspec/changes/archive").glob("*-enrich-ir-semantic-facts/specs"))
    texts = [p.read_text() for p in specs.glob("*/spec.md")]
    scenarios = [s for text in texts for s in re.findall(r"^#### Scenario: (.+)$", text, re.M)]
    requirements = [s for text in texts for s in re.findall(r"^### Requirement: (.+)$", text, re.M)]
    assert len(scenarios) == 34 and len(requirements) == 13
    assert all(s in mapping for s in scenarios + requirements)
    contract = json.loads((ROOT / "schemas/contracts.json").read_text())["$defs"]
    assert contract["ModuleFacts"]["properties"]["schema_version"]["const"] == 2
    assert contract["RunReport"]["properties"]["schema_version"]["const"] == 2
    doc = (ROOT / "doc/semantic-analysis.zh-CN.md").read_text()
    assert all(s in doc for s in ("0.2.0", "100000", "500000", "16777216", "not_evaluated", "artifact_migrations"))


def test_thread_scenarios_have_validation_entries():
    mapping = (ROOT / "tests/fixtures/documentation/history.md").read_text()
    change = ROOT / "openspec/changes/model-thread-and-sync-contexts"
    if not change.is_dir():
        archived = sorted((ROOT / "openspec/changes/archive").glob(
            "*-model-thread-and-sync-contexts"))
        assert archived, "P3 OpenSpec change is neither active nor archived"
        change = archived[-1]
    specs = change / "specs"
    texts = [path.read_text() for path in specs.glob("*/spec.md")]
    scenarios = [value for text in texts for value in re.findall(r"^#### Scenario: (.+)$", text, re.M)]
    requirements = [value for text in texts for value in re.findall(r"^### Requirement: (.+)$", text, re.M)]
    assert len(scenarios) == 62 and len(requirements) == 27
    assert all(value in mapping for value in scenarios + requirements)
    schema = json.loads((ROOT / "schemas/threading.json").read_text())["$defs"]
    assert schema["ThreadContextGraph"]["properties"]["schema_version"]["const"] == 1
    assert schema["ThreadAnalysisReport"]["properties"]["safety"]["const"] == "not_evaluated"
    doc = (ROOT / "doc/thread-analysis.md").read_text()
    assert all(value in doc for value in ("thread-sync-contexts-v1", "posix-pthread-v1",
                                          "EffectSummary.order", "not_evaluated", "findings=null"))


def test_p1_p4_immutable_baseline():
    baseline = json.loads((ROOT / "tests/fixtures/validation/p1-p4-baseline.json").read_text())
    for relative, expected in baseline["files"].items():
        # 历史运行报告不随源码迁移；保留其摘要用于追溯，仍校验全部保留的协议与源码。
        if relative.startswith("reports/"):
            continue
        assert hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() == expected, relative
    contracts = json.loads((ROOT / "schemas/contracts.json").read_text())["$defs"]
    effects = json.loads((ROOT / "schemas/effects.json").read_text())["$defs"]
    threading = json.loads((ROOT / "schemas/threading.json").read_text())["$defs"]
    publication = json.loads((ROOT / "schemas/publication.json").read_text())["$defs"]
    assert contracts["ModuleFacts"]["properties"]["schema_version"]["const"] == 2
    assert contracts["RunReport"]["properties"]["schema_version"]["const"] == 2
    assert effects["EffectSummary"]["properties"]["schema_version"]["const"] == 1
    assert threading["ThreadContextGraph"]["properties"]["schema_version"]["const"] == 1
    assert publication["PublicationRiskReport"]["properties"]["schema_version"]["const"] == 1


def test_p5_status_links_and_safety_boundary():
    roadmap = (ROOT / "tests/fixtures/documentation/history.md").read_text()
    readme = (ROOT / "README.zh-CN.md").read_text()
    assert "P4 [detect-single-publication-risks]" in roadmap and "已完成并归档" in roadmap
    assert "P5 `validate-and-scale-analysis` 已完成实现与质量验收" in readme
    assert "同步主规格并归档" in readme and "非全程序安全结论" in readme
    assert "已完成、验证、同步并归档" in roadmap


def test_p5_validation_numbers_hashes_bilingual_and_safety_boundary():
    text = (ROOT / "tests/fixtures/documentation/history.md").read_text()
    for value in ("3/8 = 37.5%", "TP=3", "strict FN=7", "8/8 = 100%", "not_run",
                  "not_established", "非全程序安全", "6957fc8383d6c7db25b60b8c849b29caab1caaee",
                  "a14757b85a8acab53c184a65cff36974a9666bad77d3d8e1b3d1319eddb0ab24"):
        assert value in text
    decision = read_validation_document(ROOT / "tests/fixtures/validation/decision-baseline.json",
                                        "AnalysisExtensionDecision")
    assert len(decision["entries"]) == 4
    assert all(item["detail"] and item["detail_en"] and item["suggestion"] and item["suggestion_en"]
               and not item["human_confirmed"] for item in decision["entries"])
    sample = json.loads((ROOT / "tests/fixtures/validation/sample-adjudication.json").read_text())
    assert sample["selected_cases"] == sample["adjudicated_cases"] == 5
    assert sample["unadjudicated_cases"] == 0 and sample["inconclusive_cases"] == 2
    assert sample["safety"] == "not_established" and "不外推" in sample["selection_bias"]
    assert {item["name"] for item in sample["strata"]} == {"finding", "discharged", "unknown", "unsupported", "no-candidate"}


def test_a2_protocol_docs_language_matrix_and_archive_provenance():
    from memory_order_analyzer.degraded_contracts import validate_degraded_document

    protocol = json.loads((ROOT / "protocols/degraded-source-analysis-protocol.json").read_text())
    schema = json.loads((ROOT / "schemas/degraded_source_analysis.json").read_text())["$defs"]
    assert protocol["policy_id"] == "degraded-source-analysis-v1"
    assert set(protocol["kinds"]) == {
        "DegradedSourceAnalysisRequest", "TUEvidenceAvailability", "SourceCandidate",
        "SynchronizationGap", "DegradedSourceAnalysisReport", "DegradedValidationSuite",
        "DegradedValidationTruth", "DegradedValidationReport"}
    assert schema["SourceCandidate"]["allOf"][1]["properties"]["evidence_level"]["const"] == "source-only"
    assert schema["SourceCandidate"]["allOf"][1]["properties"]["verdict"]["const"] == "unknown"
    text = (ROOT / "doc/DEGRADED_SOURCE_ANALYSIS.md").read_text()
    for value in ("C11", "C17", "C++17", "C++20", "ast-ir", "ir-only", "ast-only", "failed",
                  "Windows", "MSVC", "clang-cl", "SynchronizationGap", "not-established"):
        assert value in text
    inventory = json.loads((ROOT / "tests/fixtures/degraded-source-analysis/sample-inventory.json").read_text())
    assert inventory["eligible"][0]["source_sha256"] == "f37e516834a9511b5591deb6a2b83ea31332a6923d2d6b932d93f217b9d89eae"
    assert all((ROOT / "tests/fixtures/degraded-source-analysis" / item["local"]).is_file()
               for item in inventory["eligible"])
    validation_root = ROOT / "tests/fixtures/degraded-source-analysis"
    for filename, kind in (
        ("validation-suite.json", "DegradedValidationSuite"),
        ("validation-truth.json", "DegradedValidationTruth"),
        ("validation-report.json", "DegradedValidationReport"),
    ):
        validate_degraded_document(
            json.loads((validation_root / filename).read_text(encoding="utf-8")), kind)
    acceptance = json.loads((ROOT / "tests/fixtures/documentation/DEGRADED_SOURCE_ANALYSIS_ACCEPTANCE.json").read_text())
    assert acceptance["status"] == "validated-synchronized-archived"
    assert acceptance["truth"]["aggregate"]["exact_match"] == {"hit": 8, "total": 8}
    assert acceptance["coverage"]["affected_modules_passed"] is True
    for filename, digest in acceptance["artifacts"].items():
        if filename == "schemas/degraded_source_analysis.json":
            # A2's archived hash remains evidence of that release; the external-BC
            # change intentionally extends failure classification without rewriting it.
            assert {"external-artifact-missing", "external-build-failed",
                    "artifact-format-unsupported", "reader-incompatible"} <= set(
                        schema["FailureRecord"]["properties"]["failure_class"]["enum"])
            continue
        if filename in {"validation-suite.json", "validation-truth.json", "validation-report.json"}:
            path = validation_root / filename
        elif filename == "coverage-summary.json":
            # 历史覆盖率报告不属于交付源码；当前质量结果由 quality 入口重新生成。
            continue
        else:
            path = ROOT / filename
        assert hashlib.sha256(path.read_bytes()).hexdigest() == digest
    assert "memory-model-ir-checker" not in "\n".join(
        path.read_text() for path in ROOT.joinpath("python/memory_order_analyzer").glob("*.py"))


def test_a3_protocol_profiles_truth_acceptance_and_safety_boundary():
    from memory_order_analyzer.cpp_thread_contracts import read_cpp_thread_document

    protocol = json.loads((ROOT / "protocols/cpp-thread-lifecycle-protocol.json").read_text())
    schema = json.loads((ROOT / "schemas/cpp_thread_lifecycle.json").read_text())["$defs"]
    assert protocol["policy_id"] == "cpp-thread-lifecycle-v1"
    assert set(protocol["kinds"]) == {
        "CppThreadLifecycleRequest", "CppThreadLibraryProfile", "CppThreadLocalFacts",
        "CppThreadLifecycleGraph", "CppThreadLifecycleReport", "CppThreadValidationSuite",
        "CppThreadValidationTruth", "CppThreadValidationReport",
    }
    assert schema["CppThreadLifecycleReport"]["allOf"][1]["properties"]["safety"]["const"] == "not_evaluated"

    documentation = (ROOT / "doc/thread-analysis.md").read_text()
    validation = (ROOT / "tests/fixtures/documentation/history.md").read_text()
    for value in ("C11", "C17", "C++17", "C++20", "libstdc++", "libc++", "not_evaluated",
                  "findings", "全程序安全"):
        assert value in documentation + validation

    profiles = [read_cpp_thread_document(path, "CppThreadLibraryProfile")
                for path in sorted(ROOT.joinpath("cpp-thread-profiles").glob("*.json"))]
    assert {(item["vendor"], item["cxx_standard"], item["status"]) for item in profiles} == {
        ("libstdc++", "c++17", "verified"),
        ("libstdc++", "c++20", "verified"),
        ("libc++", "c++20", "verified"),
    }

    fixture = ROOT / "tests/fixtures/cpp-thread-lifecycle"
    read_cpp_thread_document(fixture / "validation-suite.json", "CppThreadValidationSuite")
    read_cpp_thread_document(fixture / "validation-truth.json", "CppThreadValidationTruth")
    report = read_cpp_thread_document(fixture / "validation-report.json", "CppThreadValidationReport")
    assert report["metrics"] == {
        "expected": 16, "actual": 16, "exact": 8, "fp": 0, "fn": 0,
        "unknown": 3, "abstention": 3,
    }

    acceptance = json.loads((ROOT / "tests/fixtures/documentation/CPP_THREAD_LIFECYCLE_ACCEPTANCE.json").read_text())
    assert acceptance["status"] == "validated-synchronized-archived"
    assert acceptance["required_gate"] is True
    assert acceptance["coverage"]["passed"] is True
    assert acceptance["coverage"]["affected_modules_passed"] is True
    assert acceptance["truth"]["safety"] == "not_evaluated"
    assert acceptance["performance"]["semantic_equal"] is True
    assert acceptance["performance"]["cold"]["cache_misses"] == 2
    assert acceptance["performance"]["warm"]["cache_hits"] == 2
    for module in acceptance["coverage"]["affected_modules"].values():
        assert module["lines"]["percent"] >= 90
        assert module["branches"]["percent"] >= 90
    for filename, digest in acceptance["artifacts"].items():
        if filename.startswith("reports/"):
            continue
        assert hashlib.sha256((ROOT / filename).read_bytes()).hexdigest() == migration_digest(filename, digest), filename
    for item in acceptance["profiles"]:
        assert hashlib.sha256((ROOT / item["file"]).read_bytes()).hexdigest() == item["sha256"]


def test_a4_protocol_profiles_truth_docs_and_bilingual_safety_boundary():
    from memory_order_analyzer.cpp_raii_contracts import read_cpp_raii_document

    protocol = json.loads((ROOT / "protocols/cpp-raii-synchronization-protocol.json").read_text())
    schema = json.loads((ROOT / "schemas/cpp_raii_synchronization.json").read_text())["$defs"]
    assert protocol["policy_id"] == "cpp-raii-synchronization-v1"
    assert set(protocol["kinds"]) == {
        "CppRaiiSynchronizationRequest", "CppRaiiSynchronizationProfile", "CppRaiiLocalFacts",
        "CppRaiiSynchronizationGraph", "CppRaiiSynchronizationReport", "CppRaiiValidationSuite",
        "CppRaiiValidationTruth", "CppRaiiValidationReport",
    }
    report_schema = schema["CppRaiiSynchronizationReport"]["allOf"][1]["properties"]
    assert report_schema["safety"]["const"] == "not_established"
    assert report_schema["exit_code"]["enum"] == [0, 1, 2]
    diagnostic = schema["Diagnostic"]
    assert {"detail", "detail_en", "limitation", "limitation_en", "suggestion", "suggestion_en"} <= set(
        diagnostic["required"])

    documentation = (ROOT / "doc/thread-analysis.md").read_text(encoding="utf-8")
    validation = (ROOT / "tests/fixtures/documentation/history.md").read_text(encoding="utf-8")
    for value in ("C11", "C17", "C++17", "C++20", "libstdc++", "libc++", "lock_guard",
                  "unique_lock", "scoped_lock", "not_established", "全程序安全", "0", "2", "1"):
        assert value in documentation + validation

    profiles = [read_cpp_raii_document(path, "CppRaiiSynchronizationProfile")
                for path in sorted(ROOT.joinpath("cpp-raii-profiles").glob("*.json"))]
    assert {(item["vendor"], item["cxx_standard"], item["status"]) for item in profiles} == {
        ("libstdc++", "c++17", "verified"),
        ("libstdc++", "c++20", "verified"),
        ("libc++", "c++20", "verified"),
    }
    assert all(item["lifecycle_profile_id"] for item in profiles)

    fixture = ROOT / "tests/fixtures/cpp-raii-synchronization"
    suite = read_cpp_raii_document(fixture / "validation-suite.json", "CppRaiiValidationSuite")
    truth = read_cpp_raii_document(fixture / "validation-truth.json", "CppRaiiValidationTruth")
    assert len(suite["cases"]) == len(truth["cases"]) == 8
    assert {item["standard"] for item in suite["cases"]} == {"c11", "c17", "c++17", "c++20"}
    inventory = json.loads((fixture / "sample-inventory.json").read_text(encoding="utf-8"))
    sample = fixture / inventory["sources"][0]["local"]
    assert hashlib.sha256(sample.read_bytes()).hexdigest() == inventory["sources"][0]["sha256"]

    acceptance = json.loads((ROOT / "tests/fixtures/documentation/CPP_RAII_SYNCHRONIZATION_ACCEPTANCE.json").read_text())
    assert acceptance["status"] == "validated-awaiting-sync-archive"
    assert acceptance["required_gate"] is True
    assert acceptance["truth"]["cases"] == {"exact": 8, "total": 8}
    assert acceptance["truth"]["facts"]["fp"] == acceptance["truth"]["facts"]["fn"] == 0
    assert acceptance["tests"] == {
        "cpp_unit": {"passed": 92, "failed": 0},
        "python_unit": {"passed": 542, "failed": 0},
        "integration": {"passed": 62, "failed": 0},
    }
    for metric in (acceptance["coverage"]["overall"],
                   *acceptance["coverage"]["languages"].values(),
                   *acceptance["coverage"]["affected_modules"].values()):
        assert metric["lines"]["percent"] >= 90
        assert metric["branches"]["percent"] >= 90
    for relative, expected in acceptance["artifacts"].items():
        if relative.startswith("reports/"):
            continue
        assert hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() == migration_digest(relative, expected), relative
    for item in acceptance["profiles"]:
        assert hashlib.sha256((ROOT / item["file"]).read_bytes()).hexdigest() == item["sha256"]
