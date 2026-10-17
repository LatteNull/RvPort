import logging
import os
import stat
import zipfile

import pytest
from unittest.mock import patch, MagicMock

from common.public.logger import (
    AntiCRLFLogRecord,
    BASE_LOG_DIR,
    BACKUP_COUNT,
    DATE_FORMAT,
    LOG_FORMAT,
    LOG_LEVEL,
    MAX_BYTES,
    LogHandler,
    init_analysis_log,
    init_collect_log,
    init_log,
    logger_name_to_logger_dict,
    reset_level,
)


class TestAntiCRLFLogRecord:
    """测试 AntiCRLFLogRecord 类"""

    def test_normal_message(self):
        record = AntiCRLFLogRecord(
            name="test", level=logging.INFO, pathname="test.py",
            lineno=1, msg="Hello World", args=None, exc_info=None
        )
        assert record.getMessage() == "Hello World"

    def test_crlf_replaced(self):
        record = AntiCRLFLogRecord(
            name="test", level=logging.INFO, pathname="test.py",
            lineno=1, msg="line1\nline2\rline3", args=None, exc_info=None
        )
        message = record.getMessage()
        assert '\n' not in message
        assert '\r' not in message
        assert '\\n' in message
        assert '\\r' in message

    def test_password_redacted(self):
        record = AntiCRLFLogRecord(
            name="test", level=logging.INFO, pathname="test.py",
            lineno=1, msg="user password is secret", args=None, exc_info=None
        )
        assert record.getMessage() == ''

    def test_check_password_redacted(self):
        record = AntiCRLFLogRecord(
            name="test", level=logging.INFO, pathname="test.py",
            lineno=1, msg="check_password called", args=None, exc_info=None
        )
        assert record.getMessage() == ''

    def test_message_with_args(self):
        record = AntiCRLFLogRecord(
            name="test", level=logging.INFO, pathname="test.py",
            lineno=1, msg="Count: %d", args=(42,), exc_info=None
        )
        assert record.getMessage() == "Count: 42"


class TestLogHandler:
    """测试 LogHandler 类"""

    def test_init_creates_handler(self, tmp_path):
        log_file = str(tmp_path / "test.log")
        handler = LogHandler(log_file, maxBytes=MAX_BYTES, backupCount=BACKUP_COUNT)
        assert handler is not None
        handler.close()

    def test_namer_zip(self):
        assert LogHandler.namer_zip("test.log") == "test.log.zip"

    def test_rotator_zip(self, tmp_path):
        src = str(tmp_path / "source.log")
        dst = str(tmp_path / "dest.log.zip")
        with open(src, 'w') as f:
            f.write("test content")

        LogHandler.rotator_zip(src, dst)

        assert os.path.isfile(dst)
        assert not os.path.isfile(src)
        with zipfile.ZipFile(dst, 'r') as zf:
            assert "source.log" in zf.namelist()

    def test_get_namer_and_rotator_zip(self, tmp_path):
        log_file = str(tmp_path / "test.log")
        handler = LogHandler(log_file, maxBytes=MAX_BYTES, backupCount=BACKUP_COUNT)
        namer, rotator = handler._get_namer_and_rotator('ZIP')
        assert namer == LogHandler.namer_zip
        assert rotator == LogHandler.rotator_zip
        handler.close()

    def test_get_namer_and_rotator_unknown_defaults_to_zip(self, tmp_path):
        log_file = str(tmp_path / "test.log")
        handler = LogHandler(log_file, maxBytes=MAX_BYTES, backupCount=BACKUP_COUNT)
        namer, rotator = handler._get_namer_and_rotator('UNKNOWN')
        assert namer == LogHandler.namer_zip
        assert rotator == LogHandler.rotator_zip
        handler.close()


class TestInitLog:
    """测试 init_log 函数"""

    def setup_method(self):
        logger_name_to_logger_dict.clear()

    def test_returns_logger(self):
        logger = init_log('test_init_log')
        assert logger is not None
        assert isinstance(logger, logging.Logger)

    def test_none_returned_for_non_string_file_name(self):
        result = init_log('test_func', file_name=123)
        assert result is None

    def test_non_string_function_name_raises_type_error(self):
        """源码中类型检查在字符串拼接之后，所以非字符串会触发 TypeError"""
        with pytest.raises(TypeError):
            init_log(function_name=456)

    def test_none_returned_for_non_string_log_flag(self):
        result = init_log('test_func', log_flag=True)
        assert result is None

    def test_logger_name_from_file_name(self):
        logger = init_log('test_module', file_name='mylog.log')
        assert logger is not None
        assert 'mylog' in logger_name_to_logger_dict
        assert logger_name_to_logger_dict['mylog'] is logger

    def test_logger_name_with_log_flag(self):
        logger = init_log('test_module', file_name='mylog.log', log_flag='flag1')
        assert 'mylog-flag1' in logger_name_to_logger_dict

    def test_same_logger_returned_for_same_name(self):
        logger1 = init_log('test_repeat', file_name='repeat.log')
        logger2 = init_log('test_repeat', file_name='repeat.log')
        assert logger1 is logger2

    def test_creates_log_directory(self, tmp_path):
        with patch('common.public.logger.BASE_LOG_DIR', str(tmp_path / 'logs')):
            logger = init_log('test_dir_create', file_name='dir_test.log')
            log_dir = str(tmp_path / 'logs' / 'test_dir_create')
            assert os.path.isdir(log_dir)

    def test_default_file_name(self):
        logger = init_log('myfunction')
        assert 'myfunction' in logger_name_to_logger_dict

    def test_logger_has_handlers(self):
        logger = init_log('test_handlers')
        assert len(logger.handlers) > 0

    def test_logger_level(self):
        logger = init_log('test_level')
        assert logger.level == LOG_LEVEL


class TestResetLevel:
    """测试 reset_level 函数"""

    def setup_method(self):
        logger_name_to_logger_dict.clear()

    def test_resets_all_loggers_level(self):
        logger1 = init_log('reset_test1')
        logger2 = init_log('reset_test2')
        reset_level(logging.DEBUG)
        assert logger1.level == logging.DEBUG
        assert logger2.level == logging.DEBUG


class TestInitCollectLog:
    """测试 init_collect_log 函数"""

    def setup_method(self):
        logger_name_to_logger_dict.clear()

    def test_returns_logger(self):
        logger = init_collect_log('my_collect')
        assert logger is not None


class TestInitAnalysisLog:
    """测试 init_analysis_log 函数"""

    def setup_method(self):
        logger_name_to_logger_dict.clear()

    def test_returns_logger(self):
        logger = init_analysis_log('my_analysis')
        assert logger is not None
