from __future__ import annotations

import unittest
from dataclasses import FrozenInstanceError

from kb_scanner.knowledge.identity import curated_entry_id
from kb_scanner.knowledge.production import CandidateDecision, lint_curated, lint_generated, render_model, runtime_decisions
from kb_scanner.knowledge.schema import (
    CuratedEntryModel, CuratedFactsModel, GeneratedFactV2Model, GeneratedFactsV2Model,
    ReferenceRegistryModel, SourceDescriptorModel, SourceReferenceModel,
)


REVISION = "a" * 40
HASH = "b" * 64


def descriptor() -> SourceDescriptorModel:
    return SourceDescriptorModel(
        sourceId="llvm-x86", officialUrl="https://github.com/llvm/llvm-project", release="llvmorg-18.1.8",
        revision=REVISION, license="Apache-2.0 WITH LLVM-exception", collectedAt="2026-09-07",
        inputPaths=("llvm/lib/Target/X86/X86.td",), inputSha256=(HASH,),
    )


def generated(*values: str) -> GeneratedFactsV2Model:
    facts = tuple(
        GeneratedFactV2Model(
            factKind="targetFeatures", architectureFamily="x86", canonicalValue=value, semanticScope="x86-toolchain",
        )
        for value in values
    )
    return GeneratedFactsV2Model(schemaVersion="2.0", source=descriptor(), facts=facts)


def registry() -> ReferenceRegistryModel:
    return ReferenceRegistryModel(
        schemaVersion="1.0",
        references=(SourceReferenceModel(
            referenceId="gcc-vector-size", officialUrl="https://gcc.gnu.org/onlinedocs/gcc/Vector-Extensions.html",
            release="GCC 14.2.0", revision=REVISION, logicalLocation="Using Vector Instructions",
            license="GFDL-1.3", collectedAt="2026-09-07", sha256=HASH,
        ),),
    )


def curated(*, entry_id: str | None = None, refs: tuple[str, ...] = ("gcc-vector-size",)) -> CuratedFactsModel:
    value = "vector_size(16)"
    return CuratedFactsModel(
        schemaVersion="1.0", sourceId="curated-x86", reviewPolicy="two-source-or-owner-review", reviewPolicyVersion="1.0",
        entries=(CuratedEntryModel(
            entryId=entry_id or curated_entry_id("vectorWidthMarkers", "x86", value), factKind="vectorWidthMarkers",
            architectureFamily="x86", canonicalValue=value, semanticScope="migration-sensitive",
            referenceIds=refs, reviewStatus="accepted",
        ),),
    )


class ProductionTests(unittest.TestCase):
    def test_candidate_decisions_are_frozen_deduplicated_and_runtime_filtered(self) -> None:
        accepted = CandidateDecision("b", "api", "__rdtsc", "accepted", ("r2", "r1", "r2"), "compiler header")
        rejected = CandidateDecision("a", "api", "clock_gettime", "rejected", (), "OS API excluded")
        self.assertEqual(accepted.reference_ids, ("r1", "r2"))
        self.assertEqual(runtime_decisions((rejected, accepted)), (accepted,))
        with self.assertRaises(FrozenInstanceError):
            accepted.status = "rejected"  # type: ignore[misc]

    def test_candidate_decision_rejects_empty_unknown_and_unreferenced_runtime_status(self) -> None:
        with self.assertRaises(ValueError):
            CandidateDecision("", "api", "x", "deferred", (), "why")
        with self.assertRaises(ValueError):
            CandidateDecision("x", "api", "x", "accepted", (), "why")
        with self.assertRaises(ValueError):
            CandidateDecision("x", "api", "x", "unknown", (), "why")  # type: ignore[arg-type]

    def test_renderer_is_deterministic_json_safe_and_newline_terminated(self) -> None:
        first = render_model(generated("avx2"))
        second = render_model(generated("avx2"))
        self.assertEqual(first, second)
        self.assertTrue(first.endswith(b"\n"))
        self.assertIn(b'"schemaVersion": "2.0"', first)

    def test_generated_lint_reports_order_and_canonicalization(self) -> None:
        self.assertEqual(lint_generated(generated("avx", "sse2")), ())
        failures = lint_generated(generated("sse2", "AVX"))
        self.assertIn("facts-not-sorted", failures)
        self.assertTrue(any(item.startswith("non-canonical:") for item in failures))

    def test_curated_lint_checks_identity_references_and_order(self) -> None:
        self.assertEqual(lint_curated(curated(), registry()), ())
        failures = lint_curated(curated(entry_id="wrong", refs=("missing",)), registry())
        self.assertTrue(any(item.startswith("entry-id-mismatch:") for item in failures))
        self.assertTrue(any(item.startswith("missing-references:") for item in failures))


if __name__ == "__main__":
    unittest.main()
