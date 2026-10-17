import os
import sys
import sqlite3
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from plugin.codemig.codemig_common.codemig_common_utils import (
    create_relative_file_path,
    add_dot_slash,
    FileSource,
    CodeTooLong,
    ChangeType,
    matches_c_file,
    extract_suffix,
    extract_zipfile,
    add_counter_to_extract_path,
    create_new_extract_path,
    create_new_path,
    move_file_to_new_path,
    regex_arch,
    regex_riscv_arch,
    load_list_from_file,
    get_database_path,
    query_file_by_path_from_database,
    query_file_tree_from_database,
    query_missing_file_tree_from_database,
    query_missing_files_not_generated_from_database,
    query_all_file_from_database,
    query_file_path_from_database,
    query_file_info_from_database,
    save_new_file_to_database,
    save_generated_file_to_database,
    update_file_removed_to_database,
    update_directory_removed_recursively_to_database,
    update_suggestion_ignored,
    query_user_id_from_database,
    create_ai_info_to_database,
    update_ai_result,
    update_ai_suggestion,
    update_ai_exception,
    query_ai_finished,
    query_ai_suggestion_from_database,
    set_ai_score_to_database,
    query_ai_score_from_database,
    set_permissions_pathlib,
    extract_file,
    TAR_GZ, TGZ, TAR,
    SUPPORTED_ARCHIVES,
    NUMBER_LINES_TOO_LONG,
    BATCH_SIZE,
)


class TestCreateRelativeFilePath:
    @patch('plugin.codemig.codemig_common.codemig_common_utils.get_codemig_data_path',
           return_value='/data')
    def test_relative_path(self, _):
        result = create_relative_file_path('/data/user/1/file.txt')
        assert result == './user/1/file.txt'


class TestAddDotSlash:
    def test_basic(self):
        assert add_dot_slash('path/to/file') == './path/to/file'

    def test_empty(self):
        assert add_dot_slash('') == './'


class TestFileSource:
    def test_values(self):
        assert FileSource.CHANGED.value == "changed"
        assert FileSource.ORIGINAL.value == "original"
        assert FileSource.MISSING.value == "missing"
        assert FileSource.GENERATE.value == "generated"


class TestCodeTooLong:
    def test_values(self):
        assert CodeTooLong.HAS_SOURCE_CODE.value == 0
        assert CodeTooLong.CODE_TOO_LONG.value == 1


class TestChangeType:
    def test_values(self):
        assert ChangeType.APPEND.value == 0
        assert ChangeType.REPLACE.value == 1
        assert ChangeType.OTHER.value == 2


class TestMatchesCFile:
    def test_c_file(self):
        assert matches_c_file("main.c") is True

    def test_h_file(self):
        assert matches_c_file("header.h") is True

    def test_cpp_file(self):
        assert matches_c_file("source.cpp") is True

    def test_cc_file(self):
        assert matches_c_file("source.cc") is True

    def test_hpp_file(self):
        assert matches_c_file("header.hpp") is True

    def test_h_in_file(self):
        assert matches_c_file("config.h.in") is True

    def test_py_file(self):
        assert matches_c_file("script.py") is False

    def test_txt_file(self):
        assert matches_c_file("readme.txt") is False

    def test_java_file(self):
        assert matches_c_file("Main.java") is False


class TestExtractSuffix:
    def test_single_suffix(self):
        assert extract_suffix(['.zip']) == '.zip'

    def test_tar_gz_suffix(self):
        assert extract_suffix(['.tar', '.gz']) == TAR_GZ

    def test_no_suffix(self):
        assert extract_suffix([]) is None

    def test_jar_suffix(self):
        assert extract_suffix(['.jar']) == '.jar'


class TestConstants:
    def test_tar_gz(self):
        assert TAR_GZ == '.tar.gz'

    def test_tgz(self):
        assert TGZ == '.tgz'

    def test_tar(self):
        assert TAR == '.tar'

    def test_supported_archives(self):
        assert '.jar' in SUPPORTED_ARCHIVES
        assert '.zip' in SUPPORTED_ARCHIVES
        assert '.tar.gz' in SUPPORTED_ARCHIVES
        assert '.whl' in SUPPORTED_ARCHIVES

    def test_number_lines_too_long(self):
        assert NUMBER_LINES_TOO_LONG == 50

    def test_batch_size(self):
        assert BATCH_SIZE == 1000


class TestExtractZipfile:
    def test_extract_valid_zip(self, tmp_path):
        import zipfile
        zip_path = tmp_path / "test.zip"
        extract_path = tmp_path / "extracted"

        with zipfile.ZipFile(str(zip_path), 'w') as zf:
            zf.writestr("hello.txt", "hello world")

        result = extract_zipfile(str(zip_path), str(extract_path))
        assert result is True
        assert (extract_path / "hello.txt").exists()

    def test_extract_bad_zip(self, tmp_path):
        bad_zip = tmp_path / "bad.zip"
        bad_zip.write_text("not a zip")
        extract_path = tmp_path / "out"

        result = extract_zipfile(str(bad_zip), str(extract_path))
        assert result is False


class TestAddCounterToExtractPath:
    def test_returns_new_path(self, tmp_path):
        existing = tmp_path / "folder"
        existing.mkdir()
        result = add_counter_to_extract_path(existing)
        assert result.name == "folder_1"

    def test_increments_counter(self, tmp_path):
        existing = tmp_path / "folder"
        existing.mkdir()
        (tmp_path / "folder_1").mkdir()
        result = add_counter_to_extract_path(existing)
        assert result.name == "folder_2"


class TestCreateNewExtractPath:
    def test_creates_path(self, tmp_path):
        result = create_new_extract_path(tmp_path, "archive.tar.gz")
        assert "archive_tar_gz" in str(result)

    def test_existing_path_gets_counter(self, tmp_path):
        root = tmp_path
        name = "test.zip"
        import datetime
        time_suffix = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        existing = root / f"{name.replace('.', '_')}_{time_suffix}"
        existing.mkdir()
        result = create_new_extract_path(root, name)
        assert result != existing


class TestCreateNewPath:
    @patch('plugin.codemig.codemig_common.codemig_common_utils.get_codemig_data_path',
           return_value='/data')
    def test_creates_new_path(self, _):
        result = create_new_path('/data/user/1/changed/file.c', 'tmp')
        parts = Path(result).parts
        assert 'tmp' in parts


class TestMoveFileToNewPath:
    def test_copy_file(self, tmp_path):
        src = tmp_path / "src.txt"
        src.write_text("hello")
        dst = tmp_path / "dest.txt"
        move_file_to_new_path(str(src), str(dst))
        assert dst.exists()
        assert src.exists()

    def test_copy_tree(self, tmp_path):
        src_dir = tmp_path / "src_dir"
        src_dir.mkdir()
        (src_dir / "file.txt").write_text("content")
        dst_dir = tmp_path / "dst_dir"
        move_file_to_new_path(str(src_dir), str(dst_dir), tree=True)
        assert dst_dir.exists()
        assert (dst_dir / "file.txt").exists()


class TestRegexArch:
    def test_x86_64(self):
        assert regex_arch("build_x86_64") is True

    def test_arm64(self):
        assert regex_arch("arm64_platform") is True

    def test_aarch64(self):
        assert regex_arch("aarch64_system") is True

    def test_riscv_not_matched(self):
        assert regex_arch("riscv64_board") is False

    def test_no_arch(self):
        assert regex_arch("plain_name") is False

    def test_case_insensitive(self):
        assert regex_arch("X86_64_BUILD") is True


class TestRegexRiscvArch:
    def test_riscv64(self):
        assert regex_riscv_arch("riscv64_board") is True

    def test_riscv(self):
        assert regex_riscv_arch("riscv_chip") is True

    def test_rvv(self):
        assert regex_riscv_arch("rvv_vector") is True

    def test_risc_v(self):
        assert regex_riscv_arch("risc-v_soc") is True

    def test_x86_not_matched(self):
        assert regex_riscv_arch("x86_64") is False

    def test_no_arch(self):
        assert regex_riscv_arch("plain_name") is False


class TestLoadListFromFile:
    def test_loads_lines(self, tmp_path):
        f = tmp_path / "list.txt"
        f.write_text("line1\nline2\nline3\n")
        result = load_list_from_file(str(f))
        assert result == ["line1", "line2", "line3"]

    def test_strips_whitespace(self, tmp_path):
        f = tmp_path / "list.txt"
        f.write_text("  line1  \n\n  line2  \n")
        result = load_list_from_file(str(f))
        assert result == ["line1", "line2"]

    def test_empty_file(self, tmp_path):
        f = tmp_path / "empty.txt"
        f.write_text("")
        result = load_list_from_file(str(f))
        assert result == []


class TestGetDatabasePath:
    @patch('plugin.codemig.codemig_common.codemig_common_utils.get_codemig_data_path',
           return_value='/data')
    def test_returns_correct_path(self, _):
        result = get_database_path("user1", 5)
        assert result == Path("/data/user1/5/5.db")


# ---------------------------------------------------------------------------
# Database operation tests (using mocks)
# ---------------------------------------------------------------------------

def _mock_db(mocker, exists=True, fetchone=..., fetchall=None, lastrowid=1,
             db_error=False):
    """Helper to mock database operations."""
    mock_db_path = MagicMock()
    mock_db_path.exists.return_value = exists
    mocker.patch('plugin.codemig.codemig_common.codemig_common_utils.get_database_path',
                 return_value=mock_db_path)
    if not exists:
        return None

    mock_conn = mocker.MagicMock()
    mock_cursor = mocker.MagicMock()
    if db_error:
        mock_cursor.execute.side_effect = sqlite3.Error("db error")
    if fetchone is not ...:
        mock_cursor.fetchone.return_value = fetchone
    if fetchall is not None:
        mock_cursor.fetchall.return_value = fetchall
    mock_cursor.lastrowid = lastrowid
    mock_conn.cursor.return_value = mock_cursor
    mocker.patch('plugin.codemig.codemig_common.codemig_common_utils.get_conn',
                 return_value=mock_conn)
    return mock_cursor


class TestQueryFileByPathFromDatabase:
    def test_db_not_exists(self, mocker):
        _mock_db(mocker, exists=False)
        status, result = query_file_by_path_from_database("user1", 1, "/file.c")
        assert status is False
        assert result is None

    def test_found(self, mocker):
        _mock_db(mocker, fetchone=(42,))
        status, result = query_file_by_path_from_database("user1", 1, "/file.c")
        assert status is True
        assert result == 42

    def test_not_found(self, mocker):
        _mock_db(mocker, fetchone=None)
        status, result = query_file_by_path_from_database("user1", 1, "/file.c")
        assert status is True
        assert result is None

    def test_db_error(self, mocker):
        _mock_db(mocker, db_error=True)
        status, result = query_file_by_path_from_database("user1", 1, "/file.c")
        assert status is False


class TestQueryFileTreeFromDatabase:
    def test_db_not_exists(self, mocker):
        _mock_db(mocker, exists=False)
        status, result = query_file_tree_from_database("user1", 1)
        assert status is False

    def test_success(self, mocker):
        _mock_db(mocker, fetchall=[(1, "/file.c", "original", 1)])
        status, result = query_file_tree_from_database("user1", 1)
        assert status is True
        assert len(result) == 1

    def test_db_error(self, mocker):
        _mock_db(mocker, db_error=True)
        status, result = query_file_tree_from_database("user1", 1)
        assert status is False


class TestQueryMissingFileTreeFromDatabase:
    def test_db_not_exists(self, mocker):
        _mock_db(mocker, exists=False)
        status, result = query_missing_file_tree_from_database("user1", 1)
        assert status is False

    def test_success(self, mocker):
        _mock_db(mocker, fetchall=[])
        status, result = query_missing_file_tree_from_database("user1", 1)
        assert status is True


class TestQueryMissingFilesNotGenerated:
    def test_db_not_exists(self, mocker):
        _mock_db(mocker, exists=False)
        status, result = query_missing_files_not_generated_from_database("user1", 1)
        assert status is False


class TestQueryAllFileFromDatabase:
    def test_db_not_exists(self, mocker):
        _mock_db(mocker, exists=False)
        status, result = query_all_file_from_database("user1", 1)
        assert status is False

    def test_success(self, mocker):
        _mock_db(mocker, fetchall=[(1, "/file.c", "original", 1)])
        status, result = query_all_file_from_database("user1", 1)
        assert status is True

    def test_db_error(self, mocker):
        _mock_db(mocker, db_error=True)
        status, result = query_all_file_from_database("user1", 1)
        assert status is False


class TestQueryFilePathFromDatabase:
    def test_db_not_exists(self, mocker):
        mocker.patch('os.path.exists', return_value=False)
        mock_db_path = MagicMock()
        mocker.patch('plugin.codemig.codemig_common.codemig_common_utils.get_database_path',
                     return_value=mock_db_path)
        status, result = query_file_path_from_database("user1", 1, 100)
        assert status is False

    def test_found(self, mocker):
        mocker.patch('os.path.exists', return_value=True)
        mock_db_path = MagicMock()
        mocker.patch('plugin.codemig.codemig_common.codemig_common_utils.get_database_path',
                     return_value=mock_db_path)
        _mock_db(mocker, fetchone=("/data/file.c",))
        status, result = query_file_path_from_database("user1", 1, 100)
        assert status is True
        assert result == "/data/file.c"

    def test_not_found(self, mocker):
        mocker.patch('os.path.exists', return_value=True)
        mock_db_path = MagicMock()
        mocker.patch('plugin.codemig.codemig_common.codemig_common_utils.get_database_path',
                     return_value=mock_db_path)
        _mock_db(mocker, fetchone=None)
        status, result = query_file_path_from_database("user1", 1, 100)
        assert status is True
        assert result is None


class TestQueryFileInfoFromDatabase:
    def test_db_not_exists(self, mocker):
        mocker.patch('os.path.exists', return_value=False)
        mock_db_path = MagicMock()
        mocker.patch('plugin.codemig.codemig_common.codemig_common_utils.get_database_path',
                     return_value=mock_db_path)
        status, result = query_file_info_from_database("user1", 1, 100)
        assert status is False

    def test_found(self, mocker):
        mocker.patch('os.path.exists', return_value=True)
        mock_db_path = MagicMock()
        mocker.patch('plugin.codemig.codemig_common.codemig_common_utils.get_database_path',
                     return_value=mock_db_path)
        _mock_db(mocker, fetchone=("/file.c", "original", True, 0))
        status, result = query_file_info_from_database("user1", 1, 100)
        assert status is True


class TestSaveNewFileToDatabase:
    def test_db_not_exists(self, mocker):
        _mock_db(mocker, exists=False)
        status, file_id = save_new_file_to_database("user1", 1, 1, "/file.c", "original", True)
        assert status is False

    def test_success(self, mocker):
        _mock_db(mocker, lastrowid=42)
        status, file_id = save_new_file_to_database("user1", 1, 1, "/file.c", "original", True)
        assert status is True
        assert file_id == 42

    def test_db_error(self, mocker):
        _mock_db(mocker, db_error=True)
        status, file_id = save_new_file_to_database("user1", 1, 1, "/file.c", "original", True)
        assert status is False


class TestSaveGeneratedFileToDatabase:
    def test_db_not_exists(self, mocker):
        _mock_db(mocker, exists=False)
        status, file_id = save_generated_file_to_database("user1", 1, 1, "/file.c", "generated", True, 10)
        assert status is False

    def test_success(self, mocker):
        _mock_db(mocker, lastrowid=55)
        status, file_id = save_generated_file_to_database("user1", 1, 1, "/file.c", "generated", True, 10)
        assert status is True
        assert file_id == 55


class TestUpdateFileRemovedToDatabase:
    def test_db_not_exists(self, mocker):
        _mock_db(mocker, exists=False)
        status = update_file_removed_to_database("user1", 1, 100)
        assert status is False

    def test_success(self, mocker):
        _mock_db(mocker)
        status = update_file_removed_to_database("user1", 1, 100)
        assert status is True


class TestUpdateDirectoryRemovedRecursively:
    def test_db_not_exists(self, mocker):
        _mock_db(mocker, exists=False)
        status = update_directory_removed_recursively_to_database("user1", 1, "/dir")
        assert status is False

    def test_success(self, mocker):
        _mock_db(mocker)
        status = update_directory_removed_recursively_to_database("user1", 1, "/dir")
        assert status is True


class TestUpdateSuggestionIgnored:
    def test_db_not_exists(self, mocker):
        _mock_db(mocker, exists=False)
        status = update_suggestion_ignored("user1", 1, 100, 200, True)
        assert status is False

    def test_success(self, mocker):
        _mock_db(mocker)
        status = update_suggestion_ignored("user1", 1, 100, 200, True)
        assert status is True


class TestQueryUserIdFromDatabase:
    def test_db_not_exists(self, mocker):
        _mock_db(mocker, exists=False)
        status, user_id = query_user_id_from_database("user1", 1)
        assert status is False

    def test_found(self, mocker):
        _mock_db(mocker, fetchone=(100,))
        status, user_id = query_user_id_from_database("user1", 1)
        assert status is True
        assert user_id == 100

    def test_not_found(self, mocker):
        _mock_db(mocker, fetchone=None)
        status, user_id = query_user_id_from_database("user1", 1)
        assert status is False

    def test_db_error(self, mocker):
        _mock_db(mocker, db_error=True)
        status, user_id = query_user_id_from_database("user1", 1)
        assert status is False


class TestCreateAiInfoToDatabase:
    def test_db_not_exists(self, mocker):
        _mock_db(mocker, exists=False)
        status, ai_id = create_ai_info_to_database("user1", 1, 10, "req1", "/file.c", "mode", "cmd")
        assert status is False

    def test_success(self, mocker):
        _mock_db(mocker, lastrowid=7)
        status, ai_id = create_ai_info_to_database("user1", 1, 10, "req1", "/file.c", "mode", "cmd")
        assert status is True
        assert ai_id == 7


class TestUpdateAiResult:
    def test_db_not_exists(self, mocker):
        _mock_db(mocker, exists=False)
        status = update_ai_result("user1", 1, "req1", 10, "suggestion", "completed")
        assert status is False

    def test_success(self, mocker):
        _mock_db(mocker)
        status = update_ai_result("user1", 1, "req1", 10, "suggestion", "completed")
        assert status is True


class TestUpdateAiSuggestion:
    def test_calls_update_ai_result(self, mocker):
        mock_update = mocker.patch('plugin.codemig.codemig_common.codemig_common_utils.update_ai_result')
        update_ai_suggestion("user1", 1, "req1", 10, "suggestion")
        mock_update.assert_called_once_with("user1", 1, "req1", 10, "suggestion", "completed")


class TestUpdateAiException:
    def test_calls_update_ai_result(self, mocker):
        mock_update = mocker.patch('plugin.codemig.codemig_common.codemig_common_utils.update_ai_result')
        update_ai_exception("user1", 1, "error msg", "req1", 10)
        mock_update.assert_called_once_with("user1", 1, "req1", 10, "error msg", "abnormal")


class TestQueryAiFinished:
    def test_db_not_exists(self, mocker):
        _mock_db(mocker, exists=False)
        status, ai_id, result = query_ai_finished("user1", 1, 10)
        assert status is False

    def test_no_ai_id(self, mocker):
        _mock_db(mocker, fetchone=(None,))
        status, ai_id, result = query_ai_finished("user1", 1, 10)
        assert status is True
        assert ai_id == 0

    def test_with_ai_id(self, mocker):
        mock_cursor = _mock_db(mocker, fetchone=("finished_result",))
        # First call returns ai_id, second returns finished status
        mock_cursor.fetchone.side_effect = [(5,), ("completed",)]
        status, ai_id, result = query_ai_finished("user1", 1, 10)
        assert status is True


class TestQueryAiSuggestionFromDatabase:
    def test_db_not_exists(self, mocker):
        _mock_db(mocker, exists=False)
        status, ai_id, result = query_ai_suggestion_from_database("user1", 1, 10)
        assert status is False

    def test_no_ai_id(self, mocker):
        _mock_db(mocker, fetchone=(None,))
        status, ai_id, result = query_ai_suggestion_from_database("user1", 1, 10)
        assert status is True
        assert ai_id == 0


class TestSetAiScoreToDatabase:
    def test_db_not_exists(self, mocker):
        _mock_db(mocker, exists=False)
        status, msg = set_ai_score_to_database("user1", 1, 10)
        assert status is False

    def test_no_ai_id(self, mocker):
        _mock_db(mocker, fetchone=(None,))
        status, msg = set_ai_score_to_database("user1", 1, 10)
        assert status is False
        assert "not finished" in msg

    def test_success(self, mocker):
        mock_cursor = _mock_db(mocker, fetchone=(5,))
        mock_cursor.fetchone.side_effect = [(5,)]
        status, msg = set_ai_score_to_database("user1", 1, 10, ai_id=5)
        assert status is True

    def test_with_explicit_ai_id(self, mocker):
        _mock_db(mocker)
        status, msg = set_ai_score_to_database("user1", 1, 10, ai_id=5, score=5)
        assert status is True


class TestQueryAiScoreFromDatabase:
    def test_db_not_exists(self, mocker):
        _mock_db(mocker, exists=False)
        status, result = query_ai_score_from_database("user1", 1, 10)
        assert status is False

    def test_with_uuid(self, mocker):
        _mock_db(mocker, fetchone=(4,))
        status, result = query_ai_score_from_database("user1", 1, 10, uuid="test-uuid")
        assert status is True

    def test_no_uuid_no_ai_id(self, mocker):
        _mock_db(mocker, fetchone=(None,))
        status, result = query_ai_score_from_database("user1", 1, 10, uuid=None)
        assert status is True
        assert result is None

    def test_empty_uuid(self, mocker):
        _mock_db(mocker, fetchone=(None,))
        status, result = query_ai_score_from_database("user1", 1, 10, uuid="")
        assert status is True

    def test_db_error(self, mocker):
        _mock_db(mocker, db_error=True)
        status, result = query_ai_score_from_database("user1", 1, 10, uuid="uuid")
        assert status is False


class TestSetPermissionsPathlib:
    def test_path_not_exists(self, mocker):
        mocker.patch('pathlib.Path.exists', return_value=False)
        result = set_permissions_pathlib("/nonexistent/path")
        assert result is None

    def test_sets_permissions(self, tmp_path):
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")
        set_permissions_pathlib(str(tmp_path))
        assert test_file.exists()


class TestExtractFile:
    def test_not_tar_nor_zip(self, tmp_path):
        src = tmp_path / "test.txt"
        src.write_text("not an archive")
        dst = tmp_path / "out"
        result = extract_file(src, dst)
        assert result is False

    def test_extract_zip(self, tmp_path):
        import zipfile
        src = tmp_path / "test.zip"
        with zipfile.ZipFile(str(src), 'w') as zf:
            zf.writestr("hello.txt", "hello")
        dst = tmp_path / "out"
        result = extract_file(src, dst)
        assert result is True

    def test_extract_tar_gz(self, tmp_path):
        import tarfile
        src = tmp_path / "test.tar.gz"
        with tarfile.open(str(src), 'w:gz') as tf:
            info = tarfile.TarInfo(name="hello.txt")
            info.size = 5
            import io
            tf.addfile(info, io.BytesIO(b"hello"))
        dst = tmp_path / "out"
        result = extract_file(src, dst)
        assert result is True

    def test_extract_zip_with_max_depth(self, tmp_path):
        import zipfile
        src = tmp_path / "test.zip"
        with zipfile.ZipFile(str(src), 'w') as zf:
            zf.writestr("hello.txt", "hello")
        dst = tmp_path / "out"
        result = extract_file(src, dst, max_depth=1)
        assert result is True


class TestExtractZipfileAdditional:
    def test_permission_error(self, tmp_path):
        import zipfile
        src = tmp_path / "test.zip"
        with zipfile.ZipFile(str(src), 'w') as zf:
            zf.writestr("hello.txt", "hello")
        dst = tmp_path / "out"
        with patch('zipfile.ZipFile.extract', side_effect=PermissionError("no access")):
            result = extract_zipfile(str(src), str(dst))
            assert result is False

    def test_runtime_error(self, tmp_path):
        import zipfile
        src = tmp_path / "test.zip"
        with zipfile.ZipFile(str(src), 'w') as zf:
            zf.writestr("hello.txt", "hello")
        dst = tmp_path / "out"
        with patch('zipfile.ZipFile.extract', side_effect=RuntimeError("err")):
            result = extract_zipfile(str(src), str(dst))
            assert result is False


class TestExtractZipfileConflict:
    def test_path_conflict_parent_is_file(self, tmp_path):
        """测试解压时父路径存在但不是目录的情况"""
        import zipfile
        src = tmp_path / "test.zip"
        # Create a zip with a nested file
        with zipfile.ZipFile(str(src), 'w') as zf:
            zf.writestr("conflict/hello.txt", "hello")
        dst = tmp_path / "out"
        # Create a file where a directory should be
        conflict_file = dst / "conflict"
        dst.mkdir()
        conflict_file.write_text("I am a file, not a directory")

        result = extract_zipfile(str(src), str(dst))
        assert result is True
        # The conflict file should have been renamed
        assert (dst / "conflict.backup").exists()


class TestSetPermissionsDeep:
    def test_git_dir_deletion_error(self, tmp_path, mocker):
        """测试 .git 目录删除失败"""
        test_dir = tmp_path / "project"
        test_dir.mkdir()
        git_dir = test_dir / ".git"
        git_dir.mkdir()
        mocker.patch('shutil.rmtree', side_effect=PermissionError("no access"))
        set_permissions_pathlib(str(test_dir))
        # Should not raise

    def test_process_path_permission_error(self, tmp_path, mocker):
        """测试 process_path 中权限错误"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")
        mocker.patch('pathlib.Path.chmod', side_effect=PermissionError("no access"))
        set_permissions_pathlib(str(tmp_path))
        # Should not raise

    def test_process_path_os_error(self, tmp_path, mocker):
        """测试 process_path 中 OSError"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")
        mocker.patch('os.chown', side_effect=OSError("chown error"))
        set_permissions_pathlib(str(tmp_path))
        # Should not raise

    def test_with_git_dir(self, tmp_path):
        """测试 .git 目录被删除"""
        test_dir = tmp_path / "project"
        test_dir.mkdir()
        git_dir = test_dir / ".git"
        git_dir.mkdir()
        (git_dir / "config").write_text("gitconfig")
        set_permissions_pathlib(str(test_dir))
        # .git dir should be removed
        assert not git_dir.exists()


class TestExtractFileDeep:
    def test_tar_error(self, tmp_path, mocker):
        """测试 tar 文件解压失败"""
        import tarfile
        src = tmp_path / "test.tar.gz"
        with tarfile.open(str(src), 'w:gz') as tf:
            import io
            info = tarfile.TarInfo(name="hello.txt")
            info.size = 5
            tf.addfile(info, io.BytesIO(b"hello"))
        dst = tmp_path / "out"
        mocker.patch('tarfile.open', side_effect=tarfile.TarError("bad tar"))
        result = extract_file(src, dst)
        assert result is False

    def test_extract_zip_failure(self, tmp_path, mocker):
        """测试 zip 解压 extract_zipfile 返回 False"""
        src = tmp_path / "test.zip"
        src.write_text("not a real zip but has zip header")
        dst = tmp_path / "out"
        mocker.patch('zipfile.is_zipfile', return_value=True)
        mocker.patch('plugin.codemig.codemig_common.codemig_common_utils.extract_zipfile',
                     return_value=False)
        result = extract_file(src, dst)
        assert result is False

    def test_extract_with_nested_archive(self, tmp_path):
        """测试嵌套压缩文件的递归解压"""
        import zipfile
        # Create inner zip
        inner_src = tmp_path / "inner.zip"
        with zipfile.ZipFile(str(inner_src), 'w') as zf:
            zf.writestr("inner_file.txt", "inner content")

        # Create outer zip
        outer_src = tmp_path / "outer.zip"
        with zipfile.ZipFile(str(outer_src), 'w') as zf:
            zf.write(str(inner_src), "inner.zip")

        dst = tmp_path / "out"
        result = extract_file(outer_src, dst)
        assert result is True


class TestQueryMissingFilesNotGenerated:
    def test_db_error(self, mocker):
        _mock_db(mocker, db_error=True)
        status, result = query_missing_files_not_generated_from_database("user1", 1)
        assert status is False

    def test_success(self, mocker):
        _mock_db(mocker, fetchall=[(1, "/file.c", "original")])
        status, result = query_missing_files_not_generated_from_database("user1", 1)
        assert status is True
        assert len(result) == 1


class TestQueryFileByPathDbError:
    def test_rollback_on_error(self, mocker):
        mock_cursor = _mock_db(mocker, db_error=True)
        status, result = query_file_by_path_from_database("user1", 1, "/file.c")
        assert status is False


class TestSaveNewFileDbError:
    def test_rollback_on_error(self, mocker):
        _mock_db(mocker, db_error=True)
        status, file_id = save_new_file_to_database("user1", 1, 1, "/file.c", "original", True)
        assert status is False


class TestUpdateFileRemovedDbError:
    def test_rollback_on_error(self, mocker):
        _mock_db(mocker, db_error=True)
        status = update_file_removed_to_database("user1", 1, 100)
        assert status is False


class TestCreateAiInfoDbError:
    def test_rollback_on_error(self, mocker):
        _mock_db(mocker, db_error=True)
        status, ai_id = create_ai_info_to_database("user1", 1, 10, "req1", "/file.c", "mode", "cmd")
        assert status is False


class TestUpdateAiResultDbError:
    def test_rollback_on_error(self, mocker):
        _mock_db(mocker, db_error=True)
        status = update_ai_result("user1", 1, "req1", 10, "suggestion", "completed")
        assert status is False


class TestSetAiScoreDbError:
    def test_rollback_on_error(self, mocker):
        _mock_db(mocker, db_error=True)
        status, msg = set_ai_score_to_database("user1", 1, 10, ai_id=5)
        assert status is False


# ---------------------------------------------------------------------------
# Branch coverage supplement tests
# ---------------------------------------------------------------------------

class TestExtractZipfileBranches:
    def test_parent_dir_exists_and_is_dir(self, tmp_path):
        """测试父目录存在且是目录（正常路径，走111行分支）"""
        import zipfile
        src = tmp_path / "test.zip"
        extract_path = tmp_path / "out"
        with zipfile.ZipFile(str(src), 'w') as zf:
            zf.writestr("subdir/hello.txt", "hello")
        result = extract_zipfile(str(src), str(extract_path))
        assert result is True

    def test_parent_dir_empty_string(self, tmp_path):
        """测试 parent_dir 为空字符串（根级文件，跳过111和113分支）"""
        import zipfile
        src = tmp_path / "test.zip"
        extract_path = tmp_path / "out"
        with zipfile.ZipFile(str(src), 'w') as zf:
            zf.writestr("rootfile.txt", "content")
        result = extract_zipfile(str(src), str(extract_path))
        assert result is True


class TestSetPermissionsPathlibBranches:
    def test_is_dir_and_not_symlink(self, tmp_path, mocker):
        """测试 process_path 中 is_dir and not is_symlink 分支（行178-180）"""
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        set_permissions_pathlib(str(tmp_path))
        assert subdir.exists()

    def test_symlink_skipped(self, tmp_path):
        """测试符号链接被跳过（is_file/False, is_dir/False 分支）"""
        target_file = tmp_path / "real.txt"
        target_file.write_text("content")
        link = tmp_path / "link.txt"
        link.symlink_to(target_file)
        set_permissions_pathlib(str(tmp_path))
        assert link.exists()

    def test_process_path_returns_true(self, tmp_path):
        """测试 process_path 正常返回 True（行182）"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")
        set_permissions_pathlib(str(tmp_path))
        assert test_file.exists()

    def test_git_dir_not_dir_skipped(self, tmp_path, mocker):
        """测试 .git 路径不是目录时跳过 is_dir 检查（行163 False分支）"""
        git_file = tmp_path / ".git"
        git_file.write_text("not a dir")
        mocker.patch.object(Path, 'rglob',
                            side_effect=lambda name: iter([]) if name == '*' else iter([git_file]))
        # Should not crash even when .git is a file
        set_permissions_pathlib(str(tmp_path))

    def test_github_dir_deletion(self, tmp_path):
        """测试 .github 目录被删除"""
        github_dir = tmp_path / ".github"
        github_dir.mkdir()
        (github_dir / "config").write_text("config")
        set_permissions_pathlib(str(tmp_path))
        assert not github_dir.exists()


class TestExtractFileBranches:
    def test_tar_extract_error_branch(self, tmp_path, mocker):
        """测试 tar 解压异常（行207-210）"""
        import tarfile
        src = tmp_path / "test.tar.gz"
        with tarfile.open(str(src), 'w:gz') as tf:
            import io
            info = tarfile.TarInfo(name="hello.txt")
            info.size = 5
            tf.addfile(info, io.BytesIO(b"hello"))
        dst = tmp_path / "out"
        mocker.patch('tarfile.open', side_effect=tarfile.TarError("bad tar"))
        result = extract_file(src, dst)
        assert result is False

    def test_max_depth_not_zero(self, tmp_path):
        """测试 max_depth > 0 时不立即返回（行220-222走max_depth != 0分支）"""
        import zipfile
        src = tmp_path / "test.zip"
        with zipfile.ZipFile(str(src), 'w') as zf:
            zf.writestr("hello.txt", "hello")
        dst = tmp_path / "out"
        result = extract_file(src, dst, max_depth=2)
        assert result is True


class TestQueryMissingFileTreeDbError:
    def test_db_error_branch(self, mocker):
        """测试 query_missing_file_tree_from_database db_error（行347-349）"""
        _mock_db(mocker, db_error=True)
        status, result = query_missing_file_tree_from_database("user1", 1)
        assert status is False


class TestQueryFilePathDbError:
    def test_db_error_branch(self, mocker):
        """测试 query_file_path_from_database db_error（行403-405）"""
        mocker.patch('os.path.exists', return_value=True)
        mock_db_path = MagicMock()
        mocker.patch('plugin.codemig.codemig_common.codemig_common_utils.get_database_path',
                     return_value=mock_db_path)
        _mock_db(mocker, db_error=True)
        status, result = query_file_path_from_database("user1", 1, 100)
        assert status is False


class TestQueryFileInfoDbError:
    def test_db_error_branch(self, mocker):
        """测试 query_file_info_from_database db_error（行422-424）"""
        mocker.patch('os.path.exists', return_value=True)
        mock_db_path = MagicMock()
        mocker.patch('plugin.codemig.codemig_common.codemig_common_utils.get_database_path',
                     return_value=mock_db_path)
        _mock_db(mocker, db_error=True)
        status, result = query_file_info_from_database("user1", 1, 100)
        assert status is False


class TestSaveGeneratedFileDbError:
    def test_rollback_on_error(self, mocker):
        """测试 save_generated_file_to_database db_error rollback（行467-471）"""
        _mock_db(mocker, db_error=True)
        status, file_id = save_generated_file_to_database("user1", 1, 1, "/file.c", "generated", True, 10)
        assert status is False


class TestUpdateDirectoryRemovedDbError:
    def test_rollback_on_error(self, mocker):
        """测试 update_directory_removed_recursively_to_database db_error（行522-526）"""
        _mock_db(mocker, db_error=True)
        status = update_directory_removed_recursively_to_database("user1", 1, "/dir")
        assert status is False


class TestUpdateSuggestionIgnoredDbError:
    def test_rollback_on_error(self, mocker):
        """测试 update_suggestion_ignored db_error（行542-546）"""
        _mock_db(mocker, db_error=True)
        status = update_suggestion_ignored("user1", 1, 100, 200, True)
        assert status is False


class TestQueryAiFinishedDeepBranches:
    def test_ai_id_none_row_none(self, mocker):
        """测试 query_ai_finished 中 ai_id=None 且 row[0] is None（行647-653）"""
        _mock_db(mocker, fetchone=(None,))
        status, ai_id, result = query_ai_finished("user1", 1, 10)
        assert status is True
        assert ai_id == 0

    def test_ai_id_provided_directly(self, mocker):
        """测试 query_ai_finished 传入 ai_id 参数直接跳过 None 检查（行654+）"""
        mock_cursor = _mock_db(mocker, fetchone=("completed",))
        status, ai_id, result = query_ai_finished("user1", 1, 10, ai_id=5)
        assert status is True
        assert ai_id == 5
        assert result == "completed"

    def test_db_error_rollback(self, mocker):
        """测试 query_ai_finished db_error rollback（行657-661）"""
        _mock_db(mocker, db_error=True)
        status, ai_id, result = query_ai_finished("user1", 1, 10)
        assert status is False


class TestQueryAiSuggestionDeepBranches:
    def test_ai_id_none_row_not_none(self, mocker):
        """测试 query_ai_suggestion_from_database 中 ai_id=None, row有值（行676-685）"""
        mock_cursor = _mock_db(mocker, fetchone=("suggestion_text",))
        mock_cursor.fetchone.side_effect = [(7,), ("suggestion_text",)]
        status, ai_id, result = query_ai_suggestion_from_database("user1", 1, 10)
        assert status is True
        assert ai_id == 7

    def test_ai_id_provided(self, mocker):
        """测试 query_ai_suggestion_from_database 传入 ai_id"""
        _mock_db(mocker, fetchone=("suggestion_text",))
        status, ai_id, result = query_ai_suggestion_from_database("user1", 1, 10, ai_id=3)
        assert status is True
        assert result == "suggestion_text"

    def test_db_error(self, mocker):
        """测试 query_ai_suggestion_from_database db_error（行683-688）"""
        _mock_db(mocker, db_error=True)
        status, ai_id, result = query_ai_suggestion_from_database("user1", 1, 10)
        assert status is False


class TestSetAiScoreDeepBranches:
    def test_no_ai_id_with_none_row(self, mocker):
        """测试 set_ai_score_to_database 中 ai_id=None, row[0] is None（行705-707）"""
        _mock_db(mocker, fetchone=(None,))
        status, msg = set_ai_score_to_database("user1", 1, 10)
        assert status is False
        assert "not finished" in msg

    def test_db_error_rollback(self, mocker):
        """测试 set_ai_score_to_database db_error rollback（行713-715）"""
        _mock_db(mocker, db_error=True)
        status, msg = set_ai_score_to_database("user1", 1, 10, ai_id=5)
        assert status is False
        assert "Database" in msg or "error" in msg.lower()


class TestQueryAiScoreDeepBranches:
    def test_no_uuid_with_ai_id_found(self, mocker):
        """测试 query_ai_score_from_database 无 uuid, 有 ai_id（行726-732）"""
        mock_cursor = _mock_db(mocker, fetchone=(4,))
        mock_cursor.fetchone.side_effect = [(3,), (4,)]
        status, result = query_ai_score_from_database("user1", 1, 10, uuid=None)
        assert status is True
        assert result == 4

    def test_no_uuid_no_ai_id_returns_true_none(self, mocker):
        """测试 query_ai_score_from_database 无 uuid, 无 ai_id（行731-732）"""
        _mock_db(mocker, fetchone=(None,))
        status, result = query_ai_score_from_database("user1", 1, 10, uuid=None)
        assert status is True
        assert result is None

    def test_with_valid_uuid(self, mocker):
        """测试 query_ai_score_from_database 有 uuid（行734）"""
        _mock_db(mocker, fetchone=(5,))
        status, result = query_ai_score_from_database("user1", 1, 10, uuid="valid-uuid")
        assert status is True
        assert result == 5


class TestUpdateAiResultDeepBranches:
    def test_db_error_rollback(self, mocker):
        """测试 update_ai_result db_error rollback（行624-626）"""
        _mock_db(mocker, db_error=True)
        status = update_ai_result("user1", 1, "req1", 10, "suggestion", "completed")
        assert status is False


class TestCreateAiInfoDeepBranches:
    def test_db_error_rollback(self, mocker):
        """测试 create_ai_info_to_database db_error rollback（行603-605）"""
        _mock_db(mocker, db_error=True)
        status, ai_id = create_ai_info_to_database("user1", 1, 10, "req1", "/file.c", "mode", "cmd")
        assert status is False


class TestQueryUserIdDeepBranches:
    def test_db_error_rollback(self, mocker):
        """测试 query_user_id_from_database db_error rollback（行578-580）"""
        _mock_db(mocker, db_error=True)
        status, user_id = query_user_id_from_database("user1", 1)
        assert status is False


class TestUpdateFileRemovedDeepBranches:
    def test_db_error_rollback(self, mocker):
        """测试 update_file_removed_to_database db_error rollback（行489-491）"""
        _mock_db(mocker, db_error=True)
        status = update_file_removed_to_database("user1", 1, 100)
        assert status is False


class TestExtractZipfileLargeZipFile:
    def test_large_zip_file(self, tmp_path):
        """测试 LargeZipFile 异常（行123分支）"""
        import zipfile
        src = tmp_path / "test.zip"
        with zipfile.ZipFile(str(src), 'w') as zf:
            zf.writestr("hello.txt", "hello")
        dst = tmp_path / "out"
        with patch('zipfile.ZipFile.__init__', side_effect=zipfile.LargeZipFile("too large")):
            result = extract_zipfile(str(src), str(dst))
            assert result is False
