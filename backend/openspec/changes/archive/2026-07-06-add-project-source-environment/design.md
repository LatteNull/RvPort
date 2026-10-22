## Context

当前后端已经完成 Java/Spring Boot 工程骨架、Liquibase schema、jOOQ 生成代码、认证与本地用户管理、Redis session、RabbitMQ 投递、任务运行时、项目级 SSE 和凭据加密工具。数据库已经包含 `projects`、`source_revisions`、`source_imports`、`credentials`、`environments`、`environment_snapshots` 和 `environment_components`，但还没有对应的业务 API 和服务层。

项目、源码和环境是后续迁移流程的三条主干：

```text
项目
  ├─ 当前源码版本
  │   ├─ 压缩包导入
  │   └─ Git 同步
  ├─ 执行环境
  │   ├─ x86 源环境
  │   ├─ RISC-V 目标环境
  │   └─ 通用执行环境
  └─ 长任务
      ├─ 连接测试
      ├─ 环境采集
      └─ 远程脚本
```

已有 API 设计明确 `projects.stage` 只是导航提示，不是权威状态机。修复后的源码重新入库会创建新的源码版本，项目真实状态由 overview 聚合当前源码、环境、任务、扫描、构建、测试、报告等事实数据。

## Goals / Non-Goals

**Goals:**

- 实现项目列表、创建、详情、更新和概览 API。
- 实现源码版本列表、压缩包上传、Git 同步任务创建和当前版本切换 API。
- 实现环境列表、创建、详情、更新、连接测试任务、采集任务、远程脚本任务和快照列表 API。
- 支持环境配置可选跳板机，源机器或目标机器可以引用同项目内另一个已启用环境作为 SSH 跳转入口。
- 通过 `CredentialCipher` 加密保存 Git/SSH 业务凭据。
- 所有查询响应只返回凭据遮蔽摘要，不返回明文、密文或服务器本地路径。
- 将 Git 同步、环境连接测试、环境采集和远程脚本接入现有任务运行时。
- 补充服务层、仓储层、请求/响应 DTO、校验、审计和测试。

**Non-Goals:**

- 不实现完整 Git clone、checkout、解压校验、源码结构解析或文件级扫描。
- 不实现真实 SSH 连接、远程命令执行、环境采集解析或脚本结果归档。
- 不实现多级跳板机链路、动态代理池或复杂 SSH 路由策略；MVP 只支持单个跳板机引用。
- 不引入项目成员、角色、权限或用户角色映射。
- 除跳板机引用字段外，不新增其他数据库 schema。
- 不暴露通用 artifact API，也不暴露本地上传目录、工作目录或日志真实路径。

## Decisions

### 1. 按业务域拆分模块

新增 `project`、`source`、`environment` 和 `credential` 包，每个包内保持 Controller、Service、Repository、DTO 的清晰分层。项目概览属于 `project`，但可读取源码、环境和任务仓储。

理由：这三块会被后续 KB、SBOM、构建、测试、报告复用。按业务域拆分比把所有接口塞进一个工作台服务更容易扩展和测试。

备选方案是创建一个 `workspace` 或 `migration` 大模块统一承载。该方案短期文件少，但后续能力增长后边界会变模糊。

### 2. 项目访问边界先收敛为登录态

MVP 不做项目成员表，也不做角色权限系统。项目相关 API 先要求用户已登录；列表默认返回未软删除的活跃项目。超级管理员不获得额外项目授权语义，因为当前没有可配置的项目级授权模型。

理由：这与已有认证设计一致，避免提前设计半套权限系统。

后续如果需要项目级隔离，可以新增 `project_members` 或所有者范围策略，并作为独立 change 修改 API 和数据库设计。

### 3. `stage` 作为缓存式导航提示

创建项目时默认 `stage=PROJECT_CREATED`、`status=ACTIVE`。源码上传或 Git 同步创建成功后，可以根据动作将 `stage` 更新为 `SOURCE_IMPORTED`。环境创建后可以更新为 `ENV_CONFIGURED`，但 overview 不能只依赖 `stage`。

理由：`stage` 对前端默认入口有价值，但迁移流程会因为修复后源码重新入库而回退，不能当作线性状态机。

### 4. 源码压缩包先保存元数据和文件，不做深度解析

`POST /api/projects/{projectId}/sources/archive` 接收 multipart 文件，保存到 `RVPORT_UPLOAD_DIR` 下按项目和源码版本划分的目录，创建 `source_revisions` 和 `source_imports`。响应返回源码版本 ID 和导入记录状态，但不返回 `archive_path` 或 `working_copy_path`。

理由：前端和后续流程需要一个可引用的源码版本。源码包格式校验、解压、语言识别和启动扫描可以由后续任务处理器深化。

实现中应限制文件名使用安全归一化后的展示名，真实存储名使用 UUID，避免路径穿越。

### 5. Git 同步先创建任务和导入记录

`POST /api/projects/{projectId}/sources/git-sync` 校验 Git URL 不包含用户名、密码或 token；如果请求携带新凭据，则先加密保存为 `credentials`；随后创建 `source_imports` 和 `tasks`，并投递任务。完整 clone/checkout 由后续 Git worker handler 实现。

理由：Git 同步天然可能较慢或失败，应复用任务运行时。当前 change 的目标是打通业务骨架和安全边界，不把 Git 执行器混入。

### 6. 凭据使用嵌入式写入，不提供独立凭据管理页 API

环境创建/更新和 Git 同步请求可以携带凭据字段或引用已有 `credentialId`。后端统一通过 `CredentialService` 构造结构化 payload，调用 `CredentialCipher` 加密为 JSON 后写入 `credentials.encrypted_payload`。查询响应只返回：

```json
{
  "configured": true,
  "kind": "SSH_PASSWORD",
  "name": "rv-dev-01",
  "maskedSummary": "root@192.0.2.10"
}
```

理由：API 设计已经倾向不做独立全局凭据管理页面；嵌入式写入最贴近当前 UI 流程。

### 7. 环境长操作全部走任务运行时

连接测试、环境采集和远程脚本 API 不直接执行 SSH，而是创建 `tasks` 并投递队列。任务 input snapshot 只保存环境 ID、项目 ID、脚本摘要、超时等安全信息，不保存明文凭据。

建议任务类型：

- `ENV_TEST_CONNECTION`
- `ENV_COLLECT`
- `ENV_RUN_SCRIPT`
- `SOURCE_GIT_SYNC`

理由：任务运行时已经提供队列、SSE、日志、状态补偿和取消能力。复用它可以让前端交互保持一致。

### 8. 环境使用自引用字段表达跳板机

在 `environments` 表新增可空字段 `jump_host_environment_id uuid references environments(id)`。跳板机本身仍是一条普通环境记录，源环境或目标环境通过该字段引用跳板机。创建或更新环境时，后端必须校验：

- 跳板机环境存在。
- 跳板机和目标环境属于同一项目。
- 跳板机已启用。
- 环境不能引用自己作为跳板机。
- MVP 不允许多级跳板链路，即被选为跳板机的环境本身不能再配置跳板机。

查询环境详情和列表时返回跳板机摘要，例如：

```json
{
  "jumpHost": {
    "id": "env_jump_001",
    "name": "jump-01",
    "host": "192.0.2.10",
    "sshPort": 22,
    "username": "ops",
    "enabled": true
  }
}
```

任务 input snapshot 只保存 `jumpHostEnvironmentId`，不复制跳板机凭据或目标机凭据。

理由：把跳板机建模为环境自引用，可以复用已有凭据加密、环境状态、审计和任务引用能力。相比新增独立 `jump_hosts` 表，这个设计更贴近“先配置一个环境，再在目标/源机器选择它”的产品行为。

### 9. 概览先实现可用聚合，允许部分领域为空

`GET /api/projects/{projectId}/overview` 返回项目基本信息、当前源码版本、源码版本数量、环境数量与角色覆盖、最近任务、最近环境快照摘要和推荐下一步动作。尚未实现的 KB/SBOM/报告/构建/测试统计返回空摘要或 0。

理由：概览 API 应该从一开始就稳定，但领域能力会分阶段补齐。返回结构可以保留摘要位置，避免前端在后续频繁改协议。

### 10. 单元测试必须覆盖三类路径

本 change 的单元测试和轻量集成测试必须按正常流程、异常流程和 edge case 三类组织。每个核心服务或控制器能力至少覆盖：

- 正常流程：合法输入、成功写入、成功查询、成功投递任务。
- 异常流程：无权限、资源不存在、状态不允许、凭据密钥无效、Git URL 携带凭据、禁用环境不能创建任务等。
- edge case：空列表、可选字段为空、重复源码上传、已有 active 源码切换、跳板机自引用、多级跳板、跳板机跨项目、分页边界、输入长度和端口边界。

理由：项目/源码/环境是后续所有能力的底座，只测 happy path 会把很多边界问题推迟到更晚阶段暴露。

## Risks / Trade-offs

- Git 同步 API 创建任务但没有真实 handler 时任务会失败或停留为待处理。→ 在任务类型消息和文档中明确本 change 只完成任务投递；实现时可提供占位 handler 返回明确 `TASK_HANDLER_NOT_FOUND` 或后续补 handler。
- 嵌入式凭据写入会产生凭据复用能力不足。→ 当前响应包含凭据 ID 和遮蔽摘要，后续可追加凭据选择接口。
- 项目访问边界过宽。→ MVP 不设计项目成员；后续若需要多租户隔离，单独引入项目授权模型。
- 上传文件占用本地磁盘。→ 使用 `RVPORT_UPLOAD_DIR`，按项目和版本分目录，后续由归档/清理策略管理。
- `stage` 与 overview 推导可能短期不一致。→ API 文档和实现都把 overview 作为展示真实状态的来源，`stage` 只作为导航提示。
- 跳板机自引用可能形成环。→ MVP 禁止自引用和多级跳板链路，创建/更新时做同项目、启用状态和链路深度校验。

## Migration Plan

本 change 需要新增 Liquibase 迁移，为 `environments` 增加可空 `jump_host_environment_id` 自引用外键和索引，并重新生成 jOOQ 代码。上线前确认：

1. PostgreSQL、Redis、RabbitMQ 已通过根目录 Docker Compose 启动。
2. Liquibase 已迁移到包含项目、源码、凭据、环境、跳板机引用和任务表的 schema。
3. jOOQ 生成代码与当前 schema 一致，并包含 `environments.jump_host_environment_id`。
4. `RVPORT_CREDENTIAL_MASTER_KEY` 已配置为 base64 后 32 字节的密钥。
5. `RVPORT_UPLOAD_DIR` 指向可写目录。

回滚时停止使用新增 API 即可；已创建的项目、源码版本、凭据、环境和任务数据仍保留在数据库中。若需要数据库回滚，应先清空或迁移 `environments.jump_host_environment_id` 引用，再回滚该列和索引。

## Open Questions

- 项目列表是否应默认只返回当前用户创建的项目，还是所有登录用户都可见全部项目？当前设计按“登录用户可见全部未删除项目”处理。
- 源码上传是否需要限制文件大小和允许的压缩格式？实现阶段应至少做基础大小和扩展名校验，但具体上限可先使用配置默认值。
- 远程脚本任务是否允许任意脚本文本？当前只设计任务创建和安全摘要，真实执行策略应在 SSH worker handler change 中再确认。
