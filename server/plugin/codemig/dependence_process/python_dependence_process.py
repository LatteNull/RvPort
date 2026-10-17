import sys

import json
import os
import random
import re
import shutil
import string
import subprocess
from pathlib import Path
from urllib.parse import urlparse
from json.decoder import JSONDecodeError

MODULE_PATH = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if MODULE_PATH not in sys.path:
    sys.path.append(MODULE_PATH)

from common.public import logger
from common.public.public import get_codemig_data_path
from plugin.codemig.codemig_common.codemig_common_utils import extract_file
from plugin.codemig.dependence_process.dependence_sql import scan_packages, record_fail_package_info
from plugin.codemig.dependence_process.dependence_info import DOWNLOAD_TIMEOUT
from plugin.codemig.dependence_process.models import DependencePackages
from plugin.codemig.dependence_process.dependence_base import (
    DependenceProcessor
)

base_dir = Path(get_codemig_data_path()) / "python_packages"
LOGGER = logger.init_log('codemig')


def get_package_dir(pkg_name, version):
    """获取包的安装目录路径"""
    safe_name = re.sub(r'[^a-zA-Z0-9_]', '_', pkg_name)
    safe_version = re.sub(r'[^0-9.]', '', version)
    dir_name = f"{safe_name}_{safe_version}" if safe_version else safe_name
    return os.path.join(base_dir, dir_name)


def get_tmp_dir():
    """获取包的安装目录路径"""
    characters = string.ascii_letters + string.digits
    random_file_name = ''.join(random.choice(characters) for _ in range(8))
    return os.path.join(base_dir, random_file_name)


def get_pip_config(python_path):
    """
    使用 pip config list 命令获取配置
    """
    try:
        # 获取 pip 配置列表
        result = subprocess.run(
            [python_path, '-m', 'pip', 'config', 'list'],
            capture_output=True,
            text=True,
            # timeout=10
        )

        if result.returncode == 0:
            config = {}
            for line in result.stdout.split('\n'):
                if '=' in line:
                    key, value = line.split('=', 1)
                    config[key.strip()] = value.strip()
            return config
        else:
            print(f"pip config 命令失败: {result.stderr}")
            return {}

    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        print(f"执行 pip config 命令时出错: {e}")
        return {}


def get_proxy_from_pip_config(python_path, python_config):
    """
    从 pip config 中提取代理设置
    """
    if python_config and python_config[0]:
        return python_config[1]
    config = get_pip_config(python_path)
    proxy_settings = {}

    proxy_keys = ['global.proxy', 'global.http-proxy', 'global.https-proxy', 'global.no-proxy']

    for key in proxy_keys:
        if key in config:
            value = config[key].strip("'")
            if key == 'global.proxy':
                proxy_settings['http'] = value
                proxy_settings['https'] = value
            elif key == 'global.http-proxy':
                proxy_settings['http'] = value
            elif key == 'global.https-proxy':
                proxy_settings['https'] = value
            if key == 'global.no-proxy':
                proxy_settings['no-proxy'] = value
    python_config = (True, proxy_settings)
    return proxy_settings


def download_with_proxy(link, target_dir, python_path=None, python_config=None):
    pip_proxy = get_proxy_from_pip_config(python_path, python_config)
    env = os.environ.copy()
    if 'http' in pip_proxy:
        env['http_proxy'] = pip_proxy.get('http')
    if 'https' in pip_proxy:
        env['https_proxy'] = pip_proxy.get('https')
    if 'no_proxy' in pip_proxy:
        env['no_proxy'] = pip_proxy.get('no_proxy')
    try:

        result = subprocess.run(['wget', '-P', target_dir, link], capture_output=True, text=True,
                                env=env, timeout=43200)
        if result.returncode == 0:
            return True, None
        else:
            return False, f"安装 {link} 失败! {result.stderr}"
    except subprocess.TimeoutExpired:
        LOGGER.error(f"错误: 执行下载{link}超时，请检查网络")
        return False, "下载失败，可能文件过大，或者网路问题，请手动下载再分析"
    except (subprocess.CalledProcessError, OSError, IOError, FileNotFoundError,
            PermissionError) as e:
        error_msg = f"安装 {link} 失败! {e}"
        LOGGER.error(e, exc_info=True)
        return False, error_msg


def download_package_source(cmd, target_dir, python_path, python_config):
    try:
        env = os.environ.copy()
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=DOWNLOAD_TIMEOUT,
                                env=env)
        if result.returncode == 0:

            return True, result.stdout
        else:
            for line in result.stdout.splitlines():
                if 'Downloading' in line and 'http' in line:
                    match = re.search(r'(https?://[^\s]+)', line)
                    if match:
                        link = match.group(1)
                        return download_with_proxy(link, target_dir, python_path, python_config)
            return False, result.stderr
    except subprocess.TimeoutExpired:
        LOGGER.error(f"错误: 执行 {' '.join(cmd)}超时，请检查网络")
        return False, "下载失败，可能文件过大，或者网路问题，请手动下载再分析"
    except subprocess.CalledProcessError as e:
        error_msg = f"安装 {cmd} 失败! {e.stderr}"
        LOGGER.error(error_msg, exc_info=True)
        return False, error_msg


def extract_version_advanced(filename):
    """
    更精确的版本号提取，支持各种格式
    """
    # 移除扩展名
    base_name = re.sub(r'\.tar\.gz$', '', filename)

    # 定义版本号模式（更全面）
    version_patterns = [
        # 标准格式: name-version
        r'^(?:.*[_-])?v?(\d+\.\d+\.\d+(?:[._-]?(?:alpha|beta|rc|dev|a|b)\d*)?)',
        r'^(?:.*[_-])?v?(\d+\.\d+(?:[._-]?(?:alpha|beta|rc|dev|a|b)\d*)?)',
        r'^(?:.*[_-])?v?(\d+(?:[._-]?(?:alpha|beta|rc|dev|a|b)\d*)?)',

        # 其他常见格式
        r'v?(\d+\.\d+\.\d+)[a-zA-Z]',  # 1.2.3a
        r'v?(\d+\.\d+)[a-zA-Z]',  # 1.2a
    ]

    for pattern in version_patterns:
        match = re.search(pattern, base_name, re.IGNORECASE)
        if match:
            return match.group(1)

    return None


def remove_pkg_advanced(spec, pkg):
    """高级版本：处理各种分隔符"""
    # 匹配包名后面可能的分隔符：空格、==、>=、<=、~=、!=等
    pattern = rf'^{re.escape(pkg)}[\s=<>!~]*'
    return re.sub(pattern, '', spec)


def download_package(python_path, pkg_spec, mirror_url, dir_id, python_config):
    """安装单个包到指定目录"""
    tmp_dir = get_tmp_dir()
    os.makedirs(tmp_dir, exist_ok=True)
    # 构建安装命令
    # cmd = [
    #     python_path,
    #     '-m', 'pip',
    #     'install',
    #     pkg_spec,
    #     '--target', target_dir,
    #     '--no-deps',  # 不安装相关依赖
    # ]
    pkg, specs = pkg_spec
    specs_string = [spec.strip().replace('"', "'") for spec in specs]
    query_cmd = [python_path,
                 '-m', 'pip', 'install', '--no-deps',
                 '--dry-run', '--report', '-', '-q',
                 *specs_string]
    if mirror_url:
        query_cmd.extend(
            ['-i', mirror_url, '--trusted-host', mirror_url.split('://')[1].split('/')[0]])
    result = None
    try:
        LOGGER.info(f"正在查询 {pkg} ...")
        env = os.environ.copy()
        result = subprocess.run(query_cmd, capture_output=True, text=True, timeout=DOWNLOAD_TIMEOUT,
                                env=env)
        if result.returncode == 0:
            data = json.loads(result.stdout)
            if 'install' in data:
                for install in data['install']:
                    if 'metadata' in install and 'version' in install['metadata']:
                        version = install['metadata']['version']
                        dep_id = DependencePackages.is_package_installed(pkg, version)
                        if dep_id:
                            LOGGER.info(f"{pkg}=={version} 已安装，跳过")
                            return True, None, dep_id
    except (subprocess.SubprocessError, AttributeError) as e:
        pass
    except FileNotFoundError as e:
        error_msg = f"安装 {pkg} 失败! {e}"
        dep_id = record_fail_package_info(pkg, remove_pkg_advanced('\n'.join(specs), pkg), '',
                                          error_msg)
        return False, error_msg, dep_id
    except JSONDecodeError as e:
        error_msg = f"查询 {pkg} 失败! : {result.stdout}"
        LOGGER.error(error_msg)
    cmd = [
        python_path,
        '-m', 'pip',
        'download',
        *specs_string,
        '--no-binary', ':all:',
        '-d', tmp_dir,
        '--no-deps',  # 不安装相关依赖
        '--no-cache-dir',
        '--no-input'
    ]

    if mirror_url:
        cmd.extend(['-i', mirror_url, '--trusted-host', mirror_url.split('://')[1].split('/')[0]])

    try:
        LOGGER.info(f"正在安装 {pkg} 到 {tmp_dir}...")
        status, error_msg = download_package_source(cmd, tmp_dir, python_path, python_config)
        if not status:
            dep_id = record_fail_package_info(pkg, remove_pkg_advanced('\n'.join(specs), pkg), '',
                                              error_msg)
            return status, error_msg, dep_id
        LOGGER.info(f"安装 {pkg} 到 {tmp_dir}成功")
        # 获取实际安装的版本

        compress_file = None
        for file in os.listdir(tmp_dir):
            if file != "." and file != '..':
                compress_file = os.path.join(tmp_dir, file)
                break
        if not compress_file:
            msg = [m for m in error_msg.split('\n') if not m.startswith("[notice]")]
            return False, '\n'.join(msg), None

        version = extract_version_advanced(os.path.basename(compress_file))
        # 重命名目录以包含版本号
        versioned_dir = get_package_dir(pkg, version)
        if os.path.exists(versioned_dir):
            dep_id = DependencePackages.is_package_installed(pkg, version)
            if dep_id:
                LOGGER.info(f"{pkg}=={version} 已安装，跳过")
                return True, None, dep_id
        extract_file(Path(compress_file), Path(tmp_dir), max_depth=1)
        os.remove(compress_file)
        uncompress_dir = None
        for file in os.listdir(tmp_dir):
            if os.path.isdir(os.path.join(tmp_dir, file)):
                uncompress_dir = os.path.join(tmp_dir, file)
        if uncompress_dir is None:
            LOGGER.error(f'{pkg_spec} cannot find uncompress dir')
            return False, f'{pkg_spec} cannot find uncompress dir', None
        # 重命名目录以包含版本号
        if os.path.exists(versioned_dir):
            shutil.rmtree(versioned_dir)
        os.rename(uncompress_dir, versioned_dir)

        return scan_packages(pkg, version, versioned_dir, pkg + version)
    except subprocess.CalledProcessError as e:
        error_msg = f"安装 {pkg} 失败! {e.stderr}"
        dep_id = record_fail_package_info(pkg, remove_pkg_advanced('\n'.join(specs), pkg), '',
                                          error_msg)
        return False, error_msg, dep_id
    except FileNotFoundError as e:
        error_msg = f"安装 {pkg} 失败! {e}"
        dep_id = record_fail_package_info(pkg, remove_pkg_advanced('\n'.join(specs), pkg), '',
                                          error_msg)
        return False, error_msg, dep_id
    finally:
        if os.path.exists(tmp_dir):
            shutil.rmtree(tmp_dir)


def validate_python_interpreter(python_path):
    """验证 Python 解释器路径是否有效"""
    if not python_path:
        return False, f"错误: Python解释器未配置"
    if not os.path.exists(python_path):
        return False, f"错误: Python解释器路径不存在: {python_path}"

    if not os.path.isfile(python_path):
        return False, f"错误: 路径不是文件: {python_path}"

    if not os.access(python_path, os.X_OK):
        return False, f"错误: Python解释器不可执行: {python_path}"

    try:
        result = subprocess.run(
            [python_path, "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if "Python" not in result.stdout and "Python" not in result.stderr:
            return False, f"错误: 路径不是有效的Python解释器: {python_path}"
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, OSError, FileNotFoundError,
            PermissionError) as e:
        return False, f"错误: 验证Python解释器时出错: {str(e)}"

    return True, "验证通过"


def validate_python_mirror(mirror_url):
    """验证Python镜像源是否有效"""
    # 基本URL格式验证
    try:
        result = urlparse(mirror_url)
        if not all([result.scheme, result.netloc]):
            return False, f"镜像源URL格式不正确: {mirror_url}"

        if result.scheme not in ('http', 'https'):
            return False, f"镜像源协议必须是http或https: {mirror_url}"
    except (ValueError, TypeError, AttributeError) as e:
        return False, f"镜像源URL解析失败: {str(e)}"

    try:
        import requests
        test_url = mirror_url.rstrip('/')
        response = requests.get(test_url, timeout=(10, 10))
        if response.status_code != 200:
            return False, f"镜像源不可达或响应异常(HTTP {response.status_code}): {mirror_url}"
    except requests.RequestException as e:
        return False, f"镜像源连接测试失败: {str(e)}"

    return True, f"镜像源验证通过: {mirror_url}"


class PythonDependenceProcessor(DependenceProcessor):
    """
    Python 依赖处理器
    """

    def __init__(self, config, to_process, task_id):
        """
        初始化 Python 依赖处理器

        Args:
            config: 配置参数 (python_path, mirror_url)
            to_process: 待处理的依赖列表
            task_id: 任务ID
        """
        super().__init__(config_name="Python", config=config, to_process=to_process,
                         task_id=task_id)
        self.validated_config = None

    def validate_config(self, config):
        """
        验证 Python 配置

        Args:
            config: (python_path, mirror_url) 元组

        Returns:
            tuple: (is_valid: bool, validated_config or error_msg)
        """
        python_path, mirror_url = config
        is_valid, msg = validate_python_interpreter(python_path)
        if not is_valid:
            return False, msg
        # 检查镜像源是否有效（如果提供了镜像源才检查）
        if mirror_url:
            is_valid, msg = validate_python_mirror(mirror_url)
            if not is_valid:
                return False, msg
        self.validated_config = (python_path, mirror_url)
        return True, self.validated_config

    def _get_base_dir(self):
        """获取基础目录路径"""
        return str(base_dir)

    def _should_check_installed(self, item):
        """判断是否需要检查包是否已安装（总是检查）"""
        return True

    def _extract_version_for_check(self, package, specs):
        """提取版本号用于检查"""
        spec_list = specs.splitlines()

        # 尝试提取版本号
        if len(spec_list) == 1 and (
                "==" in spec_list[0] or '>=' in spec_list[0] or "<=" in spec_list[0]):
            versions = spec_list[0].split(';')[0].split(',')
            for v in versions:
                if '==' in v:
                    return v.split('==')[1].strip()
                elif '<=' in v:
                    return v.split('<=')[1].strip()
                elif '>=' in v:
                    return v.split('>=')[1].strip()
        return None

    @staticmethod
    def install_single_package(dir_id, package, specs, local_path, validated_config):
        """安装单个包"""
        python_path, mirror_url = validated_config

        spec_list = specs.splitlines()
        python_config = (False, None)

        return download_package(
            python_path=python_path,
            pkg_spec=(package, spec_list),
            mirror_url=mirror_url,
            dir_id=dir_id,
            python_config=python_config
        )
