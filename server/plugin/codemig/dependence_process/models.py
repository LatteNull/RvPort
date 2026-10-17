"""
Codemig 依赖处理 ORM 模型
对应数据库表: codemig_task_dependence, dependence_packages, file_dependence,
            file_dependence_suggestion, software_dependence_suggestion,
            dependence_existing_architecture, dependence_task
"""
import sys

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, CheckConstraint, func, \
    case

import os
from datetime import datetime

MODULE_PATH = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if MODULE_PATH not in sys.path:
    sys.path.append(MODULE_PATH)
from common.db.SQLOperation import Base, DatabaseException, db_session_scope
from common.public import logger
# 导入相关模型以确保表被注册到 Base 元数据中
# 这样 SQLAlchemy 才能正确解析外键关系（task_id, dir_id, dependence_id）
from plugin.codemig.codemig_task_manager.models import CodemigTasks  # noqa: F401
from plugin.codemig.codemig_dir_manager.models import CodemigDirectoryStorage  # noqa: F401

LOGGER = logger.init_log('codemig')


class CodemigTaskDependence(Base):
    """
    任务依赖关系 ORM 类
    对应数据库表: codemig_task_dependence
    """
    __tablename__ = 'codemig_task_dependence'
    __table_args__ = {'extend_existing': True}

    user_id = Column(String(64))
    task_id = Column(Integer, ForeignKey('codemig_tasks.task_id'))
    dir_id = Column(Integer, ForeignKey('codemig_directory_storage.dir_id'))
    dependence_id = Column(Integer, ForeignKey('dependence_packages.dependence_id'))
    task_dependence_id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, default=datetime.now)

    @staticmethod
    def get_dependencies_by_task_id(task_id, session=None):
        """
        根据任务ID查询依赖包信息

        Args:
            task_id: 任务ID
            session: 可选的数据库会话，如果提供则使用该会话，否则创建新会话

        Returns:
            list or None: 成功返回 (dependence_id, dependence_package, version, status, reason) 元组列表，
                         失败返回 None
        """
        # 使用提供的会话
        results = session.query(
            DependencePackages.dependence_id,
            DependencePackages.dependence_package,
            DependencePackages.version,
            DependencePackages.status,
            DependencePackages.fail_reason
        ).join(
            CodemigTaskDependence,
            CodemigTaskDependence.dependence_id == DependencePackages.dependence_id
        ).filter(
            CodemigTaskDependence.task_id == task_id
        ).order_by(
            DependencePackages.dependence_package.asc()
        ).all()

        return [
            (result.dependence_id, result.dependence_package, result.version,
             result.status, result.fail_reason)
            for result in results
        ]


class DependencePackages(Base):
    """
    依赖包 ORM 类
    对应数据库表: dependence_packages
    status: 0 -> failed, 1 -> success
    """
    __tablename__ = 'dependence_packages'
    __table_args__ = {'extend_existing': True}

    dependence_id = Column(Integer, primary_key=True, autoincrement=True)
    dependence_package = Column(Text)
    version = Column(Text)
    status = Column(Integer)
    fail_reason = Column(Text)
    dependence_package_path = Column(Text)

    @staticmethod
    def is_package_installed(package, version):
        """
        检查包是否已安装

        Args:
            package: 包名
            version: 版本号

        Returns:
            int or None: 如果包已安装（status=1）则返回 dependence_id，否则返回 None
        """
        try:
            with db_session_scope() as session:
                result = session.query(DependencePackages).filter(
                    DependencePackages.dependence_package == package,
                    DependencePackages.version == version,
                    DependencePackages.status == 1
                ).first()

                if result:
                    return result.dependence_id
                return None

        except (DatabaseException, OSError, IOError) as e:
            LOGGER.error(f"get {package}:{version} error of db error: {str(e)}")
            return None

    @staticmethod
    def record_package(package, version, path, status, fail_reason):
        """
        记录已安装包到数据库（INSERT OR IGNORE 语义）

        Args:
            package: 包名
            version: 版本号
            path: 包路径
            status: 状态值（0 -> failed, 1 -> success）
            fail_reason: 失败原因（可选）

        Returns:
            int or None: 成功返回 dependence_id，失败返回 None
        """
        try:
            with db_session_scope() as session:
                # 先查询是否已存在相同的记录（INSERT OR IGNORE 语义）
                existing = session.query(DependencePackages).filter(
                    DependencePackages.dependence_package == package,
                    DependencePackages.version == version,
                    DependencePackages.dependence_package_path == path
                ).first()

                if existing:
                    # 如果已存在，返回现有的 dependence_id
                    return existing.dependence_id

                # 如果不存在，插入新记录
                new_package = DependencePackages(
                    dependence_package=package,
                    version=version,
                    dependence_package_path=path,
                    status=status,
                    fail_reason=fail_reason
                )
                session.add(new_package)
                session.flush()
                return new_package.dependence_id

        except (DatabaseException, OSError, IOError) as e:
            LOGGER.error(f"record {package}:{version} error of db error: {str(e)}")
            return None

    @staticmethod
    def get_package_path(dependence_id):
        """
        查询依赖包路径

        Args:
            dependence_id: 依赖ID

        Returns:
            str or None: 依赖包路径，如果未找到或发生错误则返回 None
        """
        try:
            with db_session_scope() as session:
                dependence_package = session.query(DependencePackages).filter(
                    DependencePackages.dependence_id == dependence_id
                ).first()

                if not dependence_package:
                    LOGGER.warning(f"Dependence package not found: dependence_id={dependence_id}")
                    return None

                return dependence_package.dependence_package_path
        except (DatabaseException, OSError, IOError) as err:
            LOGGER.error("Database operation failed: %s", err)
            return None


class FileDependence(Base):
    """
    文件依赖 ORM 类
    对应数据库表: file_dependence
    """
    __tablename__ = 'file_dependence'
    __table_args__ = {'extend_existing': True}

    dependence_id = Column(Integer, ForeignKey('dependence_packages.dependence_id'))
    file_id = Column(Integer, primary_key=True, autoincrement=True)
    type = Column(Integer)
    file_path = Column(Text)
    created_at = Column(DateTime, default=datetime.now)

    @staticmethod
    def get_file_path(file_id):
        """
        根据文件ID查询文件路径

        Args:
            file_id: 文件ID

        Returns:
            str or None: 文件路径，如果未找到或发生错误则返回 None
        """
        try:
            with db_session_scope() as session:
                file_dependence = session.query(FileDependence).filter(
                    FileDependence.file_id == file_id
                ).first()

                if not file_dependence:
                    LOGGER.warning(f"File dependence not found: file_id={file_id}")
                    return None

                return file_dependence.file_path
        except (DatabaseException, OSError, IOError) as err:
            LOGGER.error("Database operation failed: %s", err)
            return None

    @staticmethod
    def get_summary_by_dependence_ids(dependence_ids, session):
        """
        根据依赖ID列表查询汇总信息

        Args:
            dependence_ids: 依赖ID列表
            session: 可选的数据库会话，如果提供则使用该会话，否则创建新会话

        Returns:
            list or None: 成功返回 (dependence_id, text_type, file_type) 元组列表，
                         失败返回 None
        """
        if not dependence_ids:
            return []

        # 使用提供的会话
        results = session.query(
            FileDependence.dependence_id,
            func.count(
                func.distinct(
                    case(
                        (FileDependence.type == 0, FileDependenceSuggestion.id),
                        else_=None
                    )
                )
            ).label('text_type'),
            func.count(
                func.distinct(
                    case(
                        (FileDependence.type > 0, FileDependence.file_id),
                        else_=None
                    )
                )
            ).label('file_type')
        ).outerjoin(
            FileDependenceSuggestion,
            (FileDependence.dependence_id == FileDependenceSuggestion.dependence_id) &
            (FileDependence.file_id == FileDependenceSuggestion.file_id) &
            (FileDependence.type == 0)
        ).filter(
            FileDependence.dependence_id.in_(dependence_ids)
        ).group_by(
            FileDependence.dependence_id
        ).all()

        return [
            (result.dependence_id, result.text_type or 0, result.file_type or 0)
            for result in results
        ]

    @staticmethod
    def get_task_name_and_file_path(user_id, task_id, dir_id, file_id, dependence_id):
        """
        根据用户ID、任务ID、目录ID、文件ID和依赖ID查询任务名称和文件路径

        Args:
            user_id: 用户ID
            task_id: 任务ID
            dir_id: 目录ID
            file_id: 文件ID
            dependence_id: 依赖ID

        Returns:
            tuple or None: 成功返回 (task_name, file_path) 元组，如果未找到或发生错误则返回 None
        """
        try:
            with db_session_scope() as session:

                result = session.query(
                    CodemigTasks.task_name,
                    FileDependence.file_path
                ).join(
                    CodemigTaskDependence,
                    CodemigTasks.task_id == CodemigTaskDependence.task_id
                ).join(
                    FileDependence,
                    CodemigTaskDependence.dependence_id == FileDependence.dependence_id
                ).filter(
                    CodemigTaskDependence.user_id == user_id,
                    CodemigTaskDependence.task_id == task_id,
                    CodemigTaskDependence.dir_id == dir_id,
                    FileDependence.file_id == file_id,
                    FileDependence.dependence_id == dependence_id,
                    FileDependence.type == 0
                ).first()

                if result:
                    return (result.task_name, result.file_path)
                return None
        except (DatabaseException, OSError, IOError) as err:
            LOGGER.error("Database operation failed: %s", err)
            return None


class FileDependenceSuggestion(Base):
    """
    文件依赖建议 ORM 类
    对应数据库表: file_dependence_suggestion
    """
    __tablename__ = 'file_dependence_suggestion'
    __table_args__ = (
        CheckConstraint('append_or_replace IN (0, 1, 2)',
                        name='ck_file_dependence_suggestion_append_or_replace'),
        {'extend_existing': True}
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    dependence_id = Column(Integer, ForeignKey('dependence_packages.dependence_id'), nullable=False)
    file_id = Column(Integer, ForeignKey('file_dependence.file_id'), nullable=False)
    type = Column(Integer, nullable=False)
    append_or_replace = Column(Integer, nullable=False)
    start_line_number = Column(Integer, nullable=False)
    end_line_number = Column(Integer, nullable=False)
    suggestion = Column(Text, nullable=False)
    code_too_long = Column(Integer)
    code = Column(Text)
    created_at = Column(DateTime, default=datetime.now)

    @staticmethod
    def get_ai_suggestion_data(user_id, task_id, dir_id, file_id, change_id, dependence_id):
        """
        根据用户ID、任务ID、目录ID、文件ID、变更ID和依赖ID查询AI建议数据

        Args:
            user_id: 用户ID
            task_id: 任务ID
            dir_id: 目录ID
            file_id: 文件ID
            change_id: 变更ID（FileDependenceSuggestion.id）
            dependence_id: 依赖ID

        Returns:
            tuple or None: 成功返回 (task_name, file_path, suggestion_type, start_line_number, end_line_number, suggestion) 元组，
                          如果未找到或发生错误则返回 None
        """
        try:
            with db_session_scope() as session:

                # 使用 ORM 查询，从 CodemigTaskDependence 开始
                result = session.query(
                    CodemigTasks.task_name,
                    FileDependence.file_path,
                    FileDependenceSuggestion.type.label('suggestion_type'),
                    FileDependenceSuggestion.start_line_number,
                    FileDependenceSuggestion.end_line_number,
                    FileDependenceSuggestion.suggestion
                ).select_from(
                    CodemigTaskDependence
                ).join(
                    FileDependence,
                    CodemigTaskDependence.dependence_id == FileDependence.dependence_id
                ).join(
                    FileDependenceSuggestion,
                    (FileDependence.dependence_id == FileDependenceSuggestion.dependence_id) &
                    (FileDependence.file_id == FileDependenceSuggestion.file_id)
                ).join(
                    CodemigTasks,
                    CodemigTasks.task_id == CodemigTaskDependence.task_id
                ).filter(
                    CodemigTaskDependence.user_id == user_id,
                    CodemigTaskDependence.task_id == task_id,
                    CodemigTaskDependence.dir_id == dir_id,
                    FileDependenceSuggestion.file_id == file_id,
                    FileDependenceSuggestion.id == change_id,
                    FileDependence.dependence_id == dependence_id,
                    FileDependence.type == 0
                ).first()

                if result:
                    return (
                        result.task_name,
                        result.file_path,
                        result.suggestion_type,
                        result.start_line_number,
                        result.end_line_number,
                        result.suggestion
                    )
                return None
        except (DatabaseException, OSError, IOError) as err:
            LOGGER.error("Database operation failed: %s", err)
            return None

    @staticmethod
    def get_all_ai_suggestion_data(user_id, task_id, dir_id, file_id, dependence_id):
        """
        根据用户ID、任务ID、目录ID、文件ID和依赖ID查询所有AI建议数据（不包含change_id条件）

        Args:
            user_id: 用户ID
            task_id: 任务ID
            dir_id: 目录ID
            file_id: 文件ID
            dependence_id: 依赖ID

        Returns:
            list: 成功返回 (task_name, file_path, suggestion_type, start_line_number, end_line_number, suggestion) 元组列表，
                 如果未找到或发生错误则返回空列表
        """
        try:
            with db_session_scope() as session:

                # 使用 ORM 查询，从 CodemigTaskDependence 开始
                results = session.query(
                    CodemigTasks.task_name,
                    FileDependence.file_path,
                    FileDependenceSuggestion.type.label('suggestion_type'),
                    FileDependenceSuggestion.start_line_number,
                    FileDependenceSuggestion.end_line_number,
                    FileDependenceSuggestion.suggestion
                ).select_from(
                    CodemigTaskDependence
                ).join(
                    FileDependence,
                    CodemigTaskDependence.dependence_id == FileDependence.dependence_id
                ).join(
                    FileDependenceSuggestion,
                    (FileDependence.dependence_id == FileDependenceSuggestion.dependence_id) &
                    (FileDependence.file_id == FileDependenceSuggestion.file_id)
                ).join(
                    CodemigTasks,
                    CodemigTasks.task_id == CodemigTaskDependence.task_id
                ).filter(
                    CodemigTaskDependence.user_id == user_id,
                    CodemigTaskDependence.task_id == task_id,
                    CodemigTaskDependence.dir_id == dir_id,
                    FileDependenceSuggestion.file_id == file_id,
                    FileDependence.dependence_id == dependence_id,
                    FileDependence.type == 0
                ).all()

                return [
                    (
                        result.task_name,
                        result.file_path,
                        result.suggestion_type,
                        result.start_line_number,
                        result.end_line_number,
                        result.suggestion
                    )
                    for result in results
                ]
        except (DatabaseException, OSError, IOError) as err:
            LOGGER.error("Database operation failed: %s", err)
            return []


class SoftwareDependenceSuggestion(Base):
    """
    软件依赖建议 ORM 类
    对应数据库表: software_dependence_suggestion
    """
    __tablename__ = 'software_dependence_suggestion'
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, autoincrement=True)
    dependence_id = Column(Integer, ForeignKey('dependence_packages.dependence_id'))
    file_id = Column(Integer, ForeignKey('file_dependence.file_id'), nullable=False)
    support_architecture = Column(Text, nullable=False)
    suggestion = Column(Text)
    created_at = Column(DateTime, default=datetime.now)


class DependenceExistingArchitecture(Base):
    """
    依赖现有架构 ORM 类
    对应数据库表: dependence_existing_architecture
    architecture_path: 缺失文件对应的其他架构路径，例如缺失file_riscv64.go文件对应file_arm64.go文件
    """
    __tablename__ = 'dependence_existing_architecture'
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, autoincrement=True)
    dependence_id = Column(Integer, ForeignKey('dependence_packages.dependence_id'))
    file_id = Column(Integer, ForeignKey('file_dependence.file_id'), nullable=False)
    architecture_path = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.now)
    type = Column(Integer, default=0)


class DependenceTask(Base):
    """
    依赖任务 ORM 类
    对应数据库表: dependence_task
    注意：该表在 SQL 中没有定义主键，这里使用复合主键 (task_id, dir_id, pkg)
    """
    __tablename__ = 'dependence_task'
    __table_args__ = {'extend_existing': True}

    task_id = Column(Integer, ForeignKey('codemig_tasks.task_id'), primary_key=True)
    dir_id = Column(Integer, ForeignKey('codemig_task_directory.dir_id'), primary_key=True)
    pkg = Column(Text, nullable=False, primary_key=True)
    version = Column(Text)
    local_path = Column(Text)
    status = Column(Integer, default=0)
    dependence_id = Column(Integer, ForeignKey('dependence_packages.dependence_id'))

    @staticmethod
    def bulk_insert_tasks(task_data_list):
        """
        批量插入依赖任务

        Args:
            task_data_list: 任务数据列表，每个元素可以是：
                - (task_id, dir_id, pkg, version) 元组（Python 依赖，local_path 为 None）
                - (task_id, dir_id, pkg, version, local_path) 元组（Go 依赖）

        Returns:
            tuple: (success: bool, count: int) 成功返回 (True, 插入数量)，失败返回 (False, 0)
        """
        try:
            with db_session_scope() as session:
                insert_objects = []
                for task_data in task_data_list:
                    if len(task_data) == 4:
                        # Python 依赖：没有 local_path
                        task_id, dir_id, pkg, version = task_data
                        local_path = None
                    else:
                        # Go 依赖：有 local_path
                        task_id, dir_id, pkg, version, local_path = task_data

                    insert_objects.append(
                        DependenceTask(
                            task_id=task_id,
                            dir_id=dir_id,
                            pkg=pkg,
                            version=version,
                            local_path=local_path
                        )
                    )

                session.bulk_save_objects(insert_objects)
                # 事务会在 db_session_scope 退出时自动提交
                return True, len(insert_objects)
        except (DatabaseException, OSError, IOError) as err:
            LOGGER.error(f"Bulk insert dependence tasks error: {str(err)}")
            return False, 0

    @staticmethod
    def update_task_status(task_id, dir_id, package, version, status, dependence_id):
        """
        更新依赖任务状态

        Args:
            task_id: 任务ID
            dir_id: 目录ID
            package: 包名
            version: 版本号
            status: 状态值（通常是枚举的 value）
            dependence_id: 依赖ID

        Returns:
            bool: 更新成功返回 True，失败返回 False
        """
        try:
            with db_session_scope() as session:
                # 如果 status 是枚举类型，获取其 value
                status_value = status.value if hasattr(status, 'value') else status

                result = session.query(DependenceTask).filter(
                    DependenceTask.task_id == task_id,
                    DependenceTask.dir_id == dir_id,
                    DependenceTask.pkg == package,
                    DependenceTask.version == version
                ).update({
                    DependenceTask.status: status_value,
                    DependenceTask.dependence_id: dependence_id
                })

                return result > 0

        except (DatabaseException, OSError, IOError) as e:
            LOGGER.error(f"update {package}:{version} error of db error: {str(e)}")
            return False

    @staticmethod
    def delete_by_task_id(task_id):
        """
        根据任务ID删除所有依赖任务

        Args:
            task_id: 任务ID

        Returns:
            bool: 删除成功返回 True，失败返回 False
        """
        try:
            with db_session_scope() as session:
                result = session.query(DependenceTask).filter(
                    DependenceTask.task_id == task_id
                ).delete()

                return True

        except (DatabaseException, OSError, IOError) as e:
            LOGGER.error(f"Database delete dependence task failed: {str(e)}")
            return False

    @staticmethod
    def get_packages_by_task_ids(task_ids):
        """
        根据多个任务ID查询依赖任务包信息

        Args:
            task_ids: 任务ID列表

        Returns:
            list or None: 成功返回 (task_id, dir_id, pkg, version, local_path, status, dependence_id) 元组列表，
                         失败返回 None
        """
        if not task_ids:
            return []

        try:
            with db_session_scope() as session:
                results = session.query(DependenceTask).filter(
                    DependenceTask.task_id.in_(task_ids)
                ).all()

                # 返回格式与原始 SQL 查询一致：(task_id, dir_id, pkg, version, local_path, status, dependence_id)
                return [
                    (result.task_id, result.dir_id, result.pkg, result.version,
                     result.local_path, result.status, result.dependence_id)
                    for result in results
                ]

        except (DatabaseException, OSError, IOError) as e:
            LOGGER.error(f"get dep task pkg from db error: {str(e)}")
            return None
