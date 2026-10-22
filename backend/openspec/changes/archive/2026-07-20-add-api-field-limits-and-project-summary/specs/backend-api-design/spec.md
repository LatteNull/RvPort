## MODIFIED Requirements

### Requirement: API 通用约定必须统一
后端 API 设计 SHALL 定义统一的 base path、响应包络、错误格式、分页格式、时间格式、列表查询能力、字段长度边界和浏览器 Session 安全约定。除非对应 spec 明确说明业务上不是列表查询，所有返回集合或列表数据的接口 SHALL 支持分页、排序和过滤。

#### Scenario: 返回成功响应
- **WHEN** API 请求成功
- **THEN** 响应 SHALL 使用统一响应包络，包含业务数据、请求追踪 ID 和时间戳

#### Scenario: 返回错误响应
- **WHEN** API 请求失败
- **THEN** 响应 SHALL 使用统一错误格式，包含错误码、错误消息、可选字段级详情、请求追踪 ID 和时间戳

#### Scenario: 返回分页列表
- **WHEN** API 返回列表数据
- **THEN** 响应 SHALL 支持 `page`、`pageSize`、`total`、`hasMore` 和 `items`
- **AND** 请求 SHALL 支持 `page` 和 `pageSize`
- **AND** 后端 SHALL 对 `page` 和 `pageSize` 执行边界校验和最大页大小限制

#### Scenario: 列表接口支持过滤
- **WHEN** API 返回列表数据
- **THEN** 请求 SHALL 支持该资源有业务意义的过滤字段
- **AND** 多个过滤条件 SHALL 使用 AND 语义，除非对应接口 spec 明确说明其他语义
- **AND** 过滤字段 SHALL 使用白名单定义
- **AND** 后端 MUST NOT 将客户端传入的任意字段名直接拼接到 SQL

#### Scenario: 列表接口支持排序
- **WHEN** API 返回列表数据
- **THEN** 请求 SHALL 支持 `sortBy` 和 `sortDirection` 或等效排序参数
- **AND** 后端 SHALL 为每个列表接口定义排序字段白名单
- **AND** 后端 SHALL 支持升序和降序
- **AND** 每个列表接口 SHALL 定义稳定默认排序
- **AND** 后端 MUST 拒绝不在白名单内的排序字段

#### Scenario: 列表能力例外
- **WHEN** 某个集合接口由于业务语义、协议语义或数据规模不适合分页、排序或过滤
- **THEN** 对应 capability spec MUST 明确说明例外原因
- **AND** 该接口 MUST 仍然保证响应规模可控

#### Scenario: 认证字段长度边界
- **WHEN** API 接收登录名或明文密码输入
- **THEN** `username` SHALL 限制为最大 64 字符
- **AND** 明文 `password`、`currentPassword`、`newPassword` SHALL 限制为最大 16 字符
- **AND** 超过长度限制时 API SHALL 返回统一参数校验错误

#### Scenario: 使用 Session Cookie 进行浏览器认证
- **WHEN** 前端调用需要登录态的 API
- **THEN** 前端 SHALL 依赖浏览器自动携带 HttpOnly Session Cookie
- **AND** 前端 MUST NOT 通过读取 JWT 恢复 MVP 登录态

#### Scenario: 状态变更请求提交 CSRF token
- **WHEN** 前端使用 Session Cookie 调用状态变更 API
- **THEN** 前端 SHALL 能先获取 CSRF token
- **AND** 状态变更请求 SHALL 通过约定 header 提交 CSRF token

### Requirement: 认证 API 不暴露角色权限模型
MVP 认证 API SHALL 只返回本地用户信息和超级管理员标记，不 SHALL 暴露角色、权限或项目成员模型。

#### Scenario: 获取当前用户
- **WHEN** 前端调用 `GET /api/auth/me`
- **THEN** 响应 SHALL 包含用户 ID、用户名、展示名、邮箱、状态、`isSuperAdmin` 和 `mustChangePassword`
- **AND** 响应 MUST NOT 包含 `roles`、`permissions`、`projectMembers` 或 `passwordHash`

#### Scenario: 用户登录成功
- **WHEN** 用户通过本地账号登录且 `username` 不超过 64 字符、`password` 不超过 16 字符
- **THEN** API SHALL 建立基于服务端 Session 和 Cookie 的登录态
- **AND** 响应 SHALL 返回当前用户信息
- **AND** 响应和日志 MUST NOT 返回明文密码、密码哈希、角色、权限或项目成员信息

#### Scenario: 用户登录输入超过长度
- **WHEN** 用户调用 `POST /api/auth/login` 且 `username` 超过 64 字符或 `password` 超过 16 字符
- **THEN** API SHALL 返回参数校验错误
- **AND** 后端 MUST NOT 执行密码哈希校验

#### Scenario: 用户登录失败
- **WHEN** 用户名不存在、密码错误或用户状态不允许登录
- **THEN** API SHALL 返回认证失败或用户禁用错误
- **AND** 响应和日志 MUST NOT 暴露明文密码
- **AND** 响应 SHOULD NOT 泄漏可被枚举利用的账号存在性细节

#### Scenario: 当前用户修改密码
- **WHEN** 已登录用户调用 `POST /api/auth/change-password` 且 `currentPassword` 和 `newPassword` 均不超过 16 字符
- **THEN** API SHALL 校验当前密码并保存新密码哈希
- **AND** 成功后 SHALL 将用户的 `mustChangePassword` 标记清除
- **AND** API MUST NOT 在响应、日志或审计详情中记录当前密码或新密码

#### Scenario: 当前用户修改密码输入超过长度
- **WHEN** 已登录用户调用 `POST /api/auth/change-password` 且 `currentPassword` 或 `newPassword` 超过 16 字符
- **THEN** API SHALL 返回参数校验错误
- **AND** 后端 MUST NOT 更新密码哈希

#### Scenario: 强制改密用户访问受限
- **WHEN** 已登录用户的 `mustChangePassword` 为 `true`
- **THEN** API SHALL 只允许其访问当前用户查询、修改密码、退出登录和 CSRF token 获取接口
- **AND** 访问其他受保护业务接口时 SHALL 返回 `PASSWORD_CHANGE_REQUIRED` 错误

#### Scenario: 用户退出登录
- **WHEN** 已登录用户调用 `POST /api/auth/logout`
- **THEN** API SHALL 清理当前服务端 Session
- **AND** 后续使用同一登录态访问受保护接口 SHALL 失败

### Requirement: 用户邀请接受 API 必须设置密码并消费 token
认证 API SHALL 提供邀请接受接口，允许用户通过邮件 token 设置密码并完成账号注册。

#### Scenario: 接受有效邀请
- **WHEN** 用户调用 `POST /api/auth/invitations/accept` 并提交有效邀请 token 和不超过 16 字符的新密码
- **THEN** 后端 SHALL 校验 token 类型、hash、过期时间、消费状态和用户状态
- **AND** 后端 SHALL 保存新密码哈希
- **AND** 后端 SHALL 消费该 token
- **AND** 后端 SHALL 允许用户随后使用账号密码登录

#### Scenario: 邀请设密超过长度
- **WHEN** 用户调用 `POST /api/auth/invitations/accept` 且 `newPassword` 超过 16 字符
- **THEN** API SHALL 返回参数校验错误
- **AND** 后端 MUST NOT 消费邀请 token
- **AND** 后端 MUST NOT 修改用户密码

#### Scenario: 接受无效邀请
- **WHEN** 用户提交不存在、过期、已消费或类型不匹配的邀请 token
- **THEN** API SHALL 返回 token 无效或过期错误
- **AND** 后端 MUST NOT 修改用户密码

### Requirement: 忘记密码 API 必须防止账号枚举
认证 API SHALL 提供用户自行触发的忘记密码流程，并 SHALL 防止通过响应枚举账号是否存在。

#### Scenario: 请求密码重置
- **WHEN** 用户调用 `POST /api/auth/password-resets/request` 并提交用户名或邮箱
- **THEN** API SHALL 返回统一成功响应
- **AND** 若匹配到可用用户，后端 SHALL 生成密码重置 token 并发送邮件
- **AND** 若未匹配用户，后端 MUST NOT 暴露账号不存在

#### Scenario: 确认密码重置
- **WHEN** 用户调用 `POST /api/auth/password-resets/confirm` 并提交有效 token 和不超过 16 字符的新密码
- **THEN** 后端 SHALL 校验 token 类型、hash、过期时间和消费状态
- **AND** 后端 SHALL 保存新密码哈希
- **AND** 后端 SHALL 消费该 token
- **AND** 后端 SHALL 将 `mustChangePassword` 设置为 `false`

#### Scenario: 密码重置输入超过长度
- **WHEN** 用户调用 `POST /api/auth/password-resets/confirm` 且 `newPassword` 超过 16 字符
- **THEN** API SHALL 返回参数校验错误
- **AND** 后端 MUST NOT 消费密码重置 token
- **AND** 后端 MUST NOT 修改用户密码

#### Scenario: 密码重置 token 无效
- **WHEN** 用户提交不存在、过期、已消费或类型不匹配的密码重置 token
- **THEN** API SHALL 返回 token 无效或过期错误
- **AND** 后端 MUST NOT 修改用户密码

### Requirement: 项目 stage 作为导航提示暴露
项目 API SHALL 将项目阶段作为导航提示暴露，并 SHALL 通过 overview 和列表摘要聚合表达项目真实状态。

#### Scenario: 读取项目详情
- **WHEN** 前端读取项目详情
- **THEN** 响应 MAY 返回 `stage` 或 `stageHint`
- **AND** 文档 SHALL 明确该字段不是权威状态机

#### Scenario: 读取项目列表摘要
- **WHEN** 前端调用 `GET /api/projects`
- **THEN** 列表项 SHALL 包含 `highRiskCount`、`latestScanAt`、`latestBuildStatus` 和 `latestTestStatus`
- **AND** 未产生对应领域运行记录时，摘要字段 SHALL 返回 `0` 或 `null`
- **AND** 后端 MUST NOT 只依赖 `projects.stage` 判断项目真实状态

#### Scenario: 读取项目概览
- **WHEN** 前端调用 `GET /api/projects/{projectId}/overview`
- **THEN** 后端 SHALL 从当前源码版本、环境摘要、任务、扫描运行、SBOM 运行、报告、复检、构建、测试、问题和差异数据聚合当前状态
- **AND** 尚未落地的领域摘要 SHALL 返回空摘要或 0 值
- **AND** 后端 MUST NOT 只依赖 `projects.stage` 判断项目真实状态

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

#### Scenario: 设计项目名称重复策略
- **WHEN** 设计项目创建和项目列表 API
- **THEN** API SHALL 允许不同项目使用相同 `name`
- **AND** 项目唯一识别 MUST 使用 `projectId`
- **AND** 后端 MUST NOT 因项目名称重复拒绝创建项目
