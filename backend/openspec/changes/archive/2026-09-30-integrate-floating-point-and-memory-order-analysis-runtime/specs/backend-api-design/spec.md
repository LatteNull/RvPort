## ADDED Requirements

### Requirement: API 必须提供两个专项分析领域入口
API SHALL 分别提供浮点精度与内存序分析的创建、latest、运行列表、运行详情、Finding 列表、Finding 详情和 JSON/HTML 下载入口，并 SHALL 对每次访问校验项目权限。

#### Scenario: 项目成员创建分析
- **WHEN** 有权限用户对满足 readiness 的项目创建任一分析
- **THEN** API SHALL 返回对应运行 ID、任务 ID、状态和 stageId

#### Scenario: 越权访问
- **WHEN** 普通用户创建或读取其他用户不可访问项目的分析、Finding 或制品
- **THEN** API SHALL 返回受控拒绝响应
- **AND** MUST NOT 泄漏项目、运行或 Finding 是否存在

### Requirement: 运行与 Finding 列表必须支持分页过滤排序
两个领域的列表 API SHALL 使用统一分页响应，并 SHALL 对允许的过滤和排序字段使用白名单。

#### Scenario: 查询运行列表
- **WHEN** 用户按 status、sourceRevisionId、toolVersion、创建时间范围过滤并按 createdAt、startedAt、finishedAt 或 status 排序
- **THEN** API SHALL 返回稳定分页结果和总数

#### Scenario: 查询 Finding 列表
- **WHEN** 用户按 severity、confidence、status、code、category、filePath、关键字或确认状态过滤并按 severity、path、line、code 或 createdAt 排序
- **THEN** API SHALL 返回稳定分页结果
- **AND** 每条 SHALL 返回 migrationInputRefId、migrationInputStatus、confirmedForNextReport 和 includedInLatestReport

#### Scenario: 非法查询字段
- **WHEN** 用户传入未列入白名单的排序、过滤或分页值
- **THEN** API SHALL 返回统一参数错误
- **AND** MUST NOT 把原始字段拼接到 SQL

### Requirement: API 必须提供专项分析 readiness 和 latest
项目级 readiness SHALL 支持 `floating-point-analysis` 与 `memory-order-analysis`，领域 latest SHALL 使用统一响应外壳并返回当前运行、当前源码与失效原因。

#### Scenario: readiness 返回完整前置事实
- **WHEN** 用户查询任一专项分析 stage readiness
- **THEN** 响应 SHALL 列出源码、x86 构建、compile database、BC v2、produced records、工具可用性以及该领域额外 profile 条件

#### Scenario: 执行时重新校验
- **WHEN** readiness 查询后源码、构建或制品状态发生变化
- **THEN** 创建 API SHALL 重新校验事实
- **AND** 不满足时 SHALL 返回 `PREREQUISITE_NOT_SATISFIED`

### Requirement: Finding 详情必须保留领域证据
浮点 Finding 详情 SHALL 返回 occurrence、evidenceChain、validationPlan、profile/build-context 信息；内存序详情 SHALL 返回 occurrence、evidenceChain、breaks、assumptions、limitations 和 source context。

#### Scenario: 查询完整证据
- **WHEN** 用户读取合法 Finding 详情
- **THEN** API SHALL 返回版本化领域 payload 与公共摘要
- **AND** 路径 SHALL 为仓库相对路径，不得暴露服务器绝对路径
