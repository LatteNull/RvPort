CREATE TABLE IF NOT EXISTS sysconfig
(
    id INT PRIMARY KEY AUTO_INCREMENT,
    config_name VARCHAR(255) UNIQUE,
    config_value TEXT
);

INSERT INTO sysconfig (config_name, config_value)
SELECT 'max_online_users', '10' WHERE NOT EXISTS (SELECT 1 FROM sysconfig WHERE config_name = 'max_online_users');
INSERT INTO sysconfig (config_name, config_value)
SELECT 'session_timeout', '30' WHERE NOT EXISTS (SELECT 1 FROM sysconfig WHERE config_name = 'session_timeout');
INSERT INTO sysconfig (config_name, config_value)
SELECT 'max_password_failed', '5' WHERE NOT EXISTS (SELECT 1 FROM sysconfig WHERE config_name =  'max_password_failed');
INSERT INTO sysconfig (config_name, config_value)
SELECT 'password_timeout', '0' WHERE NOT EXISTS (SELECT 1 FROM sysconfig WHERE config_name = 'password_timeout');
INSERT INTO sysconfig (config_name, config_value)
SELECT 'lock_time', '3' WHERE NOT EXISTS (SELECT 1 FROM sysconfig WHERE config_name = 'lock_time');
INSERT INTO sysconfig (config_name, config_value)
SELECT 'log_save_time', '31' WHERE NOT EXISTS (SELECT 1 FROM sysconfig WHERE config_name = 'log_save_time');
INSERT INTO sysconfig (config_name, config_value)
SELECT 'task_per_user', '30' WHERE NOT EXISTS (SELECT 1 FROM sysconfig WHERE config_name = 'task_per_user');
INSERT INTO sysconfig (config_name, config_value)
SELECT 'docker_http_proxy', '' WHERE NOT EXISTS (SELECT 1 FROM sysconfig WHERE config_name = 'docker_http_proxy');
INSERT INTO sysconfig (config_name, config_value)
SELECT 'docker_https_proxy', '' WHERE NOT EXISTS (SELECT 1 FROM sysconfig WHERE config_name = 'docker_https_proxy');
INSERT INTO sysconfig (config_name, config_value)
SELECT 'docker_no_proxy', '' WHERE NOT EXISTS (SELECT 1 FROM sysconfig WHERE config_name = 'docker_no_proxy');

CREATE TABLE IF NOT EXISTS user_manager(
    id INT PRIMARY KEY AUTO_INCREMENT,
    password VARCHAR(128),
    user_id VARCHAR(64) UNIQUE,
    user_name VARCHAR(32),
    role VARCHAR(6),
    is_first_login INT,
    create_time DATETIME,
    last_login INT,
    last_login_ip VARCHAR(64),
    time_pw_reset INT,
    last_logout INT,
    status VARCHAR(32) DEFAULT 'normal',
    workspace VARCHAR(255),
    provider_id INT DEFAULT -1,
    infos VARCHAR(255)
);

CREATE TABLE IF NOT EXISTS user_failedlogin(
    id INT PRIMARY KEY AUTO_INCREMENT,
    user_name VARCHAR(64),
    failed_time INT
);

CREATE TABLE IF NOT EXISTS user_ip_failedlogin(
    id INT PRIMARY KEY AUTO_INCREMENT,
    ip_addr VARCHAR(60),
    failed_time INT,
    locked INT DEFAULT 0
);

CREATE TABLE IF NOT EXISTS user_login_failed_time(
    id INT PRIMARY KEY AUTO_INCREMENT,
    user_id VARCHAR(64),
    ip VARCHAR(60),
    failed_time DATETIME
);

CREATE TABLE IF NOT EXISTS user_password_history (
    id INT PRIMARY KEY AUTO_INCREMENT,
    user_id VARCHAR(64),
    password VARCHAR(128),
    created_at BIGINT,
    FOREIGN KEY(user_id) REFERENCES user_manager(user_id)
);

CREATE TABLE IF NOT EXISTS weakpassword (
    id INT PRIMARY KEY AUTO_INCREMENT,
    weak_password VARCHAR(100) NOT NULL
);

-- 弱密码种子数据
INSERT IGNORE INTO weakpassword (id, weak_password) VALUES (1, 'Admin123#');
INSERT IGNORE INTO weakpassword (id, weak_password) VALUES (2, 'admin123#');
INSERT IGNORE INTO weakpassword (id, weak_password) VALUES (3, 'Root123#');
INSERT IGNORE INTO weakpassword (id, weak_password) VALUES (4, 'root123#');
INSERT IGNORE INTO weakpassword (id, weak_password) VALUES (5, 'Admin123!');
INSERT IGNORE INTO weakpassword (id, weak_password) VALUES (6, 'admin123!');
INSERT IGNORE INTO weakpassword (id, weak_password) VALUES (7, 'root123!');
INSERT IGNORE INTO weakpassword (id, weak_password) VALUES (8, 'Root123!');
INSERT IGNORE INTO weakpassword (id, weak_password) VALUES (9, 'Admin@123');
INSERT IGNORE INTO weakpassword (id, weak_password) VALUES (10, 'admin@123');
INSERT IGNORE INTO weakpassword (id, weak_password) VALUES (11, 'Root@123');
INSERT IGNORE INTO weakpassword (id, weak_password) VALUES (12, 'root@123');
INSERT IGNORE INTO weakpassword (id, weak_password) VALUES (13, 'Admin123');
INSERT IGNORE INTO weakpassword (id, weak_password) VALUES (14, 'admin123');
INSERT IGNORE INTO weakpassword (id, weak_password) VALUES (15, 'Admin_123');
INSERT IGNORE INTO weakpassword (id, weak_password) VALUES (16, 'admin_123');
INSERT IGNORE INTO weakpassword (id, weak_password) VALUES (17, 'Root_123');
INSERT IGNORE INTO weakpassword (id, weak_password) VALUES (18, 'root_123');
INSERT IGNORE INTO weakpassword (id, weak_password) VALUES (19, 'Password123');
INSERT IGNORE INTO weakpassword (id, weak_password) VALUES (20, 'Password@123');
INSERT IGNORE INTO weakpassword (id, weak_password) VALUES (21, 'Password_123');
INSERT IGNORE INTO weakpassword (id, weak_password) VALUES (22, 'Password123!');
INSERT IGNORE INTO weakpassword (id, weak_password) VALUES (23, 'Admin@9000');
INSERT IGNORE INTO weakpassword (id, weak_password) VALUES (29, 'Admin123@');
INSERT IGNORE INTO weakpassword (id, weak_password) VALUES (30, 'admin123@');
INSERT IGNORE INTO weakpassword (id, weak_password) VALUES (31, 'Root123@');
INSERT IGNORE INTO weakpassword (id, weak_password) VALUES (32, 'root123@');
INSERT IGNORE INTO weakpassword (id, weak_password) VALUES (33, 'A12345678');
INSERT IGNORE INTO weakpassword (id, weak_password) VALUES (34, 'qweasdzxc123');
INSERT IGNORE INTO weakpassword (id, weak_password) VALUES (35, 'woaini1314');
INSERT IGNORE INTO weakpassword (id, weak_password) VALUES (36, 'a123456789');
INSERT IGNORE INTO weakpassword (id, weak_password) VALUES (37, 'abc123456');
INSERT IGNORE INTO weakpassword (id, weak_password) VALUES (38, 'aa123456');
INSERT IGNORE INTO weakpassword (id, weak_password) VALUES (39, 'aini1314');
INSERT IGNORE INTO weakpassword (id, weak_password) VALUES (40, 'woaini521');
INSERT IGNORE INTO weakpassword (id, weak_password) VALUES (41, 'woaini520');
INSERT IGNORE INTO weakpassword (id, weak_password) VALUES (42, 'qwe123456');
INSERT IGNORE INTO weakpassword (id, weak_password) VALUES (43, '123456789abc');
INSERT IGNORE INTO weakpassword (id, weak_password) VALUES (44, '123456..');
INSERT IGNORE INTO weakpassword (id, weak_password) VALUES (45, 'wang123456');
INSERT IGNORE INTO weakpassword (id, weak_password) VALUES (46, 'woaini1314520');
INSERT IGNORE INTO weakpassword (id, weak_password) VALUES (47, '1q2w3e4r5t');
INSERT IGNORE INTO weakpassword (id, weak_password) VALUES (48, '1234qwer');
INSERT IGNORE INTO weakpassword (id, weak_password) VALUES (49, 'as123456');
INSERT IGNORE INTO weakpassword (id, weak_password) VALUES (50, 'love1314');
INSERT IGNORE INTO weakpassword (id, weak_password) VALUES (51, 'zxcvbnm123');
INSERT IGNORE INTO weakpassword (id, weak_password) VALUES (52, 'aaa123!@#');
INSERT IGNORE INTO weakpassword (id, weak_password) VALUES (24, 'Zte12#');
INSERT IGNORE INTO weakpassword (id, weak_password) VALUES (25, 'Zte123@');
INSERT IGNORE INTO weakpassword (id, weak_password) VALUES (26, 'zte123@');
INSERT IGNORE INTO weakpassword (id, weak_password) VALUES (27, 'Zte@123');
INSERT IGNORE INTO weakpassword (id, weak_password) VALUES (28, 'zte@123');

-- 创建 plugin 表
CREATE TABLE IF NOT EXISTS plugin (
    id INT PRIMARY KEY AUTO_INCREMENT,
    plugin_type VARCHAR(255) NOT NULL,
    current_version VARCHAR(255),
    status INT,
    update_time DATETIME,
    progress_status INT,
    create_time DATETIME,
    plugin_meta_json TEXT,
    UNIQUE(plugin_type)
);

-- 创建 plugin_package 表
CREATE TABLE IF NOT EXISTS plugin_package (
    id INT PRIMARY KEY AUTO_INCREMENT,
    plugin_type VARCHAR(255) NOT NULL,
    package_version VARCHAR(255),
    package_status INT,
    release_data DATETIME,
    upload_time DATETIME,
    type VARCHAR(255),
    package_path TEXT
);

CREATE TABLE IF NOT EXISTS operation(
    id INT PRIMARY KEY AUTO_INCREMENT,
    user_id VARCHAR(64),
    user_name VARCHAR(64),
    ip VARCHAR(64),
    module VARCHAR(32),
    event VARCHAR(255),
    result VARCHAR(128),
    time DOUBLE,
    info VARCHAR(255),
    detail TEXT
);
CREATE TABLE IF NOT EXISTS operation_status(
    oversize INT DEFAULT 0
);

CREATE TABLE IF NOT EXISTS codemig_directory_storage (
    user_id VARCHAR(64) NOT NULL,
    dir_id INT PRIMARY KEY AUTO_INCREMENT,
    has_linked_task INT NOT NULL DEFAULT 0 CHECK (has_linked_task IN (0, 1)),
    has_removed INT NOT NULL DEFAULT 0 CHECK (has_removed IN (0, 1)),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX codemig_directory_storage_key_index
    ON codemig_directory_storage(user_id, dir_id);

--  status: 0 -> created, 1 -> processing, 2 -> success, 3 -> failed, 4 -> deleted
--  dependence_status: 0 -> created, 1 -> processing, 2 -> success, 3 -> failed
--  is_scan_dependence: 0 -> no, 1 -> yes
CREATE TABLE IF NOT EXISTS codemig_tasks (
    user_id VARCHAR(64) NOT NULL,
    task_id INT PRIMARY KEY AUTO_INCREMENT,
    task_name VARCHAR(128) NOT NULL,
    status INT NOT NULL DEFAULT 0,
    is_scan_dependence INT NOT NULL DEFAULT 0,
    dependence_status INT NOT NULL DEFAULT 0,
    fail_reason TEXT,
    python_interpreter TEXT,
    python_image_source TEXT,
    go_install_path TEXT,
    go_environment TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CHECK (LENGTH(task_name) <= 128),
    CHECK (is_scan_dependence IN (0, 1))
);

CREATE UNIQUE INDEX codemig_tasks_key_index
    ON codemig_tasks(user_id, task_id);

CREATE TABLE IF NOT EXISTS codemig_task_directory (
    task_id INT NOT NULL,
    dir_id INT NOT NULL,
    task_dir_id INT PRIMARY KEY AUTO_INCREMENT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (task_id) REFERENCES codemig_tasks(task_id),
    FOREIGN KEY (dir_id) REFERENCES codemig_directory_storage(dir_id)
);

CREATE UNIQUE INDEX codemig_task_directory_key_index
    ON codemig_task_directory(task_id, dir_id);

CREATE TABLE IF NOT EXISTS user_configuration (
    user_id VARCHAR(64) NOT NULL,
    configuration_id INT PRIMARY KEY AUTO_INCREMENT,
    python_interpreter TEXT,
    python_image_source TEXT,
    go_install_path TEXT,
    go_environment TEXT,
    create_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX user_configuration_key_index
    ON user_configuration(user_id);

--  status: 0 -> failed, 1 -> success
CREATE TABLE IF NOT EXISTS dependence_packages (
    dependence_id INT PRIMARY KEY AUTO_INCREMENT,
    dependence_package VARCHAR(255),
    version VARCHAR(255),
    status INT,
    fail_reason TEXT,
    dependence_package_path TEXT
);

CREATE INDEX dependence_packages_key_index
    ON dependence_packages(dependence_id);

CREATE TABLE IF NOT EXISTS codemig_task_dependence (
    user_id VARCHAR(64),
    task_id INT,
    dir_id INT,
    dependence_id INT,
    task_dependence_id INT PRIMARY KEY AUTO_INCREMENT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (task_id) REFERENCES codemig_tasks(task_id),
    FOREIGN KEY (dir_id) REFERENCES codemig_directory_storage(dir_id),
    FOREIGN KEY (dependence_id) REFERENCES dependence_packages(dependence_id)
);

CREATE INDEX codemig_task_dependence_key_index
    ON codemig_task_dependence(user_id, task_id);

CREATE TABLE IF NOT EXISTS file_dependence (
    dependence_id INT,
    file_id INT PRIMARY KEY AUTO_INCREMENT,
    type INT,
    file_path TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (dependence_id) REFERENCES dependence_packages(dependence_id)
);

CREATE INDEX file_dependence_key_index
    ON file_dependence(dependence_id);

CREATE TABLE IF NOT EXISTS file_dependence_suggestion (
    id INT PRIMARY KEY AUTO_INCREMENT,
    dependence_id INT,
    file_id INT NOT NULL,
    type INT NOT NULL,
    append_or_replace INT NOT NULL,
    start_line_number INT NOT NULL,
    end_line_number INT NOT NULL,
    suggestion TEXT NOT NULL,
    code_too_long INT,
    code TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (dependence_id) REFERENCES dependence_packages(dependence_id),
    FOREIGN KEY (file_id) REFERENCES file_dependence(file_id),
    CHECK (append_or_replace IN (0, 1, 2))
);

CREATE INDEX file_dependence_suggestion_key_index
    ON file_dependence_suggestion(dependence_id, file_id);

CREATE TABLE IF NOT EXISTS software_dependence_suggestion (
    id INT PRIMARY KEY AUTO_INCREMENT,
    dependence_id INT,
    file_id INT NOT NULL,
    support_architecture VARCHAR(255) NOT NULL,
    suggestion TEXT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (dependence_id) REFERENCES dependence_packages(dependence_id),
    FOREIGN KEY (file_id) REFERENCES file_dependence(file_id)
);

CREATE INDEX software_dependence_suggestion_key_index
    ON software_dependence_suggestion(dependence_id, file_id);

--  architecture_path 缺失文件对应的其他架构路径 例如 缺失file_riscv64.go 文件 对应 file_arm64.go 文件
CREATE TABLE IF NOT EXISTS dependence_existing_architecture (
    id INT PRIMARY KEY AUTO_INCREMENT,
    dependence_id INT,
    file_id INT NOT NULL,
    architecture_path TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    type INT DEFAULT 0,
    FOREIGN KEY (dependence_id) REFERENCES dependence_packages(dependence_id),
    FOREIGN KEY (file_id) REFERENCES file_dependence(file_id)
);

CREATE INDEX dependence_existing_architecture_key_index
    ON dependence_existing_architecture(dependence_id, file_id);

CREATE TABLE IF NOT EXISTS dependence_task (
    task_id INT,
    dir_id INT,
    pkg VARCHAR(255) NOT NULL,
    version VARCHAR(255),
    local_path TEXT,
    status INT DEFAULT 0,
    dependence_id INT,
    FOREIGN KEY (dependence_id) REFERENCES dependence_packages(dependence_id)
);

-- AI Assistant API Key 表
CREATE TABLE IF NOT EXISTS user_api_key (
    api_key_id INT PRIMARY KEY AUTO_INCREMENT,
    user_id VARCHAR(64) NOT NULL,
    api_key VARBINARY(255) NOT NULL,
    base_url VARCHAR(255) DEFAULT '',
    model VARCHAR(64) DEFAULT '',
    create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    api_format VARCHAR(64) DEFAULT '',
    others VARCHAR(255) DEFAULT '',
    is_default INT NOT NULL DEFAULT 0,
    CHECK (is_default IN (0, 1))
);

CREATE UNIQUE INDEX uk_user_api_key_api_key_model_user
    ON user_api_key(api_key, model, user_id);

-- 用户-模型选中关系表：严格按用户隔离记录"该用户在该 model 下选中哪条 api key"
CREATE TABLE IF NOT EXISTS user_model_selection (
    selection_id INT PRIMARY KEY AUTO_INCREMENT,
    user_id VARCHAR(64) NOT NULL,
    model VARCHAR(64) NOT NULL,
    api_key_id INT NOT NULL
);

CREATE UNIQUE INDEX uk_user_model_selection_user_model
    ON user_model_selection(user_id, model);

-- 用户默认API Key选择表：每个用户可以选择一个默认的API Key（替代全局 is_default）
CREATE TABLE IF NOT EXISTS user_default_selection (
    selection_id INT PRIMARY KEY AUTO_INCREMENT,
    user_id VARCHAR(64) NOT NULL UNIQUE,
    api_key_id INT NOT NULL
);
