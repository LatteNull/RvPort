"""codemig_dir_manager 测试公共隔离：mock 消费模块内的 record_operation_log。

codemig_dir_processor.py / views.py 通过
    from framework.log_manager.operation_log import record_operation_log
持有函数的本地引用——patch 源模块属性不影响已导入的副本，需 patch 各
消费模块内的名字。autouse fixture 对本目录全部用例统一生效；测试内已有
的单点 patch 语义相同，保留无害。
"""
import pytest


@pytest.fixture(autouse=True)
def _no_operation_log(mocker):
    mocker.patch(
        'plugin.codemig.codemig_dir_manager.codemig_dir_processor.record_operation_log')
    mocker.patch('plugin.codemig.codemig_dir_manager.views.record_operation_log')
