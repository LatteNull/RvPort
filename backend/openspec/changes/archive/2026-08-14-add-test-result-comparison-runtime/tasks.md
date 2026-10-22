## 1. 数据库和代码生成

- [x] 1.1 新增 Liquibase changelog 为自动化测试节点增加批次关联字段，并创建 `test_comparison_runs`，包含项目、任务、批次标识、两侧测试运行、状态、总体结论、风险等级、置信度、摘要、建议、错误摘要、输入裁剪标记和关键时间字段。
- [x] 1.2 新增 Liquibase changelog 创建 `test_comparison_findings`，包含比较运行、序号、差异类型、严重程度、置信度、标题、说明、source 摘要、target 摘要、建议和创建时间字段。
- [x] 1.3 扩展 `stored_artifacts.owner_type` 约束，支持 `TEST_COMPARISON`。
- [x] 1.4 为比较运行和差异项增加项目、状态、测试运行、风险等级、时间和排序相关索引。
- [x] 1.5 运行 Liquibase 迁移并使用 jOOQ 脚本刷新生成源码。

## 2. 比较领域模型和 Repository

- [x] 2.1 新增测试比较 DTO、自动比较批次模型、响应对象、列表查询对象、差异项查询对象和状态/枚举定义。
- [x] 2.2 新增 `TestComparisonRepository`，支持创建自动比较运行、记录不可用摘要、状态流转、保存摘要、保存差异项、分页列表、详情查询、按任务查询和 artifact 引用更新。
- [x] 2.3 新增比较输入校验逻辑，校验两条 `test_runs` 存在、属于同一项目、已进入可比较终态且不泄漏其他项目资源存在性。
- [x] 2.4 新增比较可用性检查，自动化测试完成后解析 `TEST_LOG_COMPARE` 阶段模型并校验必要配置完整；不可用时写入比较不可用摘要而不影响测试状态。

## 3. Agent 输入聚合和 Codex 调用

- [x] 3.1 新增测试比较输入聚合器，读取两侧 `test_runs` 摘要、环境摘要、stdout/stderr 完整日志和报告 artifact 内容。
- [x] 3.2 实现确定性输入裁剪策略，覆盖单日志、单报告和总输入上限，并记录 `inputTruncated` 与裁剪摘要。
- [x] 3.3 新增测试比较 agent prompt 和 JSON 输出契约，要求输出总体结论、风险等级、置信度、摘要、建议和差异项列表。
- [x] 3.4 新增 Codex agent runtime 服务，使用 `ModelProfileService.resolveForStage(TEST_LOG_COMPARE)` 解析配置并运行 Codex CLI。
- [x] 3.5 实现 agent 输出解析、脱敏、原始输出 artifact 保存和不可解析输出的受控失败处理。

## 4. 任务 Handler 和 API

- [x] 4.1 新增 `TEST_LOG_COMPARE` 任务类型并注册 worker handler。
- [x] 4.2 新增自动比较触发器，在同一自动化测试批次两侧测试记录完成后自动创建比较运行，并在模型可用时投递 `TEST_LOG_COMPARE` 任务。
- [x] 4.3 新增 `TestComparisonService`，支持自动创建比较运行、记录不可用摘要、列表、详情、差异项查询、取消和 agent 输出下载。
- [x] 4.4 新增 `TestComparisonController`，实现 `GET /api/projects/{projectId}/test-comparisons`、`GET /api/test-comparisons/{comparisonId}`、`GET /api/test-comparisons/{comparisonId}/findings`、`POST /api/test-comparisons/{comparisonId}/cancel` 和 agent 输出下载接口；不提供用户手动创建比较接口。
- [x] 4.5 保证所有比较 API 执行项目访问权限校验，普通用户不能访问其他项目的测试运行、比较记录、差异项或 agent 输出。
- [x] 4.6 通过项目级 SSE 推送比较任务状态、进度和比较不可用摘要，详情接口可补偿查询历史结果。
- [x] 4.7 在自动化测试详情或项目测试摘要中补充自动比较状态字段，未配置模型时提示比较不可用，不影响自动化测试。
- [x] 4.8 在 test-support 源码中新增 `POST /api/test-support/projects/{projectId}/test-comparisons`，仅用于 E2E/开发测试手动触发比较，并确认默认生产构建不包含该接口。

## 5. 测试和验证

- [x] 5.1 补充 Liquibase migration 测试，验证新表、约束、索引和 `TEST_COMPARISON` artifact owner type。
- [x] 5.2 补充 repository/service 单元测试，覆盖自动创建比较、模型不可用摘要、非法测试记录、非同项目、未完成测试、权限、分页过滤排序和状态流转。
- [x] 5.3 补充输入聚合器测试，覆盖空日志、stdout/stderr、报告 artifact、缺失 artifact、大日志裁剪、大报告裁剪和脱敏。
- [x] 5.4 补充 agent runtime 测试，覆盖成功 JSON、非 JSON、字段缺失、进程失败、超时和 secret 脱敏。
- [x] 5.5 补充任务 handler 测试，覆盖成功比较、agent 失败、取消、TIMEOUT、结果入库和 SSE/task event。
- [x] 5.6 补充独立 API E2E 模块，覆盖自动化测试两侧完成后自动生成比较、test-support 手动触发比较、未配置模型时比较不可用、自动化测试不受 AI 配置影响、权限隔离和结果查询。
- [x] 5.7 运行 `mvn test`。
- [x] 5.8 在基础设施和后端可用时运行相关 E2E 模块并清理测试数据。
- [x] 5.9 运行 `openspec validate add-test-result-comparison-runtime --strict`。
