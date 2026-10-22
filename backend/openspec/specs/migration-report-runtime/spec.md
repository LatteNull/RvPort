## Purpose

定义 RvPort 后端迁移评估报告运行时能力，包括基于人工确认迁移输入生成报告、保存输入快照、统计风险摘要和预计工作量、输出 HTML/JSON 制品到对象存储，并通过受控下载 API 向有项目权限的用户提供报告。
## Requirements
### Requirement: 迁移评估报告必须基于确认后的迁移输入生成
后端 SHALL 基于指定项目和源码版本下状态为 `CONFIRMED` 的迁移输入 reference 生成迁移评估报告。确认状态可以来自各分析节点的默认风险规则，也可以来自用户在节点内的人工加入或撤回操作。

#### Scenario: 生成报告读取确认输入
- **WHEN** 报告生成任务开始执行
- **THEN** 后端 SHALL 查询同一 `project_id` 和 `source_revision_id` 下 `status='CONFIRMED'` 的 `migration_input_refs`
- **AND** 后端 SHALL 根据每条 reference 的 `source_type` 和 `source_ref_id` 回查真实来源详情
- **AND** 后端 MUST NOT 将 `CANDIDATE` 或 `EXCLUDED` 迁移输入写入报告

#### Scenario: 没有确认输入
- **WHEN** 报告生成任务发现当前源码版本没有 `CONFIRMED` 迁移输入
- **THEN** 后端 SHALL 将报告任务标记为 `SUCCEEDED`
- **AND** 后端 SHALL 生成空输入报告文件
- **AND** 报告摘要中的输入数量、高风险数量和预计工作量 SHALL 为 0
- **AND** 报告总体风险 SHALL 为 `INFO`

### Requirement: 迁移评估报告必须保存不可变输入快照
后端 SHALL 在报告生成时保存报告输入快照，使历史报告不受后续迁移输入或原始分析结果变化影响。

#### Scenario: 写入报告输入快照
- **WHEN** 报告生成任务使用某条 confirmed migration input reference
- **THEN** 后端 SHALL 在 `report_inputs` 中写入一条记录
- **AND** `input_type` SHALL 为 `MIGRATION_INPUT_REF`
- **AND** `input_id` SHALL 为 `migration_input_refs.id`
- **AND** `input_snapshot` SHALL 包含 reference 展示字段、确认状态、备注和真实来源详情

#### Scenario: 历史报告不随输入状态变化
- **WHEN** 报告生成完成后用户修改迁移输入状态或备注
- **THEN** 已生成报告详情和下载内容 SHALL 继续使用生成时的 `report_inputs.input_snapshot`
- **AND** 后端 MUST NOT 重新从当前 migration input 状态动态拼接历史报告内容

### Requirement: 迁移评估报告必须生成 HTML 和 JSON 输出
后端 SHALL 为成功的迁移评估报告生成 HTML 和 JSON 两种受控输出，并 SHALL 通过对象存储制品能力保存输出内容。

#### Scenario: 成功生成报告制品
- **WHEN** 报告生成任务成功完成
- **THEN** 后端 SHALL 生成 HTML 报告文件
- **AND** 后端 SHALL 生成 JSON 报告文件
- **AND** 后端 SHALL 将两种报告内容保存到对象存储
- **AND** 后端 SHALL 为两种报告内容写入 `stored_artifacts` 元数据
- **AND** `stored_artifacts.owner_type` SHALL 为 `MIGRATION_REPORT`
- **AND** `stored_artifacts.owner_id` SHALL 为 `reports.id`
- **AND** API 响应 MUST NOT 返回服务器真实文件路径、bucket 或 object key

#### Scenario: 报告摘要聚合
- **WHEN** 报告生成任务完成
- **THEN** 后端 SHALL 写入 `reports.summary`
- **AND** 后端 SHALL 写入 `reports.risk_level`
- **AND** 摘要 SHALL 至少包含 confirmed 输入总数、按来源类型统计、按风险等级或替代状态统计和生成 schemaVersion

### Requirement: 迁移评估报告下载必须受控
后端 SHALL 通过报告下载接口读取对象存储中的报告制品，并 SHALL 防止内部存储位置泄露。

#### Scenario: 下载 HTML 报告
- **WHEN** 用户下载 `format=HTML` 的报告
- **THEN** 后端 SHALL 返回 HTML 文件内容
- **AND** 响应文件名 SHALL 使用安全文件名
- **AND** 后端 MUST NOT 在响应体或响应头中暴露服务器真实路径、bucket 或 object key

#### Scenario: 下载 JSON 报告
- **WHEN** 用户下载 `format=JSON` 的报告
- **THEN** 后端 SHALL 返回 JSON 文件内容
- **AND** 响应文件名 SHALL 使用安全文件名
- **AND** JSON 内容 SHALL 使用生成时保存的报告快照
- **AND** 后端 MUST NOT 暴露对象存储内部位置

#### Scenario: 拒绝不存在的报告制品
- **WHEN** 报告记录存在但请求格式对应的对象存储制品不存在
- **THEN** 后端 SHALL 返回统一业务错误
- **AND** 后端 MUST NOT 返回服务器路径、bucket、object key 或底层存储异常细节

### Requirement: 迁移报告说明必须满足严格校验
`migration-report-runtime` 主 spec 的 Purpose SHALL 清晰描述报告输入快照、确认后的迁移输入、统计摘要、对象存储制品和受控下载边界。

#### Scenario: 严格校验迁移报告说明
- **WHEN** 执行 `openspec validate migration-report-runtime --type spec --strict`
- **THEN** 该 spec SHALL 不再因为 `Purpose section is too brief` 失败

### Requirement: 迁移报告必须支持依赖分析输入
迁移评估报告 SHALL 在新流程中使用 confirmed 的 `DEPENDENCY_RESULT` 迁移输入生成依赖替代性说明，并 SHALL 保留历史 SBOM 输入快照兼容。

#### Scenario: 生成报告读取依赖分析输入
- **WHEN** 报告生成任务读取 confirmed migration input reference
- **AND** reference 的 `sourceType` 为 `DEPENDENCY_RESULT`
- **THEN** 后端 SHALL 回查依赖分析结果明细
- **AND** 报告 SHALL 展示依赖类型、目标匹配状态、风险等级、建议和 evidence 摘要

#### Scenario: 报告摘要统计依赖缺口
- **WHEN** 报告生成任务完成
- **THEN** 报告摘要 SHALL 统计依赖分析输入总数、按风险等级统计、按目标匹配状态统计和主要依赖风险
- **AND** 依赖替代性注意点 SHALL 优先来自 `DEPENDENCY_RESULT`

#### Scenario: 历史 SBOM 报告兼容
- **WHEN** 用户查看历史报告且报告输入快照中包含 `SBOM_RESULT`
- **THEN** 后端 SHALL 继续使用报告生成时保存的输入快照展示
- **AND** 后端 MUST NOT 因 SBOM deprecated 而破坏历史报告下载或详情查询
- **AND** 后端 MUST NOT 在新流程中为报告自动创建新的 `SBOM_RESULT` 输入

### Requirement: 评估报告页面必须支持历史报告查看
迁移评估报告 API SHALL 支持前端在评估报告页面查看项目过往评估报告，并 SHALL 允许用户基于历史报告进行比较。

#### Scenario: 查询历史评估报告
- **WHEN** 已登录用户调用 `GET /api/projects/{projectId}/reports/evaluation`
- **THEN** 后端 MUST 校验当前用户对项目有访问权限
- **AND** 响应 SHALL 返回该项目的历史评估报告分页列表
- **AND** 列表 SHALL 支持按 `sourceRevisionId`、状态、风险等级和生成时间过滤
- **AND** 列表 SHALL 支持按 `createdAt`、`generatedAt`、`status` 和 `riskLevel` 排序
- **AND** 每条报告 SHALL 返回报告 ID、源码版本摘要、状态、风险等级、摘要、制品摘要和关键时间字段

#### Scenario: 查看报告详情中的比较入口
- **WHEN** 已登录用户调用 `GET /api/reports/{reportId}`
- **THEN** 响应 SHALL 包含报告摘要、源码版本摘要、制品摘要和可比较历史报告提示
- **AND** 若存在上一份可比较报告，响应 SHOULD 包含 latest comparison 入口摘要或 base report 摘要
- **AND** 响应 MUST NOT 返回完整报告正文、对象存储内部 key 或服务器真实路径

### Requirement: 评估报告必须作为报告比较主入口
迁移评估报告 SHALL 将历史差异查看建模为报告比较能力，而不是要求前端进入独立源码对比节点。

#### Scenario: 从评估报告发起历史比较
- **WHEN** 用户在评估报告页面点击与历史报告比较
- **THEN** 前端 SHALL 调用报告比较 API
- **AND** 后端 SHALL 基于报告输入快照创建或复用比较结果
- **AND** 前端 MUST NOT 为主流程调用源码 latest compare API 来完成报告比较

#### Scenario: 历史报告下载不受比较影响
- **WHEN** 用户查看或下载任意历史评估报告
- **THEN** 后端 SHALL 继续使用该报告生成时保存的 HTML 和 JSON artifact
- **AND** 报告比较结果 MUST NOT 修改历史报告 artifact 内容

### Requirement: 评估报告节点必须提供生成前 readiness
迁移评估报告运行时 SHALL 提供当前源码版本的报告生成前 readiness 数据，使前端能够在用户创建报告任务前判断是否可生成报告并展示原因；确认迁移输入数量 SHALL 作为报告内容事实而不是报告生成阻塞条件。

#### Scenario: 当前源码版本存在 confirmed 输入
- **WHEN** 项目存在 active source revision
- **AND** 当前源码版本下至少存在一条 `status=CONFIRMED` 的 migration input reference
- **THEN** readiness SHALL 返回 `canGenerate=true`
- **AND** 阶段 readiness 中的 `INCLUDED_FINDINGS` SHALL 返回 `SATISFIED`
- **AND** readiness SHALL 返回当前源码版本摘要、confirmed 输入数量、按来源统计和按风险等级统计
- **AND** readiness SHALL 返回最新评估报告摘要或空值

#### Scenario: 当前源码版本没有 confirmed 输入
- **WHEN** 项目存在 active source revision
- **AND** 当前源码版本下不存在 `status=CONFIRMED` 的 migration input reference
- **THEN** readiness SHALL 返回 `canGenerate=true`
- **AND** 阶段 readiness 中的 `INCLUDED_FINDINGS` SHALL 返回 `SATISFIED`
- **AND** `INCLUDED_FINDINGS.details.count` SHALL 为 0
- **AND** blockers MUST NOT 包含 `REPORT_NO_CONFIRMED_INPUTS` 或等价的输入缺失原因
- **AND** 后端 SHALL 允许创建报告生成任务并生成全零报告
- **AND** 后端 MUST NOT 为 readiness 查询本身创建报告任务

#### Scenario: 项目没有 active source revision
- **WHEN** 项目没有 active source revision 且请求未指定有效源码版本
- **THEN** readiness SHALL 返回 `canGenerate=false`
- **AND** blockers SHALL 包含 `SOURCE_REVISION_REQUIRED`
- **AND** 阶段 readiness 中的 `INCLUDED_FINDINGS` SHALL 返回 `MISSING`
- **AND** 后端 MUST NOT 创建报告生成任务

#### Scenario: 低风险候选提示
- **WHEN** 当前源码版本下存在 `detectedLevel` 归一化为 `LOW` 且 `status=CANDIDATE` 的 reference
- **THEN** readiness SHALL 返回候选数量
- **AND** warnings SHALL 包含低风险候选未进入报告的提示
- **AND** 报告生成 MUST NOT 默认消费这些 `CANDIDATE` reference

### Requirement: 评估报告节点必须提供生成前输入预览
迁移评估报告运行时 SHALL 支持在报告生成前分页预览当前源码版本下的 migration input reference，供用户审计报告输入池。

#### Scenario: 查询输入预览
- **WHEN** 用户查询某项目当前源码版本的报告输入预览
- **THEN** 后端 SHALL 返回分页列表
- **AND** 每条记录 SHALL 包含 reference ID、sourceType、sourceRefId、issueTitle、detectedLevel、locationLabel、status、recommendationSummary、note、更新时间和来源定位摘要
- **AND** 响应 MUST NOT 返回完整来源详情、服务器真实路径、对象存储内部 key 或明文凭据

#### Scenario: 输入预览过滤排序
- **WHEN** 用户按 `sourceType`、`status`、风险等级或关键字过滤输入预览
- **THEN** 后端 SHALL 使用 AND 语义组合过滤条件
- **AND** 后端 SHALL 支持稳定排序白名单
- **AND** 非法排序字段 SHALL 返回统一业务错误

#### Scenario: 输入预览不修改输入状态
- **WHEN** 用户查询输入预览
- **THEN** 后端 MUST NOT 创建、确认、撤回或删除 migration input reference
- **AND** 用户状态变更 SHALL 继续通过节点内确认或 migration input 状态更新接口完成

### Requirement: 评估报告详情必须区分历史快照和当前输入状态
迁移评估报告详情 SHALL 同时表达报告生成时的不可变输入快照摘要和当前源码版本下的输入状态摘要，避免用户误解重新确认后的历史报告内容。

#### Scenario: 查看报告详情包含当前输入摘要
- **WHEN** 用户查看已生成评估报告详情
- **THEN** 响应 SHALL 返回报告生成时的 summary 和 artifact 摘要
- **AND** 响应 SHALL 返回该报告源码版本当前 migration input 的状态统计
- **AND** 当前输入摘要 SHALL 按 `CONFIRMED`、`CANDIDATE`、`EXCLUDED`、sourceType 和风险等级聚合

#### Scenario: 历史报告快照不随当前输入变化
- **WHEN** 报告生成后用户修改同源码版本下 migration input reference 状态或备注
- **THEN** 报告详情中的历史报告 summary 和下载内容 SHALL 保持生成时内容
- **AND** 当前输入摘要 MAY 反映最新状态

### Requirement: 评估报告节点必须暴露历史报告比较准备信息
评估报告运行时 SHALL 在报告页聚合数据中提供历史报告比较准备信息，使前端能从评估报告页进入报告比较。

#### Scenario: 存在可比较历史报告
- **WHEN** 当前源码版本存在最新评估报告
- **AND** 同项目存在早于该报告且状态成功的同类型历史报告
- **THEN** readiness 或 overview SHALL 返回可比较历史报告摘要
- **AND** 后端 SHALL 保持实际比较创建由报告比较 API 完成

#### Scenario: 不存在可比较历史报告
- **WHEN** 当前报告没有可比较历史报告
- **THEN** readiness 或 overview SHALL 返回空比较准备信息
- **AND** 后端 MUST NOT 将该情况视为报告生成 blocker

### Requirement: 评估报告必须返回当前输入更新状态
评估报告 readiness 和详情 API SHALL 比较当前 confirmed migration input refs 与最新评估报告输入快照，并返回报告是否需要更新。

#### Scenario: 最新报告覆盖当前输入
- **WHEN** 当前源码版本存在最新成功评估报告
- **AND** 当前 `CONFIRMED` migration input reference 集合与该报告 `report_inputs` 快照集合一致
- **THEN** readiness 和报告详情 SHALL 返回 `reportUpToDate=true`
- **AND** 更新摘要 SHALL 显示新增、移除和变化数量均为 `0`

#### Scenario: 当前输入多于最新报告
- **WHEN** 当前源码版本存在最新成功评估报告
- **AND** 当前 `CONFIRMED` migration input reference 中存在未进入最新报告快照的记录
- **THEN** readiness 和报告详情 SHALL 返回 `reportUpToDate=false`
- **AND** 更新摘要 SHALL 返回新增输入数量和示例摘要

#### Scenario: 当前输入少于最新报告
- **WHEN** 当前源码版本存在最新成功评估报告
- **AND** 最新报告快照中的输入已被撤回或不再处于 `CONFIRMED`
- **THEN** readiness 和报告详情 SHALL 返回 `reportUpToDate=false`
- **AND** 更新摘要 SHALL 返回移除输入数量和示例摘要

#### Scenario: 当前输入字段发生变化
- **WHEN** 当前源码版本存在最新成功评估报告
- **AND** 同一 migration input reference 的报告可见字段与最新报告快照不一致
- **THEN** readiness 和报告详情 SHALL 返回 `reportUpToDate=false`
- **AND** 更新摘要 SHALL 返回变化输入数量

#### Scenario: 尚未生成报告
- **WHEN** 当前源码版本不存在成功评估报告
- **THEN** readiness SHALL 返回 `reportUpToDate=false`
- **AND** 更新摘要 SHALL 标明 `latestReportMissing=true`

### Requirement: 迁移评估报告失败必须可靠写入报告终态
迁移评估报告运行时 SHALL 保证报告生成任务失败、取消或成功时，`reports.status` 与任务终态保持一致或能表达同等终态，不得因报告生成内部事务回滚使报告长期停留在 `PENDING` 或 `RUNNING`。

#### Scenario: 报告生成过程中发生运行时异常
- **WHEN** `REPORT_GENERATE` handler 在读取输入、写入快照、生成内容、保存制品或登记附加索引阶段发生运行时异常
- **THEN** 后端 SHALL 将对应 `reports.status` 写为 `FAILED`
- **AND** `reports.summary` SHALL 包含脱敏后的错误码、错误阶段和错误摘要
- **AND** 任务 SHALL 进入 `FAILED`
- **AND** 报告状态写入 MUST NOT 被报告生成主事务回滚

#### Scenario: 报告生成任务被取消
- **WHEN** `REPORT_GENERATE` handler 检测到任务取消
- **THEN** 后端 SHALL 将对应 `reports.status` 写为 `CANCELLED`
- **AND** 任务 SHALL 进入 `CANCELLED`
- **AND** 报告状态写入 MUST NOT 被报告生成主事务回滚

#### Scenario: 没有确认输入生成空报告
- **WHEN** 报告生成任务发现当前源码版本没有 `CONFIRMED` 迁移输入
- **THEN** 后端 SHALL 将对应 `reports.status` 写为 `SUCCEEDED`
- **AND** 后端 SHALL 写入空的 `report_inputs` 快照
- **AND** 后端 SHALL 生成 HTML 和 JSON 空报告 artifact
- **AND** 报告任务 MUST NOT 因没有 confirmed 输入失败

### Requirement: 迁移评估报告归档候选必须使用安全聚合摘要
迁移评估报告运行时 SHALL 在成功生成报告后登记归档候选，但候选 summary MUST 只包含安全聚合信息和报告引用，完整报告明细 SHALL 通过报告 artifact 和 `report_inputs` 快照保存。

#### Scenario: 报告明细包含路径逃逸文本
- **WHEN** confirmed migration input 中存在 `include:../include` 或其他包含 `../` 的报告明细文本
- **THEN** 报告 HTML 和 JSON artifact SHALL 能正常包含该报告明细
- **AND** 归档候选 summary MUST NOT 保存该明细文本
- **AND** 归档候选登记 MUST NOT 因该明细文本失败

#### Scenario: 报告成功后登记归档候选
- **WHEN** 迁移评估报告成功生成 HTML 和 JSON artifact
- **THEN** 后端 SHALL 登记当前项目和源码版本下的迁移报告归档候选
- **AND** 候选 summary SHALL 至少包含报告 ID、风险等级、confirmed 输入数量、高风险数量、工作量估算、来源统计和风险统计
- **AND** 候选 SHALL 包含 HTML 和 JSON artifact 引用

#### Scenario: 归档候选登记异常
- **WHEN** 报告 artifact 已保存且 `reports.status` 已写入 `SUCCEEDED`
- **AND** 归档候选登记发生异常
- **THEN** 后端 MUST NOT 将已成功生成的报告回滚为失败
- **AND** 后端 SHALL 写入脱敏 warning 日志或任务日志摘要，说明归档候选登记失败

### Requirement: 评估报告必须过滤过期依赖输入
迁移评估报告 readiness、输入预览和报告生成 SHALL 只消费当前源码版本下有效的 `DEPENDENCY_RESULT` 输入，避免历史依赖分析 run 的重复或过期 reference 进入当前报告。

#### Scenario: readiness 统计排除过期依赖输入
- **GIVEN** 当前源码版本存在旧依赖分析 run 的 `CONFIRMED` reference
- **AND** 同一源码版本存在更新的成功依赖分析 run
- **WHEN** 用户查询评估报告 readiness
- **THEN** readiness 的 confirmed 输入统计 MUST 排除旧 run 的过期依赖 reference
- **AND** readiness MUST 基于当前有效输入池返回统计

#### Scenario: 输入预览不展示过期依赖输入
- **GIVEN** 当前源码版本存在历史重复的 `gcc` dependency reference
- **WHEN** 用户查询评估报告输入预览
- **THEN** 输入预览 MUST NOT 同时展示多个语义重复的 `gcc` 依赖输入
- **AND** 输入预览 MUST 优先展示当前最新成功依赖分析 run 对应的输入

#### Scenario: 报告生成不消费旧 confirmed gcc
- **GIVEN** 旧依赖分析 run 中存在 `gcc` reference 且状态为 `CONFIRMED`
- **AND** 当前最新依赖分析 run 中对应 `gcc` reference 状态为 `CANDIDATE`
- **WHEN** 用户生成评估报告
- **THEN** 报告 MUST NOT 因旧 `CONFIRMED` reference 将 `gcc` 写入报告
- **AND** 报告 MUST 按当前最新 reference 状态决定是否纳入该依赖

#### Scenario: 历史报告详情继续使用快照
- **GIVEN** 用户查看已经生成的历史评估报告
- **WHEN** 当前输入池中的过期依赖 reference 已被清理或过滤
- **THEN** 历史报告详情 SHALL 继续显示报告生成时保存的 `report_inputs` 快照
- **AND** 后端 MUST NOT 因当前输入池过滤而改变历史报告内容

### Requirement: 迁移报告必须按模块文件类型和问题组织代码输入
迁移评估报告 SHALL 将代码类 confirmed 输入组织为“模块、文件、问题类型、具体 finding”四级层级，并 SHALL 保证每条输入只计入一个主模块和一个文件分组。

#### Scenario: 生成代码输入层级
- **WHEN** 报告生成任务读取当前报告源码版本下的代码类 confirmed 输入
- **THEN** 后端 SHALL 为每条输入保存模块、文件、问题类型和 finding 的组织投影
- **AND** 模块 finding 总数 SHALL 等于已组织代码类报告输入总数
- **AND** 同一 finding MUST NOT 因关联多个构建目标而重复计数

#### Scenario: 输入缺少有效文件定位
- **WHEN** 代码类 confirmed 输入缺少路径或有效行号
- **THEN** 后端 SHALL 将输入保留为可审计的未定位条目
- **AND** 后端 MUST NOT 因无法定位而丢弃该输入或使报告生成失败

### Requirement: 模块识别必须使用确定性降级链
后端 SHALL 按显式构建目标、构建产物或链接关系、最近构建描述文件、目录分组、项目根模块的顺序识别代码文件所属模块，并 SHALL 返回识别依据和置信度。

#### Scenario: 构建目标明确关联文件
- **WHEN** 报告绑定的构建上下文明确记录文件属于某个构建目标
- **THEN** 后端 SHALL 优先使用该构建目标作为模块
- **AND** 模块 SHALL 返回稳定的 `moduleKey`、`moduleName`、`basis` 和 `confidence`

#### Scenario: 构建上下文不足
- **WHEN** 文件无法通过构建目标或构建产物关系识别模块
- **THEN** 后端 SHALL 依次尝试最近构建描述文件和目录分组
- **AND** 所有策略均无法形成分组时 SHALL 回退到项目根模块

#### Scenario: 文件关联多个构建目标
- **WHEN** 同一文件被多个构建目标引用
- **THEN** 后端 SHALL 将文件归入确定性的共享模块或主模块
- **AND** 响应 SHALL 提供关联模块标识
- **AND** 该文件中的 finding MUST NOT 被复制计数

### Requirement: 报告代码层级接口必须支持逐级统计和分页查询
后端 SHALL 提供报告代码模块、模块文件、文件问题类型和具体 finding 的独立查询接口，并 SHALL 在每一级返回前端展示直接下级所需的统计。

#### Scenario: 查询模块列表
- **WHEN** 有项目访问权限的用户查询报告代码模块
- **THEN** 后端 SHALL 返回分页模块列表
- **AND** 每个模块 SHALL 包含文件数、finding 数、问题类型数、最高风险、风险分布、类型分布、识别依据和置信度

#### Scenario: 查询模块下的文件和类型
- **WHEN** 有项目访问权限的用户查询指定模块的文件或指定文件的问题类型
- **THEN** 文件响应 SHALL 包含 finding 数、问题类型数、最高风险、风险分布和类型分布
- **AND** 类型响应 SHALL 包含 finding 数、最高风险、首行、末行和符号数
- **AND** 列表 SHALL 支持白名单过滤、排序和分页

#### Scenario: 查询具体 finding 的默认顺序
- **WHEN** 用户未提交 finding 排序参数
- **THEN** 后端 SHALL 按 `lineStart ASC NULLS LAST`、`lineEnd ASC NULLS LAST` 和稳定 ID 升序返回

#### Scenario: 无权读取其他项目报告
- **WHEN** 用户查询无权访问项目中的报告层级数据
- **THEN** 后端 SHALL 拒绝请求
- **AND** 响应 MUST NOT 泄露模块、文件、finding 或源码上下文信息

### Requirement: 报告必须提供文件级联合源码上下文
后端 SHALL 为报告内代码文件提供联合源码上下文，默认覆盖首个纳入报告 finding 之前 20 行至最后一个纳入报告 finding 之后 20 行，并 SHALL 高亮该文件内所有纳入报告的 finding。

#### Scenario: 同一文件存在多个 finding
- **WHEN** 用户查询报告中某文件的联合上下文
- **THEN** 后端 SHALL 返回该文件所有已纳入报告 finding 的元数据
- **AND** 上下文 SHALL 从最早 finding 的起始行向前最多 20 行开始
- **AND** 上下文 SHALL 在最晚 finding 的结束行之后最多 20 行结束
- **AND** 每个代码行 SHALL 返回真实行号、文本和关联 finding 高亮

#### Scenario: 文件边界不足二十行
- **WHEN** finding 距离文件头或文件尾不足 20 行
- **THEN** 后端 SHALL 将上下文裁剪到真实文件边界
- **AND** 后端 MUST NOT 生成不存在的行号或占位代码

#### Scenario: 只包含生成报告时的 finding
- **WHEN** 同一路径在当前输入池中还有 candidate、excluded 或其他源码版本的 finding
- **THEN** 文件上下文 SHALL 只高亮该报告输入快照中的 confirmed finding
- **AND** 后端 MUST NOT 动态混入当前输入池或 active source revision 的其他问题

### Requirement: 文件上下文省略必须结构化表达
当联合上下文跨度超过服务端限制时，后端 SHALL 以 `CODE` 和 `OMITTED` block 返回内容，并 MUST NOT 将省略提示伪装成源码文字。

#### Scenario: 远距离 finding 之间产生省略区间
- **WHEN** 同一文件的 finding 窗口之间存在超过阈值的未命中行
- **THEN** 响应 SHALL 为真实源码返回 `kind=CODE` block
- **AND** 响应 SHALL 为省略范围返回 `kind=OMITTED` block
- **AND** `OMITTED` block SHALL 包含起止行、行数、稳定原因码和 `loadable` 状态

#### Scenario: 展开可加载省略区间
- **WHEN** 用户使用文件上下文 API 请求 `OMITTED` block 对应的合法行范围
- **THEN** 后端 SHALL 返回该范围内的真实代码行
- **AND** 返回内容 SHALL 继续使用报告绑定的源码版本

### Requirement: 文件上下文必须保持历史版本完整性和路径安全
报告文件上下文 SHALL 绑定报告的不可变 `sourceRevisionId`、规范化相对路径、内容哈希和行号范围，且 SHALL 通过对象存储制品或等价不可变快照提供内容。

#### Scenario: 源码更新后查看旧报告
- **WHEN** 项目 active source revision 已更新且用户查看旧报告文件上下文
- **THEN** 后端 SHALL 返回旧报告生成时绑定的源码内容和哈希
- **AND** 后端 MUST NOT 回退读取当前 active source revision

#### Scenario: 路径逃逸或文件不可读取
- **WHEN** 报告输入路径逃逸源码根、文件缺失、文件为二进制、文件过大或行号失效
- **THEN** 后端 SHALL 返回 `contextAvailable=false` 和稳定原因码
- **AND** 后端 MUST NOT 返回宿主机绝对路径、对象存储内部位置或底层异常细节
- **AND** 该情况 MUST NOT 使整份报告生成失败

### Requirement: 依赖迁移输入必须保持全局聚合展示
迁移评估报告 SHALL 将依赖分析输入独立于代码模块层级展示，并 SHALL 按 provider 软件包或待安装软件包聚合依赖证据。

#### Scenario: 同一软件包提供多个库或程序
- **WHEN** 多个 SO 或 ELF 证据解析到同一 provider 软件包
- **THEN** 报告 SHALL 只生成一个软件包主条目
- **AND** SO 或 ELF SHALL 作为该条目的 evidence 展示
- **AND** 条目 SHALL 展示依赖类型、目标匹配状态、风险和一键修复状态

#### Scenario: 依赖没有代码文件定位
- **WHEN** confirmed 依赖输入没有源码文件位置
- **THEN** 后端 SHALL 将其保留在全局依赖迁移列表
- **AND** 后端 MUST NOT 将其强行归入项目根代码模块

### Requirement: HTML 和 JSON 报告必须共享组织口径
后端 SHALL 使用同一版本化报告视图模型生成 HTML 与 JSON 报告，并 SHALL 包含执行摘要、代码模块/文件层级、全局依赖迁移列表和原始证据附录。

#### Scenario: 生成组织化报告制品
- **WHEN** 报告生成任务成功完成
- **THEN** HTML 和 JSON 的模块数、文件数、finding 数、风险分布和依赖条目数 SHALL 一致
- **AND** HTML SHALL 默认以聚合摘要展示并避免一次渲染全部源码行
- **AND** JSON SHALL 通过 schemaVersion 标识新的组织结构

#### Scenario: 查看缺少组织投影的历史报告
- **WHEN** 用户查看本变更前生成且没有组织投影的历史报告
- **THEN** 后端 SHALL 返回 `organizationAvailable=false` 或等价兼容状态
- **AND** 既有平铺输入接口及历史 HTML/JSON 下载 SHALL 保持可用
- **AND** 后端 MUST NOT 使用当前算法覆盖历史报告内容

### Requirement: 迁移报告必须支持浮点和内存序 Finding
迁移报告 SHALL 消费当前源码版本已确认的 `FLOATING_POINT_FINDING` 与 `MEMORY_ORDER_FINDING` reference，并 SHALL 将其作为代码 Finding 组织到模块、文件、问题类型和行号层级。

#### Scenario: 组织浮点 Finding
- **WHEN** 报告输入包含已确认浮点 Finding
- **THEN** 报告 SHALL 展示规则、风险、影响、建议、测试建议、validation plan 和源码位置
- **AND** 多 occurrence SHALL 能在文件视角中高亮

#### Scenario: 组织内存序 Finding
- **WHEN** 报告输入包含已确认内存序 Finding
- **THEN** 报告 SHALL 展示并发问题、风险、置信度、同步缺口、建议、假设、限制和证据断点
- **AND** MUST 区分 formal risk 与 source candidate

#### Scenario: Finding 没有位置
- **WHEN** 已确认 Finding 不具有可信文件位置
- **THEN** 报告 SHALL 将其放入未定位分组
- **AND** 报告生成 MUST NOT 因缺少位置失败

### Requirement: 报告摘要必须计入专项分析风险
报告 SHALL 将两类已确认 Finding 计入总问题数、高风险数量、风险分布、模块/文件统计、优先处理项和预计工作量。

#### Scenario: 统计严重专项 Finding
- **WHEN** 报告包含 CRITICAL 或 HIGH 浮点/内存序 Finding
- **THEN** 高风险数量 SHALL 包含这些 Finding
- **AND** 主要风险 SHALL 能引用其双语标题与建议

#### Scenario: PARTIAL 证据提示
- **WHEN** 已确认 Finding 或其来源运行为 PARTIAL、unknown 或 source candidate
- **THEN** 报告 SHALL 显示证据限制和人工确认提示
- **AND** MUST NOT 把不确定结论描述为确定缺陷

### Requirement: 报告 JSON 与 HTML 必须共享专项分析口径
JSON 和 HTML 报告 SHALL 使用同一输入快照和聚合数据，且 SHALL 保留专项分析来源类型以供前端分组和报告比较。

#### Scenario: 生成双格式报告
- **WHEN** 报告包含任一专项分析 Finding
- **THEN** JSON 与 HTML 的数量、风险、模块、文件和 Finding ID SHALL 一致
- **AND** 两种格式 MUST NOT 暴露工具工作目录或对象存储内部信息
