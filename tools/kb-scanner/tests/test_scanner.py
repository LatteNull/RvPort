from __future__ import annotations

import json
import tempfile
import textwrap
import unittest
from pathlib import Path

from kb_scanner.adapters.legacy import create_legacy_application
from kb_scanner.core import ScanRequest


ROOT = Path(__file__).resolve().parents[1]
RULES = ROOT / "rulesets" / "riscv-porting"
FIXTURES = ROOT / "tests" / "fixtures" / "riscv-porting"
GENERATED_ENTRY_FIXTURES = ROOT / "tests" / "fixtures" / "generated-entries"


class ScannerTests(unittest.TestCase):
    def run_scan(self, source: Path, *extra: str, rules: Path = RULES) -> dict:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "out"
            result = create_legacy_application().run(_legacy_request(source, rules, output, extra))
            self.assertEqual(result.exit_code, 0, result.diagnostics)
            return json.loads((output / "scan-result.json").read_text(encoding="utf-8"))

    def run_scan_with_output(self, source: Path, output: Path, *extra: str, rules: Path = RULES) -> dict:
        result = create_legacy_application().run(_legacy_request(source, rules, output, extra))
        self.assertEqual(result.exit_code, 0, result.diagnostics)
        return json.loads((output / "scan-result.json").read_text(encoding="utf-8"))

    def test_each_riscv_porting_rule_has_fixture(self) -> None:
        rules = {
            payload["id"]
            for rule_path in (RULES / "rules").rglob("*.yaml")
            for payload in [self.load_yaml(rule_path)]
        }
        fixtures = {
            json.loads((fixture / "expected.json").read_text(encoding="utf-8"))["ruleId"]
            for fixture in FIXTURES.iterdir()
            if fixture.is_dir()
        }
        self.assertEqual(rules, fixtures)

    def test_generated_clang_x86_entries_are_loaded(self) -> None:
        generated = json.loads(
            (RULES / "generated" / "clang-x86-entries.json").read_text(encoding="utf-8")
        )
        self.assertGreaterEqual(len(generated["headers"]), 100)
        self.assertGreaterEqual(len(generated["intrinsics"]), 7000)
        self.assertGreaterEqual(len(generated["builtins"]), 1500)
        self.assertGreaterEqual(len(generated["compilerFlags"]), 200)
        self.assertIn("avx512bf16intrin.h", generated["headers"])
        self.assertIn("_addcarry_u32", generated["intrinsics"])
        self.assertIn("__builtin_ia32_addps512", generated["builtins"])
        self.assertIn("-mavx2", generated["compilerFlags"])
        self.assertIn("-mno-avx2", generated["compilerFlags"])
        self.assertIn("-msse2", generated["compilerFlags"])

    def test_generated_gcc_x86_entries_are_loaded(self) -> None:
        generated = json.loads(
            (RULES / "generated" / "gcc-x86-entries.json").read_text(encoding="utf-8")
        )
        self.assertGreaterEqual(len(generated["headers"]), 100)
        self.assertGreaterEqual(len(generated["intrinsics"]), 7000)
        self.assertGreaterEqual(len(generated["builtins"]), 3000)
        self.assertGreaterEqual(len(generated["compilerFlags"]), 200)
        self.assertIn("avx512fp16intrin.h", generated["headers"])
        self.assertIn("_addcarry_u32", generated["intrinsics"])
        self.assertIn("-mavx512fp16", generated["compilerFlags"])

    def test_generated_clang_compile_flag_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "src"
            source.mkdir()
            (source / "CMakeLists.txt").write_text("add_compile_options(-mapxf)\n", encoding="utf-8")

            payload = self.run_scan(source)

        flag_findings = [f for f in payload["findings"] if f["rule_id"] == "C_CPP.X86.COMPILER_FLAG"]
        self.assertEqual({f["symbol"] for f in flag_findings}, {"-mapxf"})
        self.assertEqual(flag_findings[0]["title_en"], "Uses x86-specific compiler flags")
        self.assertIn("x86-specific compiler flags", flag_findings[0]["reason_en"])
        self.assertIn("RISC-V builds", flag_findings[0]["suggestion_en"])

    def test_commented_build_flags_are_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "src"
            source.mkdir()
            (source / "Makefile").write_text(
                "#CFLAGS=-mavx -march=core-avx2\nCFLAGS=-O3 -Wall\n",
                encoding="utf-8",
            )

            payload = self.run_scan(source)

        flag_findings = [f for f in payload["findings"] if f["rule_id"] == "C_CPP.X86.COMPILER_FLAG"]
        self.assertEqual(flag_findings, [])

    def test_rpm_spec_arch_constraints_and_metadata_are_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "src"
            source.mkdir()
            (source / "package.spec").write_text(
                textwrap.dedent(
                    """
                    Name: demo
                    Version: 1.0
                    Release: 1
                    Summary: demo

                    ExclusiveArch: x86_64 %{ix86}

                    %description
                    Demo package.
                    """
                ).strip(),
                encoding="utf-8",
            )

            payload = self.run_scan(source)

        findings = [f for f in payload["findings"] if f["rule_id"] == "RPM_SPEC.ARCH.CONSTRAINT"]
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["source_kind"], "rpm_spec")
        self.assertEqual(findings[0]["trace"]["metadata"]["rpmTag"], "ExclusiveArch")
        self.assertEqual(findings[0]["trace"]["metadata"]["archTokens"], ["x86_64", "%{ix86}"])

    def test_rpm_spec_build_and_check_sections_are_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "src"
            source.mkdir()
            (source / "package.spec").write_text(
                textwrap.dedent(
                    """
                    Name: demo
                    Version: 1.0
                    Release: 1
                    Summary: demo

                    %build
                    make CFLAGS="-O2 -mavx2"

                    %check
                    ./tests/run --skip-riscv
                    """
                ).strip(),
                encoding="utf-8",
            )

            payload = self.run_scan(source)

        findings = [f for f in payload["findings"] if f["rule_id"] == "RPM_SPEC.X86.BUILD_OR_CHECK"]
        self.assertEqual({f["symbol"] for f in findings}, {"-mavx2", "skip-riscv"})
        self.assertEqual({f["trace"]["metadata"]["section"] for f in findings}, {"build", "check"})

    def test_rpm_spec_comments_changelog_and_plain_dependencies_are_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "src"
            source.mkdir()
            (source / "package.spec").write_text(
                textwrap.dedent(
                    """
                    Name: demo
                    Version: 1.0
                    Release: 1
                    Summary: demo

                    # ExclusiveArch: x86_64
                    BuildRequires: zlib-devel

                    %changelog
                    * Thu Aug 27 2026 Example <example@example.com> - 1.0-1
                    - Mention -mavx2 and ExcludeArch: riscv64 in old notes.
                    """
                ).strip(),
                encoding="utf-8",
            )

            payload = self.run_scan(source)

        self.assertEqual(payload["findings"], [])

    def test_rpm_spec_exclude_path_and_missing_rpmspec_do_not_block_scan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "src"
            (source / "packaging").mkdir(parents=True)
            (source / "packaging" / "package.spec").write_text("ExclusiveArch: x86_64\n", encoding="utf-8")

            payload = self.run_scan(source, "--exclude-path", "packaging")

        self.assertEqual(payload["findings"], [])

    def test_rpm_spec_uses_existing_output_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "src"
            output = Path(tmp) / "out"
            source.mkdir()
            (source / "package.spec").write_text("ExclusiveArch: x86_64\n", encoding="utf-8")

            payload = self.run_scan_with_output(source, output)

            self.assertTrue((output / "scan-result.json").exists())
            self.assertTrue((output / "scan-report.html").exists())
            self.assertTrue((output / "scan.log").exists())
            self.assertFalse((output / "rpm-spec-result.json").exists())
            self.assertEqual(payload["schemaVersion"], "1.0")
            self.assertIn("findings", payload)

    def test_compiler_flag_matching_avoids_generic_arch_duplicates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "src"
            source.mkdir()
            (source / "Makefile").write_text(
                "X86_FLAGS=-march=x86-64\nARM_FLAGS=-march=armv8-a+sve\nTUNE=-mtune=generic\n",
                encoding="utf-8",
            )

            payload = self.run_scan(source)

        flag_findings = [f for f in payload["findings"] if f["rule_id"] == "C_CPP.X86.COMPILER_FLAG"]
        self.assertEqual([f["symbol"] for f in flag_findings], ["-march=x86-64"])

    def test_exclude_keeps_existing_comma_separated_path_part_semantics(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "src"
            (source / "third_party" / "simd").mkdir(parents=True)
            (source / "app" / "simd").mkdir(parents=True)
            (source / "third_party" / "simd" / "bad.cpp").write_text("#include <immintrin.h>\n", encoding="utf-8")
            (source / "app" / "simd" / "bad.cpp").write_text("#include <immintrin.h>\n", encoding="utf-8")
            (source / "app" / "portable.cpp").write_text("int main() { return 0; }\n", encoding="utf-8")

            payload = self.run_scan(source, "--exclude", ".git,build,simd")

        self.assertEqual(payload["findings"], [])

    def test_exclude_path_can_be_repeated_and_matches_exact_project_subtree(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "src"
            (source / "third_party" / "simd").mkdir(parents=True)
            (source / "vendor" / "x86").mkdir(parents=True)
            (source / "app" / "simd").mkdir(parents=True)
            (source / "third_party" / "simd" / "bad.cpp").write_text("#include <immintrin.h>\n", encoding="utf-8")
            (source / "vendor" / "x86" / "bad.cpp").write_text("#include <immintrin.h>\n", encoding="utf-8")
            (source / "app" / "simd" / "bad.cpp").write_text("#include <immintrin.h>\n", encoding="utf-8")

            payload = self.run_scan(
                source,
                "--exclude-path",
                "third_party/simd",
                "--exclude-path",
                "vendor/x86",
            )

        header_findings = [f for f in payload["findings"] if f["rule_id"] == "C_CPP.X86.HEADER"]
        self.assertEqual(len(header_findings), 1)
        self.assertTrue(header_findings[0]["file"].endswith("app/simd/bad.cpp") or header_findings[0]["file"].endswith("app\\simd\\bad.cpp"))

    def test_platform_macro_comments_and_endif_notes_are_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "src"
            source.mkdir()
            (source / "main.cpp").write_text(
                textwrap.dedent(
                    """
                    // #if defined(__AVX__)
                    #endif // __AVX__
                    int use_avx2_path = __AVX2__;
                    """
                ).strip(),
                encoding="utf-8",
            )

            payload = self.run_scan(source)

        macro_findings = [f for f in payload["findings"] if f["rule_id"] == "C_CPP.X86.PLATFORM_MACRO"]
        self.assertEqual([f["symbol"] for f in macro_findings], ["__AVX2__"])

    def test_x86_comment_arch_hints_are_reported_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "src"
            source.mkdir()
            (source / "simdinfo.h").write_text(
                textwrap.dedent(
                    """
                    typedef struct simdinfo_t {
                      // x86 and x86_64
                      unsigned _supports__AVX__;
                      // arm and aarch64
                      unsigned _supports__ARM_NEON;
                    } simdinfo_t;
                    """
                ).strip(),
                encoding="utf-8",
            )

            payload = self.run_scan(source)

        hints = [f for f in payload["findings"] if f["finding_type"] == "hint"]
        self.assertEqual([f["rule_id"] for f in hints], ["COMMENT.ARCH.HINT"])
        self.assertEqual([f["source_kind"] for f in hints], ["comment"])
        self.assertEqual([f["is_actionable"] for f in hints], [False])
        self.assertEqual([f["symbol"] for f in hints], ["x86"])
        self.assertEqual([f["title_en"] for f in hints], ["Architecture hint in comment"])
        self.assertIn("architecture, ISA, or SIMD feature hint", hints[0]["reason_en"])
        self.assertIn("source-code findings", hints[0]["suggestion_en"])
        self.assertEqual(payload["summary"]["hints"], 1)

    def test_comment_arch_hints_can_be_disabled(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "src"
            source.mkdir()
            (source / "simdinfo.h").write_text("// x86 and x86_64\n", encoding="utf-8")

            payload = self.run_scan(source, "--no-comment-hints")

        self.assertEqual(payload["findings"], [])
        self.assertEqual(payload["summary"]["hints"], 0)

    def test_single_file_input_reports_unsafe_entry_and_ignores_portable_version(self) -> None:
        unsafe_payload = self.run_scan(GENERATED_ENTRY_FIXTURES / "single-file" / "cpp" / "before-x86-only.cpp")
        safe_payload = self.run_scan(GENERATED_ENTRY_FIXTURES / "single-file" / "cpp" / "after-portable.cpp")

        header_findings = [f for f in unsafe_payload["findings"] if f["rule_id"] == "C_CPP.X86.HEADER"]
        self.assertEqual({f["symbol"] for f in header_findings}, {"adxintrin.h"})
        self.assertEqual(safe_payload["summary"]["findings"], 0, safe_payload["findings"])

    def test_c_single_file_input_reports_unsafe_entry_and_ignores_portable_version(self) -> None:
        unsafe_payload = self.run_scan(GENERATED_ENTRY_FIXTURES / "single-file" / "c" / "before-x86-only.c")
        safe_payload = self.run_scan(GENERATED_ENTRY_FIXTURES / "single-file" / "c" / "after-portable.c")

        header_findings = [f for f in unsafe_payload["findings"] if f["rule_id"] == "C_CPP.X86.HEADER"]
        self.assertEqual({f["symbol"] for f in header_findings}, {"adxintrin.h"})
        self.assertEqual(safe_payload["summary"]["findings"], 0, safe_payload["findings"])

    def test_generated_entry_matrix_reports_unsafe_folder_and_ignores_portable_folder(self) -> None:
        unsafe_payload = self.run_scan(GENERATED_ENTRY_FIXTURES / "folder-matrix" / "cpp" / "before-x86-only")
        safe_payload = self.run_scan(GENERATED_ENTRY_FIXTURES / "folder-matrix" / "cpp" / "after-portable")

        findings_by_rule = {
            rule_id: {finding["symbol"] for finding in unsafe_payload["findings"] if finding["rule_id"] == rule_id}
            for rule_id in {
                "C_CPP.X86.HEADER",
                "C_CPP.X86.INTRINSIC_CALL",
                "C_CPP.X86.BUILTIN_CALL",
                "C_CPP.X86.VECTOR_TYPE",
                "C_CPP.X86.PLATFORM_MACRO",
                "C_CPP.X86.COMPILER_FLAG",
            }
        }
        self.assertEqual(findings_by_rule["C_CPP.X86.HEADER"], {"amxavx512intrin.h"})
        self.assertEqual(findings_by_rule["C_CPP.X86.INTRINSIC_CALL"], {"_InterlockedExchange_HLEAcquire"})
        self.assertEqual(findings_by_rule["C_CPP.X86.BUILTIN_CALL"], {"__builtin_ia32_aadd32"})
        self.assertEqual(findings_by_rule["C_CPP.X86.VECTOR_TYPE"], {"__m512"})
        self.assertEqual(findings_by_rule["C_CPP.X86.PLATFORM_MACRO"], set())
        self.assertEqual(findings_by_rule["C_CPP.X86.COMPILER_FLAG"], {"-mapxf"})
        self.assertEqual(unsafe_payload["summary"]["files"], 6)
        self.assertEqual(safe_payload["summary"]["findings"], 0, safe_payload["findings"])
        self.assertEqual(safe_payload["summary"]["files"], 6)

    def test_c_generated_entry_matrix_reports_unsafe_folder_and_ignores_portable_folder(self) -> None:
        unsafe_payload = self.run_scan(GENERATED_ENTRY_FIXTURES / "folder-matrix" / "c" / "before-x86-only")
        safe_payload = self.run_scan(GENERATED_ENTRY_FIXTURES / "folder-matrix" / "c" / "after-portable")

        findings_by_rule = {
            rule_id: {finding["symbol"] for finding in unsafe_payload["findings"] if finding["rule_id"] == rule_id}
            for rule_id in {
                "C_CPP.X86.HEADER",
                "C_CPP.X86.INTRINSIC_CALL",
                "C_CPP.X86.BUILTIN_CALL",
                "C_CPP.X86.VECTOR_TYPE",
                "C_CPP.X86.PLATFORM_MACRO",
                "C_CPP.X86.COMPILER_FLAG",
            }
        }
        self.assertEqual(findings_by_rule["C_CPP.X86.HEADER"], {"amxavx512intrin.h"})
        self.assertEqual(findings_by_rule["C_CPP.X86.INTRINSIC_CALL"], {"_InterlockedExchange_HLEAcquire"})
        self.assertEqual(findings_by_rule["C_CPP.X86.BUILTIN_CALL"], {"__builtin_ia32_aadd32"})
        self.assertEqual(findings_by_rule["C_CPP.X86.VECTOR_TYPE"], {"__m512"})
        self.assertEqual(findings_by_rule["C_CPP.X86.PLATFORM_MACRO"], set())
        self.assertEqual(findings_by_rule["C_CPP.X86.COMPILER_FLAG"], {"-mapxf"})
        self.assertEqual(unsafe_payload["summary"]["files"], 6)
        self.assertEqual(safe_payload["summary"]["findings"], 0, safe_payload["findings"])
        self.assertEqual(safe_payload["summary"]["files"], 6)

    def test_language_specific_rules_are_filtered_by_source_suffix(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "src"
            source.mkdir()
            (source / "not_c.cpp").write_text(
                "#define add_vector(a, b) _Generic((a), __m128: _mm_add_ps)(a, b)\n",
                encoding="utf-8",
            )
            (source / "not_cpp.c").write_text(
                textwrap.dedent(
                    """
                    enum Backend { avx2 };
                    #define SUM(B) if constexpr (B == avx2) { return avx2_sum(data); }
                    """
                ).strip(),
                encoding="utf-8",
            )

            payload = self.run_scan(source)

        rule_ids = {finding["rule_id"] for finding in payload["findings"]}
        self.assertNotIn("C.X86.GENERIC_DISPATCH", rule_ids)
        self.assertNotIn("CPP.X86.CONSTEXPR_ARCH_BRANCH", rule_ids)

    def test_riscv_porting_rule_fixtures(self) -> None:
        for fixture in sorted(FIXTURES.iterdir()):
            if not fixture.is_dir():
                continue
            with self.subTest(fixture=fixture.name):
                expected = json.loads((fixture / "expected.json").read_text(encoding="utf-8"))
                payload = self.run_scan(fixture / "src")
                findings = [f for f in payload["findings"] if f["rule_id"] == expected["ruleId"]]
                self.assertEqual(len(findings), expected.get("count", 1), payload["findings"])
                if "symbols" in expected:
                    self.assertEqual({f["symbol"] for f in findings}, set(expected["symbols"]))
                if "conditionMacros" in expected:
                    macros = sorted({macro for f in findings for macro in f["condition_macros"]})
                    self.assertEqual(macros, sorted(expected["conditionMacros"]))

    @staticmethod
    def load_yaml(path: Path) -> dict:
        import yaml

        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise AssertionError(f"{path} is not a YAML object")
        return payload

    def test_custom_macro_guarding_x86_header_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "src"
            source.mkdir()
            (source / "main.cpp").write_text(
                textwrap.dedent(
                    """
                    #ifdef USE_FAST_PATH
                    #include <immintrin.h>
                    #endif
                    int main() { return 0; }
                    """
                ).strip(),
                encoding="utf-8",
            )

            payload = self.run_scan(source)

        self.assertEqual(payload["project"]["scanMode"], "source_context")
        header_findings = [f for f in payload["findings"] if f["rule_id"] == "C_CPP.X86.HEADER"]
        self.assertEqual(len(header_findings), 1)
        self.assertEqual(header_findings[0]["condition_macros"], ["USE_FAST_PATH"])
        self.assertIn("自定义宏 USE_FAST_PATH", header_findings[0]["reason"])

    def test_macro_expansion_to_intrinsic_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "src"
            source.mkdir()
            (source / "simd.cpp").write_text(
                textwrap.dedent(
                    """
                    #define VEC_ADD(a, b) _mm256_add_ps(a, b)
                    void f() {
                      VEC_ADD(x, y);
                    }
                    """
                ).strip(),
                encoding="utf-8",
            )

            payload = self.run_scan(source)

        macro_findings = [f for f in payload["findings"] if f["rule_id"] == "C_CPP.X86.MACRO_EXPANDS_TO_INTRINSIC"]
        self.assertEqual(len(macro_findings), 1)
        self.assertEqual(macro_findings[0]["trace"]["macro"], "VEC_ADD")

    def test_macro_definition_is_reference_source_but_macro_use_is_reference(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "src"
            output = Path(tmp) / "out"
            source.mkdir()
            (source / "aes.c").write_text(
                textwrap.dedent(
                    """
                    #define AES_IMC(rkey) _mm_aesimc_si128(rkey)
                    void f() {
                      AES_IMC(round_key);
                    }
                    """
                ).strip(),
                encoding="utf-8",
            )

            payload = self.run_scan_with_output(source, output)
            html_report = (output / "scan-report.html").read_text(encoding="utf-8")

        intrinsic_findings = [f for f in payload["findings"] if f["rule_id"] == "C_CPP.X86.INTRINSIC_CALL"]
        self.assertEqual(len(intrinsic_findings), 2, payload["findings"])
        source_findings = [f for f in intrinsic_findings if f["is_reference_source"]]
        reference_findings = [f for f in intrinsic_findings if not f["is_reference_source"]]
        self.assertEqual(len(source_findings), 1)
        self.assertEqual(source_findings[0]["location"]["line"], 1)
        self.assertEqual(len(reference_findings), 1)
        self.assertEqual(reference_findings[0]["trace"]["macro"], "AES_IMC")
        self.assertGreaterEqual(payload["summary"]["referenceSources"], 1)
        self.assertIn("<th>引用源头</th>", html_report)

    def test_severity_policy_uses_context_and_reference_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "src"
            source.mkdir()
            (source / "severity.cpp").write_text(
                textwrap.dedent(
                    """
                    // x86 runtime note
                    #include <immintrin.h>
                    #define AES_IMC(rkey) _mm_aesimc_si128(rkey)
                    void f() {
                      _mm256_add_ps(a, b);
                      AES_IMC(round_key);
                    }
                    #ifdef USE_AVX2
                    void guarded() {
                      _mm256_mul_ps(a, b);
                    }
                    #endif
                    """
                ).strip(),
                encoding="utf-8",
            )

            payload = self.run_scan(source)

        by_line = {
            (f["rule_id"], f["location"]["line"], f["is_reference_source"]): f
            for f in payload["findings"]
        }
        self.assertEqual(by_line[("C_CPP.X86.HEADER", 2, True)]["severity"], "critical")
        self.assertEqual(by_line[("C_CPP.X86.INTRINSIC_CALL", 5, True)]["severity"], "critical")
        self.assertEqual(by_line[("C_CPP.X86.INTRINSIC_CALL", 10, True)]["severity"], "high")
        self.assertEqual(by_line[("C_CPP.X86.INTRINSIC_CALL", 6, False)]["severity"], "medium")
        hint = next(f for f in payload["findings"] if f["finding_type"] == "hint")
        self.assertEqual(hint["severity"], "info")

    def test_compile_commands_supplement_records_include_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "src"
            source.mkdir()
            cpp = source / "main.cpp"
            cpp.write_text("#include <immintrin.h>\n", encoding="utf-8")
            compile_commands = source / "compile_commands.json"
            compile_commands.write_text(
                json.dumps(
                    [
                        {
                            "directory": str(source),
                            "file": str(cpp),
                            "command": "clang++ -Igenerated -Iinclude -DUSE_AVX2 -std=c++17 main.cpp",
                        }
                    ]
                ),
                encoding="utf-8",
            )

            payload = self.run_scan(source)

        self.assertEqual(payload["project"]["scanMode"], "source_context_with_compile_database")
        context = next(iter(payload["project"]["compileContexts"].values()))
        self.assertEqual(context["includeDirs"], ["generated", "include"])
        self.assertIn("USE_AVX2", context["defines"])
        self.assertEqual(context["languageStandard"], "c++17")

    def test_compile_commands_generates_finding_for_x86_flag_without_source_text(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "src"
            source.mkdir()
            cpp = source / "main.cpp"
            cpp.write_text("int main() { return 0; }\n", encoding="utf-8")
            (source / "compile_commands.json").write_text(
                json.dumps(
                    [
                        {
                            "directory": str(source),
                            "file": str(cpp),
                            "arguments": ["clang++", "-O2", "-mavx2", "-c", "main.cpp"],
                        }
                    ]
                ),
                encoding="utf-8",
            )

            payload = self.run_scan(source)

        flag_findings = [f for f in payload["findings"] if f["rule_id"] == "C_CPP.X86.COMPILER_FLAG"]
        self.assertEqual(len(flag_findings), 1, payload["findings"])
        self.assertEqual(flag_findings[0]["source_kind"], "compile_command")
        self.assertEqual(flag_findings[0]["symbol"], "-mavx2")
        self.assertEqual(flag_findings[0]["trace"]["compileCommand"]["token"], "-mavx2")
        self.assertEqual(flag_findings[0]["trace"]["compileCommand"]["tokenKind"], "compiler_flag")
        self.assertEqual(flag_findings[0]["trace"]["compileCommand"]["sourceFile"], "main.cpp")

    def test_compile_commands_supports_arguments_and_command_string_for_findings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "src"
            source.mkdir()
            first = source / "first.cpp"
            second = source / "second.cpp"
            first.write_text("int first() { return 0; }\n", encoding="utf-8")
            second.write_text("int second() { return 0; }\n", encoding="utf-8")
            (source / "compile_commands.json").write_text(
                json.dumps(
                    [
                        {
                            "directory": str(source),
                            "file": str(first),
                            "arguments": ["clang++", "-msse2", "-c", "first.cpp"],
                        },
                        {
                            "directory": str(source),
                            "file": str(second),
                            "command": "clang++ -march=x86-64 -D__AVX__ -c second.cpp",
                        },
                    ]
                ),
                encoding="utf-8",
            )

            payload = self.run_scan(source)

        flag_symbols = {
            f["symbol"]
            for f in payload["findings"]
            if f["rule_id"] == "C_CPP.X86.COMPILER_FLAG" and f["source_kind"] == "compile_command"
        }
        macro_symbols = {
            f["symbol"]
            for f in payload["findings"]
            if f["rule_id"] == "C_CPP.X86.PLATFORM_MACRO" and f["source_kind"] == "compile_command"
        }
        self.assertEqual(flag_symbols, {"-msse2", "-march=x86-64"})
        self.assertEqual(macro_symbols, {"__AVX__"})

    def test_compile_commands_invalid_and_out_of_scope_entries_do_not_fail_scan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "src"
            source.mkdir()
            cpp = source / "main.cpp"
            cpp.write_text("int main() { return 0; }\n", encoding="utf-8")
            build_file = source / "build" / "CMakeFiles" / "probe.c"
            build_file.parent.mkdir(parents=True)
            build_file.write_text("int probe(void) { return 0; }\n", encoding="utf-8")
            (source / "compile_commands.json").write_text(
                json.dumps(
                    [
                        {"directory": str(source), "command": "clang -mavx2 -c missing-file.c"},
                        {"directory": str(source), "file": str(build_file), "command": "clang -mavx2 -c probe.c"},
                        {"directory": str(source), "file": str(cpp), "command": '"unterminated -mavx2'},
                    ]
                ),
                encoding="utf-8",
            )

            payload = self.run_scan(source)

        self.assertEqual(
            [f for f in payload["findings"] if f["source_kind"] == "compile_command"],
            [],
        )
        self.assertTrue(any("跳过无 file 字段" in item for item in payload["diagnostics"]))
        self.assertTrue(any("无法解析命令行" in item for item in payload["diagnostics"]))

    def test_compile_commands_merges_duplicate_build_flag_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "src"
            source.mkdir()
            cpp = source / "main.cpp"
            cpp.write_text("int main() { return 0; }\n", encoding="utf-8")
            (source / "Makefile").write_text("CFLAGS += -mavx2\n", encoding="utf-8")
            (source / "compile_commands.json").write_text(
                json.dumps(
                    [
                        {
                            "directory": str(source),
                            "file": str(cpp),
                            "arguments": ["clang++", "-mavx2", "-c", "main.cpp"],
                        }
                    ]
                ),
                encoding="utf-8",
            )

            payload = self.run_scan(source)

        flag_findings = [f for f in payload["findings"] if f["rule_id"] == "C_CPP.X86.COMPILER_FLAG"]
        self.assertEqual(len(flag_findings), 1, payload["findings"])
        self.assertNotEqual(flag_findings[0]["source_kind"], "compile_command")
        evidence = flag_findings[0]["trace"]["compileCommandEvidence"]
        self.assertEqual(len(evidence), 1)
        self.assertEqual(evidence[0]["token"], "-mavx2")
        self.assertEqual(evidence[0]["sourceFile"], "main.cpp")

    def test_known_x86_api_call_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "src"
            source.mkdir()
            (source / "cpu.cpp").write_text(
                textwrap.dedent(
                    """
                    void cpu_feature_probe() {
                      int out[4];
                      __cpuid(out, 0);
                      auto ticks = __rdtsc();
                    }
                    """
                ).strip(),
                encoding="utf-8",
            )

            payload = self.run_scan(source)

        api_findings = [f for f in payload["findings"] if f["rule_id"] == "C_CPP.X86.API_CALL"]
        self.assertEqual({f["symbol"] for f in api_findings}, {"__cpuid", "__rdtsc"})

    def test_x86_only_branch_is_hidden_for_riscv_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "src"
            source.mkdir()
            (source / "simd.c").write_text(
                textwrap.dedent(
                    """
                    #if defined(__x86_64__)
                    #include <immintrin.h>
                    int add() { return _mm256_movemask_ps(v); }
                    #endif
                    """
                ).strip(),
                encoding="utf-8",
            )

            payload = self.run_scan(source)

        self.assertEqual(payload["summary"]["findings"], 0, payload["findings"])

    def test_x86_only_branch_can_be_audited_when_requested(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "src"
            source.mkdir()
            (source / "simd.c").write_text(
                textwrap.dedent(
                    """
                    #if defined(__x86_64__)
                    #include <immintrin.h>
                    int add() { return _mm256_movemask_ps(v); }
                    #endif
                    """
                ).strip(),
                encoding="utf-8",
            )

            payload = self.run_scan(source, "--include-inactive-branches")

        self.assertGreater(payload["summary"]["findings"], 0)
        self.assertTrue(any(f["symbol"] == "immintrin.h" for f in payload["findings"]))

    def test_macro_branch_with_riscv_sibling_is_hidden_by_default_and_auditable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "src"
            source.mkdir()
            (source / "simd.c").write_text(
                textwrap.dedent(
                    """
                    #if defined(__AVX2__)
                    #include <immintrin.h>
                    int add() { return _mm256_movemask_ps(v); }
                    #elif defined(__riscv) && defined(__riscv_vector)
                    int add() { return rvv_add(); }
                    #else
                    int add() { return scalar_add(); }
                    #endif
                    """
                ).strip(),
                encoding="utf-8",
            )

            default_payload = self.run_scan(source)
            audit_payload = self.run_scan(source, "--include-inactive-branches")

        self.assertEqual(default_payload["summary"]["findings"], 0, default_payload["findings"])
        guarded = [f for f in audit_payload["findings"] if f["finding_type"] == "guarded"]
        self.assertGreaterEqual(len(guarded), 1, audit_payload["findings"])
        self.assertTrue(all(not f["is_blocking"] for f in guarded))
        self.assertTrue(all(f["compatible_sibling_branch"] for f in guarded))
        self.assertEqual({f["compatible_branch_kind"] for f in guarded}, {"riscv"})
        self.assertEqual({f["arch_reachability"] for f in guarded}, {"inactive_on_riscv"})

    def test_macro_branch_with_generic_fallback_is_hidden_by_default_and_auditable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "src"
            source.mkdir()
            (source / "simd.c").write_text(
                textwrap.dedent(
                    """
                    #ifdef USE_AVX2
                    #include <immintrin.h>
                    int add() { return _mm256_movemask_ps(v); }
                    #else
                    int add() { return scalar_add(); }
                    #endif
                    """
                ).strip(),
                encoding="utf-8",
            )

            default_payload = self.run_scan(source)
            audit_payload = self.run_scan(source, "--include-inactive-branches")

        self.assertEqual(default_payload["summary"]["findings"], 0, default_payload["findings"])
        guarded = [f for f in audit_payload["findings"] if f["finding_type"] == "guarded"]
        self.assertGreaterEqual(len(guarded), 1, audit_payload["findings"])
        self.assertEqual({f["compatible_branch_kind"] for f in guarded}, {"fallback"})

    def test_x86_macro_branch_without_riscv_or_generic_sibling_is_portability_gap(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "src"
            source.mkdir()
            (source / "simd.c").write_text(
                textwrap.dedent(
                    """
                    #ifdef USE_AVX2
                    #include <immintrin.h>
                    int add() { return _mm256_movemask_ps(v); }
                    #endif
                    """
                ).strip(),
                encoding="utf-8",
            )

            payload = self.run_scan(source)

        gaps = [f for f in payload["findings"] if f["finding_type"] == "portability_gap"]
        self.assertGreaterEqual(len(gaps), 1, payload["findings"])
        self.assertTrue(all(f["is_blocking"] for f in gaps))
        self.assertEqual(payload["summary"]["portabilityGaps"], len(gaps))

    def test_x86_directory_with_riscv_sibling_impl_is_hidden_by_default_and_auditable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "src"
            (source / "x86").mkdir(parents=True)
            (source / "riscv").mkdir(parents=True)
            (source / "x86" / "simd.c").write_text(
                "#include <immintrin.h>\nint add() { return _mm256_movemask_ps(v); }\n",
                encoding="utf-8",
            )
            (source / "riscv" / "simd.c").write_text("int add() { return rvv_add(); }\n", encoding="utf-8")

            default_payload = self.run_scan(source)
            audit_payload = self.run_scan(source, "--include-inactive-branches")

        self.assertEqual(default_payload["summary"]["findings"], 0, default_payload["findings"])
        inactive = [f for f in audit_payload["findings"] if f["finding_type"] == "inactive"]
        self.assertGreaterEqual(len(inactive), 1, audit_payload["findings"])
        self.assertTrue(all(f["alternative_impl"]["has_riscv_alternative"] for f in inactive))
        self.assertTrue(all(not f["is_blocking"] for f in inactive))

    def test_compile_commands_does_not_hide_unlisted_x86_file_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "src"
            source.mkdir()
            x86_file = source / "simd.c"
            riscv_file = source / "portable.c"
            x86_file.write_text("#include <immintrin.h>\n", encoding="utf-8")
            riscv_file.write_text("int add() { return rvv_add(); }\n", encoding="utf-8")
            (source / "compile_commands.json").write_text(
                json.dumps([{"directory": str(source), "file": str(riscv_file), "command": "clang -c portable.c"}]),
                encoding="utf-8",
            )

            default_payload = self.run_scan(source)
            audit_payload = self.run_scan(source, "--include-inactive-branches")

        self.assertGreaterEqual(default_payload["summary"]["findings"], 1, default_payload["findings"])
        x86_findings = [f for f in default_payload["findings"] if f["file"].endswith("simd.c")]
        self.assertGreaterEqual(len(x86_findings), 1, default_payload["findings"])
        self.assertEqual({f["build_context"]["included_in_riscv_build"] for f in x86_findings}, {"unknown"})
        audit_x86_findings = [f for f in audit_payload["findings"] if f["file"].endswith("simd.c")]
        self.assertGreaterEqual(len(audit_x86_findings), 1, audit_payload["findings"])

    def test_compile_commands_marks_included_header_reachable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "src"
            source.mkdir()
            main_file = source / "main.c"
            header_file = source / "simd.h"
            main_file.write_text('#include "simd.h"\nint main(void) { return 0; }\n', encoding="utf-8")
            header_file.write_text(
                "#include <immintrin.h>\n",
                encoding="utf-8",
            )
            (source / "compile_commands.json").write_text(
                json.dumps([{"directory": str(source), "file": str(main_file), "command": "clang -I. -c main.c"}]),
                encoding="utf-8",
            )

            payload = self.run_scan(source)

        header_findings = [f for f in payload["findings"] if f["file"].endswith("simd.h")]
        self.assertGreaterEqual(len(header_findings), 1, payload["findings"])
        self.assertEqual({f["build_context"]["included_in_riscv_build"] for f in header_findings}, {"true"})

    def test_new_yaml_rule_can_be_added_without_core_change(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "src"
            source.mkdir()
            (source / "platform.cpp").write_text("int custom_platform_flag = 1;\n", encoding="utf-8")
            rules = Path(tmp) / "rules"
            (rules / "rules" / "c_cpp").mkdir(parents=True)
            (rules / "manifest.yaml").write_text("id: custom\nversion: 1\n", encoding="utf-8")
            (rules / "rules" / "c_cpp" / "custom.yaml").write_text(
                textwrap.dedent(
                    r"""
                    id: CUSTOM.PLATFORM.MACRO
                    language: cpp
                    severity: medium
                    confidence: medium
                    match:
                      any:
                        - text:
                            regex: "custom_platform_flag"
                    message:
                      zh-CN:
                        title: "自定义平台宏"
                        reason: "发现平台相关宏。"
                        suggestion: "确认 RISC-V 分支。"
                    """
                ).strip(),
                encoding="utf-8",
            )
            output = Path(tmp) / "out"
            result = create_legacy_application().run(ScanRequest(str(source), str(rules), str(output), formats=("json",)))
            self.assertEqual(result.exit_code, 0, result.diagnostics)
            payload = json.loads((output / "scan-result.json").read_text(encoding="utf-8"))

        self.assertEqual(payload["findings"][0]["rule_id"], "CUSTOM.PLATFORM.MACRO")


def _legacy_request(source: Path, rules: Path, output: Path, extra: tuple[str, ...]) -> ScanRequest:
    excludes = (".git", "build")
    exclude_paths: list[str] = []
    include_inactive = False
    include_comments = True
    index = 0
    while index < len(extra):
        option = extra[index]
        if option == "--exclude":
            index += 1
            excludes = tuple(item.strip() for item in extra[index].split(",") if item.strip())
        elif option == "--exclude-path":
            index += 1
            exclude_paths.append(extra[index])
        elif option == "--include-inactive-branches":
            include_inactive = True
        elif option == "--no-comment-hints":
            include_comments = False
        index += 1
    return ScanRequest(
        str(source), str(rules), str(output), excludes=excludes, exclude_paths=tuple(exclude_paths),
        include_inactive_branches=include_inactive, include_comment_hints=include_comments,
    )


if __name__ == "__main__":
    unittest.main()

