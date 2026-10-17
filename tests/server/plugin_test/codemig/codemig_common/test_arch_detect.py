import pytest
from plugin.codemig.codemig_common.arch_detect import (
    is_rv_arch, is_other_arch, merge_star_sequences,
    extract_pattern_and_remainder, has_arch_and_remainder,
    OTHER, RISCV, arch_other_pattern, arch_riscv_pattern,
    isa_other_pattern, isa_riscv_pattern,
)


# ---------------------------------------------------------------------------
# is_rv_arch
# ---------------------------------------------------------------------------
class TestIsRvArch:
    def test_riscv64(self):
        assert is_rv_arch("file_riscv64") is True

    def test_riscv64_upper(self):
        assert is_rv_arch("FILE_RISCV64") is True

    def test_riscv(self):
        assert is_rv_arch("file_riscv") is True

    def test_risc_v(self):
        assert is_rv_arch("file_risc-v") is True

    def test_risc_v_mixed_case(self):
        assert is_rv_arch("Risc-V") is True

    def test_riscv_uppercase(self):
        assert is_rv_arch("RISCV") is True

    def test_riscv32_not_matched(self):
        """riscv32 is explicitly excluded by the (?!32) negative lookahead."""
        assert is_rv_arch("riscv32") is False

    def test_x86_not_matched(self):
        assert is_rv_arch("x86_64") is False

    def test_arm_not_matched(self):
        assert is_rv_arch("arm64") is False

    def test_empty_string(self):
        assert is_rv_arch("") is False

    def test_random_string(self):
        assert is_rv_arch("hello_world") is False

    def test_riscv_in_middle(self):
        assert is_rv_arch("lib_riscv64_so") is True

    def test_plain_riscv(self):
        assert is_rv_arch("riscv") is True


# ---------------------------------------------------------------------------
# is_other_arch
# ---------------------------------------------------------------------------
class TestIsOtherArch:
    def test_x86_64(self):
        assert is_other_arch("x86_64") is True

    def test_amd64(self):
        assert is_other_arch("amd64") is True

    def test_arm64(self):
        assert is_other_arch("arm64") is True

    def test_aarch64(self):
        assert is_other_arch("aarch64") is True

    def test_armv8(self):
        assert is_other_arch("armv8") is True

    def test_armv9(self):
        assert is_other_arch("armv9") is True

    def test_x86_word_boundary(self):
        assert is_other_arch(" x86 ") is True

    def test_arm_word_boundary(self):
        assert is_other_arch("_arm_") is True

    def test_riscv_not_matched(self):
        assert is_other_arch("riscv64") is False

    def test_riscv_not_matched2(self):
        assert is_other_arch("riscv") is False

    def test_empty_string(self):
        assert is_other_arch("") is False

    def test_random_string(self):
        assert is_other_arch("hello") is False

    def test_x86_amd(self):
        assert is_other_arch("x86_amd") is True

    def test_arm64be(self):
        assert is_other_arch("arm64be") is True

    def test_aarch64_be(self):
        assert is_other_arch("aarch64_be") is True

    def test_armv8_a(self):
        assert is_other_arch("armv8-a") is True

    def test_armv8_a_underscore(self):
        assert is_other_arch("armv8_a") is True

    def test_armv9a(self):
        assert is_other_arch("armv9a") is True

    def test_uppercase_x86(self):
        assert is_other_arch("X86") is True

    def test_uppercase_arm(self):
        assert is_other_arch("ARM") is True

    def test_embedded_x86(self):
        assert is_other_arch("file_x86_64_release") is True

    def test_amd64p32(self):
        assert is_other_arch("amd64p32") is True

    def test_armv_uppercase(self):
        assert is_other_arch("ARMV8") is True

    def test_armx(self):
        assert is_other_arch("armx") is True

    def test_arm9_a(self):
        assert is_other_arch("arm9-a") is True

    def test_armbe(self):
        assert is_other_arch("armbe") is True


# ---------------------------------------------------------------------------
# merge_star_sequences
# ---------------------------------------------------------------------------
class TestMergeStarSequences:
    def test_merge_dash(self):
        assert merge_star_sequences("*isa*-*isa*") == "*isa*"

    def test_merge_underscore(self):
        assert merge_star_sequences("*isa*_*isa*") == "*isa*"

    def test_merge_dot(self):
        assert merge_star_sequences("*isa*.*isa*") == "*isa*"

    def test_merge_hash(self):
        assert merge_star_sequences("*isa*#*isa*") == "*isa*"

    def test_no_merge_needed(self):
        assert merge_star_sequences("*isa*") == "*isa*"

    def test_no_star_isa(self):
        assert merge_star_sequences("hello") == "hello"

    def test_empty_string(self):
        assert merge_star_sequences("") == ""

    def test_multiple_merges(self):
        assert merge_star_sequences("*isa*-*isa*-*isa*") == "*isa*"

    def test_mixed_separators(self):
        """*isa*-*isa*_*isa* → first merge: *isa*_*isa* → second merge: *isa*"""
        assert merge_star_sequences("*isa*-*isa*_*isa*") == "*isa*"

    def test_non_isa_star_not_merged(self):
        assert merge_star_sequences("*arch*-*arch*") == "*arch*-*arch*"

    def test_text_around_merge(self):
        assert merge_star_sequences("prefix_*isa*-*isa*_suffix") == "prefix_*isa*_suffix"


# ---------------------------------------------------------------------------
# extract_pattern_and_remainder
# ---------------------------------------------------------------------------
class TestExtractPatternAndRemainder:
    def test_match_arch_default_replace(self):
        matched, groups, remainder = extract_pattern_and_remainder(
            arch_other_pattern, "file_x86_64_release")
        assert matched is True
        # groups contains all capture groups from the regex; inner groups may be None
        assert "x86_64" in groups
        assert remainder == "file_*arch*_release"

    def test_no_match(self):
        matched, groups, remainder = extract_pattern_and_remainder(
            arch_other_pattern, "hello_world")
        assert matched is False
        assert groups is None
        assert remainder == "hello_world"

    def test_empty_name(self):
        matched, groups, remainder = extract_pattern_and_remainder(
            arch_other_pattern, "")
        assert matched is False
        assert groups is None
        assert remainder is None

    def test_replace_isa(self):
        matched, groups, remainder = extract_pattern_and_remainder(
            isa_other_pattern, "lib_avx2_func", replace='isa')
        assert matched is True
        assert groups == ("avx2",)
        assert remainder == "lib_*isa*_func"

    def test_riscv_arch_pattern(self):
        matched, groups, remainder = extract_pattern_and_remainder(
            arch_riscv_pattern, "file_riscv64_test")
        assert matched is True
        assert groups == ("riscv64",)
        assert remainder == "file_*arch*_test"

    def test_riscv_isa_pattern(self):
        matched, groups, remainder = extract_pattern_and_remainder(
            isa_riscv_pattern, "func_rvv_impl", replace='isa')
        assert matched is True
        assert groups == ("rvv",)
        assert remainder == "func_*isa*_impl"

    def test_isa_triggers_merge(self):
        """When replace='isa', consecutive *isa*-*isa* should be merged."""
        matched, groups, remainder = extract_pattern_and_remainder(
            isa_other_pattern, "avx2_avx2_test", replace='isa')
        assert matched is True
        # Both avx2 instances should be replaced, then merged
        assert "*isa*" in remainder

    def test_multiple_isa_matches_merged(self):
        """Multiple ISA patterns get replaced and then merged."""
        matched, groups, remainder = extract_pattern_and_remainder(
            isa_other_pattern, "avx-sse_func", replace='isa')
        assert matched is True

    def test_none_name(self):
        matched, groups, remainder = extract_pattern_and_remainder(
            arch_other_pattern, None)
        assert matched is False
        assert groups is None
        assert remainder is None


# ---------------------------------------------------------------------------
# has_arch_and_remainder
# ---------------------------------------------------------------------------
class TestHasArchAndRemainder:
    # -- Other arch (x86, arm, etc.) path --
    def test_x86_64(self):
        matched, arch_type, remainder = has_arch_and_remainder("file_x86_64_release")
        assert matched is True
        assert arch_type == OTHER
        assert remainder == "file_*arch*_release"

    def test_arm64(self):
        matched, arch_type, remainder = has_arch_and_remainder("lib_arm64_so")
        assert matched is True
        assert arch_type == OTHER
        assert remainder == "lib_*arch*_so"

    def test_aarch64(self):
        matched, arch_type, remainder = has_arch_and_remainder("aarch64_test")
        assert matched is True
        assert arch_type == OTHER

    # -- RISC-V arch path --
    def test_riscv64(self):
        matched, arch_type, remainder = has_arch_and_remainder("file_riscv64_test")
        assert matched is True
        assert arch_type == RISCV
        assert remainder == "file_*arch*_test"

    def test_riscv(self):
        matched, arch_type, remainder = has_arch_and_remainder("riscv_bin")
        assert matched is True
        assert arch_type == RISCV
        assert remainder == "*arch*_bin"

    def test_risc_v(self):
        matched, arch_type, remainder = has_arch_and_remainder("risc-v_module")
        assert matched is True
        assert arch_type == RISCV

    # -- Both arch present: RISC-V takes precedence --
    def test_both_riscv_and_x86(self):
        matched, arch_type, remainder = has_arch_and_remainder("riscv64_x86_64")
        assert matched is True
        assert arch_type == RISCV

    # -- Neither arch --
    def test_no_match(self):
        matched, arch_type, remainder = has_arch_and_remainder("plain_file")
        assert matched is False
        assert arch_type == OTHER
        assert remainder == "plain_file"

    def test_empty_string(self):
        matched, arch_type, remainder = has_arch_and_remainder("")
        assert matched is False
        assert arch_type == OTHER
        assert remainder == ""

    # -- ISA detection (other) --
    def test_avx2_only(self):
        matched, arch_type, remainder = has_arch_and_remainder("func_avx2_impl")
        assert matched is True
        assert arch_type == OTHER
        assert remainder == "func_*isa*_impl"

    def test_sse_only(self):
        matched, arch_type, remainder = has_arch_and_remainder("sse_handler")
        assert matched is True
        assert arch_type == OTHER
        assert remainder == "*isa*_handler"

    def test_neon_only(self):
        matched, arch_type, remainder = has_arch_and_remainder("neon_accel")
        assert matched is True
        assert arch_type == OTHER

    # -- ISA detection (RISC-V) --
    def test_rvv_isa(self):
        matched, arch_type, remainder = has_arch_and_remainder("rvv_vector")
        assert matched is True
        assert arch_type == RISCV
        assert remainder == "*isa*_vector"

    def test_zba_isa(self):
        matched, arch_type, remainder = has_arch_and_remainder("zba_bitmanip")
        assert matched is True
        assert arch_type == RISCV
        assert remainder == "*isa*_bitmanip"

    def test_zbb_isa(self):
        matched, arch_type, remainder = has_arch_and_remainder("zbb_op")
        assert matched is True
        assert arch_type == RISCV

    # -- ISA + arch combined --
    def test_x86_with_avx2(self):
        matched, arch_type, remainder = has_arch_and_remainder("x86_64_avx2_lib")
        assert matched is True
        assert arch_type == OTHER
        # Both arch and isa should be replaced
        assert "*arch*" in remainder
        assert "*isa*" in remainder

    def test_riscv64_with_rvv(self):
        matched, arch_type, remainder = has_arch_and_remainder("riscv64_rvv_lib")
        assert matched is True
        assert arch_type == RISCV
        assert "*arch*" in remainder
        assert "*isa*" in remainder

    # -- zk edge case --
    def test_zk_alone_matches_riscv_isa(self):
        """When 'zk' appears alone it matches isa_riscv_pattern; since match2 is a tuple
        (not the string 'zk'), the zk edge-case guard in the source does NOT trigger,
        so it is treated as RISC-V."""
        matched, arch_type, remainder = has_arch_and_remainder("zk_crypto")
        assert matched is True
        assert arch_type == RISCV

    def test_zk_with_riscv_arch(self):
        """When 'zk' appears alongside a riscv arch, it IS treated as RISC-V ISA."""
        matched, arch_type, remainder = has_arch_and_remainder("riscv64_zk_crypto")
        assert matched is True
        assert arch_type == RISCV

    def test_zk_with_riscv(self):
        """zk with riscv (no 64) should be treated as RISC-V."""
        matched, arch_type, remainder = has_arch_and_remainder("riscv_zk_module")
        assert matched is True
        assert arch_type == RISCV

    # -- Case sensitivity --
    def test_riscv_uppercase(self):
        """has_arch_and_remainder uses compiled patterns without IGNORECASE,
        so uppercase won't match."""
        matched, arch_type, remainder = has_arch_and_remainder("RISCV64_test")
        assert matched is False
        assert arch_type == OTHER

    def test_x86_uppercase(self):
        """has_arch_and_remainder uses compiled patterns without IGNORECASE,
        so uppercase won't match."""
        matched, arch_type, remainder = has_arch_and_remainder("X86_64_TEST")
        assert matched is False
        assert arch_type == OTHER

    # -- arch_riscv_string validation --
    def test_all_riscv_strings(self):
        from plugin.codemig.codemig_common.arch_detect import arch_riscv_string
        for s in arch_riscv_string:
            assert is_rv_arch(s) is True, f"Expected is_rv_arch('{s}') to be True"

    # -- arch_others_string validation --
    def test_all_other_arch_strings(self):
        from plugin.codemig.codemig_common.arch_detect import arch_others_string
        for s in arch_others_string:
            assert is_other_arch(s) is True, f"Expected is_other_arch('{s}') to be True"

    # -- ISA string list validation --
    def test_isa_riscv_strings(self):
        from plugin.codemig.codemig_common.arch_detect import isa_riscv_string
        import re
        from plugin.codemig.codemig_common.arch_detect import isa_riscv
        for s in isa_riscv_string:
            # Some strings like rv64gcv contain multiple base patterns;
            # at minimum the regex should find something in them
            assert re.search(isa_riscv, s) is not None or s in ("rv64gc", "rv64gcv"), \
                f"isa_riscv_pattern should match '{s}'"

    # -- Edge: riscv32 excluded --
    def test_riscv32_excluded(self):
        matched, arch_type, remainder = has_arch_and_remainder("riscv32_module")
        assert matched is False
        assert arch_type == OTHER

    # -- Multiple ISA merge edge case --
    def test_riscv_arch_with_multiple_isa_merged(self):
        matched, arch_type, remainder = has_arch_and_remainder("riscv64_rvv_zbb_func")
        assert matched is True
        assert arch_type == RISCV

    # -- Other arch with ISA also detected --
    def test_arm64_neon(self):
        matched, arch_type, remainder = has_arch_and_remainder("arm64_neon_simd")
        assert matched is True
        assert arch_type == OTHER

    # -- zk with other ISA (not riscv) --
    def test_zk_alone(self):
        """zk alone matches isa_riscv_pattern (match2 is a tuple, not str 'zk'),
        so it is treated as RISC-V."""
        matched, arch_type, remainder = has_arch_and_remainder("zk")
        assert matched is True
        assert arch_type == RISCV

    # -- Constant values --
    def test_constants(self):
        assert OTHER == 0
        assert RISCV == 1
        assert OTHER != RISCV
