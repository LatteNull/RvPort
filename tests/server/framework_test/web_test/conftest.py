import os.path
import shutil
import sys
import os

import pytest

import sqlite3
import tempfile

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
import common.db.SQLOperation as sql_op
from common.db.SQLOperation import DB_INFO, Base, engine as global_engine

MODULE_PATH = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..'))
if MODULE_PATH not in sys.path:
    sys.path.insert(0, MODULE_PATH)

# 添加测试目录到 Python 路径
# 注意：必须指向 tests/server（framework_test 的父目录）而非 framework_test 本身。
# framework_test 下存在与 server 同名的子包，若将其插入 sys.path 首位，
# server 下的模块导入可能解析到测试目录的同名包导致导入失败。
TEST_DIR = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..'))
if TEST_DIR not in sys.path:
    sys.path.insert(0, TEST_DIR)

try:
    from framework_test.public.random_pw import random_pw
except ImportError:
    # 如果导入失败，尝试使用相对路径
    import importlib.util
    random_pw_path = os.path.join(os.path.dirname(__file__), '..', 'public', 'random_pw.py')
    spec = importlib.util.spec_from_file_location("random_pw", random_pw_path)
    random_pw_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(random_pw_module)
    random_pw = random_pw_module.random_pw

import flask
from flask.testing import FlaskClient
from session_cache import UserSessionCache
from unittest.mock import patch, MagicMock

key = random_pw(15)


def setup_test_database_helper(create_tables=True, init_default_user=False):
    """
    辅助函数：设置测试数据库环境
    
    Args:
        create_tables: 是否创建表，默认为 True
        init_default_user: 是否初始化默认用户，默认为 False
    
    Yields:
        tuple: (db_path, original_engine, original_session, new_engine)
    """
    
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as test_db_file:
        db_path = test_db_file.name
    
    # 设置数据库路径
    old_file = DB_INFO.file
    DB_INFO.update_file(db_path)
    
    # 重新初始化引擎以使用测试数据库
    
    # 关闭旧引擎
    if hasattr(sql_op, 'engine'):
        global_engine.dispose()
    
    # 创建新引擎（测试环境不使用加密）
    new_engine = create_engine(
        f"sqlite:///{db_path}",
        echo=False,
        pool_pre_ping=True,
        connect_args={'check_same_thread': False}
    )
    
    # 创建新的会话工厂
    new_session_local = sessionmaker(bind=new_engine, autocommit=False, autoflush=False)
    new_db_session = scoped_session(new_session_local)
    
    # 临时替换全局变量
    original_engine = sql_op.engine
    original_session = sql_op.db_session
    sql_op.engine = new_engine
    sql_op.db_session = new_db_session
    
    # 根据参数决定是否创建表
    if create_tables:
        Base.metadata.create_all(bind=new_engine)
        
        # 如果需要，初始化默认用户
        if init_default_user:
            from framework.user_manager.user_db import UserManager
            UserManager.init_default_user()
    
    try:
        yield (db_path, original_engine, original_session, new_engine)
    finally:
        # 恢复原始引擎和会话
        sql_op.engine = original_engine
        sql_op.db_session = original_session
        if hasattr(sql_op, 'engine'):
            new_engine.dispose()
        DB_INFO.update_file(old_file)
        
        # 清理测试数据库
        if os.path.exists(db_path):
            os.remove(db_path)


@pytest.fixture(autouse=False)
def app():
    # 在导入 app 之前创建测试数据库并设置路径
    # 这样可以避免 SQLOperation 在模块级别使用错误的数据库路径

    # 保存原始环境变量
    old_env_uri = os.environ.get('SQLITE_DATABASE_URI')

    # 清空操作日志异步缓冲：log_buffer 是进程级单例，跨测试残留的日志条目
    # 会随本测试的 db_session 落到新建的临时库，污染日志计数断言。
    # 持 _flush_lock 先等在途批次落库（写旧库），再清空队列，
    # 防止"后台线程已取出批次、尚未提交"与建新库之间交错。
    from framework.log_manager.operation_log import log_buffer, OperationLog
    with log_buffer._flush_lock:
        with log_buffer._lock:
            log_buffer._queue.clear()

    # 使用共享的数据库设置函数
    for context in setup_test_database_helper(create_tables=True, init_default_user=True):
        db_path_name, original_engine, original_session, new_engine = context
        
        try:
            # 执行 SQL 脚本（用于初始化表结构）
            try:
                conn = sqlite3.connect(db_path_name)
                sql_file = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..',
                                                         'scripts', 'install', 'sqlite.sql'))
                with open(sql_file, "r") as f:
                    sql = f.read()
                    try:
                        conn.executescript(sql)
                        print(f"Executed SQL from: {sql_file}")
                    except Exception as e:
                        print(f"Executed SQL error from: {sql_file}: {e}")
                conn.commit()
                conn.close()
            except Exception as e:
                print(f"Error executing SQL scripts: {e}")
            
            # 设置环境变量，让 Config 使用测试数据库路径
            # 这需要在导入 app 之前设置，因为 SQLOperation 在模块级别会创建数据库引擎
            os.environ['SQLITE_DATABASE_URI'] = f'sqlite:///{db_path_name}'

            # 现在可以安全地导入 app 了
            # 注意：延迟导入是必要的，因为需要在设置环境变量后才能导入
            # 如果移到模块级别，SQLOperation 在导入时会使用错误的数据库路径
            from app import create_app
            from framework.config_manager.config import SysConfig
            
            SysConfig.list_all()
            UserSessionCache._cache = {}
            
            app_instance = create_app(key, {
                'TESTING': True,
                'db_file': db_path_name,
            })

            print(f"Created test database: {db_path_name}")
            # 测试期操作日志同步落库：把 log_buffer.push 替换为直接 insert，
            # 消除 HTTP 请求产生的日志与后续 list/csv 计数断言之间的异步竞态。
            # push 在 record 内被调用（同一线程），替换后 record 语义变为同步写库。
            def _sync_push(entry):
                with log_buffer._flush_lock:
                    OperationLog.insert(entry.user_id, entry.user_name, entry.ip,
                                        entry.module, entry.event, entry.result, entry.detail)

            with patch('framework.user_manager.user_update_cache._update_last_logout'), \
                 patch('framework.log_manager.operation_log.log_buffer.push', _sync_push), \
                 patch('framework.log_manager.operation_log.OperationLog.del_over_limit_log'):
                # del_over_limit_log 被屏蔽：后台 flush 线程每 12 个周期的自动清理
                # 会删除测试库日志，干扰精确计数断言；需要清理的测试显式调用
                # （test_checker.flush_and_cleanup 直接调 OperationLog 类方法不受影响）
                yield app_instance
        finally:
            # 恢复环境变量
            if old_env_uri is not None:
                os.environ['SQLITE_DATABASE_URI'] = old_env_uri
            elif 'SQLITE_DATABASE_URI' in os.environ:
                del os.environ['SQLITE_DATABASE_URI']
        
        # setup_test_database_helper 的 finally 块会处理引擎恢复和数据库清理
        break  # 只执行一次循环


@pytest.fixture(autouse=False)
def client(app):
    return app.test_client()


@pytest.fixture(autouse=False)
def runner(app):
    return app.test_cli_runner()


@pytest.fixture
def client_with_ip(app):
    print(f"Flask version: {flask.__version__}")
    print(f"FlaskClient: {FlaskClient}")
    """创建可以指定IP的client工厂"""
    def _client(ip_address='127.0.0.1'):
        return app.test_client(environ_base={
            'REMOTE_ADDR': ip_address,
            'HTTP_X_FORWARDED_FOR': ip_address,
            'HTTP_X_REAL_IP': ip_address
        })
    return _client