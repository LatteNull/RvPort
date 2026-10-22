from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

from kb_scanner.knowledge.extractors import extract_binutils, extract_gcc, extract_llvm, with_descriptor
from kb_scanner.knowledge.identity import candidate_id, curated_entry_id
from kb_scanner.knowledge.production import render_model
from kb_scanner.knowledge.schema import (
    CandidateDecisionModel, CuratedEntryModel, CuratedFactsModel, DecisionLedgerModel, GeneratedFactsV2Model,
    ReferenceRegistryModel, SourceDescriptorModel, SourceReferenceModel,
)


COLLECTED_AT = "2026-09-07"
LLVM_REVISION = "3b5b5c1ec4a3095ab096dd780e84d7ab81f3d7ff"
GCC_REVISION = "04696df09633baf97cdbbdd6e9929b9d472161d3"
BINUTILS_REVISION = "c7f28aad0c99d1d2fec4e52ebfa3735d90ceb8e9"


def _descriptor(source_id: str, url: str, release: str, revision: str, license_id: str) -> SourceDescriptorModel:
    return SourceDescriptorModel(
        sourceId=source_id, officialUrl=url, release=release, revision=revision, license=license_id,
        collectedAt=COLLECTED_AT, inputPaths=("placeholder",), inputSha256=("0" * 64,),
    )


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(root: Path, path: str, model: object) -> None:
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(render_model(model))


def refresh(llvm_root: Path, gcc_root: Path, binutils_root: Path, output_root: Path) -> None:
    instruction_paths = tuple(
        path.relative_to(llvm_root).as_posix()
        for path in sorted((llvm_root / "llvm/lib/Target/X86").glob("X86Instr*.td"))
    )
    llvm = extract_llvm(
        llvm_root, "llvm/lib/Target/X86/X86RegisterInfo.td", "llvm/lib/Target/X86/X86.td", instruction_paths,
    )
    gcc = extract_gcc(gcc_root, "gcc/common/config/i386/i386-common.cc", "gcc/common/config/i386/i386-isas.h")
    binutils = extract_binutils(binutils_root, "opcodes/i386-opc.tbl", "opcodes/i386-reg.tbl")
    for result in (llvm, gcc, binutils):
        if not result.succeeded:
            raise RuntimeError(result.diagnostics)

    generated = (
        ("generated/binutils-2.42-x86.json", GeneratedFactsV2Model(
            schemaVersion="2.0",
            source=with_descriptor(_descriptor(
                "binutils-2.42-x86", "https://sourceware.org/git/binutils-gdb.git", "binutils-2_42",
                BINUTILS_REVISION, "GPL-3.0-or-later",
            ), binutils), facts=binutils.facts,
        )),
        ("generated/gcc-14.2.0-x86-target.json", GeneratedFactsV2Model(
            schemaVersion="2.0",
            source=with_descriptor(_descriptor(
                "gcc-14.2.0-x86-target", "https://gcc.gnu.org/git/gcc.git", "releases/gcc-14.2.0",
                GCC_REVISION, "GPL-3.0-or-later WITH GCC-exception-3.1",
            ), gcc), facts=gcc.facts,
        )),
        ("generated/llvm-18.1.8-x86.json", GeneratedFactsV2Model(
            schemaVersion="2.0",
            source=with_descriptor(_descriptor(
                "llvm-18.1.8-x86", "https://github.com/llvm/llvm-project", "llvmorg-18.1.8",
                LLVM_REVISION, "Apache-2.0 WITH LLVM-exception",
            ), llvm), facts=llvm.facts,
        )),
    )
    for path, model in generated:
        _write(output_root, path, model)

    reference_specs = (
        ("gcc-14.2.0-cpuid-header", "gcc/config/i386/cpuid.h", "cpuid.h API declarations"),
        ("gcc-14.2.0-ia32intrin-header", "gcc/config/i386/ia32intrin.h", "RDTSC/RDTSCP intrinsic declarations"),
        ("gcc-14.2.0-vector-extensions", "gcc/doc/extend.texi", "vector_size attribute documentation"),
    )
    references = tuple(
        SourceReferenceModel(
            referenceId=reference_id,
            officialUrl=f"https://gcc.gnu.org/git/?p=gcc.git;a=blob;f={logical_path};hb={GCC_REVISION}",
            release="releases/gcc-14.2.0", revision=GCC_REVISION, logicalLocation=location,
            license="GPL-3.0-or-later WITH GCC-exception-3.1" if "/doc/" not in logical_path else "GFDL-1.3-or-later",
            collectedAt=COLLECTED_AT, sha256=_sha(gcc_root / logical_path),
        )
        for reference_id, logical_path, location in reference_specs
    )
    registry = ReferenceRegistryModel(schemaVersion="1.0", references=references)
    _write(output_root, "curated/source-references.json", registry)

    curated_specs = (
        ("cpuPlatformApis", "__cpuid", "x86-only", ("gcc-14.2.0-cpuid-header",)),
        ("cpuPlatformApis", "__cpuid_count", "x86-only", ("gcc-14.2.0-cpuid-header",)),
        ("cpuPlatformApis", "__get_cpuid", "x86-only", ("gcc-14.2.0-cpuid-header",)),
        ("cpuPlatformApis", "__get_cpuid_count", "x86-only", ("gcc-14.2.0-cpuid-header",)),
        ("cpuPlatformApis", "__rdtsc", "x86-only", ("gcc-14.2.0-ia32intrin-header",)),
        ("cpuPlatformApis", "__rdtscp", "x86-only", ("gcc-14.2.0-ia32intrin-header",)),
        ("vectorWidthMarkers", "vector_size(16)", "migration-sensitive", ("gcc-14.2.0-vector-extensions",)),
        ("vectorWidthMarkers", "vector_size(32)", "migration-sensitive", ("gcc-14.2.0-vector-extensions",)),
        ("vectorWidthMarkers", "vector_size(64)", "migration-sensitive", ("gcc-14.2.0-vector-extensions",)),
    )
    entries = tuple(
        CuratedEntryModel(
            entryId=curated_entry_id(kind, "x86", value), factKind=kind, architectureFamily="x86",
            canonicalValue=value, semanticScope=scope, referenceIds=reference_ids, reviewStatus="accepted",
        )
        for kind, value, scope, reference_ids in curated_specs
    )
    curated = CuratedFactsModel(
        schemaVersion="1.0", sourceId="curated-x86-migration-semantics",
        reviewPolicy="authority-source-and-independent-maintainer-review", reviewPolicyVersion="1.0", entries=entries,
    )
    _write(output_root, "curated/x86-migration-semantics.json", curated)

    decisions = (
        CandidateDecisionModel(
            decisionId=candidate_id("assembly-instruction", "toolchain tables"), category="assembly-instruction",
            candidateValue="toolchain tables", status="generated", referenceIds=("binutils-2.42-x86", "llvm-18.1.8-x86"),
            rationale="Opcode and register identities are deterministic upstream definitions.", runtimeFactKind="assemblyInstructions",
        ),
        CandidateDecisionModel(
            decisionId=candidate_id("cpu-platform-api", "cpuid and rdtsc APIs"), category="cpu-platform-api",
            candidateValue="cpuid and rdtsc APIs", status="accepted",
            referenceIds=("gcc-14.2.0-cpuid-header", "gcc-14.2.0-ia32intrin-header"),
            rationale="GCC x86 headers define the compiler-facing source spellings.", runtimeFactKind="cpuPlatformApis",
        ),
        CandidateDecisionModel(
            decisionId=candidate_id("vector-width", "vector_size(16/32/64)"), category="vector-width",
            candidateValue="vector_size(16/32/64)", status="accepted", referenceIds=("gcc-14.2.0-vector-extensions",),
            rationale="The extension is authoritative, but width alone is migration-sensitive rather than x86-only.",
            runtimeFactKind="vectorWidthMarkers",
        ),
        CandidateDecisionModel(
            decisionId=candidate_id("architecture-alias", "amd64/x64"), category="architecture-alias",
            candidateValue="amd64/x64", status="deferred", referenceIds=(),
            rationale="Common spellings require a fixed normative source and context-sensitive identifier policy before runtime acceptance.",
        ),
        CandidateDecisionModel(
            decisionId=candidate_id("linker-source", "ELF relocation and emulation tables"), category="linker-source",
            candidateValue="ELF relocation and emulation tables", status="rejected", referenceIds=(),
            rationale="They do not add source-level C/C++ facts that compiler or assembler definitions cannot provide in this change.",
        ),
        CandidateDecisionModel(
            decisionId=candidate_id("cpu-platform-api", "clock_gettime"), category="cpu-platform-api",
            candidateValue="clock_gettime", status="rejected", referenceIds=(),
            rationale="Operating-system API migration is explicitly outside this change.",
        ),
    )
    ledger = DecisionLedgerModel(
        schemaVersion="1.0", scope="c-cpp-x86-to-riscv-static-analysis",
        decisions=tuple(sorted(decisions, key=lambda item: item.decisionId)),
    )
    _write(output_root, "audit/candidate-decisions.json", ledger)


def main() -> int:
    parser = argparse.ArgumentParser(description="Regenerate fixed-source x86 knowledge JSON without network or toolchain execution")
    parser.add_argument("--llvm-root", type=Path, required=True)
    parser.add_argument("--gcc-root", type=Path, required=True)
    parser.add_argument("--binutils-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    refresh(args.llvm_root, args.gcc_root, args.binutils_root, args.output_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
