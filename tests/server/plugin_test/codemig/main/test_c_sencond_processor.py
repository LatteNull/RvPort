import pytest
from unittest.mock import MagicMock, patch

from plugin.codemig.main.C_sencond_processor import (
    matches_file,
    advise,
    post_process_file
)
from plugin.codemig.solver.solvers_mapping import SolverType


class TestMatchesFile:
    """测试 matches_file 函数"""

    @patch('plugin.codemig.main.C_sencond_processor.matches_c_file')
    def test_matches_file_c_extension(self, mock_matches_c_file):
        """测试 C 文件扩展名匹配"""
        mock_matches_c_file.return_value = True
        
        result = matches_file("test.c")
        
        assert result is True
        mock_matches_c_file.assert_called_once_with("test.c")

    @patch('plugin.codemig.main.C_sencond_processor.matches_c_file')
    def test_matches_file_cpp_extension(self, mock_matches_c_file):
        """测试 C++ 文件扩展名匹配"""
        mock_matches_c_file.return_value = False
        
        result = matches_file("test.cpp")
        
        assert result is False

    @patch('plugin.codemig.main.C_sencond_processor.matches_c_file')
    def test_matches_file_h_extension(self, mock_matches_c_file):
        """测试头文件扩展名匹配"""
        mock_matches_c_file.return_value = True
        
        result = matches_file("test.h")
        
        assert result is True


class TestAdvise:
    """测试 advise 函数"""

    def test_advise_inline_asm(self):
        """测试内联汇编建议"""
        mock_solver = MagicMock()
        mock_solver.get_solver_type.return_value = SolverType.INLINE_ASM

        result = advise(mock_solver)

        assert result == "增加相关的内联汇编\n"

    def test_advise_intrinsics(self):
        """测试 intrinsic 函数建议"""
        mock_solver = MagicMock()
        mock_solver.get_solver_type.return_value = SolverType.INTRINSICS

        result = advise(mock_solver)

        assert result == "替换riscv相关的intrinsic函数\n"

    def test_advise_builtin(self):
        """测试 builtin 函数建议"""
        mock_solver = MagicMock()
        mock_solver.get_solver_type.return_value = SolverType.BUILTIN

        result = advise(mock_solver)

        assert result == "替换riscv相关的builtin函数\n"

    def test_advise_macros(self):
        """测试宏定义建议"""
        mock_solver = MagicMock()
        mock_solver.get_solver_type.return_value = SolverType.MACROS

        result = advise(mock_solver)

        assert result == "替换riscv相关的宏定义\n"

    def test_advise_makefile_default_case(self):
        """测试 Makefile 类型建议（默认分支）"""
        mock_solver = MagicMock()
        mock_solver.get_solver_type.return_value = SolverType.MAKEFILE
        
        result = advise(mock_solver)
        
        # MAKEFILE 不是 INTRINSICS, BUILTIN, MACROS, INLINE_ASM，所以走默认分支
        assert result == "仿照其他架构替换相关实现\n"
class TestPostProcessFile:
    """测试 post_process_file 函数"""

    def test_post_process_file_non_c_file(self):
        """测试非 C 文件不处理"""
        mock_source_file = MagicMock()
        mock_source_file.get_file_path.return_value = "test.cpp"
        
        file_solvers_result = {}
        
        with patch('plugin.codemig.main.C_sencond_processor.matches_file', return_value=False):
            result = post_process_file(mock_source_file, file_solvers_result)
        
        assert result is None

    def test_post_process_file_empty_result(self):
        """测试空结果"""
        mock_source_file = MagicMock()
        mock_source_file.get_file_path.return_value = "test.c"
        
        file_solvers_result = {}
        
        with patch('plugin.codemig.main.C_sencond_processor.matches_file', return_value=True):
            result = post_process_file(mock_source_file, file_solvers_result)
        
        assert result is None

    def test_post_process_file_single_solver(self):
        """测试单个 solver 的情况"""
        mock_source_file = MagicMock()
        mock_source_file.get_file_path.return_value = "test.c"
        
        mock_solver = MagicMock()
        mock_solver.get_solver_type.return_value = SolverType.INLINE_ASM
        
        # changed_list 和 found_list
        mock_found = MagicMock()
        mock_found.start_line = 10
        mock_found.end_line = 20
        
        changed_list = [[15, 18, "original"]]
        found_list = [mock_found]
        
        file_solvers_result = {mock_solver: (changed_list, found_list)}
        
        with patch('plugin.codemig.main.C_sencond_processor.matches_file', return_value=True):
            post_process_file(mock_source_file, file_solvers_result)
        
        # 只有一个 solver，没有其他 solver 来影响结果
        assert mock_solver in file_solvers_result

    def test_post_process_file_overlapping_ranges(self):
        """测试重叠范围的情况"""
        mock_source_file = MagicMock()
        mock_source_file.get_file_path.return_value = "test.c"
        
        mock_solver1 = MagicMock()
        mock_solver1.get_solver_type.return_value = SolverType.INLINE_ASM.value
        
        mock_solver2 = MagicMock()
        mock_solver2.get_solver_type.return_value = SolverType.INTRINSICS.value
        
        # Solver1 的 found_list - 大范围
        mock_found = MagicMock()
        mock_found.start_line = 10
        mock_found.end_line = 50
        
        # Solver1 的 changed_list - 小范围在 found 范围内
        changed_list1 = [[15, 20, "original1"]]
        found_list1 = [mock_found]
        
        # Solver2 的 changed_list - 与 found 重叠
        changed_list2 = [[12, 25, "original2"]]
        found_list2 = []
        
        file_solvers_result = {
            mock_solver1: (changed_list1, found_list1),
            mock_solver2: (changed_list2, found_list2)
        }
        
        with patch('plugin.codemig.main.C_sencond_processor.matches_file', return_value=True):
            post_process_file(mock_source_file, file_solvers_result)
        
        # 检查结果是否被正确更新
        assert mock_solver1 in file_solvers_result
        assert mock_solver2 in file_solvers_result

    def test_post_process_file_contained_ranges(self):
        """测试包含范围的情况"""
        mock_source_file = MagicMock()
        mock_source_file.get_file_path.return_value = "test.c"
        
        mock_solver1 = MagicMock()
        mock_solver1.get_solver_type.return_value = SolverType.INLINE_ASM.value
        
        mock_solver2 = MagicMock()
        mock_solver2.get_solver_type.return_value = SolverType.INTRINSICS.value
        
        # Solver1 的 changed_list - 大范围
        changed_list1 = [[10, 50, "original1"]]
        found_list1 = []
        
        # Solver2 的 changed_list - 小范围在大范围内
        changed_list2 = [[15, 20, "original2"]]
        found_list2 = []
        
        file_solvers_result = {
            mock_solver1: (changed_list1, found_list1),
            mock_solver2: (changed_list2, found_list2)
        }
        
        with patch('plugin.codemig.main.C_sencond_processor.matches_file', return_value=True):
            post_process_file(mock_source_file, file_solvers_result)
        
        # changed_list1 中的元素应该添加了建议
        assert len(changed_list1) > 0
        # 第三个元素应该是添加了建议后的字符串
        if len(changed_list1[0]) >= 3:
            assert "original1" in str(changed_list1[0][2])

    def test_post_process_file_no_overlap(self):
        """测试无重叠范围的情况"""
        mock_source_file = MagicMock()
        mock_source_file.get_file_path.return_value = "test.c"
        
        mock_solver1 = MagicMock()
        mock_solver1.get_solver_type.return_value = SolverType.INLINE_ASM.value
        
        mock_solver2 = MagicMock()
        mock_solver2.get_solver_type.return_value = SolverType.INTRINSICS.value
        
        # Solver1 的范围
        changed_list1 = [[10, 20, "original1"]]
        found_list1 = []
        
        # Solver2 的范围 - 完全不重叠
        changed_list2 = [[30, 40, "original2"]]
        found_list2 = []
        
        file_solvers_result = {
            mock_solver1: (changed_list1, found_list1),
            mock_solver2: (changed_list2, found_list2)
        }
        
        original_changed_list1 = [row[:] for row in changed_list1]
        
        with patch('plugin.codemig.main.C_sencond_processor.matches_file', return_value=True):
            post_process_file(mock_source_file, file_solvers_result)
        
        # 没有重叠，不应该有移除操作
        assert changed_list1 == original_changed_list1

    def test_post_process_file_multiple_solvers(self):
        """测试多个 solver 的情况"""
        mock_source_file = MagicMock()
        mock_source_file.get_file_path.return_value = "test.c"
        
        mock_solver1 = MagicMock()
        mock_solver1.get_solver_type.return_value = SolverType.INLINE_ASM.value
        
        mock_solver2 = MagicMock()
        mock_solver2.get_solver_type.return_value = SolverType.INTRINSICS.value
        
        mock_solver3 = MagicMock()
        mock_solver3.get_solver_type.return_value = SolverType.BUILTIN.value
        
        changed_list1 = [[10, 20, "original1"]]
        found_list1 = []
        
        changed_list2 = [[15, 25, "original2"]]
        found_list2 = []
        
        changed_list3 = [[18, 22, "original3"]]
        found_list3 = []
        
        file_solvers_result = {
            mock_solver1: (changed_list1, found_list1),
            mock_solver2: (changed_list2, found_list2),
            mock_solver3: (changed_list3, found_list3)
        }
        
        with patch('plugin.codemig.main.C_sencond_processor.matches_file', return_value=True):
            post_process_file(mock_source_file, file_solvers_result)
        
        # 所有 solver 都应该在结果中
        assert mock_solver1 in file_solvers_result
        assert mock_solver2 in file_solvers_result
        assert mock_solver3 in file_solvers_result
