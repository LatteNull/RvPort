## MODIFIED Requirements

### Requirement: 项目 stage 作为导航提示暴露
项目 API SHALL 将项目阶段作为导航提示暴露，并 SHALL 通过 overview 聚合表达项目真实状态。

#### Scenario: 读取项目详情
- **WHEN** 前端读取项目详情
- **THEN** 响应 MAY 返回 `stage` 或 `stageHint`
- **AND** 文档 SHALL 明确该字段不是权威状态机

#### Scenario: 读取项目概览
- **WHEN** 前端调用 `GET /api/projects/{projectId}/overview`
- **THEN** 后端 SHALL 从当前源码版本、环境摘要、任务、扫描运行、SBOM 运行、报告、复检、构建、测试、问题和差异数据聚合当前状态
- **AND** 尚未落地的领域摘要 SHALL 返回空摘要或 0 值
- **AND** 后端 MUST NOT 只依赖 `projects.stage` 判断项目真实状态

### Requirement: 长任务 API 以 PostgreSQL 任务模型为事实来源
所有长任务创建 API SHALL 先创建持久化任务记录，再返回 `taskId` 和初始任务状态。

#### Scenario: 创建长任务
- **WHEN** 前端发起 Git 同步、环境连接测试、环境采集、远程脚本、KB 扫描、SBOM 分析、报告生成、复检、构建、测试或归档
- **THEN** API SHALL 返回 `taskId`、任务类型和初始状态
- **AND** API SHALL 先创建 `tasks` 记录并追加初始 `task_events`
- **AND** 队列载荷 SHALL 只使用 `task_id` 等路由信息
- **AND** API 响应 MUST NOT 返回完整任务输入快照、明文凭据或服务器本地路径

#### Scenario: 查询任务详情
- **WHEN** 前端调用 `GET /api/tasks/{taskId}`
- **THEN** API SHALL 从持久化任务状态返回任务类型、状态、进度、消息、时间、错误摘要和关联业务资源引用
- **AND** API 响应 MUST NOT 返回完整任务输入快照、明文凭据或服务器本地路径

#### Scenario: 查询项目任务列表
- **WHEN** 前端调用 `GET /api/projects/{projectId}/tasks`
- **THEN** API SHALL 返回该项目的分页任务列表
- **AND** 列表项 SHALL 包含任务 ID、任务类型、状态、进度、消息和关键时间字段

#### Scenario: 取消任务
- **WHEN** 前端调用 `POST /api/tasks/{taskId}/cancel`
- **THEN** API SHALL 可靠取消 `PENDING` 或 `QUEUED` 任务
- **AND** 对 `RUNNING` 任务 SHALL 返回明确错误或当前状态，说明 MVP 暂不支持强制中止运行中任务
- **AND** API MUST NOT 直接把仍在执行的任务伪造为已取消

#### Scenario: 枚举任务状态
- **WHEN** API 文档列出任务状态
- **THEN** 文档 SHALL 包含 `PENDING`、`QUEUED`、`RUNNING`、`SUCCEEDED`、`FAILED`、`CANCELLED` 和 `TIMEOUT`

### Requirement: 凭据 API 只允许遮蔽展示
环境和源码相关 API SHALL 允许写入或重新配置凭据，但查询响应 MUST NOT 返回明文秘密。

#### Scenario: 保存 SSH 凭据
- **WHEN** 用户创建或更新 SSH 环境并提交密码或私钥
- **THEN** API SHALL 将明文秘密交给后端加密保存
- **AND** 响应 MUST NOT 返回明文秘密
- **AND** 响应 MUST NOT 返回加密密文

#### Scenario: 读取环境详情
- **WHEN** 前端读取环境详情
- **THEN** 响应 SHALL 只返回凭据是否已配置、凭据类型、名称和遮蔽摘要

#### Scenario: 保存 Git 凭据
- **WHEN** 用户从 Git 同步源码并提交密码、token 或凭据引用
- **THEN** API SHALL 防止 Git URL 中保存 token、用户名或密码
- **AND** 任务输入快照 MUST NOT 包含明文 Git 凭据

### Requirement: 领域 API 必须映射到已设计的数据模型
后端 API 设计 SHALL 覆盖数据库设计中的核心领域，并保持对外业务命名与内部表模型可映射。

#### Scenario: 设计源码 API
- **WHEN** 定义源码管理接口
- **THEN** API SHALL 覆盖压缩包上传、Git 同步、源码版本列表和当前源码版本切换
- **AND** SHALL 支持修复后源码重新入库
- **AND** 源码查询响应 MUST NOT 暴露服务器本地路径

#### Scenario: 设计环境 API
- **WHEN** 定义环境管理接口
- **THEN** API SHALL 覆盖环境列表、环境创建、环境详情、环境更新、连接测试、环境采集、远程脚本和快照列表
- **AND** 连接测试、环境采集和远程脚本 SHALL 通过任务运行时创建长任务

#### Scenario: 设计跳板机配置
- **WHEN** 定义环境创建和更新接口
- **THEN** API SHALL 支持可选 `jumpHostEnvironmentId`
- **AND** 跳板机 SHALL 是同一项目内另一个已启用环境
- **AND** API MUST NOT 允许自引用或多级跳板链路
- **AND** 环境查询响应 SHALL 返回跳板机的非敏感摘要
- **AND** 任务输入快照 MUST NOT 包含目标环境或跳板机的明文凭据

#### Scenario: 设计项目访问边界
- **WHEN** 设计 MVP 项目、源码和环境 API
- **THEN** API SHALL 要求用户已登录
- **AND** API MUST NOT 引入角色、权限、用户角色映射或项目成员模型
