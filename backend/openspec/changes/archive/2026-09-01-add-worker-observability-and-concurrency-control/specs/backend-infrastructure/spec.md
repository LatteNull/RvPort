## ADDED Requirements

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
