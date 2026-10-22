## ADDED Requirements

### Requirement: API 必须支持自动化测试节点的自动比较结果查询
后端 API SHALL 提供测试结果比较列表、详情、差异项查询、取消和原始 agent 输出下载能力，并 SHALL 以项目访问权限作为授权边界。比较任务 SHALL 由自动化测试节点完成后自动创建，不 SHALL 要求用户手动创建。

#### Scenario: 自动化测试完成后可查询比较摘要
- **WHEN** 已登录用户查询自动化测试详情、项目测试列表或项目比较列表
- **THEN** API SHALL 能返回自动化测试节点关联的比较摘要
- **AND** 比较摘要 SHALL 包含比较运行 ID、状态、总体结论、风险等级、置信度、摘要、建议、不可用原因和关键时间字段
- **AND** 响应 MUST NOT 返回完整日志、完整 agent 输入、明文凭据或模型 secret

#### Scenario: 模型未配置时展示比较不可用
- **WHEN** 自动化测试完成但 `TEST_LOG_COMPARE` 阶段未配置可用模型
- **THEN** API SHALL 返回测试结果本身
- **AND** 比较摘要 SHALL 表达 `UNAVAILABLE` 或等效状态
- **AND** 不可用原因 SHOULD 为 `TEST_COMPARE_MODEL_NOT_CONFIGURED`
- **AND** 不可用消息 SHALL 说明测试结果比较功能未配置模型，当前不可用

#### Scenario: 查询项目测试结果比较列表
- **WHEN** 已登录用户调用 `GET /api/projects/{projectId}/test-comparisons`
- **THEN** API SHALL 返回分页比较运行列表
- **AND** 列表接口 SHALL 支持按状态、源码版本、测试运行 ID、环境、风险等级和时间范围过滤
- **AND** 列表接口 SHALL 支持按 `createdAt`、`finishedAt`、`status` 和 `riskLevel` 排序

#### Scenario: 查询测试结果比较详情
- **WHEN** 已登录用户调用 `GET /api/test-comparisons/{comparisonId}`
- **THEN** API SHALL 通过比较运行所属项目校验访问权限
- **AND** 响应 SHALL 返回比较摘要、两侧测试记录摘要、状态、总体结论、风险等级、置信度、建议、agent 输出 artifact 摘要和关键时间字段
- **AND** 响应 MUST NOT 返回完整日志、完整 agent 输入、对象存储内部 key 或服务器真实路径

#### Scenario: 查询测试结果比较差异项
- **WHEN** 已登录用户调用 `GET /api/test-comparisons/{comparisonId}/findings`
- **THEN** API SHALL 返回分页差异项列表
- **AND** 列表接口 SHALL 支持按严重程度、差异类型、置信度和关键字过滤
- **AND** 列表接口 SHALL 支持按序号、严重程度、置信度和创建时间排序

#### Scenario: 取消测试结果比较
- **WHEN** 已登录用户调用 `POST /api/test-comparisons/{comparisonId}/cancel`
- **THEN** API SHALL 校验访问权限
- **AND** 后端 SHALL 复用任务取消机制取消关联 `TEST_LOG_COMPARE` 任务
- **AND** 响应 SHALL 返回取消后的任务或比较运行摘要

#### Scenario: 下载原始 agent 输出
- **WHEN** 已登录用户调用 `GET /api/test-comparisons/{comparisonId}/agent-output`
- **THEN** API SHALL 校验访问权限
- **AND** 后端 SHALL 返回该比较运行保存的原始 agent 输出 artifact
- **AND** 响应 MUST NOT 暴露对象存储 bucket、object key 或服务器真实路径

#### Scenario: 不提供手动创建比较入口
- **WHEN** 前端需要触发自动化测试节点
- **THEN** 前端 SHALL 只调用自动化测试创建接口
- **AND** 后端 MUST NOT 要求前端再调用测试结果比较创建接口
- **AND** 若后端保留内部方法创建比较，外部 API MUST NOT 暴露任意模型参数、prompt 或完整日志输入

#### Scenario: test-support 可手动触发比较
- **WHEN** 后端以 test-support 构建运行，E2E 或开发测试需要绕过完整自动化测试节点手动触发比较
- **THEN** 后端 MAY 提供 test-support only 的 `POST /api/test-support/projects/{projectId}/test-comparisons`
- **AND** 请求 SHALL 只接受 `sourceTestRunId` 和 `targetTestRunId` 等测试夹具所需字段
- **AND** 该接口 MUST NOT 编译进入默认生产 jar
- **AND** 生产环境 MUST NOT 暴露 `/api/test-support/projects/{projectId}/test-comparisons`
- **AND** 该接口 MUST NOT 接受任意模型参数、prompt、完整日志内容或 provider secret

### Requirement: 自动化测试 API 必须暴露自动比较状态
后端 API SHALL 让前端能够在自动化测试节点中展示比较进度、报告或不可用原因。

#### Scenario: 测试详情包含自动比较状态
- **WHEN** 前端查询自动化测试详情或项目测试相关摘要
- **THEN** 后端 SHALL 返回该测试节点关联的比较状态或比较摘要
- **AND** 未配置 `TEST_LOG_COMPARE` 模型时，该摘要 SHALL 表达比较功能不可用
- **AND** 后端 MUST NOT 因比较功能不可用隐藏或拒绝已有测试结果
