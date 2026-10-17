import os
import re
import sys

from sqlalchemy import Column, Integer, String

MODULE_PATH = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..'))
if MODULE_PATH not in sys.path:
    sys.path.append(MODULE_PATH)

from common.public import logger
from common.response.response_code import ResponseCode
from common.db.SQLOperation import Base, db_session_scope, DatabaseException

LOGGER = logger.init_log('usermanager')


# ORM 模型：弱密码表
class WeakPwd(Base):
    """弱密码表"""
    __tablename__ = 'weakpassword'

    id = Column(Integer, primary_key=True, autoincrement=True)
    weak_password = Column(String(100), nullable=False)

    @staticmethod
    def list_weak_pw():
        """
        列出所有弱密码

        Returns:
            tuple: (成功标志, 弱密码列表, 错误代码)
        """
        weak_pwd = []
        try:
            with db_session_scope() as session:
                results = session.query(WeakPwd).order_by(WeakPwd.id).all()
                weak_pwd = [{'id': item.id, 'weak_password': item.weak_password} for item in
                            results]
                return True, weak_pwd, None
        except (DatabaseException, OSError, IOError, RuntimeError) as err:
            LOGGER.error(f'query weak p... error! {err}')
            return False, weak_pwd, ResponseCode.DB_EXCEPTION

    @staticmethod
    def insert(weak_password):
        """
        插入弱密码

        Args:
            weak_password: 弱密码字符串

        Returns:
            tuple: (成功标志, 响应代码)
        """
        if not WeakPwd._validate_weak_password(weak_password):
            return False, ResponseCode.WEAKPWD_INVALID

        try:
            with db_session_scope() as session:
                # 检查是否已存在
                if WeakPwd._weak_passsword_exist(session, weak_password):
                    return False, ResponseCode.EXIST

                # 插入新记录
                new_weak_pwd = WeakPwd(weak_password=weak_password)
                session.add(new_weak_pwd)
                return True, ResponseCode.OK
        except (DatabaseException, OSError, IOError, RuntimeError) as err:
            LOGGER.error(f'insert weak p..  data error!{err}')
            return False, ResponseCode.DB_EXCEPTION

    @staticmethod
    def is_weak_passsword(weak_password):
        """
        检查密码是否为弱密码

        Args:
            weak_password: 要检查的密码

        Returns:
            bool: 如果是弱密码返回 True，否则返回 False
        """
        try:
            with db_session_scope() as session:
                return WeakPwd._weak_passsword_exist(session, weak_password)
        except (DatabaseException, OSError, IOError, RuntimeError) as err:
            LOGGER.error(f'query weak p..  data error! {err}')
            return False

    @staticmethod
    def _weak_passsword_exist(session, weak_password):
        """
        检查弱密码是否存在

        Args:
            weak_password: 要检查的弱密码
            session: 数据库会话对象（如果为 None，则创建新会话）

        Returns:
            bool: 如果存在返回 True，否则返回 False
        """

        result = session.query(WeakPwd).filter(
            WeakPwd.weak_password == weak_password).first()
        return result is not None

    @staticmethod
    def _validate_weak_password(weak_password):
        """
        验证弱密码格式是否有效

        Args:
            weak_password: 要验证的弱密码

        Returns:
            bool: 如果格式有效返回 True，否则返回 False
        """
        if not isinstance(weak_password, str):
            return False
        regex = ('^(?=.*[a-z])(?=.*[A-Z])(?=.*[0-9]|.*[`~!@#$%^&*()\\-_=+\\\\|[{}];:\'",<.>/?])'
                 '[A-Za-z0-9`~!@#$%^&*()\\-_=+\\\\|[{};:\'",<.>/?]{8,32}$')

        return bool(re.match(regex, weak_password))
