import sys
import time

import os
import re
import shutil
import subprocess
from pathlib import Path

MODULE_PATH = os.path.realpath(
    os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if MODULE_PATH not in sys.path:
    sys.path.append(MODULE_PATH)
from common.public import logger
from common.public.public import get_codemig_data_path
from plugin.codemig.dependence_process.dependence_sql import scan_packages, \
    record_fail_package_info
from plugin.codemig.dependence_process.models import DependencePackages
from plugin.codemig.dependence_process.dependence_info import DOWNLOAD_TIMEOUT
from plugin.codemig.dependence_process.dependence_base import DependenceProcessor

base_dir = Path(get_codemig_data_path()) / "go_packages"
LOGGER = logger.init_log('codemig')


def get_module_dir(module_path, version, local_path=None):
    """获取模块的安装目录路径"""
    if local_path:
        return os.path.realpath(local_path)
    dir_path = module_path.strip('/').split('/')
    if version:
        dir_path[-1] = f"{dir_path[-1]}@{version}"
    safe_path = [re.sub(r'[^\w\.@-]', '_', part) for part in dir_path]

    return os.path.join(base_dir, *safe_path)


def install_module(go_path, module_path, version, target_dir, env, dir_id):
    """安装单个Go模块到指定目录"""
    # 构建命令
    module_spec = f"{module_path}@{version}" if version else module_path
    cmd = [go_path, "mod", "download", "-json", module_spec]

    try:
        LOGGER.info(f"正在下载Go模块 {module_spec} 到 {target_dir}...")
        if env:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True, env=env,
                                    timeout=DOWNLOAD_TIMEOUT)
        else:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True,
                                    timeout=DOWNLOAD_TIMEOUT)
        # 解析下载结果
        if result.stdout:
            download_info = eval(result.stdout)
            actual_path = download_info.get("Dir", "")
            if actual_path:
                # 将下载的模块复制到目标目录
                if not os.path.exists(target_dir):
                    try:
                        shutil.copytree(actual_path, target_dir, symlinks=True)
                    except (OSError, IOError, PermissionError, FileNotFoundError) as e:
                        LOGGER.info(f"{module_spec} -> {target_dir} exception: {e} ")
                else:
                    LOGGER.info(f" 目录已存在{target_dir} ")
                    count = 50
                    while count > 0:
                        dep = DependencePackages.is_package_installed(module_path, version)
                        if dep:
                            LOGGER.info(f"{module_path}_{version} 已安装，跳过")
                            return True, None, dep
                        count -= 1
                        time.sleep(2)
                    if os.path.exists(target_dir):
                        try:
                            shutil.rmtree(target_dir)
                            shutil.copytree(actual_path, target_dir, symlinks=True)
                        except (OSError, IOError, PermissionError, FileNotFoundError) as e:
                            LOGGER.error(f"{module_spec} -> {target_dir} exception: {e} ")

                LOGGER.info(f"下载成功: {module_spec} -> {target_dir}")
                return scan_packages(module_path, version, target_dir, module_spec)
        dep = record_fail_package_info(module_path, version, target_dir,
                                       f"安装 {module_spec} 失败!")
        return False, f"安装 {module_spec} 失败! {result.stderr if result.stderr else result.stdout}", dep
    except subprocess.TimeoutExpired:
        dep = record_fail_package_info(module_path, version, target_dir,
                                       f"下载 {module_spec} 超时! 可能文件过大，或者网路问题，请手动下载再分析")
        LOGGER.error(f"错误: 执行下载{module_spec}超时，请检查网络")
        return False, "下载失败，可能文件过大，或者网路问题，请手动下载再分析", dep
    except subprocess.CalledProcessError as e:
        dep = record_fail_package_info(module_path, version, target_dir,
                                       f"安装 {module_spec} 失败! {e.stderr}")
        return False, f"安装 {module_spec} 失败! {e.stderr if e.stderr else e.stdout}", dep


def install_local_module(module_path, version, local_path, target_dir, dir_id):
    if not os.path.exists(local_path):
        LOGGER.error(f"本地依赖路径不存在: {local_path}")
        return False, f"本地依赖路径不存在: {local_path}", None
    module_spec = f"{module_path}@{version}" if version else module_path
    return scan_packages(module_path, version, local_path, module_spec)


def validate_go_install_path(go_path):
    """验证 Go 安装路径是否有效"""
    if not go_path:
        return False, "Go安装路径为空"

    # 检查路径是否存在
    if not os.path.exists(go_path):
        return False, f"Go安装路径不存在: {go_path}"

    # 验证Go版本
    try:
        result = subprocess.run(
            [go_path, 'version'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if "go version" not in result.stdout:
            return False, f"路径不是有效的Go安装: {go_path}"
    except (subprocess.TimeoutExpired, FileNotFoundError, PermissionError, OSError) as e:
        return False, f"验证Go安装路径时出错: {str(e)}"

    return True, "Go安装路径验证通过"


def validate_and_parse_go_environment(env_str):
    """验证并解析Go环境变量字符串，只验证格式不限制具体变量"""
    if not env_str:
        return True, {}  # 空环境变量是允许的
    env_dict = {}
    env_pairs = [pair.strip() for pair in env_str.split('|') if pair.strip()]

    for pair in env_pairs:
        if '=' not in pair:
            return False, f"错误: 环境变量格式不正确，缺少等号: {pair}"

        var_name, var_value = pair.split('=', 1)
        var_name = var_name.strip()
        var_value = var_value.strip()

        # 基本格式验证
        if not re.fullmatch(r'^[A-Za-z_][A-Za-z0-9_]*$', var_name):
            return False, f"错误: 环境变量名格式不正确: {var_name}"

        # 值不能为空
        if not var_value:
            return False, f"错误: 环境变量值不能为空: {var_name}"

        # 特殊处理文件路径类变量
        if var_name.endswith(('_FILE', '_PATH')) and not os.path.exists(var_value):
            LOGGER.warning(f"警告: 文件路径环境变量 {var_name} 指向的文件不存在: {var_value}")
            # 这里只是警告，不阻止继续执行

        env_dict[var_name] = var_value

    return True, env_dict


class GoDependenceProcessor(DependenceProcessor):
    """
    Go 依赖处理器
    """

    def __init__(self, config, to_process, task_id):
        """
        初始化 Go 依赖处理器

        Args:
            config: 配置参数 (go_path, go_env_str)
            to_process: 待处理的依赖列表
            task_id: 任务ID
        """
        super().__init__(config_name="Go", config=config, to_process=to_process, task_id=task_id)
        self.validated_config = None

    def validate_config(self, config):
        """
        验证 Go 配置

        Args:
            config: (go_path, go_env_str) 元组

        Returns:
            tuple: (is_valid: bool, validated_config or error_msg)
        """
        go_path, go_env_str = config
        is_valid, msg = validate_go_install_path(go_path)
        if not is_valid:
            return False, msg
        # 验证并解析 Go 环境变量
        env_valid, go_env_or_error_msg = validate_and_parse_go_environment(go_env_str)
        if not env_valid:
            return False, go_env_or_error_msg
        self.validated_config = (go_path, go_env_or_error_msg)
        return True, (go_path, go_env_or_error_msg)

    def _get_base_dir(self):
        """获取基础目录路径"""
        return str(base_dir)

    def _should_check_installed(self, local_path):
        """判断是否需要检查包是否已安装（仅当不是本地路径时）"""
        return local_path is None or local_path == ''

    def _extract_version_for_check(self, package, version):
        """提取版本号用于检查"""
        return version

    @staticmethod
    def install_single_package(dir_id, pkg, version, local_path, validated_config):
        """安装单个包"""
        go_path, go_env = validated_config

        # 构建环境变量
        env = os.environ.copy()
        env["GO111MODULE"] = "on"
        if go_env:
            for key, value in go_env.items():
                env[key] = value

        module_dir = get_module_dir(pkg, version, local_path)

        # 安装模块
        if local_path:
            return install_local_module(
                module_path=pkg,
                version=version,
                local_path=local_path,
                target_dir=module_dir,
                dir_id=dir_id
            )
        else:
            return install_module(
                go_path=go_path,
                module_path=pkg,
                version=version,
                target_dir=module_dir,
                env=env,
                dir_id=dir_id
            )
