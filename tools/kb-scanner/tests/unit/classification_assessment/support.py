from __future__ import annotations

from pathlib import Path

from kb_scanner.core import (
    AnalysisSnapshot,
    Entity,
    Evidence,
    KnowledgeEntry,
    KnowledgeSnapshot,
    KnowledgeSource,
    NormalizedFact,
    NormalizedSnapshot,
    Observation,
    ProofPath,
    Relation,
    ScanContext,
    stable_id,
)


ROOT = Path(__file__).resolve().parents[3]


def context() -> ScanContext:
    return ScanContext(
        ROOT,
        ROOT / "out",
        ROOT / "rulesets/riscv-porting",
        ("c", "cpp"),
        (),
        (),
        ("json",),
        "auto",
        "riscv64",
        False,
        True,
        "zh-CN",
        None,
        (),
        "source_context",
        "riscv-porting",
        "1",
        "test@1",
        "kb-scanner",
        "1",
    )


def knowledge(*values: str) -> KnowledgeSnapshot:
    source_id = stable_id("knowledge-source", "unit")
    source = KnowledgeSource(source_id, "unit", "generated", "facts.json", "0" * 64)
    entries = tuple(
        KnowledgeEntry(stable_id("knowledge-entry", value), "compilerFlags", "x86", value, (source_id,))
        for value in values
    )
    return KnowledgeSnapshot(stable_id("knowledge", values), "1", (source,), entries)


def test_facts(
    *,
    status: str = "selected",
    input_kind: str = "ctest",
    target: str = "unit-test",
    include_x86: bool = True,
    source_name: str = "tests/test_math.c",
) -> NormalizedSnapshot:
    subject = Entity(stable_id("entity", "build-file"), "build_file", "ctest-v1.json")
    source = Entity(stable_id("entity", source_name), "source_file", source_name)
    records = [
        ("build_target", target, {"inputKind": input_kind, "target": target, "configuration": "cfg", "selectionStatus": status}),
        ("build_source", source_name, {"inputKind": input_kind, "target": target, "configuration": "cfg", "selectionStatus": status}),
    ]
    if include_x86:
        records.append(("build_argument", "-mavx", {"inputKind": input_kind, "target": target, "configuration": "cfg", "selectionStatus": status}))
    evidence = []
    facts = []
    for index, (kind, value, metadata) in enumerate(records):
        evidence_id = stable_id("evidence", index, kind, value, status)
        evidence.append(Evidence(evidence_id, kind, subject.id, value, "unit", "static-build", "high", metadata=metadata))
        facts.append(
            NormalizedFact(
                stable_id("fact", index, kind, value, status),
                kind,
                subject.id,
                value,
                f"unit:{index}",
                (evidence_id,),
                producers=("unit",),
                metadata=metadata,
            )
        )
    return NormalizedSnapshot((subject, source), tuple(evidence), tuple(facts))


def proof_analysis(*, status: str = "selected", role: str = "x86", test: bool = False) -> tuple[AnalysisSnapshot, Observation]:
    selector = Entity(stable_id("entity", "selector"), "architecture_selector", "riscv64")
    target = Entity(stable_id("entity", "target", test), "test_target" if test else "build_argument", "unit-test" if test else "-mavx")
    evidence_id = stable_id("evidence", "proof")
    relation = Relation(
        stable_id("relation", status, role, test),
        "selects_test" if test else "adds_argument",
        selector.id,
        target.id,
        (evidence_id,),
        "high",
        status,
        {"role": role, "configuration": "cfg", "reason": "unit"},
    )
    proof_status = "complete" if status in {"selected", "inactive", "not_selected"} else "unknown"
    proof = ProofPath(
        stable_id("proof", relation.id, proof_status),
        selector.id,
        target.id,
        (relation.id,),
        proof_status,
        None if proof_status == "complete" else "unit-unknown",
        2,
    )
    kind = "riscv_test_blocker" if test and status == "selected" else "x86_test_guarded" if test else "build_selected_x86_dependency" if status == "selected" else "build_inactive_x86_path"
    observation = Observation(
        stable_id("observation", kind, status),
        "UNIT",
        kind,
        (evidence_id,),
        (relation.id,),
        "high",
        "confirmed_local",
        {"proofPathIds": (proof.id,), "rootCauseId": "root", "configuration": "cfg"},
        (stable_id("knowledge", "x86"),),
    )
    return AnalysisSnapshot((relation,), (selector, target), (proof,)), observation


def assessment_scope(**properties: object) -> Entity:
    defaults = {
        "sourceComplete": True,
        "buildComplete": True,
        "testNotApplicable": True,
        "packagingComplete": True,
    }
    defaults.update(properties)
    return Entity(stable_id("entity", "assessment-scope", defaults), "assessment_scope", "project", properties=defaults)
