## 1. 数据模型和生成代码

- [x] 1.1 盘点现有 `reports`、`report_inputs`、`recheck_runs`、`diff_items` 是否能表达 base/target report 关系
- [x] 1.2 若现有表不足，新增 Liquibase migration 保存 report comparison run 与 report 引用
- [x] 1.3 若新增或调整 schema，运行 Liquibase 并重新生成 jOOQ 代码
- [x] 1.4 确认新增表和字段具备项目、报告、状态、创建时间等必要索引

## 2. 报告比较核心服务

- [x] 2.1 实现报告比较创建服务，支持指定 `baseReportId`
- [x] 2.2 实现未指定 `baseReportId` 时自动选择上一份可比较成功报告
- [x] 2.3 实现报告输入快照读取和 comparable input adapter
- [x] 2.4 复用或抽取现有 recheck diff 匹配算法，基于两份报告快照生成差异项
- [x] 2.5 实现重复创建复用逻辑，避免同一 base/target report 重复并发比较
- [x] 2.6 实现不支持历史报告、缺少输入快照、跨项目报告等错误处理

## 3. API 实现

- [x] 3.1 新增 `POST /api/reports/{reportId}/comparisons`
- [x] 3.2 新增 `GET /api/report-comparisons/{comparisonId}`
- [x] 3.3 新增 `GET /api/report-comparisons/{comparisonId}/diff-items`
- [x] 3.4 新增 `GET /api/report-comparisons/{comparisonId}/diff-items/{diffItemId}`
- [x] 3.5 调整报告详情响应，返回可比较历史报告提示或 latest comparison 摘要
- [x] 3.6 确认报告历史列表支持分页、过滤和排序白名单
- [x] 3.7 将 source compare/recheck API 在文档或响应摘要中标记为兼容入口，不作为主流程推荐入口

## 4. 任务运行和事件

- [x] 4.1 增加 `REPORT_COMPARE` 或等效任务类型
- [x] 4.2 实现报告比较 task handler，写入 RUNNING、SUCCEEDED、FAILED 等状态
- [x] 4.3 报告比较任务通过项目级 SSE 推送状态变化
- [x] 4.4 失败时写入安全错误摘要，避免暴露服务器路径、对象存储 key 或完整输入快照

## 5. 归档和历史兼容

- [x] 5.1 确认报告比较结果是否登记为归档候选
- [x] 5.2 若登记归档候选，补充 candidate type、node type、summary 和 artifact refs
- [x] 5.3 确认历史 source recheck 记录仍可查询，不破坏旧 E2E 和调试脚本

## 6. 测试覆盖

- [x] 6.1 补充单元测试正常流程：当前报告自动选择上一份报告并生成 RESOLVED/UNCHANGED/NEW/CHANGED
- [x] 6.2 补充单元测试正常流程：指定 base report 创建比较
- [x] 6.3 补充异常流程测试：跨项目报告、无可比较报告、报告未成功、缺少输入快照
- [x] 6.4 补充 edge case 测试：同一源码版本多份报告、同一问题行号变化、低置信度模糊匹配、重复创建比较
- [x] 6.5 补充 API E2E 模块，覆盖报告列表、报告详情比较入口、创建比较、查询差异列表和详情
- [x] 6.6 补充越权 E2E，确认无项目权限用户无法访问报告比较

## 7. 验证

- [x] 7.1 运行相关单元测试
- [x] 7.2 运行 `mvn test`
- [x] 7.3 运行 API E2E 报告/比较相关模块
- [x] 7.4 运行 `openspec validate merge-source-compare-into-report-comparison --strict`
- [x] 7.5 运行 `openspec validate --specs --strict`
