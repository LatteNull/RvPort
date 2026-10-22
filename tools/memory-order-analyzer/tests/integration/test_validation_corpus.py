"""Fixed P5 corpus: offline compile-only inputs and human truth identities."""

import json
from pathlib import Path
import subprocess

from memory_order_analyzer.contracts import AnalysisError, file_hash
from memory_order_analyzer.source_contracts import read_source_document
from memory_order_analyzer.source_validation import (
    LAYERS, build_ast_extension_decision, build_ast_validation_report,
)
from memory_order_analyzer.validation_analysis import bind_truth
from memory_order_analyzer.validation_analysis import aggregate_metrics, compare_case, public_case_result
from memory_order_analyzer.validation_contracts import read_validation_document
from test_publication_risks import analyze, analyze_ast_comparison


ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "tests/fixtures/validation/offline-v1"


def test_fixed_corpus_matrix_truth_and_history_are_closed():
    suite = read_validation_document(CORPUS / "suite.json", "ValidationSuiteManifest")
    assert len(suite["profiles"]) == len(suite["cases"]) == 8
    assert {item["standard"] for item in suite["profiles"]} == {"c11", "c17", "c++17", "c++20"}
    assert {item["compiler"] for item in suite["profiles"]} == {"gcc", "clang"}
    assert {item["layout"] for item in suite["cases"]} == {"single-tu", "multi-tu"}
    assert {item["category"] for item in suite["cases"]} == {"correct", "risk", "unknown"}
    history = json.loads((CORPUS / "truth-history.json").read_text())
    history = {item["case_id"]: item for item in history["entries"]}
    before = {}
    for case in suite["cases"]:
        truth_path = CORPUS / case["truth"]["path"]
        before[case["id"]] = file_hash(truth_path)
        truth = read_validation_document(truth_path, "TruthAnnotation")
        bind_truth(CORPUS, suite, case, truth)
        assert history[case["id"]] == {"case_id": case["id"], "truth_version": truth["truth_version"],
                                       "truth_sha256": before[case["id"]], "input_digest": truth["input_digest"]}
        physical_tus = [item for item in case["sources"] if Path(item["path"]).suffix in (".c", ".cpp")]
        assert len(physical_tus) >= (3 if case["layout"] == "multi-tu" else 1)
    assert before == {case["id"]: file_hash(CORPUS / case["truth"]["path"]) for case in suite["cases"]}


def test_fixed_corpus_sources_compile_without_link_or_execution():
    suite = read_validation_document(CORPUS / "suite.json", "ValidationSuiteManifest")
    for case in suite["cases"]:
        case_dir = CORPUS / case["source_root"]
        database = json.loads((CORPUS / case["compile_commands"]["path"]).read_text())
        assert len(database) == len([item for item in case["sources"] if Path(item["path"]).suffix in (".c", ".cpp")])
        for record in database:
            arguments = [*record["arguments"]]
            arguments[arguments.index("-c")] = "-fsyntax-only"
            completed = subprocess.run(arguments, cwd=case_dir, text=True, capture_output=True, check=False)
            assert completed.returncode == 0, (case["id"], record["file"], completed.stderr)


def test_fixed_corpus_runs_p1_p4_against_human_truth(tmp_path):
    suite = read_validation_document(CORPUS / "suite.json", "ValidationSuiteManifest")
    profiles = {item["id"]: item for item in suite["profiles"]}
    results = []
    for case in suite["cases"]:
        profile = profiles[case["profile_id"]]
        case_dir = tmp_path / case["id"]; case_dir.mkdir()
        sources = {}
        for entry in case["sources"]:
            content = (CORPUS / entry["path"]).read_text()
            name = Path(entry["path"]).name
            if entry["role"] == "header":
                (case_dir / name).write_text(content)
            else:
                sources[name] = content
        driver = ("g++" if profile["language"] == "c++" else "gcc") if profile["compiler"] == "gcc" else ("clang++" if profile["language"] == "c++" else "clang")
        truth = read_validation_document(CORPUS / case["truth"]["path"], "TruthAnnotation")
        try:
            _, report, graph = analyze(case_dir, sources, driver, profile["standard"])
            result = compare_case(case, truth, report, graph)
        except FileNotFoundError:
            required = len(truth["expected"]["required_findings"])
            result = {"case_id": case["id"], "profile_id": case["profile_id"], "category": case["category"],
                      "status": "failed", "matched": False, "strict_fn": required, "abstained": True,
                      "required_missing": truth["expected"]["required_findings"], "forbidden_observed": [],
                      "semantic_digests": {}, "resources": {}, "diagnostics": [],
                      "_counts": {"tp": 0, "fp": 0, "fn": required,
                                  "supported_tp": 0, "supported_fp": 0, "supported_fn": 0}}
        results.append(result)
    metrics = aggregate_metrics(results)
    evidence = {"planned": len(suite["cases"]), "executed": len(results),
                "matched": sum(item["matched"] for item in results), "metrics": metrics,
                "cases": [public_case_result(item) for item in results], "safety": "not_established"}
    (tmp_path / "corpus-evidence.json").write_text(json.dumps(evidence, sort_keys=True) + "\n")
    assert evidence["planned"] == evidence["executed"] == 8
    assert {item["category"] for item in results} == {"correct", "risk", "unknown"}
    assert 0 < metrics["exact_match"]["hit"] <= metrics["exact_match"]["total"]


def test_fixed_corpus_runs_ir_and_ast_assisted_against_same_reviewed_truth(tmp_path):
    suite = read_validation_document(CORPUS / "suite.json", "ValidationSuiteManifest")
    profiles = {item["id"]: item for item in suite["profiles"]}
    ast_root = ROOT / "tests/fixtures/validation/ast-ir-v2"
    ast_suite = read_source_document(ast_root / "suite.json", "AstIrValidationSuite")
    ast_truth = read_source_document(ast_root / "truth.json", "AstIrValidationTruth")
    truth = {item["case_id"]: item["verdict"] for item in ast_truth["cases"]}
    observations, performance = [], []
    for case in suite["cases"]:
        profile = profiles[case["profile_id"]]
        case_dir = tmp_path / case["id"]; case_dir.mkdir()
        sources = {}
        for entry in case["sources"]:
            content = (CORPUS / entry["path"]).read_text()
            name = Path(entry["path"]).name
            if entry["role"] == "header":
                (case_dir / name).write_text(content)
            else:
                sources[name] = content
        driver = (("g++" if profile["language"] == "c++" else "gcc")
                  if profile["compiler"] == "gcc" else
                  ("clang++" if profile["language"] == "c++" else "clang"))
        try:
            results = analyze_ast_comparison(case_dir, sources, driver, profile["standard"])
        except FileNotFoundError:
            results = {}
        for mode in ("ir_only", "ast_assisted"):
            result = results.get(mode)
            graph = result["graph"] if result else {}
            statuses = {item.get("status") for item in graph.get("assessments", [])}
            verdict = "risk" if "finding" in statuses else "discharged" if "discharged" in statuses else "unknown"
            status = "complete" if result and result["report"].get("risk_evaluation") == "complete" else "partial"
            layers = {}
            if mode == "ast_assisted" and result:
                layer_report = result["source_report"]["layers"]
                names = {"profile_replay": "input_profile", "source_extraction": "source_extraction",
                         "entity_resolution": "entity_resolution", "entity_binding": "entity_binding",
                         "expression_binding": "expression_binding", "overlay": "overlay"}
                for target, source_name in names.items():
                    item = layer_report[source_name]
                    layers[target] = {"status": item["status"], "hit": item["counts"]["emitted"],
                                      "total": item["counts"]["planned"]}
                slice_path = result["output"] / "source-assistance/candidate-slices.json"
                slices = json.loads(slice_path.read_text()) if slice_path.is_file() else None
                count = slices["counts"]["candidates"] if slices else {"planned": 0, "emitted": 0}
                layers["candidate_slices"] = {"status": slices["status"] if slices else "not_run",
                                               "hit": count["emitted"], "total": count["planned"]}
                performance.extend({"case_id": case["id"], **item} for item in result["measurements"])
            observations.append({"mode": mode, "case_id": case["id"], "status": status,
                                 "verdict": verdict, "matched": verdict == truth[case["id"]],
                                 "abstained": status != "complete" or verdict == "unknown",
                                 "supported": status == "complete" and verdict != "unknown",
                                 "layers": layers})
    report = build_ast_validation_report(ast_suite, ast_truth, observations,
                                         performance={"runs": performance})
    (tmp_path / "ast-validation-report.json").write_text(json.dumps(report, sort_keys=True) + "\n")
    decision = build_ast_extension_decision(ast_suite, report)
    (tmp_path / "ast-extension-decision.json").write_text(json.dumps(decision, sort_keys=True) + "\n")
    assert report["modes"]["ir_only"]["cases"] == report["modes"]["ast_assisted"]["cases"] == 8
    assert report["safety"] == "not_established"
    assert not report["delta"]["new_false_positives"]
    ast_metrics = report["modes"]["ast_assisted"]
    assert ast_metrics["exact_match"]["hit"] == ast_metrics["exact_match"]["total"] == 8
    assert (ast_metrics["true_positive"], ast_metrics["false_positive"],
            ast_metrics["false_negative"]) == (3, 0, 0)
    ast_cases = {item["case_id"]: item for item in observations if item["mode"] == "ast_assisted"}
    for case_id in ("c11-risk-multi", "cpp20-risk-multi"):
        assert ast_cases[case_id]["verdict"] == "risk"
        assert ast_cases[case_id]["layers"]["candidate_slices"]["total"] > 0
    assert report["delta"]["still_unknown"] == ["c17-unknown-single", "cpp17-unknown-multi"]
    assert all(not item["human_confirmed"] for item in decision["entries"])
