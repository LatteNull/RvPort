"""
Codemig 配置 ORM 模型
对应数据库表: user_configuration
"""
import os
import sys

from datetime import datetime
from common.db.SQLOperation import Base, DatabaseException, db_session_scope
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey

MODULE_PATH = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if MODULE_PATH not in sys.path:
    sys.path.append(MODULE_PATH)


class UserConfiguration(Base):
    """
    用户配置 ORM 类
    对应数据库表: user_configuration
    """
    __tablename__ = 'user_configuration'
    __table_args__ = {'extend_existing': True}

    user_id = Column(String(64), nullable=False)
    configuration_id = Column(Integer, primary_key=True, autoincrement=True)
    python_interpreter = Column(String)
    python_image_source = Column(String)
    go_install_path = Column(String)
    go_environment = Column(String)
    create_at = Column(DateTime, default=datetime.now)

    @staticmethod
    def query_user_configuration(user_id):
        """
        查询用户配置
        
        Args:
            user_id: 用户ID
            
        Returns:
            tuple: (status, configuration)
                status: True 表示成功，False 表示失败
                configuration: 成功时返回配置元组 (user_id, configuration_id, python_interpreter, 
                               python_image_source, go_install_path, go_environment)，失败时返回 None
        """
        try:
            with db_session_scope() as session:
                config = session.query(UserConfiguration).filter(
                    UserConfiguration.user_id == user_id
                ).first()
                
                if not config:
                    return True, None
                
                # 返回与原始 SQL 查询相同的格式
                configuration = (
                    config.user_id,
                    config.configuration_id,
                    config.python_interpreter,
                    config.python_image_source,
                    config.go_install_path,
                    config.go_environment
                )
                
                return True, configuration

        except (DatabaseException, OSError, IOError) as e:
            return False, None

