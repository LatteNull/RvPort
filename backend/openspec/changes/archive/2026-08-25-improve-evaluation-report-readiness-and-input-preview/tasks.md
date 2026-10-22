## 1. API 与 DTO

- [x] 1.1 新增评估报告 readiness 响应 DTO，包含 canGenerate、blockers、warnings、sourceRevision、inputSummary、latestReport、latestComparableReport 和 latestComparison。
- [x] 1.2 新增评估报告输入预览分页响应 DTO，返回 reference 展示字段、状态、来源定位摘要和更新时间。
- [x] 1.3 在报告详情响应中增加 currentInputSummary，并明确与历史报告 summary 区分。
- [x] 1.4 在 `ReportController` 增加 readiness 和 input-preview 接口，保留现有报告生成、列表、详情、下载和比较接口。

## 2. Service 与 Repository

- [x] 2.1 在报告服务中解析请求源码版本：未传入时使用 active source revision，传入时校验属于项目。
- [x] 2.2 实现当前源码版本 migration input 聚合查询，按 status、sourceType、风险等级和 LOW candidate 统计。
- [x] 2.3 实现 readiness 逻辑：没有源码版本、没有 confirmed 输入返回 blocker；LOW candidate 和 excluded 输入返回 warning。
- [x] 2.4 实现输入预览查询，支持分页、sourceType/status/riskLevel/keyword 过滤和排序白名单。
- [x] 2.5 查询 latestReport、latestComparableReport 和 latestComparison，并在 readiness 与报告详情中返回安全摘要。
- [x] 2.6 确保 readiness 和 input-preview 不创建任务、不修改 migration input 状态、不返回服务器路径或存储内部字段。

## 3. 报告生成一致性

- [x] 3.1 确认报告生成仍只读取当前源码版本下 `CONFIRMED` reference。
- [x] 3.2 确认 `CANDIDATE` 和 `EXCLUDED` 不进入报告输入快照。
- [x] 3.3 确认报告生成成功后继续登记归档候选，重新生成同源码版本报告时 latest report 口径稳定。
- [x] 3.4 确认历史报告下载和 `report_inputs` 快照不随当前 input 状态变化。

## 4. 测试

- [x] 4.1 增加单元测试覆盖 readiness 可生成、无 confirmed blocker、无 active source blocker、LOW candidate warning。
- [x] 4.2 增加单元测试覆盖输入预览分页、过滤、排序白名单和非法参数。
- [x] 4.3 增加单元测试覆盖报告详情 currentInputSummary 与历史 summary 的区分。
- [x] 4.4 更新 `008-migration-reports` E2E：验证 readiness、输入预览、LOW candidate、人工加入、人工撤回、历史快照不可变。
- [x] 4.5 增加越权 E2E：普通用户不能访问其他项目 readiness 和 input-preview。

## 5. 文档与验证

- [x] 5.1 更新 `docs/API_DESIGN.md` 中评估报告 readiness、input-preview 和详情响应字段说明。
- [x] 5.2 更新 `docs/api-e2e-coverage.md` 中评估报告模块覆盖矩阵。
- [x] 5.3 运行相关单元测试和报告 E2E。
- [x] 5.4 运行 `openspec validate improve-evaluation-report-readiness-and-input-preview --strict`。
