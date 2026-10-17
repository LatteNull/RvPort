"""
AI Assistant ORM 模型
对应数据库表: user_api_key, user_model_selection, user_default_selection
"""
import os
import sys

from datetime import datetime
from common.db.SQLOperation import Base, DatabaseException, db_session_scope
from common.public import logger
from common.public.common import decrypt_passphrase
from framework.user_manager.user_db import UserManager
from sqlalchemy import Column, Integer, String, DateTime, Boolean, UniqueConstraint, LargeBinary, case

LOGGER = logger.init_log('aiModels')

MODULE_PATH = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if MODULE_PATH not in sys.path:
    sys.path.append(MODULE_PATH)


class UserApiKey(Base):
    """
    API Key ORM 类
    对应数据库表: user_api_key

    注意：is_default 列不再作为全局默认使用（保留列避免迁移）。
    默认机制已迁移至 UserDefaultSelection 表，每个用户独立设置自己的默认 API Key。
    """
    __tablename__ = 'user_api_key'
    __table_args__ = (
            UniqueConstraint('api_key', 'model', 'user_id', name='uk_user_api_key_api_key_model_user'),
            {'extend_existing': True}
    )

    api_key_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(64), nullable=False)
    api_key = Column(LargeBinary, nullable=False)
    base_url = Column(String(255), default="")
    model = Column(String(64), default="")
    api_format = Column(String(64), default="")
    create_time = Column(DateTime, default=datetime.now)
    others = Column(String(255), default="")
    is_default = Column(Boolean, default=False)  # 保留但不再使用，默认逻辑见 UserDefaultSelection

    @staticmethod
    def _get_admin_user_ids(session):
        """获取所有 admin 角色用户的 user_id 集合"""
        admins = session.query(UserManager).filter(
            UserManager.role == 'admin'
        ).all()
        admin_ids = {u.user_id for u in admins if u.user_id is not None}
        admin_ids_str = {str(uid) for uid in admin_ids}
        return admin_ids.union(admin_ids_str)

    @staticmethod
    def del_api_key(user_id, api_key_id, is_admin=False):
        try:
            with db_session_scope() as session:
                # 先按 api_key_id 查询
                api_key = session.query(UserApiKey).filter(
                    UserApiKey.api_key_id == api_key_id
                ).first()

                if not api_key:
                    return -2

                # admin 可以删除任意 key
                if not is_admin:
                    # 普通用户：只能删除自己的 key，不能删除 admin 的 key
                    if str(api_key.user_id) != str(user_id):
                        # 检查该 key 是否属于 admin
                        admin_ids = UserApiKey._get_admin_user_ids(session)
                        if str(api_key.user_id) in admin_ids:
                            return -3  # 无权限删除 admin 的 key
                        return -3  # 不能删除其他用户的 key

                # 级联清理：删除引用此 key 的用户选中记录和用户默认记录，避免悬空引用
                session.query(UserModelSelection).filter(
                    UserModelSelection.api_key_id == api_key_id
                ).delete(synchronize_session=False)

                session.query(UserDefaultSelection).filter(
                    UserDefaultSelection.api_key_id == api_key_id
                ).delete(synchronize_session=False)

                session.delete(api_key)

            return 0

        except (DatabaseException, OSError, IOError) as e:
            return -1

    @staticmethod
    def store(user_id, encrypted_api_key, base_url, model, api_format, others, is_default):
        try:
            with db_session_scope() as session:
                # 使用 ORM 创建新记录
                new_api_key = UserApiKey(
                    user_id=user_id,
                    api_key=encrypted_api_key,
                    base_url=base_url,
                    model=model,
                    api_format=api_format,
                    others=others,
                    is_default=is_default  # 保留列写，但不再作为全局默认使用
                )
                session.add(new_api_key)
                session.flush()  # 获取自增ID
                api_key_id = new_api_key.api_key_id

                # 如果标记为默认，同步写入 UserDefaultSelection（按用户隔离）
                if is_default:
                    uid = str(user_id) if user_id is not None else None
                    if uid is not None:
                        existing = session.query(UserDefaultSelection).filter(
                            UserDefaultSelection.user_id == uid
                        ).first()
                        if existing:
                            existing.api_key_id = api_key_id
                        else:
                            session.add(UserDefaultSelection(
                                user_id=uid,
                                api_key_id=api_key_id
                            ))

            return 0, api_key_id
        except DatabaseException as e:
            # 捕获唯一约束冲突（重复插入）
            error_msg = str(e)
            if 'UNIQUE' in error_msg or 'unique' in error_msg.lower():
                return  -2, None
            else:
                return  -1,None
        except (OSError, IOError) as e:

            return -1,None

    @staticmethod
    def get_agent_config(agent_model, user_id=None, is_admin=False):
        """
        按 model 查找 AI 调用用的 API Key 配置。
        候选范围：
          - admin：全部记录
          - 普通用户：自己的 + admin 的（不含其他普通用户）
        选取优先级（从高到低，逐项排序后取第一条）：
          1. 手动选中：该用户在 user_model_selection 中对该 model 选中的 api_key_id
          2. 用户默认：该用户在 user_default_selection 中设置的默认 api_key_id（按用户隔离）
          3. 属于自己：user_id 与当前用户一致的记录（同优先级下，自己的优先于 admin 的）
          4. 主键升序：以上均相同时，按创建顺序取靠前
        """
        try:
            with db_session_scope() as session:
                query = session.query(UserApiKey).filter(
                    UserApiKey.model == agent_model
                )

                if not is_admin:
                    admin_ids = UserApiKey._get_admin_user_ids(session)
                    allowed_ids = set()
                    if user_id is not None:
                        allowed_ids.add(user_id)
                        allowed_ids.add(str(user_id))
                    allowed_ids = allowed_ids.union(admin_ids)
                    query = query.filter(UserApiKey.user_id.in_(list(allowed_ids)))

                    # 该用户在该 model 下手动选中的 api_key_id（严格按用户隔离）
                    selected_api_key_id = None
                    if user_id is not None:
                        sel = session.query(UserModelSelection).filter(
                            UserModelSelection.user_id == str(user_id),
                            UserModelSelection.model == agent_model
                        ).first()
                        if sel:
                            selected_api_key_id = sel.api_key_id

                    # 该用户设置的默认 api_key_id（按用户隔离，替代全局 is_default）
                    user_default_api_key_id = None
                    if user_id is not None:
                        default_sel = session.query(UserDefaultSelection).filter(
                            UserDefaultSelection.user_id == str(user_id)
                        ).first()
                        if default_sel:
                            user_default_api_key_id = default_sel.api_key_id

                    # 排序优先级：手动选中 > 用户默认 > 属于自己 > 主键升序
                    order_clauses = []

                    if selected_api_key_id is not None:
                        selected_flag = case(
                            (UserApiKey.api_key_id == selected_api_key_id, 1),
                            else_=0
                        )
                        order_clauses.append(selected_flag.desc())

                    if user_default_api_key_id is not None:
                        user_default_flag = case(
                            (UserApiKey.api_key_id == user_default_api_key_id, 1),
                            else_=0
                        )
                        order_clauses.append(user_default_flag.desc())

                    if user_id is not None:
                        own_flag = case(
                            (UserApiKey.user_id == user_id, 1),
                            else_=0
                        )
                        order_clauses.append(own_flag.desc())

                    order_clauses.append(UserApiKey.api_key_id.asc())

                    query = query.order_by(*order_clauses)
                else:
                    query = query.order_by(
                        UserApiKey.api_key_id.asc()
                    )

                api_key_record = query.first()

                if not api_key_record:
                    return -2, None

                # 解密 API Key
                api_key = decrypt_passphrase(api_key_record.api_key)

                agent_config = {
                    "api_key": api_key,
                    "base_url": api_key_record.base_url,
                    "model": api_key_record.model
                }

                return 0, agent_config

        except (DatabaseException, OSError, IOError) as e:
            LOGGER.error(f"get_agent_config exception: {type(e).__name__}: {e}", exc_info=True)
            return -1, None

    @staticmethod
    def get_all_api_keys(user_id=None, is_admin=False):
        """
        获取 API Key 列表
        - admin: 返回所有人的 key
        - 普通用户: 返回自己的 + admin 的 key
        """
        try:
            with db_session_scope() as session:
                # 使用 ORM 查询记录
                query = session.query(UserApiKey)

                # admin 角色用户集合
                admin_ids = UserApiKey._get_admin_user_ids(session)

                if not is_admin:
                    # 普通用户：只能看到自己的和 admin 的 key
                    # 收集允许查看的 user_id 集合：自己 + 所有 admin
                    allowed_ids = set()
                    if user_id is not None:
                        allowed_ids.add(user_id)
                        allowed_ids.add(str(user_id))
                    allowed_ids = allowed_ids.union(admin_ids)

                    if allowed_ids:
                        query = query.filter(UserApiKey.user_id.in_(list(allowed_ids)))
                    else:
                        query = query.filter(UserApiKey.user_id == '__no_match__')

                api_keys = query.all()

                # 批量获取 user_name，避免在 session 内再嵌套打开 db_session_scope()
                user_ids = [r.user_id for r in api_keys]
                user_id_keys = {uid for uid in user_ids if uid is not None}
                # 兼容 user_id 字段可能是 str/int 的情况
                user_id_keys_str = {str(uid) for uid in user_id_keys}
                lookup_keys = list(user_id_keys.union(user_id_keys_str))
                user_name_map = {}
                if lookup_keys:
                    users = session.query(UserManager).filter(
                        UserManager.user_id.in_(lookup_keys)
                    ).all()
                    for u in users:
                        # 同时用原值和字符串值做映射，提升命中率
                        if getattr(u, "user_id", None) is not None:
                            user_name_map[u.user_id] = u.user_name or ""
                            user_name_map[str(u.user_id)] = u.user_name or ""

                # 查询当前用户在 user_model_selection 中的选中记录（严格按用户隔离）
                # 构建 {model: api_key_id} 映射，用于判断每条 key 是否被当前用户选中
                user_selection_map = {}
                # 查询当前用户在 user_default_selection 中的默认 api_key_id（按用户隔离）
                user_default_api_key_id = None
                if user_id is not None:
                    selections = session.query(UserModelSelection).filter(
                        UserModelSelection.user_id == str(user_id)
                    ).all()
                    user_selection_map = {s.model: s.api_key_id for s in selections}

                    default_sel = session.query(UserDefaultSelection).filter(
                        UserDefaultSelection.user_id == str(user_id)
                    ).first()
                    if default_sel:
                        user_default_api_key_id = default_sel.api_key_id

                apikey_list = []
                for api_key_record in api_keys:
                    row_dict = {
                        'api_key_id': api_key_record.api_key_id,
                        'user_id': api_key_record.user_id,
                        'base_url': api_key_record.base_url,
                        'user_name': user_name_map.get(api_key_record.user_id, user_name_map.get(str(api_key_record.user_id), "")),
                        'model': api_key_record.model,
                        'create_time': api_key_record.create_time.strftime("%Y-%m-%d %H:%M:%S") if api_key_record.create_time else None,
                        'api_format': api_key_record.api_format,
                        'others': api_key_record.others,
                        'is_default': user_default_api_key_id == api_key_record.api_key_id,
                        'is_model_default': user_selection_map.get(api_key_record.model) == api_key_record.api_key_id
                    }

                    # 解密 API Key 并取前8位
                    if api_key_record.api_key:
                        try:
                            decrypted_api_key = decrypt_passphrase(api_key_record.api_key)
                            if decrypted_api_key:
                                row_dict['api_key'] = decrypted_api_key[:8]
                            else:
                                row_dict['api_key'] = ''
                        except (UnicodeDecodeError, OSError, AttributeError, MemoryError):
                            row_dict['api_key'] = ''
                    else:
                        row_dict['api_key'] = ''

                    apikey_list.append(row_dict)

                return 0, apikey_list

        except (DatabaseException, OSError, IOError) as e:
            return -1, None

    @staticmethod
    def set_default_api_key(api_key_id, user_id=None, is_admin=False):
        """
        设置当前用户的默认 API Key（按用户隔离，替代全局 is_default）。
        - 每个用户只能设置一个默认 api_key，记录在 user_default_selection 表。
        - 普通用户只能把可见范围内的 key（自己的 + admin 的）设为默认，禁止操作其他普通用户的 key。
        """
        try:
            with db_session_scope() as session:
                # 检查api_key_id是否存在
                api_key = session.query(UserApiKey).filter(
                    UserApiKey.api_key_id == api_key_id
                ).first()

                if not api_key:
                    return -4

                # 普通用户：只能操作可见范围内的 key（自己的 + admin 的），禁止操作其他普通用户的
                if not is_admin and str(api_key.user_id) != str(user_id):
                    admin_ids = UserApiKey._get_admin_user_ids(session)
                    if str(api_key.user_id) not in admin_ids:
                        return -3  # 不能把其他普通用户的 key 设为默认

                uid = str(user_id) if user_id is not None else None
                if uid is None:
                    return -3

                # upsert：该用户的默认 api_key 唯一，存在则更新 api_key_id，不存在则插入
                existing = session.query(UserDefaultSelection).filter(
                    UserDefaultSelection.user_id == uid
                ).first()
                if existing:
                    existing.api_key_id = api_key_id
                else:
                    session.add(UserDefaultSelection(
                        user_id=uid,
                        api_key_id=api_key_id
                    ))

            return 0

        except (DatabaseException, OSError, IOError) as e:
            return -1

    @staticmethod
    def set_model_default_api_key(api_key_id, user_id=None, is_admin=False):
        """
        将指定 API Key 设置为「该用户在该 model 下的选中项」。
        通过独立的 user_model_selection 表实现严格按用户隔离：
        - 普通用户 A 选中 admin 的共享 key，不影响 admin 和其他用户的视图。
        - 每个用户对每个 model 最多一条选中记录（user_id + model 唯一）。
        - 普通用户只能选自己可见范围内的 key（自己的 + admin 的），不能选其他普通用户的。
        """
        try:
            with db_session_scope() as session:
                # 检查目标记录是否存在
                api_key = session.query(UserApiKey).filter(
                    UserApiKey.api_key_id == api_key_id
                ).first()

                if not api_key:
                    return -4

                # 普通用户：只能选自己可见范围内的 key（自己的 + admin 的），禁止选其他普通用户的
                if not is_admin and str(api_key.user_id) != str(user_id):
                    admin_ids = UserApiKey._get_admin_user_ids(session)
                    if str(api_key.user_id) not in admin_ids:
                        return -3  # 不能选其他普通用户的 key

                target_model = api_key.model
                uid = str(user_id) if user_id is not None else None
                if uid is None:
                    return -3

                # upsert：该用户对该 model 的选中记录唯一，存在则更新 api_key_id，不存在则插入
                existing = session.query(UserModelSelection).filter(
                    UserModelSelection.user_id == uid,
                    UserModelSelection.model == target_model
                ).first()
                if existing:
                    existing.api_key_id = api_key_id
                else:
                    session.add(UserModelSelection(
                        user_id=uid,
                        model=target_model,
                        api_key_id=api_key_id
                    ))

            return 0

        except (DatabaseException, OSError, IOError) as e:
            return -1


class UserModelSelection(Base):
    """
    用户-模型选中关系表：严格按用户隔离记录"该用户在该 model 下选中哪条 api key"。
    与 UserApiKey 解耦，选中 admin 的共享 key 不会影响 admin 或其他用户的视图。
    """
    __tablename__ = 'user_model_selection'
    __table_args__ = (
            UniqueConstraint('user_id', 'model', name='uk_user_model_selection_user_model'),
            {'extend_existing': True}
    )

    selection_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(64), nullable=False)
    model = Column(String(64), nullable=False)
    api_key_id = Column(Integer, nullable=False)


class UserDefaultSelection(Base):
    """
    用户默认 API Key 选择表：每个用户可以选择一个默认的 API Key（全局 is_default 的替代）。
    按用户隔离——用户 A 设置的默认不会影响用户 B。
    每个用户最多一条记录（user_id 唯一约束）。
    """
    __tablename__ = 'user_default_selection'
    __table_args__ = (
        {'extend_existing': True}
    )

    selection_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(64), nullable=False, unique=True)
    api_key_id = Column(Integer, nullable=False)
