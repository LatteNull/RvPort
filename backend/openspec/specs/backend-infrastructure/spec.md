## Purpose

定义 RvPort 后端 MVP 本地基础设施的 Docker 启动方式、环境变量边界、服务职责和运行期目录约定。
## Requirements
### Requirement: 本地基础设施通过 Docker Compose 启动
RvPort SHALL 提供根目录 `docker-compose.yml`，用于启动后端 MVP 所需的 PostgreSQL、RabbitMQ 和 Redis 基础设施。

#### Scenario: 开发者启动基础设施
- **WHEN** 开发者在项目根目录运行 Docker Compose 启动命令
- **THEN** Compose 配置 SHALL 启动 PostgreSQL、RabbitMQ 和 Redis 服务
- **AND** 这些服务 SHALL 位于同一个 Compose 网络内

#### Scenario: 后端服务按服务名访问基础设施
- **WHEN** 后续 API 或 worker 容器加入同一 Compose 网络
- **THEN** 它们 SHALL 能通过 `postgres`、`rabbitmq` 和 `redis` 服务名访问对应基础设施

### Requirement: 基础设施配置通过环境变量管理
Docker Compose 配置 SHALL 通过根目录 `.env` 读取本地私有配置，并 SHALL 提供 `.env.example` 作为可提交模板。

#### Scenario: 提供配置模板
- **WHEN** 开发者首次配置本地环境
- **THEN** 根目录 `.env.example` SHALL 包含数据库、队列、缓存、端口和本地目录相关变量
- **AND** `.env.example` MUST NOT 包含真实密码

#### Scenario: 保护本地私有配置
- **WHEN** 开发者填写真实基础设施密码或本地路径
- **THEN** 这些值 SHALL 写入根目录 `.env`
- **AND** `.env` MUST 被版本控制忽略

### Requirement: PostgreSQL 使用当前稳定版本并启用 pgcrypto
基础设施 SHALL 使用 PostgreSQL 当前稳定镜像，并 SHALL 为后端数据库启用 `pgcrypto` 扩展。

#### Scenario: 启动 PostgreSQL
- **WHEN** Compose 启动 PostgreSQL 服务
- **THEN** 服务 SHALL 使用 `postgres:18.4`
- **AND** 数据 SHALL 持久化到命名卷
- **AND** 容器内数据卷挂载点 SHALL 覆盖 `/var/lib/postgresql`

#### Scenario: 初始化数据库扩展
- **WHEN** PostgreSQL 初始化脚本执行
- **THEN** 初始化脚本 SHALL 执行 `CREATE EXTENSION IF NOT EXISTS pgcrypto`
- **AND** 该脚本 SHALL 可重复执行

### Requirement: RabbitMQ 作为异步任务投递队列
基础设施 SHALL 使用 RabbitMQ 作为异步任务投递队列，并 SHALL 保持队列载荷最小化。

#### Scenario: 启动 RabbitMQ
- **WHEN** Compose 启动 RabbitMQ 服务
- **THEN** 服务 SHALL 使用 `rabbitmq:4.3.2-management`
- **AND** SHALL 暴露 AMQP 端口和本地管理界面端口
- **AND** RabbitMQ 用户、密码和 vhost SHALL 从环境变量读取

#### Scenario: 投递任务消息
- **WHEN** 后端 API 创建长任务并投递队列
- **THEN** RabbitMQ 消息载荷 SHALL 只包含 `task_id` 和必要路由信息
- **AND** RabbitMQ MUST NOT 作为任务输入、任务状态、任务进度、任务结果或日志的事实来源
- **AND** 后端 SHALL 通过统一任务队列客户端投递 RabbitMQ 消息

#### Scenario: 配置任务队列路由
- **WHEN** 后端应用启动
- **THEN** 任务队列 exchange、queue 和 routing key SHALL 可通过环境变量配置

#### Scenario: 使用集群友好的任务队列类型
- **WHEN** 后端声明 RabbitMQ 任务队列
- **THEN** 任务队列 SHALL 声明为 durable queue
- **AND** 任务队列 SHOULD 使用 `x-queue-type = quorum`
- **AND** 任务消息 SHOULD 使用 persistent delivery mode

#### Scenario: 使用手动确认消费模式
- **WHEN** 后续 worker 消费 RabbitMQ 任务队列消息
- **THEN** RabbitMQ listener ack mode SHOULD 配置为 manual
- **AND** 消息确认 SHOULD 发生在 worker 已完成必要处理并写回 PostgreSQL 之后

### Requirement: RabbitMQ 必须支持 worker 定点取消队列
基础设施 SHALL 为运行中任务取消提供独立 RabbitMQ exchange、worker 专属取消队列和取消 DLQ。

#### Scenario: 配置取消队列路由
- **WHEN** 后端应用启动
- **THEN** 取消 exchange、routing key 前缀、队列名前缀、DLQ、mandatory publish 和 publisher return SHALL 可通过环境变量配置
- **AND** 默认配置 SHALL 与既有任务队列配置互相独立

#### Scenario: Worker 声明专属取消队列
- **WHEN** worker 实例启动并生成 `workerInstanceId`
- **THEN** worker SHALL 声明只服务当前实例的取消队列
- **AND** SHALL 绑定到取消 exchange 的 `worker.cancel.<workerInstanceId>` routing key
- **AND** 取消队列 SHALL 具备明确生命周期控制，避免 worker 下线后废弃队列长期堆积

#### Scenario: 取消消息无法路由
- **WHEN** 后端向取消 exchange 投递取消消息但没有队列匹配 routing key
- **THEN** RabbitMQ publisher return SHALL 被后端捕获
- **AND** 后端 SHALL 将对应 runtime handle 标记为路由不可达或 worker 不存在
- **AND** 后端 MUST NOT 把 publish 成功等同于取消消息已被目标 worker 接收

#### Scenario: 使用集群友好的取消队列配置
- **WHEN** 后端声明取消队列
- **THEN** 取消队列 SHALL 使用 durable 或具备明确生命周期控制的队列配置
- **AND** 取消消息 SHOULD 使用 persistent delivery mode
- **AND** 取消队列 SHOULD 配置 dead-letter exchange

#### Scenario: 使用手动确认取消消息
- **WHEN** worker 消费取消队列消息
- **THEN** RabbitMQ listener ack mode SHALL 配置为 manual
- **AND** 消息确认 SHALL 发生在取消清理状态已经可靠写回 PostgreSQL 之后

#### Scenario: 取消消息进入 DLQ
- **WHEN** 取消清理超过最大重试次数或出现不可恢复错误
- **THEN** 取消消息 SHALL 进入取消 DLQ
- **AND** 后端 SHALL 在 runtime handle 中记录清理失败状态

### Requirement: Redis 作为缓存而不是事实来源
基础设施 SHALL 使用 Redis 作为缓存和短期状态存储，但 SHALL NOT 作为业务事实来源。

#### Scenario: 启动 Redis
- **WHEN** Compose 启动 Redis 服务
- **THEN** 服务 SHALL 使用 `redis:8.8.0`
- **AND** Redis 端口和密码 SHALL 从环境变量读取

#### Scenario: 使用 Redis 缓存
- **WHEN** 后端需要缓存登录态、token、短期 nonce 或限流计数
- **THEN** 后端 MAY 使用 Redis 保存这些短期数据
- **AND** Redis 数据失效或丢失 MUST NOT 破坏 PostgreSQL 中的权威业务状态
- **AND** 后端业务缓存 SHOULD 通过统一 Redis 缓存客户端访问

#### Scenario: 避免 Redis 承载任务事实
- **WHEN** 任务状态、任务事件、任务结果或审计记录需要保存
- **THEN** 系统 MUST 使用 PostgreSQL 作为事实来源
- **AND** 系统 MUST NOT 依赖 Redis 作为任务队列

#### Scenario: 配置业务缓存命名空间
- **WHEN** 后端应用启动
- **THEN** Redis 业务缓存 namespace SHALL 可通过环境变量配置
- **AND** Redis 业务缓存 namespace SHALL 与 Spring Session namespace 分离

#### Scenario: 使用可读 Redis key
- **WHEN** 后端业务缓存客户端写入 Redis key
- **THEN** Redis key SHALL 使用字符串序列化
- **AND** Redis key MUST NOT 因 JDK 或 JSON key 序列化产生不可读二进制前缀

### Requirement: 本地运行期文件目录可配置
基础设施配置 SHALL 为日志、归档和上传文件提供可配置的本地目录变量。

#### Scenario: 配置本地日志目录
- **WHEN** 开发者复制 `.env.example` 创建 `.env`
- **THEN** 配置 SHALL 包含 `RVPORT_LOG_DIR`、`RVPORT_ARCHIVE_DIR` 和 `RVPORT_UPLOAD_DIR`
- **AND** 默认值 SHALL 指向 `backend/runtime` 下的对应目录

#### Scenario: 保存完整任务日志
- **WHEN** 后续 worker 写入完整 stdout 或 stderr 日志
- **THEN** 日志 SHOULD 写入 `RVPORT_LOG_DIR` 指向的目录
- **AND** PostgreSQL 只保存日志元数据和摘要

### Requirement: 基础设施文档使用中文说明边界
RvPort SHALL 在 `backend/docs/INFRASTRUCTURE.md` 维护中文基础设施文档，说明启动方式、环境变量和服务职责边界。

#### Scenario: 阅读基础设施文档
- **WHEN** 开发者查看 `backend/docs/INFRASTRUCTURE.md`
- **THEN** 文档 SHALL 说明如何复制 `.env.example`、如何启动和停止 Docker Compose
- **AND** 文档 SHALL 说明 PostgreSQL、RabbitMQ 和 Redis 的职责边界
- **AND** 文档 SHALL 说明 `.env` 不应提交到版本控制

### Requirement: 基础设施必须提供 MinIO 对象存储
RvPort 本地 Docker Compose SHALL 提供 MinIO 服务，用于保存后端运行产生的输出制品。

#### Scenario: 启动 MinIO
- **WHEN** 开发者在项目根目录启动 Docker Compose
- **THEN** Compose 配置 SHALL 启动 MinIO 服务
- **AND** MinIO 数据 SHALL 持久化到命名卷
- **AND** MinIO SHALL 加入后端所在 Compose 网络
- **AND** 后端 SHALL 能通过服务名访问 MinIO

#### Scenario: 暴露 MinIO 控制台
- **WHEN** Compose 启动 MinIO
- **THEN** MinIO API 端口和 Console 端口 SHALL 可通过环境变量配置
- **AND** 本地默认端口 SHALL 避免与现有 PostgreSQL、RabbitMQ、Redis、后端和前端端口冲突

#### Scenario: 配置 MinIO 凭据
- **WHEN** 开发者复制 `.env.example` 创建 `.env`
- **THEN** `.env.example` SHALL 包含 MinIO root 用户、root 密码、bucket 和端口变量
- **AND** `.env.example` MUST NOT 包含真实生产凭据

### Requirement: 后端对象存储配置必须通过环境变量管理
后端 SHALL 通过环境变量读取对象存储连接信息。

#### Scenario: 配置对象存储连接
- **WHEN** 后端容器启动
- **THEN** 后端 SHALL 读取对象存储 endpoint、bucket、region、access key、secret key 和 path-style 配置
- **AND** 本地默认配置 SHALL 指向 Compose 中的 MinIO 服务

#### Scenario: 对象存储健康依赖
- **WHEN** 后端依赖对象存储保存运行制品
- **THEN** Compose SHALL 为 MinIO 配置健康检查
- **AND** 后端服务 SHOULD 在 MinIO 健康后启动

### Requirement: 后端容器必须支持多 Agent Runtime
后端 Docker 构建 SHALL 支持 Codex、DeepSeek Harness 和 OpenCode 三类 agent runtime 的可执行入口，使测试结果比较可以在容器内运行选定 agent。

#### Scenario: 构建包含 Codex runtime
- **WHEN** 构建后端 Docker 镜像
- **THEN** 镜像 SHALL 提供 Codex CLI 可执行入口或明确的安装失败诊断
- **AND** 默认 Codex runtime executable SHALL 可通过环境变量覆盖

#### Scenario: 构建包含 DeepSeek Harness runtime
- **WHEN** 构建后端 Docker 镜像
- **THEN** 镜像 SHALL 提供 DeepSeek Harness 可执行入口或明确的安装失败诊断
- **AND** DeepSeek Harness runtime executable SHALL 可通过环境变量覆盖

#### Scenario: 构建包含 OpenCode runtime
- **WHEN** 构建后端 Docker 镜像
- **THEN** 镜像 SHALL 提供 OpenCode 可执行入口或明确的安装失败诊断
- **AND** OpenCode runtime executable SHALL 可通过环境变量覆盖

#### Scenario: Runtime 不可用
- **WHEN** 容器内某个 agent 可执行文件不存在或无法运行
- **THEN** 后端 SHALL 在 agent runtime 探测中返回不可用状态
- **AND** 后端 MUST NOT 在应用启动时因为某个非默认 agent 缺失而整体启动失败

#### Scenario: Maven 依赖缓存不受 agent 安装影响
- **WHEN** 后端 Docker 构建安装 agent CLI
- **THEN** 构建过程 SHALL 继续使用已有 Maven 依赖缓存策略
- **AND** agent 安装层 SHOULD 与 Maven 依赖下载层解耦，减少无关变更导致的重复下载

### Requirement: 后端部署必须支持 API 和 worker 运行角色拆分
后端基础设施 SHALL 支持同一后端镜像以 API 节点或 worker 节点运行，并 SHALL 允许部署平台自行管理 worker 副本数量。

#### Scenario: API 节点部署
- **WHEN** 后端容器以 API 模式启动
- **THEN** 容器 SHALL 对外提供 HTTP API
- **AND** 容器 MUST NOT 消费 RabbitMQ 任务队列

#### Scenario: Worker 节点部署
- **WHEN** 后端容器以 worker 模式启动
- **THEN** 容器 SHALL 消费 RabbitMQ 任务队列并执行任务
- **AND** 容器 SHOULD 不对外暴露 HTTP 服务

#### Scenario: 不控制部署平台 scale
- **WHEN** 管理员需要增加或减少 worker 容器副本数量
- **THEN** RvPort 后端 MUST NOT 直接调用 Docker Swarm 或 Kubernetes scale API
- **AND** worker 副本数量 SHALL 由部署平台或运维流程管理

### Requirement: API 和 worker 节点必须共享 runtime 存储
后端部署 SHALL 确保 API 节点和 worker 节点能够访问同一套 runtime 日志、源码、上传文件和报告路径。

#### Scenario: 共享 runtime volume
- **WHEN** API 节点和 worker 节点分别运行在不同容器
- **THEN** 部署配置 SHALL 将 `RVPORT_LOG_DIR`、`RVPORT_ARCHIVE_DIR`、`RVPORT_UPLOAD_DIR`、`RVPORT_SOURCE_DIR`、`RVPORT_SBOM_WORK_DIR` 和 `RVPORT_KB_SCAN_OUTPUT_DIR` 指向共享存储
- **AND** API 节点 SHALL 能读取 worker 写入的日志和报告制品引用

#### Scenario: 未配置共享存储
- **WHEN** API 节点无法访问 worker 写入的 runtime 文件
- **THEN** 对应日志或制品 API SHALL 返回受控错误
- **AND** 响应 MUST NOT 暴露容器内部真实敏感路径

### Requirement: RabbitMQ 任务 listener prefetch 必须固定为一
后端基础设施 SHALL 将任务队列 listener 的 prefetch 固定为 `1`，避免长任务预取囤积。

#### Scenario: 声明 listener prefetch
- **WHEN** worker 节点启动 RabbitMQ 任务 listener
- **THEN** listener container SHALL 使用 `prefetch=1`
- **AND** 该值 MUST NOT 通过 `.env`、Compose 环境变量或管理员 API 暴露为可编辑配置

### Requirement: 后端镜像必须包含 KB Scanner schema v2 运行环境
后端 Docker 镜像 SHALL 安装新版 KB Scanner 所需的系统依赖和隔离 Python 依赖。

#### Scenario: 构建后端生产镜像
- **WHEN** 构建后端 Docker 镜像
- **THEN** 镜像 SHALL 安装 `python3`、`python3-venv`、`clang-18`、`libclang-18-dev` 和 `python3-clang-18`
- **AND** 镜像 SHALL 创建专用于 KB Scanner 的 Python venv
- **AND** venv SHALL 安装 `tools/kb-scanner/requirements/runtime.lock` 中固定的依赖
- **AND** 镜像 SHALL 复制新版 `tools/kb-scanner` 到运行目录

#### Scenario: 运行时导入 scanner 依赖
- **WHEN** 后端容器启动后执行 KB Scanner
- **THEN** 配置的 Python 命令 SHALL 指向 KB Scanner venv
- **AND** 该 Python SHALL 能导入 `kb_scanner`、`tree_sitter` 和 `clang.cindex`
- **AND** 依赖导入失败 SHALL 使扫描任务失败并记录明确日志

### Requirement: 后端配置必须显式声明 KB Scanner venv Python
后端运行配置 SHALL 能区分系统 Python 和 KB Scanner venv Python。

#### Scenario: Compose 启动后端与 worker
- **WHEN** 使用 docker compose 启动后端 API 和 worker
- **THEN** 两类进程 SHALL 使用相同的 KB Scanner Python 命令配置
- **AND** worker 执行扫描任务时 SHALL 使用容器内 venv Python
- **AND** 本地开发仍 MAY 覆盖该 Python 命令指向开发机环境

### Requirement: 后端容器必须提供 UTF-8 原生运行环境
后端运行镜像 SHALL 为 API、Worker 及其子进程提供一致的 UTF-8 locale，使 JVM 原生编码和 Agent CLI 文本边界支持完整 Unicode 内容。

#### Scenario: 启动 API 容器
- **WHEN** 使用后端运行镜像启动 API 进程
- **THEN** 容器 SHALL 设置有效的 UTF-8 `LANG` 和 `LC_ALL`
- **AND** JVM `native.encoding` 与 `sun.jnu.encoding` SHALL 为 UTF-8

#### Scenario: 启动 Worker 容器
- **WHEN** 使用同一后端运行镜像启动 Worker 进程
- **THEN** 容器 SHALL 设置与 API 进程相同的 UTF-8 locale
- **AND** Worker 启动的 Codex、DeepSeek Harness 和 OpenCode 子进程 SHALL 继承 UTF-8 locale

#### Scenario: 容器内执行中文子进程参数闭环
- **WHEN** 后端容器内的 JVM 启动子进程并传递非 ASCII 受控参数
- **THEN** 子进程接收到的 Unicode 内容 SHALL 与 Java 原始字符串一致
- **AND** 镜像验证 MUST NOT 仅检查 `file.encoding` 而忽略原生编码

### Requirement: Worker 镜像必须固定安装两个分析工具
backend-worker 镜像 SHALL 安装固定版本的浮点精度扫描 Python 包、memory-order Python 模块、`fp-ir-worker`、`moa-worker`、`memory-order-source-worker` 以及所需 LLVM/Clang 21 运行库；API-only 进程 MAY 不安装这些工具。

#### Scenario: 构建 Worker 镜像
- **WHEN** 构建 backend-worker 镜像
- **THEN** 多阶段构建 SHALL 编译并复制三个 C++ worker
- **AND** Python 依赖 SHALL 安装到固定只读隔离环境或固定模块目录

#### Scenario: 离线运行
- **WHEN** Worker 执行专项分析
- **THEN** 工具 MUST NOT 在运行时从网络安装依赖
- **AND** MUST NOT 依赖宿主机源码挂载或 Docker socket

### Requirement: Worker 必须暴露分析工具健康状态
Worker SHALL 在启动时执行版本和 doctor 检查，并 SHALL 将每个分析器的可用性、版本和失败原因提供给 readiness 使用。

#### Scenario: 工具完整可用
- **WHEN** Python CLI、锁定 schema、LLVM 动态库和对应 C++ worker 均可用
- **THEN** 该分析器健康状态 SHALL 为 AVAILABLE

#### Scenario: 缺少运行组件
- **WHEN** CLI、动态库或 C++ worker 缺失或版本不兼容
- **THEN** 健康状态 SHALL 为 UNAVAILABLE 并包含安全原因码
- **AND** 创建分析任务 SHALL 被阻止

### Requirement: 分析运行资源必须可配置且受限
系统 SHALL 为 workspace、cache、执行超时、输出大小、解压大小、文件数量和并发设置安全默认值与环境变量配置。

#### Scenario: 输出超过预算
- **WHEN** 工具输出或解压内容超过配置预算
- **THEN** Worker SHALL 停止导入并清理临时目录
- **AND** 任务 SHALL 以明确资源限制原因失败

#### Scenario: cache 不共享
- **WHEN** 多个 Worker 使用各自本地 cache
- **THEN** cache miss MAY 导致重复计算
- **AND** MUST NOT 改变分析语义或结果身份
