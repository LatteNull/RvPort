import os
import pytest
import tempfile
import shutil

from unittest import mock
from unittest.mock import patch, MagicMock, mock_open
from pathlib import Path
from framework.log_manager.operation_constant import OpLogModule, OpLogResult
from plugin.codemig.codemig_dir_manager.codemig_dir_processor import (
    process_upload, save_file_to_dir, process_upload_zip, MY_DATA_PATH,
    merge_file, delete_folder_by_dir_id, process_chunk, chunk_upload
)
from plugin.codemig.codemig_dir_manager.models import CodemigDirectoryStorage


@pytest.fixture
def mock_db_connection(mocker):
    """Mock ORM 方法"""
    mocker.patch(
        "plugin.codemig.codemig_dir_manager.models.CodemigDirectoryStorage.insert_directory",
        return_value=123)
    return None, None


@pytest.fixture
def mock_file():
    """Mock Flask 的 FileStorage 对象"""
    file = mock.Mock()
    file.filename = "test.zip"
    file.save = mock.Mock()
    return file


@pytest.fixture
def mock_request():
    request = mock.Mock()
    request.user_id = 1
    # request.user_name="test_user"
    request.remote_addr = "127.0.0.1"
    return request


# **测试上传**
def test_process_upload(mock_db_connection, mock_file, mock_request, mocker):
    mock_mkdir = mocker.patch("pathlib.Path.mkdir")
    mocker.patch('framework.log_manager.operation_log.record_operation_log')

    response = process_upload("test_user", mock_file, mock_request)

    assert response == {"code": 0, "msg": "ok", "dir_id": 123}
    CodemigDirectoryStorage.insert_directory.assert_called_once_with(1)  # 确保调用 ORM 方法
    mock_mkdir.assert_called_once()  # 目录应当被创建
    mock_file.save.assert_called_once()  # 确保文件被保存


# **测试 `insert_directory` 插入成功**
def test_insert_directory_success(mocker):
    mocker.patch(
        "plugin.codemig.codemig_dir_manager.models.CodemigDirectoryStorage.insert_directory",
        return_value=123)

    dir_id = CodemigDirectoryStorage.insert_directory(1)

    assert dir_id == 123  # 预期插入成功返回 ID
    CodemigDirectoryStorage.insert_directory.assert_called_once_with(1)


# **测试 `insert_directory` 失败**
def test_insert_directory_fail(mocker):
    mocker.patch(
        "plugin.codemig.codemig_dir_manager.models.CodemigDirectoryStorage.insert_directory",
        return_value=None)

    dir_id = CodemigDirectoryStorage.insert_directory(1)

    assert dir_id is None  # 失败时返回 None


# **测试 `save_file_to_dir` 成功**
def test_save_file_to_dir_success(mock_file, mocker):
    mock_mkdir = mocker.patch("pathlib.Path.mkdir")  # Mock mkdir 避免创建真实目录

    save_file_to_dir("test_user", 123, mock_file)

    mock_mkdir.assert_called_once()  # 目录应当被创建
    mock_file.save.assert_called_once()  # 文件应当被保存


def test_process_upload_zip_success(mock_db_connection, mocker):
    data = {
        'code': '0',
        'msg': 'File merged successfully',
        'dir_id': 123
    }
    mock_path = mocker.MagicMock(spec=Path)
    mock_path.__truediv__.return_value = mock_path
    mock_path.__str__.return_value = "/mock/path"

    mock_merge = mocker.patch(
        'plugin.codemig.codemig_dir_manager.codemig_dir_processor.merge_file',
        return_value=data
    )
    result = process_upload_zip(
        user_name="test_user",
        file_name="test.zip",
        uploaded_chunks=3,
        chunk_dir="/tmp/chunks",
        user_id=0
    )

    assert result["code"] == '0'
    assert result["dir_id"] == 123
    CodemigDirectoryStorage.insert_directory.assert_called_once_with(0)
    mock_merge.assert_called_once_with(123, "test.zip", 3, "/tmp/chunks",
                                       MY_DATA_PATH / "test_user" / "123")


def test_process_upload_zip_failure(mocker):
    mocker.patch(
        "plugin.codemig.codemig_dir_manager.models.CodemigDirectoryStorage.insert_directory",
        return_value=None)

    result = process_upload_zip(
        user_name="test_user",
        file_name="test.zip",
        uploaded_chunks=3,
        chunk_dir="/tmp/chunks",
        user_id=0
    )

    assert result["code"] == -1
    assert result["msg"] == "Database Error!"
    CodemigDirectoryStorage.insert_directory.assert_called_once_with(0)


class TestMergeFile:
    """测试 merge_file 函数"""

    def test_merge_file_success(self, tmp_path):
        """测试成功合并文件"""
        # 创建临时目录结构
        chunk_dir = tmp_path / "chunks"
        chunk_dir.mkdir()
        folder_path = tmp_path / "output"

        # 创建测试分块文件
        chunk_content_0 = b"chunk0_content"
        chunk_content_1 = b"chunk1_content"
        chunk_content_2 = b"chunk2_content"

        (chunk_dir / "0").write_bytes(chunk_content_0)
        (chunk_dir / "1").write_bytes(chunk_content_1)
        (chunk_dir / "2").write_bytes(chunk_content_2)

        uploaded_chunks = {"0", "1", "2"}
        file_name = "test.zip"
        dir_id = 123

        # 执行合并
        result = merge_file(dir_id, file_name, uploaded_chunks, str(chunk_dir), folder_path)

        # 验证结果
        assert result["code"] == "0"
        assert result["msg"] == "File merged successfully"
        assert result["dir_id"] == dir_id

        # 验证合并后的文件内容
        final_path = folder_path / file_name
        assert final_path.exists()
        expected_content = chunk_content_0 + chunk_content_1 + chunk_content_2
        assert final_path.read_bytes() == expected_content

        # 验证分块目录已被删除
        assert not chunk_dir.exists()

    def test_merge_file_with_subdirectory(self, tmp_path):
        """测试合并文件到子目录"""
        chunk_dir = tmp_path / "chunks"
        chunk_dir.mkdir()
        folder_path = tmp_path / "output"

        # 创建测试分块
        (chunk_dir / "0").write_bytes(b"chunk0")
        (chunk_dir / "1").write_bytes(b"chunk1")

        uploaded_chunks = {"0", "1"}
        file_name = "subdir/test.zip"
        dir_id = 456

        # 执行合并
        result = merge_file(dir_id, file_name, uploaded_chunks, str(chunk_dir), folder_path)

        # 验证结果
        assert result["code"] == "0"
        assert result["dir_id"] == dir_id

        # 验证文件在子目录中
        final_path = folder_path / file_name
        assert final_path.exists()
        assert final_path.read_bytes() == b"chunk0chunk1"

        # 验证分块目录已被删除
        assert not chunk_dir.exists()

    def test_merge_file_unsorted_chunks(self, tmp_path):
        """测试乱序分块合并"""
        chunk_dir = tmp_path / "chunks"
        chunk_dir.mkdir()
        folder_path = tmp_path / "output"

        # 创建乱序分块
        (chunk_dir / "2").write_bytes(b"chunk2")
        (chunk_dir / "0").write_bytes(b"chunk0")
        (chunk_dir / "1").write_bytes(b"chunk1")

        uploaded_chunks = {"2", "0", "1"}
        file_name = "test.zip"
        dir_id = 789

        # 执行合并
        result = merge_file(dir_id, file_name, uploaded_chunks, str(chunk_dir), folder_path)

        # 验证结果（应该按顺序合并）
        assert result["code"] == "0"
        final_path = folder_path / file_name
        assert final_path.read_bytes() == b"chunk0chunk1chunk2"

        # 验证分块目录已被删除
        assert not chunk_dir.exists()

    def test_merge_file_empty_chunks(self, tmp_path):
        """测试空分块合并"""
        chunk_dir = tmp_path / "chunks"
        chunk_dir.mkdir()
        folder_path = tmp_path / "output"

        # 创建空分块
        (chunk_dir / "0").write_bytes(b"")

        uploaded_chunks = {"0"}
        file_name = "empty.zip"
        dir_id = 999

        # 执行合并
        result = merge_file(dir_id, file_name, uploaded_chunks, str(chunk_dir), folder_path)

        # 验证结果
        assert result["code"] == "0"
        final_path = folder_path / file_name
        assert final_path.exists()
        assert final_path.read_bytes() == b""

        # 验证分块目录已被删除
        assert not chunk_dir.exists()


class TestDeleteFolderByDirId:
    """测试 delete_folder_by_dir_id 函数"""

    def test_delete_folder_success(self, tmp_path, mocker):
        """测试成功删除文件夹"""
        # Mock get_codemig_data_path
        mocker.patch(
            'plugin.codemig.codemig_dir_manager.codemig_dir_processor.get_codemig_data_path',
            return_value=str(tmp_path)
        )

        # Mock mark_as_removed 返回成功
        mocker.patch(
            'plugin.codemig.codemig_dir_manager.codemig_dir_processor.CodemigDirectoryStorage.mark_as_removed',
            return_value=True
        )

        # Mock record_operation_log
        mock_log = mocker.patch(
            'plugin.codemig.codemig_dir_manager.codemig_dir_processor.record_operation_log'
        )

        # 创建测试文件夹
        user_name = "test_user"
        dir_id = 123
        folder_path = tmp_path / user_name / str(dir_id)
        folder_path.mkdir(parents=True)
        test_file = folder_path / "test.txt"
        test_file.write_text("test content")

        # 创建 mock request
        mock_request = mock.Mock()
        mock_request.user_id = 1
        mock_request.remote_addr = "127.0.0.1"

        # 执行删除
        result = delete_folder_by_dir_id(user_name, dir_id, mock_request)

        # 验证结果
        assert result["code"] == 0
        assert result["msg"] == "remove success"

        # 验证文件夹已被删除
        assert not folder_path.exists()

        # 验证数据库标记被调用
        CodemigDirectoryStorage.mark_as_removed.assert_called_once_with(dir_id)

        # 验证操作日志被记录（成功）
        assert mock_log.call_count == 1
        call_args = mock_log.call_args
        assert call_args[0][0] == 1  # user_id
        assert call_args[0][1] == "127.0.0.1"  # remote_addr
        assert call_args[0][2] == OpLogModule.CODEMIG
        assert call_args[0][3] == "Delete File"  # operation
        assert call_args[0][4] == OpLogResult.SUCCESS

    def test_delete_folder_database_failure(self, tmp_path, mocker):
        """测试数据库标记失败"""
        # Mock get_codemig_data_path
        mocker.patch(
            'plugin.codemig.codemig_dir_manager.codemig_dir_processor.get_codemig_data_path',
            return_value=str(tmp_path)
        )

        # Mock mark_as_removed 返回失败
        mocker.patch(
            'plugin.codemig.codemig_dir_manager.codemig_dir_processor.CodemigDirectoryStorage.mark_as_removed',
            return_value=False
        )

        # Mock record_operation_log
        mock_log = mocker.patch(
            'plugin.codemig.codemig_dir_manager.codemig_dir_processor.record_operation_log'
        )

        # 创建测试文件夹
        user_name = "test_user"
        dir_id = 456
        folder_path = tmp_path / user_name / str(dir_id)
        folder_path.mkdir(parents=True)
        test_file = folder_path / "test.txt"
        test_file.write_text("test content")

        # 创建 mock request
        mock_request = mock.Mock()
        mock_request.user_id = 2
        mock_request.remote_addr = "192.168.1.1"

        # 执行删除
        result = delete_folder_by_dir_id(user_name, dir_id, mock_request)

        # 验证结果
        assert result["code"] == -1
        assert result["msg"] == "remove failure"

        # 验证文件夹未被删除（因为数据库操作失败）
        assert folder_path.exists()

        # 验证操作日志被记录（失败）
        assert mock_log.call_count == 1
        call_args = mock_log.call_args
        assert call_args[0][4] == OpLogResult.FAILED
        assert "Database Error" in call_args[0][5]  # message

    def test_delete_folder_not_exists(self, tmp_path, mocker):
        """测试删除不存在的文件夹"""
        # Mock get_codemig_data_path
        mocker.patch(
            'plugin.codemig.codemig_dir_manager.codemig_dir_processor.get_codemig_data_path',
            return_value=str(tmp_path)
        )

        # Mock mark_as_removed 返回成功
        mocker.patch(
            'plugin.codemig.codemig_dir_manager.codemig_dir_processor.CodemigDirectoryStorage.mark_as_removed',
            return_value=True
        )

        # Mock record_operation_log
        mock_log = mocker.patch(
            'plugin.codemig.codemig_dir_manager.codemig_dir_processor.record_operation_log'
        )

        # 文件夹不存在
        user_name = "test_user"
        dir_id = 789

        # 创建 mock request
        mock_request = mock.Mock()
        mock_request.user_id = 3
        mock_request.remote_addr = "10.0.0.1"

        # 执行删除
        result = delete_folder_by_dir_id(user_name, dir_id, mock_request)

        # 验证结果（即使文件夹不存在，也应该返回成功）
        assert result["code"] == 0
        assert result["msg"] == "remove success"

        # 验证数据库标记被调用
        CodemigDirectoryStorage.mark_as_removed.assert_called_once_with(dir_id)

        # 验证操作日志被记录
        assert mock_log.call_count == 1
        call_args = mock_log.call_args
        assert call_args[0][4] == OpLogResult.SUCCESS

    def test_delete_folder_with_nested_files(self, tmp_path, mocker):
        """测试删除包含嵌套文件的文件夹"""
        # Mock get_codemig_data_path
        mocker.patch(
            'plugin.codemig.codemig_dir_manager.codemig_dir_processor.get_codemig_data_path',
            return_value=str(tmp_path)
        )

        # Mock mark_as_removed 返回成功
        mocker.patch(
            'plugin.codemig.codemig_dir_manager.codemig_dir_processor.CodemigDirectoryStorage.mark_as_removed',
            return_value=True
        )

        # Mock record_operation_log
        mocker.patch(
            'plugin.codemig.codemig_dir_manager.codemig_dir_processor.record_operation_log'
        )

        # 创建嵌套文件夹结构
        user_name = "test_user"
        dir_id = 999
        folder_path = tmp_path / user_name / str(dir_id)
        folder_path.mkdir(parents=True)

        # 创建嵌套文件和目录
        (folder_path / "file1.txt").write_text("file1")
        (folder_path / "file2.txt").write_text("file2")
        subdir = folder_path / "subdir"
        subdir.mkdir()
        (subdir / "file3.txt").write_text("file3")

        # 创建 mock request
        mock_request = mock.Mock()
        mock_request.user_id = 4
        mock_request.remote_addr = "172.16.0.1"

        # 执行删除
        result = delete_folder_by_dir_id(user_name, dir_id, mock_request)

        # 验证结果
        assert result["code"] == 0
        assert result["msg"] == "remove success"

        # 验证整个文件夹树已被删除
        assert not folder_path.exists()
        assert not subdir.exists()


class TestProcessChunk:
    """测试 process_chunk 函数"""
    
    @patch('plugin.codemig.codemig_dir_manager.codemig_dir_processor.process_upload_single_zip')
    @patch('plugin.codemig.codemig_dir_manager.codemig_dir_processor.record_operation_log')
    def test_process_chunk_single_chunk_success(self, mock_log, mock_single_zip, mock_request):
        """测试单块上传成功"""
        mock_file = MagicMock()
        mock_single_zip.return_value = {
            'code': 0,
            'msg': 'File uploaded successfully',
            'dir_id': 123
        }
        
        result = process_chunk(
            'test_user', mock_file, '0', '1', 'file.zip', '', mock_request
        )
        
        assert result['code'] == 0
        assert result['msg'] == 'File uploaded successfully'
        mock_single_zip.assert_called_once_with('test_user', 'file.zip', mock_file, 1)
        mock_log.assert_called_once()
    
    @patch('plugin.codemig.codemig_dir_manager.codemig_dir_processor.chunk_upload')
    @patch('plugin.codemig.codemig_dir_manager.codemig_dir_processor.record_operation_log')
    def test_process_chunk_multi_chunk_first(self, mock_log, mock_chunk_upload, mock_request):
        """测试多块上传第一块"""
        mock_file = MagicMock()
        mock_chunk_upload.return_value = {
            'code': 0,
            'msg': 'Chunk 0 uploaded successfully',
            'uploaded_chunks_length': 1,
            'total': 5,
            'dir_id': -1
        }
        
        result = process_chunk(
            'test_user', mock_file, '0', '5', 'large.zip', 'path/to', mock_request
        )
        
        assert result['code'] == 0
        assert result['uploaded_chunks_length'] == 1
        mock_chunk_upload.assert_called_once()
        mock_log.assert_not_called()  # 中间块不记录日志
    
    @patch('plugin.codemig.codemig_dir_manager.codemig_dir_processor.chunk_upload')
    @patch('plugin.codemig.codemig_dir_manager.codemig_dir_processor.record_operation_log')
    def test_process_chunk_multi_chunk_final(self, mock_log, mock_chunk_upload, mock_request):
        """测试多块上传最后一块（触发合并）"""
        mock_file = MagicMock()
        mock_chunk_upload.return_value = {
            'code': 0,
            'msg': 'File merged successfully',
            'dir_id': 456
        }
        
        result = process_chunk(
            'test_user', mock_file, '4', '5', 'large.zip', 'path/to', mock_request
        )
        
        assert result['code'] == 0
        assert result['msg'] == 'File merged successfully'
        mock_log.assert_called_once()
        call_args = mock_log.call_args
        assert call_args[0][3] == 'Upload Zip'
        assert call_args[0][4] == OpLogResult.SUCCESS
    
    @patch('plugin.codemig.codemig_dir_manager.codemig_dir_processor.chunk_upload')
    @patch('plugin.codemig.codemig_dir_manager.codemig_dir_processor.record_operation_log')
    def test_process_chunk_failure(self, mock_log, mock_chunk_upload, mock_request):
        """测试分块上传失败"""
        mock_file = MagicMock()
        mock_chunk_upload.return_value = {
            'code': -1,
            'msg': 'Directory creation failed'
        }
        
        result = process_chunk(
            'test_user', mock_file, '0', '3', 'file.zip', '', mock_request
        )
        
        assert result['code'] == -1
        mock_log.assert_called_once()
        call_args = mock_log.call_args
        assert call_args[0][4] == OpLogResult.FAILED


class TestChunkUpload:
    """测试 chunk_upload 函数"""
    
    @patch('plugin.codemig.codemig_dir_manager.codemig_dir_processor.os.makedirs')
    @patch('plugin.codemig.codemig_dir_manager.codemig_dir_processor.os.path.exists')
    def test_chunk_upload_mkdir_failure(self, mock_exists, mock_makedirs):
        """测试创建目录失败"""
        mock_makedirs.side_effect = OSError("Cannot create directory")
        mock_exists.return_value = False
        
        mock_file = MagicMock()
        
        result = chunk_upload(
            'user', mock_file, 'file.zip', '0', '3', 'path', 'md5hash', 1
        )
        
        assert result['code'] == -1
        assert 'Directory creation failed' in result['msg']
    
    @patch('plugin.codemig.codemig_dir_manager.codemig_dir_processor.os.listdir')
    @patch('plugin.codemig.codemig_dir_manager.codemig_dir_processor.os.path.exists')
    @patch('plugin.codemig.codemig_dir_manager.codemig_dir_processor.os.makedirs')
    def test_chunk_upload_not_all_chunks(self, mock_makedirs, mock_exists, mock_listdir):
        """测试不是所有分块都已上传"""
        mock_makedirs.return_value = None
        mock_exists.return_value = True
        mock_listdir.return_value = ['0']  # 只有第0块，总共需要3块
        
        mock_file = MagicMock()
        
        with patch('builtins.open', mock_open()):
            result = chunk_upload(
                'user', mock_file, 'file.zip', '0', '3', 'path', 'md5hash', 1
            )
            
            assert result['code'] == 0
            assert 'Chunk 0 uploaded successfully' in result['msg']
            assert result['uploaded_chunks_length'] == 1
            assert result['total'] == 3
            assert result['dir_id'] == -1
    
    @patch('plugin.codemig.codemig_dir_manager.codemig_dir_processor.process_upload_zip')
    @patch('plugin.codemig.codemig_dir_manager.codemig_dir_processor.os.listdir')
    @patch('plugin.codemig.codemig_dir_manager.codemig_dir_processor.os.path.exists')
    @patch('plugin.codemig.codemig_dir_manager.codemig_dir_processor.os.makedirs')
    @patch('builtins.open', new_callable=mock_open)
    def test_chunk_upload_all_chunks_merge_success(self, mock_file, mock_makedirs, mock_exists, 
                                                    mock_listdir, mock_merge):
        """测试所有分块上传完成并成功合并"""
        mock_makedirs.return_value = None
        mock_exists.return_value = True
        mock_listdir.return_value = ['0', '1', '2']  # 所有分块都已上传
        
        mock_merge.return_value = {
            'code': '0',
            'msg': 'File merged successfully',
            'dir_id': 789
        }
        
        mock_flock = MagicMock()
        with patch('fcntl.flock', mock_flock):
            result = chunk_upload(
                'user', MagicMock(), 'file.zip', '2', '3', 'path', 'md5hash', 1
            )
            
            assert result['code'] == '0'
            assert result['msg'] == 'File merged successfully'
            mock_merge.assert_called_once()
            mock_flock.assert_called_once()
    
    @patch('plugin.codemig.codemig_dir_manager.codemig_dir_processor.os.listdir')
    @patch('plugin.codemig.codemig_dir_manager.codemig_dir_processor.os.path.exists')
    @patch('plugin.codemig.codemig_dir_manager.codemig_dir_processor.os.makedirs')
    @patch('builtins.open', new_callable=mock_open)
    def test_chunk_upload_merge_in_progress(self, mock_file, mock_makedirs, mock_exists, mock_listdir):
        """测试合并正在进行中（锁被占用）"""
        mock_makedirs.return_value = None
        mock_exists.return_value = True
        mock_listdir.return_value = ['0', '1', '2']
        
        def mock_flock_side_effect(fd, flags):
            raise BlockingIOError("Lock held by another process")
        
        with patch('fcntl.flock', side_effect=mock_flock_side_effect):
            result = chunk_upload(
                'user', MagicMock(), 'file.zip', '2', '3', 'path', 'md5hash', 1
            )
            
            assert result['code'] == -1
            assert 'Merge in progress' in result['msg']
    
    @patch('plugin.codemig.codemig_dir_manager.codemig_dir_processor.os.listdir')
    @patch('plugin.codemig.codemig_dir_manager.codemig_dir_processor.os.path.exists')
    @patch('plugin.codemig.codemig_dir_manager.codemig_dir_processor.os.makedirs')
    @patch('builtins.open', new_callable=mock_open)
    def test_chunk_upload_save_chunk_failure(self, mock_file, mock_makedirs, mock_exists, mock_listdir):
        """测试保存分块失败"""
        mock_makedirs.return_value = None
        mock_exists.return_value = True
        mock_listdir.return_value = ['0']
        
        mock_file_instance = MagicMock()
        mock_file_instance.save.side_effect = IOError("Disk full")
        
        with pytest.raises(IOError, match="Disk full"):
            chunk_upload(
                'user', mock_file_instance, 'file.zip', '1', '3', 'path', 'md5hash', 1
            )
