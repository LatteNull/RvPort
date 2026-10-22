## ADDED Requirements

### Requirement: 后端镜像必须包含 KB Scanner schema v2 运行环境

后端 Docker 镜像 MUST 安装新版 KB Scanner 所需的系统依赖和隔离 Python 依赖。

#### Scenario: 构建后端生产镜像

- **WHEN** 构建后端 Docker 镜像
- **THEN** 镜像 MUST 安装 `python3`、`python3-venv`、`clang-18`、`libclang-18-dev` 和 `python3-clang-18`
- **AND** 镜像 MUST 创建专用于 KB Scanner 的 Python venv
- **AND** venv MUST 安装 `tools/kb-scanner/requirements/runtime.lock` 中固定的依赖
- **AND** 镜像 MUST 复制新版 `tools/kb-scanner` 到运行目录

#### Scenario: 运行时导入 scanner 依赖

- **WHEN** 后端容器启动后执行 KB Scanner
- **THEN** 配置的 Python 命令 MUST 指向 KB Scanner venv
- **AND** 该 Python MUST 能导入 `kb_scanner`、`tree_sitter` 和 `clang.cindex`
- **AND** 依赖导入失败 MUST 使扫描任务失败并记录明确日志

### Requirement: 后端配置必须显式声明 KB Scanner venv Python

后端运行配置 MUST 能区分系统 Python 和 KB Scanner venv Python。

#### Scenario: Compose 启动后端与 worker

- **WHEN** 使用 docker compose 启动后端 API 和 worker
- **THEN** 两类进程 MUST 使用相同的 KB Scanner Python 命令配置
- **AND** worker 执行扫描任务时 MUST 使用容器内 venv Python
- **AND** 本地开发仍 MAY 覆盖该 Python 命令指向开发机环境
