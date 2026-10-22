## ADDED Requirements

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
- **THEN** 后端 SHALL 对路径执行 normalize 和工作副本根目录边界校验
- **AND** 后端 MUST NOT 允许绝对路径、`..` 路径段或符号链接逃逸读取工作副本之外的文件
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
