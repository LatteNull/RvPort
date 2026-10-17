VERSION = 'ZXW-CPU-ECO-KIT-V26.03.03'
CODE_MIG_VERSION = 'ZXW-CPU-ECO-KIT-V26.03.03'

# 说明：上面两个常量是「种子源」，仅用于
#   1) scripts/install_db.py 初始化时读取并写入 plugin 表；
#   2) 打包时由 update_version.sh 读取并烘焙进 agent（agent 是独立二进制，运行时读不到 DB）。
# 运行时一切版本取值统一走下面的 getter，从数据库 plugin 表读取。


def _query_plugin_version(plugin_type):
    """按 plugin_type 从 plugin 表取 current_version（运行时统一数据源）。

    延迟导入 DB 层，避免 version 模块在应用启动早期与 plugin_db / SQLOperation
    形成导入期耦合；查询失败或记录缺失时返回 None，由调用方回退。
    说明：query_version_by_type 内部已捕获数据库类异常并返回 None，
    这里只兜底延迟导入失败（plugin_db 依赖的应用上下文未就绪等场景）。
    """
    try:
        from framework.plugin_manager.plugin_db import Plugin
        return Plugin.query_version_by_type(plugin_type)
    except (ImportError, OSError, IOError):
        return None


def get_master_version():
    """框架版本：运行时取 plugin 表 framework 行，缺失时回退到 VERSION 常量。"""
    return _query_plugin_version('framework') or VERSION


def get_codemig_version():
    """codemig 版本：运行时取 plugin 表 codemig 行，缺失时回退到 CODE_MIG_VERSION 常量。"""
    return _query_plugin_version('codemig') or CODE_MIG_VERSION
