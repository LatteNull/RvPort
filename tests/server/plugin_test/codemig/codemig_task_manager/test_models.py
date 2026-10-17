"""
为 plugin/codemig/codemig_task_manager/models.py 补充测试。
"""
import os
import sys
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest

MODULE_PATH = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if MODULE_PATH not in sys.path:
    sys.path.append(MODULE_PATH)

from common.db.SQLOperation import DatabaseException
from plugin.codemig.codemig_task_manager.models import CodemigTasks, CodemigTaskDirectory
from plugin.codemig.codemig_task_manager.task_common import TaskStatus


@contextmanager
def mock_db_session_scope_with_session(session):
    yield session


# ------------------- CodemigTasks.update_dependence_status -------------------

class TestUpdateDependenceStatus:
    def test_success_returns_false(self, mocker):
        """成功更新返回 False"""
        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.update.return_value = 1
        mocker.patch(
            'plugin.codemig.codemig_task_manager.models.db_session_scope',
            side_effect=mock_db_session_scope_with_session,
            args=mock_session,
        ) if False else mocker.patch(
            'plugin.codemig.codemig_task_manager.models.db_session_scope',
            return_value=mock_db_session_scope_with_session(mock_session))
        result = CodemigTasks.update_dependence_status(1, 2, 'reason')
        assert result is False

    def test_not_found_returns_false(self, mocker):
        """任务不存在时仍返回 False（result=0 触发 warning）"""
        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.update.return_value = 0
        mocker.patch(
            'plugin.codemig.codemig_task_manager.models.db_session_scope',
            return_value=mock_db_session_scope_with_session(mock_session))
        result = CodemigTasks.update_dependence_status(1, 2, 'reason')
        assert result is False

    def test_db_exception_returns_true(self, mocker):
        """数据库异常时返回 True"""
        mocker.patch(
            'plugin.codemig.codemig_task_manager.models.db_session_scope',
            side_effect=DatabaseException("boom"))
        result = CodemigTasks.update_dependence_status(1, 2, 'reason')
        assert result is True

    def test_oserror_returns_true(self, mocker):
        """OSError 也走异常分支"""
        mocker.patch(
            'plugin.codemig.codemig_task_manager.models.db_session_scope',
            side_effect=OSError("io"))
        result = CodemigTasks.update_dependence_status(1, 2, 'reason')
        assert result is True


# ------------------- CodemigTasks.get_task_name -------------------

class TestGetTaskName:
    def test_success(self, mocker):
        mock_task = MagicMock()
        mock_task.task_name = 'task_alpha'
        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.first.return_value = mock_task
        mocker.patch(
            'plugin.codemig.codemig_task_manager.models.db_session_scope',
            return_value=mock_db_session_scope_with_session(mock_session))
        name = CodemigTasks.get_task_name('uid-1', task_id=1)
        assert name == 'task_alpha'

    def test_not_found(self, mocker):
        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.first.return_value = None
        mocker.patch(
            'plugin.codemig.codemig_task_manager.models.db_session_scope',
            return_value=mock_db_session_scope_with_session(mock_session))
        name = CodemigTasks.get_task_name('uid-1', task_id=1)
        assert name is None

    def test_db_exception(self, mocker):
        mocker.patch(
            'plugin.codemig.codemig_task_manager.models.db_session_scope',
            side_effect=DatabaseException("boom"))
        name = CodemigTasks.get_task_name('uid-1', task_id=1)
        assert name is None


# ------------------- CodemigTasks.update_task_status -------------------

class TestUpdateTaskStatus:
    def test_success_returns_true(self, mocker):
        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.update.return_value = 1
        mocker.patch(
            'plugin.codemig.codemig_task_manager.models.db_session_scope',
            return_value=mock_db_session_scope_with_session(mock_session))
        result = CodemigTasks.update_task_status(1, TaskStatus.SUCCESS)
        assert result is True

    def test_not_found_still_returns_true(self, mocker):
        """任务不存在时仍返回 True，仅记录 warning"""
        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.update.return_value = 0
        mocker.patch(
            'plugin.codemig.codemig_task_manager.models.db_session_scope',
            return_value=mock_db_session_scope_with_session(mock_session))
        result = CodemigTasks.update_task_status(1, TaskStatus.SUCCESS)
        assert result is True

    def test_db_exception_returns_false(self, mocker):
        mocker.patch(
            'plugin.codemig.codemig_task_manager.models.db_session_scope',
            side_effect=DatabaseException("boom"))
        result = CodemigTasks.update_task_status(1, TaskStatus.SUCCESS)
        assert result is False

    def test_oserror_returns_false(self, mocker):
        mocker.patch(
            'plugin.codemig.codemig_task_manager.models.db_session_scope',
            side_effect=OSError("io"))
        result = CodemigTasks.update_task_status(1, TaskStatus.SUCCESS)
        assert result is False
