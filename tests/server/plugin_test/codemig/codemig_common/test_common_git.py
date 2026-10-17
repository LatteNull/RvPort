import os
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, PropertyMock, mock_open

from plugin.codemig.codemig_common.common_git import (
    get_repo_path,
    convert_abs_path_to_repo_path,
    _is_revert_commit,
    commit_git_repo,
    generate_patch_from_initial_commit,
    generate_patch_between,
    query_original_file_from_git,
    query_new_files_from_git,
    revert_to_last_commit,
    restore_workspace,
)


# ---------------------------------------------------------------------------
# get_repo_path
# ---------------------------------------------------------------------------
class TestGetRepoPath:
    @patch('plugin.codemig.codemig_common.common_git.get_codemig_data_path',
           return_value='/data')
    def test_returns_correct_path(self, _):
        result = get_repo_path('user1', 5)
        assert result == Path('/data/user1/5/changed')

    @patch('plugin.codemig.codemig_common.common_git.get_codemig_data_path',
           return_value='/data')
    def test_different_user_and_dir(self, _):
        result = get_repo_path('admin', 100)
        assert result == Path('/data/admin/100/changed')


# ---------------------------------------------------------------------------
# convert_abs_path_to_repo_path
# ---------------------------------------------------------------------------
class TestConvertAbsPathToRepoPath:
    @patch('plugin.codemig.codemig_common.common_git.get_repo_path',
           return_value=Path('/data/user1/5/changed'))
    def test_converts_absolute_path(self, _):
        status, rel_path = convert_abs_path_to_repo_path(
            'user1', 5, Path('/data/user1/5/changed/src/main.c'))
        assert status is True
        assert str(rel_path).endswith('src/main.c')

    @patch('plugin.codemig.codemig_common.common_git.get_repo_path',
           return_value=Path('/data/user1/5/changed'))
    def test_relative_path_returns_false(self, _):
        status, msg = convert_abs_path_to_repo_path(
            'user1', 5, Path('relative/path'))
        assert status is False

    @patch('plugin.codemig.codemig_common.common_git.get_repo_path',
           return_value=Path('/data/user1/5/changed'))
    def test_exact_repo_path(self, _):
        status, rel_path = convert_abs_path_to_repo_path(
            'user1', 5, Path('/data/user1/5/changed'))
        assert status is True


# ---------------------------------------------------------------------------
# _is_revert_commit
# ---------------------------------------------------------------------------
class TestIsRevertCommit:
    def test_none_commit(self):
        status, hash_val = _is_revert_commit(None)
        assert status is False
        assert hash_val is None

    def test_empty_message(self):
        mock_commit = MagicMock()
        mock_commit.message = None
        status, hash_val = _is_revert_commit(mock_commit)
        assert status is False

    def test_revert_commit(self):
        mock_commit = MagicMock()
        mock_commit.message = "revert file.txt from commit abc123 last commit: def456"
        status, hash_val = _is_revert_commit(mock_commit)
        assert status is True
        assert hash_val == "def456"

    def test_revert_case_insensitive(self):
        mock_commit = MagicMock()
        mock_commit.message = "Revert changes last commit: abc123"
        status, hash_val = _is_revert_commit(mock_commit)
        assert status is True
        assert hash_val == "abc123"

    def test_non_revert_commit(self):
        mock_commit = MagicMock()
        mock_commit.message = "Save type:manual stage:init"
        status, hash_val = _is_revert_commit(mock_commit)
        assert status is False
        assert hash_val is None

    def test_from_to_commit_with_last(self):
        mock_commit = MagicMock()
        mock_commit.message = "from commit abc to commit def last commit: xyz789"
        status, hash_val = _is_revert_commit(mock_commit)
        assert status is True
        assert hash_val == "xyz789"

    def test_whitespace_message(self):
        mock_commit = MagicMock()
        mock_commit.message = "   \n  "
        status, hash_val = _is_revert_commit(mock_commit)
        assert status is False

    def test_only_revert_no_last_commit(self):
        mock_commit = MagicMock()
        mock_commit.message = "revert some changes"
        status, hash_val = _is_revert_commit(mock_commit)
        assert status is False

    def test_only_last_commit_no_revert(self):
        mock_commit = MagicMock()
        mock_commit.message = "save last commit: abc123"
        status, hash_val = _is_revert_commit(mock_commit)
        assert status is False

    def test_from_to_without_last_commit(self):
        mock_commit = MagicMock()
        mock_commit.message = "from commit abc to commit def"
        status, hash_val = _is_revert_commit(mock_commit)
        assert status is False


# ---------------------------------------------------------------------------
# commit_git_repo
# ---------------------------------------------------------------------------
class TestCommitGitRepo:
    @patch('plugin.codemig.codemig_common.common_git.get_repo_path')
    def test_code_path_not_exist(self, mock_repo_path):
        mock_path = MagicMock()
        mock_path.exists.return_value = False
        mock_repo_path.return_value = mock_path
        status, msg = commit_git_repo('user1', 1, 'manual', 'init')
        assert status is False
        assert 'not exist' in msg

    @patch('plugin.codemig.codemig_common.common_git.Repo')
    @patch('plugin.codemig.codemig_common.common_git.get_repo_path')
    def test_dirty_repo_commit_success(self, mock_repo_path, mock_repo_class):
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_repo_path.return_value = mock_path

        mock_repo = MagicMock()
        mock_repo.is_dirty.return_value = True
        mock_repo.git = MagicMock()
        mock_commit = MagicMock()
        mock_commit.hexsha = 'abc123'
        mock_commit.message = 'test message'
        mock_commit.committed_datetime.strftime.return_value = '2025-01-01 00:00:00'
        mock_repo.head.commit = mock_commit
        mock_repo_class.return_value = mock_repo

        status, result = commit_git_repo('user1', 1, 'manual', 'init')
        assert status is True
        assert result[0] == 'abc123'
        mock_repo.git.commit.assert_called_once()

    @patch('plugin.codemig.codemig_common.common_git.Repo')
    @patch('plugin.codemig.codemig_common.common_git.get_repo_path')
    def test_clean_repo_no_commit(self, mock_repo_path, mock_repo_class):
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_repo_path.return_value = mock_path

        mock_repo = MagicMock()
        mock_repo.is_dirty.return_value = False
        # head.commit raises ValueError when no commits
        type(mock_repo.head).commit = PropertyMock(side_effect=ValueError("no commits"))
        mock_repo_class.return_value = mock_repo

        status, msg = commit_git_repo('user1', 1, 'manual', 'init')
        assert status is False
        assert 'No commits' in msg

    @patch('plugin.codemig.codemig_common.common_git.Repo')
    @patch('plugin.codemig.codemig_common.common_git.get_repo_path')
    def test_init_new_repo(self, mock_repo_path, mock_repo_class):
        from git.exc import InvalidGitRepositoryError
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_repo_path.return_value = mock_path

        mock_repo = MagicMock()
        mock_repo.is_dirty.return_value = True
        mock_repo.git = MagicMock()
        mock_commit = MagicMock()
        mock_commit.hexsha = 'def456'
        mock_commit.message = 'init'
        mock_commit.committed_datetime.strftime.return_value = '2025-01-01 00:00:00'
        mock_repo.head.commit = mock_commit
        mock_repo_class.side_effect = [InvalidGitRepositoryError, mock_repo]
        mock_repo_class.init.return_value = mock_repo

        status, result = commit_git_repo('user1', 1, 'manual', 'init')
        assert status is True


# ---------------------------------------------------------------------------
# generate_patch_from_initial_commit
# ---------------------------------------------------------------------------
class TestGeneratePatchFromInitialCommit:
    @patch('plugin.codemig.codemig_common.common_git.get_repo_path')
    def test_code_path_not_exist(self, mock_repo_path):
        mock_path = MagicMock()
        mock_path.exists.return_value = False
        mock_repo_path.return_value = mock_path
        status, msg = generate_patch_from_initial_commit('user1', 1)
        assert status is False

    @patch('plugin.codemig.codemig_common.common_git.Repo')
    @patch('plugin.codemig.codemig_common.common_git.get_repo_path')
    def test_not_git_repo(self, mock_repo_path, mock_repo_class):
        from git.exc import InvalidGitRepositoryError
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_repo_path.return_value = mock_path
        mock_repo_class.side_effect = InvalidGitRepositoryError("not a repo")

        status, msg = generate_patch_from_initial_commit('user1', 1)
        assert status is False
        assert 'not found' in msg.lower() or 'not initialized' in msg.lower()

    @patch('plugin.codemig.codemig_common.common_git.Repo')
    @patch('plugin.codemig.codemig_common.common_git.get_repo_path')
    def test_no_commits(self, mock_repo_path, mock_repo_class):
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_repo_path.return_value = mock_path
        mock_repo = MagicMock()
        mock_repo.iter_commits.return_value = iter([])
        mock_repo_class.return_value = mock_repo

        status, msg = generate_patch_from_initial_commit('user1', 1)
        assert status is False

    @patch('plugin.codemig.codemig_common.common_git.Repo')
    @patch('plugin.codemig.codemig_common.common_git.get_repo_path')
    def test_single_commit(self, mock_repo_path, mock_repo_class):
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_repo_path.return_value = mock_path
        mock_commit = MagicMock()
        mock_commit.hexsha = 'abc12345'
        mock_commit.message = 'initial'
        mock_repo = MagicMock()
        mock_repo.iter_commits.return_value = iter([mock_commit])
        mock_repo.head.commit = mock_commit
        mock_repo_class.return_value = mock_repo

        status, patch = generate_patch_from_initial_commit('user1', 1)
        assert status is True
        assert patch == ""

    @patch('plugin.codemig.codemig_common.common_git.Repo')
    @patch('plugin.codemig.codemig_common.common_git.get_repo_path')
    def test_multiple_commits_with_diff(self, mock_repo_path, mock_repo_class):
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_repo_path.return_value = mock_path

        initial = MagicMock()
        initial.hexsha = 'aaa11111'
        initial.message = 'initial commit'
        current = MagicMock()
        current.hexsha = 'bbb22222'
        current.message = 'second commit'

        mock_repo = MagicMock()
        mock_repo.iter_commits.return_value = iter([current, initial])
        mock_repo.head.commit = current
        mock_repo.git.diff.return_value = "--- a/file.c\n+++ b/file.c\n@@ -1 +1 @@\n-old\n+new\n"
        mock_repo_class.return_value = mock_repo

        status, patch = generate_patch_from_initial_commit('user1', 1)
        assert status is True
        assert 'Patch file generated' in patch
        assert 'aaa11111' in patch

    @patch('plugin.codemig.codemig_common.common_git.Repo')
    @patch('plugin.codemig.codemig_common.common_git.get_repo_path')
    def test_empty_diff(self, mock_repo_path, mock_repo_class):
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_repo_path.return_value = mock_path

        initial = MagicMock()
        initial.hexsha = 'aaa11111'
        current = MagicMock()
        current.hexsha = 'bbb22222'

        mock_repo = MagicMock()
        mock_repo.iter_commits.return_value = iter([current, initial])
        mock_repo.head.commit = current
        mock_repo.git.diff.return_value = ""
        mock_repo_class.return_value = mock_repo

        status, patch = generate_patch_from_initial_commit('user1', 1)
        assert status is True
        assert patch == ""


# ---------------------------------------------------------------------------
# query_original_file_from_git
# ---------------------------------------------------------------------------
class TestQueryOriginalFileFromGit:
    @patch('plugin.codemig.codemig_common.common_git.query_file_path_from_database')
    def test_db_query_fails(self, mock_query):
        mock_query.return_value = (False, None)
        status, content = query_original_file_from_git('user1', 1, 100)
        assert status is False
        assert content == ""

    @patch('plugin.codemig.codemig_common.common_git.query_file_path_from_database')
    def test_db_returns_empty_path(self, mock_query):
        mock_query.return_value = (True, None)
        status, content = query_original_file_from_git('user1', 1, 100)
        assert status is False
        assert content == ""

    @patch('plugin.codemig.codemig_common.common_git.convert_abs_path_to_repo_path')
    @patch('plugin.codemig.codemig_common.common_git.query_file_path_from_database')
    def test_convert_path_fails(self, mock_query, mock_convert):
        mock_query.return_value = (True, '/data/user1/1/changed/file.c')
        mock_convert.return_value = (False, "error")
        status, content = query_original_file_from_git('user1', 1, 100)
        assert status is False

    @patch('plugin.codemig.codemig_common.common_git.get_repo_path')
    @patch('plugin.codemig.codemig_common.common_git.convert_abs_path_to_repo_path')
    @patch('plugin.codemig.codemig_common.common_git.query_file_path_from_database')
    def test_code_path_not_exist(self, mock_query, mock_convert, mock_repo_path):
        mock_query.return_value = (True, '/data/user1/1/changed/file.c')
        mock_convert.return_value = (True, Path('/file.c'))
        mock_path = MagicMock()
        mock_path.exists.return_value = False
        mock_repo_path.return_value = mock_path
        status, content = query_original_file_from_git('user1', 1, 100)
        assert status is False

    @patch('plugin.codemig.codemig_common.common_git.Repo')
    @patch('plugin.codemig.codemig_common.common_git.get_repo_path')
    @patch('plugin.codemig.codemig_common.common_git.convert_abs_path_to_repo_path')
    @patch('plugin.codemig.codemig_common.common_git.query_file_path_from_database')
    def test_no_commits(self, mock_query, mock_convert, mock_repo_path, mock_repo_class):
        mock_query.return_value = (True, '/data/user1/1/changed/file.c')
        mock_convert.return_value = (True, Path('/file.c'))
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_repo_path.return_value = mock_path
        mock_repo = MagicMock()
        mock_repo.iter_commits.return_value = iter([])
        mock_repo_class.return_value = mock_repo

        status, content = query_original_file_from_git('user1', 1, 100)
        assert status is False

    @patch('plugin.codemig.codemig_common.common_git.Repo')
    @patch('plugin.codemig.codemig_common.common_git.get_repo_path')
    @patch('plugin.codemig.codemig_common.common_git.convert_abs_path_to_repo_path')
    @patch('plugin.codemig.codemig_common.common_git.query_file_path_from_database')
    def test_file_not_in_initial_commit(self, mock_query, mock_convert, mock_repo_path, mock_repo_class):
        mock_query.return_value = (True, '/data/user1/1/changed/newfile.c')
        mock_convert.return_value = (True, Path('/newfile.c'))
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_repo_path.return_value = mock_path
        mock_commit = MagicMock()
        mock_tree = MagicMock()
        mock_tree.__truediv__ = MagicMock(side_effect=KeyError("not found"))
        mock_commit.tree = mock_tree
        mock_repo = MagicMock()
        mock_repo.iter_commits.return_value = iter([mock_commit])
        mock_repo_class.return_value = mock_repo

        status, content = query_original_file_from_git('user1', 1, 100)
        assert status is True
        assert content == ""

    @patch('plugin.codemig.codemig_common.common_git.Repo')
    @patch('plugin.codemig.codemig_common.common_git.get_repo_path')
    @patch('plugin.codemig.codemig_common.common_git.convert_abs_path_to_repo_path')
    @patch('plugin.codemig.codemig_common.common_git.query_file_path_from_database')
    def test_read_file_success(self, mock_query, mock_convert, mock_repo_path, mock_repo_class):
        mock_query.return_value = (True, '/data/user1/1/changed/file.c')
        mock_convert.return_value = (True, Path('/file.c'))
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_repo_path.return_value = mock_path

        mock_blob = MagicMock()
        mock_blob.data_stream.read.return_value = b'file content here'
        mock_tree = MagicMock()
        mock_tree.__truediv__ = MagicMock(return_value=mock_blob)
        mock_commit = MagicMock()
        mock_commit.tree = mock_tree

        mock_repo = MagicMock()
        mock_repo.iter_commits.return_value = iter([mock_commit])
        mock_repo_class.return_value = mock_repo

        status, content = query_original_file_from_git('user1', 1, 100)
        assert status is True
        assert content == 'file content here'

    @patch('plugin.codemig.codemig_common.common_git.Repo')
    @patch('plugin.codemig.codemig_common.common_git.get_repo_path')
    @patch('plugin.codemig.codemig_common.common_git.convert_abs_path_to_repo_path')
    @patch('plugin.codemig.codemig_common.common_git.query_file_path_from_database')
    def test_unicode_decode_error(self, mock_query, mock_convert, mock_repo_path, mock_repo_class):
        mock_query.return_value = (True, '/data/user1/1/changed/file.c')
        mock_convert.return_value = (True, Path('/file.c'))
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_repo_path.return_value = mock_path

        mock_blob = MagicMock()
        mock_blob.data_stream.read.return_value = b'\xff\xfe invalid utf-8'
        mock_tree = MagicMock()
        mock_tree.__truediv__ = MagicMock(return_value=mock_blob)
        mock_commit = MagicMock()
        mock_commit.tree = mock_tree

        mock_repo = MagicMock()
        mock_repo.iter_commits.return_value = iter([mock_commit])
        mock_repo_class.return_value = mock_repo

        status, content = query_original_file_from_git('user1', 1, 100)
        assert status is True

    @patch('plugin.codemig.codemig_common.common_git.convert_abs_path_to_repo_path')
    @patch('plugin.codemig.codemig_common.common_git.query_file_path_from_database')
    def test_outer_exception(self, mock_query, mock_convert):
        mock_query.return_value = (True, '/data/user1/1/changed/file.c')
        mock_convert.side_effect = OSError("test error")
        status, content = query_original_file_from_git('user1', 1, 100)
        assert status is False


# ---------------------------------------------------------------------------
# query_new_files_from_git
# ---------------------------------------------------------------------------
class TestQueryNewFilesFromGit:
    @patch('plugin.codemig.codemig_common.common_git.get_repo_path')
    def test_code_path_not_exist(self, mock_repo_path):
        mock_path = MagicMock()
        mock_path.exists.return_value = False
        mock_repo_path.return_value = mock_path
        status, files = query_new_files_from_git('user1', 1)
        assert status is False
        assert files == []

    @patch('plugin.codemig.codemig_common.common_git.Repo')
    @patch('plugin.codemig.codemig_common.common_git.get_repo_path')
    def test_init_new_repo(self, mock_repo_path, mock_repo_class):
        from git.exc import InvalidGitRepositoryError
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_repo_path.return_value = mock_path

        mock_repo = MagicMock()
        mock_repo_class.side_effect = InvalidGitRepositoryError
        mock_repo_class.init.return_value = mock_repo

        status, files = query_new_files_from_git('user1', 1)
        assert status is True
        assert files == []

    @patch('plugin.codemig.codemig_common.common_git.Repo')
    @patch('plugin.codemig.codemig_common.common_git.get_repo_path')
    def test_untracked_files(self, mock_repo_path, mock_repo_class):
        mock_code_path = MagicMock()
        mock_code_path.exists.return_value = True
        mock_repo_path.return_value = mock_code_path

        mock_repo = MagicMock()
        mock_repo.untracked_files = ['new_file.c', 'another.py']
        # mock code_path / file_path
        mock_file1 = MagicMock()
        mock_file1.exists.return_value = True
        mock_file1.is_file.return_value = True
        mock_file2 = MagicMock()
        mock_file2.exists.return_value = True
        mock_file2.is_file.return_value = True
        mock_code_path.__truediv__ = lambda self, other: (
            mock_file1 if other == 'new_file.c' else mock_file2
        )
        mock_repo_class.return_value = mock_repo

        status, files = query_new_files_from_git('user1', 1)
        assert status is True
        assert len(files) == 2

    @patch('plugin.codemig.codemig_common.common_git.Repo')
    @patch('plugin.codemig.codemig_common.common_git.get_repo_path')
    def test_no_untracked_files(self, mock_repo_path, mock_repo_class):
        mock_code_path = MagicMock()
        mock_code_path.exists.return_value = True
        mock_repo_path.return_value = mock_code_path
        mock_repo = MagicMock()
        mock_repo.untracked_files = []
        mock_repo_class.return_value = mock_repo

        status, files = query_new_files_from_git('user1', 1)
        assert status is True
        assert files == []

    @patch('plugin.codemig.codemig_common.common_git.Repo')
    @patch('plugin.codemig.codemig_common.common_git.get_repo_path')
    def test_untracked_error(self, mock_repo_path, mock_repo_class):
        mock_code_path = MagicMock()
        mock_code_path.exists.return_value = True
        mock_repo_path.return_value = mock_code_path

        class BadIter:
            def __iter__(self):
                raise AttributeError("err")
        mock_repo = MagicMock()
        mock_repo.untracked_files = BadIter()
        mock_repo_class.return_value = mock_repo

        status, files = query_new_files_from_git('user1', 1)
        assert status is False
        assert files == []


# ---------------------------------------------------------------------------
# revert_to_last_commit
# ---------------------------------------------------------------------------
class TestRevertToLastCommit:
    @patch('plugin.codemig.codemig_common.common_git.get_repo_path')
    def test_code_path_not_exist(self, mock_repo_path):
        mock_path = MagicMock()
        mock_path.exists.return_value = False
        mock_repo_path.return_value = mock_path
        status, msg, content = revert_to_last_commit('user1', 1, Path('/some/file.c'))
        assert status is False

    @patch('plugin.codemig.codemig_common.common_git.Repo')
    @patch('plugin.codemig.codemig_common.common_git.get_repo_path')
    def test_not_git_repo(self, mock_repo_path, mock_repo_class):
        from git.exc import InvalidGitRepositoryError
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_repo_path.return_value = mock_path
        mock_repo_class.side_effect = InvalidGitRepositoryError("not a repo")

        status, msg, content = revert_to_last_commit('user1', 1, Path('/data/user1/1/changed/file.c'))
        assert status is False

    @patch('plugin.codemig.codemig_common.common_git.Repo')
    @patch('plugin.codemig.codemig_common.common_git.convert_abs_path_to_repo_path')
    @patch('plugin.codemig.codemig_common.common_git.get_repo_path')
    def test_no_commits_for_file(self, mock_repo_path, mock_convert, mock_repo_class):
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_repo_path.return_value = mock_path
        mock_repo_class.return_value = MagicMock()
        mock_convert.return_value = (True, Path('/file.c'))
        mock_repo = MagicMock()
        mock_repo.iter_commits.return_value = iter([])
        mock_repo_class.return_value = mock_repo

        status, msg, content = revert_to_last_commit('user1', 1, Path('/data/user1/1/changed/file.c'))
        assert status is True
        assert '没有可回退版本' in msg

    @patch('plugin.codemig.codemig_common.common_git.convert_abs_path_to_repo_path')
    @patch('plugin.codemig.codemig_common.common_git.get_repo_path')
    def test_convert_fails(self, mock_repo_path, mock_convert):
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_repo_path.return_value = mock_path

        with patch('plugin.codemig.codemig_common.common_git.Repo') as mock_repo_class:
            mock_repo_class.return_value = MagicMock()
            mock_convert.return_value = (False, "error")
            status, msg, content = revert_to_last_commit('user1', 1, Path('/data/user1/1/changed/file.c'))
            assert status is False


# ---------------------------------------------------------------------------
# restore_workspace
# ---------------------------------------------------------------------------
class TestRestoreWorkspace:
    @patch('plugin.codemig.codemig_common.common_git.get_repo_path')
    def test_code_path_not_exist(self, mock_repo_path):
        mock_path = MagicMock()
        mock_path.exists.return_value = False
        mock_repo_path.return_value = mock_path
        status, msg = restore_workspace('user1', 1)
        assert status is False

    @patch('plugin.codemig.codemig_common.common_git.Repo')
    @patch('plugin.codemig.codemig_common.common_git.get_repo_path')
    def test_not_git_repo(self, mock_repo_path, mock_repo_class):
        from git.exc import InvalidGitRepositoryError
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_repo_path.return_value = mock_path
        mock_repo_class.side_effect = InvalidGitRepositoryError("not a repo")

        status, msg = restore_workspace('user1', 1)
        assert status is False

    @patch('plugin.codemig.codemig_common.common_git.Repo')
    @patch('plugin.codemig.codemig_common.common_git.get_repo_path')
    def test_restore_success(self, mock_repo_path, mock_repo_class):
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_path.as_posix.return_value = '/data/user1/1/changed'
        mock_repo_path.return_value = mock_path
        mock_repo = MagicMock()
        mock_repo.git = MagicMock()
        mock_repo_class.return_value = mock_repo

        status, msg = restore_workspace('user1', 1)
        assert status is True
        assert msg == ''
        mock_repo.git.checkout.assert_called_once()
        mock_repo.git.clean.assert_called_once()

    @patch('plugin.codemig.codemig_common.common_git.Repo')
    @patch('plugin.codemig.codemig_common.common_git.get_repo_path')
    def test_git_command_error(self, mock_repo_path, mock_repo_class):
        from git.exc import GitCommandError
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_repo_path.return_value = mock_path
        mock_repo = MagicMock()
        mock_repo.git.checkout.side_effect = GitCommandError("checkout error")
        mock_repo_class.return_value = mock_repo

        status, msg = restore_workspace('user1', 1)
        assert status is False
        assert 'Git command error' in msg


# ---------------------------------------------------------------------------
# generate_patch_from_initial_commit - additional branches
# ---------------------------------------------------------------------------
class TestGeneratePatchAdditional:
    @patch('plugin.codemig.codemig_common.common_git.Repo')
    @patch('plugin.codemig.codemig_common.common_git.get_repo_path')
    def test_diff_without_trailing_newline(self, mock_repo_path, mock_repo_class):
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_repo_path.return_value = mock_path

        initial = MagicMock()
        initial.hexsha = 'aaa11111'
        initial.message = 'initial commit'
        current = MagicMock()
        current.hexsha = 'bbb22222'
        current.message = 'second commit'

        mock_repo = MagicMock()
        mock_repo.iter_commits.return_value = iter([current, initial])
        mock_repo.head.commit = current
        # diff without trailing newline
        mock_repo.git.diff.return_value = "--- a/file.c\n+++ b/file.c\n@@ -1 +1 @@\n-old\n+new"
        mock_repo_class.return_value = mock_repo

        status, patch = generate_patch_from_initial_commit('user1', 1)
        assert status is True
        assert patch.endswith("\n")

    @patch('plugin.codemig.codemig_common.common_git.Repo')
    @patch('plugin.codemig.codemig_common.common_git.get_repo_path')
    def test_git_command_error(self, mock_repo_path, mock_repo_class):
        from git.exc import GitCommandError
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_repo_path.return_value = mock_path

        initial = MagicMock()
        initial.hexsha = 'aaa11111'
        current = MagicMock()
        current.hexsha = 'bbb22222'

        mock_repo = MagicMock()
        mock_repo.iter_commits.return_value = iter([current, initial])
        mock_repo.head.commit = current
        mock_repo.git.diff.side_effect = GitCommandError("diff error")
        mock_repo_class.return_value = mock_repo

        status, msg = generate_patch_from_initial_commit('user1', 1)
        assert status is False
        assert 'Git command error' in msg

    @patch('plugin.codemig.codemig_common.common_git.Repo')
    @patch('plugin.codemig.codemig_common.common_git.get_repo_path')
    def test_attribute_error(self, mock_repo_path, mock_repo_class):
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_repo_path.return_value = mock_path

        mock_repo = MagicMock()
        mock_repo.iter_commits.return_value = iter([])
        mock_repo.head.commit = MagicMock()
        type(mock_repo.head.commit).hexsha = PropertyMock(side_effect=AttributeError("no attr"))
        mock_repo_class.return_value = mock_repo

        status, msg = generate_patch_from_initial_commit('user1', 1)
        assert status is False


# ---------------------------------------------------------------------------
# revert_to_last_commit - deep branch tests
# ---------------------------------------------------------------------------
class TestRevertToLastCommitDeep:
    @patch('plugin.codemig.codemig_common.common_git._is_revert_commit')
    @patch('plugin.codemig.codemig_common.common_git.Repo')
    @patch('plugin.codemig.codemig_common.common_git.convert_abs_path_to_repo_path')
    @patch('plugin.codemig.codemig_common.common_git.get_repo_path')
    def test_simple_revert_non_revert_commit(self, mock_repo_path, mock_convert, mock_repo_class, mock_is_revert):
        """Test: first commit is not a revert, so to_this_commit=True, next commit becomes target"""
        mock_code_path = MagicMock()
        mock_code_path.exists.return_value = True
        mock_repo_path.return_value = mock_code_path
        mock_convert.return_value = (True, Path('/file.c'))

        commit1 = MagicMock()
        commit1.hexsha = 'aaa111'
        commit2 = MagicMock()
        commit2.hexsha = 'bbb222'

        mock_repo = MagicMock()
        # First: non-revert -> sets to_this_commit=True
        # Second: becomes target (non-revert), to_this_commit was True
        # Third: target_commit is set, records last_commit_hash
        commit3 = MagicMock()
        commit3.hexsha = 'ccc333'
        mock_repo.iter_commits.return_value = iter([commit1, commit2, commit3])

        # commit1 is not revert -> to_this_commit = True
        # commit2: to_this_commit is True, dist_hash is None so not skipped
        #   becomes target, _is_revert_commit returns False
        # commit3: target_commit is set, records last_commit_hash
        mock_is_revert.side_effect = [
            (False, None),   # commit1: not a revert
            (False, None),   # commit2: target, not revert
        ]
        mock_repo.head.commit.hexsha = 'current_hash'

        blob = MagicMock()
        blob.data_stream.read.return_value = b'reverted content'
        commit2.tree.__truediv__ = MagicMock(return_value=blob)

        mock_repo.is_dirty.return_value = True
        mock_repo.git = MagicMock()
        mock_repo_class.return_value = mock_repo

        with patch('builtins.open', mock_open()):
            status, msg, content = revert_to_last_commit('user1', 1, Path('/data/user1/1/changed/file.c'))
        assert status is True
        assert content == 'reverted content'

    @patch('plugin.codemig.codemig_common.common_git._is_revert_commit')
    @patch('plugin.codemig.codemig_common.common_git.Repo')
    @patch('plugin.codemig.codemig_common.common_git.convert_abs_path_to_repo_path')
    @patch('plugin.codemig.codemig_common.common_git.get_repo_path')
    def test_revert_commit_chain(self, mock_repo_path, mock_convert, mock_repo_class, mock_is_revert):
        """Test: first commit is a revert, sets dist_hash"""
        mock_code_path = MagicMock()
        mock_code_path.exists.return_value = True
        mock_repo_path.return_value = mock_code_path
        mock_convert.return_value = (True, Path('/file.c'))

        commit1 = MagicMock()
        commit1.hexsha = 'aaa111'
        commit2 = MagicMock()
        commit2.hexsha = 'dist_hash_1'  # matches dist_hash
        commit3 = MagicMock()
        commit3.hexsha = 'ccc333'

        mock_repo = MagicMock()
        mock_repo.iter_commits.return_value = iter([commit1, commit2, commit3])

        # commit1 is a revert -> dist_hash = 'dist_hash_1'
        # commit2: to_this_commit still False, is revert -> already has dist_hash
        # commit3: not a revert -> to_this_commit = True
        # No more commits -> target_commit is None
        mock_is_revert.side_effect = [
            (True, 'dist_hash_1'),   # commit1: revert, sets dist_hash
            (True, 'dist_hash_2'),   # commit2: still in initial loop, dist_hash already set
            (False, None),           # commit3: not revert, sets to_this_commit
        ]

        mock_repo_class.return_value = mock_repo

        status, msg, content = revert_to_last_commit('user1', 1, Path('/data/user1/1/changed/file.c'))
        assert status is True
        assert '没有可回退版本' in msg

    @patch('plugin.codemig.codemig_common.common_git._is_revert_commit')
    @patch('plugin.codemig.codemig_common.common_git.Repo')
    @patch('plugin.codemig.codemig_common.common_git.convert_abs_path_to_repo_path')
    @patch('plugin.codemig.codemig_common.common_git.get_repo_path')
    def test_blob_read_error(self, mock_repo_path, mock_convert, mock_repo_class, mock_is_revert):
        """Test: target commit found but blob read fails"""
        mock_code_path = MagicMock()
        mock_code_path.exists.return_value = True
        mock_repo_path.return_value = mock_code_path
        mock_convert.return_value = (True, Path('/file.c'))

        commit1 = MagicMock()
        commit1.hexsha = 'aaa111'
        commit2 = MagicMock()
        commit2.hexsha = 'bbb222'

        mock_repo = MagicMock()
        mock_repo.iter_commits.return_value = iter([commit1, commit2])

        # commit1 is not revert -> to_this_commit=True
        # commit2: target, is not revert
        mock_is_revert.side_effect = [
            (False, None),
            (False, None),
        ]

        commit2.tree.__truediv__ = MagicMock(side_effect=KeyError("not found"))
        mock_repo_class.return_value = mock_repo

        status, msg, content = revert_to_last_commit('user1', 1, Path('/data/user1/1/changed/file.c'))
        assert status is False
        assert 'Failed to read' in msg

    @patch('plugin.codemig.codemig_common.common_git._is_revert_commit')
    @patch('plugin.codemig.codemig_common.common_git.Repo')
    @patch('plugin.codemig.codemig_common.common_git.convert_abs_path_to_repo_path')
    @patch('plugin.codemig.codemig_common.common_git.get_repo_path')
    def test_write_file_error(self, mock_repo_path, mock_convert, mock_repo_class, mock_is_revert):
        """Test: blob read succeeds but writing file fails"""
        mock_code_path = MagicMock()
        mock_code_path.exists.return_value = True
        mock_repo_path.return_value = mock_code_path
        mock_convert.return_value = (True, Path('/file.c'))

        commit1 = MagicMock()
        commit1.hexsha = 'aaa111'
        commit2 = MagicMock()
        commit2.hexsha = 'bbb222'

        mock_repo = MagicMock()
        mock_repo.iter_commits.return_value = iter([commit1, commit2])

        mock_is_revert.side_effect = [
            (False, None),
            (False, None),
        ]

        blob = MagicMock()
        blob.data_stream.read.return_value = b'content'
        commit2.tree.__truediv__ = MagicMock(return_value=blob)

        mock_code_path.__truediv__ = MagicMock(return_value=MagicMock())
        mock_repo_class.return_value = mock_repo

        with patch('builtins.open', side_effect=PermissionError("no write")):
            status, msg, content = revert_to_last_commit('user1', 1, Path('/data/user1/1/changed/file.c'))
        assert status is False
        assert 'Failed to write' in msg

    @patch('plugin.codemig.codemig_common.common_git._is_revert_commit')
    @patch('plugin.codemig.codemig_common.common_git.Repo')
    @patch('plugin.codemig.codemig_common.common_git.convert_abs_path_to_repo_path')
    @patch('plugin.codemig.codemig_common.common_git.get_repo_path')
    def test_dirty_repo_commit(self, mock_repo_path, mock_convert, mock_repo_class, mock_is_revert):
        """Test: repo is dirty after revert, commits the change"""
        mock_code_path = MagicMock()
        mock_code_path.exists.return_value = True
        mock_repo_path.return_value = mock_code_path
        mock_convert.return_value = (True, Path('/file.c'))

        commit1 = MagicMock()
        commit1.hexsha = 'aaa111'
        commit2 = MagicMock()
        commit2.hexsha = 'bbb222'

        mock_repo = MagicMock()
        mock_repo.iter_commits.return_value = iter([commit1, commit2])

        mock_is_revert.side_effect = [
            (False, None),
            (False, None),
        ]

        blob = MagicMock()
        blob.data_stream.read.return_value = b'new content'
        commit2.tree.__truediv__ = MagicMock(return_value=blob)

        mock_repo.head.commit.hexsha = 'current_hash'
        mock_repo.is_dirty.return_value = True
        mock_repo.git = MagicMock()
        mock_code_path.__truediv__ = MagicMock(return_value=MagicMock())
        mock_repo_class.return_value = mock_repo

        with patch('builtins.open', mock_open()):
            status, msg, content = revert_to_last_commit('user1', 1, Path('/data/user1/1/changed/file.c'))
        assert status is True
        assert 'revert' in msg
        mock_repo.git.commit.assert_called_once()

    @patch('plugin.codemig.codemig_common.common_git._is_revert_commit')
    @patch('plugin.codemig.codemig_common.common_git.Repo')
    @patch('plugin.codemig.codemig_common.common_git.convert_abs_path_to_repo_path')
    @patch('plugin.codemig.codemig_common.common_git.get_repo_path')
    def test_git_command_error_on_commit(self, mock_repo_path, mock_convert, mock_repo_class, mock_is_revert):
        """Test: GitCommandError during commit"""
        from git.exc import GitCommandError
        mock_code_path = MagicMock()
        mock_code_path.exists.return_value = True
        mock_repo_path.return_value = mock_code_path
        mock_convert.return_value = (True, Path('/file.c'))

        commit1 = MagicMock()
        commit1.hexsha = 'aaa111'
        commit2 = MagicMock()
        commit2.hexsha = 'bbb222'

        mock_repo = MagicMock()
        mock_repo.iter_commits.return_value = iter([commit1, commit2])

        mock_is_revert.side_effect = [
            (False, None),
            (False, None),
        ]

        blob = MagicMock()
        blob.data_stream.read.return_value = b'content'
        commit2.tree.__truediv__ = MagicMock(return_value=blob)

        mock_repo.head.commit.hexsha = 'current_hash'
        mock_repo.is_dirty.return_value = True
        mock_repo.git.commit.side_effect = GitCommandError("commit error")
        mock_code_path.__truediv__ = MagicMock(return_value=MagicMock())
        mock_repo_class.return_value = mock_repo

        with patch('builtins.open', mock_open()):
            status, msg, content = revert_to_last_commit('user1', 1, Path('/data/user1/1/changed/file.c'))
        assert status is False
        assert 'Git command error' in msg

    @patch('plugin.codemig.codemig_common.common_git._is_revert_commit')
    @patch('plugin.codemig.codemig_common.common_git.Repo')
    @patch('plugin.codemig.codemig_common.common_git.convert_abs_path_to_repo_path')
    @patch('plugin.codemig.codemig_common.common_git.get_repo_path')
    def test_to_this_commit_skip_hash_mismatch(self, mock_repo_path, mock_convert, mock_repo_class, mock_is_revert):
        """Test: to_this_commit=True but hash doesn't match dist_hash, should skip"""
        mock_code_path = MagicMock()
        mock_code_path.exists.return_value = True
        mock_repo_path.return_value = mock_code_path
        mock_convert.return_value = (True, Path('/file.c'))

        commit1 = MagicMock()
        commit1.hexsha = 'revert_hash'
        commit2 = MagicMock()
        commit2.hexsha = 'mismatch_hash'  # doesn't match dist_hash
        commit3 = MagicMock()
        commit3.hexsha = 'dist_hash_target'
        commit4 = MagicMock()
        commit4.hexsha = 'ddd444'

        mock_repo = MagicMock()
        mock_repo.iter_commits.return_value = iter([commit1, commit2, commit3, commit4])

        # commit1: is revert -> dist_hash = 'dist_hash_target'
        # commit2: not revert -> to_this_commit=True
        # commit3: to_this_commit=True, dist_hash='dist_hash_target', commit2.hexsha mismatch -> skip
        # Wait, the logic is: after commit2 sets to_this_commit, commit3 enters `if to_this_commit:` branch
        # commit3: dist_hash != commit3.hexsha -> continue (skip)
        # commit4: dist_hash matches -> target_commit = commit4
        mock_is_revert.side_effect = [
            (True, 'dist_hash_target'),   # commit1: revert
            (False, None),                 # commit2: not revert -> to_this_commit=True
            (False, None),                 # commit3: skipped (hash mismatch)
            (False, None),                 # commit4: matches dist_hash, becomes target
        ]

        blob = MagicMock()
        blob.data_stream.read.return_value = b'content'
        commit4.tree.__truediv__ = MagicMock(return_value=blob)
        mock_repo.head.commit.hexsha = 'current'
        mock_repo.is_dirty.return_value = True
        mock_repo.git = MagicMock()
        mock_code_path.__truediv__ = MagicMock(return_value=MagicMock())
        mock_repo_class.return_value = mock_repo

        with patch('builtins.open', mock_open()):
            status, msg, content = revert_to_last_commit('user1', 1, Path('/data/user1/1/changed/file.c'))
        assert status is True

    @patch('plugin.codemig.codemig_common.common_git._is_revert_commit')
    @patch('plugin.codemig.codemig_common.common_git.Repo')
    @patch('plugin.codemig.codemig_common.common_git.convert_abs_path_to_repo_path')
    @patch('plugin.codemig.codemig_common.common_git.get_repo_path')
    def test_target_is_revert_commit(self, mock_repo_path, mock_convert, mock_repo_class, mock_is_revert):
        """Test: target commit is itself a revert commit"""
        mock_code_path = MagicMock()
        mock_code_path.exists.return_value = True
        mock_repo_path.return_value = mock_code_path
        mock_convert.return_value = (True, Path('/file.c'))

        commit1 = MagicMock()
        commit1.hexsha = 'aaa111'
        commit2 = MagicMock()
        commit2.hexsha = 'bbb222'

        mock_repo = MagicMock()
        mock_repo.iter_commits.return_value = iter([commit1, commit2])

        mock_is_revert.side_effect = [
            (False, None),        # commit1: not revert -> to_this_commit=True
            (True, 'revert_hash'), # commit2: target, and is a revert
        ]

        blob = MagicMock()
        blob.data_stream.read.return_value = b'reverted'
        commit2.tree.__truediv__ = MagicMock(return_value=blob)
        mock_repo.head.commit.hexsha = 'current'
        mock_repo.is_dirty.return_value = True
        mock_repo.git = MagicMock()
        mock_code_path.__truediv__ = MagicMock(return_value=MagicMock())
        mock_repo_class.return_value = mock_repo

        with patch('builtins.open', mock_open()):
            status, msg, content = revert_to_last_commit('user1', 1, Path('/data/user1/1/changed/file.c'))
        assert status is True
        assert 'last commit: revert_hash' in msg


# ---------------------------------------------------------------------------
# query_original_file_from_git - additional branch
# ---------------------------------------------------------------------------
class TestQueryOriginalFileAdditional:
    @patch('plugin.codemig.codemig_common.common_git.Repo')
    @patch('plugin.codemig.codemig_common.common_git.get_repo_path')
    @patch('plugin.codemig.codemig_common.common_git.convert_abs_path_to_repo_path')
    @patch('plugin.codemig.codemig_common.common_git.query_file_path_from_database')
    def test_invalid_git_repo(self, mock_query, mock_convert, mock_repo_path, mock_repo_class):
        from git.exc import InvalidGitRepositoryError
        mock_query.return_value = (True, '/data/user1/1/changed/file.c')
        mock_convert.return_value = (True, Path('/file.c'))
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_repo_path.return_value = mock_path
        mock_repo_class.side_effect = InvalidGitRepositoryError("not a repo")

        status, content = query_original_file_from_git('user1', 1, 100)
        assert status is False


# ---------------------------------------------------------------------------
# generate_patch_between（增量 patch 导出）
# ---------------------------------------------------------------------------
class TestGeneratePatchBetween:
    @patch('plugin.codemig.codemig_common.common_git.get_repo_path')
    def test_from_hash_empty(self, mock_repo_path):
        status, msg = generate_patch_between('user1', 1, '')
        assert status is False
        assert 'from_hash' in msg

    @patch('plugin.codemig.codemig_common.common_git.get_repo_path')
    def test_code_path_not_exist(self, mock_repo_path):
        mock_path = MagicMock()
        mock_path.exists.return_value = False
        mock_repo_path.return_value = mock_path
        status, msg = generate_patch_between('user1', 1, 'abc123')
        assert status is False
        assert 'not exist' in msg

    @patch('plugin.codemig.codemig_common.common_git.Repo')
    @patch('plugin.codemig.codemig_common.common_git.get_repo_path')
    def test_not_git_repo(self, mock_repo_path, mock_repo_class):
        from git.exc import InvalidGitRepositoryError
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_repo_path.return_value = mock_path
        mock_repo_class.side_effect = InvalidGitRepositoryError("not a repo")

        status, msg = generate_patch_between('user1', 1, 'abc123', 'def456')
        assert status is False
        assert 'not found' in msg

    @patch('plugin.codemig.codemig_common.common_git.Repo')
    @patch('plugin.codemig.codemig_common.common_git.get_repo_path')
    def test_same_hash_returns_empty(self, mock_repo_path, mock_repo_class):
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_repo_path.return_value = mock_path
        mock_repo = MagicMock()
        mock_repo_class.return_value = mock_repo

        status, result = generate_patch_between('user1', 1, 'same1234', 'same1234')
        assert status is True
        assert result == ""
        mock_repo.git.diff.assert_not_called()

    @patch('plugin.codemig.codemig_common.common_git.Repo')
    @patch('plugin.codemig.codemig_common.common_git.get_repo_path')
    def test_to_hash_defaults_to_head(self, mock_repo_path, mock_repo_class):
        """to_hash=None 时自动取 HEAD，且 diff 带 --binary 参数"""
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_repo_path.return_value = mock_path

        from_commit = MagicMock()
        from_commit.message = 'Save type:manual stage:init src:codemig-init reason:first-init'
        to_commit = MagicMock()
        to_commit.message = 'Save type:manual stage:end src:codemig-migrate reason:done'

        mock_repo = MagicMock()
        mock_repo.head.commit.hexsha = 'bbb22222'
        mock_repo.git.diff.return_value = "--- a/file.c\n+++ b/file.c\n@@ -1 +1 @@\n-old\n+new\n"
        mock_repo.commit.side_effect = lambda h: from_commit if h == 'aaa11111' else to_commit
        mock_repo_class.return_value = mock_repo

        status, result = generate_patch_between('user1', 1, 'aaa11111')
        assert status is True
        assert 'aaa11111' in result and 'bbb22222' in result
        # F4 核心：diff 必须带 --binary，否则二进制改动无法还原
        mock_repo.git.diff.assert_called_once_with('aaa11111', 'bbb22222', '--unified=3', '--binary')
        assert result.endswith("\n")

    @patch('plugin.codemig.codemig_common.common_git.Repo')
    @patch('plugin.codemig.codemig_common.common_git.get_repo_path')
    def test_explicit_to_hash(self, mock_repo_path, mock_repo_class):
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_repo_path.return_value = mock_path

        from_commit = MagicMock()
        from_commit.message = 'msg-from'
        to_commit = MagicMock()
        to_commit.message = 'msg-to'

        mock_repo = MagicMock()
        mock_repo.git.diff.return_value = "diff content\n"
        mock_repo.commit.side_effect = lambda h: from_commit if h == 'aaa11111' else to_commit
        mock_repo_class.return_value = mock_repo

        status, result = generate_patch_between('user1', 1, 'aaa11111', 'ccc33333')
        assert status is True
        mock_repo.git.diff.assert_called_once_with('aaa11111', 'ccc33333', '--unified=3', '--binary')
        assert result.startswith("# Incremental patch")

    @patch('plugin.codemig.codemig_common.common_git.Repo')
    @patch('plugin.codemig.codemig_common.common_git.get_repo_path')
    def test_empty_diff_returns_empty_string(self, mock_repo_path, mock_repo_class):
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_repo_path.return_value = mock_path
        mock_repo = MagicMock()
        mock_repo.head.commit.hexsha = 'bbb22222'
        mock_repo.git.diff.return_value = ""
        mock_repo_class.return_value = mock_repo

        status, result = generate_patch_between('user1', 1, 'aaa11111')
        assert status is True
        assert result == ""

    @patch('plugin.codemig.codemig_common.common_git.Repo')
    @patch('plugin.codemig.codemig_common.common_git.get_repo_path')
    def test_git_command_error(self, mock_repo_path, mock_repo_class):
        from git.exc import GitCommandError
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_repo_path.return_value = mock_path
        mock_repo = MagicMock()
        mock_repo.head.commit.hexsha = 'bbb22222'
        mock_repo.git.diff.side_effect = GitCommandError("diff error")
        mock_repo_class.return_value = mock_repo

        status, msg = generate_patch_between('user1', 1, 'aaa11111')
        assert status is False
        assert 'Git command error' in msg


# ---------------------------------------------------------------------------
# generate_patch_from_initial_commit - --binary 参数断言（F4）
# ---------------------------------------------------------------------------
class TestGeneratePatchBinaryFlag:
    @patch('plugin.codemig.codemig_common.common_git.Repo')
    @patch('plugin.codemig.codemig_common.common_git.get_repo_path')
    def test_full_patch_diff_includes_binary_flag(self, mock_repo_path, mock_repo_class):
        """全量导出 diff 必须带 --binary，否则二进制改动只输出占位行无法还原"""
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_repo_path.return_value = mock_path

        initial = MagicMock()
        initial.hexsha = 'aaa11111'
        initial.message = 'Save type:manual stage:init src:codemig-init reason:first-init'
        current = MagicMock()
        current.hexsha = 'bbb22222'
        current.message = 'Save type:manual stage:end src:codemig-migrate reason:done'

        mock_repo = MagicMock()
        mock_repo.iter_commits.return_value = iter([current, initial])
        mock_repo.head.commit = current
        mock_repo.git.diff.return_value = "--- a/file.c\n+++ b/file.c\n@@ -1 +1 @@\n-old\n+new\n"
        mock_repo_class.return_value = mock_repo

        status, patch = generate_patch_from_initial_commit('user1', 1)
        assert status is True
        mock_repo.git.diff.assert_called_once_with(
            'aaa11111', 'bbb22222', '--unified=3', '--binary')


# ---------------------------------------------------------------------------
# list_project_history - max_count 截断（F3 支撑函数）
# ---------------------------------------------------------------------------
class TestListProjectHistoryMaxCount:
    def _build_repo(self, mock_repo_class, mock_repo_path, count):
        """构造带 count 条 reflog 记录的 mock 仓库，时间从早到晚排列"""
        from datetime import datetime
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_repo_path.return_value = mock_path

        commits = {}
        entries = []
        for i in range(count):
            hexsha = f'hash{i:04d}'
            dt = datetime(2025, 1, 1, 0, i, 0)
            commit = MagicMock()
            commit.message = f'Save type:manual stage:end src:codemig-migrate reason:r{i}'
            commit.committed_datetime = dt
            commits[hexsha] = commit
            entry = MagicMock()
            entry.newhexsha = hexsha
            entries.append(entry)

        mock_repo = MagicMock()
        mock_repo.head.commit.hexsha = f'hash{count - 1:04d}'
        mock_repo.head.log.return_value = entries
        mock_repo.commit.side_effect = lambda h: commits[h]
        mock_repo_class.return_value = mock_repo
        return mock_repo

    @patch('plugin.codemig.codemig_common.common_git.Repo')
    @patch('plugin.codemig.codemig_common.common_git.get_repo_path')
    def test_max_count_200_keeps_all(self, mock_repo_path, mock_repo_class):
        """F3 场景：handler 传 max_count=200 时 3 条 reflog 全部保留（默认 50 同理不截断）"""
        from plugin.codemig.codemig_common.common_git import list_project_history
        self._build_repo(mock_repo_class, mock_repo_path, count=3)

        status, history = list_project_history('user1', 1, max_count=200)
        assert status is True
        assert len(history) == 3

    @patch('plugin.codemig.codemig_common.common_git.Repo')
    @patch('plugin.codemig.codemig_common.common_git.get_repo_path')
    def test_truncation_takes_newest(self, mock_repo_path, mock_repo_class):
        """max_count 截断取最新 N 条且倒序排列（最老在前）"""
        from plugin.codemig.codemig_common.common_git import list_project_history
        self._build_repo(mock_repo_class, mock_repo_path, count=3)

        status, history = list_project_history('user1', 1, max_count=2)
        assert status is True
        assert len(history) == 2
        # 最新在前：hash0002 时间最晚
        assert history[0]['hash'] == 'hash0002'
        assert history[1]['hash'] == 'hash0001'
