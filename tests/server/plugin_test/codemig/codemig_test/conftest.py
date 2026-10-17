"""codemig 主模块 import 副作用抑制。

plugin/codemig/codemig.py 在模块级执行 backend_process()，其中
multiprocessing.Process(target=run_tasks, name="CodemigBackend").start()
会在多线程的 pytest 进程里真实 fork：
1. 泄漏一个空转的守护子进程（target 只是 while True: sleep(120)）；
2. 触发 Python 3.12+ DeprecationWarning（multi-threaded fork 可能死锁）。

本 conftest 在该模块首次被 import 前注入一个不 fork 的 Process 替身，
模块级 backend_process() 启动的即为此替身，fork 不再发生。
测试内对 backend_process 行为的断言不受影响——它们各自显式 patch 依赖后
调用真实函数。
"""
import builtins
import multiprocessing
import os
import sys
from unittest import mock

MODULE_PATH = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))
if MODULE_PATH not in sys.path:
    sys.path.append(MODULE_PATH)

if 'plugin.codemig.codemig' not in sys.modules:
    _RealProcess = multiprocessing.Process

    class _NoForkProcess(_RealProcess):
        """跨过真实 fork 的 Process 替身：start() 只标记已启动。"""

        def start(self):
            self._popen = mock.MagicMock()

    _real_import = builtins.__import__

    def _hooked_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == 'plugin.codemig.codemig' and name not in sys.modules:
            # 仅包住该模块的加载执行期：模块体内 ENABLE_CRON_PERMANENT_DELETE=True
            # 分支拿到的 Process 是替身，import 结束后全局 Process 原样恢复
            with mock.patch.object(multiprocessing, 'Process', _NoForkProcess):
                return _real_import(name, globals, locals, fromlist, level)
        return _real_import(name, globals, locals, fromlist, level)

    builtins.__import__ = _hooked_import
