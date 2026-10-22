from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from kb_scanner.knowledge.extractors import ReadOnlySource, extract_binutils, extract_gcc, extract_llvm, with_descriptor
from kb_scanner.knowledge.schema import SourceDescriptorModel


REVISION = "a" * 40
HASH = "b" * 64


def write(root: Path, path: str, content: bytes | str) -> None:
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content if isinstance(content, bytes) else content.encode())


def descriptor() -> SourceDescriptorModel:
    return SourceDescriptorModel(
        sourceId="test", officialUrl="https://example.test/source", release="1", revision=REVISION,
        license="MIT", collectedAt="2026-09-07", inputPaths=("placeholder",), inputSha256=(HASH,),
    )


class ExtractorTests(unittest.TestCase):
    def test_binutils_extracts_deduplicated_sorted_instruction_and_register_facts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, "opcodes/i386-opc.tbl", "# comment\nmov,0,0\nADD,0,0\nmov,0,0\nbad token,0\n")
            write(root, "opcodes/i386-reg.tbl", "xmm0,0,0\nrax,0,0\n;ignored,0\n")
            before = (root / "opcodes/i386-opc.tbl").read_bytes()
            result = extract_binutils(root, "opcodes/i386-opc.tbl", "opcodes/i386-reg.tbl")
            after = (root / "opcodes/i386-opc.tbl").read_bytes()
        self.assertTrue(result.succeeded)
        self.assertEqual(before, after)
        self.assertEqual(
            [(item.factKind, item.canonicalValue) for item in result.facts],
            [("assemblyInstructions", "add"), ("assemblyInstructions", "mov"), ("registerNames", "rax"), ("registerNames", "xmm0")],
        )
        self.assertEqual(len(result.input_sha256), 2)

    def test_llvm_extracts_register_feature_and_cpu_with_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, "X86RegisterInfo.td", 'def AL : X86Reg<"AL", 0>;\ndef XMM0 : X86RegWithSubRegs<"xmm0", 1>;')
            write(root, "X86.td", 'def FeatureSSE2 : SubtargetFeature<"SSE2", "", "", "">;\ndef : Proc<"i386", []>;')
            write(root, "X86Instr.td", 'def PAUSE : I<0x90, RawFrm, (outs), (ins), "pause\\t", []>;')
            result = extract_llvm(root, "X86RegisterInfo.td", "X86.td", ("X86Instr.td",))
        self.assertTrue(result.succeeded)
        values = {(item.factKind, item.canonicalValue) for item in result.facts}
        self.assertTrue({
            ("registerNames", "al"), ("targetFeatures", "sse2"), ("architectureAliases", "i386"),
            ("assemblyInstructions", "pause"),
        } <= values)
        updated = with_descriptor(descriptor(), result)
        self.assertEqual(updated.inputPaths, result.input_paths)

    def test_gcc_extracts_aliases_features_and_deduplicates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, "i386-common.cc", '{"haswell", PROCESSOR_HASWELL, 0},\n{"HASWELL", PROCESSOR_HASWELL, 0},')
            write(root, "i386-isas.h", 'ISA_NAMES_TABLE_ENTRY("AVX2", FEATURE_AVX2)\nISA_NAMES_TABLE_ENTRY("sse2", FEATURE_SSE2)')
            result = extract_gcc(root, "i386-common.cc", "i386-isas.h")
        self.assertTrue(result.succeeded)
        self.assertEqual(len([item for item in result.facts if item.canonicalValue == "haswell"]), 1)
        self.assertIn("avx2", {item.canonicalValue for item in result.facts})

    def test_missing_escape_encoding_and_unsupported_structures_are_sanitized_failures(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, "binary", b"\xff")
            write(root, "empty", "not a table")
            missing = extract_binutils(root, "missing", "also-missing")
            escape = ReadOnlySource(root).read("../secret")
            encoding = ReadOnlySource(root).read("binary")
            unsupported = extract_binutils(root, "empty", "empty")
        self.assertFalse(missing.succeeded)
        self.assertEqual(len(missing.diagnostics), 2)
        self.assertEqual(escape.code, "extractor.path-escape")
        self.assertEqual(encoding.code, "extractor.source-encoding")
        self.assertEqual(unsupported.diagnostics[0].code, "extractor.unsupported-structure")
        self.assertNotIn(str(root), repr(missing.diagnostics))
        with self.assertRaises(ValueError):
            with_descriptor(descriptor(), missing)

    def test_llvm_and_gcc_reject_changed_structure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, "a", "nothing")
            write(root, "b", "nothing")
            llvm = extract_llvm(root, "a", "b")
            gcc = extract_gcc(root, "a", "b")
        self.assertEqual(llvm.diagnostics[0].code, "extractor.unsupported-structure")
        self.assertEqual(gcc.diagnostics[0].code, "extractor.unsupported-structure")

    def test_llvm_rejects_instruction_structure_without_assembly_strings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, "registers", 'def AL : X86Reg<"al", 0>;')
            write(root, "target", 'def F : SubtargetFeature<"sse2", "", "", "">; def : Proc<"i386", []>;')
            write(root, "instructions", "def BROKEN : UnknownClass<0>;")
            result = extract_llvm(root, "registers", "target", ("instructions",))
        self.assertEqual(result.diagnostics[0].code, "extractor.unsupported-structure")


if __name__ == "__main__":
    unittest.main()
