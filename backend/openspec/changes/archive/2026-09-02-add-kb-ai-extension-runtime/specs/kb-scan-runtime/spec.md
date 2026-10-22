## ADDED Requirements

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
