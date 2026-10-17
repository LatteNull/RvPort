import os
import sys
import importlib.util

import pytest
import sqlite3


from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session

MODULE_PATH = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..'))
if MODULE_PATH not in sys.path:
    sys.path.append(MODULE_PATH)
import common.db.SQLOperation as sql_op
from framework.user_manager.user_db import UserManager, Role, encrypt_password, UserStatus
from common.db.SQLOperation import DB_INFO, Base
from framework_test.public.random_pw import random_pw

test_pw = random_pw()
test_pw2 = random_pw()
sql_file = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..',
                                         'scripts', 'install', 'sqlite.sql'))

# 导入 conftest 中的共享函数
# 使用 importlib 导入，因为 conftest 在 pytest 中的加载机制特殊
_conftest_path = os.path.join(os.path.dirname(__file__), 'conftest.py')
_conftest_spec = importlib.util.spec_from_file_location("conftest_module", _conftest_path)
_conftest_module = importlib.util.module_from_spec(_conftest_spec)
_conftest_spec.loader.exec_module(_conftest_module)
setup_test_database_helper = _conftest_module.setup_test_database_helper

class TestUserManager:

    def _recreate_engine_for_path(self, db_path):
        """辅助函数：为指定路径重新创建引擎和会话（用于删除数据库文件后的场景）"""
        # 直接使用 conftest 中的共享函数，但需要确保使用指定的路径
        
        # 保存当前状态
        original_engine = sql_op.engine
        original_session = sql_op.db_session
        
        # 关闭旧引擎
        if hasattr(sql_op, 'engine') and sql_op.engine:
            sql_op.engine.dispose()
        
        # 设置数据库路径
        DB_INFO.update_file(db_path)
        
        # 创建新引擎
        new_engine = create_engine(
            f"sqlite:///{db_path}",
            echo=False,
            pool_pre_ping=True,
            connect_args={'check_same_thread': False}
        )
        new_session_local = sessionmaker(bind=new_engine, autocommit=False, autoflush=False)
        new_db_session = scoped_session(new_session_local)
        
        # 临时替换
        sql_op.engine = new_engine
        sql_op.db_session = new_db_session
        
        # 创建表（使用 ORM 的 Base.metadata.create_all）
        Base.metadata.create_all(bind=new_engine)
        
        return original_engine, original_session, new_engine

    @pytest.fixture(scope="function")
    def setup_db(self):
        """设置测试数据库环境，执行 SQL 脚本并初始化默认用户"""
        # 使用 conftest.py 中的共享函数设置数据库
        for context in setup_test_database_helper(create_tables=True, init_default_user=True):
            db_path, original_engine, original_session, new_engine = context
            
            # 执行 SQL 脚本（如果需要，用于初始化表结构）
            try:
                conn = sqlite3.connect(db_path)
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
                print(f"Error executing SQL script: {e}")
            
            # 返回一个对象，其 name 属性是数据库路径（保持向后兼容）
            yield type('obj', (object,), {'name': db_path})()

    def test_encrypt_password(self):
        pwwwwd = test_pw
        encrypted_pw = encrypt_password(pwwwwd)

        # 断言加密密码的效果
        assert isinstance(encrypted_pw, str)
        assert encrypted_pw != pwwwwd  # 确保密码被加密
        assert len(encrypted_pw) > len(pwwwwd)  # 假设加密后长度增加

    def test_save_user(self, setup_db):
        result, user_id = UserManager.save('testuser', Role.NORMAL, test_pw)
        assert result is True
        assert user_id is not None

    def test_save_user_exception(self, setup_db):
        # ORM 在数据库文件不存在时会创建新数据库，所以这个测试需要调整
        # 测试删除数据库文件后的行为：ORM 会创建新数据库，但新数据库是空的
        db_path = setup_db.name
        os.remove(db_path)  # 删除测试数据库
        
        # setup_db fixture 已经设置了引擎和会话，但删除文件后需要重新创建引擎
        # 因为连接池可能仍持有对已删除文件的引用
        
        # 使用辅助函数重新创建引擎
        original_engine, original_session, new_engine = self._recreate_engine_for_path(db_path)
        
        try:
            # 尝试保存用户（应该成功，因为 ORM 会创建新数据库）
            result, user_id = UserManager.save('testuser', Role.NORMAL, test_pw)
            # ORM 创建新数据库后，保存应该成功
            assert result is True, "ORM 应该能够创建新数据库并保存用户"
            assert user_id is not None, "应该返回有效的 user_id"
        finally:
            # 恢复（虽然 setup_db fixture 会恢复，但为了清晰，这里也恢复）
            sql_op.engine = original_engine
            sql_op.db_session = original_session
            new_engine.dispose()

    def test_list_all_users(self, setup_db):
        # 确保初始化默认用户
        UserManager.init_default_user()
        
        users = UserManager.list_all_local()
        # 初始应该有 Admin 用户（由 init_default_user 创建）
        admin_count = sum(1 for u in users if u.user_name == 'Admin')
        assert admin_count >= 1, f"应该至少有一个 Admin 用户，实际用户列表: {[u.user_name for u in users]}"
        
        # 保存新用户
        UserManager.save('testuser', Role.NORMAL, test_pw)
        users = UserManager.list_all_local()
        
        # 验证新用户已添加
        testuser_count = sum(1 for u in users if u.user_name == 'testuser')
        assert testuser_count == 1, f"应该有一个 testuser 用户，实际用户列表: {[u.user_name for u in users]}"
        
        # 验证用户对象类型
        testuser = next((u for u in users if u.user_name == 'testuser'), None)
        assert testuser is not None
        assert isinstance(testuser, UserManager)
        assert testuser.user_name == 'testuser'

    def test_list_all_users_exception(self, setup_db):
        # ORM 在数据库文件不存在时会尝试创建新数据库
        # 这个测试需要调整：删除数据库后，ORM 可能会创建新数据库
        # 测试删除数据库文件后的行为
        db_path = setup_db.name
        os.remove(db_path)  # 删除测试数据库
        
        # 使用辅助函数重新创建引擎（使用指定的路径）
        original_engine, original_session, new_engine = self._recreate_engine_for_path(db_path)
        
        try:
            users = UserManager.list_all_local()
            # ORM 创建新数据库后，应该返回空列表或只有默认用户
            assert users is not None
            # 新数据库可能是空的，或者有默认的 Admin 用户
        finally:
            # 恢复（虽然 setup_db fixture 会恢复，但为了清晰，这里也恢复）
            sql_op.engine = original_engine
            sql_op.db_session = original_session
            new_engine.dispose()

    def test_update_user(self, setup_db):
        status, test_id = UserManager.save('testuser', Role.NORMAL, test_pw)
        assert UserManager.query_by_id(test_id).is_first_login == 1
        result = UserManager.update(test_id, is_first_login=0, status=UserStatus.NORMAL)
        assert result is True
        tester = UserManager.query_by_id(test_id)
        assert tester.is_first_login == 0

    def test_update_user_exception(self, setup_db):
        os.remove(setup_db.name)  # 删除测试数据库
        result = UserManager.update('0', is_first_login=0, status=UserStatus.NORMAL)
        assert result is False

    def test_delete_user(self, setup_db):
        status, test_id = UserManager.save('testuser', Role.NORMAL, test_pw)
        initial_count = len(UserManager.list_all_local())
        assert initial_count >= 1, "初始应该至少有一个用户（Admin）"
        
        # 删除测试用户
        UserManager.delete_user(test_id)
        final_count = len(UserManager.list_all_local())
        
        # 验证用户已删除
        assert final_count == initial_count - 1, f"删除后用户数应该减少1（从 {initial_count} 到 {final_count}）"
        
        # 验证 testuser 已不存在
        testuser = UserManager.query_by_id(test_id)
        assert testuser is None, "testuser 应该已被删除"

    def test_delete_user_exception(self, setup_db):
        os.remove(setup_db.name)  # 删除测试数据库
        status = UserManager.delete_user(0)
        assert status is False

    def test_query_by_id(self, setup_db):
        status, test_id = UserManager.save('testuser', Role.NORMAL, test_pw)
        status, test_id2 = UserManager.save('testuser2', Role.NORMAL, test_pw2)
        assert UserManager.query_by_id(test_id).user_name == 'testuser'
        assert UserManager.query_by_id(test_id2).user_name == 'testuser2'
        assert UserManager.query_by_id(0) is None

    def test_query_with_selector(self, setup_db):
        status, test_id = UserManager.save('testuser', Role.NORMAL, test_pw)
        status, test_id2 = UserManager.save('testuser2', Role.ADMIN, test_pw2)

        assert UserManager.query(nopw=False, user_id=test_id).user_name == 'testuser'
        assert UserManager.query(nopw=False, user_name='testuser2').user_id == test_id2
        assert UserManager.query(nopw=False, user_name='xx') is None
