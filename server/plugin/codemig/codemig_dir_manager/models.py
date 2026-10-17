"""
Codemig 目录管理 ORM 模型
对应数据库表: codemig_directory_storage
"""
import os
import sys
from datetime import datetime, timedelta
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, CheckConstraint, func, text

MODULE_PATH = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if MODULE_PATH not in sys.path:
    sys.path.append(MODULE_PATH)
from common.db.SQLOperation import Base, DatabaseException, db_session_scope


class CodemigDirectoryStorage(Base):
    """
    目录存储 ORM 类
    对应数据库表: codemig_directory_storage
    """
    __tablename__ = 'codemig_directory_storage'
    __table_args__ = (
        CheckConstraint('has_linked_task IN (0, 1)',
                        name='ck_codemig_directory_storage_has_linked_task'),
        CheckConstraint('has_removed IN (0, 1)', name='ck_codemig_directory_storage_has_removed'),
        {'extend_existing': True}
    )

    user_id = Column(String(64), nullable=False)
    dir_id = Column(Integer, primary_key=True, autoincrement=True)
    has_linked_task = Column(Integer, nullable=False, default=0)
    has_removed = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=datetime.now)

    @staticmethod
    def insert_directory(user_id):
        """
        插入目录记录

        Args:
            user_id: 用户ID

        Returns:
            int or None: 成功时返回 dir_id，失败时返回 None
        """
        try:
            with db_session_scope() as session:
                new_directory = CodemigDirectoryStorage(
                    user_id=user_id,
                    has_linked_task=0,
                    has_removed=0
                )
                session.add(new_directory)
                session.flush()  # 获取自增ID
                dir_id = new_directory.dir_id
                # db_session_scope 会自动提交

                return dir_id

        except (DatabaseException, OSError, IOError) as e:
            return None

    @staticmethod
    def mark_as_removed(dir_id):
        """
        标记目录为已删除（软删除）

        Args:
            dir_id: 目录ID

        Returns:
            bool: 成功时返回 True，失败时返回 False
        """
        try:
            with db_session_scope() as session:
                directory = session.query(CodemigDirectoryStorage).filter(
                    CodemigDirectoryStorage.dir_id == dir_id
                ).first()

                if not directory:
                    return False

                directory.has_removed = 1
                # db_session_scope 会自动提交

                return True

        except (DatabaseException, OSError, IOError) as e:
            return False

    @staticmethod
    def get_removed_directories(session=None):
        """
        获取已标记为删除的目录信息（包含用户名）
        
        Args:
            session: 可选的数据库会话，如果提供则使用该会话，否则创建新会话
        
        Returns:
            list: 返回 (dir_id, user_name) 元组列表，失败返回 None
        """
        try:
            if session is None:
                with db_session_scope() as session:
                    return CodemigDirectoryStorage._get_removed_directories_internal(session)
            else:
                return CodemigDirectoryStorage._get_removed_directories_internal(session)
        except (DatabaseException, OSError, IOError) as e:
            return None

    @staticmethod
    def _get_removed_directories_internal(session):
        """内部方法：获取已删除目录"""
        # 使用原始 SQL 查询，因为需要 JOIN user_manager 表
        # 如果 user_manager 有 ORM 类，可以使用 join
        result = session.execute(
            text(
                """
                SELECT ds.dir_id, u.user_name 
                FROM codemig_directory_storage ds 
                LEFT JOIN user_manager u ON ds.user_id = u.user_id 
                WHERE ds.has_removed = 1 
                ORDER BY ds.dir_id ASC
                """
            )
        )
        return [(row[0], row[1]) for row in result.fetchall()]

    @staticmethod
    def get_no_link_directories(session=None):
        """
        获取未关联任务且创建时间超过30天的目录信息（包含用户名）
        
        Args:
            session: 可选的数据库会话，如果提供则使用该会话，否则创建新会话
        
        Returns:
            list: 返回 (dir_id, user_name) 元组列表，失败返回 None
        """
        try:
            if session is None:
                with db_session_scope() as session:
                    return CodemigDirectoryStorage._get_no_link_directories_internal(session)
            else:
                return CodemigDirectoryStorage._get_no_link_directories_internal(session)
        except (DatabaseException, OSError, IOError) as e:
            return None

    @staticmethod
    def _get_no_link_directories_internal(session):
        """内部方法：获取未关联任务的目录"""
        # 使用原始 SQL 查询，因为需要 JOIN user_manager 表和日期计算
        result = session.execute(
            text(
                """
                SELECT ds.dir_id, u.user_name 
                FROM codemig_directory_storage ds 
                LEFT JOIN user_manager u ON ds.user_id = u.user_id 
                WHERE ds.has_linked_task = 0 
                AND ds.created_at < datetime('now', '-30 days')
                ORDER BY ds.dir_id ASC
                """
            )
        )
        return [(row[0], row[1]) for row in result.fetchall()]
