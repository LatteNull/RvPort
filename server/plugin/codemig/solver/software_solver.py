import os
import subprocess
import sys
from typing import override

MODULE_PATH = os.path.realpath(
    os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if MODULE_PATH not in sys.path:
    sys.path.append(MODULE_PATH)

from plugin.codemig.codemig_common.migration_class import MigrationClass
from plugin.codemig.solver.solver import Solver
from plugin.codemig.codemig_common.codemig_common_utils import ChangeType

# 目标平台架构 (RV架构)
TARGET_ARCHITECTURE = 'riscv64'


def analyze_library(lib_path, scan_results):
    """
    分析本地库文件的架构信息
    :param lib_path: 库文件路径
    :param scan_results: 扫描结果列表
    """
    # 获取文件架构信息
    arch_info = get_file_architecture(lib_path)

    # 如果文件架构不是RV架构
    if not is_architecture_supported(arch_info):
        # 返回文件架构信息和建议信息
        # TODO 建议信息后续补充
        scan_results.append([arch_info, None])


def get_file_architecture(file_path):
    """
    获取文件的架构信息
    :param file_path: 文件路径
    :return: 架构信息字符串
    """
    try:
        # Linux/macOS使用file命令
        result = subprocess.run(
            ['file', '--brief', file_path],
            capture_output=True, text=True
        )
        output = result.stdout
        # 解析file命令输出
        if 'ELF 64-bit' in output:
            if 'x86-64' in output:
                return 'x86_64'
            if 'aarch64' in output or 'ARM' in output:
                return 'arm64'
            if 'riscv64' in output or 'RISCV64' in output or 'RISC-V' in output:
                return 'riscv64'
            return 'unknown_64bit'
        if 'ELF 32-bit' in output:
            if 'ARM' in output:
                return 'arm'
            if 'Intel 80386' in output:
                return 'x86'
            return 'unknown_32bit'
        if 'Mach-O' in output:
            if 'x86_64' in output:
                return 'x86_64'
            if 'arm64' in output:
                return 'arm64'
            return 'unknown_macho'
        if 'PE32+' in output:
            return 'x86_64'
        if 'PE32' in output:
            return 'x86'
        return 'unknown'
    except (OSError, FileNotFoundError, PermissionError, AttributeError, subprocess.TimeoutExpired,
             UnicodeDecodeError):
        return 'error'


def is_architecture_supported(arch_info):
    """
    判断架构是否支持目标平台
    :param arch_info: 架构信息字符串
    :return: 是否支持
    """
    return arch_info.lower() == TARGET_ARCHITECTURE.lower()


class SoftwareSolver(Solver):

    # 扫描Python包中的原生库并检测RISC-V架构支持
    @staticmethod
    @override
    def matches_file(file_name):
        return file_name.endswith(".so") or file_name.endswith(".dll")

    @classmethod
    @override
    def solve(cls, source_file):
        file_path = source_file.get_file_path()
        scan_results = []
        analyze_library(file_path, scan_results)
        return scan_results, []

    @staticmethod
    @override
    def append_or_replace():
        return ChangeType.OTHER.value

    @staticmethod
    @override
    def migration_class():
        return MigrationClass.DYNAMIC_LINK_LIBRARY
