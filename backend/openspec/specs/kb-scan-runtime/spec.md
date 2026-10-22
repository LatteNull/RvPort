## Purpose

定义知识库扫描运行时能力的执行边界、输入输出契约和结果查询方式。该能力覆盖后端如何调用独立 KB Scanner CLI、如何读取项目源码版本、如何持久化 finding 和代码上下文、如何生成可下载制品，以及如何避免泄露服务器本机路径。
## Requirements
### Requirement: KB Scanner 必须作为独立 CLI 运行
后端 SHALL 通过受控本地进程调用根目录 `tools/kb-scanner`，并 SHALL NOT 将 KB Scanner 嵌入为 Java 内部库。

#### Scenario: 调用 KB Scanner
- **WHEN** worker 执行 `KB_SCAN` 任务
- **THEN** 后端 SHALL 使用配置的 Python 命令执行 `python -m kb_scanner scan`
- **AND** 后端 SHALL 提交源码工作副本目录、规则集目录、输出目录、输出格式和扫描选项
- **AND** 后端 SHALL 将本地进程登记到任务执行上下文以支持取消
- **AND** 任务事件、API 响应和日志摘要 MUST NOT 暴露服务器真实路径或完整命令行

#### Scenario: Scanner 输出文件
- **WHEN** KB Scanner 执行完成
- **THEN** 后端 SHALL 从受控输出目录读取 `scan-result.json`
- **AND** 后端 MAY 读取 `scan-report.html` 和 `scan.log` 生成 artifact 或报告摘要
- **AND** 后端 MUST NOT 要求前端直接读取服务器文件路径

#### Scenario: Scanner 失败
- **WHEN** KB Scanner 启动失败、超时、返回非零退出码、缺少 `scan-result.json` 或结果 JSON 无法解析
- **THEN** worker SHALL 将 `KB_SCAN` 任务和 `kb_scan_runs` 标记为 `FAILED`
- **AND** 后端 SHALL 写入 tool run、任务日志和安全错误摘要
- **AND** 后端 MUST NOT 写入成功态 findings

### Requirement: KB 扫描运行必须绑定项目源码版本
KB 扫描 SHALL 基于 `source_revisions` 的后端本机工作副本执行，并 SHALL 校验源码版本属于当前项目。

#### Scenario: 使用指定源码版本
- **WHEN** 用户创建 KB 扫描任务并提交 `sourceRevisionId`
- **THEN** 后端 SHALL 校验该源码版本属于 URL 中的 `projectId`
- **AND** 后端 SHALL 校验该源码版本存在可用 `working_copy_path`
- **AND** 后端 SHALL 使用该源码版本创建 `kb_scan_runs`

#### Scenario: 使用当前启用源码版本
- **WHEN** 用户创建 KB 扫描任务且未提交 `sourceRevisionId`
- **THEN** 后端 SHALL 查询该项目当前启用源码版本
- **AND** 若不存在当前启用源码版本，API SHALL 返回明确业务错误
- **AND** 后端 MUST NOT 创建任务或投递队列消息

#### Scenario: 跨项目源码版本
- **WHEN** 用户在项目 A 的 KB 扫描请求中提交项目 B 的源码版本 ID
- **THEN** 后端 SHALL 拒绝请求
- **AND** 后端 MUST NOT 暴露项目 B 的源码版本路径、状态或存在性细节
- **AND** 后端 MUST NOT 创建任务、扫描运行或队列消息

### Requirement: KB 扫描结果必须按行导入 findings
后端 SHALL 将 KB Scanner 输出的每条 finding 分别写入 `findings` 表，支持后续分页、过滤、排序和审计。

#### Scenario: 导入 findings
- **WHEN** `scan-result.json` 包含 findings
- **THEN** 后端 SHALL 为每条 finding 创建 `findings` 记录
- **AND** 每条记录 SHALL 关联 `project_id`、`scan_run_id` 和 `source_revision_id`
- **AND** 后端 SHALL 保存 rule、category、severity、title、description、file path、line range、symbol、suggestion、fingerprint 和受控 evidence
- **AND** 后端 MUST NOT 将完整 `scan-result.json` 原文整体塞入单个字段作为查询事实

#### Scenario: 空 finding 结果
- **WHEN** KB Scanner 成功完成但 findings 为空
- **THEN** 后端 SHALL 将 `KB_SCAN` 任务和 `kb_scan_runs` 标记为 `SUCCEEDED`
- **AND** 后端 SHALL 保存 findings 总数为 0 的 summary
- **AND** findings 列表 API SHALL 返回空分页列表

#### Scenario: 重复 finding fingerprint
- **WHEN** 同一次扫描输出多个相同 fingerprint 的 finding
- **THEN** 后端 SHALL 使用稳定策略处理重复项
- **AND** 后端 SHALL 保证 API 查询结果可审计并能追溯 scanner 原始 finding id
- **AND** 后端 MUST NOT 因重复项导致整次成功扫描错误失败，除非数据库约束要求唯一且无法安全合并

### Requirement: KB 扫描必须保存安全摘要和 artifact 元数据
后端 SHALL 保存 KB 扫描结果摘要、报告摘要和日志摘要，使前端能查看扫描结论而不暴露服务器真实路径。

#### Scenario: 保存运行摘要
- **WHEN** KB 扫描成功完成
- **THEN** 后端 SHALL 更新 `kb_scan_runs.summary`
- **AND** summary SHALL 包含 schema version、tool version、rule pack、文件数、finding 总数、issue/hint 数量、severity counts 和 diagnostics 摘要
- **AND** summary MUST NOT 包含源码工作副本路径、输出目录或完整日志

#### Scenario: 保存报告 artifact
- **WHEN** KB Scanner 生成 `scan-report.html`、`scan-result.json` 或 `scan.log`
- **THEN** 后端 SHALL 保存受控 artifact 元数据或等效报告记录
- **AND** 元数据 SHALL 包含 artifact type、sha256、size bytes、created at 和安全 summary
- **AND** API 响应 MUST NOT 返回服务器真实文件路径

#### Scenario: Artifact 内容安全
- **WHEN** 后端向 API 返回 KB artifact 或报告内容
- **THEN** 后端 SHALL 执行项目访问权限校验
- **AND** 响应 MUST NOT 包含明文凭据、私钥、token、passphrase、后端本地 runtime 路径或完整任务输入快照

### Requirement: KB 扫描必须使用统一服务器路径安全工具
KB 扫描相关文件访问和路径脱敏 SHALL 使用统一服务器路径安全工具，避免各模块重复实现不一致的 `normalize`、`toRealPath`、边界校验和文本替换逻辑。

#### Scenario: 解析根目录内既有文件
- **WHEN** 后端需要读取 KB artifact、源码文件或其他服务器本地文件
- **THEN** 后端 SHALL 将根目录和候选路径转换为绝对规范路径
- **AND** 后端 SHALL 对既有文件执行真实路径校验
- **AND** 若候选路径不在允许根目录内或通过符号链接逃逸，后端 SHALL 拒绝读取
- **AND** 错误响应 MUST NOT 暴露服务器真实路径

#### Scenario: 解析根目录内相对路径
- **WHEN** 后端根据 scanner 输出、finding `file_path` 或用户输入的相对路径定位文件
- **THEN** 后端 SHALL 将候选路径解析到允许根目录下
- **AND** 后端 MUST 拒绝绝对路径、`..` 路径段、normalize 后越界路径和符号链接逃逸
- **AND** 后端 MUST NOT 允许客户端通过路径参数读取任意服务器文件

#### Scenario: 脱敏根目录内路径文本
- **WHEN** 后端向 API 响应、任务事件、日志摘要、tool run summary 或 finding evidence 写入路径文本
- **THEN** 后端 SHALL 将允许根目录内的服务器绝对路径替换为受控占位符或相对路径
- **AND** 输出 MUST NOT 包含源码工作副本根路径、KB 输出根路径、后端 runtime 根路径或用户 home 下真实路径

#### Scenario: 处理根目录外路径文本
- **WHEN** 待返回文本中包含不属于允许根目录的服务器绝对路径
- **THEN** 后端 SHALL 将其替换为 `<server-path-redacted>` 或返回安全错误
- **AND** 后端 MUST NOT 将根目录外服务器绝对路径原样返回给 API 客户端

### Requirement: KB artifact 下载必须校验输出根目录边界
KB artifact 下载 SHALL 在项目权限校验之后、返回文件之前校验 artifact `content_path` 位于受控 KB 输出根目录内。

#### Scenario: 下载合法 artifact 文件
- **WHEN** 用户下载 KB 扫描 artifact 且 `content_path` 指向 KB 输出根目录内的既有普通文件
- **THEN** 后端 SHALL 返回该文件内容
- **AND** 响应 SHALL 使用由 artifact type 和 scan id 生成的安全文件名
- **AND** 响应 MUST NOT 返回 artifact `content_path`

#### Scenario: artifact content path 越界
- **WHEN** artifact `content_path` 指向 KB 输出根目录之外、包含路径逃逸或通过符号链接逃逸
- **THEN** 后端 SHALL 拒绝下载
- **AND** 后端 SHALL 返回安全错误
- **AND** 后端 MUST NOT 返回真实路径、符号链接目标或文件系统异常细节

#### Scenario: artifact 文件不存在
- **WHEN** artifact metadata 存在但 `content_path` 对应文件不存在或不是普通文件
- **THEN** 后端 SHALL 返回 artifact 文件不存在的安全错误
- **AND** 后端 MUST NOT 暴露服务器真实路径

### Requirement: KB finding 必须支持代码上下文读取
后端 SHALL 为单个 finding 提供代码上下文读取能力，用于前端展示源码片段并高亮 finding 命中行。

#### Scenario: 读取 finding 代码上下文
- **WHEN** 用户查询 finding 代码上下文
- **THEN** 后端 SHALL 使用 finding 所属 `source_revision_id` 定位源码工作副本
- **AND** 后端 SHALL 使用 finding 保存的相对 `file_path` 定位源码文件
- **AND** 后端 SHALL 返回实际读取的起始行、结束行、命中起始行、命中结束行和逐行代码内容
- **AND** 每行代码 SHALL 标记是否属于 finding 命中行范围，便于前端高亮

#### Scenario: 防止路径逃逸
- **WHEN** 后端根据 finding `file_path` 定位源码文件
- **THEN** 后端 SHALL 使用统一服务器路径安全工具校验源码工作副本边界
- **AND** 后端 MUST NOT 允许绝对路径、`..` 路径段、normalize 后越界路径或符号链接逃逸读取工作副本之外的文件
- **AND** 失败响应 MUST NOT 暴露服务器真实路径

#### Scenario: 控制上下文大小
- **WHEN** 用户查询 finding 代码上下文
- **THEN** 后端 SHALL 固定返回命中代码起始行之前最多 20 行和命中代码结束行之后最多 20 行
- **AND** 后端 SHALL 在响应中返回 `contextBefore=20`、`contextAfter=20` 与实际起止行
- **AND** 当源码文件开头或结尾不足 20 行时，后端 SHALL 返回实际可用行数
- **AND** 后端 MUST NOT 允许客户端通过参数扩大代码上下文范围

### Requirement: KB 扫描必须写入进度、日志和 tool run
KB_SCAN handler SHALL 通过任务执行上下文写入阶段进度、日志事件和工具执行记录。

#### Scenario: 写入阶段进度
- **WHEN** KB_SCAN handler 校验输入、准备输出、启动 scanner、解析结果和导入 findings
- **THEN** handler SHALL 写入单调递增的任务进度事件
- **AND** 项目级 SSE SHALL 能推送这些进度事件

#### Scenario: 写入任务日志
- **WHEN** Scanner 产生 stdout、stderr 或 scan.log
- **THEN** 后端 SHALL 写入任务日志和任务级日志事件
- **AND** 日志内容 SHALL 经过脱敏和大小控制
- **AND** 任务级日志 SSE SHALL 能补发历史日志并推送新增日志

#### Scenario: 写入 tool run
- **WHEN** 后端调用 KB Scanner
- **THEN** 后端 SHALL 写入 `tool_runs`
- **AND** `tool_runs.tool_name` SHALL 使用稳定工具名 `kb-scanner`
- **AND** `tool_runs.exit_code` SHALL 保存进程退出码
- **AND** `tool_runs.summary` SHALL 保存版本、规则集摘要、输出摘要、耗时和安全诊断摘要

### Requirement: KB scanner 输出路径必须统一脱敏
KB scanner 的 result、evidence、stdout、stderr、scan log、tool run summary 和失败摘要 SHALL 通过与数据类型匹配的路径脱敏逻辑处理后才能进入 API 可见数据，并 MUST 保持结构化结果有效和源码证据语义完整。

#### Scenario: 脱敏 scanner evidence
- **WHEN** scanner finding evidence 中包含源码根目录、scanner 输出目录或其他服务器绝对路径
- **THEN** 后端 SHALL 在写入 `findings.evidence` 前脱敏服务器路径
- **AND** `findings.evidence` MUST NOT 保存服务器真实路径
- **AND** 后端 MUST NOT 修改 matched text、代码上下文或建议文本中的安全相对路径和源码表达式

#### Scenario: 脱敏 scanner 日志和错误摘要
- **WHEN** scanner stdout、stderr、scan log 或异常消息包含服务器路径
- **THEN** 后端 SHALL 在写入任务日志事件、tool run summary 或任务错误摘要前脱敏路径
- **AND** API 和 SSE MUST NOT 推送服务器真实路径

#### Scenario: 结构化脱敏 JSON 制品
- **WHEN** scanner 生成合法的 `scan-result.json`
- **THEN** 后端 SHALL 将其解析为 JSON 结构后递归处理路径语义字段并重新序列化
- **AND** 脱敏后的 `scan-result.json` SHALL 仍能被 JSON parser 成功读取
- **AND** 安全的项目相对路径 SHALL 保持不变
- **AND** 后端 MUST NOT 通过对完整 JSON 文本运行通用路径正则完成脱敏

#### Scenario: 保留源码中的相对 include
- **WHEN** finding matched text 或代码上下文包含 `#include "../compat/header.h"` 等相对源码表达式
- **THEN** 脱敏后的 finding evidence 和 `scan-result.json` SHALL 保留该源码文本
- **AND** 后端 MUST NOT 将其中的相对 include 替换为服务器路径占位符

#### Scenario: 嵌套 JSON 路径脱敏
- **WHEN** scanner 输出中的服务器绝对路径出现在嵌套 JSON object、array 或路径语义字符串中
- **THEN** 后端 SHALL 递归脱敏这些路径
- **AND** 后端 MUST NOT 只处理顶层字段

### Requirement: KB 扫描成功事实不得被归档候选登记异常反转
KB 扫描运行时 SHALL 区分 Scanner 执行、结果导入和制品保存失败与归档候选登记失败，避免把成功扫描误报为 Scanner 失败。

#### Scenario: Scanner 和结果导入成功
- **WHEN** Scanner 成功退出、schema v2 结果通过解析、findings 完成入库且必要制品保存成功
- **THEN** KB 扫描和对应任务 SHALL 进入 `SUCCEEDED`
- **AND** 后端 SHALL 尝试登记 KB 扫描归档候选

#### Scenario: 成功扫描后的归档候选登记失败
- **WHEN** Scanner、结果导入和制品保存已经成功，但归档候选登记发生异常
- **THEN** KB 扫描 SHALL 保持 `SUCCEEDED`
- **AND** 对应任务 MUST NOT 因该异常重新执行完整 Scanner
- **AND** 后端 SHALL 写入不包含敏感内容和服务器真实路径的 warning 或 tool run 后处理摘要
- **AND** 后端 MUST NOT 将错误信息概括为“KB Scanner 扫描失败”

#### Scenario: Scanner 或结果导入失败
- **WHEN** Scanner 失败、JSON 无效、schema 不兼容、findings 导入失败或必要制品保存失败
- **THEN** KB 扫描 SHALL 按实际失败阶段进入 `FAILED`
- **AND** 后端 SHALL 保留可诊断且已脱敏的阶段摘要

### Requirement: KB 导入安全修复必须覆盖三类测试
KB 导入、路径脱敏和归档登记修复 SHALL 具备正常流程、异常流程和 edge case 自动化测试。

#### Scenario: 正常流程覆盖
- **WHEN** 测试执行包含空 `paths`、安全相对路径和相对 include 的合法 schema v2 结果
- **THEN** 扫描 SHALL 成功导入并登记归档候选
- **AND** JSON 制品 SHALL 保持合法且源码证据不变

#### Scenario: 异常流程覆盖
- **WHEN** 测试输入包含服务器绝对路径、目录穿越、秘密字段或无效 JSON
- **THEN** 后端 SHALL 按对应安全或导入错误拒绝内容
- **AND** 错误响应、日志和摘要 MUST NOT 泄露被拒绝的敏感值

#### Scenario: edge case 覆盖
- **WHEN** 测试输入包含空数组、嵌套路径集合、Windows 与 Unix 路径、源码字符串中的斜杠以及归档登记异常
- **THEN** 后端 SHALL 保持安全相对内容、脱敏服务器路径并维持正确扫描终态

### Requirement: KB 扫描必须配套测试覆盖
KB 扫描相关实现 SHALL 配套 Java 单元测试、轻量集成测试和 API E2E 测试，并覆盖正常流程、异常流程和 edge case。

#### Scenario: 覆盖正常流程
- **WHEN** 编写 KB 扫描测试
- **THEN** 测试 SHALL 覆盖创建扫描、默认 active source、指定 source revision、worker 调用 scanner、结果解析、findings 入库、列表查询、详情查询和日志事件

#### Scenario: 覆盖异常流程
- **WHEN** 编写 KB 扫描测试
- **THEN** 测试 SHALL 覆盖无项目权限、源码版本不存在、源码版本不属于项目、没有 active source、working copy 缺失、scanner 失败、JSON 无效和结果导入失败

#### Scenario: 覆盖 edge case
- **WHEN** 编写 KB 扫描测试
- **THEN** 测试 SHALL 覆盖空 findings、重复 fingerprint、超长日志、非法分页参数、非法排序字段、路径脱敏、取消运行中 scanner 和清理测试数据

### Requirement: KB findings 必须可加入迁移输入
KB 扫描结果 SHALL 能作为迁移输入 reference 的代码类来源，并 SHALL 保持源码版本一致性。

#### Scenario: KB finding 导入迁移输入
- **WHEN** 用户将 KB finding 加入迁移输入
- **THEN** 后端 SHALL 校验 finding 属于当前项目
- **AND** 后端 SHALL 校验 finding 的 `source_revision_id` 等于迁移输入 URL 中的 `sourceRevisionId`
- **AND** 后端 SHALL 使用 finding 的 title 生成 `issueTitle`
- **AND** 后端 SHALL 使用 finding 的 severity 生成 `detectedLevel`

#### Scenario: KB finding location label
- **WHEN** 后端为 KB finding 创建迁移输入 reference
- **THEN** `locationLabel` SHALL 使用 finding 的相对 `file_path` 和行号生成
- **AND** 单行 SHALL 表达为 `path:line`
- **AND** 行范围 SHALL 表达为 `path:start-end`
- **AND** 无行号时 SHALL 只使用相对路径

#### Scenario: 跨源码版本 finding 被拒绝
- **WHEN** 用户尝试把源码版本 A 的 finding 导入源码版本 B 的迁移输入
- **THEN** 后端 SHALL 拒绝请求
- **AND** 后端 MUST NOT 创建迁移输入 reference

### Requirement: KB 扫描 artifact 必须支持对象存储
KB 扫描运行时 SHALL 支持将新生成的扫描输出制品保存到对象存储，并 SHALL 保持现有 KB 业务下载接口语义。

#### Scenario: 保存 KB 输出到对象存储
- **WHEN** KB Scanner 生成 `scan-result.json`、`scan-report.html` 或 `scan.log`
- **THEN** 后端 SHALL 能将文件内容上传到对象存储
- **AND** 后端 SHALL 保存输出制品元数据
- **AND** 元数据 SHALL 关联 `project_id`、`task_id` 和 `scan_run_id`

#### Scenario: 下载对象存储中的 KB artifact
- **WHEN** 用户通过 KB artifact 下载接口下载已保存到对象存储的 artifact
- **THEN** 后端 SHALL 校验 artifact 属于该 scan run
- **AND** 后端 SHALL 校验用户对 scan 所属项目有访问权限
- **AND** 后端 SHALL 从对象存储读取内容并返回安全文件名

#### Scenario: 兼容历史本地 KB artifact
- **WHEN** KB artifact 只有历史 `content_path` 且没有对象存储元数据
- **THEN** 后端 MAY 继续按受控本地路径规则读取历史文件
- **AND** 后端 MUST 继续校验 KB 输出根目录边界

### Requirement: 知识库扫描说明必须满足严格校验
`kb-scan-runtime` 主 spec 的 Purpose SHALL 清晰描述知识库扫描运行时的独立 CLI 调用、源码输入、finding 输出、代码上下文和制品边界。

#### Scenario: 严格校验知识库扫描说明
- **WHEN** 执行 `openspec validate kb-scan-runtime --type spec --strict`
- **THEN** 该 spec SHALL 不再因为 `Purpose section is too brief` 失败

### Requirement: KB 扫描节点必须支持本节点确认进入报告
KB 扫描运行时 SHALL 支持在 KB 扫描节点内将 finding 加入、撤回或确认为报告输入。

#### Scenario: KB finding 默认确认
- **WHEN** KB 扫描任务成功写入 finding
- **AND** finding severity 归一化为 `CRITICAL`、`HIGH`、`MEDIUM`、`INFO` 或 `COMMENT`
- **THEN** 后端 SHALL 创建或维护对应 `KB_FINDING` migration input reference
- **AND** reference 状态 SHALL 默认为 `CONFIRMED`

#### Scenario: KB finding 低风险默认候选
- **WHEN** KB 扫描任务成功写入 finding
- **AND** finding severity 归一化为 `LOW`
- **THEN** 后端 SHALL 创建或维护对应 `KB_FINDING` migration input reference
- **AND** reference 状态 SHALL 默认为 `CANDIDATE`

#### Scenario: KB 节点人工撤回
- **WHEN** 用户在 KB 扫描节点撤回某个 finding
- **THEN** 后端 SHALL 将对应 migration input reference 状态更新为 `EXCLUDED`
- **AND** 报告生成 MUST NOT 使用该 finding

#### Scenario: KB 节点人工加入低风险
- **WHEN** 用户在 KB 扫描节点人工加入 `LOW` finding
- **THEN** 后端 SHALL 将对应 migration input reference 状态更新为 `CONFIRMED`
- **AND** 报告生成 SHALL 可以使用该 finding

### Requirement: KB 扫描必须自动复用构建上下文 compile database
KB 扫描运行时 SHALL 在执行 scanner 前自动查找同一项目和源码版本下最新成功 source/x86 构建保存的 compile database，并在可用时传给 KB Scanner。

#### Scenario: 自动使用最新成功构建上下文
- **WHEN** worker 执行 `KB_SCAN` 任务
- **AND** 同一 `projectId` 和 `sourceRevisionId` 存在最新成功 source/x86 构建
- **AND** 该构建的 `build_facts.compileDatabase.available=true`
- **THEN** worker SHALL 从对象存储下载对应 compile database 到受控临时文件
- **AND** worker SHALL 调用 KB Scanner 时传入 `--compile-commands <temp-file>`
- **AND** `kb_scan_runs.summary.compileCommands.mode` SHALL 为 `USED`
- **AND** summary SHALL 记录来源 build run ID、stored artifact ID、sha256 和 command count

#### Scenario: 没有构建上下文时降级扫描
- **WHEN** worker 执行 `KB_SCAN` 任务
- **AND** 同一源码版本不存在可用 compile database
- **THEN** worker SHALL 不传 `--compile-commands`
- **AND** KB Scanner SHALL 按源码上下文扫描继续执行
- **AND** `kb_scan_runs.summary.compileCommands.mode` SHALL 为 `NOT_AVAILABLE`
- **AND** summary SHALL 保存安全原因码

#### Scenario: artifact 下载失败时降级扫描
- **WHEN** worker 找到 compile database artifact 但对象存储下载失败或内容不可用
- **THEN** worker SHALL 记录 warning
- **AND** worker SHALL 不传 `--compile-commands`
- **AND** KB Scanner SHALL 按源码上下文扫描继续执行
- **AND** `kb_scan_runs.summary.compileCommands.mode` SHALL 为 `FALLBACK`

#### Scenario: 源码版本隔离
- **WHEN** 项目上传或同步新源码并产生新的 `source_revision_id`
- **THEN** KB 扫描 MUST NOT 复用旧源码版本的 compile database
- **AND** 后端 SHALL 只查询与本次 scan run 相同 `source_revision_id` 的构建上下文

#### Scenario: 扫描输出继续脱敏
- **WHEN** KB Scanner 使用 compile database 产生 findings、diagnostics、stdout、stderr 或 artifacts
- **THEN** 后端 SHALL 继续执行现有路径脱敏和输出安全处理
- **AND** API、SSE 和 artifact summary MUST NOT 暴露 compile database 临时路径、远端路径或对象存储 key

### Requirement: KB Scanner 必须从 compile database 生成构建命令 finding
KB 扫描运行时 SHALL 在使用 compile database 时，将真实编译命令中明确的 x86/SIMD 编译参数和命令行宏转换为可入库的 KB finding。

#### Scenario: x86 编译参数生成 finding
- **WHEN** worker 执行 `KB_SCAN` 任务
- **AND** `kb_scan_runs.summary.compileCommands.mode=USED`
- **AND** compile database 中的真实编译命令包含明确 x86/SIMD 编译参数
- **THEN** KB Scanner SHALL 为这些参数生成 finding
- **AND** finding SHALL 使用稳定 rule id、severity、title、description、suggestion 和 fingerprint
- **AND** finding evidence SHALL 标记来源为 compile command

#### Scenario: 命令行宏生成 finding
- **WHEN** compile database 中的真实编译命令包含明确启用 x86/SIMD 路径的 `-D` 宏
- **THEN** KB Scanner SHALL 为该宏生成 finding 或附加到对应 finding evidence
- **AND** finding evidence SHALL 保存宏名、宏值摘要、关联源码相对路径和 compile command 索引
- **AND** scanner MUST NOT 将普通项目宏仅因名称格式相似就误判为 x86/SIMD 风险

#### Scenario: arguments 和 command 字段兼容
- **WHEN** compile database entry 提供 `arguments` 数组
- **THEN** KB Scanner SHALL 优先基于 `arguments` 解析 token
- **WHEN** compile database entry 只提供 `command` 字符串
- **THEN** KB Scanner SHALL 使用 shell-like 解析提取 token
- **AND** 解析失败 SHALL 记录 warning 并继续扫描其他 entry

#### Scenario: compile database 不得减少源码 finding
- **WHEN** KB Scanner 使用 compile database 执行扫描
- **THEN** scanner SHALL 保留默认源码扫描 finding
- **AND** scanner MUST NOT 仅因为某个源码、头文件或构建文件没有出现在 compile database 顶层 `file` 字段中而隐藏该 finding
- **AND** compile database SHALL 只能补充上下文、可达性信息或新增构建命令 finding

#### Scenario: 过滤未参与本次构建的配置项
- **WHEN** 仓库中存在 CMake、Meson、Ninja、Make 或 rpmbuild 配置文件
- **AND** 本次 compile database 没有真实执行对应工具或没有关联项目源码 entry
- **THEN** KB Scanner MUST NOT 仅因为配置文件存在就生成 compile command finding

#### Scenario: 过滤内部探测和越界命令
- **WHEN** compile database entry 的 `file` 不在当前源码版本工作副本内
- **OR** entry 命中 scanner 排除目录、排除文件或构建系统内部探测文件
- **THEN** KB Scanner MUST NOT 为该 entry 生成 compile command finding
- **AND** scanner MAY 在 diagnostics 中记录被过滤的安全原因码

#### Scenario: finding evidence 安全边界
- **WHEN** compile command 派生 finding 被写入数据库、API 响应、artifact 或任务日志
- **THEN** evidence MUST NOT 暴露服务器真实路径、远端绝对路径、compile database 临时路径、对象存储 key、凭据、token 或私钥
- **AND** evidence SHALL 使用源码相对路径和脱敏命令摘要表达命中位置

#### Scenario: 同源 finding 去重
- **WHEN** 同一次扫描中多个 compile database entry 产生相同 `sourceKind + ruleId + relativePath + token` 的 finding
- **THEN** KB Scanner SHALL 对同源 finding 做稳定去重
- **AND** 去重后的 finding evidence SHALL 保留可审计的命中次数或命中 entry 摘要
- **AND** scanner MUST NOT 因重复命中导致整次扫描失败

#### Scenario: 源码已命中的构建参数不重复展示
- **WHEN** 默认源码或构建文件扫描已经产出某个构建参数风险 finding
- **AND** compile database 中的真实编译命令也包含同一个风险 token
- **THEN** KB Scanner MUST NOT 再生成另一条用于展示的 compile command finding
- **AND** Scanner SHALL 将 compile command 的命中 token、token 类型、entry index 和脱敏命令摘要合并到已有 finding evidence 或使用稳定 fingerprint 保证导入后只有一条展示记录
- **AND** 该合并 MUST NOT 删除已有源码 finding 的 rule、severity、位置、描述或建议

### Requirement: KB 扫描列表必须默认收敛到当前源码版本
KB 扫描运行列表 API SHALL 默认返回当前 active source revision 下的扫描记录，并 SHALL 支持显式查看历史源码版本记录。

#### Scenario: 默认查询当前 KB 扫描记录
- **WHEN** 用户调用 `GET /api/projects/{projectId}/kb-scans` 且未指定 `sourceRevisionId` 或 `includeStale`
- **THEN** 后端 SHALL 使用项目 active source revision 作为默认源码版本
- **AND** 响应 MUST NOT 混入旧源码版本的 KB 扫描运行

#### Scenario: 显式查看历史 KB 扫描记录
- **WHEN** 用户调用 KB 扫描列表 API 并显式提交历史 `sourceRevisionId` 或 `includeStale=true`
- **THEN** 后端 SHALL 按请求参数返回匹配历史记录
- **AND** 响应 SHALL 标明每条记录是否属于当前源码版本

### Requirement: KB finding 响应必须附带最新 AI 扩展建议
KB finding 列表和详情 SHALL 在原始 finding 字段之外返回同一 KB scan 下最新成功 AI 扩展结果，使前端无需单独查询 AI result 即可展示当条 AI 建议。

#### Scenario: finding 列表返回 AI 建议
- **WHEN** 用户查询 `GET /api/kb-scans/{scanId}/findings`
- **AND** 该 scan 存在最新成功的 AI 扩展结果
- **THEN** 每条有对应结果的 finding SHALL 返回 `aiExtension`
- **AND** `aiExtension` SHALL 包含 AI 扩展运行 ID、状态、summary、suggestion、confidence、action type 和更新时间

#### Scenario: finding 详情返回 AI 建议
- **WHEN** 用户查询 `GET /api/findings/{findingId}`
- **AND** 该 finding 所属 scan 存在最新成功 AI 扩展结果
- **THEN** 响应 SHALL 返回该 finding 对应的 `aiExtension`
- **AND** 后端 MUST NOT 要求前端自行联表推断 AI 建议

#### Scenario: 没有 AI 扩展结果
- **WHEN** 用户查询 finding 列表或详情
- **AND** 当前 finding 没有同一 KB scan 下的成功 AI 扩展结果
- **THEN** 响应 SHALL 返回 `aiExtension=null`
- **AND** 原 finding 字段、报告纳入状态和代码上下文能力 SHALL 保持不变

### Requirement: KB Scanner 主输出不得被 AI 扩展修改
KB AI 扩展 SHALL 作为 KB 扫描后的派生能力运行，不得修改 KB Scanner 的主输出文件和主解析契约。

#### Scenario: AI 扩展不修改 scanner 输出
- **WHEN** AI 扩展扫描运行
- **THEN** 后端 SHALL 读取已入库 findings 或受控 artifact 生成 AI 输入文件
- **AND** 后端 MUST NOT 修改 `scan-result.json`、`scan-report.html`、`scan.log` 或 KB Scanner 主输出结构
- **AND** AI 扩展失败 MUST NOT 改变原 KB scan 的成功状态和原 finding 内容

### Requirement: KB 扫描报告生成可以引用 AI 扩展建议
评估报告生成 SHALL 继续以已确认 migration input reference 为准，并 MAY 在对应 KB finding 存在当前 scan 的 AI 扩展结果时引用 AI 建议。

#### Scenario: 已确认 finding 存在 AI 建议
- **WHEN** 评估报告生成读取已确认 KB finding
- **AND** 该 finding 存在同一 KB scan 下最新成功 AI 扩展结果
- **THEN** 报告输入快照 SHALL 能包含该 AI summary 和 AI suggestion
- **AND** 报告仍 SHALL 保留原始 KB suggestion 作为基础事实

#### Scenario: AI 建议不改变确认状态
- **WHEN** AI 扩展扫描成功写入结果
- **THEN** 后端 MUST NOT 自动改变 finding 对应 migration input reference 的状态
- **AND** 低风险、人工撤回或人工加入的规则 SHALL 继续由 KB 节点确认机制决定

### Requirement: KB finding 必须返回报告纳入状态
KB finding 列表和详情 SHALL 返回该 finding 与当前报告输入池、最新评估报告之间的关系。

#### Scenario: finding 已确认进入下一次报告
- **WHEN** KB finding 存在同一源码版本下的 `sourceType=KB_FINDING` migration input reference
- **AND** reference 状态为 `CONFIRMED`
- **THEN** finding 响应 SHALL 返回 `confirmedForNextReport=true`
- **AND** 响应 SHALL 返回 `migrationInputRefId` 和 `migrationInputStatus`

#### Scenario: finding 已纳入最新报告
- **WHEN** 当前源码版本存在最新成功评估报告
- **AND** 该报告的 `report_inputs` 包含对应 migration input reference
- **THEN** finding 响应 SHALL 返回 `includedInLatestReport=true`
- **AND** 响应 SHALL 返回 `latestReportId`

#### Scenario: finding 未纳入报告
- **WHEN** KB finding 没有对应 migration input reference 或 reference 未进入最新报告快照
- **THEN** finding 响应 SHALL 返回明确的 `confirmedForNextReport=false` 或 `includedInLatestReport=false`
- **AND** 后端 MUST NOT 要求前端自行联表推断该状态

### Requirement: KB Scanner 必须扫描 RPM spec 文件
KB Scanner SHALL 将 RPM spec 文件作为知识库扫描输入，并 SHALL 对 `*.spec` 使用 RPM spec 专属匹配语义。

#### Scenario: 发现 RPM spec 文件
- **WHEN** 项目源码版本中存在 `*.spec` 文件
- **THEN** KB Scanner SHALL 将该文件纳入扫描文件集合
- **AND** scanner SHALL 将该文件标记为 RPM spec 类型或等效 source kind
- **AND** scanner MUST NOT 因默认语言为 `c,cpp` 而跳过该文件

#### Scenario: RPM spec 文件被排除
- **WHEN** 用户提交的扫描排除路径命中某个 `*.spec` 文件
- **THEN** KB Scanner SHALL 跳过该 RPM spec 文件
- **AND** scanner MUST NOT 为该文件生成 finding

### Requirement: RPM spec 扫描必须使用独立 YAML 规则
RPM spec 检测规则 SHALL 使用独立 YAML 文件定义，并 SHALL 只匹配 RPM spec 文件或 RPM spec facts。

#### Scenario: 使用独立 RPM spec 规则文件
- **WHEN** 规则集包含 RPM spec 检测能力
- **THEN** 规则集 SHALL 使用单独 YAML 文件保存 RPM spec 规则
- **AND** 该规则文件 SHALL 具有稳定 rule id、language 或 source kind、severity、confidence、match 和 message 字段
- **AND** RPM spec 规则 MUST NOT 混入通用 build 规则文件

#### Scenario: RPM spec 规则不影响普通构建文件
- **WHEN** 项目中存在 `Makefile`、`CMakeLists.txt`、`meson.build` 或 shell 构建脚本
- **THEN** RPM spec YAML 规则 MUST NOT 匹配这些非 RPM spec 文件
- **AND** scanner MUST NOT 因 RPM spec 规则导致普通构建文件新增误报

### Requirement: RPM spec 扫描必须识别 section 和架构条件
KB Scanner SHALL 识别 RPM spec 中的 section、架构限制和条件块，并 SHALL 将命中位置和条件栈写入 finding evidence。

#### Scenario: 识别 RPM spec section
- **WHEN** RPM spec 中出现 `%prep`、`%build`、`%install`、`%check`、`%files` 或 `%changelog`
- **THEN** scanner SHALL 记录后续命中所在 section
- **AND** finding evidence SHALL 包含 section 名称

#### Scenario: 识别架构限制
- **WHEN** RPM spec 中出现 `ExclusiveArch` 或 `ExcludeArch`
- **THEN** scanner SHALL 解析该行中的架构 token
- **AND** scanner SHALL 能识别 `x86_64`、`amd64`、`i386`、`i686`、`%{ix86}`、`riscv64` 和 `riscv` 等常见 token
- **AND** finding evidence SHALL 保存原始行摘要和解析后的架构 token

#### Scenario: 识别架构条件块
- **WHEN** RPM spec 中出现 `%ifarch`、`%ifnarch`、`%if`、`%else` 或 `%endif`
- **THEN** scanner SHALL 维护当前条件栈
- **AND** 条件块内生成的 finding SHALL 保存命中的条件栈摘要

### Requirement: RPM spec 扫描默认不得依赖完整宏展开
RPM spec 扫描 SHALL 默认基于原始 spec 静态文本和架构相关局部宏识别，不得要求完整 RPM 宏展开才能发现基础迁移风险。

#### Scenario: 不依赖 rpmspec parse
- **WHEN** 运行环境未安装 `rpmspec`
- **THEN** scanner SHALL 继续扫描原始 `*.spec` 文件
- **AND** scanner SHALL 能发现显式 `ExclusiveArch`、`ExcludeArch`、`%ifarch`、`%ifnarch` 和 x86-only 编译或测试参数
- **AND** scanner MUST NOT 因缺少完整宏展开工具导致整次 KB 扫描失败

#### Scenario: 只识别架构相关局部宏
- **WHEN** RPM spec 中存在 `%global`、`%define` 或 `%{...}` 宏引用
- **THEN** scanner SHALL 只将 `_target_cpu`、`_host_cpu`、`_build_cpu`、`optflags`、`build_cflags`、`build_cxxflags`、`build_ldflags`、架构 token 和 x86-only 参数作为默认风险相关宏处理
- **AND** scanner MUST NOT 将 `%{name}`、`%{version}`、`%{release}`、`%{_bindir}`、`%{_libdir}`、`%{buildroot}` 等普通包元信息或安装路径宏作为默认风险来源

#### Scenario: 未解析宏保留为诊断
- **WHEN** scanner 发现无法静态判断的复杂 RPM 宏表达式
- **THEN** scanner MAY 在 diagnostics 或 finding evidence 中记录安全摘要
- **AND** scanner MUST NOT 因无法完整展开该宏而阻断扫描

### Requirement: RPM spec 扫描必须发现架构迁移风险
KB Scanner SHALL 从 RPM spec 中发现会影响 RISC-V 构建、安装或测试的架构迁移风险。

#### Scenario: ExclusiveArch 不包含 RISC-V
- **WHEN** RPM spec 中存在 `ExclusiveArch`
- **AND** 该行允许的架构只包含 x86 或不包含 RISC-V
- **THEN** scanner SHALL 生成 RPM spec finding
- **AND** finding severity SHALL 至少为 `high`
- **AND** finding suggestion SHALL 提示检查是否需要补充 RISC-V 构建支持

#### Scenario: ExcludeArch 排除 RISC-V
- **WHEN** RPM spec 中存在 `ExcludeArch`
- **AND** 该行包含 `riscv64`、`riscv` 或等效 RISC-V token
- **THEN** scanner SHALL 生成 RPM spec finding
- **AND** finding severity SHALL 至少为 `high`
- **AND** finding evidence SHALL 标明 RISC-V 被显式排除

#### Scenario: build 或 install 阶段出现 x86 参数
- **WHEN** RPM spec 的 `%build` 或 `%install` section 中出现 `-mavx`、`-mavx2`、`-mavx512*`、`-msse*`、`-mfma`、`-mxsave`、`-march=x86-64` 或等效 x86-only 参数
- **THEN** scanner SHALL 生成 RPM spec finding
- **AND** finding severity SHALL 至少为 `high`
- **AND** finding evidence SHALL 包含 section、命中 token 和脱敏后的原始行摘要

#### Scenario: check 阶段出现 x86 测试逻辑
- **WHEN** RPM spec 的 `%check` section 中出现 x86-only 测试选择、RISC-V 跳过逻辑或 x86-only 编译/运行参数
- **THEN** scanner SHALL 生成 RPM spec finding
- **AND** finding SHALL 标明该风险来自测试阶段
- **AND** finding suggestion SHALL 提示迁移后需要补充或调整 RISC-V 测试路径

#### Scenario: 架构条件块存在兼容分支
- **WHEN** RPM spec 中 x86 架构条件块命中风险
- **AND** 同一条件结构存在 RISC-V、portable、generic 或 fallback 分支
- **THEN** scanner MAY 降低 finding severity 或将其标记为 hint
- **AND** finding evidence SHALL 标明存在兼容分支

### Requirement: RPM spec 扫描必须控制误报
KB Scanner SHALL 忽略 RPM spec 中默认不代表当前迁移风险的文本，并 SHALL 避免与依赖分析职责重复。

#### Scenario: 忽略注释和 changelog
- **WHEN** x86、RISC-V 或构建参数只出现在注释行或 `%changelog` section 中
- **THEN** scanner MUST NOT 因这些文本生成默认 finding

#### Scenario: 普通依赖行不生成 KB finding
- **WHEN** RPM spec 中存在普通 `BuildRequires`、`Requires` 或 `Requires(post)` 依赖行
- **AND** 该依赖行不在架构条件块中
- **AND** 该依赖名称不表达 x86-only 行为
- **THEN** scanner MUST NOT 将该普通依赖行生成为 KB finding
- **AND** 依赖可用性 SHALL 继续由构建驱动依赖分析节点处理

#### Scenario: 架构相关依赖行生成 finding
- **WHEN** `BuildRequires`、`Requires` 或等效依赖行位于 x86-only 条件块中
- **OR** 依赖行明确表达 x86-only 依赖
- **THEN** scanner SHALL 生成 RPM spec finding 或 hint
- **AND** finding evidence SHALL 标明依赖行、section 和条件栈

### Requirement: RPM spec 扫描不得修改 KB Scanner 输出文件契约
RPM spec 扫描 SHALL 复用现有 KB Scanner 输出文件，不得新增或替换主输出文件格式。

#### Scenario: 复用现有 scan-result.json
- **WHEN** RPM spec 扫描生成 finding
- **THEN** scanner SHALL 将该 finding 写入现有 `scan-result.json` findings 结构
- **AND** scanner MAY 增加 rule id、source kind、evidence 或 trace 字段内容
- **AND** scanner MUST NOT 要求后端读取新的 RPM spec 专属结果文件

#### Scenario: 复用现有报告和日志文件
- **WHEN** RPM spec 扫描完成
- **THEN** scanner SHALL 继续使用现有 `scan-report.html` 和 `scan.log` 表达报告和日志
- **AND** scanner MUST NOT 用新的输出文件替代现有 KB artifact 下载契约

#### Scenario: 后端解析契约保持兼容
- **WHEN** 后端导入 RPM spec findings
- **THEN** 后端 SHALL 使用现有 KB Scanner result parser 读取结果
- **AND** 后端 MUST NOT 因 RPM spec 能力要求修改 KB Scanner 主输出文件名、主 JSON 顶层结构或 artifact 类型集合

### Requirement: RPM spec 扫描必须配套测试覆盖
RPM spec KB 扫描实现 SHALL 覆盖正常流程、异常流程和 edge case。

#### Scenario: 正常流程测试
- **WHEN** fixture 项目包含 RPM spec 文件，并在 `%build`、`%check` 或架构限制中包含 x86-only 逻辑
- **THEN** 测试 SHALL 验证 scanner 生成对应 RPM spec finding
- **AND** 测试 SHALL 验证 finding 通过后端 KB findings API 可查询

#### Scenario: 异常流程测试
- **WHEN** RPM spec 文件语法不完整、条件块未闭合或包含未知宏
- **THEN** scanner SHALL 尽可能继续扫描可解析内容
- **AND** scanner MUST NOT 因单个 spec 文件格式问题导致整次 KB 扫描失败

#### Scenario: edge case 测试
- **WHEN** x86 token 只出现在注释、changelog、普通依赖行或带兼容分支的条件块中
- **THEN** 测试 SHALL 验证 scanner 不误报或按预期降级
- **AND** 测试 SHALL 验证 finding evidence 包含 section、条件栈和命中 token

### Requirement: 知识库扫描必须提供 latest
知识库扫描领域 SHALL 提供当前 Context 下的 latest 接口，用于返回最新知识库扫描执行状态和结果摘要。

#### Scenario: 查询知识库扫描 latest
- **WHEN** 已登录用户调用 `GET /api/projects/{projectId}/kb-scans/latest`
- **THEN** 后端 SHALL 返回统一 latest 外壳
- **AND** `context.sourceRevisionId` SHALL 为项目当前 active source revision
- **AND** `execution` SHALL 指向当前源码版本下最新知识库扫描任务
- **AND** `result` SHALL 包含知识库扫描摘要、finding 数量和 artifact 摘要

#### Scenario: 知识库扫描 latest 识别旧源码
- **WHEN** 只有旧源码版本的知识库扫描记录存在
- **THEN** 后端 MUST NOT 将该记录标记为 `CURRENT`
- **AND** latest SHALL 返回 `freshness=STALE` 或 `freshness=EMPTY`

### Requirement: 知识库扫描 readiness 必须校验 active source 和 x86 构建
项目级 readiness 在 `stageId=kb` 时 SHALL 返回知识库扫描所需的源码与 x86 构建前置条件。

#### Scenario: active source 已存在
- **WHEN** 项目存在 active source revision
- **THEN** `ACTIVE_SOURCE` prerequisite SHALL 返回 `SATISFIED`
- **AND** `referenceId` SHALL 指向 active source revision

#### Scenario: 当前上下文 x86 构建成功
- **WHEN** 当前源码版本和当前运行环境配置版本下的 x86 source-only 构建成功
- **THEN** `X86_BUILD` prerequisite SHALL 返回 `SATISFIED`

#### Scenario: 当前上下文 x86 构建尚未成功
- **WHEN** 当前上下文没有 x86 source-only 构建，或最新构建处于运行中、失败、取消或超时状态
- **THEN** `X86_BUILD` prerequisite SHALL 返回对应的 `MISSING`、`RUNNING` 或 `FAILED`
- **AND** 知识库分析 SHALL NOT 被 readiness 表示为可开始

#### Scenario: active source 缺失
- **WHEN** 项目不存在 active source revision
- **THEN** `ACTIVE_SOURCE` prerequisite SHALL 返回 `MISSING`
- **AND** `reasonCode` SHALL 为 `ACTIVE_SOURCE_MISSING`
### Requirement: KB 扫描运行时必须使用 schema v2
KB 扫描任务 SHALL 显式调用新版 KB Scanner 并请求 `schemaVersion: "2.0"` 的结果。

#### Scenario: 成功运行 schema v2 扫描
- **WHEN** 后端执行知识库扫描任务
- **THEN** 扫描命令 SHALL 包含 `--schema-version 2.0`
- **AND** 后端 SHALL 读取 `scan-result.json` 中的 `schemaVersion`
- **AND** 当版本为 `2.0` 时 SHALL 继续导入 finding、保存 artifact 并完成任务
- **AND** 保存的扫描结果 artifact SHALL 标记为 schema v2

#### Scenario: 拒绝非 schema v2 结果
- **WHEN** `scan-result.json` 缺失 `schemaVersion` 或版本不是 `2.0`
- **THEN** 后端 SHALL 将任务标记为失败
- **AND** 错误信息 SHALL 明确说明 KB Scanner 结果版本不兼容
- **AND** 后端 SHALL NOT 按旧 v1 DTO 继续导入 finding

### Requirement: KB 扫描运行时必须逐条导入 schema v2 finding
KB 扫描结果导入 SHALL 基于 v2 finding 的 `fact`、`conclusion`、`occurrences` 和 `evidenceChain` 建立查询投影。

#### Scenario: 导入带主位置的 finding
- **GIVEN** v2 finding 包含 `fact.primaryLocation`
- **WHEN** 后端导入扫描结果
- **THEN** 后端 SHALL 将 `conclusion.severity` 投影为风险等级
- **AND** 后端 SHALL 将 `conclusion.title` 投影为标题
- **AND** 后端 SHALL 将 `fact.kind` 和 `conclusion.findingType` 投影为来源与类型
- **AND** 后端 SHALL 将 `fact.primaryLocation.file`、起始行和结束行投影到可查询字段
- **AND** 后端 SHALL 在 evidence 中保存完整 v2 finding payload

#### Scenario: 导入缺少主位置的 finding
- **GIVEN** v2 finding 没有 `fact.primaryLocation`
- **WHEN** 后端导入扫描结果
- **THEN** 后端 SHALL 保留该 finding
- **AND** 位置投影字段 MAY 为空
- **AND** 完整 v2 finding payload SHALL 仍保存在 evidence 中

#### Scenario: 导入结构化 diagnostics
- **GIVEN** v2 扫描结果包含结构化 diagnostics
- **WHEN** 后端保存扫描摘要和 artifact metadata
- **THEN** 后端 SHALL 保留 diagnostics 的结构化内容或可审计摘要
- **AND** 后端 SHALL NOT 假设 diagnostics 是字符串数组

### Requirement: KB 扫描结果必须继续支持报告纳入状态
schema v2 finding 导入后 SHALL 继续支持用户确认、排除、报告纳入状态以及后续报告输入预览。

#### Scenario: 新 finding 进入报告候选
- **WHEN** v2 finding 被导入
- **THEN** 后端 SHALL 按现有风险策略生成或刷新报告候选状态
- **AND** 列表接口 SHALL 能返回该 finding 是否已纳入报告
- **AND** 用户后续手动排除或加入 SHALL 作用于当前 finding 记录
