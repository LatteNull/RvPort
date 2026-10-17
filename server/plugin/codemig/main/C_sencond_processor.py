import os

MODULE_PATH = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from plugin.codemig.codemig_common.codemig_common_utils import matches_c_file
from plugin.codemig.solver.solvers_mapping import SolverType


def matches_file(file_name):
    return matches_c_file(file_name)


def advise(solver):
    match SolverType(solver.get_solver_type()):
        case SolverType.INLINE_ASM:
            content = '增加相关的内联汇编\n'
        case SolverType.INTRINSICS:
            content = '替换riscv相关的intrinsic函数\n'
        case SolverType.BUILTIN:
            content = '替换riscv相关的builtin函数\n'
        case SolverType.MACROS:
            content = '替换riscv相关的宏定义\n'
        case _:
            content = '仿照其他架构替换相关实现\n'
    return content


def post_process_file(source_file, file_solvers_result):
    if not matches_file(source_file.get_file_path()):
        return
    for solver, result in file_solvers_result.items():
        changed_list, found_list = result
        res_found_list = []
        for found in found_list:
            found_start_lineno = found.start_line
            found_end_lineno = found.end_line
            for solver2, result2 in file_solvers_result.items():
                if solver2 == solver:
                    continue
                changed2_list, _ = result2
                # 收集需要移除的索引
                indices_to_remove = []

                for i, changed in enumerate(changed2_list):
                    changed_start_lineno = changed[0]
                    changed_end_lineno = changed[1]

                    if found_start_lineno <= changed_start_lineno and found_end_lineno >= changed_end_lineno:
                        indices_to_remove.append(i)

                # 从后往前移除，避免索引问题
                for i in sorted(indices_to_remove, reverse=True):
                    if i < len(changed2_list):
                        changed2_list.pop(i)
            res_found_list.append([found_start_lineno, found_end_lineno])
        for changed in changed_list:
            start_lineno = changed[0]
            end_lineno = changed[1]
            for solver2, result2 in file_solvers_result.items():
                if solver2 == solver:
                    continue
                changed2_list, _ = result2
                indices_to_remove_from_changed2 = []

                for i, found in enumerate(changed2_list):
                    found_start_lineno = found[0]
                    found_end_lineno = found[1]

                    if (start_lineno <= found_start_lineno and end_lineno >= found_end_lineno):
                        indices_to_remove_from_changed2.append(i)
                if len(indices_to_remove_from_changed2) > 0:
                    changed[2] += f'{advise(solver2)}'
                # 从后往前移除
                for i in sorted(indices_to_remove_from_changed2, reverse=True):
                    if i < len(changed2_list):
                        changed2_list.pop(i)
        file_solvers_result[solver] = (changed_list, res_found_list)
