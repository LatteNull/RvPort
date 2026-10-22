from __future__ import annotations

import json
import os
import platform
import resource
import time
from pathlib import Path

import networkx

from kb_scanner.analyzers import EvidenceGraphAnalyzer
from kb_scanner.detectors import LocalX86Detector
from kb_scanner.frontends.cpp import CppFrontend, CppWorkspaceCollector
from kb_scanner.knowledge import GeneratedFactsKnowledgeProvider
from kb_scanner.normalization import CppEvidenceNormalizer
from tests.unit.knowledge_detection.support import make_context


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FIXTURE = Path("/fixtures/avx-avx2-example-code/source")


def measure(fixture: Path = DEFAULT_FIXTURE) -> dict[str, object]:
    context = make_context(fixture, rule_dir=ROOT / "rulesets" / "riscv-porting")
    workspace = CppWorkspaceCollector().collect(context)
    frontend = CppFrontend().analyze(context, workspace.value)
    knowledge = GeneratedFactsKnowledgeProvider().load(context)
    normalized = CppEvidenceNormalizer().normalize(context, frontend.value)
    rss_before = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    started = time.perf_counter()
    analysis = EvidenceGraphAnalyzer().analyze(context, normalized.value, knowledge.value)
    elapsed = time.perf_counter() - started
    rss_after = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    detections = LocalX86Detector().detect(context, normalized.value, analysis.value, knowledge.value)
    observations = detections.value.observations
    function_macros = [
        item
        for item in frontend.value.evidence
        if item.kind == "macro_definition" and item.metadata.get("nodeType") == "preproc_function_def"
    ]
    replacement_calls = [
        item
        for item in frontend.value.evidence
        if item.kind == "macro_replacement_token" and item.metadata.get("tokenRole") == "call_candidate"
    ]
    return {
        "fixture": fixture.as_posix(),
        "pythonVersion": platform.python_version(),
        "networkxVersion": networkx.__version__,
        "proofBudgets": {"maxDepth": 8, "maxVisited": 10_000, "maxPaths": 4},
        "files": len(workspace.value.files),
        "frontendStatus": frontend.status.value,
        "normalizedStatus": normalized.status.value,
        "analysisStatus": analysis.status.value,
        "detectionStatus": detections.status.value,
        "evidence": len(frontend.value.evidence),
        "facts": len(normalized.value.facts),
        "graphEntities": len(analysis.value.entities),
        "relations": len(analysis.value.relations),
        "proofPaths": len(analysis.value.proof_paths),
        "functionMacroDefinitions": len(function_macros),
        "replacementCallCandidates": len(replacement_calls),
        "headerObservations": sum(item.kind == "x86_header_reference" for item in observations),
        "vectorTypeObservations": sum(item.kind == "x86_vector_type_reference" for item in observations),
        "directIntrinsicObservations": sum(
            item.kind == "x86_intrinsic_reference" and item.metadata.get("factKind") == "symbol"
            for item in observations
        ),
        "replacementIntrinsicObservations": sum(
            item.kind == "x86_intrinsic_reference" and item.metadata.get("factKind") == "macro_replacement"
            for item in observations
        ),
        "commentHintObservations": sum(item.kind == "x86_comment_hint" for item in observations),
        "graphSeconds": elapsed,
        "graphPeakRssDeltaMiB": max(0, rss_after - rss_before) / 1024,
        "diagnostics": [item.code for item in (*frontend.diagnostics, *normalized.diagnostics, *analysis.diagnostics, *detections.diagnostics)],
    }


def main() -> int:
    fixture = Path(os.environ.get("KB_SCANNER_AVX_FIXTURE", str(DEFAULT_FIXTURE)))
    print(json.dumps(measure(fixture), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
