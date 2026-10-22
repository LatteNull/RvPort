## ADDED Requirements

### Requirement: API 必须支持新建环境前连接预检
后端 API SHALL 提供不依赖 `environmentId` 的项目级环境连接预检接口，使前端能在新建环境提交前验证 SSH 连接配置。

#### Scenario: 创建新建环境连接预检任务
- **WHEN** 已登录用户调用 `POST /api/projects/{projectId}/environments/test-connection` 并提交完整 SSH 连接配置
- **THEN** 后端 SHALL 校验当前用户有权访问该项目
- **AND** 后端 SHALL 校验连接配置字段合法
- **AND** 后端 SHALL 创建 `ENV_TEST_CONNECTION` 任务并返回 `taskId`、任务类型和初始状态
- **AND** 后端 MUST NOT 创建 `environments` 记录
- **AND** API 响应 MUST NOT 返回明文密码、私钥、passphrase、加密密文或完整任务输入快照

#### Scenario: 新建环境预检使用表单明文凭据但不保存正式凭据
- **WHEN** 新建环境连接预检请求提交 `password` 或 `privateKey`/`passphrase`
- **THEN** 后端 SHALL 只在请求处理阶段读取明文凭据
- **AND** 后端 SHALL 将凭据加密保存为任务级临时 secret payload
- **AND** 后端 MUST NOT 将该凭据写入正式 `credentials` 表
- **AND** `tasks.input_snapshot` MUST only contain `temporaryCredentialPayloadId`、校验 hash 和非敏感连接字段
- **AND** API 响应、任务输入、日志、事件和审计 MUST NOT 暴露明文密码、私钥、passphrase 或加密密文
- **AND** 预检任务进入终态后，后端 SHALL 删除对应任务级临时 secret payload，并保留任务状态和日志供查询

#### Scenario: 新建环境预检支持跳板机
- **WHEN** 新建环境连接预检请求包含 `jumpHostEnvironmentId`
- **THEN** 后端 SHALL 校验跳板机环境存在、属于同一项目且已启用
- **AND** 后端 SHALL 拒绝多级跳板链路
- **AND** 任务输入 SHALL 只保存跳板机环境 ID 或安全摘要
- **AND** API 响应 MUST NOT 返回跳板机凭据明文

#### Scenario: 新建环境预检拒绝非法凭据
- **WHEN** 新建环境连接预检请求缺少凭据、引用无效凭据或提交的凭据无法安全加密保存为任务级 secret payload
- **THEN** API SHALL 返回统一错误响应
- **AND** 后端 MUST NOT 创建任务
- **AND** 后端 MUST NOT 保存明文凭据或泄漏凭据内容

#### Scenario: 已创建环境连接复测接口保持兼容
- **WHEN** 已登录用户调用 `POST /api/projects/{projectId}/environments/{environmentId}/test-connection`
- **THEN** 后端 SHALL 继续按已创建环境配置创建连接测试任务
- **AND** 后端 SHALL 校验环境属于 URL 中的项目
- **AND** 响应格式 SHALL 与新建环境预检任务保持一致

### Requirement: API 环境列表必须支持状态过滤
后端环境列表 API SHALL 支持按环境运行状态过滤环境，供 SBOM 配置等前端视图只展示可用环境。

#### Scenario: 按状态查询环境列表
- **WHEN** 已登录用户调用 `GET /api/projects/{projectId}/environments?status=AVAILABLE`
- **THEN** 后端 SHALL 校验当前用户有权访问该项目
- **AND** 后端 SHALL 只返回 `environments.status=AVAILABLE` 的环境
- **AND** 响应 SHALL 继续使用分页响应格式
- **AND** 响应 MUST NOT 返回明文凭据

#### Scenario: 状态过滤与现有过滤条件组合
- **WHEN** 已登录用户调用环境列表接口并同时提交 `role`、`enabled` 和 `status`
- **THEN** 后端 SHALL 使用 AND 语义组合过滤条件
- **AND** 后端 SHALL 保持稳定默认排序

#### Scenario: 非法状态过滤值
- **WHEN** 用户提交不在环境状态枚举内的 `status`
- **THEN** API SHALL 返回统一参数校验错误
- **AND** 后端 MUST NOT 将非法状态值拼接到 SQL
