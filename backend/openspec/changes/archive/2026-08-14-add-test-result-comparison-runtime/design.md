## Context

当前后端已经实现自动化测试运行时：测试任务在远程环境执行，`test_runs` 保存状态、退出码、stdout/stderr 日志引用、输出摘要和报告 artifact 摘要；完整日志保存在本地 `rvport.runtime.log-dir`，测试报告保存在对象存储。后端也已经实现模型 profile 和 `TEST_LOG_COMPARE` 阶段绑定，Codex CLI 可作为 agent runtime 调用 OpenAI-compatible 模型。

测试结果比较是自动化测试节点内部的后续步骤。用户只在节点上点击开始自动化测试；两侧测试完成后，后端自动读取原始环境和目标环境已有的测试运行结果，让 agent 比较两侧输出差异，形成可查询、可审计的比较结论。前端最终展示测试结果和比较报告，或者展示“比较功能不可用”的明确提示。

## Goals / Non-Goals

**Goals:**
- 支持自动化测试完成后自动创建测试结果比较任务。
- 比较任务只能消费同一项目内已有测试结果、日志和报告 artifact。
- 比较任务必须通过 `TEST_LOG_COMPARE` 阶段绑定解析模型配置。
- 未配置 AI 或模型不可用时，自动化测试结果正常保存，比较记录标记为不可用并给前端明确提示。
- 自动化测试创建、执行和查询不依赖 AI 配置。
- 保存结构化比较摘要、差异项和原始 agent 输出 artifact，支持分页、过滤和排序。
- 通过项目级 SSE 推送比较任务状态，前端通过查询接口获取历史结果。

**Non-Goals:**
- 不在本 change 重新设计自动化测试执行流程。
- 不解析 JUnit、CTest、pytest 等用例级结构化报告。
- 不实现失败用例重跑。
- 不让前端提交任意模型参数、prompt 或 provider 配置。
- 不承诺 agent 比较结果为确定性事实；它是辅助分析结果，需要保留原始测试日志和报告供复核。

## Decisions

### 测试结果比较作为自动化测试节点的自动后续任务

新增 `TEST_LOG_COMPARE` 任务类型，但不提供用户手动创建入口。自动化测试节点完成两侧测试运行后，由后端根据同一节点内的 source/target 测试运行自动创建比较运行和比较任务。任务输入只保存比较运行 ID、项目 ID 和两条测试运行 ID，不保存日志内容或模型参数。

原因：
- 比较可能耗时较长，适合沿用 RabbitMQ worker、任务状态、取消和 SSE 机制。
- 用户视角只需要一次点击开始自动化测试，避免完成测试后再手动点击比较。
- 比较失败不应影响已有自动化测试结果。
- 后续可以复用任务日志记录 agent 执行摘要和错误。

### 自动化测试节点需要批次关联

当前自动化测试记录主要围绕单条构建运行创建。为了支持“用户点击一次自动化测试，完成后自动比较”，后端需要在同一次自动化测试节点请求中建立 source/target 两侧测试记录的关联。实现上可以新增 `test_group_id`、`comparison_group_id` 或等效字段，写入同一节点产生的两条 `test_runs`。

原因：
- 自动比较必须知道哪两条测试记录属于同一次节点运行。
- 不能靠“最近两条测试记录”推断，否则多用户、多次重跑或并发运行会错配。
- 后续查询节点详情时也需要返回该批次下的两侧测试状态和比较状态。

### 比较输入从已持久化测试结果聚合

比较输入包含：
- 两侧 `test_runs` 的状态、退出码、输出摘要、源码版本、环境摘要和任务 ID。
- 两侧 stdout/stderr 完整日志文件或受控摘要。
- 两侧 `report_artifacts` 指向的对象存储内容或受控摘要。

输入聚合器需要按固定顺序组织内容，并设置大小上限。建议初始策略：
- 小日志和小报告直接纳入 agent 输入。
- 超过单项大小上限时截取头部、尾部和关键错误片段。
- 总输入超过上限时优先保留退出码、摘要、stderr、失败关键字和报告摘要。

原因：
- 日志可能很大，不能直接全部塞进 prompt。
- 需要保持可复现，聚合策略必须确定。
- 比较结论需要能回指原始日志和 artifact。

### 未配置模型时记录比较不可用

自动化测试准备自动创建比较任务时检查：
- `TEST_LOG_COMPARE` 阶段是否绑定模型 profile。
- profile 是否启用。
- executable path、base URL、model、wire API、API key、超时配置是否完整。

任一条件不满足时，后端不创建 agent 执行任务，但 SHALL 创建或更新比较运行摘要为 `UNAVAILABLE`，记录 `TEST_COMPARE_MODEL_NOT_CONFIGURED` 或等效原因，供前端在自动化测试节点中展示“比较功能不可用，请配置模型”。

原因：
- 用户已经完成自动化测试动作，不能因为 AI 未配置让测试节点整体失败。
- 前端需要在同一节点中看到明确缺失原因，而不是再点击一次后才知道不可用。

### 结果表按运行和差异项拆分

新增 `test_comparison_runs` 保存一次比较运行摘要，新增 `test_comparison_findings` 保存结构化差异项。原始 agent 输出保存为 `stored_artifacts`，owner type 增加 `TEST_COMPARISON`。

原因：
- 列表页、详情页、排序和过滤需要结构化字段。
- 原始 agent 输出可能很大，不适合放在普通详情响应里。
- 差异项单独入库便于后续报告、确认和复核。

### Codex agent 输出使用严格 JSON 契约

后端向 agent 提供固定 prompt 和输入文件，要求输出 JSON。JSON 至少包含：
- `summary`
- `overallStatus`
- `riskLevel`
- `confidence`
- `findings[]`
- `recommendation`

后端解析失败时仍保存原始输出 artifact，并将比较运行标记为失败或部分失败。

原因：
- 前端展示需要稳定结构。
- agent 输出不可完全信任，必须保留原始输出便于审计。

## Risks / Trade-offs

- 大日志导致 agent 输入过大 → 使用确定性裁剪、摘要和大小上限，保留原始日志下载入口。
- agent 输出 JSON 不合法 → 保存原始输出 artifact，返回受控失败，不丢失审计材料。
- 未配置模型导致用户误以为测试失败 → 比较运行标记为 `UNAVAILABLE`，自动化测试状态保持真实结果并给出独立提示。
- 两条测试运行不具备可比性 → 后端校验同项目，并优先要求一个 source 环境、一个 target 环境；无法识别角色时返回明确校验错误或在结果中标注低置信度。
- API 泄漏日志或敏感环境变量 → 输入聚合和 agent 输出保存前复用日志脱敏规则，并且 API 响应不返回服务器真实路径。

## Migration Plan

1. 新增 Liquibase changelog 创建 `test_comparison_runs`、`test_comparison_findings`，并扩展 `stored_artifacts.owner_type`。
2. 运行 Liquibase 和 jOOQ codegen。
3. 实现比较 repository、service、查询 controller 和 worker handler。
4. 实现日志/report artifact 聚合器和 Codex agent runner。
5. 补充单元测试、轻量集成测试和 E2E。
6. 验证未配置 `TEST_LOG_COMPARE` 模型时自动化测试正常完成，比较摘要返回不可用提示。

## Open Questions

- 初始 agent 输入大小上限使用多少更合适，需要结合真实测试日志规模校准。
- 比较结果 `overallStatus` 枚举是否需要区分 `EQUIVALENT`、`DIFFERENT_ACCEPTABLE`、`DIFFERENT_BLOCKING` 和 `INCONCLUSIVE`，还是先使用更简单枚举。
- 差异项是否需要人工确认状态，本 change 暂不纳入，后续可与报告或人工处理节点整合。
