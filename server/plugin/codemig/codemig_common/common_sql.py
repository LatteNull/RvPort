# """
# --  type: 0-> 源码扫描 对应 codemig_task_directory_file_suggestion
# --  type: 1-> 软件包扫描 对应 codemig_task_directory_software_suggestion
# --  type: 2-> 缺失文件 对应 codemig_task_directory_existing_architecture
# """
TASK_DIRECTORY_FILE_TABLE_NAME = "codemig_task_directory_file"
TASK_DIRECTORY_FILE_SCHEMA = (
    "user_id INTEGER NOT NULL,"
    "dir_id INTEGER NOT NULL,"
    "file_id INTEGER PRIMARY KEY AUTOINCREMENT,"
    "type INTEGER NOT NULL DEFAULT 0 CHECK (type IN (0, 1, 2)),"
    "file_path TEXT NOT NULL,"
    "has_removed INTEGER NOT NULL DEFAULT 0 CHECK (has_removed IN (0, 1)),"
    "file_source TEXT NOT NULL CHECK (file_source IN ('original', 'changed', 'missing', 'generated')),"
    "is_file INTEGER NOT NULL DEFAULT 1 CHECK (is_file IN (0, 1)),"
    "source_file_id INTEGER,"
    "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
)
TASK_DIRECTORY_FILE_KEY_INDEX = ("""
    CREATE UNIQUE INDEX IF NOT EXISTS codemig_task_directory_file_key_index
    ON codemig_task_directory_file(user_id, dir_id, file_id);
""")
TASK_DIRECTORY_FILE_TYPE_KEY_INDEX = ("""
    CREATE UNIQUE INDEX IF NOT EXISTS codemig_task_directory_file_type_key_index
    ON codemig_task_directory_file(user_id, type, dir_id, file_id);
""")
# 完整建表 DDL：表名/列定义在此处静态组合，调用方不得再拼接（防 SQL 注入告警）
CREATE_TASK_DIRECTORY_FILE_TABLE_SQL = (
    f"CREATE TABLE IF NOT EXISTS {TASK_DIRECTORY_FILE_TABLE_NAME} "
    f"({TASK_DIRECTORY_FILE_SCHEMA})"
)

# """
# --  type: 建议类型
# --  0 -> makefile, 1 -> intrinsices, 2 -> builtin, 3 -> macros, 4 -> assembly in c or c++,
# --  5 -> assembly file, 6 -> java source code, 7 -> python source code, 8 -> go source code,
# --  9 -> shell, 10 -> build script, 11 -> build meson
# --  code_too_long: 源代码是否太长
# --  0 -> 有源码, 1 -> 源码太长不存储
# """
TASK_DIRECTORY_FILE_SUGGESTION_TABLE_NAME = "codemig_task_directory_file_suggestion"
TASK_DIRECTORY_FILE_SUGGESTION_SCHEMA = (
    "file_id INTEGER NOT NULL,"
    "change_id INTEGER PRIMARY KEY AUTOINCREMENT,"
    "type INTEGER NOT NULL,"
    "append_or_replace INTEGER NOT NULL CHECK (append_or_replace IN (0, 1, 2)),"
    "start_line_number INTEGER NOT NULL,"
    "end_line_number INTEGER NOT NULL,"
    "suggestion TEXT NOT NULL,"
    "code_too_long INTEGER,"
    "code TEXT,"
    "ignored INTEGER NOT NULL DEFAULT 0 CHECK (ignored IN (0, 1)),"
    "is_manual INTEGER NOT NULL DEFAULT 0 CHECK (is_manual IN (0, 1)),"
    "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,"
    "FOREIGN KEY (file_id) REFERENCES codemig_task_directory_file(file_id)"
)
TASK_DIRECTORY_FILE_SUGGESTION_KEY_INDEX = ("""
    CREATE UNIQUE INDEX IF NOT EXISTS codemig_task_directory_file_suggestion_key_index
    ON codemig_task_directory_file_suggestion(file_id, change_id);
""")
CREATE_TASK_DIRECTORY_FILE_SUGGESTION_TABLE_SQL = (
    f"CREATE TABLE IF NOT EXISTS {TASK_DIRECTORY_FILE_SUGGESTION_TABLE_NAME} "
    f"({TASK_DIRECTORY_FILE_SUGGESTION_SCHEMA})"
)



# """
# --  support_architecture: 架构信息 riscv64\x86_64...
# --  suggestion: 建议信息（建议、或者链接）
# """
TASK_DIRECTORY_SOFTWARE_SUGGESTION_TABLE_NAME = "codemig_task_directory_software_suggestion"
TASK_DIRECTORY_SOFTWARE_SUGGESTION_SCHEMA = (
    "file_id INTEGER NOT NULL,"
    "change_id INTEGER PRIMARY KEY AUTOINCREMENT,"
    "support_architecture TEXT NOT NULL,"
    "suggestion TEXT NULL,"
    "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,"
    "FOREIGN KEY (file_id) REFERENCES codemig_task_directory_file(file_id)"
)
TASK_DIRECTORY_SOFTWARE_SUGGESTION_KEY_INDEX = ("""
    CREATE UNIQUE INDEX IF NOT EXISTS codemig_task_directory_software_suggestion_key_index
    ON codemig_task_directory_software_suggestion(file_id, change_id);
""")
CREATE_TASK_DIRECTORY_SOFTWARE_SUGGESTION_TABLE_SQL = (
    f"CREATE TABLE IF NOT EXISTS {TASK_DIRECTORY_SOFTWARE_SUGGESTION_TABLE_NAME} "
    f"({TASK_DIRECTORY_SOFTWARE_SUGGESTION_SCHEMA})"
)


# """
# --  architecture_path 缺失文件对应的其他架构路径 例如 缺失file_riscv64.go 文件 对应 file_arm64.go 文件
# """
TASK_DIRECTORY_EXISTING_ARCHITECTURE_TABLE_NAME = "codemig_task_directory_existing_architecture"
TASK_DIRECTORY_EXISTING_ARCHITECTURE_SCHEMA = (
    "file_id INTEGER NOT NULL,"
    "change_id INTEGER PRIMARY KEY AUTOINCREMENT,"
    "architecture_path TEXT NOT NULL,"
    "type INTEGER DEFAULT 0,"
    "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,"
    "FOREIGN KEY (file_id) REFERENCES codemig_task_directory_file(file_id)"
)
TASK_DIRECTORY_EXISTING_ARCHITECTURE_KEY_INDEX = ("""
    CREATE UNIQUE INDEX IF NOT EXISTS codemig_task_directory_existing_architecture_key_index
    ON codemig_task_directory_existing_architecture(file_id, change_id);
""")
CREATE_TASK_DIRECTORY_EXISTING_ARCHITECTURE_TABLE_SQL = (
    f"CREATE TABLE IF NOT EXISTS {TASK_DIRECTORY_EXISTING_ARCHITECTURE_TABLE_NAME} "
    f"({TASK_DIRECTORY_EXISTING_ARCHITECTURE_SCHEMA})"
)


# codemig_task_directory_file
INSERT_FILE_SQL = ("""
    INSERT INTO codemig_task_directory_file
    (user_id, dir_id, file_path, file_source, is_file)
    VALUES (?, ?, ?, ?, ?)
""")

REMOVE_FILE_SQL = ("""
    UPDATE codemig_task_directory_file
    SET has_removed = 1
    WHERE file_id = ?
""")

# 标记删除的目录及其所有子目录和文件
REMOVE_DIRECTORY_RECURSIVE_SQL = ("""
    UPDATE codemig_task_directory_file
    SET has_removed = 1
    WHERE file_path LIKE ? || '/%'
       OR file_path = ?
       AND type = 0
""")

INSERT_CHANGED_FILE_SQL = ("""
    INSERT INTO codemig_task_directory_file  
    (user_id, dir_id, file_path, type, file_source, is_file)
    VALUES (?, ?, ?, ?, ?, ?)
""")

UPDATE_CHANGED_FILE_SQL = ("""
    UPDATE codemig_task_directory_file
    SET file_source = ?, type = ?
    WHERE file_path = ?
""")

SELECT_FILE_BY_PATH_SQL = ("""
    SELECT file_id
    FROM codemig_task_directory_file
    WHERE file_path = ? AND has_removed = 0 AND type != 2
    LIMIT 1
""")

SELECT_FILE_TREE_SQL = ("""
    SELECT file_id, file_path, file_source, is_file, source_file_id FROM codemig_task_directory_file
    WHERE has_removed = 0 AND type = 0
    ORDER BY file_path ASC
""")

SELECT_MISSING_FILE_TREE_SQL = ("""
    SELECT file_id, file_path, file_source, is_file FROM codemig_task_directory_file
    WHERE type = 2
    ORDER BY file_path ASC
""")

# type=2 缺失文件，排除：同一 file_path 下存在 file_source='generated' 且 has_removed=0 的记录（即存在生成的文件 不再提供给前端）
# ★ 字面量必须与 FileSource.GENERATE 枚举值 "generated"（codemig_common_utils.py）一致。
SELECT_MISSING_FILES_NOT_GENERATED_FROM_DATABASE_SQL = ("""
    SELECT m.file_id, m.file_path, m.file_source, m.is_file
    FROM codemig_task_directory_file m
    WHERE m.type = 2 AND m.has_removed = 0
      AND NOT EXISTS (
        SELECT 1 FROM codemig_task_directory_file g
        WHERE g.file_path = m.file_path
          AND g.file_source = 'generated'
          AND g.has_removed = 0
      )
    ORDER BY m.file_path ASC
""")

# 迁移生成的新增文件（file_source='generated'，type=0）。
# ②功能验证（test/）阶段产物同样落此表，由该节点的清单接口
# （query_ut_test_files_processor 扫描目录）负责展示，①代码生成节点按
# repo 相对路径前缀（含历史残留的 mca/ 目录）在 processor 侧排除。
SELECT_GENERATED_FILE_SQL = ("""
    SELECT file_id, file_path, is_file FROM codemig_task_directory_file
    WHERE file_source = 'generated' AND has_removed = 0 AND type = 0
    ORDER BY file_path ASC
""")

SELECT_ALL_FILE_SQL = ("""
    SELECT file_path, file_source, is_file, file_id FROM codemig_task_directory_file
    WHERE has_removed = 0
    ORDER BY file_path ASC
""")

SELECT_FILE_PATH_SQL = (
    "SELECT file_path FROM codemig_task_directory_file WHERE file_id = ?")

SELECT_FILE_INFO_SQL = (
    "SELECT file_path, file_source, has_removed, is_file FROM codemig_task_directory_file WHERE file_id = ?")

INSERT_GENERATE_FILE_SQL = ("""
    INSERT INTO codemig_task_directory_file  
    (user_id, dir_id, file_path, file_source, is_file, source_file_id)
    VALUES (?, ?, ?, ?, ?, ?)
""")

# codemig_task_directory_file_suggestion
INSERT_SUGGESTION_SQL = (
    "INSERT INTO codemig_task_directory_file_suggestion "
    "(file_id, type, append_or_replace, start_line_number,"
    " end_line_number, suggestion, code_too_long, code) VALUES (?, ?, ?, ?, ?, ?, ?, ?)")

INSERT_SUGGESTION_WITH_IGNORE_SQL = (
    "INSERT INTO codemig_task_directory_file_suggestion "
    "(file_id, type, append_or_replace, start_line_number,"
    " end_line_number, suggestion, code_too_long, code, ignored, is_manual) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0)")

UPDATE_SUGGESTION_IGNORED_SQL = (
    "UPDATE codemig_task_directory_file_suggestion "
    "SET ignored = ? "
    "WHERE file_id = ? AND change_id = ?")

REMOVE_SUGGESTION_OF_FILE_SQL = ("""
    DELETE FROM codemig_task_directory_file_suggestion
    WHERE file_id = ? AND ignored = 0 AND is_manual = 0
""")

SELECT_IGNORED_SUGGESTIONS_BY_FILE_ID_SQL = ("""
    SELECT start_line_number, end_line_number, suggestion, code
    FROM codemig_task_directory_file_suggestion
    WHERE file_id = ? AND ignored = 1
""")

# codemig_task_directory_software_suggestion
INSERT_SUGGESTION_SOFTWARE_SQL = (
    "INSERT INTO codemig_task_directory_software_suggestion "
    "(file_id, support_architecture, suggestion) VALUES (?, ?, ?)")


# codemig_task_directory_existing_architecture
INSERT_EXISTING_ARCHITECTURE_SQL = (
    "INSERT INTO codemig_task_directory_existing_architecture "
    "(file_id, architecture_path) VALUES (?, ?)")

INSERT_EXISTING_ARCHITECTURE_DIR_SQL = (
    "INSERT INTO codemig_task_directory_existing_architecture (file_id,"
    " type, architecture_path) VALUES (?, 1, ?)")

# """
# request_id 用于关联一次AI请求
# act_file_path 执行的文件路径
# mode ai模型
# run_time 执行时间
# suggestion ai建议内容
# score ai任务得分 低0到高4, 默认5未评价
# finished ai任务是否完成 running completed abnormal stopped
# stage v4.x：项目级阶段标记（project_migrate/ut_test；历史数据可能还有
#   mca_optimize——性能优化阶段已下线，查询侧按"最近一次"语义兜底展示），
#   用于刷新后按阶段恢复 AI 面板输出与前端阶段历史切换；
#   NULL/空串 = 旧数据（历史遗留记录，按"最近一次"语义兜底展示）
# """
TASK_AI_TABLE_NAME = "codemig_task_ai"
TASK_AI_SCHEMA = (
    "ai_id INTEGER PRIMARY KEY AUTOINCREMENT,"
    "file_id INTEGER NOT NULL,"
    "request_id TEXT NOT NULL,"
    "act_file_path TEXT NOT NULL,"
    "mode TEXT NOT NULL,"
    "run_time TEXT NOT NULL,"
    "suggestion TEXT NOT NULL,"
    "cmd TEXT NOT NULL,"
    "score INTEGER NOT NULL DEFAULT 5 CHECK (score IN (0, 1, 2, 3, 4, 5)),"
    "finished TEXT NOT NULL,"
    "stage TEXT,"
    "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
)
TASK_AI_KEY_INDEX = ("""
    CREATE UNIQUE INDEX IF NOT EXISTS codemig_task_ai_key_index
    ON codemig_task_ai(file_id, ai_id, request_id);
""")
CREATE_TASK_AI_TABLE_SQL = (
    f"CREATE TABLE IF NOT EXISTS {TASK_AI_TABLE_NAME} "
    f"({TASK_AI_SCHEMA})"
)

# v4.x 增量迁移：老库的 codemig_task_ai 没有 stage 列。SQLite 的
# ADD COLUMN 没有 IF NOT EXISTS，重复执行会报 duplicate column——
# 调用方捕获该错误后忽略即可（幂等）。
ALTER_TASK_AI_ADD_STAGE_SQL = (
    f"ALTER TABLE {TASK_AI_TABLE_NAME} ADD COLUMN stage TEXT"
)

INSTER_AI_RESULT_SQL = (
    "INSERT INTO codemig_task_ai "
    "(file_id, request_id, act_file_path, mode, cmd, finished, run_time, suggestion) "
    "VALUES (?, ?, ?, ?, ?, 'running', '', '')"
)

UPDATE_AI_RESULT_SQL = (
    "UPDATE codemig_task_ai "
    "SET suggestion = ?, run_time = ?, finished = ? "
    "WHERE request_id = ?"
)

SELECT_AI_FINISHED_SQL = (
    "SELECT finished FROM codemig_task_ai WHERE ai_id = ?"
)

SELECT_MAX_AI_ID_BY_FILE_SQL = (
    "SELECT MAX(ai_id) FROM codemig_task_ai WHERE file_id = ?"
)

# v4.x：按阶段取项目级（file_id=0）最近一次记录 id；
# stage 为 None 时不过滤 = 最近一次（任意阶段，兼容旧行为）。
SELECT_MAX_PROJECT_AI_ID_BY_STAGE_SQL = (
    "SELECT MAX(ai_id) FROM codemig_task_ai "
    "WHERE file_id = 0 AND (? IS NULL OR stage = ?)"
)

# v4.x：项目级（file_id=0）阶段历史列表，供前端切换器展示。
# 只回元信息（不含 suggestion 大字段），按时间倒序。
SELECT_PROJECT_AI_HISTORY_SQL = (
    "SELECT ai_id, stage, mode, run_time, finished, request_id, created_at "
    "FROM codemig_task_ai WHERE file_id = 0 "
    "ORDER BY ai_id DESC LIMIT 50"
)

SELECT_AI_SUGGESTION_SQL = (
    "SELECT suggestion FROM codemig_task_ai WHERE ai_id = ?"
)

SET_AI_SCORE_SQL = (
    "UPDATE codemig_task_ai "
    "SET score = ? "
    "WHERE ai_id = ?"
)

SELECT_AI_SCORE_SQL = (
    "SELECT score FROM codemig_task_ai WHERE ai_id = ?"
)

SELECT_AI_SCORE_BY_UUID_SQL = (
    "SELECT score FROM codemig_task_ai WHERE request_id = ?"
)

# 查询运行中 AI 任务的 request_id 列表（项目级迁移/UT/MCA/单文件 Agent 共用）。
# request_id 即 request_uuid，容器名规则为 docker_{request_uuid}，
# 调用方逐条 docker inspect 校验容器是否真的在跑（见 is_ai_task_running）。
SELECT_RUNNING_AI_REQUEST_IDS_SQL = (
    "SELECT request_id FROM codemig_task_ai WHERE finished = 'running'"
)

# ─── v4.2：保存时行号重绑定 ───
# 查询某 file 的所有 suggestion（含 manual），用于保存时遍历重绑定。
# 区别于 SELECT_SUGGESTION_SQL：那个 is_manual=0 只查 AI 建议；
# 这个 is_manual IN (0, 1) 都查。
SELECT_ALL_SUGGESTIONS_BY_FILE_SQL = ("""
    SELECT change_id, start_line_number, end_line_number, is_manual
    FROM codemig_task_directory_file_suggestion
    WHERE file_id = ? AND ignored = 0
    ORDER BY start_line_number ASC
""")

# 更新某条 suggestion 的行号
UPDATE_SUGGESTION_LINE_SQL = ("""
    UPDATE codemig_task_directory_file_suggestion
    SET start_line_number = ?, end_line_number = ?
    WHERE change_id = ?
""")

# 按 change_id 删除 suggestion（行号失效时的清理）
# 静态单条语句，调用方用 executemany 批量传参，避免动态拼接 SQL 结构
DELETE_SUGGESTION_BY_CHANGE_ID_SQL = (
    "DELETE FROM codemig_task_directory_file_suggestion "
    "WHERE change_id = ?"
)
