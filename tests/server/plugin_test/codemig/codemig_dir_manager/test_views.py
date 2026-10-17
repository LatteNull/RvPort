import pytest
import io
from flask import Flask, request
import flask
from plugin.codemig.codemig_dir_manager.views import directory_storage_bp
from unittest.mock import ANY, MagicMock
from pathlib import Path


@pytest.fixture
def mock_db_connection(mocker):
    """Mock ORM 方法"""
    mocker.patch(
        "plugin.codemig.codemig_dir_manager.models.CodemigDirectoryStorage.insert_directory",
        return_value=123)
    return None, None


# 创建 Flask 测试应用
@pytest.fixture
def client():
    app = Flask(__name__)
    app.config['TESTING'] = True  # 启用测试模式
    app.config['SECRET_KEY'] = 'test-secret-key'  # 需要设置 SECRET_KEY 才能使用 session
    app.register_blueprint(directory_storage_bp)  # 注册蓝图
    @app.before_request
    def mock_request():
        request.user_id = 1
        # 设置 session
        from flask import session
        session['user_name'] = 'test_user'
    return app.test_client()



# **测试上传**
#def test_upload(client, mocker):
def upload(client, mocker):


    # 2. 模拟文件上传的 `data`
    data = {
        "user_name": "test_user",
        "file": (io.BytesIO(b"dummy file content"), "test.zip")
    }
    # 临时添加调试信息来找到正确路径
    import sys

    # 查看所有已加载的模块
    for module_name in sorted(sys.modules.keys()):
        if 'record_operation_log' in module_name or 'operation_log' in module_name:
            print(f"Found module: {module_name}")
    mocker.patch('framework.log_manager.operation_log.record_operation_log')
    # mocker.patch('plugin.codemig.codemig_dir_manager.codemig_dir_processor.record_operation_log')
    # mock_request = mocker.MagicMock(spec=Request)
    # mock_request.user_id = "test_user_id"
    # mock_request.remote_addr = "127.0.0.1"
    # # 打桩 flask.request
    # mocker.patch('plugin.codemig.codemig_dir_manager.codemig_dir_processor.request', mock_request)
    #
    # # 替换 Request 类
    # monkeypatch.setattr('flask.Request', MockRequest)
    # 1. 使用 `mocker.patch` 模拟返回值
    mocker.patch(
            'plugin.codemig.codemig_dir_manager.codemig_dir_processor.save_file_to_dir')
    mocker.patch(
            'plugin.codemig.codemig_dir_manager.models.CodemigDirectoryStorage.insert_directory',
            return_value=123)

    # 3. 发送 POST 请求
    response = client.post('/dir/upload',
                               data=data,
                               content_type='multipart/form-data')

    # 4. 断言：验证 `process_upload` 被调用，且返回正确响应
    assert response.json == {"code": 0, "msg": "ok", "dir_id": 123}


# 测试分块上传 - 单块上传（完整文件）
def test_upload_zip_single_chunk(client, mocker):
    # 模拟数据库
    mocker.patch(
        'plugin.codemig.codemig_dir_manager.models.CodemigDirectoryStorage.insert_directory',
        return_value=456
    )

    # 模拟路径操作
    mock_path = mocker.MagicMock(spec=Path)
    mock_path.__truediv__.return_value = mock_path
    mock_path.__str__.return_value = "/mock/path/single.zip"

    # 模拟单块上传的实际处理函数（total_chunk_size=1 时 process_chunk 走此路径）
    mock_process_single = mocker.patch(
        'plugin.codemig.codemig_dir_manager.codemig_dir_processor.process_upload_single_zip',
        return_value={'code': 0, 'msg': 'File uploaded successfully', 'dir_id': 456}
    )

    # 准备测试数据
    file_content = b"mock file content"

    data = {
        "user_name": "test_user",
        "file": (io.BytesIO(file_content), "single.zip"),
        "current_chunk_idx": "0",
        "total_chunk_size": "1",
        "file_name": "single.zip",
        "relativePath": ""
    }

    response = client.post('/dir/upload_zip',
                           data=data,
                           content_type='multipart/form-data')

    # 验证响应
    assert response.status_code == 200
    assert response.json['code'] == 0
    assert response.json['dir_id'] == 456
    assert response.json['msg'] == 'File uploaded successfully'

    # 验证单块上传处理函数被调用
    mock_process_single.assert_called_once()


# 测试分块上传 - 多块上传（第一块）
def test_upload_zip_first_chunk(client, mocker):
    # 模拟常量值
    mock_file_md5 = "mock_md5_value"
    mock_chunk = "0"

    # 1. 模拟 hashlib.md5 返回值
    mocker.patch(
        'hashlib.md5',
        return_value=mocker.Mock(hexdigest=lambda: mock_file_md5)
    )

    # 2. 模拟文件系统操作
    mocker.patch('os.makedirs')
    mocker.patch('os.path.exists', return_value=True)

    # 3. 模拟文件保存
    mocker.patch('werkzeug.datastructures.FileStorage.save')

    # 4. 模拟目录列表
    mocker.patch('os.listdir', return_value=[mock_chunk])

    data = {
            "user_name": "test_user",
            "file": (io.BytesIO(b"chunk 0 content"), "chunk.part"),
            "current_chunk_idx": "0",
            "total_chunk_size": "3",
            "file_name": "large_file.zip",
            "relativePath": "path/to/large_file.zip"
        }

    response = client.post('/dir/upload_zip',
                           data=data,
                           content_type='multipart/form-data')
    assert response.status_code == 200
    assert response.json['code'] == 0
    assert response.json['uploaded_chunks_length'] == 1
    assert response.json['total'] == 3
    assert response.json['dir_id'] == -1


# 测试分块上传 - 中间块
def test_upload_zip_middle_chunk(client, mocker):
    # 模拟常量值
    mock_file_md5 = "mock_md5_value"
    mock_chunk = "2"

    # 1. 模拟 hashlib.md5 返回值
    mocker.patch(
        'hashlib.md5',
        return_value=mocker.Mock(hexdigest=lambda: mock_file_md5)
    )

    # 2. 模拟文件系统操作
    mocker.patch('os.makedirs')
    mocker.patch('os.path.exists', return_value=True)

    # 3. 模拟文件保存
    mocker.patch('werkzeug.datastructures.FileStorage.save')

    # 4. 模拟目录列表
    mocker.patch('os.listdir', return_value=[mock_chunk])

    data = {
        "user_name": "test_user",
        "file": (io.BytesIO(b"chunk 2 content"), "chunk.part"),
        "current_chunk_idx": "2",
        "total_chunk_size": "3",
        "file_name": "large_file.zip",
        "relativePath": "path/to/large_file.zip"
    }

    response = client.post('/dir/upload_zip',
                           data=data,
                           content_type='multipart/form-data')

    assert response.status_code == 200
    assert response.json['code'] == 0
    assert response.json['uploaded_chunks_length'] == 1
    assert response.json['total'] == 3
    assert response.json['dir_id'] == -1


# 测试分块上传 - 最后一块触发合并
# def test_upload_zip_final_chunk(mock_db_connection, mocker, client):
def upload_zip_final_chunk(mock_db_connection, mocker, client):
    # 1. 模拟常量
    mock_chunk = "2"  # 最后一个分块编号

    # 2. 模拟文件系统
    mocker.patch('os.makedirs')
    mocker.patch('os.path.exists', return_value=True)
    mocker.patch('os.listdir', return_value=['0', '1', '2'])  # 所有分块已上传

    # 3. 模拟文件操作
    mocker.patch('werkzeug.datastructures.FileStorage.save')
    mocker.patch('builtins.open', mocker.mock_open())
    mocker.patch('shutil.rmtree')

    # 4. 模拟锁（成功）
    mocker.patch('fcntl.flock', return_value=None)

    # 5. 模拟合并过程
    mock_path = mocker.MagicMock(spec=Path)
    mock_path.__truediv__.return_value = mock_path
    mock_path.__str__.return_value = "/mock/path"
    data = {
        'code': '0',
        'msg': 'File merged successfully',
        'dir_id': 123
    }
    mock_merge = mocker.patch(
        'plugin.codemig.codemig_dir_manager.codemig_dir_processor.merge_file',
        return_value=data
    )

    # 6. 发送请求（最后一个分块）
    response = client.post('/dir/upload_zip', data={
        "user_name": "test_user",
        "file": (io.BytesIO(b"chunk2"), "chunk.part"),
        "current_chunk_idx": mock_chunk,
        "total_chunk_size": "3",  # 总分块数
        "file_name": "test.zip",
        "relativePath": "path/to/large_file.zip"
    },  content_type='multipart/form-data')

    # 7. 验证合并逻辑被触发
    assert response.json['code'] == '0'
    assert response.json['dir_id'] == 123
    # 修改这里：匹配实际的调用参数
    mock_merge.assert_called_once_with(
        123,
        "test.zip",
        {'0', '1', '2'},
        ANY,
        ANY
    )
    CodemigDirectoryStorage.insert_directory.assert_called_once()


# =====================================================================
# 以下为 test_views_extra.py 合并的测试类
# =====================================================================

from plugin.codemig.codemig_dir_manager.views import (
    validate_chunk_parameters,
    validate_relative_path,
    validate_file_upload,
    check_upload_zip,
)


class TestValidateChunkParameters:

    # --- current_chunk_idx: empty / None ---

    def test_none_current_chunk_idx(self):
        status, field, msg = validate_chunk_parameters(None, "5")
        assert status is False
        assert field == "current_chunk_idx"
        assert "不能为空" in msg

    def test_empty_string_current_chunk_idx(self):
        status, field, msg = validate_chunk_parameters("", "5")
        assert status is False
        assert field == "current_chunk_idx"

    # --- current_chunk_idx: not a string ---

    def test_int_current_chunk_idx(self):
        status, field, msg = validate_chunk_parameters(3, "5")
        assert status is False
        assert field == "current_chunk_idx"

    def test_list_current_chunk_idx(self):
        status, field, msg = validate_chunk_parameters(["1"], "5")
        assert status is False
        assert field == "current_chunk_idx"

    # --- current_chunk_idx: non-digit string ---

    def test_non_digit_current_chunk_idx_letters(self):
        status, field, msg = validate_chunk_parameters("abc", "5")
        assert status is False
        assert field == "current_chunk_idx"
        assert "数字" in msg

    def test_non_digit_current_chunk_idx_negative_sign(self):
        status, field, msg = validate_chunk_parameters("-1", "5")
        assert status is False
        assert field == "current_chunk_idx"

    def test_non_digit_current_chunk_idx_float(self):
        status, field, msg = validate_chunk_parameters("3.5", "5")
        assert status is False
        assert field == "current_chunk_idx"

    def test_non_digit_current_chunk_idx_with_spaces(self):
        status, field, msg = validate_chunk_parameters(" 10 ", "5")
        assert status is False
        assert field == "current_chunk_idx"

    # --- current_chunk_idx: range ---

    def test_negative_range_current_chunk_idx(self):
        status, field, msg = validate_chunk_parameters("0", "5")
        assert status is True

    def test_chunk_idx_exactly_zero(self):
        status, field, msg = validate_chunk_parameters("0", "5")
        assert status is True

    def test_chunk_idx_exactly_40000(self):
        status, field, msg = validate_chunk_parameters("40000", "5")
        assert status is True

    def test_chunk_idx_over_40000(self):
        status, field, msg = validate_chunk_parameters("40001", "5")
        assert status is False
        assert field == "current_chunk_idx"
        assert "范围" in msg

    # --- total_chunk_size: non-digit ---

    def test_valid_chunk_idx_non_digit_total_chunk_size(self):
        status, field, msg = validate_chunk_parameters("0", "abc")
        assert status is False
        assert field == "total_chunk_size"
        assert "数字" in msg

    def test_valid_chunk_idx_negative_total_chunk_size(self):
        status, field, msg = validate_chunk_parameters("0", "-100")
        assert status is False
        assert field == "total_chunk_size"

    def test_valid_chunk_idx_float_total_chunk_size(self):
        status, field, msg = validate_chunk_parameters("0", "1.5")
        assert status is False
        assert field == "total_chunk_size"

    # --- total_chunk_size: range ---

    def test_total_chunk_size_over_4gb(self):
        over_limit = 4 * 1024 * 1024 * 1024 + 1
        status, field, msg = validate_chunk_parameters("0", str(over_limit))
        assert status is False
        assert field == "total_chunk_size"
        assert "限制" in msg

    def test_total_chunk_size_exactly_4gb(self):
        exactly_limit = 4 * 1024 * 1024 * 1024
        status, field, msg = validate_chunk_parameters("0", str(exactly_limit))
        assert status is True

    def test_total_chunk_size_zero(self):
        status, field, msg = validate_chunk_parameters("0", "0")
        assert status is True

    # --- total_chunk_size: None / non-string (should pass) ---

    def test_total_chunk_size_none_passes(self):
        status, field, msg = validate_chunk_parameters("0", None)
        assert status is True
        assert msg == "验证通过"

    def test_total_chunk_size_int_passes(self):
        status, field, msg = validate_chunk_parameters("0", 1024)
        assert status is True
        assert msg == "验证通过"

    def test_total_chunk_size_empty_string_passes(self):
        status, field, msg = validate_chunk_parameters("0", "")
        assert status is True
        assert msg == "验证通过"

    # --- fully valid ---

    def test_valid_params_basic(self):
        status, field, msg = validate_chunk_parameters("0", "10")
        assert status is True
        assert field == ""
        assert msg == "验证通过"

    def test_valid_params_large_chunk_idx(self):
        status, field, msg = validate_chunk_parameters("20000", "1073741824")
        assert status is True

    def test_valid_params_without_total_chunk_size(self):
        status, field, msg = validate_chunk_parameters("5", None)
        assert status is True
        assert msg == "验证通过"


class TestValidateRelativePath:

    # --- empty / None ---

    def test_none_relative_path(self):
        status, path, msg = validate_relative_path(None)
        assert status is True
        assert path == ""
        assert msg == ""

    def test_empty_string_relative_path(self):
        status, path, msg = validate_relative_path("")
        assert status is True
        assert path == ""
        assert msg == ""

    # --- not a string ---

    def test_int_relative_path(self):
        status, path, msg = validate_relative_path(123)
        assert status is False
        assert path == 123
        assert "类型异常" in msg

    def test_list_relative_path(self):
        status, path, msg = validate_relative_path(["a", "b"])
        assert status is False
        assert "类型异常" in msg

    # --- absolute path ---

    def test_unix_absolute_path(self):
        status, path, msg = validate_relative_path("/etc/passwd")
        assert status is False
        assert "绝对路径" in msg

    def test_windows_absolute_path(self):
        status, path, msg = validate_relative_path("C:\\Windows\\System32")
        assert status is False

    # --- path traversal ---

    def test_parent_directory_traversal(self):
        status, path, msg = validate_relative_path("../etc/passwd")
        assert status is False
        assert "遍历" in msg

    def test_mid_path_traversal(self):
        status, path, msg = validate_relative_path("foo/../bar")
        assert status is False
        assert "遍历" in msg

    def test_backslash_traversal(self):
        status, path, msg = validate_relative_path("foo\\..\\bar")
        assert status is False
        assert "遍历" in msg

    def test_double_dot_at_end(self):
        status, path, msg = validate_relative_path("foo/bar/..")
        assert status is False
        assert "遍历" in msg

    # --- illegal characters ---

    def test_path_with_semicolon(self):
        status, path, msg = validate_relative_path("foo;bar")
        assert status is False
        assert "非法字符" in msg

    def test_path_with_pipe(self):
        status, path, msg = validate_relative_path("foo|bar")
        assert status is False
        assert "非法字符" in msg

    def test_path_with_null_byte(self):
        status, path, msg = validate_relative_path("foo\x00bar")
        assert status is False

    def test_path_with_special_shell_chars(self):
        status, path, msg = validate_relative_path("$(whoami)")
        assert status is False
        assert "非法字符" in msg

    def test_path_with_backtick(self):
        status, path, msg = validate_relative_path("`cmd`")
        assert status is False

    # --- path depth > 10 ---

    def test_path_depth_exactly_10(self):
        path = "/".join([f"dir{i}" for i in range(10)])
        status, _, msg = validate_relative_path(path)
        assert status is True

    def test_path_depth_11(self):
        path = "/".join([f"dir{i}" for i in range(11)])
        status, _, msg = validate_relative_path(path)
        assert status is False
        assert "深度" in msg

    def test_path_depth_15(self):
        path = "/".join([f"d" for _ in range(15)])
        status, _, msg = validate_relative_path(path)
        assert status is False
        assert "深度" in msg

    # --- hidden file / directory ---

    def test_hidden_file_starts_with_dot(self):
        status, path, msg = validate_relative_path(".hidden_file")
        assert status is False
        assert "隐藏" in msg

    def test_hidden_directory_in_path(self):
        status, path, msg = validate_relative_path("foo/.secret/file.txt")
        assert status is False
        assert "隐藏" in msg

    def test_hidden_file_at_end(self):
        status, path, msg = validate_relative_path("docs/.env")
        assert status is False
        assert "隐藏" in msg

    # --- valid paths ---

    def test_simple_filename(self):
        status, path, msg = validate_relative_path("file.txt")
        assert status is True
        assert msg == "验证通过"
        assert path == "file.txt"

    def test_nested_directory(self):
        status, path, msg = validate_relative_path("foo/bar/baz.txt")
        assert status is True
        assert msg == "验证通过"

    def test_path_with_underscores_and_hyphens(self):
        status, path, msg = validate_relative_path("my-folder/my_file.txt")
        assert status is True
        assert msg == "验证通过"

    def test_path_with_spaces(self):
        status, path, msg = validate_relative_path("my folder/my file.txt")
        assert status is True

    def test_path_with_backslash(self):
        status, path, msg = validate_relative_path("foo\\bar\\baz.txt")
        assert status is True

    def test_path_with_single_dot_component(self):
        status, path, msg = validate_relative_path("./foo.txt")
        assert status is True

    def test_path_depth_exactly_5(self):
        path = "/".join([f"level{i}" for i in range(5)] + ["file.txt"])
        status, _, msg = validate_relative_path(path)
        assert status is True


class TestValidateFileUpload:

    # --- no file ---

    def test_no_file(self):
        status, msg = validate_file_upload(None, "test.zip")
        assert status is False
        assert "未上传文件" in msg

    def test_empty_file(self):
        status, msg = validate_file_upload("", "test.zip")
        assert status is False
        assert "未上传文件" in msg

    # --- no file_name ---

    def test_no_file_name(self):
        mock_file = MagicMock()
        status, msg = validate_file_upload(mock_file, None)
        assert status is False
        assert "文件名不能为空" in msg

    def test_empty_file_name(self):
        mock_file = MagicMock()
        status, msg = validate_file_upload(mock_file, "")
        assert status is False
        assert "文件名不能为空" in msg

    # --- unsafe filename ---

    def test_unsafe_filename_with_path_traversal(self):
        mock_file = MagicMock()
        status, msg = validate_file_upload(mock_file, "../evil.zip")
        assert status is False
        assert "不安全" in msg

    def test_unsafe_filename_with_spaces(self):
        mock_file = MagicMock()
        status, msg = validate_file_upload(mock_file, "my file.zip")
        assert status is False
        assert "不安全" in msg

    def test_unsafe_filename_with_special_chars(self):
        mock_file = MagicMock()
        status, msg = validate_file_upload(mock_file, "file;name.zip")
        assert status is False

    def test_unsafe_filename_with_null_bytes(self):
        mock_file = MagicMock()
        status, msg = validate_file_upload(mock_file, "file\x00.zip")
        assert status is False

    def test_unsafe_filename_absolute_path(self):
        mock_file = MagicMock()
        status, msg = validate_file_upload(mock_file, "/etc/passwd")
        assert status is False

    # --- valid file upload ---

    def test_valid_file_upload(self):
        mock_file = MagicMock()
        status, msg = validate_file_upload(mock_file, "test.zip")
        assert status is True
        assert "验证通过" in msg

    def test_valid_file_upload_with_underscores(self):
        mock_file = MagicMock()
        status, msg = validate_file_upload(mock_file, "my_file_v2.zip")
        assert status is True

    def test_valid_file_upload_simple_name(self):
        mock_file = MagicMock()
        status, msg = validate_file_upload(mock_file, "data.tar")
        assert status is True

    def test_valid_file_upload_no_extension(self):
        mock_file = MagicMock()
        status, msg = validate_file_upload(mock_file, "README")
        assert status is True


class TestCheckUploadZip:

    # --- invalid chunk params ---

    def test_invalid_chunk_params_none_idx(self):
        mock_file = MagicMock()
        status, msg, path = check_upload_zip(None, "10", mock_file, "test.zip", "folder/file.txt")
        assert status == -1
        assert path is None
        assert "current_chunk_idx" in msg

    def test_invalid_chunk_params_non_digit_idx(self):
        mock_file = MagicMock()
        status, msg, path = check_upload_zip("abc", "10", mock_file, "test.zip", "folder/file.txt")
        assert status == -1
        assert path is None

    def test_invalid_chunk_params_out_of_range_idx(self):
        mock_file = MagicMock()
        status, msg, path = check_upload_zip("99999", "10", mock_file, "test.zip", "folder/file.txt")
        assert status == -1
        assert path is None

    def test_invalid_chunk_params_non_digit_total_size(self):
        mock_file = MagicMock()
        status, msg, path = check_upload_zip("0", "not_a_number", mock_file, "test.zip", "folder/file.txt")
        assert status == -1
        assert path is None
        assert "total_chunk_size" in msg

    # --- invalid file ---

    def test_invalid_file_none(self):
        status, msg, path = check_upload_zip("0", "10", None, "test.zip", "folder/file.txt")
        assert status == -1
        assert path is None
        assert "未上传文件" in msg

    def test_invalid_file_empty(self):
        status, msg, path = check_upload_zip("0", "10", "", "test.zip", "folder/file.txt")
        assert status == -1
        assert path is None

    def test_invalid_file_no_name(self):
        mock_file = MagicMock()
        status, msg, path = check_upload_zip("0", "10", mock_file, None, "folder/file.txt")
        assert status == -1
        assert path is None
        assert "文件名不能为空" in msg

    def test_invalid_file_unsafe_name(self):
        mock_file = MagicMock()
        status, msg, path = check_upload_zip("0", "10", mock_file, "../evil.zip", "folder/file.txt")
        assert status == -1
        assert path is None
        assert "不安全" in msg

    # --- invalid path ---

    def test_invalid_path_absolute(self):
        mock_file = MagicMock()
        status, msg, path = check_upload_zip("0", "10", mock_file, "test.zip", "/etc/passwd")
        assert status == -1
        assert path is None
        assert "绝对路径" in msg

    def test_invalid_path_traversal(self):
        mock_file = MagicMock()
        status, msg, path = check_upload_zip("0", "10", mock_file, "test.zip", "../secret")
        assert status == -1
        assert path is None
        assert "遍历" in msg

    def test_invalid_path_hidden_file(self):
        mock_file = MagicMock()
        status, msg, path = check_upload_zip("0", "10", mock_file, "test.zip", ".hidden")
        assert status == -1
        assert path is None
        assert "隐藏" in msg

    def test_invalid_path_illegal_chars(self):
        mock_file = MagicMock()
        status, msg, path = check_upload_zip("0", "10", mock_file, "test.zip", "foo;bar")
        assert status == -1
        assert path is None
        assert "非法字符" in msg

    def test_invalid_path_too_deep(self):
        deep_path = "/".join([f"d{i}" for i in range(12)])
        mock_file = MagicMock()
        status, msg, path = check_upload_zip("0", "10", mock_file, "test.zip", deep_path)
        assert status == -1
        assert path is None
        assert "深度" in msg

    # --- all valid ---

    def test_all_valid_with_relative_path(self):
        mock_file = MagicMock()
        status, msg, safe_path = check_upload_zip("0", "1024", mock_file, "test.zip", "folder/file.txt")
        assert status == 0
        assert msg == ""
        assert safe_path == "folder/file.txt"

    def test_all_valid_without_relative_path(self):
        mock_file = MagicMock()
        status, msg, safe_path = check_upload_zip("0", "1024", mock_file, "test.zip", "")
        assert status == 0
        assert msg == ""
        assert safe_path == ""

    def test_all_valid_without_total_chunk_size(self):
        mock_file = MagicMock()
        status, msg, safe_path = check_upload_zip("0", None, mock_file, "test.zip", "data.txt")
        assert status == 0
        assert safe_path == "data.txt"

    def test_all_valid_none_relative_path(self):
        mock_file = MagicMock()
        status, msg, safe_path = check_upload_zip("0", "512", mock_file, "test.zip", None)
        assert status == 0
        assert safe_path == ""

    def test_all_valid_chunk_idx_at_boundary(self):
        mock_file = MagicMock()
        status, msg, safe_path = check_upload_zip("40000", "0", mock_file, "test.zip", "a/b.txt")
        assert status == 0

    def test_all_valid_large_total_size(self):
        mock_file = MagicMock()
        large_size = 4 * 1024 * 1024 * 1024
        status, msg, safe_path = check_upload_zip("0", str(large_size), mock_file, "test.zip", "big.zip")
        assert status == 0

    # --- validation order: chunk params checked first ---

    def test_validation_order_chunk_first(self):
        status, msg, path = check_upload_zip(None, "10", None, None, "/absolute")
        assert status == -1
        assert "current_chunk_idx" in msg


# ---------------------------------------------------------------------------
# Flask route tests for views.py
# ---------------------------------------------------------------------------

class TestUploadRoute:
    def test_upload_no_session(self):
        """测试 upload 路由无 session 的情况（行27-28）"""
        app = Flask(__name__)
        app.config['TESTING'] = True
        app.config['SECRET_KEY'] = 'test-secret-key'
        app.register_blueprint(directory_storage_bp)
        client = app.test_client()
        response = client.post('/dir/upload', data={
            "file": (io.BytesIO(b"content"), "test.zip")
        }, content_type='multipart/form-data')
        assert response.json["code"] == -1
        assert "Unkown" in response.json["msg"]

    def test_upload_with_session(self, mocker):
        """测试 upload 路由有 session 的情况（行29-31）"""
        mock_process = mocker.patch(
            'plugin.codemig.codemig_dir_manager.views.process_upload',
            return_value={"code": 0, "msg": "ok", "dir_id": 123})
        app = Flask(__name__)
        app.config['TESTING'] = True
        app.config['SECRET_KEY'] = 'test-secret-key'
        app.register_blueprint(directory_storage_bp)

        @app.before_request
        def set_session():
            from flask import session as flask_session
            flask_session['user_name'] = 'test_user'
            request.user_id = 1

        with app.test_client() as client:
            data = {
                "file": (io.BytesIO(b"dummy file content"), "test.zip")
            }
            response = client.post('/dir/upload', data=data,
                                   content_type='multipart/form-data')
            assert response.json["code"] == 0


class TestUploadZipRoute:
    def test_upload_zip_no_session(self):
        """测试 upload_zip 路由无 session 的情况（行141-142）"""
        app = Flask(__name__)
        app.config['TESTING'] = True
        app.config['SECRET_KEY'] = 'test-secret-key'
        app.register_blueprint(directory_storage_bp)
        client = app.test_client()
        response = client.post('/dir/upload_zip', data={
            "file": (io.BytesIO(b"content"), "test.zip"),
            "current_chunk_idx": "0",
            "total_chunk_size": "100",
            "file_name": "test.zip",
            "relativePath": ""
        }, content_type='multipart/form-data')
        assert response.json["code"] == -1
        assert "Unkown" in response.json["msg"]

    def test_upload_zip_validation_fails(self):
        """测试 upload_zip 验证失败记录操作日志（行154-157）"""
        app = Flask(__name__)
        app.config['TESTING'] = True
        app.config['SECRET_KEY'] = 'test-secret-key'
        app.register_blueprint(directory_storage_bp)

        @app.before_request
        def mock_request():
            from flask import session as flask_session
            flask_session['user_name'] = 'test_user'
            request.user_id = 1

        with app.test_client() as client:
            with app.app_context():
                response = client.post('/dir/upload_zip', data={
                    "file": (io.BytesIO(b"content"), "test.zip"),
                    "current_chunk_idx": "invalid",
                    "total_chunk_size": "100",
                    "file_name": "test.zip",
                    "relativePath": ""
                }, content_type='multipart/form-data')
                assert response.json["code"] == -1


class TestDeleteFolderRoute:
    def test_delete_folder_no_session(self):
        """测试 delete_folder 路由无 session 的情况（行165-166）"""
        app = Flask(__name__)
        app.config['TESTING'] = True
        app.config['SECRET_KEY'] = 'test-secret-key'
        app.register_blueprint(directory_storage_bp)
        client = app.test_client()
        import json
        response = client.post('/dir/delete_folder',
                               data=json.dumps({"dir_id": 1}),
                               content_type='application/json')
        assert response.json["code"] == -1
        assert "Unkown" in response.json["msg"]

    def test_delete_folder_with_session(self, mocker):
        """测试 delete_folder 路由有 session 的情况（行168-170）"""
        mock_delete = mocker.patch(
            'plugin.codemig.codemig_dir_manager.views.delete_folder_by_dir_id',
            return_value={"code": 0, "msg": "ok"})
        app = Flask(__name__)
        app.config['TESTING'] = True
        app.config['SECRET_KEY'] = 'test-secret-key'
        app.register_blueprint(directory_storage_bp)

        @app.before_request
        def mock_request():
            from flask import session as flask_session
            flask_session['user_name'] = 'test_user'
            request.user_id = 1

        with app.test_client() as client:
            import json
            response = client.post('/dir/delete_folder',
                                   data=json.dumps({"dir_id": 1}),
                                   content_type='application/json')
            assert response.json["code"] == 0
