## ADDED Requirements

### Requirement: 后端 API 设计文档使用中文并落在 backend 内
后端 API 设计 SHALL 在 backend 目录内维护中文文档，并 SHALL 以根目录 API 设计为底稿进行收敛，而不是原样复制旧接口边界。

#### Scenario: 创建后端 API 设计文档
- **WHEN** 创建正式后端 API 设计文档
- **THEN** 文档 SHALL 位于 `backend/docs/API_DESIGN.md`
- **AND** 说明文字 SHALL 使用中文
- **AND** 接口路径、HTTP 方法、字段名、枚举值和协议关键字 MAY 保留英文

#### Scenario: 复用根目录 API 底稿
- **WHEN** 从根目录 `docs/design/01_API_DESIGN.md` 迁移 API 设计内容
- **THEN** 后端文档 SHALL 先对齐当前数据库设计边界，再保留可复用的模块划分、页面触发和交互说明

### Requirement: API 通用约定必须统一
后端 API 设计 SHALL 定义统一的 base path、响应包络、错误格式、分页格式和时间格式。

#### Scenario: 返回成功响应
- **WHEN** API 请求成功
- **THEN** 响应 SHALL 使用统一响应包络，包含业务数据、请求追踪 ID 和时间戳

#### Scenario: 返回错误响应
- **WHEN** API 请求失败
- **THEN** 响应 SHALL 使用统一错误格式，包含错误码、错误消息、可选字段级详情、请求追踪 ID 和时间戳

#### Scenario: 返回分页列表
- **WHEN** API 返回列表数据
- **THEN** 响应 SHALL 支持 `page`、`pageSize`、`total`、`hasMore` 和 `items`

### Requirement: 认证 API 不暴露角色权限模型
MVP 认证 API SHALL 只返回本地用户信息和超级管理员标记，不 SHALL 暴露角色、权限或项目成员模型。

#### Scenario: 获取当前用户
- **WHEN** 前端调用 `GET /api/auth/me`
- **THEN** 响应 SHALL 包含用户 ID、用户名、展示名、邮箱、状态、`isSuperAdmin` 和 `mustChangePassword`
- **AND** 响应 MUST NOT 包含 `roles`、`permissions` 或 `projectMembers`

#### Scenario: 用户登录成功
- **WHEN** 用户通过本地账号登录
- **THEN** API SHALL 建立后续请求可识别的登录态，并 SHALL NOT 在响应或日志中返回明文密码

#### Scenario: 当前用户修改密码
- **WHEN** 已登录用户调用 `POST /api/auth/change-password`
- **THEN** API SHALL 校验当前密码并保存新密码哈希
- **AND** 成功后 SHALL 将用户的 `mustChangePassword` 标记清除

### Requirement: 超级管理员可以管理本地用户
MVP API SHALL 为超级管理员提供配置页用户信息表和本地用户增删改查能力，但 SHALL NOT 通过 API 创建或提升超级管理员。

#### Scenario: 超级管理员查看用户列表
- **WHEN** 超级管理员打开配置页用户信息表
- **THEN** 前端 SHALL 能调用 `GET /api/admin/users` 获取分页用户列表
- **AND** 列表项 SHALL 包含用户 ID、用户名、展示名、邮箱、状态、`isSuperAdmin`、`mustChangePassword`、最近登录时间和创建时间

#### Scenario: 超级管理员创建普通用户
- **WHEN** 超级管理员调用 `POST /api/admin/users`
- **THEN** API SHALL 创建本地普通用户并保存初始密码哈希
- **AND** API SHALL 支持设置 `mustChangePassword`
- **AND** API MUST NOT 接受 `isSuperAdmin=true`

#### Scenario: 超级管理员读取和更新用户
- **WHEN** 超级管理员调用 `GET /api/admin/users/{userId}` 或 `PATCH /api/admin/users/{userId}`
- **THEN** API SHALL 允许读取和更新普通用户的展示名、邮箱和状态
- **AND** API MUST NOT 允许通过请求体修改 `isSuperAdmin`

#### Scenario: 超级管理员重置用户密码
- **WHEN** 超级管理员调用 `POST /api/admin/users/{userId}/reset-password`
- **THEN** API SHALL 保存新的密码哈希
- **AND** API SHALL 支持设置 `mustChangePassword=true`，使用户下次登录后必须修改密码

#### Scenario: 超级管理员删除或禁用用户
- **WHEN** 超级管理员从配置页移除用户
- **THEN** API SHALL 提供禁用、软删除或删除语义之一
- **AND** API 文档 SHALL 明确该语义对历史创建人和审计记录的影响

### Requirement: API 设计标注用户强制改密字段依赖
用户管理和重置密码 API SHALL 依赖数据库提供 `users.must_change_password` 字段。

#### Scenario: 用户被创建或重置密码
- **WHEN** 超级管理员创建用户或重置用户密码并要求下次登录改密
- **THEN** 后端 SHALL 将 `users.must_change_password` 设置为 `true`

#### Scenario: 用户完成强制改密
- **WHEN** 用户成功修改自己的密码
- **THEN** 后端 SHALL 将 `users.must_change_password` 设置为 `false`

#### Scenario: 邮箱验证暂不设计
- **WHEN** 设计 MVP 用户管理 API
- **THEN** API 文档 MUST NOT 要求邮箱验证字段、邮箱验证流程或用户 action token 表

### Requirement: 项目 stage 作为导航提示暴露
项目 API SHALL 将项目阶段作为导航提示暴露，并 SHALL 通过 overview 聚合表达项目真实状态。

#### Scenario: 读取项目详情
- **WHEN** 前端读取项目详情
- **THEN** 响应 MAY 返回 `stage` 或 `stageHint`
- **AND** 文档 SHALL 明确该字段不是权威状态机

#### Scenario: 读取项目概览
- **WHEN** 前端调用 `GET /api/projects/{projectId}/overview`
- **THEN** 后端 SHALL 从当前源码版本、任务、扫描运行、SBOM 运行、报告、复检、构建、测试、问题和差异数据聚合当前状态

### Requirement: 长任务 API 以 PostgreSQL 任务模型为事实来源
所有长任务创建 API SHALL 先创建持久化任务记录，再返回 `taskId` 和初始任务状态。

#### Scenario: 创建长任务
- **WHEN** 前端发起 KB 扫描、SBOM 分析、环境采集、远程脚本、报告生成、复检、构建、测试或归档
- **THEN** API SHALL 返回 `taskId`、任务类型和初始状态
- **AND** 队列载荷 SHALL 只使用 `task_id` 等路由信息

#### Scenario: 查询任务详情
- **WHEN** 前端调用 `GET /api/tasks/{taskId}`
- **THEN** API SHALL 从持久化任务状态返回任务类型、状态、进度、消息、时间、错误摘要和关联业务资源引用

#### Scenario: 枚举任务状态
- **WHEN** API 文档列出任务状态
- **THEN** 文档 SHALL 包含 `PENDING`、`QUEUED`、`RUNNING`、`SUCCEEDED`、`FAILED`、`CANCELLED` 和 `TIMEOUT`

### Requirement: API 使用项目级 SSE 作为实时任务通道
后端 API 设计 SHALL 使用项目级 SSE 作为 MVP 实时任务事件主通道。

#### Scenario: 建立 SSE 连接
- **WHEN** 前端进入项目工作台
- **THEN** 前端 SHALL 通过 `GET /api/projects/{projectId}/task-events` 建立项目级 SSE 连接

#### Scenario: SSE 断线恢复
- **WHEN** 前端携带 `Last-Event-ID` 重新连接
- **THEN** 后端 SHALL 从持久化任务事件中补发后续事件

#### Scenario: 断线补偿
- **WHEN** SSE 连接不可用或恢复失败
- **THEN** 前端 SHALL 通过 `GET /api/tasks/{taskId}` 和 `GET /api/tasks/{taskId}/logs` 补偿刷新

#### Scenario: 避免重复 SSE 通道
- **WHEN** 设计 MVP API
- **THEN** 文档 SHOULD NOT 将 `GET /api/tasks/{taskId}/events` 作为主实时通道

### Requirement: API 不引入通用 Artifact 资源
MVP API 设计 SHALL NOT 引入通用 Artifact API，下载能力 SHALL 由报告、归档和日志等业务资源提供。

#### Scenario: 下载报告
- **WHEN** 前端下载 HTML 或 JSON 报告
- **THEN** API SHALL 通过报告资源的受控下载接口提供文件
- **AND** SHALL NOT 要求引用通用 artifact 记录

#### Scenario: 下载归档包
- **WHEN** 前端下载项目归档包
- **THEN** API SHALL 通过归档资源的受控下载接口提供文件
- **AND** SHALL NOT 暴露服务器真实路径

#### Scenario: 下载任务日志
- **WHEN** 前端下载任务日志
- **THEN** API SHALL 通过任务日志资源的受控下载接口提供文件
- **AND** SHALL NOT 暴露服务器真实路径

### Requirement: 凭据 API 只允许遮蔽展示
环境和源码相关 API SHALL 允许写入或重新配置凭据，但查询响应 MUST NOT 返回明文秘密。

#### Scenario: 保存 SSH 凭据
- **WHEN** 用户创建或更新 SSH 环境并提交密码或私钥
- **THEN** API SHALL 将明文秘密交给后端加密保存
- **AND** 响应 MUST NOT 返回明文秘密

#### Scenario: 读取环境详情
- **WHEN** 前端读取环境详情
- **THEN** 响应 SHALL 只返回凭据是否已配置、凭据类型、名称和遮蔽摘要

#### Scenario: 保存 Git 凭据
- **WHEN** 用户从 Git 同步源码并提交密码或凭据引用
- **THEN** API SHALL 防止 Git URL 中保存 token 或密码

### Requirement: 测试 API 限定为 MVP 摘要能力
MVP 测试 API SHALL 只暴露测试命令退出码和汇总计数，不 SHALL 承诺用例级解析、失败用例重跑或结构化报告对比。

#### Scenario: 创建测试任务
- **WHEN** 前端发起自动化测试
- **THEN** API SHALL 返回测试任务 ID，并在完成后提供退出码、通过数、失败数、可选跳过数、状态、时间和日志引用

#### Scenario: 失败用例重跑
- **WHEN** 设计 MVP API
- **THEN** 文档 MUST NOT 承诺 `rerun failed cases` 这类依赖单个测试用例解析的能力

#### Scenario: 测试对比
- **WHEN** 设计测试对比能力
- **THEN** MVP 文档 MAY 只描述摘要级对比
- **AND** MUST NOT 要求解析 JUnit、CTest、pytest 或类似报告

### Requirement: 领域 API 必须映射到已设计的数据模型
后端 API 设计 SHALL 覆盖数据库设计中的核心领域，并保持对外业务命名与内部表模型可映射。

#### Scenario: 设计源码 API
- **WHEN** 定义源码管理接口
- **THEN** API SHALL 覆盖压缩包上传、Git 同步、源码版本列表和当前源码版本切换
- **AND** SHALL 支持修复后源码重新入库

#### Scenario: 设计扫描和 SBOM API
- **WHEN** 定义 KB 扫描和 SBOM 分析接口
- **THEN** API SHALL 覆盖运行记录、结果列表、结果详情和加入问题清单

#### Scenario: 设计报告、复检、构建、测试和归档 API
- **WHEN** 定义后续验证接口
- **THEN** API SHALL 覆盖报告、复检 diff、构建运行、测试运行和归档快照
