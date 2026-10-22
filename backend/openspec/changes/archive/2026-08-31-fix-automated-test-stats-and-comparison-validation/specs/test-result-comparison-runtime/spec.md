## ADDED Requirements

### Requirement: 测试结果比较必须优先读取 agent 结果文件
测试结果比较运行时 SHALL 要求 agent 在专用 workspace 中写出固定结构化结果文件，并 SHALL 以该文件作为比较结果的主要解析来源。

#### Scenario: agent 写出结果文件
- **WHEN** 后端调用 `TEST_LOG_COMPARE` 阶段绑定的 agent runtime
- **THEN** 后端 SHALL 在 agent workspace 中提供比较输入文件
- **AND** prompt SHALL 要求 agent 写出 `comparison-result.json`
- **AND** `comparison-result.json` SHALL 包含总体结论、风险等级、置信度、source/target 测试统计和差异项
- **AND** 后端 SHALL 优先读取 `comparison-result.json` 作为结构化结果

#### Scenario: transcript 不作为主要解析来源
- **WHEN** agent 执行结束并产生 stdout、stderr 或 mergedOutput
- **THEN** 后端 MUST NOT 从 `mergedOutput` 中直接截取第一个 JSON 对象作为成功结果
- **AND** 后端 SHALL 将 stdout、stderr 和 mergedOutput 保存为诊断材料
- **AND** 后端 SHALL 在 artifact 摘要中记录实际解析来源

#### Scenario: 结果文件缺失
- **WHEN** agent 退出码为 0 但未写出 `comparison-result.json`
- **THEN** 后端 MAY 从 stdout 中提取 fenced JSON 或最后一个完整 JSON 作为兼容降级
- **AND** 降级结果仍 MUST 通过结构和语义校验
- **AND** 如果无法取得合法结果，比较运行 SHALL 标记为 `FAILED`

### Requirement: 测试结果比较必须拒绝占位符和组合枚举输出
测试结果比较运行时 SHALL 对 agent 输出执行结构校验和语义校验，防止 schema 示例或占位符被保存为成功结果。

#### Scenario: 拒绝组合枚举值
- **WHEN** agent 输出字段值包含 `SUCCEEDED|FAILED|CANCELLED|TIMEOUT|UNKNOWN`、`CRITICAL|HIGH|MEDIUM|LOW|INFO` 或类似组合枚举字符串
- **THEN** 后端 SHALL 认为 agent 输出无效
- **AND** 比较运行 SHALL 标记为 `FAILED`
- **AND** 错误码 SHALL 为 `TEST_COMPARE_AGENT_OUTPUT_INVALID` 或等效受控错误码

#### Scenario: 拒绝模板占位符
- **WHEN** agent 输出的 `summary`、`recommendation`、`testCountBasis`、finding 标题或描述仍为 `...`、空模板或明显示例内容
- **THEN** 后端 SHALL 认为 agent 输出无效
- **AND** 后端 MUST NOT 将该比较运行保存为 `SUCCEEDED`

#### Scenario: 校验统计字段
- **WHEN** agent 输出 source 或 target 测试统计
- **THEN** `status` SHALL 是 `SUCCEEDED`、`FAILED`、`CANCELLED`、`TIMEOUT`、`UNKNOWN` 中的单个值
- **AND** 测试数量字段 MAY 为 `null`
- **AND** 非空测试数量字段 MUST 为非负整数
- **AND** `extractionConfidence` MUST 为空或位于 0 到 1 之间

#### Scenario: 校验差异项字段
- **WHEN** agent 输出差异项列表
- **THEN** 每条差异项的 `differenceType` SHALL 是 `EXIT_CODE`、`STDERR`、`STDOUT`、`REPORT`、`MISSING_REPORT`、`OTHER` 中的单个值
- **AND** 每条差异项的 `severity` SHALL 是 `CRITICAL`、`HIGH`、`MEDIUM`、`LOW`、`INFO` 中的单个值
- **AND** `confidence` MUST 为空或位于 0 到 1 之间

### Requirement: 测试结果比较提示词必须避免可照抄的占位 JSON
测试结果比较 prompt SHALL 以字段说明和单值枚举约束描述输出格式，避免把组合枚举或 `...` 作为可直接照抄的 JSON 字段值。

#### Scenario: 输出契约描述
- **WHEN** 后端生成测试比较 agent prompt
- **THEN** prompt SHALL 明确要求最终结果写入 `comparison-result.json`
- **AND** prompt SHALL 说明每个枚举字段必须选择单个合法值
- **AND** prompt MUST NOT 使用 `"A|B|C"` 作为实际 JSON 字段值示例
- **AND** prompt MUST NOT 使用 `...` 作为可直接输出的字段值

#### Scenario: 允许补充说明文件
- **WHEN** agent 需要输出非结构化判断说明
- **THEN** agent MAY 写出 `comparison-notes.txt`
- **AND** 后端 MAY 将其保存为诊断 artifact
- **AND** 后端 MUST NOT 从说明文件解析业务字段
