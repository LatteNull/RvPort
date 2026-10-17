import os
import sqlite3
import sys
import tempfile

import pytest
from unittest.mock import patch, MagicMock, PropertyMock

import common.db.SQLOperation as sql_op
from common.db.SQLOperation import (
    DatabaseException, DBInfo, db_session_scope, get_conn,
    get_connect_args, get_engine_kwargs, get_db, init_db,
    setup_sqlcipher_connection
)

# UT 用的假密钥素材（非真实密钥）：mock 注入用，须在被测模块白名单字符集内
TEST_KEY_MATERIAL = 'k3yMat3rialForUT'


class TestDatabaseException:
    """测试 DatabaseException 类"""

    def test_basic_message(self):
        exc = DatabaseException("test error")
        assert str(exc) == "test error"
        assert exc.original_exception is None
        assert exc.original_type is None

    def test_with_original_exception(self):
        original = ValueError("original")
        exc = DatabaseException("wrapped", original)
        assert exc.original_exception is original
        assert exc.original_type == "ValueError"

    def test_with_sqlite_error(self):
        original = sqlite3.Error("db error")
        exc = DatabaseException("sqlite error", original)
        assert exc.original_type == "Error"


class TestDBInfo:
    """测试 DBInfo 类"""

    def test_init_default(self):
        info = DBInfo()
        assert info.file is None
        assert info.key is None

    def test_init_with_values(self):
        info = DBInfo(file="/path/to/db", key="secret")
        assert info.file == "/path/to/db"
        assert info.key == "secret"

    def test_update_key(self):
        info = DBInfo()
        info.update_key("new-key")
        assert info.key == "new-key"

    def test_update_file_resets_key(self):
        info = DBInfo(key="old-key")
        info.update_file("/new/path/db")
        assert info.file == "/new/path/db"
        assert info.key is None


class TestGetConnectArgs:
    """测试 get_connect_args 函数"""

    def test_sqlite_type(self):
        with patch.object(type(sql_op._config_instance), 'DB_TYPE',
                          new_callable=PropertyMock, return_value='sqlite'):
            args = get_connect_args()
            assert args['check_same_thread'] is False

    def test_mysql_type(self):
        with patch.object(type(sql_op._config_instance), 'DB_TYPE',
                          new_callable=PropertyMock, return_value='mysql'):
            args = get_connect_args()
            assert args == {}

    def test_other_type(self):
        with patch.object(type(sql_op._config_instance), 'DB_TYPE',
                          new_callable=PropertyMock, return_value='postgresql'):
            args = get_connect_args()
            assert args == {}


class TestGetEngineKwargs:
    """测试 get_engine_kwargs 函数"""

    def test_sqlite_kwargs(self):
        with patch.object(type(sql_op._config_instance), 'DB_TYPE',
                          new_callable=PropertyMock, return_value='sqlite'):
            kwargs = get_engine_kwargs()
            assert kwargs['echo'] is False
            assert kwargs['pool_pre_ping'] is True
            assert 'connect_args' in kwargs
            assert kwargs['connect_args']['check_same_thread'] is False
            assert 'pool_recycle' not in kwargs

    def test_mysql_kwargs(self):
        with patch.object(type(sql_op._config_instance), 'DB_TYPE',
                          new_callable=PropertyMock, return_value='mysql'):
            kwargs = get_engine_kwargs()
            assert kwargs['pool_recycle'] == 3600
            # 读写分离: 默认写池 10
            assert kwargs['pool_size'] == 10
            assert kwargs['max_overflow'] == 5

    def test_mysql_kwargs_read_role(self):
        with patch.object(type(sql_op._config_instance), 'DB_TYPE',
                          new_callable=PropertyMock, return_value='mysql'):
            kwargs = get_engine_kwargs(role='read')
            assert kwargs['pool_recycle'] == 3600
            assert kwargs['pool_size'] == 40
            assert kwargs['max_overflow'] == 10

    def test_sqlite_kwargs_read_role(self):
        with patch.object(type(sql_op._config_instance), 'DB_TYPE',
                          new_callable=PropertyMock, return_value='sqlite'):
            kwargs = get_engine_kwargs(role='read')
            assert kwargs['pool_size'] == 30


class TestSetupSqlcipherConnection:
    """测试 setup_sqlcipher_connection 函数"""

    def test_no_encryption(self):
        mock_conn = MagicMock()
        with patch.object(type(sql_op._config_instance), 'DB_TYPE',
                          new_callable=PropertyMock, return_value='sqlite'), \
             patch.object(type(sql_op._config_instance), 'SQLITE_USE_ENCRYPTION',
                          new_callable=PropertyMock, return_value=False):
            setup_sqlcipher_connection(mock_conn, None)
            mock_conn.cursor.assert_not_called()

    def test_with_encryption(self):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch.object(type(sql_op._config_instance), 'DB_TYPE',
                          new_callable=PropertyMock, return_value='sqlite'), \
             patch.object(type(sql_op._config_instance), 'SQLITE_USE_ENCRYPTION',
                          new_callable=PropertyMock, return_value=True), \
             patch.object(type(sql_op._config_instance), 'SQLITE_PASSWORD',
                          new_callable=PropertyMock, return_value=TEST_KEY_MATERIAL):
            setup_sqlcipher_connection(mock_conn, None)
            mock_conn.cursor.assert_called_once()
            mock_cursor.execute.assert_called_once()
            # 拼接与执行分离：execute 收到完整语句，期望值由被测模块模板构造
            expected = sql_op._PRAGMA_KEY_TEMPLATE.format(TEST_KEY_MATERIAL)
            assert mock_cursor.execute.call_args[0][0] == expected
            mock_cursor.close.assert_called_once()

    def test_password_with_single_quote_escaped(self):
        """白名单校验：含单引号的密码直接拒绝（防注入主防线），不再进入拼接。

        原"转义后放行"（pass''word）语义已被 _quote_pragma_value 白名单取代：
        PRAGMA 不支持参数绑定，任何含 SQL 语义字符的密码一律 ValueError。
        """
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch.object(type(sql_op._config_instance), 'DB_TYPE',
                          new_callable=PropertyMock, return_value='sqlite'), \
             patch.object(type(sql_op._config_instance), 'SQLITE_USE_ENCRYPTION',
                          new_callable=PropertyMock, return_value=True), \
             patch.object(type(sql_op._config_instance), 'SQLITE_PASSWORD',
                          new_callable=PropertyMock, return_value="pass'word"):
            with pytest.raises(ValueError):
                setup_sqlcipher_connection(mock_conn, None)
            mock_cursor.execute.assert_not_called()

    def test_password_hex_like_accepted(self):
        """白名单内的合法密码（字母数字+常规符号）正常建连。"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        # 现网密钥形态（含符号），断言只做包含性检查、不拼出完整语句字面量
        key_material = "9!G^UpsJvtYrM%#^"

        with patch.object(type(sql_op._config_instance), 'DB_TYPE',
                          new_callable=PropertyMock, return_value='sqlite'), \
             patch.object(type(sql_op._config_instance), 'SQLITE_USE_ENCRYPTION',
                          new_callable=PropertyMock, return_value=True), \
             patch.object(type(sql_op._config_instance), 'SQLITE_PASSWORD',
                          new_callable=PropertyMock, return_value=key_material):
            setup_sqlcipher_connection(mock_conn, None)
            call_args = mock_cursor.execute.call_args[0][0]
            assert key_material in call_args
            assert sql_op._PRAGMA_KEY_TEMPLATE.format(key_material) == call_args


class TestGetConn:
    """测试 get_conn 函数"""

    def test_file_none_raises_error(self):
        with pytest.raises(ValueError, match="file parameter cannot be None"):
            get_conn(None)

    def test_debug_mode_uses_sqlite3(self, tmp_path):
        db_file = str(tmp_path / "test.db")
        with patch.object(type(sql_op._config_instance), 'DEBUG',
                          new_callable=PropertyMock, return_value=True):
            conn = get_conn(db_file)
            assert conn is not None
            conn.close()

    def test_creates_parent_directory(self, tmp_path):
        db_file = str(tmp_path / "subdir" / "test.db")
        with patch.object(type(sql_op._config_instance), 'DEBUG',
                          new_callable=PropertyMock, return_value=True):
            conn = get_conn(db_file)
            assert os.path.exists(os.path.dirname(db_file))
            conn.close()

    def test_non_debug_mode_uses_sqlcipher(self, tmp_path):
        db_file = str(tmp_path / "test_cipher.db")

        with patch.object(type(sql_op._config_instance), 'DEBUG',
                          new_callable=PropertyMock, return_value=False), \
             patch('common.db.SQLOperation.get_key', return_value=TEST_KEY_MATERIAL), \
             patch('common.db.SQLOperation.sqlcipher3') as mock_sqlcipher:
            mock_conn = MagicMock()
            mock_sqlcipher.connect.return_value = mock_conn
            result = get_conn(db_file)
            assert result is mock_conn
            mock_sqlcipher.connect.assert_called_once()
            # get_conn 与 setup_sqlcipher_connection 走同一拼接/执行分离路径
            execute_args = [c[0][0] for c in mock_conn.execute.call_args_list]
            expected = sql_op._PRAGMA_KEY_TEMPLATE.format(TEST_KEY_MATERIAL)
            assert expected in execute_args


class TestDbSessionScope:
    """测试 db_session_scope 上下文管理器"""

    def test_successful_session(self):
        mock_session = MagicMock()
        with patch.object(sql_op, 'db_session', return_value=mock_session):
            with db_session_scope() as session:
                assert session is mock_session
            mock_session.commit.assert_called_once()
            mock_session.close.assert_called()

    def test_sqlite_error_raises_database_exception(self):
        mock_session = MagicMock()
        mock_session.commit.side_effect = sqlite3.Error("sqlite error")

        with patch.object(sql_op, 'db_session', return_value=mock_session):
            with pytest.raises(DatabaseException, match="SQLite database error"):
                with db_session_scope():
                    pass
            mock_session.rollback.assert_called_once()

    def test_sqlalchemy_error_raises_database_exception(self):
        from sqlalchemy.exc import SQLAlchemyError
        mock_session = MagicMock()
        mock_session.commit.side_effect = SQLAlchemyError("sa error")

        with patch.object(sql_op, 'db_session', return_value=mock_session):
            with pytest.raises(DatabaseException, match="SQLAlchemy error"):
                with db_session_scope():
                    pass
            mock_session.rollback.assert_called_once()


class TestGetDb:
    """测试 get_db 生成器"""

    def test_yields_session_and_closes(self):
        mock_session = MagicMock()
        with patch.object(sql_op, 'db_session', return_value=mock_session):
            gen = get_db()
            session = next(gen)
            assert session is mock_session
            mock_session.close.assert_not_called()
            try:
                next(gen)
            except StopIteration:
                pass
            mock_session.close.assert_called_once()
