"""Public machine-readable CLI. Diagnostic prose goes to stderr only."""

import argparse
import json
from pathlib import Path
import sys

from .contracts import AnalysisError, canonical, read_document
from .execution import OutputStore
from .pipeline import import_bc, write_json
from .report import make_report
from .scope import index_scope
from .toolchain import reader_doctor
from .external_bitcode_ingestion import ingest_bundle
from .external_bitcode_contracts import failed_report as failed_ingestion_report
from .summarize import failed_report, summarize
from .model_threads import model_threads
from .thread_report import failed_thread_report
from .detect_publication import detect_publication_risks
from .publication_report import failed_publication_report
from .validate_analysis import validate_analysis
from .validation_contracts import failed_validation_report
from .index_source_evidence import failed_source_report, index_source_evidence
from .analyze_degraded_source import analyze_degraded_source, failed_degraded_report
from .model_cpp_thread_lifecycle import model_cpp_thread_lifecycle
from .cpp_thread_analysis import failed_lifecycle_report
from .model_cpp_raii_synchronization import model_cpp_raii_synchronization
from .cpp_raii_analysis import failed_synchronization_report
from .analyze_object_provenance import analyze_object_provenance
from .object_provenance import failed_report as failed_provenance_report
from .plan_execution_roots import plan_execution_roots
from .root_analysis import failed_root_report
from .discover_thread_entries import discover_thread_entries
from .thread_entry_analysis import failed_report as failed_thread_entry_report
from .build_concurrent_access_candidates import build_concurrent_access_candidates
from .concurrent_access_analysis import failed_report as failed_concurrent_access_report
from .analyze_demanded_functions import analyze_demanded_functions
from .analyze_demanded_functions import failed_report as failed_demand_report
from .model_fence_rmw_publication import model_fence_rmw_publication
from .advanced_atomic_contracts import failed_report as failed_advanced_atomic_report
from .unified_coordinator import analyze_project
from .unified_contracts import failed_report as failed_unified_report


def parser():
    result = argparse.ArgumentParser(description="LLVM facts infrastructure; safety is not evaluated")
    commands = result.add_subparsers(dest="operation", required=True)
    for name in ("doctor", "import-bc", "index"):
        command = commands.add_parser(name)
        command.add_argument("--worker", default="/output/build/moa-worker")
        if name != "doctor":
            command.add_argument("--output", type=Path, required=True)
        if name == "import-bc":
            command.add_argument("--input", type=Path, required=True)
            command.add_argument("--manifest", type=Path)
        if name == "index":
            command.add_argument("--scope", type=Path, required=True)
            command.add_argument("--artifact-store", type=Path, required=True)
    command = commands.add_parser("ingest-bc-bundle")
    command.add_argument("--bundle", type=Path, required=True)
    command.add_argument("--output", type=Path, required=True)
    command.add_argument("--worker", default="/output/build/moa-worker")
    command.add_argument("--cache", type=Path)
    command = commands.add_parser("summarize")
    command.add_argument("--request", type=Path, required=True)
    command.add_argument("--scope", type=Path, required=True)
    command.add_argument("--artifact-store", type=Path, required=True)
    command.add_argument("--worker", default="/output/build/moa-worker")
    command.add_argument("--output", type=Path, required=True)
    command.add_argument("--source-evidence", type=Path,
                         help="Explicit AST-assisted evidence output; omitted keeps P2 IR-only semantics")
    command = commands.add_parser("model-threads")
    command.add_argument("--request", type=Path, required=True)
    command.add_argument("--artifact-store", type=Path, required=True)
    command.add_argument("--worker", default="/output/build/moa-worker")
    command.add_argument("--output", type=Path, required=True)
    command.add_argument("--source-evidence", type=Path,
                         help="Explicit AST-assisted evidence output; omitted keeps P3 IR-only semantics")
    command = commands.add_parser("detect-publication-risks")
    command.add_argument("--request", type=Path, required=True)
    command.add_argument("--artifact-store", type=Path, required=True)
    command.add_argument("--worker", default="/output/build/moa-worker")
    command.add_argument("--output", type=Path, required=True)
    command.add_argument("--source-evidence", type=Path,
                         help="Explicit AST-assisted evidence output; omitted keeps P4 IR-only semantics")
    command = commands.add_parser("validate-analysis")
    command.add_argument("--request", type=Path, required=True)
    command.add_argument("--artifact-store", type=Path, required=True)
    command.add_argument("--worker", default="/output/build/moa-worker")
    command.add_argument("--output", type=Path, required=True)
    command = commands.add_parser("index-source-evidence")
    command.add_argument("--request", type=Path, required=True)
    command.add_argument("--artifact-store", type=Path, required=True)
    command.add_argument("--worker", default="/output/build/memory-order-source-worker")
    command.add_argument("--output", type=Path, required=True)
    command = commands.add_parser("analyze-degraded-source")
    command.add_argument("--request", type=Path, required=True)
    command.add_argument("--artifact-store", type=Path, required=True)
    command.add_argument("--output", type=Path, required=True)
    command.add_argument("--source-worker", default="/output/build/memory-order-source-worker")
    command.add_argument("--ir-worker", default="/output/build/memory-order-source-worker")
    command = commands.add_parser("model-cpp-thread-lifecycle")
    command.add_argument("--request", type=Path, required=True)
    command.add_argument("--artifact-store", type=Path, required=True)
    command.add_argument("--output", type=Path, required=True)
    command.add_argument("--source-worker", default="/output/build/memory-order-source-worker")
    command.add_argument("--ir-worker", default="/output/build/moa-worker")
    command = commands.add_parser("model-cpp-raii-synchronization")
    command.add_argument("--request", type=Path, required=True)
    command.add_argument("--artifact-store", type=Path, required=True)
    command.add_argument("--output", type=Path, required=True)
    command.add_argument("--source-worker", default="/output/build/memory-order-source-worker")
    command.add_argument("--ir-worker", default="/output/build/moa-worker")
    command = commands.add_parser("analyze-object-provenance")
    command.add_argument("--request", type=Path, required=True)
    command.add_argument("--artifact-store", type=Path, required=True)
    command.add_argument("--output", type=Path, required=True)
    command.add_argument("--source-worker", default="/output/build/memory-order-source-worker")
    command.add_argument("--ir-worker", default="/output/build/moa-worker")
    command = commands.add_parser("plan-execution-roots")
    command.add_argument("--request", type=Path, required=True)
    command.add_argument("--artifact-store", type=Path, required=True)
    command.add_argument("--output", type=Path, required=True)
    command.add_argument("--source-worker", default="/output/build/memory-order-source-worker")
    command.add_argument("--ir-worker", default="/output/build/moa-worker")
    command = commands.add_parser("discover-thread-entries")
    command.add_argument("--request", type=Path, required=True)
    command.add_argument("--artifact-store", type=Path, required=True)
    command.add_argument("--output", type=Path, required=True)
    command.add_argument("--source-worker", default="/output/build/memory-order-source-worker")
    command.add_argument("--ir-worker", default="/output/build/moa-worker")
    command = commands.add_parser("build-concurrent-access-candidates")
    command.add_argument("--request", type=Path, required=True)
    command.add_argument("--artifact-store", type=Path, required=True)
    command.add_argument("--output", type=Path, required=True)
    command = commands.add_parser("analyze-demanded-functions")
    command.add_argument("--request", type=Path, required=True)
    command.add_argument("--artifact-store", type=Path, required=True)
    command.add_argument("--worker", default="/output/build/moa-worker")
    command.add_argument("--output", type=Path, required=True)
    command = commands.add_parser("model-fence-rmw-publication")
    command.add_argument("--request", type=Path, required=True)
    command.add_argument("--artifact-store", type=Path, required=True)
    command.add_argument("--output", type=Path, required=True)
    command = commands.add_parser("analyze-project")
    command.add_argument("--request", type=Path, required=True)
    command.add_argument("--output", type=Path, required=True)
    command.add_argument("--ir-worker", default="/output/build/moa-worker")
    command.add_argument("--source-worker", default="/output/build/memory-order-source-worker")
    command.add_argument("--artifact-store", "--cache", dest="cache", type=Path,
                         help="Persistent content-addressed ingestion and coordinator cache")
    return result


def execute(args):
    operation = args.operation
    if operation == "doctor":
        status = reader_doctor(args.worker)
        return make_report(operation, failures=status["failures"], ready=status["ready"]), status
    if operation == "ingest-bc-bundle":
        return ingest_bundle(args.bundle, args.output, args.worker, cache_path=args.cache), None
    if operation == "summarize":
        report = (summarize(args.request, args.scope, args.artifact_store, args.output, args.worker,
                            args.source_evidence) if args.source_evidence else
                  summarize(args.request, args.scope, args.artifact_store, args.output, args.worker))
        return report, None
    if operation == "model-threads":
        report = (model_threads(args.request, args.artifact_store, args.output, args.worker,
                                args.source_evidence) if args.source_evidence else
                  model_threads(args.request, args.artifact_store, args.output, args.worker))
        return report, None
    if operation == "detect-publication-risks":
        report = (detect_publication_risks(args.request, args.artifact_store, args.output, args.worker,
                                           args.source_evidence) if args.source_evidence else
                  detect_publication_risks(args.request, args.artifact_store, args.output, args.worker))
        return report, None
    if operation == "validate-analysis":
        return validate_analysis(args.request, args.artifact_store, args.output, args.worker), None
    if operation == "index-source-evidence":
        return index_source_evidence(args.request, args.artifact_store, args.output, args.worker), None
    if operation == "analyze-degraded-source":
        return analyze_degraded_source(args.request, args.artifact_store, args.output,
                                       args.source_worker, args.ir_worker), None
    if operation == "model-cpp-thread-lifecycle":
        return model_cpp_thread_lifecycle(args.request, args.artifact_store, args.output,
                                          args.source_worker, args.ir_worker), None
    if operation == "model-cpp-raii-synchronization":
        return model_cpp_raii_synchronization(args.request, args.artifact_store, args.output,
                                              args.source_worker, args.ir_worker), None
    if operation == "analyze-object-provenance":
        return analyze_object_provenance(args.request, args.artifact_store, args.output,
                                         args.source_worker, args.ir_worker), None
    if operation == "plan-execution-roots":
        return plan_execution_roots(args.request, args.artifact_store, args.output,
                                    args.source_worker, args.ir_worker), None
    if operation == "discover-thread-entries":
        return discover_thread_entries(args.request, args.artifact_store, args.output,
                                       args.source_worker, args.ir_worker), None
    if operation == "build-concurrent-access-candidates":
        return build_concurrent_access_candidates(args.request, args.artifact_store, args.output), None
    if operation == "analyze-demanded-functions":
        return analyze_demanded_functions(args.request, args.artifact_store, args.output, args.worker), None
    if operation == "model-fence-rmw-publication":
        return model_fence_rmw_publication(args.request, args.artifact_store, args.output), None
    if operation == "analyze-project":
        return analyze_project(args.request, args.output, ir_worker=args.ir_worker,
                               source_worker=args.source_worker, cache_path=args.cache), None
    store = OutputStore(args.output)
    if operation == "import-bc":
        status = reader_doctor(args.worker)
        if not status["ready"]:
            raise AnalysisError("toolchain_not_ready", canonical(status))
    else:
        status = None
    artifacts, facts, failures, cached, scope_index = [], [], [], 0, None
    records, planned = 0, 1
    if operation == "import-bc":
        manifest = read_document(args.manifest, "BCArtifact") if args.manifest else None
        artifact, module = import_bc(args.input, store, args.worker, manifest=manifest)
        artifacts, facts = [artifact], [module]
    else:
        scope = read_document(args.scope, "ScopeManifest")
        members = scope["members"]
        artifact_map = {key: read_document(args.artifact_store / "artifacts" / f"{key}.json", "BCArtifact") for key in members}
        fact_map = {key: read_document(args.artifact_store / "facts" / f"{key}.json", "ModuleFacts") for key in members}
        scope_index = index_scope(scope, artifact_map, fact_map)
        artifacts, facts = list(artifact_map.values()), list(fact_map.values())
        planned = len(artifacts)
        write_json(store, scope_index, f"scopes/{scope_index['scope_id']}.json")
    report = make_report(operation, planned=planned, records=records, artifacts=artifacts, facts=facts,
                         failures=failures, cached=cached, scope=scope_index)
    write_json(store, report, "report.json")
    return report, None


def main(argv=None, *, stdout=None, stderr=None):
    stdout, stderr = stdout or sys.stdout, stderr or sys.stderr
    try:
        args = parser().parse_args(argv)
    except SystemExit as exc:
        if exc.code == 0:
            return 0
        report = (failed_unified_report("request_invalid", "参数无效；请查看 stderr 用法", "Invalid arguments; see stderr usage")
                  if argv and "analyze-project" in argv else
                  failed_ingestion_report("request_invalid", "参数无效；请查看 stderr 用法", "Invalid arguments; see stderr usage")
                  if argv and "ingest-bc-bundle" in argv else
                  failed_demand_report("request_invalid", "参数无效；请查看 stderr 用法", "Invalid arguments; see stderr usage")
                  if argv and "analyze-demanded-functions" in argv else
                  failed_advanced_atomic_report("request_invalid", "参数无效；请查看 stderr 用法", "Invalid arguments; see stderr usage")
                  if argv and "model-fence-rmw-publication" in argv else
                  failed_concurrent_access_report("request_invalid", "参数无效；请查看 stderr 用法", "Invalid arguments; see stderr usage")
                  if argv and "build-concurrent-access-candidates" in argv else
                  failed_thread_entry_report("request_invalid", "参数无效；请查看 stderr 用法", "Invalid arguments; see stderr usage")
                  if argv and "discover-thread-entries" in argv else
                  failed_root_report("request_invalid", "参数无效；请查看 stderr 用法", "Invalid arguments; see stderr usage")
                  if argv and "plan-execution-roots" in argv else
                  failed_provenance_report("request_invalid", "参数无效；请查看 stderr 用法", "Invalid arguments; see stderr usage")
                  if argv and "analyze-object-provenance" in argv else
                  failed_synchronization_report("request_invalid", "参数无效；请查看 stderr 用法", "Invalid arguments; see stderr usage")
                  if argv and "model-cpp-raii-synchronization" in argv else
                  failed_lifecycle_report("request_invalid", "参数无效；请查看 stderr 用法", "Invalid arguments; see stderr usage")
                  if argv and "model-cpp-thread-lifecycle" in argv else
                  failed_degraded_report("request_invalid", "参数无效；请查看 stderr 用法", "Invalid arguments; see stderr usage")
                  if argv and "analyze-degraded-source" in argv else
                  failed_source_report("request_invalid", "参数无效；请查看 stderr 用法", "Invalid arguments; see stderr usage")
                  if argv and "index-source-evidence" in argv else
                  failed_validation_report("request_invalid", "参数无效；请查看 stderr 用法", "Invalid arguments; see stderr usage")
                  if argv and "validate-analysis" in argv else
                  failed_publication_report("request_invalid", "See argument usage on stderr")
                  if argv and "detect-publication-risks" in argv else
                  failed_thread_report("request_invalid", "See argument usage on stderr")
                  if argv and "model-threads" in argv else failed_report("request_invalid", "See argument usage on stderr")
                  if argv and "summarize" in argv else
                  make_report("invalid_request", failures=[{"code": "request_invalid", "detail": "See argument usage on stderr"}]))
        print(canonical(report), file=stdout)
        return 1
    try:
        report, details = execute(args)
    except (AnalysisError, OSError, ValueError) as exc:
        error = exc.as_dict() if isinstance(exc, AnalysisError) else {"code": "io_failed", "detail": str(exc)}
        report, details = ((failed_unified_report(error["code"], error["detail"], error["detail"]), None)
                           if args.operation == "analyze-project" else
                           (failed_ingestion_report(error["code"], error["detail"], error["detail"]), None)
                           if args.operation == "ingest-bc-bundle" else
                           (failed_demand_report(error["code"], error["detail"], error["detail"]), None)
                           if args.operation == "analyze-demanded-functions" else
                           (failed_advanced_atomic_report(error["code"], error["detail"], error["detail"]), None)
                           if args.operation == "model-fence-rmw-publication" else
                           (failed_concurrent_access_report(error["code"], error["detail"], error["detail"]), None)
                           if args.operation == "build-concurrent-access-candidates" else
                           (failed_thread_entry_report(error["code"], error["detail"], error["detail"]), None)
                           if args.operation == "discover-thread-entries" else
                           (failed_root_report(error["code"], error["detail"]), None)
                           if args.operation == "plan-execution-roots" else
                           (failed_provenance_report(error["code"], error["detail"]), None)
                           if args.operation == "analyze-object-provenance" else
                           (failed_synchronization_report(error["code"], error["detail"]), None)
                           if args.operation == "model-cpp-raii-synchronization" else
                           (failed_lifecycle_report(error["code"], error["detail"]), None)
                           if args.operation == "model-cpp-thread-lifecycle" else
                           (failed_degraded_report(error["code"], error["detail"]), None)
                           if args.operation == "analyze-degraded-source" else
                           (failed_source_report(error["code"], error["detail"]), None)
                           if args.operation == "index-source-evidence" else
                           (failed_validation_report(error["code"], error["detail"]), None)
                           if args.operation == "validate-analysis" else
                           (failed_publication_report(error["code"], error["detail"]), None)
                           if args.operation == "detect-publication-risks" else
                           (failed_thread_report(error["code"], error["detail"]), None)
                           if args.operation == "model-threads" else
                           (failed_report(error["code"], error["detail"]), None)
                           if args.operation == "summarize" else
                           (make_report(args.operation, failures=[error]), None))
        print(error["detail"], file=stderr)
    print(canonical({"report": report, "doctor": details}) if details else canonical(report), file=stdout)
    return report["exit_code"]
