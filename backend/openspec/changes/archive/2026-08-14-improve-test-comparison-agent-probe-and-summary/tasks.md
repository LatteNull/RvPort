## 1. 模型 agent 兼容性测试

- [x] 1.1 盘点现有 `CodexProviderProbeService`、模型 profile 表结构和 API 响应，明确现有 last test 字段是否需要新增带 `agentType` 的 JSON 分项字段或扩展摘要字段。
- [x] 1.2 新增模型测试分项枚举和 DTO，覆盖 `BASIC_TEXT`、`AGENT_TEXT`、`AGENT_WORKSPACE_TOOL`、`TEST_COMPARE_SCHEMA`，并在结果中携带 `agentType`。
- [x] 1.3 扩展模型 profile 测试运行逻辑，当前使用 `CODEX` agent 在临时 workspace 文件中验证 workspace/tool 闭环，但结构上允许后续接入其他 agent runner。
- [x] 1.4 扩展测试比较 schema probe，使用最小 source/target merged log 输入验证指定 agent 能输出可解析比较 JSON。
- [x] 1.5 保存并返回基础可用、agent 兼容和测试比较兼容的聚合状态，确保错误信息脱敏且不暴露 API key、授权头、完整命令或服务器路径。

## 2. 自动化测试 merged log

- [x] 2.1 盘点自动化测试 worker 当前 stdout/stderr 采集与 `TaskLogService` 写入路径，确定 merged log 的存储位置和引用字段。
- [x] 2.2 实现执行阶段 stdout/stderr 有序合并写入，日志片段保留 stream 来源和顺序信息。
- [x] 2.3 保留 stdout.log 和 stderr.log 作为调试材料，并在测试详情或日志摘要中区分 merged/stdout/stderr。
- [x] 2.4 更新测试结果比较输入聚合器，使新记录优先读取 merged log，旧记录缺少 merged log 时降级并记录摘要。

## 3. 测试比较结构化统计

- [x] 3.1 扩展测试比较 agent prompt，要求输出 source/target 测试总数、执行数、通过数、失败数、跳过数、失败项、失败原因、统计依据和置信度。
- [x] 3.2 扩展 agent 输出解析模型，校验结构化统计字段并允许不确定数量使用空值或低置信度。
- [x] 3.3 扩展测试比较运行持久化结构，保存 source/target 结构化统计摘要，避免在普通字段保存完整日志或完整 agent 输入。
- [x] 3.4 更新测试比较详情 API 响应，返回结构化环境统计和已有差异项摘要。

## 4. API 与兼容性边界

- [x] 4.1 更新模型 profile 测试 API 响应，返回 agent 类型、分项 probe 结果、聚合兼容性状态和最近测试时间。
- [x] 4.2 更新模型 profile 列表 API，暴露最近一次 agent 类型、基础可用、agent 兼容和测试比较兼容状态。
- [x] 4.3 确认阶段绑定保存时不强制阻止不兼容模型，但运行时或测试结果中必须能明确提示不兼容。
- [x] 4.4 更新 OpenAPI/E2E 文档或后端 API 文档中相关字段说明。

## 5. 测试与验证

- [x] 5.1 补充模型 probe 单元测试，覆盖基础成功、指定 agent workspace/tool 闭环成功、工具结果回传失败、schema 输出不可解析、agent 类型保存和 secret 脱敏。
- [x] 5.2 补充自动化测试 merged log 单元测试，覆盖 stdout/stderr 交错、只有 stdout、只有 stderr、大日志和旧记录降级。
- [x] 5.3 补充测试比较 agent runtime 测试，覆盖结构化统计成功、数量不确定、失败项解析、低置信度和非法 JSON。
- [x] 5.4 补充 API E2E 模块，验证模型测试分项结果、测试详情 merged log 引用和比较详情结构化统计。
- [x] 5.5 使用真实模型至少验证一个兼容模型和一个不兼容模型，记录实际分项结果。
- [x] 5.6 运行 `mvn test`。
- [x] 5.7 运行相关 E2E 模块并清理测试数据。
- [x] 5.8 运行 `openspec validate improve-test-comparison-agent-probe-and-summary --strict`。
