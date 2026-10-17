"""测试环境全局隔离：将数据库与数据目录整体重定向到临时目录。

pytest 收集/导入任何测试模块之前，本文件先完成两层重定向：

  a. 环境变量 SQLITE_DATABASE_URI 指向临时库（config.Config 优先读环境变量，
     common/db/SQLOperation.py 创建 engine 时即使用临时库）；
  b. patch common.public.public 的路径常量（DB_DIR/DATABASE/CODEMIG_DATA_PATH/
     AGENT_DATA_PATH/AGENT_TEMP_PATH）——get_conn(file) 与各插件模块 import 时
     复制这些值，patch 先于任何 server 模块导入，故全部生效。

如此一来，测试中未被 mock 的写库调用也只会落在临时库。临时目录在会话
结束后整体删除；个别测试（user_manager/web_test 的 app fixture）自行创建
的临时库不受影响。
"""
import atexit
import os
import shutil
import tempfile

# ── 必须在任何 server 模块导入之前完成重定向 ──────────────────────────
# pytest 先加载本 conftest、后收集/导入测试模块，且 pythonpath(../../server)
# 在 conftest 导入前已生效，因此这里的 import 与 patch 均安全。
_TEST_DATA_DIR = tempfile.mkdtemp(prefix='codemig_test_data_')

# a. engine 层：Config 优先读环境变量（见 server/config.py::_get_config）
os.environ['SQLITE_DATABASE_URI'] = f"sqlite:///{os.path.join(_TEST_DATA_DIR, 'codemig.db')}"

# b. 直连层：get_conn / 各插件按 DB_DIR、CODEMIG_DATA_PATH 等常量定位文件
import common.public.public as _public  # noqa: E402

_public.DB_DIR = _TEST_DATA_DIR
_public.DATABASE = os.path.join(_TEST_DATA_DIR, 'codemig.db')
_public.CODEMIG_DATA_PATH = os.path.join(_TEST_DATA_DIR, 'codemig')
_public.AGENT_DATA_PATH = os.path.join(_TEST_DATA_DIR, 'agent')
_public.AGENT_TEMP_PATH = os.path.join(_TEST_DATA_DIR, 'temp_file')

_original_env_uri = None


def _cleanup_test_data_dir():
    shutil.rmtree(_TEST_DATA_DIR, ignore_errors=True)


atexit.register(_cleanup_test_data_dir)


import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def _ensure_db_isolation():
    """逐用例兜底：个别测试（user_manager/web_test 的 app fixture）会在
    teardown 中删除 SQLITE_DATABASE_URI 环境变量，此处确保下一个用例
    开始前重定向仍然生效，杜绝中途退回真实库。"""
    global _original_env_uri
    uri = os.environ.get('SQLITE_DATABASE_URI')
    if uri != f"sqlite:///{os.path.join(_TEST_DATA_DIR, 'codemig.db')}":
        _original_env_uri = uri
        os.environ['SQLITE_DATABASE_URI'] = f"sqlite:///{os.path.join(_TEST_DATA_DIR, 'codemig.db')}"
    yield
    if _original_env_uri is not None:
        os.environ['SQLITE_DATABASE_URI'] = _original_env_uri
        _original_env_uri = None
