import json
import os
import pytest
from unittest.mock import patch, MagicMock

from config import Config, load_config_from_json


class TestLoadConfigFromJson:
    """测试 load_config_from_json 函数"""

    def test_load_valid_config(self, tmp_path):
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({"DB_TYPE": "mysql", "PORT": 3307}))
        result = load_config_from_json(str(config_file))
        assert result["DB_TYPE"] == "mysql"
        assert result["PORT"] == 3307

    def test_load_missing_file(self, tmp_path):
        result = load_config_from_json(str(tmp_path / "nonexistent.json"))
        assert result == {}

    def test_load_invalid_json(self, tmp_path):
        config_file = tmp_path / "config.json"
        config_file.write_text("{invalid json")
        result = load_config_from_json(str(config_file))
        assert result == {}

    def test_load_none_path(self):
        with patch.dict(os.environ, {}, clear=True):
            result = load_config_from_json(None)
            assert isinstance(result, dict)


class TestConfigGetConfig:
    """测试 Config._get_config 方法"""

    def test_env_variable_takes_priority(self):
        config = Config()
        with patch.dict(os.environ, {"DB_TYPE": "mysql_from_env"}):
            assert config._get_config("DB_TYPE", "sqlite") == "mysql_from_env"

    def test_json_config_used_when_no_env(self):
        config = Config()
        config._json_config = {"DB_TYPE": "from_json"}
        with patch.dict(os.environ, {}, clear=True):
            assert config._get_config("DB_TYPE", "sqlite") == "from_json"

    def test_default_value_when_nothing_set(self):
        config = Config()
        config._json_config = {}
        with patch.dict(os.environ, {}, clear=True):
            assert config._get_config("MISSING_KEY", "default_val") == "default_val"

    def test_bool_env_variable_true(self):
        config = Config()
        with patch.dict(os.environ, {"MY_BOOL": "true"}):
            assert config._get_config("MY_BOOL", False) is True

    def test_bool_env_variable_one(self):
        config = Config()
        with patch.dict(os.environ, {"MY_BOOL": "1"}):
            assert config._get_config("MY_BOOL", False) is True

    def test_bool_env_variable_false(self):
        config = Config()
        with patch.dict(os.environ, {"MY_BOOL": "false"}):
            assert config._get_config("MY_BOOL", False) is False

    def test_int_env_variable(self):
        config = Config()
        with patch.dict(os.environ, {"MY_INT": "8080"}):
            assert config._get_config("MY_INT", 8081) == 8080

    def test_int_env_variable_invalid_returns_default(self):
        config = Config()
        with patch.dict(os.environ, {"MY_INT": "not_a_number"}):
            assert config._get_config("MY_INT", 8081) == 8081

    def test_string_env_variable(self):
        config = Config()
        with patch.dict(os.environ, {"MY_KEY": "env_value"}):
            assert config._get_config("MY_KEY", "default") == "env_value"


class TestConfigProperties:
    """测试 Config 属性"""

    def setup_method(self):
        self.config = Config()
        self.config._json_config = {}

    def test_db_type_default(self):
        with patch.dict(os.environ, {}, clear=True):
            assert self.config.DB_TYPE == 'sqlite'

    def test_db_type_mysql(self):
        with patch.dict(os.environ, {"DB_TYPE": "MySQL"}):
            assert self.config.DB_TYPE == 'mysql'

    def test_secret_key_default(self):
        # 未配置时默认空串（不再内置可预测默认值）
        with patch.dict(os.environ, {}, clear=True):
            assert self.config.SECRET_KEY == ''

    def test_secret_key_from_env(self):
        with patch.dict(os.environ, {"key": "my-secret"}):
            assert self.config.SECRET_KEY == 'my-secret'

    def test_sqlite_database_uri_default(self):
        with patch.dict(os.environ, {}, clear=True):
            uri = self.config.SQLITE_DATABASE_URI
            assert uri.startswith('sqlite:///')
            assert 'codemig.db' in uri

    def test_sqlite_database_uri_custom(self):
        self.config._json_config = {"SQLITE_DATABASE_URI": "sqlite:///custom.db"}
        with patch.dict(os.environ, {}, clear=True):
            assert self.config.SQLITE_DATABASE_URI == "sqlite:///custom.db"

    def test_sqlite_use_encryption_true_when_not_debug(self):
        self.config._json_config = {}
        with patch.dict(os.environ, {"DEBUG": "false"}, clear=False):
            assert self.config.SQLITE_USE_ENCRYPTION is True

    def test_sqlite_use_encryption_false_when_debug(self):
        self.config._json_config = {}
        with patch.dict(os.environ, {"DEBUG": "true"}, clear=False):
            assert self.config.SQLITE_USE_ENCRYPTION is False

    def test_mysql_host_default(self):
        with patch.dict(os.environ, {}, clear=True):
            assert self.config.MYSQL_HOST == 'localhost'

    def test_mysql_port_default(self):
        with patch.dict(os.environ, {}, clear=True):
            assert self.config.MYSQL_PORT == 3306

    def test_mysql_user_default(self):
        with patch.dict(os.environ, {}, clear=True):
            assert self.config.MYSQL_USER == 'root'

    def test_mysql_database_default(self):
        with patch.dict(os.environ, {}, clear=True):
            assert self.config.MYSQL_DATABASE == 'codemig'

    def test_host_default(self):
        with patch.dict(os.environ, {}, clear=True):
            assert self.config.HOST == '0.0.0.0'

    def test_port_default(self):
        with patch.dict(os.environ, {}, clear=True):
            assert self.config.PORT == 8081

    def test_debug_default(self):
        with patch.dict(os.environ, {}, clear=True):
            assert self.config.DEBUG is False

    def test_debug_from_env(self):
        with patch.dict(os.environ, {"DEBUG": "true"}):
            assert self.config.DEBUG is True

    def test_sqlalchemy_echo_default(self):
        with patch.dict(os.environ, {}, clear=True):
            assert self.config.SQLALCHEMY_ECHO is False

    def test_sqlalchemy_database_uri_sqlite(self):
        self.config._json_config = {}
        with patch.dict(os.environ, {"DB_TYPE": "sqlite"}, clear=False):
            uri = self.config.SQLALCHEMY_DATABASE_URI
            assert uri.startswith('sqlite:///')

    def test_sqlalchemy_database_uri_mysql(self):
        self.config._json_config = {}
        with patch.dict(os.environ, {"DB_TYPE": "mysql"}, clear=False), \
             patch.object(type(self.config), 'MYSQL_PASSWORD',
                          new_callable=lambda: property(lambda s: 'pw')):
            uri = self.config.SQLALCHEMY_DATABASE_URI
            assert uri.startswith('mysql+pymysql://')

    def test_sqlite_password_debug_returns_none(self):
        self.config._json_config = {}
        with patch.dict(os.environ, {"DEBUG": "true"}, clear=False):
            assert self.config.SQLITE_PASSWORD is None

    def test_mysql_password_calls_get_key(self):
        with patch('config.get_key', return_value='decrypted_pw') as mock_gk:
            result = self.config.MYSQL_PASSWORD
            assert result == 'decrypted_pw'
            mock_gk.assert_called_once()

    def test_mysql_password_raises_on_failure(self):
        with patch('config.get_key', side_effect=Exception("decrypt fail")):
            with pytest.raises(RuntimeError, match="MySQL"):
                _ = self.config.MYSQL_PASSWORD

    def test_sqlite_password_not_debug_calls_get_key(self):
        self.config._json_config = {}
        with patch.dict(os.environ, {"DEBUG": "false"}, clear=False), \
             patch('config.get_key', return_value='sqlite_pw'):
            result = self.config.SQLITE_PASSWORD
            assert result == 'sqlite_pw'

    def test_sqlite_password_not_debug_raises_on_failure(self):
        self.config._json_config = {}
        with patch.dict(os.environ, {"DEBUG": "false"}, clear=False), \
             patch('config.get_key', side_effect=Exception("fail")):
            with pytest.raises(RuntimeError, match="SQLite"):
                _ = self.config.SQLITE_PASSWORD

    def test_track_modifications_is_false(self):
        assert self.config.SQLALCHEMY_TRACK_MODIFICATIONS is False

    def test_server_threads(self):
        assert self.config.SERVER_THREADS == 4
