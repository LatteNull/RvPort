"""真实 pthread compile-only P4：只编译和分析 BC，不链接或执行目标程序。"""

import json
from pathlib import Path
import time

import pytest

from memory_order_analyzer import cli
from memory_order_analyzer.contracts import canonical, document, identity
from memory_order_analyzer.publication_contracts import expected_publication_protocol, publication_document
from memory_order_analyzer.scope import preflight
from memory_order_analyzer.source_contracts import dependency, expected_source_protocol, source_document
from memory_order_analyzer.source_profile import build_profile
from memory_order_analyzer.thread_contracts import expected_thread_protocol, thread_document
from memory_order_analyzer.validate_analysis import _directory_bytes, _resource_snapshot
from test_offline import collect, WORKER


CASES = {
    "CASE0": ("int flag = 0;", "payload = 42; flag = 1;",
              "while (flag != 1) {}", "finding"),
    "CASE1": ("_Atomic int flag = 0;", "payload = 42; atomic_store_explicit(&flag, 1, memory_order_relaxed);",
              "while (atomic_load_explicit(&flag, memory_order_relaxed) != 1) {}", "finding"),
    "CASE2": ("_Atomic int flag = 0;", "payload = 42; atomic_store_explicit(&flag, 1, memory_order_release);",
              "while (atomic_load_explicit(&flag, memory_order_acquire) != 1) {}", "discharged"),
    "CASE3": ("_Atomic int flag = 0;", "payload = 42; atomic_store_explicit(&flag, 1, memory_order_seq_cst);",
              "while (atomic_load_explicit(&flag, memory_order_seq_cst) != 1) {}", "discharged"),
    "CASE4": ("_Atomic int flag = 0;", "atomic_store_explicit(&payload_atomic, 42, memory_order_relaxed); atomic_store_explicit(&flag, 1, memory_order_relaxed);",
              "while (atomic_load_explicit(&flag, memory_order_relaxed) != 1) {} int atomic_value = atomic_load_explicit(&payload_atomic, memory_order_relaxed); (void)atomic_value;", "finding"),
    "CASE5": ("_Atomic int flag = 0;", "payload = 42; atomic_store_explicit(&flag, 1, memory_order_release);",
              "while (atomic_load_explicit(&flag, memory_order_relaxed) != 1) {}", "finding"),
    "CASE6": ("_Atomic int flag = 0;", "atomic_store_explicit(&flag, 1, memory_order_release); payload = 42;",
              "while (atomic_load_explicit(&flag, memory_order_acquire) != 1) {}", "finding"),
    "CASE7": ("_Atomic int flag = 1;", "payload = 42; atomic_store_explicit(&flag, 1, memory_order_release);",
              "while (atomic_load_explicit(&flag, memory_order_acquire) != 1) {}", "unknown"),
}


def source(flag, producer, consumer):
    return f"""
#include <pthread.h>
#include <stdatomic.h>
{flag}
int payload = 0;
_Atomic int payload_atomic = 0;
static void *producer(void *unused) {{ (void)unused; {producer} return 0; }}
static void *consumer(void *unused) {{ (void)unused; {consumer} int observed_payload = payload; (void)observed_payload; return 0; }}
int start(void) {{
  pthread_t first, second;
  if (pthread_create(&first, 0, producer, 0) != 0) return 1;
  if (pthread_create(&second, 0, consumer, 0) != 0) return 2;
  pthread_join(first, 0); pthread_join(second, 0); return 0;
}}
"""


def cpp_source():
    return """
#include <pthread.h>
#include <atomic>
std::atomic<int> signal{0};
int payload = 0;
static void *producer(void *unused) {
  (void)unused; payload = 42; signal.store(1, std::memory_order_release); return nullptr;
}
static void *consumer(void *unused) {
  (void)unused; while (signal.load(std::memory_order_acquire) != 1) {}
  int observed = payload; (void)observed; return nullptr;
}
int start() {
  pthread_t first, second;
  if (pthread_create(&first, nullptr, producer, nullptr) != 0) return 1;
  if (pthread_create(&second, nullptr, consumer, nullptr) != 0) return 2;
  pthread_join(first, nullptr); pthread_join(second, nullptr); return 0;
}
"""


def analyze(tmp_path, sources, driver, standard, *, closed=True, flags=("-pthread",)):
    report, artifacts, modules, _ = collect(tmp_path, sources, driver, standard, flags=flags)
    assert report["build_status"] == "complete", report["failures"]
    scope = document("ScopeManifest", target_id=standard, members=sorted(artifacts),
                     evidence="P4 显式 compile-only 语言 profile", closed=closed,
                     external_boundaries=[] if closed else ["application-outside-scope"])
    scope_path = tmp_path / "scope.json"; scope_path.write_text(canonical(scope))
    key, root = next((key, function) for key, module in modules.items()
                     for function in module["functions"] if function["name"] in {"start", "_Z5startv", "main"})
    thread_request = thread_document(
        "ThreadAnalysisRequest", scope=str(scope_path),
        roots=[{"artifact_key": key, "function_id": root["id"], "arguments": []}],
        model_id="posix-pthread-v1", budgets=expected_thread_protocol()["budgets"])
    thread_path = tmp_path / "thread-request.json"; thread_path.write_text(canonical(thread_request))
    publication_request = publication_document(
        "PublicationRiskRequest", thread_request=str(thread_path),
        model_id="c-cpp-single-publication-v1", budgets=expected_publication_protocol()["budgets"])
    request_path = tmp_path / "publication-request.json"; request_path.write_text(canonical(publication_request))
    output = tmp_path / "publication-output"
    code = cli.main(["detect-publication-risks", "--request", str(request_path),
                     "--artifact-store", str(tmp_path / "out"), "--output", str(output),
                     "--worker", WORKER])
    result = json.loads((output / "report.json").read_text())
    graph = json.loads(next((output / "graphs").glob("*.json")).read_text())
    return code, result, graph


def source_evidence(tmp_path, database, scope, artifacts, modules, *, artifact_store=None,
                    prefix="source"):
    """Build the explicit AST/IR request used by fixed end-to-end tests."""
    scope_id = preflight(scope, artifacts, modules)
    assert json.loads(Path(database).read_text())
    artifact_store = Path(artifact_store or tmp_path / "out")
    requests = tmp_path / f"{prefix}-requests"; requests.mkdir()
    source_paths, ir_paths = [], []
    planned = []
    compile_records = json.loads(Path(database).read_text())
    for artifact_key, artifact in artifacts.items():
        source = str(Path(artifact["toolchain"]["source"]).resolve())
        matches = [item for item in compile_records
                   if str((Path(item["directory"]) / item["file"]).resolve()) == source and
                   identity(item) == artifact["toolchain"]["compile_record_digest"]]
        assert len(matches) == 1
        record = {**matches[0], "target": artifact["toolchain"]["target"],
                  "abi": artifact["toolchain"]["abi"]}
        profile = build_profile(
            record, compiler_version=artifact["toolchain"]["producer_attested"]["version"],
            include_hashes=[{"path": path, "sha256": digest}
                            for path, digest in artifact["inputs"].items() if path != source])
        physical = identity({"profile_id": profile["profile_id"], "source": source})
        source_request = source_document(
            "SourceSemanticRequest", profile=profile, physical_tu_id=physical,
            source_path=source, budgets=expected_source_protocol()["budgets"])
        ir_request = source_document(
            "LLVMSourceBindingRequest", artifact_key=artifact_key,
            profile_id=profile["profile_id"], physical_tu_id=physical,
            bitcode={"path": artifact["path"], "sha256": artifact["sha256"]},
            budgets=expected_source_protocol()["budgets"])
        planned.append((physical, artifact_key, source_request, ir_request))
    for physical, artifact_key, source_request, ir_request in sorted(planned):
        source_path = requests / f"source-{physical}.json"
        source_path.write_text(canonical(source_request))
        source_paths.append(str(source_path))
        ir_path = requests / f"ir-{artifact_key}.json"
        ir_path.write_text(canonical(ir_request))
        ir_paths.append(str(ir_path))
    ast_request = source_document(
        "AstAssistedAnalysisRequest", scope_id=scope_id,
        source_requests=source_paths, ir_requests=sorted(ir_paths),
        module_facts=sorted((dependency("ModuleFacts", key, value)
                             for key, value in modules.items()), key=lambda item: (item["kind"], item["id"])),
        budgets=expected_source_protocol()["budgets"])
    request_path = tmp_path / f"{prefix}-request.json"; request_path.write_text(canonical(ast_request))
    worker = str(Path(WORKER).with_name("memory-order-source-worker"))
    outputs, reports, measurements = [], [], []
    for mode in ("cold", "warm"):
        output = tmp_path / f"{prefix}-{mode}"
        before = _resource_snapshot(); started = time.perf_counter()
        cache_before = len(list(artifact_store.glob("derived/ast-cross-tu-evidence-v1/**/*.json")))
        assert cli.main(["index-source-evidence", "--request", str(request_path),
                         "--artifact-store", str(artifact_store), "--output", str(output),
                         "--worker", worker]) in {0, 2}
        after = _resource_snapshot()
        report = json.loads((output / "report.json").read_text())
        outputs.append(output); reports.append(report)
        measurements.append({"mode": mode, "wall_seconds": time.perf_counter() - started,
                             "cpu_seconds": max(0.0, after["cpu_seconds"] - before["cpu_seconds"]),
                             "peak_rss_bytes": after["peak_rss_bytes"],
                             "output_bytes": _directory_bytes(output),
                             "cache_files_before": cache_before,
                             "cache_files_after": len(list(artifact_store.glob("derived/ast-cross-tu-evidence-v1/**/*.json"))),
                             "cache": report["cache"], "semantic_digest": report["semantic_digest"]})
    return outputs[0], reports[0], reports[1], measurements


def analyze_ast_comparison(tmp_path, sources, driver, standard, *, flags=("-pthread",)):
    """Run IR-only and explicit AST-assisted P4 over the same immutable inputs."""
    report, artifacts, modules, database = collect(tmp_path, sources, driver, standard, flags=flags)
    assert report["build_status"] == "complete", report["failures"]
    scope = document("ScopeManifest", target_id=f"ast-validation-{standard}",
                     members=sorted(artifacts), evidence="AST/IR v2 fixed comparison scope",
                     closed=True, external_boundaries=[])
    scope_path = tmp_path / "scope.json"; scope_path.write_text(canonical(scope))
    key, root = next((key, function) for key, module in modules.items()
                     for function in module["functions"] if function["name"] in {"start", "_Z5startv", "main"})
    thread_request = thread_document(
        "ThreadAnalysisRequest", scope=str(scope_path),
        roots=[{"artifact_key": key, "function_id": root["id"], "arguments": []}],
        model_id="posix-pthread-v1", budgets=expected_thread_protocol()["budgets"])
    thread_path = tmp_path / "thread.json"; thread_path.write_text(canonical(thread_request))
    publication = publication_document(
        "PublicationRiskRequest", thread_request=str(thread_path),
        model_id="c-cpp-single-publication-v1", budgets=expected_publication_protocol()["budgets"])
    request_path = tmp_path / "publication.json"; request_path.write_text(canonical(publication))
    results = {}
    for mode, source_dir in (("ir_only", None),):
        output = tmp_path / mode
        code = cli.main(["detect-publication-risks", "--request", str(request_path),
                         "--artifact-store", str(tmp_path / "out"), "--output", str(output),
                         "--worker", WORKER])
        results[mode] = {"code": code, "report": json.loads((output / "report.json").read_text()),
                         "graph": json.loads(next((output / "graphs").glob("*.json")).read_text()),
                         "output": output}
    source_dir, source_cold, source_warm, measurements = source_evidence(
        tmp_path, database, scope, artifacts, modules, prefix="ast-source")
    output = tmp_path / "ast_assisted"
    code = cli.main(["detect-publication-risks", "--request", str(request_path),
                     "--artifact-store", str(tmp_path / "out"), "--output", str(output),
                     "--worker", WORKER, "--source-evidence", str(source_dir)])
    results["ast_assisted"] = {
        "code": code, "report": json.loads((output / "report.json").read_text()),
        "graph": json.loads(next((output / "graphs").glob("*.json")).read_text()),
        "output": output, "source_report": source_cold, "source_warm": source_warm,
        "measurements": measurements}
    return results


@pytest.mark.parametrize("name", sorted(CASES))
def test_case0_case7_semantic_matrix(name, tmp_path):
    flag, producer, consumer, expected = CASES[name]
    report, artifacts, modules, _ = collect(
        tmp_path, {"publication.c": source(flag, producer, consumer)},
        "clang", "c11", flags=("-pthread",))
    assert report["build_status"] == "complete", report["failures"]
    scope = document("ScopeManifest", target_id=name, members=sorted(artifacts),
                     evidence="P4 CASE0–CASE7 显式 compile-only scope", closed=True,
                     external_boundaries=[])
    scope_path = tmp_path / "scope.json"; scope_path.write_text(canonical(scope))
    key, root = next((key, function) for key, module in modules.items()
                     for function in module["functions"] if function["name"] == "start")
    thread_request = thread_document(
        "ThreadAnalysisRequest", scope=str(scope_path),
        roots=[{"artifact_key": key, "function_id": root["id"], "arguments": []}],
        model_id="posix-pthread-v1", budgets=expected_thread_protocol()["budgets"])
    thread_path = tmp_path / "thread-request.json"; thread_path.write_text(canonical(thread_request))
    publication_request = publication_document(
        "PublicationRiskRequest", thread_request=str(thread_path),
        model_id="c-cpp-single-publication-v1", budgets=expected_publication_protocol()["budgets"])
    request_path = tmp_path / "publication-request.json"; request_path.write_text(canonical(publication_request))
    output = tmp_path / "publication-output"
    code = cli.main(["detect-publication-risks", "--request", str(request_path),
                     "--artifact-store", str(tmp_path / "out"), "--output", str(output),
                     "--worker", WORKER])
    result = json.loads((output / "report.json").read_text())
    graph = json.loads(next((output / "graphs").glob("*.json")).read_text())
    statuses = {item["status"] for item in graph["assessments"]}
    assert graph["protocols"], (name, graph)
    assert expected in statuses, (name, graph["assessments"])
    assert code == result["exit_code"]
    assert result["safety"] == "not_established"
    assert not list(tmp_path.glob("*.o"))


@pytest.mark.parametrize("driver,standard,filename,contents", [
    ("clang", "c11", "publication.c", source(
        "_Atomic int flag = 0;",
        "payload = 42; atomic_store_explicit(&flag, 1, memory_order_release);",
        "while (atomic_load_explicit(&flag, memory_order_acquire) != 1) {}")),
    ("gcc", "c17", "publication.c", source(
        "_Atomic int flag = 0;",
        "payload = 42; atomic_store_explicit(&flag, 1, memory_order_release);",
        "while (atomic_load_explicit(&flag, memory_order_acquire) != 1) {}")),
    ("g++", "c++17", "publication.cpp", cpp_source()),
    ("clang++", "c++20", "publication.cpp", cpp_source()),
])
def test_gcc_clang_c_cpp_language_profiles(driver, standard, filename, contents, tmp_path):
    code, result, graph = analyze(tmp_path, {filename: contents}, driver, standard)
    assert code == result["exit_code"]
    assert result["safety"] == "not_established"
    assert graph["protocols"]
    assert all(f":{standard}:" in item["language_profile"] for item in graph["protocols"])
    assert any(item["status"] == "discharged" for item in graph["assessments"])
    assert not list(tmp_path.glob("*.o"))


def test_three_tu_wrapper_nodebug_and_open_scope_are_conservative(tmp_path):
    report, artifacts, modules, _ = collect(tmp_path, {
        "main.c": "#include <pthread.h>\nextern void *producer(void*); extern void *consumer(void*); int start(void){pthread_t a,b; pthread_create(&a,0,producer,0); pthread_create(&b,0,consumer,0); return 0;}",
        "producer.c": "#include <stdatomic.h>\nextern int payload; extern _Atomic int flag; void *producer(void*x){payload=1; atomic_store_explicit(&flag,1,memory_order_release); return x;}",
        "consumer.c": "#include <stdatomic.h>\nint payload; _Atomic int flag=0; int ready(void){return atomic_load_explicit(&flag,memory_order_acquire)==1;} void *consumer(void*x){while(!ready()){} int y=payload; return x+(y==99);}",
    }, "clang", "c17", flags=("-pthread", "-g0"))
    assert report["build_status"] == "complete"
    scope = document("ScopeManifest", target_id="wrapper", members=sorted(artifacts),
                     evidence="三个物理 TU、无 debug、显式开放边界", closed=False,
                     external_boundaries=["application-outside-scope"])
    scope_path = tmp_path / "scope.json"; scope_path.write_text(canonical(scope))
    key, root = next((key, function) for key, module in modules.items()
                     for function in module["functions"] if function["name"] == "start")
    thread_request = thread_document("ThreadAnalysisRequest", scope=str(scope_path),
        roots=[{"artifact_key": key, "function_id": root["id"], "arguments": []}],
        model_id="posix-pthread-v1", budgets=expected_thread_protocol()["budgets"])
    thread_path = tmp_path / "thread.json"; thread_path.write_text(canonical(thread_request))
    publication = publication_document("PublicationRiskRequest", thread_request=str(thread_path),
        model_id="c-cpp-single-publication-v1", budgets=expected_publication_protocol()["budgets"])
    request_path = tmp_path / "request.json"; request_path.write_text(canonical(publication))
    output = tmp_path / "result"
    code = cli.main(["detect-publication-risks", "--request", str(request_path),
                     "--artifact-store", str(tmp_path / "out"), "--output", str(output),
                     "--worker", WORKER])
    result = json.loads((output / "report.json").read_text())
    assert code in {0, 2, 3} and result["safety"] == "not_established"
    assert result["source_mapping"] in {"partial", "unavailable"}


def test_ast_assisted_three_tu_evidence_is_explicit_cached_and_non_proving(tmp_path):
    report, artifacts, modules, database = collect(tmp_path, {
        "main.c": "#include <pthread.h>\nextern void *producer(void*); extern void *consumer(void*); int start(void){pthread_t a,b; pthread_create(&a,0,producer,0); pthread_create(&b,0,consumer,0); pthread_join(a,0); pthread_join(b,0); return 0;}",
        "producer.c": "#include <stdatomic.h>\nextern int payload; extern _Atomic int flag; void *producer(void*x){payload=1; atomic_store_explicit(&flag,1,memory_order_release); return x;}",
        "consumer.c": "#include <stdatomic.h>\nint payload; _Atomic int flag=0; void *consumer(void*x){while(atomic_load_explicit(&flag,memory_order_acquire)!=1){} int y=payload; return x+(y==99);}",
    }, "clang", "c17", flags=("-pthread", "-g"))
    assert report["build_status"] == "complete"
    scope = document("ScopeManifest", target_id="ast-three-tu", members=sorted(artifacts),
                     evidence="固定 AST+IR 三 TU compile-only scope", closed=True,
                     external_boundaries=[])
    scope_path = tmp_path / "scope.json"; scope_path.write_text(canonical(scope))
    source_dir, cold, warm, measurements = source_evidence(tmp_path, database, scope, artifacts, modules)
    assert cold["semantic_digest"] == warm["semantic_digest"]
    assert warm["cache"]["hits"] > cold["cache"]["hits"]
    assert measurements[0]["semantic_digest"] == measurements[1]["semantic_digest"]
    binding = json.loads((source_dir / "source-ir-binding.json").read_text())
    overlay = json.loads((source_dir / "canonical-object-overlay.json").read_text())
    assert any(item["resolution"] == "exact" for item in binding["entity_bindings"])
    assert len([item for item in overlay["mappings"] if item["resolution"] == "exact"]) >= 2

    key, root = next((key, function) for key, module in modules.items()
                     for function in module["functions"] if function["name"] == "start")
    thread_request = thread_document(
        "ThreadAnalysisRequest", scope=str(scope_path),
        roots=[{"artifact_key": key, "function_id": root["id"], "arguments": []}],
        model_id="posix-pthread-v1", budgets=expected_thread_protocol()["budgets"])
    thread_path = tmp_path / "thread-ast.json"; thread_path.write_text(canonical(thread_request))
    publication = publication_document(
        "PublicationRiskRequest", thread_request=str(thread_path),
        model_id="c-cpp-single-publication-v1", budgets=expected_publication_protocol()["budgets"])
    request_path = tmp_path / "publication-ast.json"; request_path.write_text(canonical(publication))
    output = tmp_path / "publication-ast-output"
    code = cli.main(["detect-publication-risks", "--request", str(request_path),
                     "--artifact-store", str(tmp_path / "out"), "--output", str(output),
                     "--worker", WORKER, "--source-evidence", str(source_dir)])
    result = json.loads((output / "report.json").read_text())
    graph = json.loads(next((output / "graphs").glob("*.json")).read_text())
    assert code == result["exit_code"] and result["safety"] == "not_established"
    assert {item["kind"] for item in graph["dependencies"]} >= {
        "SourceIRBinding", "CanonicalObjectOverlay"}
    assert (output / "source-assistance" / "candidate-slices.json").is_file()
    assert not list(tmp_path.glob("*.o"))


def test_std_thread_experiment_remains_ir_only_and_is_not_claimed_as_supported(tmp_path):
    fixture = (Path(__file__).parents[2] / "tests/fixtures/validation/std-thread-publication.cpp").read_text()
    code, result, graph = analyze(tmp_path, {"publication.cpp": fixture}, "clang++", "c++17")
    assert code == result["exit_code"]
    assert result["safety"] == "not_established"
    assert not graph["protocols"]
    assert not result["findings"]
