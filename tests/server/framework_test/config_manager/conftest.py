"""共享 fixture。"""
import os
import tempfile
import sqlite3

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session

from common.db import SQLOperation as sql_op
from common.db.SQLOperation import DB_INFO, Base
from common.db.SQLOperation import engine as global_engine


@pytest.fixture
def mock_db_file():
    """
    创建测试数据库文件并设置数据库环境。

    Yields:
        str: 测试数据库文件路径
    """
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as test_db_file:
        db_path = test_db_file.name

    old_file = DB_INFO.file
    old_env_uri = os.environ.get('SQLITE_DATABASE_URI')
    original_engine = sql_op.engine
    original_session = sql_op.db_session
    new_engine = None

    try:
        if hasattr(sql_op, 'engine'):
            global_engine.dispose()

        new_engine = create_engine(
            f"sqlite:///{db_path}",
            echo=False,
            pool_pre_ping=True,
            connect_args={'check_same_thread': False}
        )

        new_session_local = sessionmaker(bind=new_engine, autocommit=False, autoflush=False)
        new_db_session = scoped_session(new_session_local)

        sql_op.engine = new_engine
        sql_op.db_session = new_db_session

        Base.metadata.create_all(bind=new_engine)

        sql_file = os.path.realpath(
            os.path.join(os.path.dirname(__file__), '..', '..', '..', '..',
                         'scripts', 'install', 'sqlite.sql'))
        try:
            with open(sql_file, "r") as f:
                sql = f.read()
            conn = sqlite3.connect(db_path)
            try:
                conn.executescript(sql)
                conn.commit()
            finally:
                conn.close()
        except Exception:
            pass

        os.environ['SQLITE_DATABASE_URI'] = f'sqlite:///{db_path}'

        yield db_path

    finally:
        sql_op.engine = original_engine
        sql_op.db_session = original_session
        if hasattr(sql_op, 'engine') and new_engine:
            new_engine.dispose()

        if old_env_uri is not None:
            os.environ['SQLITE_DATABASE_URI'] = old_env_uri
        elif 'SQLITE_DATABASE_URI' in os.environ:
            del os.environ['SQLITE_DATABASE_URI']

        if os.path.exists(db_path):
            os.remove(db_path)
