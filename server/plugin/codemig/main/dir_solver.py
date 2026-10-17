import os
import sys

MODULE_PATH = os.path.realpath(
    os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if MODULE_PATH not in sys.path:
    sys.path.append(MODULE_PATH)

from plugin.codemig.codemig_common.migration_class import MigrationClass
from plugin.codemig.codemig_common.arch_pattern import ArchPattern


class DirSolver:

    @staticmethod
    def database_table():
        return MigrationClass.MISSING_ARCH_FILE

    @classmethod
    def solve(cls, dir_path):
        results = {}

        for root, _, files in os.walk(dir_path):
            for file in files:
                # 只处理 .go 或 .s 文件
                if not (file.endswith('.go') or file.endswith('.s')):
                    continue

                if ArchPattern.is_arch_pattern(file):
                    # 生成对应的 _riscv64 文件名（如 base_riscv64.go）
                    riscv64_filename = ArchPattern.get_arch_pattern().sub('_riscv64', file)
                    riscvx_filename = ArchPattern.get_arch_pattern().sub('_riscvx', file)
                    riscv64_path = os.path.join(root, riscv64_filename)
                    riscvx_path = os.path.join(root, riscvx_filename)
                    # 如果 _riscv64 文件不存在，则缺失支持rv架构文件
                    if not os.path.exists(riscv64_path) and not os.path.exists(riscvx_path):
                        # 构造原始文件路径
                        original_path = os.path.join(root, file)
                        if riscv64_path in results:
                            results[riscv64_path].append(original_path)
                        else:
                            results[riscv64_path] = [original_path]
        return results
