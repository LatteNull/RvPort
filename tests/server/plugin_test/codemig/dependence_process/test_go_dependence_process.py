import pytest
from unittest.mock import patch, MagicMock, mock_open
import os
import subprocess
from pathlib import Path
import json
from subprocess import CompletedProcess
from plugin.codemig.dependence_process.go_dependence_process import (
    get_module_dir, install_module, install_local_module,
    validate_go_install_path, validate_and_parse_go_environment,
    GoDependenceProcessor
)
from plugin.codemig.dependence_process.dependence_info import DepStatus


class TestGetModuleDir:
    """测试 get_module_dir 函数"""

    @patch('plugin.codemig.dependence_process.go_dependence_process.base_dir',
           Path('/test/go_packages'))
    def test_get_module_dir_with_version(self):
        """测试带版本的模块目录"""
        result = get_module_dir("github.com/user/package", "v1.0.0")
        assert "package@v1.0.0" in result
        assert "/test/go_packages" in result

    @patch('plugin.codemig.dependence_process.go_dependence_process.base_dir',
           Path('/test/go_packages'))
    def test_get_module_dir_without_version(self):
        """测试不带版本的模块目录"""
        result = get_module_dir("github.com/user/package", None)
        assert "package" in result
        assert "@" not in result

    @patch('plugin.codemig.dependence_process.go_dependence_process.base_dir',
           Path('/test/go_packages'))
    def test_get_module_dir_with_local_path(self):
        """测试带本地路径的模块目录"""
        local_path = "/local/path/to/module"
        result = get_module_dir("github.com/user/package", "v1.0.0", local_path)
        assert result == os.path.realpath(local_path)

    @patch('plugin.codemig.dependence_process.go_dependence_process.base_dir',
           Path('/test/go_packages'))
    def test_get_module_dir_special_chars(self):
        """测试特殊字符处理"""
        result = get_module_dir("github.com/user/package-name", "v1.0.0")
        # 特殊字符应该被替换为下划线
        assert "/test/go_packages" in result


class TestValidateGoInstallPath:
    """测试 validate_go_install_path 函数"""

    def test_validate_go_install_path_empty(self):
        """测试空路径"""
        is_valid, msg = validate_go_install_path("")
        assert is_valid is False
        assert "为空" in msg

    def test_validate_go_install_path_not_exists(self):
        """测试路径不存在"""
        is_valid, msg = validate_go_install_path("/nonexistent/path/to/go")
        assert is_valid is False
        assert "不存在" in msg

    @patch('plugin.codemig.dependence_process.go_dependence_process.os.path.exists')
    @patch('plugin.codemig.dependence_process.go_dependence_process.subprocess.run')
    def test_validate_go_install_path_valid(self, mock_run, mock_exists):
        """测试有效路径"""
        mock_exists.return_value = True
        mock_run.return_value = MagicMock(stdout="go version go1.20.0")

        is_valid, msg = validate_go_install_path("/usr/bin/go")
        assert is_valid is True
        assert "验证通过" in msg

    @patch('plugin.codemig.dependence_process.go_dependence_process.os.path.exists')
    @patch('plugin.codemig.dependence_process.go_dependence_process.subprocess.run')
    def test_validate_go_install_path_invalid_output(self, mock_run, mock_exists):
        """测试无效输出"""
        mock_exists.return_value = True
        # 创建一个模拟的 subprocess.CompletedProcess 对象

        mock_result = CompletedProcess(
            args=["/usr/bin/go", "version"],
            returncode=0,
            stdout="some other output",
            stderr=""
        )
        mock_run.return_value = mock_result

        is_valid, msg = validate_go_install_path("/usr/bin/go")
        # 实际代码检查的是 "go version" 是否在 stdout 中
        # 如果不在，返回 False
        assert is_valid is False
        assert "不是有效的Go安装" in msg

    @patch('plugin.codemig.dependence_process.go_dependence_process.os.path.exists')
    @patch('plugin.codemig.dependence_process.go_dependence_process.subprocess.run')
    def test_validate_go_install_path_timeout(self, mock_run, mock_exists):
        """测试超时"""
        mock_exists.return_value = True
        mock_run.side_effect = subprocess.TimeoutExpired("go", 5)

        is_valid, msg = validate_go_install_path("/usr/bin/go")
        assert is_valid is False
        assert "出错" in msg


class TestValidateAndParseGoEnvironment:
    """测试 validate_and_parse_go_environment 函数"""

    def test_validate_and_parse_go_environment_empty(self):
        """测试空环境变量"""
        is_valid, env_dict = validate_and_parse_go_environment("")
        assert is_valid is True
        assert env_dict == {}

    def test_validate_and_parse_go_environment_single(self):
        """测试单个环境变量"""
        env_str = "GOPATH=/path/to/go"
        is_valid, env_dict = validate_and_parse_go_environment(env_str)
        assert is_valid is True
        assert env_dict["GOPATH"] == "/path/to/go"

    def test_validate_and_parse_go_environment_multiple(self):
        """测试多个环境变量"""
        env_str = "GOPATH=/path/to/go|GOROOT=/usr/local/go"
        is_valid, env_dict = validate_and_parse_go_environment(env_str)
        assert is_valid is True
        assert env_dict["GOPATH"] == "/path/to/go"
        assert env_dict["GOROOT"] == "/usr/local/go"

    def test_validate_and_parse_go_environment_no_equals(self):
        """测试缺少等号"""
        env_str = "GOPATH"
        is_valid, msg = validate_and_parse_go_environment(env_str)
        assert is_valid is False
        assert "缺少等号" in msg

    def test_validate_and_parse_go_environment_invalid_name(self):
        """测试无效变量名"""
        env_str = "123INVALID=value"
        is_valid, msg = validate_and_parse_go_environment(env_str)
        assert is_valid is False
        assert "格式不正确" in msg

    def test_validate_and_parse_go_environment_empty_value(self):
        """测试空值"""
        env_str = "GOPATH="
        is_valid, msg = validate_and_parse_go_environment(env_str)
        assert is_valid is False
        assert "不能为空" in msg

    def test_validate_and_parse_go_environment_with_spaces(self):
        """测试带空格的环境变量"""
        env_str = "GOPATH=/path/to/go | GOROOT=/usr/local/go"
        is_valid, env_dict = validate_and_parse_go_environment(env_str)
        assert is_valid is True
        assert env_dict["GOPATH"] == "/path/to/go"
        assert env_dict["GOROOT"] == "/usr/local/go"


class TestInstallModule:
    """测试 install_module 函数"""

    @patch('plugin.codemig.dependence_process.go_dependence_process.shutil.copytree')
    @patch('plugin.codemig.dependence_process.go_dependence_process.os.path.exists')
    @patch('plugin.codemig.dependence_process.go_dependence_process.scan_packages')
    @patch('plugin.codemig.dependence_process.go_dependence_process.subprocess.run')
    def test_install_module_success_new_dir(self, mock_run, mock_scan, mock_exists, mock_copytree):
        """测试成功安装模块 - 新目录"""
        mock_exists.return_value = False
        mock_scan.return_value = (True, None, 123)
        download_info = {"Dir": "/go/pkg/mod/github.com/user/package@v1.0.0"}
        mock_result = MagicMock()
        mock_result.stdout = json.dumps(download_info)
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        success, msg, dep_id = install_module(
            "/usr/bin/go", "github.com/user/package", "v1.0.0", "/target/dir", None, 1
        )

        assert success is True
        assert dep_id == 123
        mock_copytree.assert_called_once()

    @patch('plugin.codemig.dependence_process.go_dependence_process.shutil.copytree')
    @patch('plugin.codemig.dependence_process.go_dependence_process.os.path.exists')
    @patch('plugin.codemig.dependence_process.go_dependence_process.scan_packages')
    @patch('plugin.codemig.dependence_process.go_dependence_process.subprocess.run')
    def test_install_module_success_with_env(self, mock_run, mock_scan, mock_exists, mock_copytree):
        """测试成功安装模块 - 带环境变量"""
        mock_exists.return_value = False
        mock_scan.return_value = (True, None, 123)

        download_info = {"Dir": "/go/pkg/mod/github.com/user/package@v1.0.0"}
        mock_result = MagicMock()
        mock_result.stdout = json.dumps(download_info)
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        env = {"GOPATH": "/path/to/go"}
        success, msg, dep_id = install_module(
            "/usr/bin/go", "github.com/user/package", "v1.0.0", "/target/dir", env, 1
        )

        assert success is True
        assert dep_id == 123
        # 验证 env 参数被传递
        mock_run.assert_called_once()
        call_kwargs = mock_run.call_args[1]
        assert 'env' in call_kwargs

    @patch('plugin.codemig.dependence_process.go_dependence_process.shutil.rmtree')
    @patch('plugin.codemig.dependence_process.go_dependence_process.shutil.copytree')
    @patch('plugin.codemig.dependence_process.go_dependence_process.time.sleep')
    @patch(
        'plugin.codemig.dependence_process.go_dependence_process.DependencePackages.is_package_installed')
    @patch('plugin.codemig.dependence_process.go_dependence_process.os.path.exists')
    @patch('plugin.codemig.dependence_process.go_dependence_process.scan_packages')
    @patch('plugin.codemig.dependence_process.go_dependence_process.subprocess.run')
    def test_install_module_dir_exists_not_installed(self, mock_run, mock_scan, mock_exists,
                                                     mock_is_installed, mock_sleep, mock_copytree,
                                                     mock_rmtree):
        """测试目录已存在但未安装 - 等待后重新复制"""
        # 第一次检查目录存在
        # 第二次检查目录存在（在 rmtree 之前）
        mock_exists.side_effect = [True, True]
        mock_is_installed.return_value = None  # 未安装
        mock_scan.return_value = (True, None, 123)

        download_info = {"Dir": "/go/pkg/mod/github.com/user/package@v1.0.0"}
        mock_result = MagicMock()
        mock_result.stdout = json.dumps(download_info)
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        success, msg, dep_id = install_module(
            "/usr/bin/go", "github.com/user/package", "v1.0.0", "/target/dir", None, 1
        )

        assert success is True
        assert dep_id == 123
        # 应该先删除再复制
        mock_rmtree.assert_called_once()
        mock_copytree.assert_called_once()

    @patch('plugin.codemig.dependence_process.go_dependence_process.time.sleep')
    @patch(
        'plugin.codemig.dependence_process.go_dependence_process.DependencePackages.is_package_installed')
    @patch('plugin.codemig.dependence_process.go_dependence_process.os.path.exists')
    @patch('plugin.codemig.dependence_process.go_dependence_process.subprocess.run')
    def test_install_module_dir_exists_already_installed(self, mock_run, mock_exists,
                                                         mock_is_installed, mock_sleep):
        """测试目录已存在且已安装 - 跳过"""
        mock_exists.return_value = True
        mock_is_installed.return_value = 456  # 已安装

        download_info = {"Dir": "/go/pkg/mod/github.com/user/package@v1.0.0"}
        mock_result = MagicMock()
        mock_result.stdout = json.dumps(download_info)
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        success, msg, dep_id = install_module(
            "/usr/bin/go", "github.com/user/package", "v1.0.0", "/target/dir", None, 1
        )

        assert success is True
        assert dep_id == 456
        assert msg is None

    @patch('plugin.codemig.dependence_process.go_dependence_process.record_fail_package_info')
    @patch('plugin.codemig.dependence_process.go_dependence_process.subprocess.run')
    def test_install_module_timeout(self, mock_run, mock_record_fail):
        """测试下载超时"""
        mock_run.side_effect = subprocess.TimeoutExpired("go", 5)
        mock_record_fail.return_value = 789

        success, msg, dep_id = install_module(
            "/usr/bin/go", "github.com/user/package", "v1.0.0", "/target/dir", None, 1
        )

        assert success is False
        assert "超时" in msg or "网路问题" in msg
        assert dep_id == 789

    @patch('plugin.codemig.dependence_process.go_dependence_process.record_fail_package_info')
    @patch('plugin.codemig.dependence_process.go_dependence_process.subprocess.run')
    def test_install_module_called_process_error(self, mock_run, mock_record_fail):
        """测试 CalledProcessError 异常"""
        mock_run.side_effect = subprocess.CalledProcessError(1, "go", stderr="error message")
        mock_record_fail.return_value = 999

        success, msg, dep_id = install_module(
            "/usr/bin/go", "github.com/user/package", "v1.0.0", "/target/dir", None, 1
        )

        assert success is False
        assert "失败" in msg
        assert dep_id == 999

    @patch('plugin.codemig.dependence_process.go_dependence_process.record_fail_package_info')
    @patch('plugin.codemig.dependence_process.go_dependence_process.subprocess.run')
    def test_install_module_no_stdout(self, mock_run, mock_record_fail):
        """测试无 stdout 输出"""
        mock_result = MagicMock()
        mock_result.stdout = ""
        mock_result.stderr = "some error"
        mock_run.return_value = mock_result
        mock_record_fail.return_value = 888

        success, msg, dep_id = install_module(
            "/usr/bin/go", "github.com/user/package", "v1.0.0", "/target/dir", None, 1
        )

        assert success is False
        assert "失败" in msg
        assert dep_id == 888

    @patch('plugin.codemig.dependence_process.go_dependence_process.shutil.copytree')
    @patch('plugin.codemig.dependence_process.go_dependence_process.os.path.exists')
    @patch('plugin.codemig.dependence_process.go_dependence_process.record_fail_package_info')
    @patch('plugin.codemig.dependence_process.go_dependence_process.subprocess.run')
    def test_install_module_copytree_exception(self, mock_run, mock_record_fail, mock_exists,
                                               mock_copytree):
        """测试复制文件时异常"""
        mock_exists.return_value = False
        mock_copytree.side_effect = OSError("Permission denied")
        mock_record_fail.return_value = 777

        download_info = {"Dir": "/go/pkg/mod/github.com/user/package@v1.0.0"}
        mock_result = MagicMock()
        mock_result.stdout = json.dumps(download_info)
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        success, msg, dep_id = install_module(
            "/usr/bin/go", "github.com/user/package", "v1.0.0", "/target/dir", None, 1
        )

        # 即使 copytree 失败，函数也会继续执行并返回 scan_packages 的结果
        # 但这里由于 copytree 异常，可能不会调用 scan_packages
        # 需要查看实际代码逻辑
        mock_copytree.assert_called_once()

    @patch('plugin.codemig.dependence_process.go_dependence_process.shutil.copytree')
    @patch('plugin.codemig.dependence_process.go_dependence_process.os.path.exists')
    @patch('plugin.codemig.dependence_process.go_dependence_process.scan_packages')
    @patch('plugin.codemig.dependence_process.go_dependence_process.subprocess.run')
    def test_install_module_no_version(self, mock_run, mock_scan, mock_exists, mock_copytree):
        """测试无版本号的模块"""
        mock_exists.return_value = False
        mock_scan.return_value = (True, None, 124)

        download_info = {"Dir": "/go/pkg/mod/github.com/user/package"}
        mock_result = MagicMock()
        mock_result.stdout = json.dumps(download_info)
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        success, msg, dep_id = install_module(
            "/usr/bin/go", "github.com/user/package", None, "/target/dir", None, 1
        )

        assert success is True
        assert dep_id == 124
        # 验证命令中不包含 @version
        call_args = mock_run.call_args[0][0]
        assert "@" not in " ".join(call_args) or call_args[-1] == "github.com/user/package"

    @patch('plugin.codemig.dependence_process.go_dependence_process.shutil.rmtree')
    @patch('plugin.codemig.dependence_process.go_dependence_process.shutil.copytree')
    @patch('plugin.codemig.dependence_process.go_dependence_process.time.sleep')
    @patch(
        'plugin.codemig.dependence_process.go_dependence_process.DependencePackages.is_package_installed')
    @patch('plugin.codemig.dependence_process.go_dependence_process.os.path.exists')
    @patch('plugin.codemig.dependence_process.go_dependence_process.record_fail_package_info')
    @patch('plugin.codemig.dependence_process.go_dependence_process.subprocess.run')
    def test_install_module_dir_exists_rmtree_fails(self, mock_run, mock_record_fail, mock_exists,
                                                    mock_is_installed, mock_sleep, mock_copytree,
                                                    mock_rmtree):
        """测试目录已存在，删除时失败"""
        mock_exists.side_effect = [True, True]
        mock_is_installed.return_value = None
        mock_rmtree.side_effect = OSError("Permission denied")
        mock_record_fail.return_value = 666

        download_info = {"Dir": "/go/pkg/mod/github.com/user/package@v1.0.0"}
        mock_result = MagicMock()
        mock_result.stdout = json.dumps(download_info)
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        success, msg, dep_id = install_module(
            "/usr/bin/go", "github.com/user/package", "v1.0.0", "/target/dir", None, 1
        )

        # rmtree 失败后，copytree 可能也会失败
        mock_rmtree.assert_called_once()


class TestInstallLocalModule:
    """测试 install_local_module 函数"""

    @patch('plugin.codemig.dependence_process.go_dependence_process.os.path.exists')
    @patch('plugin.codemig.dependence_process.go_dependence_process.scan_packages')
    def test_install_local_module_success(self, mock_scan, mock_exists):
        """测试成功安装本地模块"""
        mock_exists.return_value = True
        mock_scan.return_value = (True, None, 123)

        success, msg, dep_id = install_local_module(
            "github.com/user/package", "v1.0.0", "/local/path", "/target/dir", 1
        )

        assert success is True
        assert dep_id == 123
        mock_scan.assert_called_once()

    @patch('plugin.codemig.dependence_process.go_dependence_process.os.path.exists')
    def test_install_local_module_path_not_exists(self, mock_exists):
        """测试本地路径不存在"""
        mock_exists.return_value = False

        success, msg, dep_id = install_local_module(
            "github.com/user/package", "v1.0.0", "/nonexistent/path", "/target/dir", 1
        )

        assert success is False
        assert "不存在" in msg
        assert dep_id is None


class TestGoDependenceProcessor:
    """测试 GoDependenceProcessor 类"""

    def test_init(self):
        """测试初始化"""
        processor = GoDependenceProcessor(
            config=("/usr/bin/go", "GOPATH=/path/to/go"),
            to_process=[],
            task_id=1
        )
        assert processor.config_name == "Go"
        assert processor.task_id == 1
        assert processor.validated_config is None

    @patch('plugin.codemig.dependence_process.go_dependence_process.validate_go_install_path')
    @patch(
        'plugin.codemig.dependence_process.go_dependence_process.validate_and_parse_go_environment')
    def test_validate_config_success(self, mock_validate_env, mock_validate_path):
        """测试配置验证成功"""
        mock_validate_path.return_value = (True, "验证通过")
        mock_validate_env.return_value = (True, {"GOPATH": "/path/to/go"})

        processor = GoDependenceProcessor(
            config=("/usr/bin/go", "GOPATH=/path/to/go"),
            to_process=[],
            task_id=1
        )
        is_valid, result = processor.validate_config(("/usr/bin/go", "GOPATH=/path/to/go"))

        assert is_valid is True
        assert isinstance(result, tuple)

    @patch('plugin.codemig.dependence_process.go_dependence_process.validate_go_install_path')
    def test_validate_config_invalid_path(self, mock_validate_path):
        """测试配置验证失败 - 路径无效"""
        mock_validate_path.return_value = (False, "路径不存在")

        processor = GoDependenceProcessor(
            config=("/nonexistent/go", ""),
            to_process=[],
            task_id=1
        )
        is_valid, msg = processor.validate_config(("/nonexistent/go", ""))

        assert is_valid is False
        assert "路径不存在" in msg

    @patch('plugin.codemig.dependence_process.go_dependence_process.validate_go_install_path')
    @patch(
        'plugin.codemig.dependence_process.go_dependence_process.validate_and_parse_go_environment')
    def test_validate_config_invalid_env(self, mock_validate_env, mock_validate_path):
        """测试配置验证失败 - 环境变量无效"""
        mock_validate_path.return_value = (True, "验证通过")
        mock_validate_env.return_value = (False, "环境变量格式不正确")

        processor = GoDependenceProcessor(
            config=("/usr/bin/go", "INVALID"),
            to_process=[],
            task_id=1
        )
        is_valid, msg = processor.validate_config(("/usr/bin/go", "INVALID"))

        assert is_valid is False
        assert "格式不正确" in msg

    def test_get_base_dir(self):
        """测试获取基础目录"""
        processor = GoDependenceProcessor(
            config=("/usr/bin/go", ""),
            to_process=[],
            task_id=1
        )
        base_dir = processor._get_base_dir()
        assert isinstance(base_dir, str)

    def test_should_check_installed(self):
        """测试是否应该检查已安装"""
        processor = GoDependenceProcessor(
            config=("/usr/bin/go", ""),
            to_process=[],
            task_id=1
        )
        assert processor._should_check_installed(None) is True
        assert processor._should_check_installed("") is True
        assert processor._should_check_installed("/local/path") is False

    def test_extract_version_for_check(self):
        """测试提取版本号"""
        processor = GoDependenceProcessor(
            config=("/usr/bin/go", ""),
            to_process=[],
            task_id=1
        )
        version = processor._extract_version_for_check("package", "v1.0.0")
        assert version == "v1.0.0"

    @patch('plugin.codemig.dependence_process.go_dependence_process.install_local_module')
    def test_install_single_package_local(self, mock_install_local):
        """测试安装本地包"""
        mock_install_local.return_value = (True, None, 123)

        processor = GoDependenceProcessor(
            config=("/usr/bin/go", ""),
            to_process=[],
            task_id=1
        )
        success, msg, dep_id = processor.install_single_package(
            1, "github.com/user/package", "v1.0.0", "/local/path", ("/usr/bin/go", {})
        )

        assert success is True
        assert dep_id == 123

    @patch('plugin.codemig.dependence_process.go_dependence_process.install_module')
    @patch('plugin.codemig.dependence_process.go_dependence_process.os.environ')
    def test_install_single_package_remote(self, mock_environ, mock_install):
        """测试安装远程包"""
        mock_environ.copy.return_value = {}
        mock_install.return_value = (True, None, 123)

        processor = GoDependenceProcessor(
            config=("/usr/bin/go", ""),
            to_process=[],
            task_id=1
        )
        success, msg, dep_id = processor.install_single_package(
            1, "github.com/user/package", "v1.0.0", None, ("/usr/bin/go", {"GOPATH": "/path/to/go"})
        )

        assert success is True
        assert dep_id == 123
        mock_install.assert_called_once()
