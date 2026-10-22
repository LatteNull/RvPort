## ADDED Requirements

### Requirement: E2E runner 必须支持模块化选择运行
API E2E 测试套件 SHALL 支持按模块、按 case、按 tag 选择运行，并 SHALL 保留全量运行能力。

#### Scenario: 列出可运行 E2E 模块和用例
- **WHEN** 开发者执行 E2E list 命令
- **THEN** runner SHALL 输出所有可运行 case 的 `id`、`module`、`tags` 和简要说明
- **AND** 输出 SHALL 能帮助开发者选择 `--module`、`--case` 或 `--tag`

#### Scenario: 按模块运行
- **WHEN** 开发者执行 `node e2e/runner.js run --module=auth`
- **THEN** runner SHALL 只运行 module 为 `auth` 的 E2E case
- **AND** runner SHALL NOT 运行 project、task、sbom 等无关模块 case

#### Scenario: 按单个 case 运行
- **WHEN** 开发者执行 `node e2e/runner.js run --case=001-auth-users`
- **THEN** runner SHALL 只运行指定 case
- **AND** runner SHALL 在 case 不存在时返回失败状态并输出可用 case 提示

#### Scenario: 按 tag 运行
- **WHEN** 开发者执行 `node e2e/runner.js run --tag=smoke`
- **THEN** runner SHALL 运行所有包含 `smoke` tag 的 case
- **AND** runner SHALL 在 tag 不存在时返回失败状态并输出可用 tag 提示

#### Scenario: 默认全量运行
- **WHEN** 开发者执行 `node e2e/runner.js run`
- **THEN** runner SHALL 继续运行全部 E2E case
- **AND** 该行为 SHALL 与 change 前的默认全量运行兼容

#### Scenario: 显式全量运行
- **WHEN** 开发者执行 `node e2e/runner.js run --all`
- **THEN** runner SHALL 运行全部 E2E case

### Requirement: 模块化 E2E 运行必须具备独立 setup 和清理
API E2E runner SHALL 为任意被选择的模块或 case 执行公共 setup、状态恢复和清理，避免单模块运行依赖其他模块先执行。

#### Scenario: 单独运行非认证模块
- **WHEN** 开发者单独运行 project、task 或 sbom 模块
- **THEN** runner SHALL 在执行 case 前完成基础设施检查、后端健康检查、管理员登录和 CSRF 初始化
- **AND** case SHALL NOT 依赖 `001-auth-users` 先运行才能访问受保护 API

#### Scenario: 临时处理管理员强制改密状态
- **WHEN** runner 发现管理员 `must_change_password=true`
- **THEN** runner SHALL 在执行选中 case 前临时清除该状态
- **AND** runner SHALL 在成功、失败或清理完成后恢复原始状态

#### Scenario: 清理模块化运行数据
- **WHEN** 模块化 E2E 运行成功或失败
- **THEN** runner SHALL 使用本次 run id 和 cleanup registry 清理该次运行创建的数据、上传文件和队列消息
- **AND** 清理范围 SHALL NOT 依赖是否执行了其他模块

### Requirement: E2E post-run assertion 必须按选中模块启用
API E2E runner SHALL 根据选中 case 的需要执行 post-run assertion，避免轻量模块被无关外部副作用校验阻断。

#### Scenario: 轻量认证模块运行
- **WHEN** runner 只运行 auth 模块
- **THEN** runner SHALL 执行 Redis session 和敏感信息边界检查
- **AND** runner SHALL NOT 因 RabbitMQ 中存在无关历史消息而失败

#### Scenario: 任务相关模块运行
- **WHEN** runner 运行会创建异步任务的 source、task 或 sbom case
- **THEN** runner SHALL 执行 RabbitMQ 队列可查询和任务消息脱敏检查

#### Scenario: 全量运行
- **WHEN** runner 执行全量 E2E
- **THEN** runner SHALL 执行所有适用的 post-run assertion

### Requirement: E2E 文档必须说明模块化运行方式
API E2E 文档 SHALL 说明模块化运行命令、case/tag 列表查询方式、适用场景和新增 API 时的推荐验证路径。

#### Scenario: 查看模块化运行文档
- **WHEN** 开发者查看 E2E README 或覆盖矩阵文档
- **THEN** 文档 SHALL 展示 `list`、`--module`、`--case`、`--tag` 和 `--all` 的示例命令
- **AND** 文档 SHALL 说明新增 API 时应优先运行相关模块，必要时再运行全量 E2E

#### Scenario: 新增 E2E case
- **WHEN** 后续 change 新增 E2E case
- **THEN** 文档或任务说明 SHALL 要求该 case 提供稳定 metadata
- **AND** metadata SHALL 至少包含 `id`、`module` 和 `tags`
