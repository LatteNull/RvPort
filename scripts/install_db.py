import os
import random
import select
import sqlite3
import string
import sys
import re
from contextlib import contextmanager
import time
import sqlcipher3
import pymysql

_SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.join(os.path.realpath(os.path.join(_SCRIPT_DIR, '..')), 'server'))
from common import crypto  # noqa: E402

DEBUG_MODE = True
CURRENT_PATH = os.path.dirname(os.path.realpath(__file__))

ROOT_PATH = os.path.realpath(os.path.join(CURRENT_PATH, '..'))
DB_PATH = os.path.join(ROOT_PATH, 'data', 'codemig.db')
DB_SQL_FILE = os.path.join(ROOT_PATH, 'scripts', 'install')


def _validate_mysql_db_name(name):
    """校验 MySQL 库名，仅允许字母/数字/下划线，防止 SQL 注入。"""
    if not name or not re.fullmatch(r'[A-Za-z0-9_]+', name):
        print(f"Error: Invalid database name: {name!r}")
        sys.exit(1)
    return name


def _load_kit_versions():
    """从 server/version.py 读取三个版本号（版本单一源）。

    开发态：ROOT_PATH 指向项目根，读取源码 server/version.py。
    安装态：db.py 被编译为 install_db.bin，ROOT_PATH 指向安装目录，
            server/version.py 随包附带（见 compile_server.sh），同样可读。
    读取失败时回退到内置默认值，保证数据库初始化不中断。
    """
    import re
    versions = {'framework': 'ZXW-CPU-ECO-KIT-V26.03.03',
                'codemig': 'ZXW-CPU-ECO-KIT-V26.03.03'}
    try:
        version_file = os.path.join(ROOT_PATH, 'server', 'version.py')
        with open(version_file, 'r', encoding='utf-8') as f:
            text = f.read()

        def _grab(name):
            m = re.search(r"^%s\s*=\s*['\"](.*)['\"]" % name, text, re.M)
            return m.group(1) if m else None

        framework = _grab('VERSION')
        codemig = _grab('CODE_MIG_VERSION')
        if framework:
            versions['framework'] = framework
        if codemig:
            versions['codemig'] = codemig
    except Exception as err:
        print(f"warning: read server/version.py failed, use default versions: {err}")
    return versions


_KIT_VERSIONS = _load_kit_versions()


def init_key(path=None):
    key_path = os.path.join(path, "himalayan")
    nonce_path = os.path.join(path, "qomolangma")
    if not os.path.exists(os.path.dirname(key_path)):
        os.makedirs(os.path.dirname(key_path))
    if os.path.exists(key_path) and os.path.exists(nonce_path):
        return key_path, nonce_path
    try:
        crypto.generate_key_file(key_path)
        crypto.generate_nonce_file(nonce_path)
    except OSError:
        print("init file failed")
        return None, None
    return key_path, nonce_path


def generate_pw(length=16):
    # 定义字符集
    lower = string.ascii_lowercase
    upper = string.ascii_uppercase
    digits = string.digits
    symbols = '!@#$%^*()-_+={}[],.?/'

    # 确保密码包含至少一个大小写字母、数字和特殊字符
    password = [
        random.choice(lower),
        random.choice(upper),
        random.choice(digits),
        random.choice(symbols)
    ]

    # 剩余部分随机选择
    remaining_length = length - 4
    all_chars = lower + upper + digits + symbols
    password += [random.choice(all_chars) for _ in range(remaining_length)]

    # 打乱密码以确保随机性
    random.shuffle(password)

    return ''.join(password)


def encrypt_passphrase(key_path, nonce_path, pw):
    """AES-256-GCM 加密，返回 (ciphertext, tag)。"""
    key = crypto.read_key_file(key_path)
    nonce = crypto.read_nonce_file(nonce_path)
    data = crypto.aes_gcm_encrypt(key, nonce, pw)
    return data[:-crypto.TAG_SIZE], data[-crypto.TAG_SIZE:]


def decrypt_passphrase(key_path, nonce_path, pw, gcm_tag):
    """AES-256-GCM 解密，返回明文 bytes；失败抛异常。"""
    key = crypto.read_key_file(key_path)
    nonce = crypto.read_nonce_file(nonce_path)
    return crypto.aes_gcm_decrypt(key, nonce, pw + gcm_tag)

    plaintext_bytes = bytes(plaintext[:ciphertext_len])

    return plaintext_bytes


@contextmanager
def create_db(db_type="sqlite", pw=None, mysql_config=None):
    connection = None
    try:
        if db_type == "mysql":
            # MySQL 连接
            if mysql_config is None:
                print("Error: MySQL 配置不能为空")
                sys.exit(1)
            # 先连接到 MySQL 服务器（不指定数据库），创建数据库（如果不存在）
            temp_conn = pymysql.connect(
                host=mysql_config.get('host'),
                port=int(mysql_config.get('port', 3306)),
                user=mysql_config.get('user'),
                password=mysql_config.get('password'),
                charset='utf8mb4'
            )
            database_name = _validate_mysql_db_name(mysql_config.get('database', 'codemig'))
            with temp_conn.cursor() as cursor:
                cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{database_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
            temp_conn.close()
            
            # 连接到指定的数据库
            connection = pymysql.connect(
                host=mysql_config.get('host'),
                port=int(mysql_config.get('port', 3306)),
                user=mysql_config.get('user'),
                password=mysql_config.get('password'),
                database=database_name,
                charset='utf8mb4',
                cursorclass=pymysql.cursors.DictCursor
            )
        else:
            # SQLite 连接
            if not os.path.exists(os.path.dirname(DB_PATH)):
                os.makedirs(os.path.dirname(DB_PATH))
            if not DEBUG_MODE:
                connection = sqlcipher3.connect(DB_PATH)
                # 设置密码
                connection.execute(f"PRAGMA key = '{pw}';")
            else:
                connection = sqlite3.connect(DB_PATH)

        yield connection
    except Exception as e:
        print(f"db operation failed: {e}")
        print(sys.exc_info())
        sys.exit(1)
    finally:
        if connection is not None:
            connection.close()


def _generate_key_file_in_dir(base_dir, password=None):
    """
    在指定目录下生成或读取加密密钥文件的通用函数
    
    Args:
        base_dir: 基础目录路径
        password: 可选的密码，如果文件不存在且提供了密码则使用该密码，否则生成新密码
        
    Returns:
        str: 密码字符串
    """
    key_path, nonce_path = init_key(base_dir)
    if key_path is None or nonce_path is None:
        print("init key file failed")
        sys.exit(1)
    target = os.path.join(base_dir, "8848")
    if os.path.exists(target):
        print("target file exists")
        with open(target, "rb") as file:
            read_data = file.read()
        cip_text = read_data[:-16]
        gcm_tag = read_data[-16:]
        pw = decrypt_passphrase(key_path, nonce_path,
                                cip_text, gcm_tag).decode()
    else:
        if password is not None:
            pw = password
        else:
            pw = generate_pw()
        cip_text, gcm_tag = encrypt_passphrase(key_path, nonce_path, pw)
        with open(target, "wb") as file:
            file.write(cip_text + gcm_tag)
    return pw


def generate_key_file(password=None):
    """
    在 data 目录下生成或读取加密密钥文件
    
    Args:
        password: 可选的密码，如果文件不存在且提供了密码则使用该密码，否则生成新密码
        
    Returns:
        str: 密码字符串
    """
    return _generate_key_file_in_dir(os.path.join(ROOT_PATH, "data"), password)


def generate_config_key_file(password=None):
    """
    在 data/config 目录下生成或读取加密密钥文件
    
    Args:
        password: 可选的密码，如果文件不存在且提供了密码则使用该密码，否则生成新密码
        
    Returns:
        str: 密码字符串
    """
    return _generate_key_file_in_dir(os.path.join(ROOT_PATH, "data", "config"), password)


def generate_mysql_password_file(password=None):
    """使用与 generate_key_file 相同的方法加密并存储 MySQL 密码"""
    key_path, nonce_path = init_key(os.path.join(ROOT_PATH, "data"))
    if key_path is None or nonce_path is None:
        print("init key file failed")
        sys.exit(1)
    target = os.path.join(ROOT_PATH, "data", "8848")
    if password is not None and password.strip():
        # 如果提供了密码，加密并写入文件（覆盖已存在的文件）
        pw = password.strip()
        cip_text, gcm_tag = encrypt_passphrase(key_path, nonce_path, pw)
        with open(target, "wb") as file:
            file.write(cip_text + gcm_tag)
    elif os.path.exists(target):
        # 如果文件存在且未提供密码，从文件读取并解密
        with open(target, "rb") as file:
            read_data = file.read()
        # 密文是去掉最后16字节（标签）后的所有内容，长度不固定
        cip_text = read_data[:-16]
        gcm_tag = read_data[-16:]
        pw = decrypt_passphrase(key_path, nonce_path,
                                cip_text, gcm_tag).decode()
    else:
        # 如果文件不存在且未提供密码，报错
        print("Error: MySQL 密码不能为空")
        sys.exit(1)
    return pw


def create_tables(conn, installed: dict, db_type="sqlite"):
    """执行SQL文件（含框架表、codemig 表、弱密码种子数据）。

    文件内段落以 `-- ===== 来源: ...` 注释分隔，弱密码数据以
    INSERT OR IGNORE / INSERT IGNORE 幂等写入，重复执行安全。
    codemig 是本工具唯一的插件，installed 参数仅用于保持调用兼容。
    """
    db_sql_path = os.path.join(ROOT_PATH, 'scripts', 'install', f'{db_type}.sql')
    if not os.path.isfile(db_sql_path):
        print(f"Error: SQL file not found: {db_sql_path}")
        sys.exit(1)

    with open(db_sql_path, "r") as f:
        sql = f.read()
    try:
        if db_type == "mysql":
            # MySQL 需要分割 SQL 语句并逐个执行
            cursor = conn.cursor()
            statements = []
            current_statement = ""
            for line in sql.split('\n'):
                # 简单的分割逻辑：以行尾分号作为语句分隔
                if line.strip().endswith(';'):
                    current_statement += line + '\n'
                    statements.append(current_statement.strip())
                    current_statement = ""
                else:
                    current_statement += line + '\n'
            if current_statement.strip():
                statements.append(current_statement.strip())

            # 逐条执行：单条语句失败不放弃整个文件，否则该文件
            # 后续的建表语句会被静默跳过，导致安装后表结构不完整
            # （曾因 user_configuration 末尾多余逗号，使 codemig
            # 后续 10 张表全部丢失且安装进程无任何报错退出）。
            file_errors = []
            for statement in statements:
                if not statement.strip():
                    continue
                try:
                    cursor.execute(statement)
                except Exception as stmt_err:
                    file_errors.append(str(stmt_err))
                    try:
                        conn.rollback()
                    except Exception:
                        pass
            cursor.close()
            if file_errors:
                print(f"Executed SQL from {db_sql_path} "
                      f"with {len(file_errors)} error(s):")
                for err in file_errors:
                    print(f"  - {err}")
            else:
                print(f"Executed SQL from: {db_sql_path}")
        else:
            # SQLite 使用 executescript
            conn.executescript(sql)
            print(f"Executed SQL from: {db_sql_path}")
    except Exception as e:
        print(f"Executed SQL error from {db_sql_path}: {e}")
    conn.commit()


class Plugin:
    PLUGIN_TABLE_NAME = 'plugin'

    LOCAL_PLUGIN_INFO_FRAMEWORK = {
        "plugin_type": 'framework',
        "current_version": _KIT_VERSIONS['framework'],
        "status": 3,
        "update_time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
        "progress_status": 100,
        "create_time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
        "plugin_meta_json": ""
    }

    LOCAL_PLUGIN_INFO_CODEMIG = {
        "plugin_type": 'codemig',
        "current_version": _KIT_VERSIONS['codemig'],
        "status": 3,
        "update_time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
        "progress_status": 100,
        "create_time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
        "plugin_meta_json": ""
    }

    @staticmethod
    def create_db(connection, install_codemig=True, db_type="sqlite"):
        try:
            cursor = connection.cursor()
            if db_type == "mysql":
                # MySQL 使用 %s 占位符和 ON DUPLICATE KEY UPDATE
                sql = f"INSERT INTO {Plugin.PLUGIN_TABLE_NAME} (plugin_type, current_version, status, update_time, progress_status, create_time, plugin_meta_json) \
                        VALUES (%(plugin_type)s, %(current_version)s, %(status)s, %(update_time)s, %(progress_status)s, %(create_time)s, %(plugin_meta_json)s) \
                        ON DUPLICATE KEY UPDATE \
                        current_version = VALUES(current_version), update_time = VALUES(update_time)"
            else:
                # SQLite 使用命名参数和 ON CONFLICT
                sql = f"INSERT INTO {Plugin.PLUGIN_TABLE_NAME} (plugin_type, current_version, status, update_time, progress_status, create_time, plugin_meta_json) \
                        VALUES (:plugin_type, :current_version, :status, :update_time, :progress_status, :create_time, :plugin_meta_json) \
                        ON CONFLICT(plugin_type) DO UPDATE SET \
                        current_version = excluded.current_version, update_time = excluded.update_time"
            # framework 是框架本体，始终随初始化写入（与插件独立）
            cursor.execute(sql, Plugin.LOCAL_PLUGIN_INFO_FRAMEWORK)
            if install_codemig:
                cursor.execute(sql, Plugin.LOCAL_PLUGIN_INFO_CODEMIG)
            cursor.close()
        except sqlite3.Error as err:
            connection.rollback()
            raise Exception("Create error: %s", err)
        except Exception as err:
            if db_type == "mysql":
                connection.rollback()
                raise Exception("Create error: %s", err)
            raise


def uninstall_mysql_db(mysql_config):
    """
    卸载 MySQL 数据库：删除数据库中的所有表
    
    Args:
        mysql_config: MySQL 配置字典，包含 host, port, user, password, database
    """
    connection = None
    try:
        # 连接到 MySQL 服务器
        connection = pymysql.connect(
            host=mysql_config.get('host'),
            port=int(mysql_config.get('port', 3306)),
            user=mysql_config.get('user'),
            password=mysql_config.get('password'),
            database=mysql_config.get('database', 'codemig'),
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor,
            connect_timeout=10,
            read_timeout=30,
            write_timeout=30
        )
        
        with connection.cursor() as cursor:
            # 获取所有表名
            cursor.execute("SHOW TABLES")
            tables = cursor.fetchall()
            
            if tables:
                # 禁用外键检查，以便删除有外键约束的表
                cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
                
                # 删除所有表
                for table in tables:
                    table_name = list(table.values())[0]
                    try:
                        cursor.execute(f"DROP TABLE IF EXISTS `{table_name}`")
                        print(f"Deleted table: {table_name}")
                    except Exception as e:
                        print(f"Error dropping table {table_name}: {e}")
                        # 如果连接丢失，尝试重新连接
                        if "Lost connection" in str(e) or "2013" in str(e):
                            print("Connection lost, attempting to reconnect...")
                            try:
                                connection.close()
                            except:
                                pass
                            connection = pymysql.connect(
                                host=mysql_config.get('host'),
                                port=int(mysql_config.get('port', 3306)),
                                user=mysql_config.get('user'),
                                password=mysql_config.get('password'),
                                database=mysql_config.get('database', 'codemig'),
                                charset='utf8mb4',
                                cursorclass=pymysql.cursors.DictCursor,
                                connect_timeout=10,
                                read_timeout=30,
                                write_timeout=30
                            )
                            cursor = connection.cursor()
                            cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
                            # 继续删除剩余的表
                            continue
                
                # 重新启用外键检查
                try:
                    cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
                    # 提交更改
                    connection.commit()
                except Exception as e:
                    # 如果连接已丢失，忽略提交错误
                    if "Lost connection" not in str(e) and "2013" not in str(e):
                        print(f"Warning: Failed to commit changes: {e}")
                
                print(f"Successfully uninstalled MySQL database: {mysql_config.get('database', 'codemig')}")
            else:
                print(f"No tables found in database: {mysql_config.get('database', 'codemig')}")

            # 删除数据库本身：库是安装时由本工具 CREATE DATABASE 创建的，卸载应一并删除（避免留下空库）
            db_name = _validate_mysql_db_name(mysql_config.get('database', 'codemig'))
            try:
                cursor.execute(f"DROP DATABASE IF EXISTS `{db_name}`")
                print(f"Dropped database: {db_name}")
            except Exception as e:
                print(f"Warning: Failed to drop database {db_name}: {e}")

        return True
    except pymysql.err.OperationalError as e:
        error_code = e.args[0] if e.args else None
        if error_code == 2013:  # Lost connection to MySQL server
            print(f"Warning: Lost connection to MySQL server. Database may have been partially uninstalled.")
            print(f"Error details: {e}")
            return True  # 返回 True，因为部分卸载也算成功（表可能已经被删除）
        else:
            print(f"Error uninstalling MySQL database: {e}")
            return False
    except Exception as e:
        print(f"Error uninstalling MySQL database: {e}")
        print(sys.exc_info())
        return False
    finally:
        # 确保连接被关闭
        if connection is not None:
            try:
                connection.close()
            except:
                pass


if __name__ == "__main__":
    # 解析卸载参数
    uninstall = False
    for arg in sys.argv:
        if arg.startswith("uninstall="):
            uninstall_value = arg.split("=", 1)[1]
            if uninstall_value == "1":
                uninstall = True
            break

    # codemig 是本工具唯一的插件，SQL 目录按 install_codemig=True 处理
    installed = {'install_codemig': True}

    # 解析数据库类型参数，默认为 sqlite
    db_type = "sqlite"
    for arg in sys.argv:
        if arg.startswith("db_type="):
            db_type_arg = arg.split("=", 1)[1].lower()
            if db_type_arg in ["mysql", "sqlite"]:
                db_type = db_type_arg
            else:
                print(f"Warning: 不支持的数据库类型 '{db_type_arg}'，使用默认值 'sqlite'")
            break

    # 解析 MySQL 连接参数（IP、端口、用户名、数据库名）
    mysql_host = None
    mysql_port = None
    mysql_user = None
    mysql_database = "codemig"  # 默认数据库名
    for arg in sys.argv:
        if arg.startswith("mysql_host=") or arg.startswith("mysql_ip="):
            mysql_host = arg.split("=", 1)[1]
        elif arg.startswith("mysql_port="):
            mysql_port = arg.split("=", 1)[1]
        elif arg.startswith("mysql_user=") or arg.startswith("mysql_username="):
            mysql_user = arg.split("=", 1)[1]
        elif arg.startswith("mysql_database=") or arg.startswith("mysql_db="):
            mysql_database = arg.split("=", 1)[1]

    # 如果数据库类型是 MySQL，验证必需参数
    mysql_config = {}
    if db_type == "mysql":
        if not mysql_host:
            print("Error: MySQL 数据库需要指定 mysql_host 或 mysql_ip 参数")
            sys.exit(1)
        if not mysql_port:
            print("Error: MySQL 数据库需要指定 mysql_port 参数")
            sys.exit(1)
        if not mysql_user:
            print("Error: MySQL 数据库需要指定 mysql_user 或 mysql_username 参数")
            sys.exit(1)
        mysql_config = {
            'host': mysql_host,
            'port': mysql_port,
            'user': mysql_user,
            'database': mysql_database
        }

    # 根据数据库类型获取密码
    pw = None
    if db_type == "mysql":
        # MySQL 从命令行管道（stdin）读取密码，如果没有则从文件获取
        mysql_password = None
        # 检查 stdin 是否是终端（TTY），如果不是终端，说明可能有管道输入
        if not sys.stdin.isatty():
            # stdin 不是终端，可能是管道输入，使用 select 非阻塞检查是否有数据可读
            if select.select([sys.stdin], [], [], 0)[0]:
                mysql_password = sys.stdin.read().strip()
        
        if mysql_password:
            # 有管道输入，使用密码并加密存储
            try:
                pw = generate_mysql_password_file(mysql_password)
                mysql_config['password'] = pw
            except Exception as e:
                print(f'Error: 存储 MySQL 密码失败: {e}')
                sys.exit(1)
        else:
            # 没有管道输入，从文件读取
            try:
                pw = generate_mysql_password_file()
                mysql_config['password'] = pw

            except Exception as e:
                print(f'Error: 读取或存储 MySQL 密码失败: {e}')
                sys.exit(1)
    else:
        # SQLite 使用 generate_key_file() 生成或获取密码
        try:
            pw = generate_key_file()
            # 在 data/config 目录下生成一组加密文件
            generate_config_key_file(pw)
        except Exception:
            try:
                files_to_remove = [
                    os.path.join(ROOT_PATH, "data", "himalayan"),
                    os.path.join(ROOT_PATH, "data", "qomolangma"),
                    os.path.join(ROOT_PATH, "data", "8848")
                ]
                for file_path in files_to_remove:
                    if os.path.exists(file_path):
                        try:
                            os.remove(file_path)
                        except OSError as e:
                            print(f'Error removing {file_path}: {e}')
                            continue
                pw = generate_key_file()
                # 在 data/config 目录下生成一组加密文件
                generate_config_key_file(pw)
            except Exception:
                print('generate file error!')
                sys.exit(1)
    # 如果是卸载模式
    if uninstall:
        if db_type == "mysql":
            # 卸载 MySQL 数据库
            if not mysql_config:
                print("Error: MySQL 配置不能为空，无法卸载")
                sys.exit(1)
            success = uninstall_mysql_db(mysql_config)
            if not success:
                sys.exit(1)
            print("MySQL database uninstalled successfully")
        else:
            print("Warning: SQLite uninstall is not supported")
        sys.exit(0)

    # 安装模式
    try:
        # 根据数据库类型创建连接
        if db_type == "mysql":
            with create_db(db_type="mysql", mysql_config=mysql_config) as conn:
                create_tables(conn, installed, db_type="mysql")
                Plugin.create_db(conn, db_type="mysql")
                conn.commit()
        else:
            with create_db(db_type="sqlite", pw=pw) as conn:
                create_tables(conn, installed, db_type="sqlite")
                Plugin.create_db(conn, db_type="sqlite")
                conn.commit()
    except Exception as e:
        print(sys.exc_info())
        sys.exit(1)
        
    try:
            pw = generate_config_key_file()

    except Exception:
            try:
                files_to_remove = [
                    os.path.join(ROOT_PATH, "data", "config", "himalayan"),
                    os.path.join(ROOT_PATH, "data", "config", "qomolangma"),
                    os.path.join(ROOT_PATH, "data", "config", "8848")
                ]
                for file_path in files_to_remove:
                    if os.path.exists(file_path):
                        try:
                            os.remove(file_path)
                        except OSError as e:
                            print(f'Error removing {file_path}: {e}')
                            continue
             
                # 在 data/config 目录下生成一组加密文件
                generate_config_key_file()
            except Exception:
                print('generate file error!')
                sys.exit(1)
