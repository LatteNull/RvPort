import pytest
from unittest.mock import patch, MagicMock, mock_open
import os
import subprocess
from pathlib import Path
import json
from plugin.codemig.dependence_process.python_dependence_process import (
    get_package_dir, get_tmp_dir, get_pip_config, get_proxy_from_pip_config,
    download_with_proxy, download_package_source, extract_version_advanced,
    remove_pkg_advanced, download_package, validate_python_interpreter,
    validate_python_mirror, PythonDependenceProcessor, DOWNLOAD_TIMEOUT
)


class TestGetPackageDir:
    """测试 get_package_dir 函数"""

    @patch('plugin.codemig.dependence_process.python_dependence_process.base_dir', Path('/test/python_packages'))
    def test_get_package_dir_with_version(self):
        """测试带版本的包目录"""
        result = get_package_dir("test-package", "1.0.0")
        assert "test_package" in result
        assert "1.0.0" in result
        assert "/test/python_packages" in result

    @patch('plugin.codemig.dependence_process.python_dependence_process.base_dir', Path('/test/python_packages'))
    def test_get_package_dir_without_version(self):
        """测试不带版本的包目录"""
        result = get_package_dir("test-package", "")
        assert "test_package" in result
        assert "/test/python_packages" in result

    @patch('plugin.codemig.dependence_process.python_dependence_process.base_dir', Path('/test/python_packages'))
    def test_get_package_dir_special_chars(self):
        """测试特殊字符处理"""
        result = get_package_dir("test.package-name", "1.0.0")
        # 特殊字符应该被替换为下划线
        assert "test_package_name" in result


class TestGetTmpDir:
    """测试 get_tmp_dir 函数"""

    @patch('plugin.codemig.dependence_process.python_dependence_process.base_dir', Path('/test/python_packages'))
    def test_get_tmp_dir(self):
        """测试获取临时目录"""
        result = get_tmp_dir()
        assert "/test/python_packages" in result
        assert len(os.path.basename(result)) == 8  # 随机文件名长度为8


class TestGetPipConfig:
    """测试 get_pip_config 函数"""

    @patch('plugin.codemig.dependence_process.python_dependence_process.subprocess.run')
    def test_get_pip_config_success(self, mock_run):
        """测试成功获取pip配置"""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="global.index-url=https://pypi.org/simple/\nglobal.timeout=60"
        )
        
        config = get_pip_config("/usr/bin/python3")
        assert "global.index-url" in config
        assert config["global.index-url"] == "https://pypi.org/simple/"

    @patch('plugin.codemig.dependence_process.python_dependence_process.subprocess.run')
    def test_get_pip_config_failure(self, mock_run):
        """测试获取pip配置失败"""
        mock_run.return_value = MagicMock(returncode=1, stderr="Error")
        
        config = get_pip_config("/usr/bin/python3")
        assert config == {}

    @patch('plugin.codemig.dependence_process.python_dependence_process.subprocess.run')
    def test_get_pip_config_timeout(self, mock_run):
        """测试获取pip配置超时"""
        mock_run.side_effect = subprocess.TimeoutExpired("python", 5)
        
        config = get_pip_config("/usr/bin/python3")
        assert config == {}


class TestGetProxyFromPipConfig:
    """测试 get_proxy_from_pip_config 函数"""

    def test_get_proxy_from_pip_config_with_config(self):
        """测试从配置中获取代理"""
        python_config = (True, {"http": "http://proxy:8080", "https": "https://proxy:8080"})
        proxy = get_proxy_from_pip_config("/usr/bin/python3", python_config)
        assert proxy["http"] == "http://proxy:8080"
        assert proxy["https"] == "https://proxy:8080"

    @patch('plugin.codemig.dependence_process.python_dependence_process.get_pip_config')
    def test_get_proxy_from_pip_config_from_pip(self, mock_get_config):
        """测试从pip配置中获取代理"""
        mock_get_config.return_value = {
            "global.http-proxy": "http://proxy:8080",
            "global.https-proxy": "https://proxy:8080"
        }
        
        proxy = get_proxy_from_pip_config("/usr/bin/python3", (False, None))
        assert "http" in proxy
        assert "https" in proxy


class TestExtractVersionAdvanced:
    """测试 extract_version_advanced 函数"""

    def test_extract_version_advanced_standard(self):
        """测试标准版本号格式"""
        version = extract_version_advanced("package-1.2.3.tar.gz")
        assert version == "1.2.3"

    def test_extract_version_advanced_with_prefix(self):
        """测试带前缀的版本号"""
        version = extract_version_advanced("package-v1.2.3.tar.gz")
        assert version == "1.2.3"

    def test_extract_version_advanced_two_part(self):
        """测试两部分版本号"""
        version = extract_version_advanced("package-1.2.tar.gz")
        assert version == "1.2"

    def test_extract_version_advanced_prerelease(self):
        """测试预发布版本"""
        version = extract_version_advanced("package-1.2.3-alpha.tar.gz")
        assert version == "1.2.3-alpha"

    def test_extract_version_advanced_no_version(self):
        """测试无版本号"""
        version = extract_version_advanced("package.tar.gz")
        assert version is None


class TestRemovePkgAdvanced:
    """测试 remove_pkg_advanced 函数"""

    def test_remove_pkg_advanced_equals(self):
        """测试等号分隔符"""
        result = remove_pkg_advanced("package==1.0.0", "package")
        assert result == "1.0.0"

    def test_remove_pkg_advanced_greater_equal(self):
        """测试大于等于分隔符"""
        result = remove_pkg_advanced("package>=1.0.0", "package")
        assert result == "1.0.0"

    def test_remove_pkg_advanced_space(self):
        """测试空格分隔符"""
        result = remove_pkg_advanced("package 1.0.0", "package")
        assert result == "1.0.0"

    def test_remove_pkg_advanced_multiple(self):
        """测试多个分隔符"""
        result = remove_pkg_advanced("package>=1.0.0,<2.0.0", "package")
        assert "1.0.0" in result or result == ">=1.0.0,<2.0.0"


class TestValidatePythonInterpreter:
    """测试 validate_python_interpreter 函数"""

    def test_validate_python_interpreter_empty(self):
        """测试空路径"""
        is_valid, msg = validate_python_interpreter("")
        assert is_valid is False
        assert "未配置" in msg

    def test_validate_python_interpreter_not_exists(self):
        """测试路径不存在"""
        is_valid, msg = validate_python_interpreter("/nonexistent/path/to/python")
        assert is_valid is False
        assert "不存在" in msg

    @patch('plugin.codemig.dependence_process.python_dependence_process.os.path.exists')
    @patch('plugin.codemig.dependence_process.python_dependence_process.os.path.isfile')
    @patch('plugin.codemig.dependence_process.python_dependence_process.os.access')
    @patch('plugin.codemig.dependence_process.python_dependence_process.subprocess.run')
    def test_validate_python_interpreter_valid(self, mock_run, mock_access, mock_isfile, mock_exists):
        """测试有效解释器"""
        mock_exists.return_value = True
        mock_isfile.return_value = True
        mock_access.return_value = True
        mock_run.return_value = MagicMock(stdout="Python 3.9.0")
        
        is_valid, msg = validate_python_interpreter("/usr/bin/python3")
        assert is_valid is True
        assert "验证通过" in msg

    @patch('plugin.codemig.dependence_process.python_dependence_process.os.path.exists')
    @patch('plugin.codemig.dependence_process.python_dependence_process.os.path.isfile')
    @patch('plugin.codemig.dependence_process.python_dependence_process.os.access')
    @patch('plugin.codemig.dependence_process.python_dependence_process.subprocess.run')
    def test_validate_python_interpreter_invalid_output(self, mock_run, mock_access, mock_isfile, mock_exists):
        """测试无效输出"""
        mock_exists.return_value = True
        mock_isfile.return_value = True
        mock_access.return_value = True
        mock_run.return_value = MagicMock(stdout="not python")
        
        is_valid, msg = validate_python_interpreter("/usr/bin/python3")
        assert is_valid is False
        assert "不是有效的Python解释器" in msg

    @patch('plugin.codemig.dependence_process.python_dependence_process.os.path.exists')
    @patch('plugin.codemig.dependence_process.python_dependence_process.os.path.isfile')
    def test_validate_python_interpreter_not_file(self, mock_isfile, mock_exists):
        """测试不是文件"""
        mock_exists.return_value = True
        mock_isfile.return_value = False
        
        is_valid, msg = validate_python_interpreter("/usr/bin/python3")
        assert is_valid is False
        assert "不是文件" in msg

    @patch('plugin.codemig.dependence_process.python_dependence_process.os.path.exists')
    @patch('plugin.codemig.dependence_process.python_dependence_process.os.path.isfile')
    @patch('plugin.codemig.dependence_process.python_dependence_process.os.access')
    def test_validate_python_interpreter_not_executable(self, mock_access, mock_isfile, mock_exists):
        """测试不可执行"""
        mock_exists.return_value = True
        mock_isfile.return_value = True
        mock_access.return_value = False
        
        is_valid, msg = validate_python_interpreter("/usr/bin/python3")
        assert is_valid is False
        assert "不可执行" in msg


class TestValidatePythonMirror:
    """测试 validate_python_mirror 函数"""

    def test_validate_python_mirror_invalid_url(self):
        """测试无效URL"""
        is_valid, msg = validate_python_mirror("invalid-url")
        assert is_valid is False
        assert "格式不正确" in msg

    def test_validate_python_mirror_invalid_scheme(self):
        """测试无效协议"""
        is_valid, msg = validate_python_mirror("ftp://example.com")
        assert is_valid is False
        assert "协议必须是http或https" in msg

    @patch('requests.get')
    def test_validate_python_mirror_success(self, mock_get):
        """测试成功验证镜像源"""
        mock_get.return_value = MagicMock(status_code=200)
        
        is_valid, msg = validate_python_mirror("https://pypi.org/simple/")
        assert is_valid is True
        assert "验证通过" in msg

    @patch('requests.get')
    def test_validate_python_mirror_failure(self, mock_get):
        """测试镜像源不可达"""
        mock_get.return_value = MagicMock(status_code=404)
        
        is_valid, msg = validate_python_mirror("https://pypi.org/simple/")
        assert is_valid is False
        assert "响应异常" in msg

    @patch('requests.get')
    def test_validate_python_mirror_request_exception(self, mock_get):
        """测试请求异常"""
        from requests import RequestException
        mock_get.side_effect = RequestException("Connection error")
        
        is_valid, msg = validate_python_mirror("https://pypi.org/simple/")
        assert is_valid is False
        assert "连接测试失败" in msg


class TestDownloadPackage:
    """测试 download_package 函数"""

    @patch('plugin.codemig.dependence_process.python_dependence_process.shutil.rmtree')
    @patch('plugin.codemig.dependence_process.python_dependence_process.os.rename')
    @patch('plugin.codemig.dependence_process.python_dependence_process.extract_file')
    @patch('plugin.codemig.dependence_process.python_dependence_process.os.remove')
    @patch('plugin.codemig.dependence_process.python_dependence_process.os.path.isdir')
    @patch('plugin.codemig.dependence_process.python_dependence_process.os.listdir')
    @patch('plugin.codemig.dependence_process.python_dependence_process.os.path.exists')
    @patch('plugin.codemig.dependence_process.python_dependence_process.scan_packages')
    @patch('plugin.codemig.dependence_process.python_dependence_process.download_package_source')
    @patch('plugin.codemig.dependence_process.python_dependence_process.DependencePackages.is_package_installed')
    @patch('plugin.codemig.dependence_process.python_dependence_process.subprocess.run')
    @patch('plugin.codemig.dependence_process.python_dependence_process.os.makedirs')
    @patch('plugin.codemig.dependence_process.python_dependence_process.get_tmp_dir')
    def test_download_package_success(self, mock_get_tmp_dir, mock_makedirs, mock_run, 
                                       mock_is_installed, mock_download_source, mock_scan,
                                       mock_exists, mock_listdir, mock_isdir, mock_remove,
                                       mock_extract, mock_rename, mock_rmtree):
        """测试成功下载和安装包"""

        
        # 设置临时目录
        tmp_dir = "/tmp/test_pkg_12345"
        mock_get_tmp_dir.return_value = tmp_dir
        
        # 模拟查询命令 - 包未安装（查询失败）
        mock_run.return_value = MagicMock(returncode=1)
        
        # 模拟下载成功
        mock_download_source.return_value = (True, None)
        
        # 模拟临时目录存在（在 finally 中检查）
        # versioned_dir 不存在
        mock_exists.side_effect = lambda path: path == tmp_dir
        
        # 模拟临时目录中的文件
        mock_listdir.side_effect = [
            ["test-package-1.0.0.tar.gz"],  # 第一次列出压缩文件
            ["test-package-1.0.0"]  # 第二次列出解压后的目录
        ]
        mock_isdir.return_value = True
        
        # 模拟扫描包成功
        mock_scan.return_value = (True, None, 123)
        
        success, msg, dep_id = download_package(
            "/usr/bin/python3",
            ("test-package", ["==1.0.0"]),
            None,
            1,
            (False, None)
        )
        
        assert success is True
        assert dep_id == 123
        mock_download_source.assert_called_once()
        mock_extract.assert_called_once()
        mock_rmtree.assert_called_once_with(tmp_dir)  # 清理临时目录

    @patch('plugin.codemig.dependence_process.python_dependence_process.shutil.rmtree')
    @patch('plugin.codemig.dependence_process.python_dependence_process.os.path.exists')
    @patch('plugin.codemig.dependence_process.python_dependence_process.os.makedirs')
    @patch('plugin.codemig.dependence_process.python_dependence_process.get_tmp_dir')
    @patch('plugin.codemig.dependence_process.python_dependence_process.DependencePackages.is_package_installed')
    @patch('plugin.codemig.dependence_process.python_dependence_process.subprocess.run')
    def test_download_package_already_installed(self, mock_run, mock_is_installed, 
                                                 mock_get_tmp_dir, mock_makedirs, mock_exists, mock_rmtree):
        """测试包已安装 - 跳过下载"""
       
        tmp_dir = "/tmp/test_pkg_12345"
        mock_get_tmp_dir.return_value = tmp_dir
        
        # 模拟查询命令返回已安装的包
        query_result = {
            "install": [{
                "metadata": {"version": "1.0.0"}
            }]
        }
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps(query_result)
        )
        mock_is_installed.return_value = 456  # 已安装
        # 在 finally 中检查 tmp_dir 是否存在
        mock_exists.return_value = True
        
        success, msg, dep_id = download_package(
            "/usr/bin/python3",
            ("test-package", ["==1.0.0"]),
            None,
            1,
            (False, None)
        )
        
        assert success is True
        assert dep_id == 456
        assert msg is None
        # 注意：查询阶段返回后，finally 块会执行（finally 在第二个 try 块中）
        # 但由于查询阶段在第一个 try 块中返回，不会执行第二个 try 的 finally
        # 实际代码中，finally 在第二个 try 块中，所以查询阶段返回时不会执行
        # 但为了测试完整性，我们验证函数正确返回即可
        # mock_rmtree 可能不会被调用，因为查询阶段就返回了

    @patch('plugin.codemig.dependence_process.python_dependence_process.shutil.rmtree')
    @patch('plugin.codemig.dependence_process.python_dependence_process.os.path.exists')
    @patch('plugin.codemig.dependence_process.python_dependence_process.record_fail_package_info')
    @patch('plugin.codemig.dependence_process.python_dependence_process.download_package_source')
    @patch('plugin.codemig.dependence_process.python_dependence_process.os.makedirs')
    @patch('plugin.codemig.dependence_process.python_dependence_process.get_tmp_dir')
    @patch('plugin.codemig.dependence_process.python_dependence_process.subprocess.run')
    def test_download_package_download_failed(self, mock_run, mock_get_tmp_dir, mock_makedirs,
                                               mock_download_source, mock_record_fail, mock_exists, mock_rmtree):
        """测试下载失败"""
       
        tmp_dir = "/tmp/test_pkg_12345"
        mock_get_tmp_dir.return_value = tmp_dir
        mock_run.return_value = MagicMock(returncode=1)  # 查询失败
        mock_download_source.return_value = (False, "Download failed")
        mock_record_fail.return_value = 789
        mock_exists.return_value = lambda path: path == tmp_dir
        
        success, msg, dep_id = download_package(
            "/usr/bin/python3",
            ("test-package", ["==1.0.0"]),
            None,
            1,
            (False, None)
        )
        
        assert success is False
        assert "Download failed" in msg
        assert dep_id == 789
        mock_rmtree.assert_called_once_with(tmp_dir)

    @patch('plugin.codemig.dependence_process.python_dependence_process.shutil.rmtree')
    @patch('plugin.codemig.dependence_process.python_dependence_process.os.path.exists')
    @patch('plugin.codemig.dependence_process.python_dependence_process.os.listdir')
    @patch('plugin.codemig.dependence_process.python_dependence_process.download_package_source')
    @patch('plugin.codemig.dependence_process.python_dependence_process.os.makedirs')
    @patch('plugin.codemig.dependence_process.python_dependence_process.get_tmp_dir')
    @patch('plugin.codemig.dependence_process.python_dependence_process.subprocess.run')
    def test_download_package_no_compress_file(self, mock_run, mock_get_tmp_dir, mock_makedirs,
                                                mock_download_source, mock_listdir, mock_exists, mock_rmtree):
        """测试无压缩文件"""
       
        tmp_dir = "/tmp/test_pkg_12345"
        mock_get_tmp_dir.return_value = tmp_dir
        mock_run.return_value = MagicMock(returncode=1)
        mock_download_source.return_value = (True, "some output")  # 提供 error_msg
        mock_listdir.return_value = [".", ".."]  # 只有 . 和 ..
        mock_exists.return_value = True  # tmp_dir 存在
        
        success, msg, dep_id = download_package(
            "/usr/bin/python3",
            ("test-package", ["==1.0.0"]),
            None,
            1,
            (False, None)
        )
        
        assert success is False
        assert dep_id is None
        mock_rmtree.assert_called_once_with(tmp_dir)

    @patch('plugin.codemig.dependence_process.python_dependence_process.shutil.rmtree')
    @patch('plugin.codemig.dependence_process.python_dependence_process.os.remove')
    @patch('plugin.codemig.dependence_process.python_dependence_process.extract_file')
    @patch('plugin.codemig.dependence_process.python_dependence_process.os.path.isdir')
    @patch('plugin.codemig.dependence_process.python_dependence_process.os.listdir')
    @patch('plugin.codemig.dependence_process.python_dependence_process.os.path.exists')
    @patch('plugin.codemig.dependence_process.python_dependence_process.download_package_source')
    @patch('plugin.codemig.dependence_process.python_dependence_process.os.makedirs')
    @patch('plugin.codemig.dependence_process.python_dependence_process.get_tmp_dir')
    @patch('plugin.codemig.dependence_process.python_dependence_process.subprocess.run')
    def test_download_package_no_uncompress_dir(self, mock_run, mock_get_tmp_dir, mock_makedirs,
                                                 mock_download_source, mock_exists, mock_listdir,
                                                 mock_isdir, mock_extract, mock_remove, mock_rmtree):
        """测试无解压目录"""        
        tmp_dir = "/tmp/test_pkg_12345"
        mock_get_tmp_dir.return_value = tmp_dir
        mock_run.return_value = MagicMock(returncode=1)
        mock_download_source.return_value = (True, None)
        mock_listdir.side_effect = [
            ["test-package-1.0.0.tar.gz"],  # 第一次列出压缩文件
            []  # 第二次列出解压后的目录（空）
        ]
        mock_isdir.return_value = False
        mock_exists.side_effect = lambda path: path == tmp_dir
        
        success, msg, dep_id = download_package(
            "/usr/bin/python3",
            ("test-package", ["==1.0.0"]),
            None,
            1,
            (False, None)
        )
        
        assert success is False
        assert "cannot find uncompress dir" in msg
        assert dep_id is None
        mock_rmtree.assert_called_once_with(tmp_dir)

    @patch('plugin.codemig.dependence_process.python_dependence_process.shutil.rmtree')
    @patch('plugin.codemig.dependence_process.python_dependence_process.os.rename')
    @patch('plugin.codemig.dependence_process.python_dependence_process.extract_file')
    @patch('plugin.codemig.dependence_process.python_dependence_process.os.remove')
    @patch('plugin.codemig.dependence_process.python_dependence_process.os.path.isdir')
    @patch('plugin.codemig.dependence_process.python_dependence_process.os.listdir')
    @patch('plugin.codemig.dependence_process.python_dependence_process.os.path.exists')
    @patch('plugin.codemig.dependence_process.python_dependence_process.scan_packages')
    @patch('plugin.codemig.dependence_process.python_dependence_process.download_package_source')
    @patch('plugin.codemig.dependence_process.python_dependence_process.DependencePackages.is_package_installed')
    @patch('plugin.codemig.dependence_process.python_dependence_process.extract_version_advanced')
    @patch('plugin.codemig.dependence_process.python_dependence_process.get_package_dir')
    @patch('plugin.codemig.dependence_process.python_dependence_process.os.makedirs')
    @patch('plugin.codemig.dependence_process.python_dependence_process.get_tmp_dir')
    @patch('plugin.codemig.dependence_process.python_dependence_process.subprocess.run')
    def test_download_package_version_dir_exists_installed(self, mock_run, mock_get_tmp_dir, mock_makedirs,
                                                          mock_get_package_dir, mock_extract_version,
                                                          mock_is_installed, mock_download_source, mock_scan,
                                                          mock_exists, mock_listdir, mock_isdir, mock_remove,
                                                          mock_extract, mock_rename, mock_rmtree):
        """测试版本目录已存在且已安装"""
       
        tmp_dir = "/tmp/test_pkg_12345"
        versioned_dir = "/test/python_packages/test_package_1.0.0"
        mock_get_tmp_dir.return_value = tmp_dir
        mock_run.return_value = MagicMock(returncode=1)
        mock_download_source.return_value = (True, None)
        mock_listdir.side_effect = [
            ["test-package-1.0.0.tar.gz"],
            ["test-package-1.0.0"]
        ]
        mock_isdir.return_value = True
        mock_extract_version.return_value = "1.0.0"  # 提取版本号
        mock_get_package_dir.return_value = versioned_dir
        # 第一次检查 versioned_dir 存在，第二次也存在，tmp_dir 存在
        mock_exists.side_effect = lambda path: path == tmp_dir or path == versioned_dir
        mock_is_installed.return_value = 999  # 已安装
        
        success, msg, dep_id = download_package(
            "/usr/bin/python3",
            ("test-package", ["==1.0.0"]),
            None,
            1,
            (False, None)
        )
        
        assert success is True
        assert dep_id == 999
        assert msg is None
        mock_rmtree.assert_called_once_with(tmp_dir)

    @patch('plugin.codemig.dependence_process.python_dependence_process.shutil.rmtree')
    @patch('plugin.codemig.dependence_process.python_dependence_process.os.rename')
    @patch('plugin.codemig.dependence_process.python_dependence_process.extract_file')
    @patch('plugin.codemig.dependence_process.python_dependence_process.os.remove')
    @patch('plugin.codemig.dependence_process.python_dependence_process.os.path.isdir')
    @patch('plugin.codemig.dependence_process.python_dependence_process.os.listdir')
    @patch('plugin.codemig.dependence_process.python_dependence_process.os.path.exists')
    @patch('plugin.codemig.dependence_process.python_dependence_process.scan_packages')
    @patch('plugin.codemig.dependence_process.python_dependence_process.download_package_source')
    @patch('plugin.codemig.dependence_process.python_dependence_process.DependencePackages.is_package_installed')
    @patch('plugin.codemig.dependence_process.python_dependence_process.os.makedirs')
    @patch('plugin.codemig.dependence_process.python_dependence_process.get_tmp_dir')
    @patch('plugin.codemig.dependence_process.python_dependence_process.subprocess.run')
    def test_download_package_version_dir_exists_not_installed(self, mock_run, mock_get_tmp_dir, mock_makedirs,
                                                               mock_is_installed, mock_download_source, mock_scan,
                                                               mock_exists, mock_listdir, mock_isdir, mock_remove,
                                                               mock_extract, mock_rename, mock_rmtree):
        """测试版本目录已存在但未安装 - 删除后重新安装"""
       
        tmp_dir = "/tmp/test_pkg_12345"
        versioned_dir = "/test/python_packages/test_package_1.0.0"
        mock_get_tmp_dir.return_value = tmp_dir
        mock_run.return_value = MagicMock(returncode=1)
        mock_download_source.return_value = (True, None)
        mock_listdir.side_effect = [
            ["test-package-1.0.0.tar.gz"],
            ["test-package-1.0.0"]
        ]
        mock_isdir.return_value = True
        mock_exists.side_effect = lambda path: path == tmp_dir or path == versioned_dir
        mock_is_installed.side_effect = [None, None]  # 未安装
        mock_scan.return_value = (True, None, 111)
        
        success, msg, dep_id = download_package(
            "/usr/bin/python3",
            ("test-package", ["==1.0.0"]),
            None,
            1,
            (False, None)
        )
        
        assert success is True
        assert dep_id == 111
        # 应该删除已存在的版本目录和临时目录
        assert mock_rmtree.call_count >= 1
        # 最后应该清理临时目录
        mock_rmtree.assert_any_call(tmp_dir)

    @patch('plugin.codemig.dependence_process.python_dependence_process.shutil.rmtree')
    @patch('plugin.codemig.dependence_process.python_dependence_process.os.path.exists')
    @patch('plugin.codemig.dependence_process.python_dependence_process.record_fail_package_info')
    @patch('plugin.codemig.dependence_process.python_dependence_process.download_package_source')
    @patch('plugin.codemig.dependence_process.python_dependence_process.os.makedirs')
    @patch('plugin.codemig.dependence_process.python_dependence_process.get_tmp_dir')
    @patch('plugin.codemig.dependence_process.python_dependence_process.subprocess.run')
    def test_download_package_called_process_error(self, mock_run, mock_get_tmp_dir, mock_makedirs,
                                                   mock_download_source, mock_record_fail, mock_exists, mock_rmtree):
        """测试 CalledProcessError 异常"""
       
        tmp_dir = "/tmp/test_pkg_12345"
        mock_get_tmp_dir.return_value = tmp_dir
        mock_run.return_value = MagicMock(returncode=1)  # 查询失败
        mock_download_source.side_effect = subprocess.CalledProcessError(1, "pip", stderr="error")
        mock_record_fail.return_value = 888
        mock_exists.return_value = lambda path: path == tmp_dir
        
        success, msg, dep_id = download_package(
            "/usr/bin/python3",
            ("test-package", ["==1.0.0"]),
            None,
            1,
            (False, None)
        )
        
        assert success is False
        assert "失败" in msg
        assert dep_id == 888
        mock_rmtree.assert_called_once_with(tmp_dir)

    @patch('plugin.codemig.dependence_process.python_dependence_process.shutil.rmtree')
    @patch('plugin.codemig.dependence_process.python_dependence_process.os.rename')
    @patch('plugin.codemig.dependence_process.python_dependence_process.extract_file')
    @patch('plugin.codemig.dependence_process.python_dependence_process.os.remove')
    @patch('plugin.codemig.dependence_process.python_dependence_process.os.path.isdir')
    @patch('plugin.codemig.dependence_process.python_dependence_process.os.listdir')
    @patch('plugin.codemig.dependence_process.python_dependence_process.os.path.exists')
    @patch('plugin.codemig.dependence_process.python_dependence_process.scan_packages')
    @patch('plugin.codemig.dependence_process.python_dependence_process.download_package_source')
    @patch('plugin.codemig.dependence_process.python_dependence_process.os.makedirs')
    @patch('plugin.codemig.dependence_process.python_dependence_process.get_tmp_dir')
    @patch('plugin.codemig.dependence_process.python_dependence_process.subprocess.run')
    def test_download_package_with_mirror(self, mock_run, mock_get_tmp_dir, mock_makedirs,
                                          mock_download_source, mock_scan, mock_exists, mock_listdir,
                                          mock_isdir, mock_remove, mock_extract, mock_rename, mock_rmtree):
        """测试带镜像源的下载"""        
        tmp_dir = "/tmp/test_pkg_12345"
        mock_get_tmp_dir.return_value = tmp_dir
        mock_run.return_value = MagicMock(returncode=1)
        mock_download_source.return_value = (True, None)
        mock_listdir.side_effect = [
            ["test-package-1.0.0.tar.gz"],
            ["test-package-1.0.0"]
        ]
        mock_isdir.return_value = True
        mock_exists.side_effect = lambda path: path == tmp_dir
        mock_scan.return_value = (True, None, 222)
        
        success, msg, dep_id = download_package(
            "/usr/bin/python3",
            ("test-package", ["==1.0.0"]),
            "https://pypi.org/simple/",
            1,
            (False, None)
        )
        
        assert success is True
        assert dep_id == 222
        # 验证镜像源参数被传递
        call_args = mock_download_source.call_args[0][0]
        assert "-i" in call_args
        assert "https://pypi.org/simple/" in call_args
        mock_rmtree.assert_called_once_with(tmp_dir)

    @patch('plugin.codemig.dependence_process.python_dependence_process.shutil.rmtree')
    @patch('plugin.codemig.dependence_process.python_dependence_process.os.path.exists')
    @patch('plugin.codemig.dependence_process.python_dependence_process.record_fail_package_info')
    @patch('plugin.codemig.dependence_process.python_dependence_process.download_package_source')
    @patch('plugin.codemig.dependence_process.python_dependence_process.os.makedirs')
    @patch('plugin.codemig.dependence_process.python_dependence_process.get_tmp_dir')
    @patch('plugin.codemig.dependence_process.python_dependence_process.subprocess.run')
    def test_download_package_query_exception(self, mock_run, mock_get_tmp_dir, mock_makedirs,
                                              mock_download_source, mock_record_fail, mock_exists, mock_rmtree):
        """测试查询命令异常"""        
        tmp_dir = "/tmp/test_pkg_12345"
        mock_get_tmp_dir.return_value = tmp_dir
        mock_run.side_effect = subprocess.SubprocessError("Query failed")
        mock_download_source.return_value = (False, "Download failed")
        mock_record_fail.return_value = 777
        mock_exists.return_value = lambda path: path == tmp_dir
        
        success, msg, dep_id = download_package(
            "/usr/bin/python3",
            ("test-package", ["==1.0.0"]),
            None,
            1,
            (False, None)
        )
        
        assert success is False
        mock_rmtree.assert_called_once_with(tmp_dir)


class TestPythonDependenceProcessor:
    """测试 PythonDependenceProcessor 类"""

    def test_init(self):
        """测试初始化"""
        processor = PythonDependenceProcessor(
            config=("/usr/bin/python3", "https://pypi.org/simple/"),
            to_process=[],
            task_id=1
        )
        assert processor.config_name == "Python"
        assert processor.task_id == 1
        assert processor.validated_config is None

    @patch('plugin.codemig.dependence_process.python_dependence_process.validate_python_interpreter')
    @patch('plugin.codemig.dependence_process.python_dependence_process.validate_python_mirror')
    def test_validate_config_success(self, mock_validate_mirror, mock_validate_interpreter):
        """测试配置验证成功"""
        mock_validate_interpreter.return_value = (True, "验证通过")
        mock_validate_mirror.return_value = (True, "验证通过")
        
        processor = PythonDependenceProcessor(
            config=("/usr/bin/python3", "https://pypi.org/simple/"),
            to_process=[],
            task_id=1
        )
        is_valid, result = processor.validate_config(("/usr/bin/python3", "https://pypi.org/simple/"))
        
        assert is_valid is True
        assert isinstance(result, tuple)

    @patch('plugin.codemig.dependence_process.python_dependence_process.validate_python_interpreter')
    def test_validate_config_invalid_interpreter(self, mock_validate_interpreter):
        """测试配置验证失败 - 解释器无效"""
        mock_validate_interpreter.return_value = (False, "路径不存在")
        
        processor = PythonDependenceProcessor(
            config=("/nonexistent/python", ""),
            to_process=[],
            task_id=1
        )
        is_valid, msg = processor.validate_config(("/nonexistent/python", ""))
        
        assert is_valid is False
        assert "路径不存在" in msg

    @patch('plugin.codemig.dependence_process.python_dependence_process.validate_python_interpreter')
    @patch('plugin.codemig.dependence_process.python_dependence_process.validate_python_mirror')
    def test_validate_config_invalid_mirror(self, mock_validate_mirror, mock_validate_interpreter):
        """测试配置验证失败 - 镜像源无效"""
        mock_validate_interpreter.return_value = (True, "验证通过")
        mock_validate_mirror.return_value = (False, "镜像源不可达")
        
        processor = PythonDependenceProcessor(
            config=("/usr/bin/python3", "https://invalid-mirror.com"),
            to_process=[],
            task_id=1
        )
        is_valid, msg = processor.validate_config(("/usr/bin/python3", "https://invalid-mirror.com"))
        
        assert is_valid is False
        assert "镜像源不可达" in msg

    @patch('plugin.codemig.dependence_process.python_dependence_process.validate_python_interpreter')
    def test_validate_config_no_mirror(self, mock_validate_interpreter):
        """测试配置验证 - 无镜像源"""
        mock_validate_interpreter.return_value = (True, "验证通过")
        
        processor = PythonDependenceProcessor(
            config=("/usr/bin/python3", ""),
            to_process=[],
            task_id=1
        )
        is_valid, result = processor.validate_config(("/usr/bin/python3", ""))
        
        assert is_valid is True

    def test_get_base_dir(self):
        """测试获取基础目录"""
        processor = PythonDependenceProcessor(
            config=("/usr/bin/python3", ""),
            to_process=[],
            task_id=1
        )
        base_dir = processor._get_base_dir()
        assert isinstance(base_dir, str)

    def test_should_check_installed(self):
        """测试是否应该检查已安装"""
        processor = PythonDependenceProcessor(
            config=("/usr/bin/python3", ""),
            to_process=[],
            task_id=1
        )
        assert processor._should_check_installed("any_path") is True

    def test_extract_version_for_check_equals(self):
        """测试提取版本号 - 等号"""
        processor = PythonDependenceProcessor(
            config=("/usr/bin/python3", ""),
            to_process=[],
            task_id=1
        )
        version = processor._extract_version_for_check("package", "==1.0.0")
        assert version == "1.0.0"

    def test_extract_version_for_check_greater_equal(self):
        """测试提取版本号 - 大于等于"""
        processor = PythonDependenceProcessor(
            config=("/usr/bin/python3", ""),
            to_process=[],
            task_id=1
        )
        version = processor._extract_version_for_check("package", ">=1.0.0")
        assert version == "1.0.0"

    def test_extract_version_for_check_less_equal(self):
        """测试提取版本号 - 小于等于"""
        processor = PythonDependenceProcessor(
            config=("/usr/bin/python3", ""),
            to_process=[],
            task_id=1
        )
        version = processor._extract_version_for_check("package", "<=1.0.0")
        assert version == "1.0.0"

    def test_extract_version_for_check_no_version(self):
        """测试提取版本号 - 无版本"""
        processor = PythonDependenceProcessor(
            config=("/usr/bin/python3", ""),
            to_process=[],
            task_id=1
        )
        # 实际代码会提取第一个 >= 的版本号
        version = processor._extract_version_for_check("package", ">=1.0.0,<2.0.0")
        # 代码会提取第一个 >= 的版本号，所以返回 "1.0.0"
        assert version == "1.0.0"

    def test_extract_version_for_check_multiple_constraints(self):
        """测试提取版本号 - 多个约束但无等号"""
        processor = PythonDependenceProcessor(
            config=("/usr/bin/python3", ""),
            to_process=[],
            task_id=1
        )
        # 如果只有 >= 和 <=，会提取 >= 的版本号
        version = processor._extract_version_for_check("package", ">=1.0.0,<=2.0.0")
        assert version == "1.0.0"

    def test_extract_version_for_check_no_match(self):
        """测试提取版本号 - 无匹配"""
        processor = PythonDependenceProcessor(
            config=("/usr/bin/python3", ""),
            to_process=[],
            task_id=1
        )
        # 如果没有 ==、>=、<=，返回 None
        version = processor._extract_version_for_check("package", "~=1.0.0")
        assert version is None

    @patch('plugin.codemig.dependence_process.python_dependence_process.download_package')
    def test_install_single_package(self, mock_download):
        """测试安装单个包"""
        mock_download.return_value = (True, None, 123)
        
        processor = PythonDependenceProcessor(
            config=("/usr/bin/python3", "https://pypi.org/simple/"),
            to_process=[],
            task_id=1
        )
        success, msg, dep_id = processor.install_single_package(
            1, "test-package", "==1.0.0", None, ("/usr/bin/python3", "https://pypi.org/simple/")
        )
        
        assert success is True
        assert dep_id == 123
        mock_download.assert_called_once()


class TestGetProxyFromPipConfigAdditional:
    """Test additional get_proxy_from_pip_config scenarios"""

    @patch('plugin.codemig.dependence_process.python_dependence_process.get_pip_config')
    def test_get_proxy_from_pip_config_http_only(self, mock_get_config):
        """Test http proxy only"""
        mock_get_config.return_value = {
            "global.http-proxy": "http://proxy:8080"
        }

        proxy = get_proxy_from_pip_config("/usr/bin/python3", (False, None))
        assert "http" in proxy
        assert "https" not in proxy

    @patch('plugin.codemig.dependence_process.python_dependence_process.get_pip_config')
    def test_get_proxy_from_pip_config_https_only(self, mock_get_config):
        """Test https proxy only"""
        mock_get_config.return_value = {
            "global.https-proxy": "https://proxy:8080"
        }

        proxy = get_proxy_from_pip_config("/usr/bin/python3", (False, None))
        assert "http" not in proxy
        assert "https" in proxy

    @patch('plugin.codemig.dependence_process.python_dependence_process.get_pip_config')
    def test_get_proxy_from_pip_config_no_proxy(self, mock_get_config):
        """Test no_proxy configuration"""
        mock_get_config.return_value = {
            "global.no-proxy": "localhost,127.0.0.1"
        }

        proxy = get_proxy_from_pip_config("/usr/bin/python3", (False, None))
        assert "no-proxy" in proxy
        assert proxy["no-proxy"] == "localhost,127.0.0.1"

    @patch('plugin.codemig.dependence_process.python_dependence_process.get_pip_config')
    def test_get_proxy_from_pip_config_global_proxy(self, mock_get_config):
        """Test global.proxy sets both http and https"""
        mock_get_config.return_value = {
            "global.proxy": "http://proxy:8080"
        }

        proxy = get_proxy_from_pip_config("/usr/bin/python3", (False, None))
        assert proxy["http"] == "http://proxy:8080"
        assert proxy["https"] == "http://proxy:8080"

    def test_get_proxy_from_pip_config_empty_config(self):
        """Test empty configuration"""
        python_config = (False, None)
        proxy = get_proxy_from_pip_config("/usr/bin/python3", python_config)
        assert proxy == {}


class TestDownloadWithProxy:
    """Test download_with_proxy function"""

    @patch('plugin.codemig.dependence_process.python_dependence_process.subprocess.run')
    @patch('plugin.codemig.dependence_process.python_dependence_process.get_proxy_from_pip_config')
    def test_download_with_proxy_success(self, mock_get_proxy, mock_run):
        """Test successful download with proxy"""
        mock_get_proxy.return_value = {"http": "http://proxy:8080"}
        mock_run.return_value = MagicMock(returncode=0)

        success, error = download_with_proxy(
            "http://example.com/package.tar.gz",
            "/tmp/target",
            "/usr/bin/python3",
            (False, None)
        )

        assert success is True
        assert error is None
        mock_run.assert_called_once()

    @patch('plugin.codemig.dependence_process.python_dependence_process.subprocess.run')
    @patch('plugin.codemig.dependence_process.python_dependence_process.get_proxy_from_pip_config')
    def test_download_with_proxy_failure(self, mock_get_proxy, mock_run):
        """Test failed download"""
        mock_get_proxy.return_value = {}
        mock_run.return_value = MagicMock(returncode=1, stderr="Download failed")

        success, error = download_with_proxy(
            "http://example.com/package.tar.gz",
            "/tmp/target",
            "/usr/bin/python3",
            (False, None)
        )

        assert success is False
        assert "失败" in error

    @patch('plugin.codemig.dependence_process.python_dependence_process.subprocess.run')
    @patch('plugin.codemig.dependence_process.python_dependence_process.get_proxy_from_pip_config')
    def test_download_with_proxy_timeout(self, mock_get_proxy, mock_run):
        """Test download timeout"""
        mock_get_proxy.return_value = {}
        mock_run.side_effect = subprocess.TimeoutExpired("wget", 43200)

        success, error = download_with_proxy(
            "http://example.com/package.tar.gz",
            "/tmp/target",
            "/usr/bin/python3",
            (False, None)
        )

        assert success is False
        assert "超时" in error or "下载失败" in error

    @patch('plugin.codemig.dependence_process.python_dependence_process.subprocess.run')
    @patch('plugin.codemig.dependence_process.python_dependence_process.get_proxy_from_pip_config')
    def test_download_with_proxy_called_process_error(self, mock_get_proxy, mock_run):
        """Test CalledProcessError"""
        mock_get_proxy.return_value = {}
        mock_run.side_effect = subprocess.CalledProcessError(1, "wget", stderr="error")

        success, error = download_with_proxy(
            "http://example.com/package.tar.gz",
            "/tmp/target",
            "/usr/bin/python3",
            (False, None)
        )

        assert success is False


class TestDownloadPackageSource:
    """Test download_package_source function"""

    @patch('plugin.codemig.dependence_process.python_dependence_process.subprocess.run')
    @patch('plugin.codemig.dependence_process.python_dependence_process.download_with_proxy')
    def test_download_package_source_success(self, mock_download_with_proxy, mock_run):
        """Test successful package source download"""
        mock_run.return_value = MagicMock(returncode=0, stdout="Downloading success")

        success, output = download_package_source(
            ["pip", "install", "package"],
            "/tmp/target",
            "/usr/bin/python3",
            (False, None)
        )

        assert success is True
        assert output == "Downloading success"

    @patch('plugin.codemig.dependence_process.python_dependence_process.subprocess.run')
    @patch('plugin.codemig.dependence_process.python_dependence_process.download_with_proxy')
    def test_download_package_source_with_download_link(self, mock_download_with_proxy, mock_run):
        """Test download with link extraction from output"""
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="Downloading https://example.com/package.tar.gz\nFailed"
        )
        mock_download_with_proxy.return_value = (True, None)

        success, output = download_package_source(
            ["pip", "install", "package"],
            "/tmp/target",
            "/usr/bin/python3",
            (False, None)
        )

        assert success is True
        mock_download_with_proxy.assert_called_once()

    @patch('plugin.codemig.dependence_process.python_dependence_process.subprocess.run')
    def test_download_package_source_failure_no_link(self, mock_run):
        """Test failure without downloadable link"""
        mock_run.return_value = MagicMock(returncode=1, stdout="Some error output", stderr="error details")

        success, output = download_package_source(
            ["pip", "install", "package"],
            "/tmp/target",
            "/usr/bin/python3",
            (False, None)
        )

        assert success is False
        # The function returns stderr when no download link found
        assert "error details" in output or "Some error output" in output

    @patch('plugin.codemig.dependence_process.python_dependence_process.subprocess.run')
    def test_download_package_source_timeout(self, mock_run):
        """Test download timeout"""
        mock_run.side_effect = subprocess.TimeoutExpired("cmd", DOWNLOAD_TIMEOUT)

        success, output = download_package_source(
            ["pip", "install", "package"],
            "/tmp/target",
            "/usr/bin/python3",
            (False, None)
        )

        assert success is False
        # Timeout returns message with 网路问题 or 下载失败
        assert "网路问题" in output or "下载失败" in output

    @patch('plugin.codemig.dependence_process.python_dependence_process.subprocess.run')
    def test_download_package_source_called_process_error(self, mock_run):
        """Test CalledProcessError"""
        mock_run.side_effect = subprocess.CalledProcessError(1, "cmd", stderr="error message")

        success, output = download_package_source(
            ["pip", "install", "package"],
            "/tmp/target",
            "/usr/bin/python3",
            (False, None)
        )

        assert success is False


class TestDownloadPackageAdditional:
    """Additional tests for download_package function"""

    @patch('plugin.codemig.dependence_process.python_dependence_process.shutil.rmtree')
    @patch('plugin.codemig.dependence_process.python_dependence_process.os.path.exists')
    @patch('plugin.codemig.dependence_process.python_dependence_process.record_fail_package_info')
    @patch('plugin.codemig.dependence_process.python_dependence_process.download_package_source')
    @patch('plugin.codemig.dependence_process.python_dependence_process.os.makedirs')
    @patch('plugin.codemig.dependence_process.python_dependence_process.get_tmp_dir')
    @patch('plugin.codemig.dependence_process.python_dependence_process.subprocess.run')
    def test_download_package_file_not_found(self, mock_run, mock_get_tmp_dir, mock_makedirs,
                                              mock_download_source, mock_record_fail, mock_exists, mock_rmtree):
        """Test FileNotFoundError during installation"""
        tmp_dir = "/tmp/test_pkg_12345"
        mock_get_tmp_dir.return_value = tmp_dir
        mock_run.return_value = MagicMock(returncode=1)
        mock_download_source.side_effect = FileNotFoundError("python not found")
        mock_record_fail.return_value = 999
        mock_exists.return_value = lambda path: path == tmp_dir

        success, msg, dep_id = download_package(
            "/usr/bin/python3",
            ("test-package", ["==1.0.0"]),
            None,
            1,
            (False, None)
        )

        assert success is False
        assert dep_id == 999
        mock_rmtree.assert_called_once_with(tmp_dir)

    @patch('plugin.codemig.dependence_process.python_dependence_process.shutil.rmtree')
    @patch('plugin.codemig.dependence_process.python_dependence_process.os.path.exists')
    @patch('plugin.codemig.dependence_process.python_dependence_process.record_fail_package_info')
    @patch('plugin.codemig.dependence_process.python_dependence_process.download_package_source')
    @patch('plugin.codemig.dependence_process.python_dependence_process.os.makedirs')
    @patch('plugin.codemig.dependence_process.python_dependence_process.get_tmp_dir')
    @patch('plugin.codemig.dependence_process.python_dependence_process.subprocess.run')
    def test_download_package_json_decode_error(self, mock_run, mock_get_tmp_dir, mock_makedirs,
                                                 mock_download_source, mock_record_fail, mock_exists, mock_rmtree):
        """Test JSONDecodeError during query"""
        import json
        tmp_dir = "/tmp/test_pkg_12345"
        mock_get_tmp_dir.return_value = tmp_dir
        mock_run.return_value = MagicMock(returncode=0, stdout="invalid json")
        # After JSON decode error, it continues to download
        mock_download_source.return_value = (False, "download failed")
        mock_record_fail.return_value = 888
        mock_exists.return_value = lambda path: path == tmp_dir

        success, msg, dep_id = download_package(
            "/usr/bin/python3",
            ("test-package", ["==1.0.0"]),
            None,
            1,
            (False, None)
        )

        # Should continue to download after JSON decode error
        mock_download_source.assert_called()

class TestValidatePythonInterpreterAdditional:
    """Additional tests for validate_python_interpreter"""

    @patch('plugin.codemig.dependence_process.python_dependence_process.os.path.exists')
    @patch('plugin.codemig.dependence_process.python_dependence_process.os.path.isfile')
    @patch('plugin.codemig.dependence_process.python_dependence_process.os.access')
    def test_validate_python_interpreter_timeout(self, mock_access, mock_isfile, mock_exists):
        """Test TimeoutExpired exception"""
        mock_exists.return_value = True
        mock_isfile.return_value = True
        mock_access.return_value = True

        with patch('plugin.codemig.dependence_process.python_dependence_process.subprocess.run') as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired("python", 5)
            is_valid, msg = validate_python_interpreter("/usr/bin/python3")

        assert is_valid is False
        assert "出错" in msg

    @patch('plugin.codemig.dependence_process.python_dependence_process.os.path.exists')
    @patch('plugin.codemig.dependence_process.python_dependence_process.os.path.isfile')
    @patch('plugin.codemig.dependence_process.python_dependence_process.os.access')
    def test_validate_python_interpreter_permission_error(self, mock_access, mock_isfile, mock_exists):
        """Test PermissionError exception"""
        mock_exists.return_value = True
        mock_isfile.return_value = True
        mock_access.return_value = True

        with patch('plugin.codemig.dependence_process.python_dependence_process.subprocess.run') as mock_run:
            mock_run.side_effect = PermissionError("Permission denied")
            is_valid, msg = validate_python_interpreter("/usr/bin/python3")

        assert is_valid is False
        assert "出错" in msg

    @patch('plugin.codemig.dependence_process.python_dependence_process.os.path.exists')
    @patch('plugin.codemig.dependence_process.python_dependence_process.os.path.isfile')
    @patch('plugin.codemig.dependence_process.python_dependence_process.os.access')
    def test_validate_python_interpreter_os_error(self, mock_access, mock_isfile, mock_exists):
        """Test OSError exception"""
        mock_exists.return_value = True
        mock_isfile.return_value = True
        mock_access.return_value = True

        with patch('plugin.codemig.dependence_process.python_dependence_process.subprocess.run') as mock_run:
            mock_run.side_effect = OSError("OS error")
            is_valid, msg = validate_python_interpreter("/usr/bin/python3")

        assert is_valid is False


class TestValidatePythonMirrorAdditional:
    """Additional tests for validate_python_mirror"""

    def test_validate_python_mirror_value_error(self):
        """Test ValueError during URL parsing"""
        with patch('plugin.codemig.dependence_process.python_dependence_process.urlparse') as mock_parse:
            mock_parse.side_effect = ValueError("Invalid URL")
            is_valid, msg = validate_python_mirror("test://url")
        assert is_valid is False

    @patch('plugin.codemig.dependence_process.python_dependence_process.requests.get')
    def test_validate_python_mirror_connection_error(self, mock_get):
        """Test connection error"""
        from requests.exceptions import ConnectionError
        mock_get.side_effect = ConnectionError("Connection refused")

        is_valid, msg = validate_python_mirror("https://pypi.org/simple/")

        assert is_valid is False
        assert "连接测试失败" in msg

    @patch('plugin.codemig.dependence_process.python_dependence_process.requests.get')
    def test_validate_python_mirror_timeout(self, mock_get):
        """Test timeout during connection"""
        from requests.exceptions import Timeout
        mock_get.side_effect = Timeout("Request timed out")

        is_valid, msg = validate_python_mirror("https://pypi.org/simple/")

        assert is_valid is False
        assert "连接测试失败" in msg


class TestGetProxyFromPipConfigAdditional:
    """Test additional get_proxy_from_pip_config scenarios"""

    @patch('plugin.codemig.dependence_process.python_dependence_process.get_pip_config')
    def test_get_proxy_from_pip_config_http_only(self, mock_get_config):
        """Test http proxy only"""
        mock_get_config.return_value = {
            "global.http-proxy": "http://proxy:8080"
        }

        proxy = get_proxy_from_pip_config("/usr/bin/python3", (False, None))
        assert "http" in proxy
        assert "https" not in proxy

    @patch('plugin.codemig.dependence_process.python_dependence_process.get_pip_config')
    def test_get_proxy_from_pip_config_https_only(self, mock_get_config):
        """Test https proxy only"""
        mock_get_config.return_value = {
            "global.https-proxy": "https://proxy:8080"
        }

        proxy = get_proxy_from_pip_config("/usr/bin/python3", (False, None))
        assert "http" not in proxy
        assert "https" in proxy

    @patch('plugin.codemig.dependence_process.python_dependence_process.get_pip_config')
    def test_get_proxy_from_pip_config_no_proxy(self, mock_get_config):
        """Test no_proxy configuration"""
        mock_get_config.return_value = {
            "global.no-proxy": "localhost,127.0.0.1"
        }

        proxy = get_proxy_from_pip_config("/usr/bin/python3", (False, None))
        assert "no-proxy" in proxy
        assert proxy["no-proxy"] == "localhost,127.0.0.1"

    @patch('plugin.codemig.dependence_process.python_dependence_process.get_pip_config')
    def test_get_proxy_from_pip_config_global_proxy(self, mock_get_config):
        """Test global.proxy sets both http and https"""
        mock_get_config.return_value = {
            "global.proxy": "http://proxy:8080"
        }

        proxy = get_proxy_from_pip_config("/usr/bin/python3", (False, None))
        assert proxy["http"] == "http://proxy:8080"
        assert proxy["https"] == "http://proxy:8080"

    def test_get_proxy_from_pip_config_empty_config(self):
        """Test empty configuration"""
        python_config = (False, None)
        proxy = get_proxy_from_pip_config("/usr/bin/python3", python_config)
        assert proxy == {}


class TestDownloadWithProxy:
    """Test download_with_proxy function"""

    @patch('plugin.codemig.dependence_process.python_dependence_process.subprocess.run')
    @patch('plugin.codemig.dependence_process.python_dependence_process.get_proxy_from_pip_config')
    def test_download_with_proxy_success(self, mock_get_proxy, mock_run):
        """Test successful download with proxy"""
        mock_get_proxy.return_value = {"http": "http://proxy:8080"}
        mock_run.return_value = MagicMock(returncode=0)

        success, error = download_with_proxy(
            "http://example.com/package.tar.gz",
            "/tmp/target",
            "/usr/bin/python3",
            (False, None)
        )

        assert success is True
        assert error is None
        mock_run.assert_called_once()

    @patch('plugin.codemig.dependence_process.python_dependence_process.subprocess.run')
    @patch('plugin.codemig.dependence_process.python_dependence_process.get_proxy_from_pip_config')
    def test_download_with_proxy_failure(self, mock_get_proxy, mock_run):
        """Test failed download"""
        mock_get_proxy.return_value = {}
        mock_run.return_value = MagicMock(returncode=1, stderr="Download failed")

        success, error = download_with_proxy(
            "http://example.com/package.tar.gz",
            "/tmp/target",
            "/usr/bin/python3",
            (False, None)
        )

        assert success is False
        assert "失败" in error

    @patch('plugin.codemig.dependence_process.python_dependence_process.subprocess.run')
    @patch('plugin.codemig.dependence_process.python_dependence_process.get_proxy_from_pip_config')
    def test_download_with_proxy_timeout(self, mock_get_proxy, mock_run):
        """Test download timeout"""
        mock_get_proxy.return_value = {}
        mock_run.side_effect = subprocess.TimeoutExpired("wget", 43200)

        success, error = download_with_proxy(
            "http://example.com/package.tar.gz",
            "/tmp/target",
            "/usr/bin/python3",
            (False, None)
        )

        assert success is False
        assert "超时" in error or "下载失败" in error

    @patch('plugin.codemig.dependence_process.python_dependence_process.subprocess.run')
    @patch('plugin.codemig.dependence_process.python_dependence_process.get_proxy_from_pip_config')
    def test_download_with_proxy_called_process_error(self, mock_get_proxy, mock_run):
        """Test CalledProcessError"""
        mock_get_proxy.return_value = {}
        mock_run.side_effect = subprocess.CalledProcessError(1, "wget", stderr="error")

        success, error = download_with_proxy(
            "http://example.com/package.tar.gz",
            "/tmp/target",
            "/usr/bin/python3",
            (False, None)
        )

        assert success is False


class TestDownloadPackageSource:
    """Test download_package_source function"""

    @patch('plugin.codemig.dependence_process.python_dependence_process.subprocess.run')
    @patch('plugin.codemig.dependence_process.python_dependence_process.download_with_proxy')
    def test_download_package_source_success(self, mock_download_with_proxy, mock_run):
        """Test successful package source download"""
        mock_run.return_value = MagicMock(returncode=0, stdout="Downloading success")

        success, output = download_package_source(
            ["pip", "install", "package"],
            "/tmp/target",
            "/usr/bin/python3",
            (False, None)
        )

        assert success is True
        assert output == "Downloading success"

    @patch('plugin.codemig.dependence_process.python_dependence_process.subprocess.run')
    @patch('plugin.codemig.dependence_process.python_dependence_process.download_with_proxy')
    def test_download_package_source_with_download_link(self, mock_download_with_proxy, mock_run):
        """Test download with link extraction from output"""
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="Downloading https://example.com/package.tar.gz\nFailed"
        )
        mock_download_with_proxy.return_value = (True, None)

        success, output = download_package_source(
            ["pip", "install", "package"],
            "/tmp/target",
            "/usr/bin/python3",
            (False, None)
        )

        assert success is True
        mock_download_with_proxy.assert_called_once()

    @patch('plugin.codemig.dependence_process.python_dependence_process.subprocess.run')
    def test_download_package_source_failure_no_link(self, mock_run):
        """Test failure without downloadable link"""
        mock_run.return_value = MagicMock(returncode=1, stdout="Some error output", stderr="error details")

        success, output = download_package_source(
            ["pip", "install", "package"],
            "/tmp/target",
            "/usr/bin/python3",
            (False, None)
        )

        assert success is False
        assert "error details" in str(output)

    @patch('plugin.codemig.dependence_process.python_dependence_process.subprocess.run')
    def test_download_package_source_timeout(self, mock_run):
        """Test download timeout"""
        # Use a large timeout value similar to DOWNLOAD_TIMEOUT
        mock_run.side_effect = subprocess.TimeoutExpired("cmd", 3600)

        success, output = download_package_source(
            ["pip", "install", "package"],
            "/tmp/target",
            "/usr/bin/python3",
            (False, None)
        )

        assert success is False
        assert "网路问题" in output or "下载失败" in output

    @patch('plugin.codemig.dependence_process.python_dependence_process.subprocess.run')
    def test_download_package_source_called_process_error(self, mock_run):
        """Test CalledProcessError"""
        mock_run.side_effect = subprocess.CalledProcessError(1, "cmd", stderr="error message")

        success, output = download_package_source(
            ["pip", "install", "package"],
            "/tmp/target",
            "/usr/bin/python3",
            (False, None)
        )

        assert success is False


class TestDownloadPackageAdditional:
    """Additional tests for download_package function"""

    @patch('plugin.codemig.dependence_process.python_dependence_process.shutil.rmtree')
    @patch('plugin.codemig.dependence_process.python_dependence_process.os.path.exists')
    @patch('plugin.codemig.dependence_process.python_dependence_process.record_fail_package_info')
    @patch('plugin.codemig.dependence_process.python_dependence_process.download_package_source')
    @patch('plugin.codemig.dependence_process.python_dependence_process.os.makedirs')
    @patch('plugin.codemig.dependence_process.python_dependence_process.get_tmp_dir')
    @patch('plugin.codemig.dependence_process.python_dependence_process.subprocess.run')
    def test_download_package_file_not_found(self, mock_run, mock_get_tmp_dir, mock_makedirs,
                                              mock_download_source, mock_record_fail, mock_exists, mock_rmtree):
        """Test FileNotFoundError during installation"""
        tmp_dir = "/tmp/test_pkg_12345"
        mock_get_tmp_dir.return_value = tmp_dir
        mock_run.return_value = MagicMock(returncode=1)
        mock_download_source.side_effect = FileNotFoundError("python not found")
        mock_record_fail.return_value = 999
        mock_exists.return_value = lambda path: path == tmp_dir

        success, msg, dep_id = download_package(
            "/usr/bin/python3",
            ("test-package", ["==1.0.0"]),
            None,
            1,
            (False, None)
        )

        assert success is False
        assert dep_id == 999
        mock_rmtree.assert_called_once_with(tmp_dir)

    @patch('plugin.codemig.dependence_process.python_dependence_process.shutil.rmtree')
    @patch('plugin.codemig.dependence_process.python_dependence_process.os.path.exists')
    @patch('plugin.codemig.dependence_process.python_dependence_process.record_fail_package_info')
    @patch('plugin.codemig.dependence_process.python_dependence_process.download_package_source')
    @patch('plugin.codemig.dependence_process.python_dependence_process.os.makedirs')
    @patch('plugin.codemig.dependence_process.python_dependence_process.get_tmp_dir')
    @patch('plugin.codemig.dependence_process.python_dependence_process.subprocess.run')
    def test_download_package_json_decode_error(self, mock_run, mock_get_tmp_dir, mock_makedirs,
                                                 mock_download_source, mock_record_fail, mock_exists, mock_rmtree):
        """Test JSONDecodeError during query"""
        import json
        tmp_dir = "/tmp/test_pkg_12345"
        mock_get_tmp_dir.return_value = tmp_dir
        mock_run.return_value = MagicMock(returncode=0, stdout="invalid json")
        # After JSON decode error, it continues to download
        mock_download_source.return_value = (False, "download failed")
        mock_record_fail.return_value = 888
        mock_exists.return_value = lambda path: path == tmp_dir

        success, msg, dep_id = download_package(
            "/usr/bin/python3",
            ("test-package", ["==1.0.0"]),
            None,
            1,
            (False, None)
        )

        # Should continue to download after JSON decode error
        mock_download_source.assert_called()

    @patch('plugin.codemig.dependence_process.python_dependence_process.shutil.rmtree')
    @patch('plugin.codemig.dependence_process.python_dependence_process.os.rename')
    @patch('plugin.codemig.dependence_process.python_dependence_process.extract_file')
    @patch('plugin.codemig.dependence_process.python_dependence_process.os.remove')
    @patch('plugin.codemig.dependence_process.python_dependence_process.os.path.isdir')
    @patch('plugin.codemig.dependence_process.python_dependence_process.os.listdir')
    @patch('plugin.codemig.dependence_process.python_dependence_process.os.path.exists')
    @patch('plugin.codemig.dependence_process.python_dependence_process.scan_packages')
    @patch('plugin.codemig.dependence_process.python_dependence_process.download_package_source')
    @patch('plugin.codemig.dependence_process.python_dependence_process.DependencePackages.is_package_installed')
    @patch('plugin.codemig.dependence_process.python_dependence_process.extract_version_advanced')
    @patch('plugin.codemig.dependence_process.python_dependence_process.get_package_dir')
    @patch('plugin.codemig.dependence_process.python_dependence_process.os.makedirs')
    @patch('plugin.codemig.dependence_process.python_dependence_process.get_tmp_dir')
    @patch('plugin.codemig.dependence_process.python_dependence_process.subprocess.run')
    def test_download_package_version_dir_exists_not_installed(
            self, mock_run, mock_get_tmp_dir, mock_makedirs, mock_get_package_dir,
            mock_extract_version, mock_is_installed, mock_download_source, mock_scan,
            mock_exists, mock_listdir, mock_isdir, mock_remove, mock_extract, mock_rename, mock_rmtree):
        """Test when versioned_dir exists but package not installed - should delete and reinstall"""
        tmp_dir = "/tmp/test_pkg_12345"
        versioned_dir = "/test/python_packages/test_package_1.0.0"
        mock_get_tmp_dir.return_value = tmp_dir
        mock_run.return_value = MagicMock(returncode=1)
        mock_download_source.return_value = (True, None)
        mock_listdir.side_effect = [
            ["test-package-1.0.0.tar.gz"],
            ["test-package-1.0.0"]
        ]
        mock_isdir.return_value = True
        mock_extract_version.return_value = "1.0.0"
        mock_get_package_dir.return_value = versioned_dir
        # All paths exist
        mock_exists.return_value = True
        # Package not installed both times checked
        mock_is_installed.side_effect = [None, None]
        mock_scan.return_value = (True, None, 333)

        success, msg, dep_id = download_package(
            "/usr/bin/python3",
            ("test-package", ["==1.0.0"]),
            None,
            1,
            (False, None)
        )

        assert success is True
        assert dep_id == 333
        # Should call rmtree on versioned_dir (line 290) and tmp_dir (finally block line 306)
        assert mock_rmtree.call_count >= 2


class TestValidatePythonInterpreterAdditional:
    """Additional tests for validate_python_interpreter"""

    @patch('plugin.codemig.dependence_process.python_dependence_process.os.path.exists')
    @patch('plugin.codemig.dependence_process.python_dependence_process.os.path.isfile')
    @patch('plugin.codemig.dependence_process.python_dependence_process.os.access')
    def test_validate_python_interpreter_timeout(self, mock_access, mock_isfile, mock_exists):
        """Test TimeoutExpired exception"""
        mock_exists.return_value = True
        mock_isfile.return_value = True
        mock_access.return_value = True

        with patch('plugin.codemig.dependence_process.python_dependence_process.subprocess.run') as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired("python", 5)
            is_valid, msg = validate_python_interpreter("/usr/bin/python3")

        assert is_valid is False
        assert "出错" in msg

    @patch('plugin.codemig.dependence_process.python_dependence_process.os.path.exists')
    @patch('plugin.codemig.dependence_process.python_dependence_process.os.path.isfile')
    @patch('plugin.codemig.dependence_process.python_dependence_process.os.access')
    def test_validate_python_interpreter_permission_error(self, mock_access, mock_isfile, mock_exists):
        """Test PermissionError exception"""
        mock_exists.return_value = True
        mock_isfile.return_value = True
        mock_access.return_value = True

        with patch('plugin.codemig.dependence_process.python_dependence_process.subprocess.run') as mock_run:
            mock_run.side_effect = PermissionError("Permission denied")
            is_valid, msg = validate_python_interpreter("/usr/bin/python3")

        assert is_valid is False
        assert "出错" in msg

    @patch('plugin.codemig.dependence_process.python_dependence_process.os.path.exists')
    @patch('plugin.codemig.dependence_process.python_dependence_process.os.path.isfile')
    @patch('plugin.codemig.dependence_process.python_dependence_process.os.access')
    def test_validate_python_interpreter_os_error(self, mock_access, mock_isfile, mock_exists):
        """Test OSError exception"""
        mock_exists.return_value = True
        mock_isfile.return_value = True
        mock_access.return_value = True

        with patch('plugin.codemig.dependence_process.python_dependence_process.subprocess.run') as mock_run:
            mock_run.side_effect = OSError("OS error")
            is_valid, msg = validate_python_interpreter("/usr/bin/python3")

        assert is_valid is False


class TestValidatePythonMirrorAdditional:
    """Additional tests for validate_python_mirror"""

    def test_validate_python_mirror_value_error(self):
        """Test ValueError during URL parsing"""
        with patch('plugin.codemig.dependence_process.python_dependence_process.urlparse') as mock_parse:
            mock_parse.side_effect = ValueError("Invalid URL")
            is_valid, msg = validate_python_mirror("test://url")
        assert is_valid is False

    def test_validate_python_mirror_connection_error(self):
        """Test connection error - mock requests using sys.modules"""
        import sys
        from unittest.mock import MagicMock

        # Create a mock requests module
        mock_requests = MagicMock()
        mock_requests.get.side_effect = Exception("Connection refused")
        mock_requests.RequestException = Exception

        # Patch requests in sys.modules
        with patch.dict(sys.modules, {'requests': mock_requests}):
            is_valid, msg = validate_python_mirror("https://pypi.org/simple/")

        assert is_valid is False
        assert "连接测试失败" in msg

    def test_validate_python_mirror_timeout(self):
        """Test timeout during connection - mock requests using sys.modules"""
        import sys
        from unittest.mock import MagicMock

        # Create a mock requests module
        mock_requests = MagicMock()
        mock_requests.get.side_effect = Exception("Timeout")
        mock_requests.RequestException = Exception

        # Patch requests in sys.modules
        with patch.dict(sys.modules, {'requests': mock_requests}):
            is_valid, msg = validate_python_mirror("https://pypi.org/simple/")

        assert is_valid is False
        assert "连接测试失败" in msg
