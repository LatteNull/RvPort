## ADDED Requirements

### Requirement: PostgreSQL 是后端持久化基础
后端数据库设计 SHALL 以 PostgreSQL 作为 MVP 持久化目标，并 SHALL 使用适合 PostgreSQL 的数据类型，包括 `uuid`、`timestamptz`、`jsonb`、`inet` 和必要的文本字段索引。

#### Scenario: 明确 Schema 目标
- **WHEN** 创建后端数据库文档或迁移脚本
- **THEN** 文档或迁移脚本 MUST 明确 PostgreSQL 是 MVP 支持的数据库目标

#### Scenario: 保留半结构化工具数据
- **WHEN** 持久化工具输入、任务输入快照、环境快照、报告摘要或分析器元数据
- **THEN** Schema SHALL 为需要追溯但不需要一等关系字段的数据提供 `jsonb` 字段

### Requirement: 项目阶段是派生的导航提示
数据库设计 SHALL 将项目阶段视为缓存式导航提示，而不是权威线性状态机。

#### Scenario: 导入修复后的代码
- **WHEN** 开发者在报告、构建或测试完成后导入修复后的代码
- **THEN** 项目阶段 MAY 回退到源码导入、扫描、报告或等待修复等提示状态，且不影响历史任务和运行记录

#### Scenario: 请求项目概览
- **WHEN** 后端计算项目概览或下一步引导
- **THEN** 后端 MUST 从源码版本、任务、领域运行表、问题和差异数据推导权威状态，而不是只依赖 `projects.stage`

### Requirement: MVP 不持久化用户角色
MVP 数据库设计 SHALL 保留本地用户和超级管理员标记，但 SHALL NOT 引入用户角色、用户角色映射或项目成员表。

#### Scenario: 定义用户表
- **WHEN** 定义 MVP 用户持久化
- **THEN** Schema SHALL 包含本地 `users` 表，用于登录、创建人引用、审计操作人引用和 `is_super_admin` 标记

#### Scenario: 考虑角色表
- **WHEN** 定义 MVP 数据库表
- **THEN** Schema MUST NOT 包含 `roles`、`user_roles` 或 `project_members` 表

### Requirement: 初始化时创建默认超级管理员
环境初始化脚本 SHALL 在第一次成功运行时创建默认超级管理员用户。

#### Scenario: 首次运行初始化
- **WHEN** 环境初始化脚本运行且不存在 `admin` 用户
- **THEN** 脚本 SHALL 创建 `username = 'admin'`、初始密码输入为 `admin123`、`is_super_admin = true` 的用户

#### Scenario: 持久化默认密码
- **WHEN** 使用默认 `admin123` 密码创建初始管理员
- **THEN** 数据库 MUST 只保存派生出的 `password_hash`，并 MUST NOT 保存明文密码

#### Scenario: 再次运行初始化
- **WHEN** 环境初始化脚本运行且 `username = 'admin'` 已存在
- **THEN** 脚本 MUST NOT 创建重复管理员

### Requirement: 任务状态持久化存储在 PostgreSQL
系统 SHALL 将 PostgreSQL 作为异步任务状态、任务事件、任务日志元数据和任务关联业务结果的事实来源。

#### Scenario: 创建任务并投递队列
- **WHEN** API 请求创建长时间运行任务
- **THEN** 系统 MUST 先插入 `tasks` 记录，再将任务 ID 投递到队列

#### Scenario: 队列载荷最小化
- **WHEN** 任务被投递到 worker 队列
- **THEN** 队列载荷 MUST 只包含 `task_id` 等路由信息，并 MUST NOT 作为任务输入、状态、进度或结果的权威存储

#### Scenario: Worker 更新任务生命周期
- **WHEN** worker 启动、推进、成功、失败、超时或取消任务
- **THEN** worker MUST 更新 PostgreSQL 中的任务状态并追加任务事件

### Requirement: SSE 恢复使用持久化任务事件
系统 SHALL 将任务事件持久化到 PostgreSQL，使项目级 SSE 通道能在客户端重连后恢复。

#### Scenario: 客户端携带最后事件 ID 重连
- **WHEN** 前端携带最后消费的事件 ID 重连项目任务事件流
- **THEN** 后端 SHALL 从持久化的 `task_events` 数据中读取后续事件

#### Scenario: 事件流不包含完整日志
- **WHEN** 任务发出进度或日志更新
- **THEN** 持久化任务事件 SHALL 包含状态、进度、消息、日志级别和短摘要，但 MUST NOT 保存完整 stdout 或 stderr 日志

### Requirement: 凭据由平台管理并加密
系统 SHALL 使用专用凭据模型保存 SSH 和 Git 凭据，凭据载荷必须加密，并只暴露非敏感摘要。

#### Scenario: 保存凭据
- **WHEN** 用户保存 SSH 密码、SSH 私钥或 Git 密码
- **THEN** 明文秘密 MUST 在持久化前加密，并 MUST NOT 存储到普通文本列

#### Scenario: 展示凭据信息
- **WHEN** API 响应包含凭据信息
- **THEN** 响应 SHALL 只返回配置状态、凭据类型、名称、遮蔽摘要等非敏感元数据

### Requirement: 日志本地存储并用元数据索引
系统 SHALL 将完整任务日志保存在本地文件系统，按天打包，并在 PostgreSQL 中只保存日志元数据和摘要。

#### Scenario: 任务写入 stdout 和 stderr
- **WHEN** worker 捕获任务的 stdout 或 stderr
- **THEN** 完整日志内容 SHALL 写入本地日志文件，PostgreSQL 只保存文件路径、日志日期、归档路径、大小、哈希和摘要元数据

#### Scenario: 打包日志
- **WHEN** 每日日志打包流程运行
- **THEN** 日志元数据 SHALL 能引用每日归档路径，且不要求通用 artifact 表

### Requirement: MVP 不包含通用 artifact 持久化
MVP 数据库设计 SHALL NOT 为源码包、报告、归档或日志引入通用 artifact 表。

#### Scenario: 生成报告
- **WHEN** 生成 HTML 或 JSON 报告
- **THEN** 报告记录 MAY 直接保存本地输出路径，而不是引用通用 artifact 记录

#### Scenario: 生成归档
- **WHEN** 生成归档包
- **THEN** 归档记录 MAY 直接保存本地归档路径、大小和哈希，而不是引用通用 artifact 记录

### Requirement: 领域结果表必须关联任务
系统 SHALL 将领域结果建模为关联权威任务记录的数据。

#### Scenario: KB 扫描完成
- **WHEN** KB 扫描任务完成
- **THEN** 系统 SHALL 持久化关联该任务的扫描运行记录，并持久化关联该扫描运行的 findings

#### Scenario: SBOM 分析完成
- **WHEN** SBOM 分析任务完成
- **THEN** 系统 SHALL 持久化关联该任务的 SBOM 运行记录，并持久化关联该运行的组件和替代候选项

#### Scenario: 构建或测试完成
- **WHEN** 构建或测试任务完成
- **THEN** 系统 SHALL 持久化关联任务、源码版本和执行环境的构建运行或测试运行记录

### Requirement: Findings 和 issues 是不同概念
系统 SHALL 区分不可变工具发现和 SBOM 记录，以及用户管理的迁移问题。

#### Scenario: 用户将发现项加入问题清单
- **WHEN** 选中的 findings 或 SBOM 风险被加入迁移问题清单
- **THEN** 系统 SHALL 创建或更新 issue 记录，并 SHALL 通过 issue source 记录保留来源映射

#### Scenario: 用户更新问题状态
- **WHEN** 用户确认、忽略或标记问题已解决
- **THEN** 系统 SHALL 更新 issue 状态，但不得修改原始 finding 或 SBOM component 事实

### Requirement: 环境快照版本化并被引用
系统 SHALL 将环境快照持久化为版本化记录，并 SHALL 在 SBOM 分析中引用实际使用的快照。

#### Scenario: 同一环境被多次采集
- **WHEN** 同一环境被采集多次
- **THEN** 系统 SHALL 将每次采集保存为独立快照

#### Scenario: 创建 SBOM 运行
- **WHEN** SBOM 分析比较 x86 源环境和 RISC-V 目标环境
- **THEN** SBOM 运行记录 SHALL 引用该次分析实际使用的源环境快照和目标环境快照

### Requirement: MVP 测试存储只保存摘要
MVP 数据库设计 SHALL 保存测试执行摘要字段，并 SHALL NOT 要求解析结构化测试报告格式。

#### Scenario: 测试运行完成
- **WHEN** 测试命令完成
- **THEN** 系统 SHALL 保存退出码、通过数、失败数、可选跳过数、状态、耗时和日志引用

#### Scenario: 存在结构化报告
- **WHEN** 存在 JUnit、CTest、pytest 或类似报告
- **THEN** MVP 系统 MUST NOT 要求解析或保存单个测试用例详情

### Requirement: 审计数据持久化且不包含秘密
系统 SHALL 为敏感或高影响操作保存审计记录，并 SHALL 确保审计详情不包含明文秘密。

#### Scenario: 发生敏感操作
- **WHEN** 用户登录、保存凭据、运行远程脚本、启动构建、启动测试、导出报告、归档数据、删除数据或忽略问题
- **THEN** 系统 SHALL 保存包含操作人、动作、资源、时间戳和脱敏详情的审计日志记录

#### Scenario: 审计详情包含输入
- **WHEN** 命令摘要、请求载荷摘要或凭据引用写入审计详情
- **THEN** 密码、私钥、token 和其他秘密 MUST 被省略或遮蔽
