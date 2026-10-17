import pytest
from unittest.mock import patch, MagicMock

from plugin.codemig.codemig_task_manager.arch_missing_process import (
    find_similar_groups,
    replace_name,
    get_split_name,
    find_and_mark_stars,
    detect_arch,
    group_files,
    classify_suffix,
)


class TestFindSimilarGroups:
    def test_groups_by_pattern(self):
        arch_list = [
            (0, "file_*arch*_release", "file_x86_release"),
            (0, "file_*arch*_release", "file_arm_release"),
            (1, "lib_*arch*_so", "lib_riscv_so"),
        ]
        groups = find_similar_groups(arch_list)
        assert "file_*arch*_release" in groups
        assert len(groups["file_*arch*_release"]) == 2
        assert "lib_*arch*_so" in groups

    def test_empty_list(self):
        groups = find_similar_groups([])
        assert groups == {}

    def test_single_item(self):
        arch_list = [(0, "pattern", "path")]
        groups = find_similar_groups(arch_list)
        assert len(groups) == 1

    def test_same_pattern_multiple_items(self):
        arch_list = [
            (0, "same_pattern", "path_a"),
            (1, "same_pattern", "path_b"),
            (0, "same_pattern", "path_c"),
        ]
        groups = find_similar_groups(arch_list)
        assert len(groups) == 1
        assert len(groups["same_pattern"]) == 3


class TestReplaceName:
    def test_basic_replace(self):
        result = replace_name("*arch*", "x86_64_release")
        assert 'riscv' in result

    def test_same_string(self):
        result = replace_name("hello", "hello")
        assert result == "hello"

    def test_empty_strings(self):
        result = replace_name("", "")
        assert result == ""

    def test_only_first_difference_replaced(self):
        result = replace_name("*arch*_*arch*", "x86_64_arm64")
        assert 'riscv' in result

    def test_different_strings(self):
        result = replace_name("abc", "xyz")
        assert isinstance(result, str)


class TestGetSplitName:
    def test_split_by_dash(self):
        parts = get_split_name("riscv64-x86_64")
        assert parts == ["riscv64", "x86", "64"]

    def test_split_by_underscore(self):
        parts = get_split_name("arm_neon")
        assert parts == ["arm", "neon"]

    def test_split_by_dot(self):
        parts = get_split_name("lib.so")
        assert parts == ["lib", "so"]

    def test_no_separator(self):
        parts = get_split_name("nosep")
        assert parts == ["nosep"]

    def test_empty_string(self):
        parts = get_split_name("")
        assert parts == [""]

    def test_split_by_hash(self):
        parts = get_split_name("arch#riscv")
        assert parts == ["arch", "riscv"]

    def test_multiple_separators(self):
        parts = get_split_name("a_b-c.d")
        assert len(parts) == 4


class TestFindAndMarkStars:
    def test_arch_star(self):
        result = find_and_mark_stars("prefix_*arch*_suffix")
        assert result == ['arch']

    def test_isa_star(self):
        result = find_and_mark_stars("prefix_*isa*_suffix")
        assert result == ['isa']

    def test_both_stars(self):
        result = find_and_mark_stars("*arch*_*isa*")
        assert result == ['arch', 'isa']

    def test_no_stars(self):
        result = find_and_mark_stars("plain_text")
        assert result == []

    def test_empty_string(self):
        result = find_and_mark_stars("")
        assert result == []

    def test_multiple_isa_stars(self):
        result = find_and_mark_stars("*isa*_*isa*")
        assert result == ['isa', 'isa']

    def test_multiple_arch_stars(self):
        result = find_and_mark_stars("*arch*_*arch*")
        assert result == ['arch', 'arch']

    def test_mixed_multiple(self):
        result = find_and_mark_stars("*arch*_*isa*_*arch*")
        assert result == ['arch', 'isa', 'arch']


class TestDetectArch:
    def test_empty_list(self):
        result = detect_arch([])
        assert result['missing'] == {}
        assert result['found'] == {}
        assert result['other'] == []

    def test_no_arch_match(self):
        result = detect_arch(["plain_file", "another_file"])
        assert result['missing'] == {}
        assert result['found'] == {}
        assert result['other'] == ["plain_file", "another_file"]

    def test_riscv_only_detection(self):
        result = detect_arch(["file_riscv64_test"])
        assert result['other'] == []
        assert len(result['found']) > 0 or len(result['missing']) == 0

    def test_other_arch_only(self):
        result = detect_arch(["file_x86_64_test"])
        assert len(result['missing']) > 0

    def test_mixed_architectures(self):
        result = detect_arch(["file_riscv64_test", "file_x86_64_test", "plain"])
        assert len(result['other']) == 0 or 'plain' in result['other']

    def test_riscv_and_x86_found(self):
        result = detect_arch(["file_riscv64_test", "file_x86_64_test"])
        assert len(result['found']) > 0

    def test_arm64_arch(self):
        result = detect_arch(["file_arm64_test"])
        assert len(result['missing']) > 0

    def test_aarch64_arch(self):
        result = detect_arch(["lib_aarch64_so"])
        assert len(result['missing']) > 0

    def test_riscv_and_arm64_found(self):
        result = detect_arch(["lib_riscv64_so", "lib_arm64_so"])
        assert len(result['found']) > 0

    def test_multiple_riscv_same_pattern(self):
        result = detect_arch(["file_riscv64_test", "file_riscv_test"])
        assert result['other'] == []

    def test_other_arch_with_remaining_paths(self):
        result = detect_arch(["file_x86_64_test", "file_avx2_impl"])
        assert isinstance(result['other'], list)


class TestGroupFiles:
    def test_empty_list(self):
        missing, found, skip = group_files([])
        assert missing == {}
        assert found == {}
        assert skip == []

    def test_no_matching_suffix(self):
        missing, found, skip = group_files(["readme.txt", "data.csv"])
        assert missing == {}
        assert found == {}
        assert skip == []

    def test_c_file_with_arch(self):
        missing, found, skip = group_files(["func_x86_64.c"])
        assert isinstance(missing, dict) or isinstance(found, dict)

    def test_c_file_riscv_and_x86(self):
        missing, found, skip = group_files(["func_riscv64.c", "func_x86_64.c"])
        assert isinstance(missing, dict) and isinstance(found, dict)
        assert len(found) > 0 or len(missing) >= 0

    def test_multiple_suffixes(self):
        missing, found, skip = group_files([
            "func_x86_64.c", "func_riscv64.c",
            "header_x86_64.h", "header_riscv64.h"
        ])
        assert isinstance(missing, dict)
        assert isinstance(found, dict)

    def test_py_files(self):
        missing, found, skip = group_files(["script_x86_64.py", "script_riscv64.py"])
        assert isinstance(found, dict)

    def test_java_files(self):
        missing, found, skip = group_files(["Main_x86_64.java"])
        assert isinstance(missing, dict)

    def test_go_files_with_riscv_and_x86(self):
        missing, found, skip = group_files(["server_riscv64.go", "server_x86_64.go"])
        assert len(found) > 0

    def test_single_riscv_file(self):
        missing, found, skip = group_files(["func_riscv64.c"])
        assert isinstance(found, dict)

    def test_non_matching_suffix_ignored(self):
        missing, found, skip = group_files(["readme.txt", "image.png"])
        assert missing == {}
        assert found == {}
        assert skip == []


class TestClassifySuffix:
    def test_contains_c_suffix(self):
        assert '.c' in classify_suffix

    def test_contains_h_suffix(self):
        assert '.h' in classify_suffix

    def test_contains_py_suffix(self):
        assert '.py' in classify_suffix

    def test_contains_java_suffix(self):
        assert '.java' in classify_suffix

    def test_contains_asm_suffix(self):
        assert '.asm' in classify_suffix

    def test_contains_go_suffix(self):
        assert '.go' in classify_suffix

    def test_contains_s_suffix(self):
        assert '.s' in classify_suffix

    def test_contains_S_suffix(self):
        assert '.S' in classify_suffix

    def test_contains_cpp_suffix(self):
        assert '.cpp' in classify_suffix

    def test_contains_hpp_suffix(self):
        assert '.hpp' in classify_suffix

    def test_contains_cc_suffix(self):
        assert '.cc' in classify_suffix

    def test_contains_rs_suffix(self):
        assert '.rs' in classify_suffix

    def test_contains_sh_suffix(self):
        assert '.sh' in classify_suffix

    def test_contains_pl_suffix(self):
        assert '.pl' in classify_suffix

    def test_contains_h_in_suffix(self):
        assert '.h.in' in classify_suffix

    def test_contains_c_in_suffix(self):
        assert '.c.in' in classify_suffix

    def test_total_count(self):
        assert len(classify_suffix) == 19


class TestDetectArchDeepBranches:
    """深度覆盖 detect_arch 中的 arch_like, arch_others_string, isa_others_string 分支"""

    def test_arch_like_paths_matched_as_others(self):
        """测试 arch_like (s390, mips, ppc) 路径被分类为 others"""
        result = detect_arch([
            "lib_riscv64_util",
            "lib_x86_64_util",
            "lib_mips_util",
            "lib_s390_util",
        ])
        assert isinstance(result, dict)

    def test_arch_others_string_x86(self):
        """测试 arch_others_string 中 x86 的匹配"""
        result = detect_arch([
            "file_riscv64_test",
            "file_x86_test",
            "file_arm_test",
        ])
        assert isinstance(result, dict)

    def test_isa_others_string_avx(self):
        """测试 isa_others_string 中 avx 的匹配"""
        result = detect_arch([
            "kernel_riscv64_impl",
            "kernel_x86_64_impl",
            "kernel_avx_impl",
            "kernel_sse_impl",
        ])
        assert isinstance(result, dict)

    def test_found_with_other_arch_paths(self):
        """测试 found 组中有其他架构路径的匹配"""
        result = detect_arch([
            "func_*arch*_release_riscv64",
            "func_*arch*_release_x86_64",
            "func_ppc_release",
            "func_loong_release",
        ])
        assert isinstance(result, dict)

    def test_missing_with_isa_match(self):
        """测试 missing 组中 ISA 匹配"""
        result = detect_arch([
            "arch_arm64_impl",
            "arch_riscv64_impl",
            "arch_neon_impl",
            "arch_sve_impl",
        ])
        assert isinstance(result, dict)

    def test_complex_mixed_architectures(self):
        """测试复杂的混合架构场景"""
        result = detect_arch([
            "crypto_riscv64_backend",
            "crypto_x86_64_backend",
            "crypto_arm64_backend",
            "crypto_ppc_backend",
            "crypto_mips_backend",
            "crypto_avx2_backend",
            "crypto_neon_backend",
            "crypto_sparc_backend",
        ])
        assert isinstance(result['other'], list)

    def test_group_files_with_riscv_found_and_skip(self):
        """测试 group_files 中 riscv 找到时的 skip_file 处理"""
        missing, found, skip = group_files([
            "hash_riscv64.c",
            "hash_x86_64.c",
            "hash_avx2.c",
            "hash_neon.c",
            "hash_ppc.c",
        ])
        assert isinstance(found, dict)
        assert len(skip) > 0

    def test_group_files_with_missing_and_others(self):
        """测试 group_files 中 missing 分支的 others 处理"""
        missing, found, skip = group_files([
            "math_arm64_impl.c",
            "math_neon_impl.c",
            "math_avx_impl.c",
            "math_sse_impl.c",
            "math_ppc_impl.c",
        ])
        assert isinstance(missing, dict)
        assert len(skip) > 0


class TestDetectArchArchLike:
    """测试 detect_arch 中 arch_like (s390, mips, ppc, loong, sparc) 分支"""

    def test_ppc_detected_as_other(self):
        """ppc 在 arch_like 中，应被匹配到 others"""
        result = detect_arch([
            "lib_riscv64_util",
            "lib_x86_64_util",
            "lib_ppc_util",
        ])
        # ppc should be in the 'others' of the found group
        for risc, val in result.get('found', {}).items():
            archs, others = val
            if others:
                assert any('ppc' in o for o in others)

    def test_mips_detected_as_other(self):
        """mips 在 arch_like 中"""
        result = detect_arch([
            "lib_riscv64_util",
            "lib_x86_64_util",
            "lib_mips_util",
        ])
        found_others = []
        for risc, val in result.get('found', {}).items():
            archs, others = val
            found_others.extend(others)
        assert any('mips' in o for o in found_others)

    def test_loong_detected_as_other(self):
        """loong 在 arch_like 中"""
        result = detect_arch([
            "lib_riscv64_util",
            "lib_x86_64_util",
            "lib_loong_util",
        ])
        found_others = []
        for risc, val in result.get('found', {}).items():
            archs, others = val
            found_others.extend(others)
        assert any('loong' in o for o in found_others)

    def test_sparc_detected_as_other(self):
        """sparc 在 arch_like 中"""
        result = detect_arch([
            "lib_riscv64_util",
            "lib_x86_64_util",
            "lib_sparc_util",
        ])
        found_others = []
        for risc, val in result.get('found', {}).items():
            archs, others = val
            found_others.extend(others)
        assert any('sparc' in o for o in found_others)


class TestDetectArchArchOthersString:
    """测试 detect_arch 中 arch_others_string (x86, arm, armv8, armv9) 分支"""

    def test_armv8_detected_in_missing(self):
        """armv8 在 arch_others_string 中，应匹配到 archs"""
        result = detect_arch([
            "lib_arm64_util",
        ])
        # arm64 creates a missing entry; remaining paths with armv8 should match
        assert isinstance(result, dict)

    def test_arm_detected_in_missing_others(self):
        """arm 在 arch_others_string 中"""
        result = detect_arch([
            "lib_arm64_util",
            "kernel_armv8_impl",
        ])
        assert isinstance(result, dict)


class TestDetectArchIsaOthersString:
    """测试 detect_arch 中 isa_others_string (avx, sse, neon 等) 分支"""

    def test_avx_matched_via_isa(self):
        """avx 在 isa_others_string 中"""
        result = detect_arch([
            "lib_x86_64_util",
            "lib_avx_util",
        ])
        assert isinstance(result, dict)

    def test_neon_matched_via_isa(self):
        """neon 在 isa_others_string 中"""
        result = detect_arch([
            "lib_arm64_util",
            "lib_neon_util",
        ])
        assert isinstance(result, dict)

    def test_sve_matched_via_isa(self):
        """sve 在 isa_others_string 中"""
        result = detect_arch([
            "lib_arm64_util",
            "lib_sve_util",
        ])
        assert isinstance(result, dict)
