# 标准库导入
import difflib
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tarfile
import zipfile
from contextlib import closing
from datetime import datetime
from enum import Enum
from pathlib import Path

# 第三方库导入
import sqlcipher3

# 项目路径设置
MODULE_PATH = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if MODULE_PATH not in sys.path:
    sys.path.append(MODULE_PATH)

# 项目导入 - common 模块
from common.db.SQLOperation import get_conn
from common.public import logger
from common.public.public import get_codemig_data_path

# 项目导入 - plugin.codemig 模块
from plugin.codemig.ai_assistant.api_key_manager import sanitize_cmd_text
from plugin.codemig.codemig_common.common_sql import (
    INSERT_FILE_SQL,
    REMOVE_FILE_SQL,
    REMOVE_DIRECTORY_RECURSIVE_SQL,
    SELECT_ALL_FILE_SQL,
    SELECT_FILE_BY_PATH_SQL,
    SELECT_FILE_PATH_SQL,
    SELECT_FILE_INFO_SQL,
    SELECT_FILE_TREE_SQL,
    SELECT_MISSING_FILE_TREE_SQL,
    UPDATE_SUGGESTION_IGNORED_SQL,
    INSTER_AI_RESULT_SQL,
    UPDATE_AI_RESULT_SQL,
    SELECT_AI_SUGGESTION_SQL,
    SELECT_AI_FINISHED_SQL,
    SELECT_MAX_AI_ID_BY_FILE_SQL,
    SELECT_MAX_PROJECT_AI_ID_BY_STAGE_SQL,
    SELECT_PROJECT_AI_HISTORY_SQL,
    ALTER_TASK_AI_ADD_STAGE_SQL,
    CREATE_TASK_AI_TABLE_SQL,
    SET_AI_SCORE_SQL,
    SELECT_AI_SCORE_SQL,
    SELECT_AI_SCORE_BY_UUID_SQL,
    SELECT_RUNNING_AI_REQUEST_IDS_SQL,
    INSERT_GENERATE_FILE_SQL,
    SELECT_MISSING_FILES_NOT_GENERATED_FROM_DATABASE_SQL,
    SELECT_GENERATED_FILE_SQL,
)

LOGGER = logger.init_log('codemig')
USE_ABSOLUTE_PATH = False
NUMBER_LINES_TOO_LONG = 50
BATCH_SIZE = 1000
BEGIN_TRANSACTION = "BEGIN TRANSACTION"
TAR_GZ = '.tar.gz'
TGZ = '.tgz'
TAR = '.tar'
# 支持的压缩文件扩展名
SUPPORTED_ARCHIVES = {'.jar', '.war', '.ear', '.whl', '.egg', '.tar.gz', '.zip'}


def create_relative_file_path(file_path):
    file_path = os.path.relpath(file_path, get_codemig_data_path())
    return add_dot_slash(file_path)


def add_dot_slash(file_path):
    return f"./{file_path}"

class FileSource(Enum):
    CHANGED = "changed"
    ORIGINAL = "original"
    MISSING = "missing"
    GENERATE = "generated"

# pylint: disable=too-few-public-methods
class CodeTooLong(Enum):
    HAS_SOURCE_CODE = 0
    CODE_TOO_LONG = 1


# pylint: disable=too-few-public-methods
class ChangeType(Enum):
    APPEND = 0
    REPLACE = 1
    OTHER = 2


def matches_c_file(file_name):
    c_extensions = {".h", ".c", ".cc", ".cpp", ".h.in", ".c.in", ".hpp", ".cc.in", ".cpp.in",
                    ".hpp.in"}
    return any(file_name.endswith(ext) for ext in c_extensions)


def extract_suffix(suffixes):
    suffixes_length = len(suffixes)
    if suffixes_length >= 2 and "".join(suffixes[-2:]) == TAR_GZ:
        return TAR_GZ
    if suffixes_length >= 1:
        return suffixes[-1]
    return None


def extract_zipfile(file_path, extract_path):
    try:
        with zipfile.ZipFile(file_path, 'r') as zip_ref:
            for member in zip_ref.namelist():
                target_path = os.path.join(extract_path, member)
                # 关键修复：检查父目录是否存在且有效
                parent_dir = os.path.dirname(target_path)
                if parent_dir and not os.path.exists(parent_dir):
                    os.makedirs(parent_dir, exist_ok=True)
                elif os.path.exists(parent_dir) and not os.path.isdir(parent_dir):
                    # 处理路径冲突：重命名冲突文件
                    conflict_file = parent_dir
                    backup_path = f"{conflict_file}.backup"
                    os.rename(conflict_file, backup_path)
                    os.makedirs(parent_dir, exist_ok=True)
                    LOGGER.warning(f"Renamed conflicting file: {conflict_file} -> {backup_path}")
                # 解压文件（确保路径检查后执行）
                zip_ref.extract(member, extract_path)
        return True
    except (zipfile.BadZipFile, zipfile.LargeZipFile) as err:
        LOGGER.warning(f"Bad zip file, path: {file_path}, error: {err}.")
        return False
    except (PermissionError, FileNotFoundError, OSError, RuntimeError) as e:
        LOGGER.error(f"Error extracting the file:{file_path}, error: {str(e)}.")
        return False


def add_counter_to_extract_path(extract_path):
    old_name = extract_path.stem
    counter = 1
    while True:
        new_name = f"{old_name}_{counter}"
        new_path = extract_path.with_name(new_name)
        if not new_path.exists():
            return new_path
        counter += 1


def create_new_extract_path(root_path, file):
    time_suffix = datetime.now().strftime("%Y%m%d_%H%M%S")
    new_extract_path = root_path / f"{file.replace('.', '_')}_{time_suffix}"
    if new_extract_path.exists():
        return add_counter_to_extract_path(new_extract_path)
    return new_extract_path


def set_permissions_pathlib(target_path):
    """使用pathlib设置权限"""
    target = Path(target_path)

    if not target.exists():
        LOGGER.error(f"路径不存在: {target_path}")
        return

    current_uid = os.getuid()
    current_gid = os.getgid()
    # 首先删除所有 .git 和 .github 目录
    for dir_name in ['.git', '.github']:
        for git_dir in target.rglob(dir_name):
            if git_dir.is_dir():
                try:
                    shutil.rmtree(git_dir)
                except  (OSError, FileNotFoundError, PermissionError) as e:
                    LOGGER.error(f"删除目录失败 {git_dir}: {e}")

    def process_path(path):
        """处理单个路径"""
        try:
            # 设置所有权
            os.chown(str(path), current_uid, current_gid)

            if path.is_file() and not path.is_symlink():
                # 文件: 644权限
                path.chmod(0o644)
            elif path.is_dir() and not path.is_symlink():
                # 目录: 755权限
                path.chmod(0o755)

            return True

        except PermissionError:
            LOGGER.error(f"权限不足: {path}")
            return False
        except (OSError, FileNotFoundError) as e:
            LOGGER.error(f"处理失败 {path}: {e}")
            return False

    # 先处理文件
    for file_path in target.rglob('*'):
        process_path(file_path)

    # 处理根目录
    process_path(target)


def extract_file(file_path: Path, extract_path: Path, max_depth=None):
    # 解压文件
    # suffix = extract_suffix(file_path.suffixes)
    if tarfile.is_tarfile(file_path):
        try:
            # 自动检测压缩方式 包括无压缩、gzip、bz2、xz
            with tarfile.open(file_path, mode='r:*') as tar_ref:
                tar_ref.extractall(extract_path, filter='data')
        except (tarfile.TarError, PermissionError, FileNotFoundError, OSError, EOFError,
                RuntimeError) as e:
            LOGGER.error(f'解压{file_path}文件失败，{e}')
            return False
    elif zipfile.is_zipfile(file_path):
        status = extract_zipfile(file_path, extract_path)
        if not status:
            return False
    else:
        # 不是支持的压缩类型
        LOGGER.error(f"Error: {file_path} is not the supported file type.")
        return False
    set_permissions_pathlib(extract_path)
    if max_depth:
        max_depth -= 1
        if max_depth == 0:
            return True
    # 扫描解压后的文件
    for root, _, files in os.walk(extract_path):
        for file in files:
            file_suffix = extract_suffix(Path(file).suffixes)
            # 如果是支持的压缩文件，递归处理
            if file_suffix in SUPPORTED_ARCHIVES:
                root_path = Path(root)
                new_file_path = root_path / file
                new_extract_path = create_new_extract_path(root_path, file)
                extract_file(new_file_path, new_extract_path)
    return True


def create_new_path(file_path:str, new_part):
    relpath = Path(os.path.relpath(file_path, get_codemig_data_path()))
    path_parts = list(relpath.parts)
    path_parts[2] = new_part
    return os.path.join(get_codemig_data_path(), Path(*path_parts).as_posix())


def move_file_to_new_path(file_path, new_file_path, tree=False):
    new_dir_path = Path(new_file_path).parent
    new_dir_path.mkdir(parents=True, exist_ok=True)
    if not tree:
        shutil.copy(file_path, new_file_path)
    else:
        shutil.copytree(file_path, new_file_path)


def regex_arch(text):
    architectures = (
        r'(?<![a-zA-Z0-9])(x86(?:_64)?|amd(?:_64)?|arm(?:_64|64)?|armv8(?:_64)?|armv9(?:_64)?|'
        r'aarch64)(?![a-zA-Z0-9])')

    # 使用 re.search 进行正则匹配，flags=re.IGNORECASE确保大小写不敏感
    return bool(re.search(architectures, text, flags=re.IGNORECASE))


def regex_riscv_arch(text):
    architectures = r'(?<![a-zA-Z0-9])(riscv|riscv64|rvv|risc-v)(?![a-zA-Z0-9])'
    # 使用 re.search 进行正则匹配，flags=re.IGNORECASE确保大小写不敏感
    return bool(re.search(architectures, text, flags=re.IGNORECASE))


def load_list_from_file(file_path: str) -> list:
    res = []
    with open(file_path, 'r') as file:
        res = [line.strip() for line in file if line.strip()]
    return res

def get_database_path(user_name, dir_id) -> Path:
    db_name = str(dir_id) + ".db"
    return Path(get_codemig_data_path()) / user_name / str(dir_id) / db_name


def query_file_by_path_from_database(user_name, dir_id, file_path):
    """
    通过路径查询文件在数据库中的信息
    insert 是否插入数据库
    Returns:
        tuple: (status, file_id)
            status: True 表示成功，False 表示失败
            file_id: 文件ID
    """
    db_path = get_database_path(user_name, dir_id)
    if not db_path.exists():
        return False, None
    conn = None
    try:
        conn = get_conn(db_path)
        cursor = conn.cursor()
        cursor.execute(SELECT_FILE_BY_PATH_SQL, (file_path,))
        result = cursor.fetchone()
        return True, result[0] if result else None
    except (sqlite3.Error, sqlcipher3.dbapi2.DatabaseError) as err:
        LOGGER.error("Database operation failed: %s", err)
        return False, None
    finally:
        if conn:
            conn.close()

def query_file_tree_from_database(user_name, dir_id):
    """
    Returns:
        tuple: (status, rows)
            status: True 表示成功, False 表示失败
            rows: 文件树列表，每个元素为 (file_id, file_path, file_source, is_file)
    """
    LOGGER.info(f"Querying the file tree for user {user_name} dir_id {dir_id}.")
    db_path = get_database_path(user_name, dir_id)
    if not db_path.exists():
        return False, None
    conn = None
    try:
        conn = get_conn(db_path)
        cursor = conn.cursor()
        cursor.execute(SELECT_FILE_TREE_SQL)
        return True, cursor.fetchall()
    except (sqlite3.Error, sqlcipher3.dbapi2.DatabaseError) as err:
        LOGGER.error("Database operation failed: %s", err)
        return False, None
    finally:
        if conn:
            conn.close()


def query_missing_file_tree_from_database(user_name, dir_id):
    """
    Returns:
        tuple: (status, rows)
            status: True 表示成功, False 表示失败
            rows: 缺失文件树列表，每个元素为 (file_id, file_path, file_source, is_file)
    """
    LOGGER.info(f"Querying the missing file tree for user {user_name} dir_id {dir_id}.")
    db_path = get_database_path(user_name, dir_id)
    if not db_path.exists():
        return False, None
    conn = None
    try:
        conn = get_conn(db_path)
        cursor = conn.cursor()
        cursor.execute(SELECT_MISSING_FILE_TREE_SQL)
        return True, cursor.fetchall()
    except (sqlite3.Error, sqlcipher3.dbapi2.DatabaseError) as err:
        LOGGER.error("Database operation failed: %s", err)
        return False, None
    finally:
        if conn:
            conn.close()

def query_missing_files_not_generated_from_database(user_name, dir_id):
    LOGGER.info(f"Querying the missing files not generated from database for user {user_name} dir_id {dir_id}.")
    db_path = get_database_path(user_name, dir_id)
    if not db_path.exists():
        return False, None
    conn = None
    try:
        conn = get_conn(db_path)
        cursor = conn.cursor()
        cursor.execute(SELECT_MISSING_FILES_NOT_GENERATED_FROM_DATABASE_SQL)
        return True, cursor.fetchall()
    except (sqlite3.Error, sqlcipher3.dbapi2.DatabaseError) as err:
        LOGGER.error("Database operation failed: %s", err)
        return False, None
    finally:
        if conn:
            conn.close()


def query_generated_files_from_database(user_name, dir_id):
    """
    查询迁移生成的新增文件（file_source='generated'，type=0，未删除）。

    Returns:
        tuple: (status, rows)
            rows: [(file_id, file_path, is_file), ...]，按 file_path 排序
    """
    LOGGER.info(f"Querying the generated files for user {user_name} dir_id {dir_id}.")
    db_path = get_database_path(user_name, dir_id)
    if not db_path.exists():
        return False, None
    conn = None
    try:
        conn = get_conn(db_path)
        cursor = conn.cursor()
        cursor.execute(SELECT_GENERATED_FILE_SQL)
        return True, cursor.fetchall()
    except (sqlite3.Error, sqlcipher3.dbapi2.DatabaseError) as err:
        LOGGER.error("Database operation failed: %s", err)
        return False, None
    finally:
        if conn:
            conn.close()


def query_all_file_from_database(user_name, dir_id):
    LOGGER.info(f"Querying the file tree for user {user_name} dir_id {dir_id}.")
    db_path = get_database_path(user_name, dir_id)
    if not db_path.exists():
        return False, None
    conn = None
    try:
        conn = get_conn(db_path)
        cursor = conn.cursor()
        cursor.execute(SELECT_ALL_FILE_SQL)
        return True, cursor.fetchall()
    except (sqlite3.Error, sqlcipher3.dbapi2.DatabaseError) as err:
        LOGGER.error("Database operation failed: %s", err)
        return False, None
    finally:
        if conn:
            conn.close()

def query_file_path_from_database(user_name, dir_id, file_id):
    LOGGER.info(f"Querying the file path for file_id {file_id}.")
    db_path = get_database_path(user_name, dir_id)
    if not os.path.exists(db_path):
        return False, None
    conn = None
    try:
        conn = get_conn(db_path)
        cursor = conn.cursor()
        cursor.execute(SELECT_FILE_PATH_SQL, (file_id,))
        result = cursor.fetchone()
        return True, result[0] if result else None
    except (sqlite3.Error, sqlcipher3.dbapi2.DatabaseError) as err:
        LOGGER.error("Database operation failed: %s", err)
        return False, None
    finally:
        if conn:
            conn.close()

def query_file_info_from_database(user_name, dir_id, file_id):
    LOGGER.info(f"Querying the file path for file_id {file_id}.")
    db_path = get_database_path(user_name, dir_id)
    if not os.path.exists(db_path):
        return False, None
    conn = None
    try:
        conn = get_conn(db_path)
        cursor = conn.cursor()
        cursor.execute(SELECT_FILE_INFO_SQL, (file_id,))
        result = cursor.fetchone()
        return True, result
    except (sqlite3.Error, sqlcipher3.dbapi2.DatabaseError) as err:
        LOGGER.error("Database operation failed: %s", err)
        return False, None
    finally:
        if conn:
            conn.close()

def save_new_file_to_database(user_name, user_id, dir_id,
                             file_path:str, source:str, is_file):
    db_path = get_database_path(user_name, dir_id)
    if not db_path.exists():
        return False, None
    try:
        with closing(get_conn(db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute(INSERT_FILE_SQL, (user_id, dir_id, file_path,
                            source, is_file))
            file_id = cursor.lastrowid
            conn.commit()
            return True, file_id
    except (sqlite3.Error, sqlcipher3.dbapi2.DatabaseError) as err:
        LOGGER.error("Database operation failed: %s", err)
        return False, None

def save_generated_file_to_database(user_name, user_id, dir_id,
                             file_path:str, source:str, is_file,
                             source_file_id):
    db_path = get_database_path(user_name, dir_id)
    if not db_path.exists():
        return False, None
    try:
        with closing(get_conn(db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute(INSERT_GENERATE_FILE_SQL, (user_id, dir_id, file_path,
                            source, is_file, source_file_id))
            file_id = cursor.lastrowid
            conn.commit()
            return True, file_id
    except (sqlite3.Error, sqlcipher3.dbapi2.DatabaseError) as err:
        LOGGER.error("Database operation failed: %s", err)
        return False, None

def update_file_removed_to_database(user_name, dir_id, file_id):
    db_path = get_database_path(user_name, dir_id)
    if not db_path.exists():
        return False
    try:
        with closing(get_conn(db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute(REMOVE_FILE_SQL, (file_id,))
            conn.commit()
            return True
    except (sqlite3.Error, sqlcipher3.dbapi2.DatabaseError) as err:
        LOGGER.error("Database operation failed: %s", err)
        return False


def update_directory_removed_recursively_to_database(user_name, dir_id, file_path):
    """
    递归更新目录及其所有子目录和文件的has_removed状态为1

    Args:
        user_name: 用户名
        dir_id: 目录ID
        file_path: 要删除的目录路径

    Returns:
        bool: 操作是否成功
    """
    db_path = get_database_path(user_name, dir_id)
    if not db_path.exists():
        return False
    try:
        with closing(get_conn(db_path)) as conn:
            cursor = conn.cursor()
            # 使用 LIKE 匹配目录及其所有子文件和子目录
            # file_path LIKE 'dir_path/%' 匹配所有子文件和子目录
            # file_path = 'dir_path' 匹配目录本身
            cursor.execute(REMOVE_DIRECTORY_RECURSIVE_SQL, (file_path, file_path))
            conn.commit()
            LOGGER.info(f"已递归删除目录及其子目录: {file_path}")
            return True
    except (sqlite3.Error, sqlcipher3.dbapi2.DatabaseError) as err:
        LOGGER.error("Database operation failed: %s", err)
        return False

def update_suggestion_ignored(user_name, dir_id, file_id, change_id, ignored:bool):
    db_path = get_database_path(user_name, dir_id)
    if not db_path.exists():
        return False
    try:
        with closing(get_conn(db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute(UPDATE_SUGGESTION_IGNORED_SQL, (ignored, file_id, change_id))
            conn.commit()
            return True
    except (sqlite3.Error, sqlcipher3.dbapi2.DatabaseError) as err:
        LOGGER.error("Database operation failed: %s", err)
        return False


def query_user_id_from_database(user_name: str, dir_id: int) -> tuple[bool, int]:
    """
    从数据库中查询 user_id
    TODO: user_id 多余，可以删除
    Returns:
        tuple: (status, user_id)
            status: True 表示成功, False 表示失败
            user_id: user_id
    """
    user_db_path = get_database_path(user_name, dir_id)
    if not user_db_path.exists():
        LOGGER.warning(f"Database not found, skip querying user_id: {user_db_path}")
        return False, None
    try:
        with closing(get_conn(user_db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT user_id FROM codemig_task_directory_file LIMIT 1")
            row = cursor.fetchone()
            if not row:
                LOGGER.warning(f"No user_id records in database, skip: {user_db_path}")
                return False, None
            user_id = row[0]
            return True, user_id
    except (sqlite3.Error, sqlcipher3.dbapi2.DatabaseError) as err:
        LOGGER.error("Database operation failed: %s", err)
        return False, None


def _ensure_task_ai_stage_column(cursor):
    """v4.x 增量迁移：给老库的 codemig_task_ai 补 stage 列（幂等）。

    新库由 CREATE_TASK_AI_TABLE_SQL 建表时直接带 stage 列，此函数对
    重复 ADD COLUMN 报的 duplicate column 错误静默忽略。
    """
    try:
        cursor.execute(ALTER_TASK_AI_ADD_STAGE_SQL)
    except (sqlite3.Error, sqlcipher3.dbapi2.DatabaseError) as err:
        # "duplicate column name" = 列已存在，正常情况
        if "duplicate column" not in str(err).lower():
            raise


def create_ai_info_to_database(user_name, dir_id, file_id, request_id,
                               act_file_path, mode, cmd, stage=None):
    db_path = get_database_path(user_name, dir_id)
    if not db_path.exists():
        return False, None
    try:
        with closing(get_conn(db_path)) as conn:
            cursor = conn.cursor()
            # cmd 中可能含 -e KEY=VALUE 形式的完整 API key，入库前脱敏
            cursor.execute(INSTER_AI_RESULT_SQL, (file_id, request_id,
                                                  act_file_path, mode,
                                                  sanitize_cmd_text(cmd)))
            ai_id = cursor.lastrowid
            # v4.x：写入阶段标记（project_migrate/ut_test）。
            # stage 列由 _ensure_task_ai_stage_column 兜底补齐（老库）。
            if stage:
                _ensure_task_ai_stage_column(cursor)
                cursor.execute(
                    "UPDATE codemig_task_ai SET stage = ? WHERE ai_id = ?",
                    (stage, ai_id))
            conn.commit()
            return True, ai_id
    except (sqlite3.Error, sqlcipher3.dbapi2.DatabaseError) as err:
        LOGGER.error("Database operation failed: %s", err)
        return False, None


def update_ai_result(user_name, dir_id, request_id, running_time, suggestion, finished):
    db_path = get_database_path(user_name, dir_id)
    if not db_path.exists():
        return False
    try:
        with closing(get_conn(db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute(UPDATE_AI_RESULT_SQL, (suggestion, running_time,
                                                  finished, request_id))
            conn.commit()
            return True
    except (sqlite3.Error, sqlcipher3.dbapi2.DatabaseError) as err:
        LOGGER.error("Database operation failed: %s", err)
        return False

def update_ai_suggestion(user_name, dir_id, request_id, running_time, suggestion):
    update_ai_result(user_name, dir_id, request_id, running_time, suggestion, "completed")


def update_ai_exception(user_name, dir_id, suggestion, request_id, running_time):
    update_ai_result(user_name, dir_id, request_id, running_time, suggestion, "abnormal")


def _is_agent_container_alive(request_uuid):
    """校验 request_uuid 对应的 Agent 容器 docker_{request_uuid} 是否仍在运行。

    docker inspect 退出码非 0 = 容器不存在（正常结束后被 --rm 清理，
    或后端重启遗留的孤儿 running 记录）→ 未运行。
    docker CLI 不存在 / daemon 不可用 / 超时 → 视为未运行（fail-open）。
    """
    try:
        result = subprocess.run(
            ["docker", "inspect", "-f", "{{.State.Running}}", f"docker_{request_uuid}"],
            capture_output=True, text=True, timeout=5,
        )
    except (OSError, subprocess.SubprocessError) as e:
        LOGGER.warning(f"[ai-running-check] docker inspect 执行失败（视为未运行）: {e}")
        return False
    if result.returncode != 0:
        return False
    return result.stdout.strip().lower() == "true"


def is_ai_task_running(user_name, dir_id):
    """是否存在"真正在跑"的 AI Agent 任务（项目级迁移 / UT / MCA / 单文件 Agent 共用）。

    用于写入口守卫：Agent 容器 bind mount 同一仓库，运行期间保存会与其写入
    互相覆盖、并把半成品误收进 user-edit-save commit。

    与只看 finished='running' 的差异（方案 C）：
      - 后端重启导致的孤儿 running 记录（容器已不在）→ 不阻塞，无需 TTL 自愈；
      - 超长任务只要容器还在跑 → 一直受保护，无时间窗缺口；
      - normal/reasoning 模式的 running 记录无容器 → 自然放行（它们不写仓库）。

    任何查询 / docker 异常都返回 False（放行），不阻塞保存主流程。
    """
    db_path = get_database_path(user_name, dir_id)
    if not db_path.exists():
        return False
    try:
        with closing(get_conn(db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute(SELECT_RUNNING_AI_REQUEST_IDS_SQL)
            rows = cursor.fetchall()
    except (sqlite3.Error, sqlcipher3.dbapi2.DatabaseError) as err:
        LOGGER.error("Database operation failed: %s", err)
        return False
    for row in rows:
        request_uuid = row[0] if row else None
        if request_uuid and _is_agent_container_alive(request_uuid):
            LOGGER.info(
                f"[ai-running-check] AI task running: request_uuid={request_uuid}")
            return True
    return False


def query_ai_finished(user_name, dir_id, file_id, ai_id = None):
    db_path = get_database_path(user_name, dir_id)
    if not db_path.exists():
        return False, 0, None
    try:
        with closing(get_conn(db_path)) as conn:
            cursor = conn.cursor()
            if ai_id is None:
                cursor.execute(SELECT_MAX_AI_ID_BY_FILE_SQL, (file_id,))
                row = cursor.fetchone()
                ai_id = row[0] if row and row[0] is not None else None
                if ai_id is None:
                    LOGGER.info(f"No ai_id found for file_id {file_id}")
                    return True, 0, None
            cursor.execute(SELECT_AI_FINISHED_SQL, (file_id, ai_id))
            result = cursor.fetchone()
            return True, ai_id, result[0] if result else None
    except (sqlite3.Error, sqlcipher3.dbapi2.DatabaseError) as err:
        LOGGER.error("Database operation failed: %s", err)
        return False, 0, None


# 获取最新已生成的AI建议内容
def query_ai_suggestion_from_database(user_name, dir_id, file_id, ai_id = None):
    db_path = get_database_path(user_name, dir_id)
    if not db_path.exists():
        return False, 0, None
    conn = None
    try:
        conn = get_conn(db_path)
        cursor = conn.cursor()
        if ai_id is None:
            cursor.execute(SELECT_MAX_AI_ID_BY_FILE_SQL, (file_id,))
            row = cursor.fetchone()
            ai_id = row[0] if row and row[0] is not None else None
            if ai_id is None:
                LOGGER.info(f"No ai_id found for file_id {file_id}")
                return True, 0, None
        cursor.execute(SELECT_AI_SUGGESTION_SQL, (ai_id,))
        result = cursor.fetchone()
        return True, ai_id, result[0] if result else None
    except (sqlite3.Error, sqlcipher3.dbapi2.DatabaseError) as err:
        LOGGER.error("Database operation failed: %s", err)
        return False, 0, None
    finally:
        if conn:
            conn.close()

def _backfill_ai_stage_from_cmd(cursor):
    """v4.x：给加 stage 列之前的历史记录回填阶段标记。

    老记录没有 stage，但 cmd 里的 pi 命名卷名包含阶段缩写：
      codemig_migrate_pm_*  → project_migrate
      codemig_migrate_ut_*  → ut_test
      codemig_migrate_mca_* → mca_optimize（性能优化阶段已下线，
        此映射仅为识别历史卷名，新构建不再产生 mca 卷）
    （命名卷规则见 _migrate_named_volume_name；老的一键迁移记录同时
      还 cp .skills/projectmigrate，同样指向 project_migrate。）

    幂等：只更新 stage IS NULL 的行；识别不出卷名的行保持 NULL。
    """
    try:
        cursor.execute(
            "UPDATE codemig_task_ai SET stage = CASE "
            "WHEN cmd LIKE '%codemig_migrate_pm_%' THEN 'project_migrate' "
            "WHEN cmd LIKE '%codemig_migrate_ut_%' THEN 'ut_test' "
            "WHEN cmd LIKE '%codemig_migrate_mca_%' THEN 'mca_optimize' "
            "WHEN cmd LIKE '%.skills/projectmigrate%' THEN 'project_migrate' "
            "ELSE stage END "
            "WHERE file_id = 0 AND stage IS NULL"
        )
    except (sqlite3.Error, sqlcipher3.dbapi2.DatabaseError) as err:
        LOGGER.debug("backfill ai stage failed (ignored): %s", err)


def query_project_ai_suggestion(user_name, dir_id, stage=None):
    """
    查询最近一次项目级迁移的 AI 建议（用于刷新恢复）。
    一键迁移记录固定用 file_id=0 写入，此函数也固定查 file_id=0，
    与单文件的 query_ai_suggestion_from_database（按真实 file_id 查）物理隔离。

    v4.x：stage 参数支持按阶段查询（project_migrate/ut_test；
    历史数据可能含 mca_optimize，按传入值透传查询）；
    None = 不过滤，取全部阶段里最近的一次（兼容旧的"最近一次"语义）。

    Returns:
        tuple: (status, ai_id, suggestion)
            status: True 表示成功
            ai_id: 记录 ID，无记录时为 0
            suggestion: 建议文本，无记录时为 None
    """
    db_path = get_database_path(user_name, dir_id)
    if not db_path.exists():
        return False, 0, None
    conn = None
    try:
        conn = get_conn(db_path)
        cursor = conn.cursor()
        # file_id=0 是一键迁移的固定标记，不会命中任何真实文件（真实 file_id >= 1）
        _ensure_task_ai_stage_column(cursor)
        # v4.x：顺手回填老记录的 stage（幂等，详见函数注释）
        _backfill_ai_stage_from_cmd(cursor)
        cursor.execute(SELECT_MAX_PROJECT_AI_ID_BY_STAGE_SQL, (stage, stage))
        row = cursor.fetchone()
        ai_id = row[0] if row and row[0] is not None else None
        if ai_id is None:
            return True, 0, None
        cursor.execute(SELECT_AI_SUGGESTION_SQL, (ai_id,))
        result = cursor.fetchone()
        return True, ai_id, result[0] if result else None
    except (sqlite3.Error, sqlcipher3.dbapi2.DatabaseError) as err:
        LOGGER.error("Database operation failed: %s", err)
        return False, 0, None
    finally:
        if conn:
            conn.close()


def query_project_ai_history(user_name, dir_id):
    """
    v4.x：查询项目级（file_id=0）阶段历史列表，供前端 AI 面板切换器展示。
    只回元信息（不含 suggestion 大字段），按 ai_id 倒序（最近在前）最多 50 条。

    Returns:
        tuple: (status, records)
            records: [{ai_id, stage, mode, run_time, finished,
                       request_id, created_at}]，无记录时为 []
            旧记录 stage 为 NULL 时返回空串，前端按"未知阶段"兜底展示。
    """
    db_path = get_database_path(user_name, dir_id)
    if not db_path.exists():
        return False, []
    conn = None
    try:
        conn = get_conn(db_path)
        cursor = conn.cursor()
        _ensure_task_ai_stage_column(cursor)
        # v4.x：顺手回填老记录的 stage（幂等，详见函数注释）
        _backfill_ai_stage_from_cmd(cursor)
        cursor.execute(SELECT_PROJECT_AI_HISTORY_SQL)
        records = [
            {
                "ai_id": row[0],
                "stage": row[1] or "",
                "mode": row[2],
                "run_time": row[3],
                "finished": row[4],
                "request_id": row[5],
                "created_at": row[6],
            }
            for row in cursor.fetchall()
        ]
        return True, records
    except (sqlite3.Error, sqlcipher3.dbapi2.DatabaseError) as err:
        LOGGER.error("Database operation failed: %s", err)
        return False, []
    finally:
        if conn:
            conn.close()

def set_ai_score_to_database(user_name, dir_id, file_id, ai_id = None, score = 4):
    db_path = get_database_path(user_name, dir_id)
    if not db_path.exists():
        return False, "Database not exists."
    try:
        with closing(get_conn(db_path)) as conn:
            cursor = conn.cursor()
            if ai_id is None:
                cursor.execute(SELECT_MAX_AI_ID_BY_FILE_SQL, (file_id,))
                row = cursor.fetchone()
                ai_id = row[0] if row and row[0] is not None else None
                if ai_id is None:
                    LOGGER.error(f"No ai_id found for file_id {file_id}")
                    return False, "AI suggestion is not finished"
            cursor.execute(SET_AI_SCORE_SQL, (score, ai_id))
            conn.commit()
            return True, ''
    except (sqlite3.Error, sqlcipher3.dbapi2.DatabaseError) as err:
        LOGGER.error("Database operation failed: %s", err)
        return False, "Some error about Database occurred"

def query_ai_score_from_database(user_name, dir_id, file_id, uuid = None):
    db_path = get_database_path(user_name, dir_id)
    if not db_path.exists():
        return False, None
    conn = None
    try:
        conn = get_conn(db_path)
        cursor = conn.cursor()
        if uuid is None or len(uuid) < 1:
            cursor.execute(SELECT_MAX_AI_ID_BY_FILE_SQL, (file_id,))
            row = cursor.fetchone()
            ai_id = row[0] if row and row[0] is not None else None
            if ai_id is None:
                LOGGER.error(f"No ai_id found for file_id {file_id}")
                return True, None   # 没有查到AI_ID的话 认为没有设置
            cursor.execute(SELECT_AI_SCORE_SQL, (ai_id,))
        else:
            cursor.execute(SELECT_AI_SCORE_BY_UUID_SQL, (uuid,))

        result = cursor.fetchone()
        return True, result[0] if result else None
    except (sqlite3.Error, sqlcipher3.dbapi2.DatabaseError) as err:
        LOGGER.error("Database operation failed: %s", err)
        return False, None
    finally:
        if conn:
            conn.close()


# ─── 行号映射工具（v4.2） ───
# 设计要点：
#   - 输入 old_content / new_content 是完整文件内容（不是 path）。
#   - 返回的行号均为 1-based（与前端 Monaco 和 DB schema 一致）。
#   - "invalid" 判定：区间内任一行被删/被改。
#   - "kept" 判定：行号完全不变。
#   - 其他情况为 "shifted"。
# 触发场景：用户在一键迁移视图编辑 modified 文件并保存时，
# 后端用本工具把 (old_start, old_end) 投影到新文件的行号，
# 避免高亮钉死后因增/删行而指错位置。
def build_line_offset_table(old_content, new_content):
    """返回 offset_table：
      - 长度 = len(old_lines) + 1
      - offset_table[i] = old_lines[i] 在 new_lines 中的 0-based 行号
      - -1 表示该行被删除/替换
    """
    old_lines = old_content.splitlines()
    new_lines = new_content.splitlines()
    sm = difflib.SequenceMatcher(a=old_lines, b=new_lines, autojunk=False)
    offset_table = [-1] * (len(old_lines) + 1)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'equal':
            for k in range(i2 - i1):
                offset_table[i1 + k] = j1 + k
    return offset_table


def map_range(offset_table, old_start, old_end, total_new_lines):
    """输入：
      - offset_table: build_line_offset_table 的输出
      - old_start / old_end: 1-based 旧行号
      - total_new_lines: 新文件总行数
    输出：
      - (new_start, new_end, status) 元组
      - status: 'kept' / 'shifted' / 'invalid'
      - 若 invalid，new_start 和 new_end 均为 None
    """
    si, ei = old_start - 1, old_end - 1
    if si < 0 or ei >= len(offset_table) - 1:
        return None, None, 'invalid'
    new_indices = [offset_table[k] for k in range(si, ei + 1)]
    if any(idx == -1 for idx in new_indices):
        return None, None, 'invalid'
    new_start = new_indices[0] + 1
    new_end = new_indices[-1] + 1
    if new_start < 1 or new_end < 1:
        return None, None, 'invalid'
    if new_start > total_new_lines or new_end > total_new_lines:
        return None, None, 'invalid'
    if new_start > new_end:
        return None, None, 'invalid'
    if new_start == old_start and new_end == old_end:
        return new_start, new_end, 'kept'
    return new_start, new_end, 'shifted'