## Why

迁移输入合并节点移除后，评估报告节点需要承担生成前可见性：用户必须在报告页清楚看到当前源码版本下哪些输入会进入报告、哪些低风险候选未进入，以及当前是否满足生成条件。否则真实流程中用户点击生成报告时无法判断报告内容是否完整，失败也只能等异步任务结束后才知道原因。

## What Changes

- 新增评估报告 readiness/overview 能力，返回当前源码版本、最新报告、历史报告摘要、confirmed/candidate/excluded 输入统计、生成阻塞原因和警告。
- 新增报告输入预览能力，支持在报告生成前分页查看当前源码版本下的迁移输入 reference，并按来源、状态、风险等级和关键字过滤排序。
- 报告详情补充当前源码版本下的输入状态摘要和来源分布，帮助前端在评估报告页展示“报告基于哪些输入生成”。
- 报告生成前仍只消费 `CONFIRMED` 输入；`LOW` 默认 `CANDIDATE` 不进入报告，但 readiness 必须提示其存在。
- 继续保留历史报告不可变快照、历史报告比较和对象存储下载能力。
- 补充 E2E 覆盖：节点内确认后生成报告、LOW 候选提示、人工加入/撤回影响 readiness、无 confirmed 输入时生成前阻塞、历史报告不可变。

## Capabilities

### New Capabilities

- 无。

### Modified Capabilities

- `migration-report-runtime`: 增加评估报告生成前 readiness、输入预览、报告页输入摘要和低风险候选提示要求。
- `backend-api-design`: 增加评估报告 overview/readiness 和输入预览 API 的请求、响应、过滤排序和权限约束。
- `api-e2e-test-suite`: 增加评估报告节点在移除迁移输入合并节点后的真实场景 E2E 覆盖。

## Impact

- 后端 API：新增或扩展评估报告页聚合接口、输入预览接口和报告详情响应字段。
- 后端服务：复用 `migration_input_refs`、`reports`、`report_inputs`、`source_revisions` 和 report comparison 数据，不新增独立合并节点。
- 前端联调：前端可用 readiness 决定按钮状态、用输入预览展示当前会进入报告的内容、用警告提示低风险候选。
- 测试：补充单元测试和 E2E，覆盖正常流程、异常流程和 edge case。
