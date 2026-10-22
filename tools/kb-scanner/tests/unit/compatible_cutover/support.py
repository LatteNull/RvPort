from __future__ import annotations

from pathlib import Path

from kb_scanner.core import (
    AnalysisSnapshot, Assessment, AssessmentSnapshot, Classification, ClassificationSnapshot,
    DetectionSnapshot, Entity, Evidence, FrontendSnapshot, KnowledgeEntry, KnowledgeSnapshot,
    KnowledgeSource, NormalizedSnapshot, Observation, ProofPath, Relation, ScanContext,
    SourceLocation, SourceSpan, WorkspaceSnapshot, stable_id,
)


def context(root: Path, *, formats: tuple[str, ...] = ("json", "html"), compile_contexts=()) -> ScanContext:
    return ScanContext(
        root, root / "out", root / "rules", ("c", "cpp"), (), (), formats, "auto", "riscv64",
        False, True, "zh-CN", None, compile_contexts, "source_context", "riscv-porting", "1",
        "knowledge@1", "kb-scanner", "1",
    )


def payload() -> dict:
    summary = {
        "files": 1, "findings": 0, "issues": 0, "hints": 0, "blocking": 0,
        "portabilityGaps": 0, "inactiveOrGuarded": 0, "referenceSources": 0, "references": 0,
    }
    return {
        "schemaVersion": "1.0", "tool": {"name": "kb-scanner", "version": "1"},
        "rulePack": {"id": "riscv-porting", "version": "1"},
        "project": {"root": "/project", "scanMode": "source_context"},
        "summary": summary, "findings": [], "diagnostics": [],
    }


def graph(root: Path, *, impact: str = "blocking_issue", detector: str = "C_CPP.X86.INTRINSIC", kind: str = "x86_intrinsic_reference", with_assessment: bool = True):
    entity = Entity(stable_id("entity", "src/main.c"), "function", "run")
    span = SourceSpan(SourceLocation("src/main.c", 7, 3), SourceLocation("src/main.c", 7, 8))
    evidence = Evidence(stable_id("evidence", "avx"), "symbol", entity.id, "_mm_add_ps", "clang", "ast", "high", span)
    source = KnowledgeSource(stable_id("source", "facts"), "compiler-facts", "generated", "facts.json", "0" * 64)
    entry = KnowledgeEntry(stable_id("entry", "_mm_add_ps"), "intrinsics", "x86", "_mm_add_ps", (source.id,))
    relation = Relation(stable_id("relation", "uses"), "uses", entity.id, entity.id, (evidence.id,), "high", "selected")
    proof = ProofPath(stable_id("proof", "uses"), entity.id, entity.id, (relation.id,), "complete", visited=1)
    observation = Observation(
        stable_id("observation", detector, kind), detector, kind, (evidence.id,), (relation.id,),
        "high", "confirmed_local", {"role": "x86"}, (entry.id,),
    )
    classification = Classification(
        stable_id("classification", impact), "migration-classifier@1", impact, f"reason-{impact}",
        (observation.id,), (evidence.id,), (entry.id,), (relation.id,), (proof.id,), "high",
    )
    assessment = Assessment(
        stable_id("assessment", impact), "project_migration_state", "riscv_blocked" if impact == "blocking_issue" else "needs_review",
        (evidence.id,), (relation.id,), "high", {"dimensions": {"source": "blocked"}, "blockingDimensions": ["source"], "completeness": {"source": "complete"}},
        (classification.id,), (observation.id,), (proof.id,),
    )
    return (
        context(root), WorkspaceSnapshot(root, ("src/main.c",)), KnowledgeSnapshot("facts@1", "1", (source,), (entry,)),
        FrontendSnapshot((entity,), (evidence,)), NormalizedSnapshot(), AnalysisSnapshot((relation,), (entity,), (proof,)),
        DetectionSnapshot((observation,)), ClassificationSnapshot((observation,), (classification,)),
        AssessmentSnapshot((assessment,) if with_assessment else ()), (),
    )
