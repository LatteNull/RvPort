## ADDED Requirements

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
