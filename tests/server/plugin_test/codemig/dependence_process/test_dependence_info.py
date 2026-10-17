import pytest
from plugin.codemig.dependence_process.dependence_info import DependenceInfo, DepStatus, DOWNLOAD_TIMEOUT


class TestDependenceInfo:
    """测试 DependenceInfo 类"""

    def test_init_minimal(self):
        """测试最小初始化"""
        dep = DependenceInfo(scan=0)
        assert dep.scan == 0
        assert dep.lang is None
        assert dep.python is None
        assert dep.python_config is None
        assert dep.go is None
        assert dep.go_config is None

    def test_init_with_lang(self):
        """测试带语言初始化"""
        dep = DependenceInfo(scan=1, lang="python")
        assert dep.scan == 1
        assert dep.lang == "python"

    def test_init_with_python(self):
        """测试带Python配置初始化"""
        dep = DependenceInfo(scan=1, lang="python", python="/usr/bin/python3", python_config="https://pypi.org/simple")
        assert dep.scan == 1
        assert dep.lang == "python"
        assert dep.python == "/usr/bin/python3"
        assert dep.python_config == "https://pypi.org/simple"

    def test_init_with_go(self):
        """测试带Go配置初始化"""
        dep = DependenceInfo(scan=1, lang="go", go="/usr/local/go", go_config="GOPROXY=https://proxy.golang.org")
        assert dep.scan == 1
        assert dep.lang == "go"
        assert dep.go == "/usr/local/go"
        assert dep.go_config == "GOPROXY=https://proxy.golang.org"

    def test_init_full(self):
        """测试完整初始化"""
        dep = DependenceInfo(
            scan=1,
            lang="python",
            python="/usr/bin/python3",
            python_config="https://pypi.org/simple",
            go="/usr/local/go",
            go_config="GOPROXY=https://proxy.golang.org"
        )
        assert dep.scan == 1
        assert dep.lang == "python"
        assert dep.python == "/usr/bin/python3"
        assert dep.python_config == "https://pypi.org/simple"
        assert dep.go == "/usr/local/go"
        assert dep.go_config == "GOPROXY=https://proxy.golang.org"


class TestDepStatus:
    """测试 DepStatus 枚举"""

    def test_dep_status_values(self):
        """测试枚举值"""
        assert DepStatus.created.value == 0
        assert DepStatus.failed.value == 1
        assert DepStatus.finished.value == 2

    def test_dep_status_names(self):
        """测试枚举名称"""
        assert DepStatus.created.name == "created"
        assert DepStatus.failed.name == "failed"
        assert DepStatus.finished.name == "finished"


class TestDownloadTimeout:
    """测试下载超时常量"""

    def test_download_timeout_value(self):
        """测试超时值"""
        assert DOWNLOAD_TIMEOUT == 10800  # 3小时
