"""models.py 单元测试 - UserApiKey ORM"""
import pytest
from unittest.mock import MagicMock, patch
from contextlib import contextmanager

from plugin.codemig.ai_assistant.models import UserApiKey


def _make_api_key_record(api_key_id=1, user_id="user1", api_key=b"encrypted",
                         base_url="http://api.test", model="gpt-4",
                         api_format="openai", is_default=False,
                         others="", create_time=None):
    """构造一个模拟的 UserApiKey ORM 对象"""
    from datetime import datetime
    record = MagicMock(spec=UserApiKey)
    record.api_key_id = api_key_id
    record.user_id = user_id
    record.api_key = api_key
    record.base_url = base_url
    record.model = model
    record.api_format = api_format
    record.is_default = is_default
    record.others = others
    record.create_time = create_time or datetime(2025, 1, 1, 12, 0, 0)
    return record


def _make_user(user_id="user1", user_name="testuser", role="normal"):
    """构造一个模拟的 UserManager 对象"""
    user = MagicMock()
    user.user_id = user_id
    user.user_name = user_name
    user.role = role
    return user


@contextmanager
def _mock_session():
    """创建一个 mock 的 db_session_scope，返回 session 以便进一步配置"""
    session = MagicMock()
    yield session


def _setup_session(scope_mock, session):
    """把 mock_scope 配置成进入后返回 session"""
    scope_mock.return_value.__enter__ = MagicMock(return_value=session)
    scope_mock.return_value.__exit__ = MagicMock(return_value=False)


def _make_session_with_admins(admin_user_ids=None, first_record=None,
                              all_records=None, user_selection=None,
                              default_selection=None):
    """
    构造一个能区分 query(UserApiKey) / query(UserManager) / query(UserModelSelection)
    / query(UserDefaultSelection) 的 session。
    admin_user_ids: list[int|str]，作为 admin 用户
    first_record: query(UserApiKey).filter().first() 的返回值
    all_records: query(UserApiKey).all() 的返回值
    user_selection: query(UserModelSelection).filter().first() 的返回值
    default_selection: query(UserDefaultSelection).filter().first() 的返回值
    """
    session = MagicMock()

    admin_users = [_make_user(user_id=uid, user_name=f"admin_{uid}", role="admin")
                   for uid in (admin_user_ids or [])]

    api_key_q = MagicMock()
    api_key_q.filter.return_value.first.return_value = first_record
    api_key_q.all.return_value = all_records if all_records is not None else []
    # filter 链式调用：filter().filter()... 仍然返回自己
    api_key_q.filter.return_value.filter.return_value = api_key_q.filter.return_value
    api_key_q.filter.return_value.order_by.return_value.first.return_value = first_record
    api_key_q.filter.return_value.order_by.return_value = api_key_q.filter.return_value.order_by.return_value

    user_q = MagicMock()
    user_q.filter.return_value.all.return_value = admin_users

    selection_q = MagicMock()
    selection_q.filter.return_value.first.return_value = user_selection
    selection_q.filter.return_value.delete.return_value = None
    selection_q.filter.return_value.update.return_value = None

    default_sel_q = MagicMock()
    default_sel_q.filter.return_value.first.return_value = default_selection
    default_sel_q.filter.return_value.delete.return_value = None

    def query_side_effect(model_cls, *args, **kwargs):
        name = getattr(model_cls, '__name__', '')
        if name == 'UserApiKey':
            return api_key_q
        if name == 'UserManager':
            return user_q
        if name == 'UserModelSelection':
            return selection_q
        if name == 'UserDefaultSelection':
            return default_sel_q
        # 兜底
        return api_key_q

    session.query.side_effect = query_side_effect
    # update/delete on api_key_q
    api_key_q.filter.return_value.update.return_value = None
    api_key_q.filter.return_value.delete.return_value = None
    return session


# ---------------------------------------------------------------------------
# UserApiKey._get_admin_user_ids
# ---------------------------------------------------------------------------
class TestGetAdminUserIds:
    @patch('plugin.codemig.ai_assistant.models.db_session_scope')
    def test_returns_id_and_str_forms(self, mock_scope):
        """返回 admin 用户的 int 与 str 两种形式，方便后续比较"""
        session = _make_session_with_admins(admin_user_ids=[1, 2])
        _setup_session(mock_scope, session)

        result = UserApiKey._get_admin_user_ids(session)
        assert 1 in result and 2 in result
        assert "1" in result and "2" in result

    @patch('plugin.codemig.ai_assistant.models.db_session_scope')
    def test_empty_when_no_admins(self, mock_scope):
        session = _make_session_with_admins(admin_user_ids=[])
        _setup_session(mock_scope, session)

        result = UserApiKey._get_admin_user_ids(session)
        assert result == set()

    @patch('plugin.codemig.ai_assistant.models.db_session_scope')
    def test_skips_none_user_id(self, mock_scope):
        """user_id 为 None 的记录被过滤掉"""
        admin_with_none = _make_user(user_id=None, role="admin")
        admin_ok = _make_user(user_id=5, role="admin")

        session = MagicMock()
        user_q = MagicMock()
        user_q.filter.return_value.all.return_value = [admin_with_none, admin_ok]
        session.query.return_value = user_q

        result = UserApiKey._get_admin_user_ids(session)
        assert 5 in result
        assert None not in result


# ---------------------------------------------------------------------------
# UserApiKey.del_api_key
# ---------------------------------------------------------------------------
class TestDelApiKey:
    @patch('plugin.codemig.ai_assistant.models.db_session_scope')
    def test_success_as_admin(self, mock_scope):
        """admin 可以删除任意 key"""
        record = _make_api_key_record(user_id="other_user")
        session = _make_session_with_admins(admin_user_ids=[1], first_record=record)
        _setup_session(mock_scope, session)

        result = UserApiKey.del_api_key("user1", 1, is_admin=True)
        assert result == 0
        session.delete.assert_called_once_with(record)

    @patch('plugin.codemig.ai_assistant.models.db_session_scope')
    def test_success_as_owner(self, mock_scope):
        """普通用户删除自己的 key"""
        record = _make_api_key_record(user_id="user1")
        session = _make_session_with_admins(admin_user_ids=[2], first_record=record)
        _setup_session(mock_scope, session)

        result = UserApiKey.del_api_key("user1", 1, is_admin=False)
        assert result == 0

    @patch('plugin.codemig.ai_assistant.models.db_session_scope')
    def test_not_found(self, mock_scope):
        session = _make_session_with_admins(admin_user_ids=[], first_record=None)
        _setup_session(mock_scope, session)

        result = UserApiKey.del_api_key("user1", 999)
        assert result == -2

    @patch('plugin.codemig.ai_assistant.models.db_session_scope')
    def test_reject_other_normal_users_key(self, mock_scope):
        """普通用户不能删除其他普通用户的 key"""
        record = _make_api_key_record(user_id="other_normal")
        session = _make_session_with_admins(admin_user_ids=[10], first_record=record)
        _setup_session(mock_scope, session)

        result = UserApiKey.del_api_key("user1", 1, is_admin=False)
        assert result == -3

    @patch('plugin.codemig.ai_assistant.models.db_session_scope')
    def test_reject_admin_key_as_normal_user(self, mock_scope):
        """普通用户不能删除 admin 的 key"""
        record = _make_api_key_record(user_id="10")  # 属于 admin
        session = _make_session_with_admins(admin_user_ids=[10], first_record=record)
        _setup_session(mock_scope, session)

        result = UserApiKey.del_api_key("user1", 1, is_admin=False)
        assert result == -3

    @patch('plugin.codemig.ai_assistant.models.db_session_scope')
    def test_db_error(self, mock_scope):
        from common.db.SQLOperation import DatabaseException
        mock_scope.side_effect = DatabaseException("db error")

        result = UserApiKey.del_api_key("user1", 1)
        assert result == -1


# ---------------------------------------------------------------------------
# UserApiKey.store
# ---------------------------------------------------------------------------
class TestStore:
    @patch('plugin.codemig.ai_assistant.models.db_session_scope')
    def test_success(self, mock_scope):
        session = MagicMock()
        def fake_flush():
            for obj in session.add.call_args_list:
                created = obj[0][0]
                created.api_key_id = 42
        session.flush.side_effect = fake_flush
        _setup_session(mock_scope, session)

        result, new_id = UserApiKey.store("user1", b"enc", "http://a", "gpt-4", "openai", "", False)
        assert result == 0
        assert new_id == 42

    @patch('plugin.codemig.ai_assistant.models.db_session_scope')
    def test_unique_constraint(self, mock_scope):
        from common.db.SQLOperation import DatabaseException
        mock_scope.side_effect = DatabaseException("UNIQUE constraint failed")

        result, new_id = UserApiKey.store("user1", b"enc", "http://a", "gpt-4", "openai", "", False)
        assert result == -2
        assert new_id is None

    @patch('plugin.codemig.ai_assistant.models.db_session_scope')
    def test_other_db_error(self, mock_scope):
        from common.db.SQLOperation import DatabaseException
        mock_scope.side_effect = DatabaseException("some other error")

        result, new_id = UserApiKey.store("user1", b"enc", "http://a", "gpt-4", "openai", "", False)
        assert result == -1
        assert new_id is None

    @patch('plugin.codemig.ai_assistant.models.db_session_scope')
    def test_os_error(self, mock_scope):
        mock_scope.side_effect = OSError("disk full")

        result, new_id = UserApiKey.store("user1", b"enc", "http://a", "gpt-4", "openai", "", False)
        assert result == -1


# ---------------------------------------------------------------------------
# UserApiKey.get_agent_config
# ---------------------------------------------------------------------------
class TestGetAgentConfig:
    @patch('plugin.codemig.ai_assistant.models.decrypt_passphrase', return_value="sk-123")
    @patch('plugin.codemig.ai_assistant.models.db_session_scope')
    def test_admin_success(self, mock_scope, mock_decrypt):
        """admin 直接拿到第一条记录"""
        record = _make_api_key_record(model="gpt-4", api_key=b"enc_data")
        session = _make_session_with_admins(admin_user_ids=[1], first_record=record)
        _setup_session(mock_scope, session)

        result, config = UserApiKey.get_agent_config("gpt-4", user_id=1, is_admin=True)
        assert result == 0
        assert config["api_key"] == "sk-123"
        assert config["model"] == "gpt-4"

    @patch('plugin.codemig.ai_assistant.models.decrypt_passphrase', return_value="sk-123")
    @patch('plugin.codemig.ai_assistant.models.db_session_scope')
    def test_normal_user_success(self, mock_scope, mock_decrypt):
        """普通用户在可见范围内拿到记录"""
        record = _make_api_key_record(model="gpt-4", user_id="user1")
        session = _make_session_with_admins(admin_user_ids=[10], first_record=record)
        _setup_session(mock_scope, session)

        result, config = UserApiKey.get_agent_config("gpt-4", user_id="user1", is_admin=False)
        assert result == 0
        assert config["api_key"] == "sk-123"

    @patch('plugin.codemig.ai_assistant.models.decrypt_passphrase', return_value="sk-123")
    @patch('plugin.codemig.ai_assistant.models.db_session_scope')
    def test_normal_user_with_manual_selection(self, mock_scope, mock_decrypt):
        """普通用户在 user_model_selection 中有手动选中"""
        record = _make_api_key_record(model="gpt-4", user_id="user1")
        selection = MagicMock()
        selection.api_key_id = 5
        session = _make_session_with_admins(
            admin_user_ids=[10], first_record=record, user_selection=selection)
        _setup_session(mock_scope, session)

        result, config = UserApiKey.get_agent_config("gpt-4", user_id="user1", is_admin=False)
        assert result == 0
        assert config["model"] == "gpt-4"

    @patch('plugin.codemig.ai_assistant.models.db_session_scope')
    def test_admin_not_found(self, mock_scope):
        session = _make_session_with_admins(admin_user_ids=[], first_record=None)
        _setup_session(mock_scope, session)

        result, config = UserApiKey.get_agent_config("unknown", user_id=1, is_admin=True)
        assert result == -2
        assert config is None

    @patch('plugin.codemig.ai_assistant.models.db_session_scope')
    def test_normal_user_not_in_scope(self, mock_scope):
        """普通用户查不到记录也返回 -2"""
        session = _make_session_with_admins(admin_user_ids=[10], first_record=None)
        _setup_session(mock_scope, session)

        result, config = UserApiKey.get_agent_config("unknown", user_id="user1", is_admin=False)
        assert result == -2

    @patch('plugin.codemig.ai_assistant.models.db_session_scope')
    def test_db_error(self, mock_scope):
        from common.db.SQLOperation import DatabaseException
        mock_scope.side_effect = DatabaseException("error")

        result, config = UserApiKey.get_agent_config("gpt-4")
        assert result == -1


# ---------------------------------------------------------------------------
# UserApiKey.get_all_api_keys
# ---------------------------------------------------------------------------
class TestGetAllApiKeys:
    @patch('plugin.codemig.ai_assistant.models.decrypt_passphrase', return_value="sk-abcdef123456")
    @patch('plugin.codemig.ai_assistant.models.db_session_scope')
    def test_admin_returns_all(self, mock_scope, mock_decrypt):
        """admin 拿到所有记录"""
        record = _make_api_key_record(user_id="user1")
        user = _make_user(user_id="user1", user_name="testuser")

        session = MagicMock()

        api_key_q = MagicMock()
        api_key_q.all.return_value = [record]
        # admin 分支不调 filter，但兜底
        api_key_q.filter.return_value = api_key_q

        user_q = MagicMock()
        user_q.filter.return_value.all.return_value = [user]

        def query_side_effect(model_cls, *args, **kwargs):
            name = getattr(model_cls, '__name__', '')
            if name == 'UserApiKey':
                return api_key_q
            if name == 'UserManager':
                return user_q
            return api_key_q

        session.query.side_effect = query_side_effect
        _setup_session(mock_scope, session)

        result, apikey_list = UserApiKey.get_all_api_keys(user_id=1, is_admin=True)
        assert result == 0
        assert len(apikey_list) == 1
        assert apikey_list[0]["api_key"] == "sk-abcde"
        assert apikey_list[0]["user_name"] == "testuser"

    @patch('plugin.codemig.ai_assistant.models.decrypt_passphrase', return_value="sk-test")
    @patch('plugin.codemig.ai_assistant.models.db_session_scope')
    def test_normal_user_filtered_to_visible(self, mock_scope, mock_decrypt):
        """普通用户只看自己的 + admin 的 key"""
        record = _make_api_key_record(user_id="user1")
        admin_user = _make_user(user_id="admin1", user_name="admin", role="admin")
        normal_user = _make_user(user_id="user1", user_name="u1")

        session = MagicMock()
        api_key_q = MagicMock()
        api_key_q.filter.return_value = api_key_q
        api_key_q.filter.return_value.all.return_value = [record]
        api_key_q.all.return_value = [record]

        user_q = MagicMock()
        # 第一次：_get_admin_user_ids 调用；第二次：根据 user_id 批量取 user_name
        user_q.filter.return_value.all.return_value = [admin_user, normal_user]

        def query_side_effect(model_cls, *args, **kwargs):
            name = getattr(model_cls, '__name__', '')
            if name == 'UserApiKey':
                return api_key_q
            if name == 'UserManager':
                return user_q
            return api_key_q

        session.query.side_effect = query_side_effect
        _setup_session(mock_scope, session)

        result, apikey_list = UserApiKey.get_all_api_keys(user_id="user1", is_admin=False)
        assert result == 0
        assert len(apikey_list) == 1

    @patch('plugin.codemig.ai_assistant.models.decrypt_passphrase',
           side_effect=UnicodeDecodeError("utf-8", b"", 0, 1, "err"))
    @patch('plugin.codemig.ai_assistant.models.db_session_scope')
    def test_decrypt_failure_fallback_empty(self, mock_scope, mock_decrypt):
        record = _make_api_key_record(user_id="user1", api_key=b"bad_data")

        session = MagicMock()
        api_key_q = MagicMock()
        api_key_q.all.return_value = [record]
        api_key_q.filter.return_value = api_key_q
        user_q = MagicMock()
        user_q.filter.return_value.all.return_value = []

        def query_side_effect(model_cls, *args, **kwargs):
            name = getattr(model_cls, '__name__', '')
            return api_key_q if name == 'UserApiKey' else user_q

        session.query.side_effect = query_side_effect
        _setup_session(mock_scope, session)

        result, apikey_list = UserApiKey.get_all_api_keys(user_id=1, is_admin=True)
        assert result == 0
        assert apikey_list[0]["api_key"] == ""

    @patch('plugin.codemig.ai_assistant.models.db_session_scope')
    def test_db_error(self, mock_scope):
        from common.db.SQLOperation import DatabaseException
        mock_scope.side_effect = DatabaseException("error")

        result, apikey_list = UserApiKey.get_all_api_keys()
        assert result == -1
        assert apikey_list is None

    @patch('plugin.codemig.ai_assistant.models.decrypt_passphrase', return_value="sk-test")
    @patch('plugin.codemig.ai_assistant.models.db_session_scope')
    def test_empty_api_key_field(self, mock_scope, mock_decrypt):
        record = _make_api_key_record(user_id="user1", api_key=None)
        record.api_key = None

        session = MagicMock()
        api_key_q = MagicMock()
        api_key_q.all.return_value = [record]
        api_key_q.filter.return_value = api_key_q
        user_q = MagicMock()
        user_q.filter.return_value.all.return_value = []

        def query_side_effect(model_cls, *args, **kwargs):
            name = getattr(model_cls, '__name__', '')
            return api_key_q if name == 'UserApiKey' else user_q

        session.query.side_effect = query_side_effect
        _setup_session(mock_scope, session)

        result, apikey_list = UserApiKey.get_all_api_keys(user_id=1, is_admin=True)
        assert result == 0
        assert apikey_list[0]["api_key"] == ""


# ---------------------------------------------------------------------------
# UserApiKey.set_default_api_key
# ---------------------------------------------------------------------------
class TestSetDefaultApiKey:
    @patch('plugin.codemig.ai_assistant.models.db_session_scope')
    def test_admin_success(self, mock_scope):
        """admin 设置默认：写入 UserDefaultSelection"""
        record = _make_api_key_record(user_id="other")
        session = _make_session_with_admins(admin_user_ids=[1], first_record=record)
        _setup_session(mock_scope, session)

        result = UserApiKey.set_default_api_key(1, user_id=1, is_admin=True)
        assert result == 0
        # 验证写入 UserDefaultSelection（不存在则插入）
        session.add.assert_called_once()
        added = session.add.call_args[0][0]
        assert added.user_id == '1'
        assert added.api_key_id == 1
        # record.is_default 不再被设置

    @patch('plugin.codemig.ai_assistant.models.db_session_scope')
    def test_normal_user_own_key(self, mock_scope):
        """普通用户把自己的 key 设为默认"""
        record = _make_api_key_record(user_id="user1")
        session = _make_session_with_admins(admin_user_ids=[10], first_record=record,
                                            default_selection=None)
        _setup_session(mock_scope, session)

        result = UserApiKey.set_default_api_key(1, user_id="user1", is_admin=False)
        assert result == 0
        # 不存在旧默认 → 新增
        session.add.assert_called_once()
        added = session.add.call_args[0][0]
        assert added.user_id == 'user1'
        assert added.api_key_id == 1

    @patch('plugin.codemig.ai_assistant.models.db_session_scope')
    def test_normal_user_admin_key_in_scope(self, mock_scope):
        """普通用户把可见的 admin 的 key 设为默认（允许）"""
        record = _make_api_key_record(user_id="10")  # 属于 admin
        existing_default = MagicMock()
        existing_default.api_key_id = 999
        session = _make_session_with_admins(admin_user_ids=[10], first_record=record,
                                            default_selection=existing_default)
        _setup_session(mock_scope, session)

        result = UserApiKey.set_default_api_key(1, user_id="user1", is_admin=False)
        assert result == 0
        # 存在旧默认 → 更新 api_key_id
        assert existing_default.api_key_id == 1
        session.add.assert_not_called()

    @patch('plugin.codemig.ai_assistant.models.db_session_scope')
    def test_normal_user_other_normal_key_rejected(self, mock_scope):
        """普通用户不能把其他普通用户的 key 设为默认，返回 -3"""
        record = _make_api_key_record(user_id="user2")  # 另一个普通用户
        session = _make_session_with_admins(admin_user_ids=[10], first_record=record,
                                            default_selection=None)
        _setup_session(mock_scope, session)

        result = UserApiKey.set_default_api_key(1, user_id="user1", is_admin=False)
        assert result == -3
        # 没有写入操作
        session.add.assert_not_called()

    @patch('plugin.codemig.ai_assistant.models.db_session_scope')
    def test_not_found(self, mock_scope):
        session = _make_session_with_admins(admin_user_ids=[], first_record=None)
        _setup_session(mock_scope, session)

        result = UserApiKey.set_default_api_key(999, user_id=1, is_admin=True)
        assert result == -4

    @patch('plugin.codemig.ai_assistant.models.db_session_scope')
    def test_db_error(self, mock_scope):
        from common.db.SQLOperation import DatabaseException
        mock_scope.side_effect = DatabaseException("error")

        result = UserApiKey.set_default_api_key(1)
        assert result == -1
