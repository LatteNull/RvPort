## ADDED Requirements

### Requirement: KB 扫描 API 必须创建和查询扫描运行
后端 API SHALL 提供项目级 KB 扫描创建、扫描运行列表、扫描详情、finding 列表和 finding 详情接口。

#### Scenario: 创建 KB 扫描任务
- **WHEN** 已登录用户调用 `POST /api/projects/{projectId}/kb-scans`
- **THEN** 后端 SHALL 校验当前用户有权访问该项目
- **AND** 后端 SHALL 校验请求中的 `sourceRevisionId` 属于该项目，或在未提交时选择当前启用源码版本
- **AND** 后端 SHALL 校验源码版本存在可用工作副本
- **AND** 后端 SHALL 创建 `KB_SCAN` 任务并返回 `taskId`、任务类型和初始状态
- **AND** 后端 SHALL 创建关联该任务的 `kb_scan_runs` 记录
- **AND** API 响应 MUST NOT 返回源码工作副本路径、scanner 输出目录、完整任务输入快照或服务器真实路径

#### Scenario: 查询项目 KB 扫描列表
- **WHEN** 已登录用户调用 `GET /api/projects/{projectId}/kb-scans`
- **THEN** 后端 SHALL 校验当前用户有权访问该项目
- **AND** 后端 SHALL 返回该项目下 KB 扫描运行分页列表
- **AND** 列表项 SHALL 包含 scan id、task id、source revision 摘要、规则版本、状态、summary、开始时间和结束时间
- **AND** 列表接口 SHALL 支持按状态、sourceRevisionId、ruleVersion 和时间范围过滤
- **AND** 列表接口 SHALL 支持按 startedAt、finishedAt、status 和 findings count 排序

#### Scenario: 查询 KB 扫描详情
- **WHEN** 已登录用户调用 `GET /api/kb-scans/{scanId}`
- **THEN** 后端 SHALL 根据扫描运行所属项目校验访问权限
- **AND** 响应 SHALL 返回运行摘要、任务摘要、源码版本摘要、规则包摘要、summary、artifact 摘要和错误摘要
- **AND** 响应 MUST NOT 暴露服务器真实路径、完整 scanner 输入、完整 stdout 或完整 stderr

#### Scenario: 下载 KB 扫描 artifact
- **WHEN** 已登录用户调用 `GET /api/kb-scans/{scanId}/artifacts/{artifactId}/download`
- **THEN** 后端 SHALL 校验 artifact 属于该扫描运行
- **AND** 后端 SHALL 根据扫描运行所属项目校验访问权限
- **AND** 响应 SHALL 使用安全文件名下载 `scan-result.json`、`scan-report.html` 或 `scan.log`
- **AND** 响应 MUST NOT 暴露服务器真实路径、源码工作副本路径或 scanner 输出目录

### Requirement: KB finding API 必须支持分页过滤排序
后端 API SHALL 提供 KB finding 分页查询和详情查询能力，用于前端审计扫描结果。

#### Scenario: 查询扫描 finding 列表
- **WHEN** 已登录用户调用 `GET /api/kb-scans/{scanId}/findings`
- **THEN** 后端 SHALL 根据扫描运行所属项目校验访问权限
- **AND** 响应 SHALL 返回该扫描运行下的 finding 分页列表
- **AND** 列表项 SHALL 包含 finding id、rule id、category、severity、title、file path、line range、symbol、status、created at 和 evidence 摘要
- **AND** 响应 MUST NOT 返回服务器真实路径或完整 scanner output 原文

#### Scenario: 过滤 finding 列表
- **WHEN** 前端查询 finding 列表
- **THEN** API SHALL 支持按 severity、category、ruleId、status、filePath、symbol 和 keyword 过滤
- **AND** 多个过滤条件 SHALL 使用 AND 语义
- **AND** 后端 SHALL 只返回当前扫描运行内的 findings
- **AND** 后端 MUST 拒绝不在白名单内的过滤字段

#### Scenario: 排序 finding 列表
- **WHEN** 前端查询 finding 列表
- **THEN** API SHALL 支持按 severity、category、ruleId、filePath、lineStart 和 createdAt 排序
- **AND** 默认排序 SHALL 为 `severity DESC, filePath ASC, lineStart ASC`
- **AND** 后端 MUST 拒绝不在白名单内的排序字段

#### Scenario: 查询 finding 详情
- **WHEN** 已登录用户调用 `GET /api/findings/{findingId}`
- **THEN** 后端 SHALL 根据 finding 所属项目校验访问权限
- **AND** 响应 SHALL 返回 finding 事实详情、扫描运行摘要、源码版本摘要、位置、证据、建议、状态和代码上下文摘要
- **AND** 响应 MUST NOT 暴露服务器真实路径、完整任务输入快照或敏感日志

#### Scenario: 查询 finding 代码上下文
- **WHEN** 已登录用户调用 `GET /api/findings/{findingId}/code-context`
- **THEN** 后端 SHALL 根据 finding 所属项目校验访问权限
- **AND** 后端 SHALL 根据 finding 关联的 `source_revision_id` 和 `file_path` 读取对应源码文件
- **AND** 响应 SHALL 返回 finding id、scan id、source revision id、相对文件路径、文件编码摘要、固定上下文行数、实际上下文起始行、实际上下文结束行、finding 起始行、finding 结束行和代码行数组
- **AND** 代码行数组中每项 SHALL 包含行号、代码文本、是否位于 finding 命中范围、是否为上下文边界外截断提示
- **AND** 响应 MUST NOT 返回服务器真实路径、源码工作副本路径或允许客户端读取任意文件

#### Scenario: 控制 finding 代码上下文范围
- **WHEN** 客户端查询 finding 代码上下文
- **THEN** 后端 SHALL 使用固定上下文边界：命中代码起始行之前最多 20 行，命中代码结束行之后最多 20 行
- **AND** 后端 SHALL 只返回 `finding.line_start - 20` 到 `finding.line_end + 20` 范围内的源码行
- **AND** 当请求范围超出文件边界时，响应 SHALL 返回实际可用的起始行和结束行
- **AND** 响应 SHALL 明确返回 `contextBefore=20` 和 `contextAfter=20`
- **AND** 后端 MUST NOT 因文件上下不足 20 行而返回错误

#### Scenario: Finding 源码文件不可用
- **WHEN** finding 关联的源码工作副本、源码文件或行号不可用
- **THEN** 后端 SHALL 返回安全错误或明确的代码上下文不可用状态
- **AND** 响应 MUST NOT 暴露服务器真实路径、文件系统异常细节或源码工作副本路径

#### Scenario: 无权限查询 finding
- **WHEN** 用户查询无权访问项目下的 finding
- **THEN** 后端 SHALL 返回与资源不存在一致的安全错误
- **AND** 后端 MUST NOT 暴露扫描运行、源码版本或 finding 是否存在

### Requirement: KB 扫描 API MVP 不实现加入问题清单
本 change 的 KB 扫描 API SHALL 不实现 finding 加入问题清单的业务联动。

#### Scenario: 用户尝试加入问题清单
- **WHEN** 客户端调用 `POST /api/kb-scans/{scanId}/findings:add-to-issues`
- **THEN** 后端 MAY 返回未实现或接口不存在
- **AND** 后端 MUST NOT 在本 change 中创建或修改 `issues`、`issue_sources` 或 `issue_events`
