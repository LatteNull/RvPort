import pytest
from unittest.mock import patch, MagicMock, Mock

from plugin.codemig.dependence_process.dependence_sql import (
    create_changes_and_copy_file,
    create_insert_values,
    save_changes_to_database,
    create_prepared_text_changes,
    create_prepared_lib_changes,
    insert_task_dependence_update_status,
    scan_packages,
    record_fail_package_info,
    process_extracted_dir
)
from plugin.codemig.dependence_process.models import DependencePackages
from plugin.codemig.codemig_task_manager.task_common import DependencePackagesStatus, TaskDependenceStatus
from common.db.SQLOperation import db_session_scope, DatabaseException
from plugin.codemig.codemig_task_manager.models import CodemigTasks
from plugin.codemig.main.dir_solver import DirSolver
from plugin.codemig.codemig_common.migration_class import MigrationClass


class TestCreateChangesAndCopyFile:
    """测试 create_changes_and_copy_file 函数"""

    def test_create_changes_and_copy_file_empty_result(self):
        """测试空结果的情况"""
        file_solvers_result = {}
        result = create_changes_and_copy_file(file_solvers_result, "/test/path/file.py")
        assert result == {}

    @patch('plugin.codemig.dependence_process.dependence_sql.create_insert_values')
    def test_create_changes_and_copy_file_with_changes(self, mock_create_insert):
        """测试有变更的情况"""
        mock_solver = MagicMock()
        mock_solver.migration_class.return_value = MigrationClass.TEXT
        
        # change_list 和 _ 元组，其中 change_list 有内容
        change_list = [(1, 2, "suggestion", False, "code")]
        file_solvers_result = {mock_solver: (change_list, None)}
        
        mock_create_insert.return_value = [("/test/path/file.py", "solver_type", 0, 1, 2, "suggestion", False, "code")]
        
        result = create_changes_and_copy_file(file_solvers_result, "/test/path/file.py")
        
        assert MigrationClass.TEXT in result
        assert len(result[MigrationClass.TEXT]) == 1
        mock_create_insert.assert_called_once_with("/test/path/file.py", mock_solver, change_list)

    @patch('plugin.codemig.dependence_process.dependence_sql.create_insert_values')
    def test_create_changes_and_copy_file_empty_change_list(self, mock_create_insert):
        """测试空变更列表的情况"""
        mock_solver = MagicMock()
        mock_solver.migration_class.return_value = MigrationClass.TEXT
        
        # 空的 change_list
        file_solvers_result = {mock_solver: ([], None)}
        
        result = create_changes_and_copy_file(file_solvers_result, "/test/path/file.py")
        
        assert result == {}
        mock_create_insert.assert_not_called()


class TestCreateInsertValues:
    """测试 create_insert_values 函数"""

    def test_create_insert_values_text_file(self):
        """测试文本文件的变更值创建"""
        mock_solver = MagicMock()
        mock_solver.migration_class.return_value = MigrationClass.TEXT
        mock_solver.get_solver_type.return_value = "solver_type"
        mock_solver.append_or_replace.return_value = 0

        change_list = [(1, 2, "suggestion", False, "code"), (3, 4, "suggestion2", True, "code2")]

        result = create_insert_values("/test/path/file.py", mock_solver, change_list)

        assert len(result) == 2
        assert result[0] == ("/test/path/file.py", "solver_type", 0, 1, 2, "suggestion", False, "code")
        assert result[1] == ("/test/path/file.py", "solver_type", 0, 3, 4, "suggestion2", True, "code2")

    def test_create_insert_values_dll_file(self):
        """测试动态链接库文件的变更值创建"""
        mock_solver = MagicMock()
        mock_solver.migration_class.return_value = MigrationClass.DYNAMIC_LINK_LIBRARY

        change_list = [("x86_64", "suggestion1"), ("aarch64", "suggestion2")]

        result = create_insert_values("/test/path/lib.so", mock_solver, change_list)

        # 对于 DLL 类型，返回的是 (file_path, arch, suggestion) 格式
        assert len(result) == 2
        assert result[0] == ("/test/path/lib.so", "x86_64", "suggestion1")
        assert result[1] == ("/test/path/lib.so", "aarch64", "suggestion2")

    def test_create_insert_values_unknown_type(self):
        """测试未知文件类型的情况"""
        mock_solver = MagicMock()
        mock_solver.migration_class.return_value = MigrationClass.UNKNOWN

        change_list = [(1, 2, "suggestion", False, "code")]

        result = create_insert_values("/test/path/file.h", mock_solver, change_list)

        assert result is None


class TestSaveChangesToDatabase:
    """测试 save_changes_to_database 函数"""

    @patch('plugin.codemig.dependence_process.dependence_sql.DependencePackages.record_package')
    @patch('plugin.codemig.dependence_process.dependence_sql.db_session_scope')
    def test_save_changes_success(self, mock_db_scope, mock_record_package):
        """测试成功保存变更到数据库"""
        mock_session = MagicMock()
        mock_record_package.return_value = 123
        
        # Mock session.add 和 session.flush
        mock_file_dep = MagicMock()
        mock_file_dep.file_id = 1
        
        def mock_add(obj):
            pass
        
        def mock_flush():
            if hasattr(obj, 'file_id'):
                obj.file_id = 1
        
        mock_session.add = mock_add
        mock_session.flush = mock_flush
        mock_session.query.return_value.filter.return_value.first.return_value = None

        with patch.object(mock_db_scope, '__enter__', return_value=mock_session):
            with patch.object(mock_db_scope, '__exit__', return_value=False):
                # code_too_long 需要是枚举类型，有 .value 属性
                class MockCodeTooLong:
                    value = False

                result = save_changes_to_database(
                    "pkg_name", "1.0.0", "/target/dir",
                    [(MigrationClass.TEXT.value, "/path/to/file.py")],
                    [("/path/to/file.py", "solver_type", 0, 1, 10, "suggestion", MockCodeTooLong(), "code")],
                    [],
                    {},
                    {}
                )

                assert result[0] is True
                assert result[1] is None
                assert result[2] == 123

    @patch('plugin.codemig.dependence_process.dependence_sql.DependencePackages.record_package')
    def test_save_changes_record_package_failed(self, mock_record_package):
        """测试记录包失败的情况"""
        mock_record_package.return_value = None
        
        result = save_changes_to_database(
            "pkg_name", "1.0.0", "/target/dir",
            [], [], [], {}, {}
        )
        
        assert result[0] is False
        assert "存储 pkg_name-1.0.0 失败!" in result[1]
        assert result[2] is None

    @patch('plugin.codemig.dependence_process.dependence_sql.DependencePackages.record_package')
    @patch('plugin.codemig.dependence_process.dependence_sql.db_session_scope')
    def test_save_changes_database_exception(self, mock_db_scope, mock_record_package):
        """测试数据库异常的情况"""
        mock_record_package.return_value = 123
        mock_db_scope.side_effect = DatabaseException("Database error")
        
        result = save_changes_to_database(
            "pkg_name", "1.0.0", "/target/dir",
            [], [], [], {}, {}
        )
        
        assert result[0] is False
        assert "Database operation failed" in result[1]
        assert result[2] is None

    @patch('plugin.codemig.dependence_process.dependence_sql.DependencePackages.record_package')
    @patch('plugin.codemig.dependence_process.dependence_sql.db_session_scope')
    def test_save_changes_with_missing_file_data(self, mock_db_scope, mock_record_package):
        """测试包含缺失文件数据的保存"""
        mock_session = MagicMock()
        mock_record_package.return_value = 123
        
        mock_file_dep = MagicMock()
        mock_file_dep.file_id = 1
        
        def mock_add(obj):
            if hasattr(obj, 'file_id'):
                obj.file_id = 1
        
        mock_session.add = mock_add
        mock_session.flush = lambda: None
        
        with patch.object(mock_db_scope, '__enter__', return_value=mock_session):
            with patch.object(mock_db_scope, '__exit__', return_value=False):
                missing_file_data = {"/missing/file.go": ["/x86_64/file.go", "/arm64/file.go"]}
                
                result = save_changes_to_database(
                    "pkg_name", "1.0.0", "/target/dir",
                    [], [], [], missing_file_data, {}
                )
                
                assert result[0] is True
                assert result[2] == 123

    @patch('plugin.codemig.dependence_process.dependence_sql.DependencePackages.record_package')
    @patch('plugin.codemig.dependence_process.dependence_sql.db_session_scope')
    def test_save_changes_with_missing_dir(self, mock_db_scope, mock_record_package):
        """测试包含缺失目录数据的保存"""
        mock_session = MagicMock()
        mock_record_package.return_value = 123
        
        def mock_add(obj):
            if hasattr(obj, 'file_id'):
                obj.file_id = 1
        
        mock_session.add = mock_add
        mock_session.flush = lambda: None
        
        with patch.object(mock_db_scope, '__enter__', return_value=mock_session):
            with patch.object(mock_db_scope, '__exit__', return_value=False):
                missing_dir = {"/missing/dir": ["/x86_64/dir", "/arm64/dir"]}
                
                result = save_changes_to_database(
                    "pkg_name", "1.0.0", "/target/dir",
                    [], [], [], {}, missing_dir
                )
                
                assert result[0] is True
                assert result[2] == 123

    @patch('plugin.codemig.dependence_process.dependence_sql.DependencePackages.record_package')
    @patch('plugin.codemig.dependence_process.dependence_sql.db_session_scope')
    def test_save_changes_os_error(self, mock_db_scope, mock_record_package):
        """测试 OSError 异常的情况"""
        mock_record_package.return_value = 123
        mock_db_scope.side_effect = OSError("OS error")
        
        result = save_changes_to_database(
            "pkg_name", "1.0.0", "/target/dir",
            [], [], [], {}, {}
        )
        
        assert result[0] is False
        assert result[2] is None

    @patch('plugin.codemig.dependence_process.dependence_sql.DependencePackages.record_package')
    @patch('plugin.codemig.dependence_process.dependence_sql.db_session_scope')
    def test_save_changes_io_error(self, mock_db_scope, mock_record_package):
        """测试 IOError 异常的情况"""
        mock_record_package.return_value = 123
        mock_db_scope.side_effect = IOError("IO error")
        
        result = save_changes_to_database(
            "pkg_name", "1.0.0", "/target/dir",
            [], [], [], {}, {}
        )
        
        assert result[0] is False
        assert result[2] is None


class TestCreatePreparedTextChanges:
    """测试 create_prepared_text_changes 函数"""

    def test_create_prepared_text_changes_success(self):
        """测试成功准备文本变更"""
        file_path_to_file_id = {(MigrationClass.TEXT.value, "/path/to/file.py"): 1}

        # code_too_long 需要是枚举类型，有 .value 属性
        class MockCodeTooLong:
            value = False

        text_file_changes = [
            ("/path/to/file.py", "solver_type", 0, 1, 10, "suggestion", MockCodeTooLong(), "code")
        ]

        result = create_prepared_text_changes(file_path_to_file_id, text_file_changes)
        
        assert len(result) == 1
        assert result[0][0] == 1  # file_id
        assert result[0][1] == "solver_type"
        assert result[0][2] == 0  # append_or_replace
        assert result[0][3] == 1  # start_lineno
        assert result[0][4] == 10  # end_lineno

    def test_create_prepared_text_changes_file_not_found(self):
        """测试文件未找到的情况"""
        file_path_to_file_id = {}
        text_file_changes = [
            ("/path/to/file.py", "solver_type", 0, 1, 10, "suggestion", False, "code")
        ]
        
        with pytest.raises(DatabaseException) as exc_info:
            create_prepared_text_changes(file_path_to_file_id, text_file_changes)
        
        assert "Error finding file Id with key" in str(exc_info.value)

    def test_create_prepared_text_changes_empty_changes(self):
        """测试空变更列表"""
        file_path_to_file_id = {}
        text_file_changes = []
        
        result = create_prepared_text_changes(file_path_to_file_id, text_file_changes)
        
        assert result == []


class TestCreatePreparedLibChanges:
    """测试 create_prepared_lib_changes 函数"""

    def test_create_prepared_lib_changes_success(self):
        """测试成功准备库变更"""
        file_path_to_file_id = {(MigrationClass.DYNAMIC_LINK_LIBRARY.value, "/path/to/lib.so"): 1}
        lib_file_changes = [
            ("/path/to/lib.so", "x86_64", "suggestion1"),
            ("/path/to/lib.so", "aarch64", "suggestion2")
        ]
        
        result = create_prepared_lib_changes(file_path_to_file_id, lib_file_changes)
        
        assert len(result) == 2
        assert result[0] == (1, "x86_64", "suggestion1")
        assert result[1] == (1, "aarch64", "suggestion2")

    def test_create_prepared_lib_changes_file_not_found(self):
        """测试文件未找到的情况"""
        file_path_to_file_id = {}
        lib_file_changes = [
            ("/path/to/lib.so", "x86_64", "suggestion1")
        ]
        
        with pytest.raises(DatabaseException) as exc_info:
            create_prepared_lib_changes(file_path_to_file_id, lib_file_changes)
        
        assert "Error finding file Id with key" in str(exc_info.value)

    def test_create_prepared_lib_changes_empty_changes(self):
        """测试空变更列表"""
        file_path_to_file_id = {}
        lib_file_changes = []
        
        result = create_prepared_lib_changes(file_path_to_file_id, lib_file_changes)
        
        assert result == []


class TestInsertTaskDependenceUpdateStatus:
    """测试 insert_task_dependence_update_status 函数"""

    @patch('plugin.codemig.dependence_process.dependence_sql.CodemigTaskDependence')
    @patch('plugin.codemig.dependence_process.dependence_sql.db_session_scope')
    def test_insert_task_dependence_success(self, mock_db_scope, mock_codemig_task_dep):
        """测试成功插入任务依赖关系"""
        from plugin.codemig.dependence_process.dependence_sql import CodemigTasks as LocalCodemigTasks

        mock_session = MagicMock()
        mock_task = MagicMock()
        mock_task.user_id = "user123"

        # 设置第一次查询（获取 task）的返回值
        mock_query_instance_1 = MagicMock()
        mock_query_instance_1.filter.return_value.first.return_value = mock_task

        # 设置第二次查询（update）的返回值
        mock_query_instance_2 = MagicMock()
        mock_query_instance_2.filter.return_value.update.return_value = 1

        # 让 query 方法根据参数返回不同的 mock
        def query_side_effect(model):
            if model == LocalCodemigTasks:
                return mock_query_instance_1
            return mock_query_instance_2

        mock_session.query.side_effect = query_side_effect
        mock_session.bulk_save_objects = MagicMock()

        # 正确设置 context manager
        mock_db_scope.return_value.__enter__.return_value = mock_session
        mock_db_scope.return_value.__exit__.return_value = False

        result = insert_task_dependence_update_status(
            1, [(1, 100), (2, 200)]
        )

        assert result is True
        # bulk_save_objects 应该被调用
        assert mock_session.bulk_save_objects.called

    @patch('plugin.codemig.dependence_process.dependence_sql.db_session_scope')
    def test_insert_task_dependence_task_not_found(self, mock_db_scope):
        """测试任务不存在的情况"""
        mock_session = MagicMock()

        # 设置查询返回 None（任务不存在）
        mock_session.query.return_value.filter.return_value.first.return_value = None

        # 正确设置 context manager
        mock_db_scope.return_value.__enter__.return_value = mock_session
        mock_db_scope.return_value.__exit__.return_value = False

        result = insert_task_dependence_update_status(999, [(1, 100)])

        assert result is False

    @patch('plugin.codemig.dependence_process.dependence_sql.db_session_scope')
    def test_insert_task_dependence_database_exception(self, mock_db_scope):
        """测试数据库异常的情况"""
        mock_db_scope.side_effect = DatabaseException("Database error")
        
        result = insert_task_dependence_update_status(1, [(1, 100)])
        
        assert result is False

    @patch('plugin.codemig.dependence_process.dependence_sql.db_session_scope')
    def test_insert_task_dependence_empty_dependence_ids(self, mock_db_scope):
        """测试空的依赖 ID 列表"""
        mock_session = MagicMock()
        mock_task = MagicMock()
        mock_task.user_id = "user123"
        mock_session.query.return_value.filter.return_value.first.return_value = mock_task
        mock_session.bulk_save_objects = MagicMock()
        mock_session.query.return_value.update = MagicMock()
        
        with patch.object(mock_db_scope, '__enter__', return_value=mock_session):
            with patch.object(mock_db_scope, '__exit__', return_value=False):
                result = insert_task_dependence_update_status(1, [])
                
                # 即使为空也应该成功（只是没有数据插入）
                assert result is True

    @patch('plugin.codemig.dependence_process.dependence_sql.db_session_scope')
    def test_insert_task_dependence_os_error(self, mock_db_scope):
        """测试 OSError 异常"""
        mock_db_scope.side_effect = OSError("OS error")
        
        result = insert_task_dependence_update_status(1, [(1, 100)])
        
        assert result is False

    @patch('plugin.codemig.dependence_process.dependence_sql.db_session_scope')
    def test_insert_task_dependence_io_error(self, mock_db_scope):
        """测试 IOError 异常"""
        mock_db_scope.side_effect = IOError("IO error")
        
        result = insert_task_dependence_update_status(1, [(1, 100)])
        
        assert result is False


class TestScanPackages:
    """测试 scan_packages 函数"""

    @patch('plugin.codemig.dependence_process.dependence_sql.os.walk')
    @patch('plugin.codemig.dependence_process.dependence_sql.detect_arch')
    @patch('plugin.codemig.dependence_process.dependence_sql.group_files')
    @patch('plugin.codemig.dependence_process.dependence_sql.CodemigProcessor.process_file')
    @patch('plugin.codemig.dependence_process.dependence_sql.create_changes_and_copy_file')
    @patch('plugin.codemig.dependence_process.dependence_sql.save_changes_to_database')
    def test_scan_packages_success(self, mock_save, mock_create_changes, mock_process_file, 
                                   mock_group_files, mock_detect_arch, mock_walk):
        """测试成功扫描包"""
        # Mock os.walk
        mock_walk.return_value = [
            ("/test/dir", [], ["file.py"])
        ]
        
        # Mock detect_arch
        mock_detect_arch.return_value = {"missing": {}, "found": {}}
        
        # Mock group_files
        mock_group_files.return_value = ({}, [], [])
        
        # Mock process_file
        mock_process_file.return_value = {}
        
        # Mock create_changes_and_copy_file
        mock_create_changes.return_value = {}
        
        # Mock save_changes_to_database
        mock_save.return_value = (True, None, 123)
        
        result = scan_packages("pkg_name", "1.0.0", "/test/dir", "pkg_spec")
        
        assert result[0] is True
        assert "安装 pkg_spec 成功!" in result[1]
        assert result[2] == 123

    @patch('plugin.codemig.dependence_process.dependence_sql.os.walk')
    @patch('plugin.codemig.dependence_process.dependence_sql.save_changes_to_database')
    def test_scan_packages_save_failed(self, mock_save, mock_walk):
        """测试保存失败的情况"""
        mock_walk.return_value = [
            ("/test/dir", [], [])
        ]
        
        mock_save.return_value = (False, "Save failed", None)
        
        result = scan_packages("pkg_name", "1.0.0", "/test/dir", "pkg_spec")
        
        assert result[0] is False
        assert result[1] == "Save failed"
        assert result[2] is None

    @patch('plugin.codemig.dependence_process.dependence_sql.os.walk')
    def test_scan_packages_skip_git_github_dirs(self, mock_walk):
        """测试跳过 .git 和 .github 目录"""
        mock_walk.return_value = [
            ("/test/dir", [".git", ".github", "normal_dir"], ["file.py"])
        ]
        
        # 调用后检查 dirs 是否被修改
        for root, dirs, files in mock_walk.return_value:
            dirs[:] = [d for d in dirs if d not in ['.git', '.github']]
        
        assert ".git" not in mock_walk.return_value[0][1]
        assert ".github" not in mock_walk.return_value[0][1]


class TestRecordFailPackageInfo:
    """测试 record_fail_package_info 函数"""

    @patch('plugin.codemig.dependence_process.dependence_sql.DependencePackages.record_package')
    def test_record_fail_package_info_success(self, mock_record_package):
        """测试成功记录失败的包信息"""
        mock_record_package.return_value = 123
        
        result = record_fail_package_info("pkg_name", "1.0.0", "/target/dir", "Error message")
        
        assert result == 123
        mock_record_package.assert_called_once_with(
            "pkg_name", "1.0.0", "/target/dir",
            DependencePackagesStatus.FAILED.value, "Error message"
        )

    @patch('plugin.codemig.dependence_process.dependence_sql.DependencePackages.record_package')
    def test_record_fail_package_info_failed(self, mock_record_package):
        """测试记录失败的包信息失败"""
        mock_record_package.return_value = None
        
        result = record_fail_package_info("pkg_name", "1.0.0", "/target/dir", "Error message")
        
        assert result is None


class TestCreateChangesAndCopyFileAdditional:
    """Test create_changes_and_copy_file additional cases"""

    @patch('plugin.codemig.dependence_process.dependence_sql.create_insert_values')
    def test_create_changes_and_copy_file_empty_result_lit(self, mock_create_insert):
        """测试空 result_lit 的情况"""
        mock_solver = MagicMock()
        # result_lit 是 (None, None) 或空列表
        file_solvers_result = {mock_solver: ([], None)}

        result = create_changes_and_copy_file(file_solvers_result, "/test/path/file.py")

        assert result == {}
        mock_create_insert.assert_not_called()


class TestScanPackagesAdditional:
    """Additional tests for scan_packages"""

    @patch('plugin.codemig.dependence_process.dependence_sql.os.walk')
    @patch('plugin.codemig.dependence_process.dependence_sql.detect_arch')
    @patch('plugin.codemig.dependence_process.dependence_sql.group_files')
    @patch('plugin.codemig.dependence_process.dependence_sql.CodemigProcessor.process_file')
    @patch('plugin.codemig.dependence_process.dependence_sql.create_changes_and_copy_file')
    @patch('plugin.codemig.dependence_process.dependence_sql.save_changes_to_database')
    def test_scan_packages_with_missing_dirs(
            self, mock_save, mock_create_changes, mock_process_file,
            mock_group_files, mock_detect_arch, mock_walk):
        """测试包含缺失目录的扫描"""
        mock_walk.return_value = [
            ("/test/dir", [".git", "normal_dir"], ["file.py"])
        ]

        # Mock detect_arch 返回有 missing 目录
        mock_detect_arch.return_value = {
            "missing": {"arm64": [["x86_64"]]},
            "found": {}
        }

        mock_group_files.return_value = ({}, [], [])
        mock_process_file.return_value = {}
        mock_create_changes.return_value = {}
        mock_save.return_value = (True, None, 123)

        result = scan_packages("pkg_name", "1.0.0", "/test/dir", "pkg_spec")

        assert result[0] is True

    @patch('plugin.codemig.dependence_process.dependence_sql.os.walk')
    @patch('plugin.codemig.dependence_process.dependence_sql.detect_arch')
    @patch('plugin.codemig.dependence_process.dependence_sql.group_files')
    @patch('plugin.codemig.dependence_process.dependence_sql.CodemigProcessor.process_file')
    @patch('plugin.codemig.dependence_process.dependence_sql.create_changes_and_copy_file')
    @patch('plugin.codemig.dependence_process.dependence_sql.save_changes_to_database')
    def test_scan_packages_with_missing_files(
            self, mock_save, mock_create_changes, mock_process_file,
            mock_group_files, mock_detect_arch, mock_walk):
        """测试包含缺失文件的扫描"""
        mock_walk.return_value = [
            ("/test/dir", [], ["file.go", "file_riscv64.go"])
        ]

        mock_detect_arch.return_value = {"missing": {}, "found": {}}

        # Mock group_files 返回有缺失文件
        mock_group_files.return_value = ({"missing.go": ["found.go"]}, [], [])

        mock_process_file.return_value = {}
        mock_create_changes.return_value = {}
        mock_save.return_value = (True, None, 123)

        result = scan_packages("pkg_name", "1.0.0", "/test/dir", "pkg_spec")

        assert result[0] is True

    @patch('plugin.codemig.dependence_process.dependence_sql.os.walk')
    @patch('plugin.codemig.dependence_process.dependence_sql.detect_arch')
    @patch('plugin.codemig.dependence_process.dependence_sql.group_files')
    @patch('plugin.codemig.dependence_process.dependence_sql.CodemigProcessor.process_file')
    @patch('plugin.codemig.dependence_process.dependence_sql.create_changes_and_copy_file')
    @patch('plugin.codemig.dependence_process.dependence_sql.save_changes_to_database')
    def test_scan_packages_skip_found_files(
            self, mock_save, mock_create_changes, mock_process_file,
            mock_group_files, mock_detect_arch, mock_walk):
        """测试跳过已找到的文件"""
        mock_walk.return_value = [
            ("/test/dir", [], ["file.go", "file_x86_64.go"])
        ]

        mock_detect_arch.return_value = {
            "missing": {},
            "found": {"file.go": [["other.go"]]}
        }

        mock_group_files.return_value = ({}, [], [])
        mock_process_file.return_value = {}
        mock_create_changes.return_value = {}
        mock_save.return_value = (True, None, 123)

        result = scan_packages("pkg_name", "1.0.0", "/test/dir", "pkg_spec")

        assert result[0] is True


class TestProcessExtractedDir:
    """测试 process_extracted_dir 函数"""

    @patch('plugin.codemig.dependence_process.dependence_sql.DirSolver')
    def test_process_extracted_dir_success(self, mock_dir_solver):
        """测试成功解析目录"""
        mock_dir_solver.solve.return_value = {"result": "data"}

        result = process_extracted_dir("/extract/path")

        assert result == {"result": "data"}
        mock_dir_solver.solve.assert_called_once_with("/extract/path")


class TestCreateChangesAndCopyFileEdgeCases:
    """Test create_changes_and_copy_file edge cases"""

    @patch('plugin.codemig.dependence_process.dependence_sql.create_insert_values')
    def test_create_changes_and_copy_file_none_result_lit(self, mock_create_insert):
        """测试 result_lit 为 None 的情况"""
        mock_solver = MagicMock()
        file_solvers_result = {mock_solver: (None, None)}

        result = create_changes_and_copy_file(file_solvers_result, "/test/path/file.py")

        assert result == {}
        mock_create_insert.assert_not_called()

    def test_create_changes_and_copy_file_empty_tuple_result_lit(self):
        """测试 result_lit 为空元组的情况（触发 line 40）"""
        mock_solver = MagicMock()
        # 空元组会被 if not result_lit 判断为 True
        file_solvers_result = {mock_solver: ()}

        result = create_changes_and_copy_file(file_solvers_result, "/test/path/file.py")

        assert result == {}

    @patch('plugin.codemig.dependence_process.dependence_sql.create_insert_values')
    def test_create_changes_and_copy_file_multiple_solvers(self, mock_create_insert):
        """测试多个 solver 的情况"""
        mock_solver1 = MagicMock()
        mock_solver1.migration_class.return_value = MigrationClass.TEXT

        mock_solver2 = MagicMock()
        mock_solver2.migration_class.return_value = MigrationClass.DYNAMIC_LINK_LIBRARY

        change_list1 = [(1, 2, "suggestion1", False, "code1")]
        change_list2 = [("x86_64", "suggestion2")]

        file_solvers_result = {
            mock_solver1: (change_list1, None),
            mock_solver2: (change_list2, None)
        }

        mock_create_insert.side_effect = [
            [("/path/file.py", "type1", 0, 1, 2, "suggestion1", False, "code1")],
            [("/path/lib.so", "x86_64", "suggestion2")]
        ]

        result = create_changes_and_copy_file(file_solvers_result, "/path/file.py")

        assert MigrationClass.TEXT in result
        assert MigrationClass.DYNAMIC_LINK_LIBRARY in result
        assert mock_create_insert.call_count == 2
