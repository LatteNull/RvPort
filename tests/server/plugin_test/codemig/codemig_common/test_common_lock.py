import pytest
from unittest.mock import patch, MagicMock

from plugin.codemig.codemig_common.common_lock import get_task_lock_file_path, task_file_lock


class TestGetTaskLockFilePath:
    @patch('plugin.codemig.codemig_common.common_lock.get_codemig_data_path', return_value='/data')
    def test_with_task_id(self, mock_path):
        result = get_task_lock_file_path('user1', 5, task_id=10)
        assert result == '/data/user1/5/task_10.lock'

    @patch('plugin.codemig.codemig_common.common_lock.query_task_id_by_dir_id', return_value=(None, 20))
    @patch('plugin.codemig.codemig_common.common_lock.get_codemig_data_path', return_value='/data')
    def test_without_task_id_query_returns_task_id(self, mock_path, mock_query):
        result = get_task_lock_file_path('user1', 5)
        assert result == '/data/user1/5/task_20.lock'

    @patch('plugin.codemig.codemig_common.common_lock.query_task_id_by_dir_id', return_value=(None, None))
    @patch('plugin.codemig.codemig_common.common_lock.get_codemig_data_path', return_value='/data')
    def test_without_task_id_query_returns_none(self, mock_path, mock_query):
        result = get_task_lock_file_path('user1', 5)
        assert result == '/data/user1/5/dir.lock'


class TestTaskFileLock:
    @patch('plugin.codemig.codemig_common.common_lock.os.makedirs')
    @patch('plugin.codemig.codemig_common.common_lock.get_task_lock_file_path', return_value='/data/user1/5/task_10.lock')
    @patch('plugin.codemig.codemig_common.common_lock.Lock')
    def test_acquire_lock_success(self, mock_lock_cls, mock_path, mock_makedirs):
        mock_lock_instance = MagicMock()
        mock_lock_instance.__enter__ = MagicMock(return_value=None)
        mock_lock_instance.__exit__ = MagicMock(return_value=False)
        mock_lock_cls.return_value = mock_lock_instance

        with task_file_lock('user1', 5, task_id=10):
            pass

        mock_makedirs.assert_called_once()

    @patch('plugin.codemig.codemig_common.common_lock.os.makedirs')
    @patch('plugin.codemig.codemig_common.common_lock.get_task_lock_file_path', return_value='/data/user1/5/task_10.lock')
    @patch('plugin.codemig.codemig_common.common_lock.Lock')
    def test_already_locked_raises_runtime_error(self, mock_lock_cls, mock_path, mock_makedirs):
        from portalocker import AlreadyLocked

        mock_lock_instance = MagicMock()
        mock_lock_instance.__enter__ = MagicMock(side_effect=AlreadyLocked())
        mock_lock_instance.__exit__ = MagicMock(return_value=False)
        mock_lock_cls.return_value = mock_lock_instance

        with pytest.raises(RuntimeError, match="Other Modify Task is running"):
            with task_file_lock('user1', 5, task_id=10, blocking=False):
                pass

    @patch('plugin.codemig.codemig_common.common_lock.os.makedirs')
    @patch('plugin.codemig.codemig_common.common_lock.get_task_lock_file_path', return_value='/data/user1/5/task_10.lock')
    @patch('plugin.codemig.codemig_common.common_lock.Lock')
    def test_lock_exception_raises_runtime_error(self, mock_lock_cls, mock_path, mock_makedirs):
        from portalocker import LockException

        mock_lock_instance = MagicMock()
        mock_lock_instance.__enter__ = MagicMock(side_effect=LockException("lock failed"))
        mock_lock_instance.__exit__ = MagicMock(return_value=False)
        mock_lock_cls.return_value = mock_lock_instance

        with pytest.raises(RuntimeError, match="Failed to acquire system lock"):
            with task_file_lock('user1', 5, task_id=10):
                pass

    @patch('plugin.codemig.codemig_common.common_lock.os.makedirs')
    @patch('plugin.codemig.codemig_common.common_lock.get_task_lock_file_path', return_value='/data/user1/5/task_10.lock')
    @patch('plugin.codemig.codemig_common.common_lock.Lock')
    def test_os_error_raises_runtime_error(self, mock_lock_cls, mock_path, mock_makedirs):
        mock_lock_instance = MagicMock()
        mock_lock_instance.__enter__ = MagicMock(side_effect=OSError("disk error"))
        mock_lock_instance.__exit__ = MagicMock(return_value=False)
        mock_lock_cls.return_value = mock_lock_instance

        with pytest.raises(RuntimeError, match="OS-level lock failure"):
            with task_file_lock('user1', 5, task_id=10):
                pass

    @patch('plugin.codemig.codemig_common.common_lock.os.makedirs')
    @patch('plugin.codemig.codemig_common.common_lock.get_task_lock_file_path', return_value='/data/user1/5/task_10.lock')
    @patch('plugin.codemig.codemig_common.common_lock.Lock')
    def test_value_error_raises_runtime_error(self, mock_lock_cls, mock_path, mock_makedirs):
        mock_lock_instance = MagicMock()
        mock_lock_instance.__enter__ = MagicMock(side_effect=ValueError("bad value"))
        mock_lock_instance.__exit__ = MagicMock(return_value=False)
        mock_lock_cls.return_value = mock_lock_instance

        with pytest.raises(RuntimeError, match="Unexpected lock error"):
            with task_file_lock('user1', 5, task_id=10):
                pass

    @patch('plugin.codemig.codemig_common.common_lock.os.makedirs')
    @patch('plugin.codemig.codemig_common.common_lock.get_task_lock_file_path', return_value='/data/user1/5/task_10.lock')
    @patch('plugin.codemig.codemig_common.common_lock.Lock')
    def test_type_error_raises_runtime_error(self, mock_lock_cls, mock_path, mock_makedirs):
        mock_lock_instance = MagicMock()
        mock_lock_instance.__enter__ = MagicMock(side_effect=TypeError("bad type"))
        mock_lock_instance.__exit__ = MagicMock(return_value=False)
        mock_lock_cls.return_value = mock_lock_instance

        with pytest.raises(RuntimeError, match="Unexpected lock error"):
            with task_file_lock('user1', 5, task_id=10):
                pass
