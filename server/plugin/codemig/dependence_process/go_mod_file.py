import sys
import os
import re
from pathlib import Path

MODULE_PATH = os.path.realpath(
    os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if MODULE_PATH not in sys.path:
    sys.path.append(MODULE_PATH)
from common.public import logger
from common.public.public import get_codemig_data_path
from plugin.codemig.dependence_process.models import DependenceTask

base_dir = Path(get_codemig_data_path()) / "go_packages"
LOGGER = logger.init_log('codemig')
replace_pattern_advanced = re.compile(
    r'^\s*replace\s+'  # replace 关键字
    r'([^\s=>]+(?:\s+[^\s=>]+)?)'  # 第一部分：模块名和可选版本
    r'\s+=>\s+'  # => 符号
    r'([^\s]+)'  # 第二部分：目标路径或模块
    r'(?:\s+([^\s#]+))?'  # 第三部分：可选的版本号（不能包含空格或注释符）
    r'(?:\s*//.*)?$',  # 可选的注释
    re.MULTILINE
)


def get_package_info(match, go_mod_dir):
    module = match.group(1).strip()
    from_version = None
    if len(module.split(' ')) > 1:
        from_version = module.split(' ')[-1]
        module = module.split(' ')[0]
    rel_path = match.group(2)
    version = match.group(3)
    if not (rel_path.startswith("/") or rel_path.startswith(".") or rel_path.startswith("..")):
        if version:
            abs_path = f'{rel_path} {version}'
        else:
            abs_path = rel_path
    else:
        abs_path = os.path.abspath(os.path.join(go_mod_dir, rel_path))
    # 特殊场景，比如测试代码，依赖的是工程代码，所以会指向源代码的根目录，这种情况需要规避掉
    if len(abs_path.split('/')) - len(get_codemig_data_path().split('/')) == 3:
        LOGGER.info(f'{abs_path} is project self')
        return module, from_version, None, None
    return module, from_version, abs_path, rel_path


def find_all_requirements(content):
    """查找所有的 require 语句（包括单行和多行）"""
    patterns = [
        # 多行 require 块
        r'require\s*\(\s*((?:.*?\n)*?)\s*\)',
        # 单行 require
        r'require\s+([^\n]+)'
    ]

    all_requirements = []

    for pattern in patterns:
        matches = re.finditer(pattern, content, re.DOTALL)
        for match in matches:
            requirements = match.group(1).strip()
            if requirements:
                # 按行分割并清理
                for line in requirements.split('\n'):
                    line = line.strip()
                    if line and not line.startswith('//'):
                        all_requirements.append(line)

    return all_requirements


def parse_go_mod(file_path, packages, local_packages, local_packages_paths):
    replaced_modules = {}
    # 获取 go.mod 所在目录
    go_mod_dir = os.path.dirname(os.path.abspath(file_path))
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
        # 预处理：移除多行注释和合并续行（如果需要）
        content = re.sub(r'//.*$', '', content, flags=re.MULTILINE)  # 移除行内注释
        # 1. 解析所有replace指令
        for match in replace_pattern_advanced.finditer(content):
            module, from_version, abs_path, rel_path = get_package_info(match, go_mod_dir)
            replaced_modules[module] = (from_version, abs_path, rel_path)

        # 2. 收集所有被replace替换的模块
        replace_blocks = re.findall(r'replace\s*\((.*?)\)', content, re.DOTALL)
        for block in replace_blocks:
            for line in block.split('\n'):
                line = line.strip()
                if not line:
                    continue
                # 匹配 replace 行，如: github.com/foo/bar => ./local/path
                match = re.match(r'([^\s=>]+(?:\s+[^\s=>]+)?)\s+=>\s+(\S+)(?:\s+(\S+))?', line)
                if match:
                    module, from_version, abs_path, rel_path = get_package_info(match, go_mod_dir)
                    replaced_modules[module] = (from_version, abs_path, rel_path)

        # 3. 处理require块
        requires = find_all_requirements(content)
        if requires:
            for require in requires:
                # 匹配模块路径和版本
                # match = re.match(r'(\S+)\s+(\S+)', require)
                dep_match = re.match(r'^("?)([^"\s]+)\1\s+(\S+)$', require)
                if dep_match:
                    module = dep_match.group(2)
                    version = dep_match.group(3)

                    # 跳过被replace替换的模块
                    if module in replaced_modules:
                        from_version, abs_path, rel_path = replaced_modules[module]
                        if from_version is not None and version != from_version:
                            packages.add((module, version))
                            continue
                        if abs_path is None and rel_path is None:
                            continue
                        if rel_path.startswith("/") or rel_path.startswith(
                                "./") or rel_path.startswith("../"):
                            local_packages.add((module, f'{version}_local', abs_path, rel_path))
                            local_packages_paths.add(abs_path)
                        else:
                            packages.add(
                                (rel_path, re.sub(rf'^{re.escape(rel_path)}[\s]*', '', abs_path)))
                    else:
                        packages.add((module, version))


def normalize_version(ver_str):
    """标准化版本号"""
    if not isinstance(ver_str, str):
        ver_str = str(ver_str)

    # 移除 v 前缀和空格
    clean = ver_str.lstrip('vV').strip()

    # 处理特殊情况
    if clean == '':
        return '0.0.0'
    # 先按 - 分割主版本和预发布版本
    if '-' in clean:
        main_part, pre_release = clean.split('-', 1)
    else:
        main_part, pre_release = clean, None
    version_parts = main_part.split('.')
    return version_parts, pre_release


def compare_versions(ver1, ver2):
    """比较两个版本号，返回 1: ver1>ver2, 0: 相等, -1: ver1<ver2"""
    v1_parts, pre1 = normalize_version(ver1)
    v2_parts, pre2 = normalize_version(ver2)

    # 补齐长度
    max_len = max(len(v1_parts), len(v2_parts))
    v1_parts.extend([0] * (max_len - len(v1_parts)))
    v2_parts.extend([0] * (max_len - len(v2_parts)))

    for i in range(max_len):
        try:
            v1_num = int(v1_parts[i])
            v2_num = int(v2_parts[i])
            if v1_num != v2_num:
                return 1 if v1_num > v2_num else -1
        except ValueError:
            # 如果是字符串（如 alpha, beta, rc 等）
            if v1_parts[i] != v2_parts[i]:
                return 1 if v1_parts[i] > v2_parts[i] else -1
    if pre1 > pre2:
        return 1
    if pre1 < pre2:
        return -1
    return 0


def combine_packages(packages):
    latest_versions = {}

    for package_name, version in packages:
        # 如果包不存在，或者当前版本更大，则更新
        if package_name not in latest_versions or compare_versions(version, latest_versions[
            package_name]) > 0:
            latest_versions[package_name] = version

    return sorted(latest_versions.items())


def parse_go_dep(source_path, task_id, user_id, dir_id):
    packages = set()
    local_packages = set()
    local_packages_paths = set()
    try:
        for root, _, files in os.walk(source_path, topdown=True):
            for file_name in files:
                if file_name == 'go.mod':
                    file_path = os.path.join(root, file_name)
                    parse_go_mod(file_path, packages, local_packages, local_packages_paths)
        pkg = combine_packages(packages)
        insert_task = [(task_id, dir_id, p, v, '') for (p, v) in pkg]
        local_task = [(task_id, dir_id, p, v, d) for (p, v, d, _) in local_packages]
        local_task = list(set(local_task))
        insert_task = insert_task + local_task

        success, count = DependenceTask.bulk_insert_tasks(insert_task)
        if success:
            return True, count, insert_task
        else:
            return False, f'insert go dependency task error', None
    except (PermissionError, OSError, IOError, AttributeError, FileNotFoundError,
            KeyError, IndexError) as e:
        LOGGER.error(f'{task_id} error', exc_info=True)
        return False, f'parse go dependency error: {str(e)}', None
