# 单元测试发现问题台账

本文件只记录本 change 新增测试发现的疑似业务问题，不在覆盖率工作中直接修改尚未确认的业务逻辑。

## 记录模板

### ISSUE-XXX：简短标题

- 分类：明确规格违例 / 语义待确认
- 状态：待确认 / 已确认待独立修复 / 非缺陷
- 规格依据：对应 OpenSpec requirement/scenario，未知时写“暂无明确规格”
- 最小复现：测试类与测试方法
- 输入条件：触发行为的最小输入和依赖返回值
- 预期行为：规格规定或待确认假设
- 实际行为：测试观测结果
- 影响范围：涉及模块、API、任务或数据
- 当前处理：失败测试阻塞 / characterization test 锁定当前行为
- 建议 change：确认需要修复后使用的 change 名称

## 当前记录

### ISSUE-001：Redis key 的 null part 抛出未归一化异常

- 分类：语义待确认
- 状态：待确认
- 规格依据：暂无明确规格；当前构造器错误信息表明非法 part 应统一作为参数错误处理
- 最小复现：`RedisCacheClientTests.redisKeyRejectsBlankSegmentsAndColonsAndCopiesParts`
- 输入条件：构造 `RedisKey("domain", "purpose", [null])`
- 预期行为：与空白或包含冒号的 part 一致，抛出带稳定消息的 `IllegalArgumentException`
- 实际行为：`List.copyOf(parts)` 在自定义校验前抛出 `NullPointerException`
- 影响范围：直接使用 `RedisKey` 构造器且 part 可能为 null 的调用方；目前未发现 API 直接暴露该输入
- 当前处理：characterization test 锁定当前行为，不在本 change 修改业务逻辑
- 建议 change：`normalize-redis-key-validation-errors`

### ISSUE-002：普通 stdout 中的嵌套 JSON 会被误截取为内部对象

- 分类：明确规格违例
- 状态：已确认待独立修复
- 规格依据：测试比较 agent 在缺少结果文件时允许从 stdout 降级读取完整结构化比较结果；降级结果仍应保留根对象
- 最小复现：`TestComparisonAgentRuntimeTests.plainStdoutNestedJsonCurrentlySelectsNestedObjectInsteadOfRoot`
- 输入条件：agent 未生成 `comparison-result.json`，stdout 同时包含说明文本和一个带 `sourceStats`、`targetStats` 等嵌套对象的合法 JSON
- 预期行为：提取并解析完整根 JSON，返回测试比较结果
- 实际行为：`extractJsonFromStdout` 从每个左花括号开始尝试解析并保留最后一个合法对象，内部 `targetStats` 覆盖根对象，最终报 `TEST_COMPARE_AGENT_OUTPUT_INVALID`
- 影响范围：未按约定写结果文件、仅把完整 JSON 输出到普通 stdout 且没有 Markdown fence 的 agent 兼容路径
- 当前处理：characterization test 锁定当前行为，不在覆盖率 change 中修改业务逻辑
- 建议 change：`fix-test-comparison-stdout-json-root-extraction`

### ISSUE-003：Agent runtime 的 JSON 字面量 null 未归一化为空集合

- 分类：明确规格违例
- 状态：已确认待独立修复
- 规格依据：Agent runtime 的 `defaultArgs`、`config` 与探测详情响应均以集合表达可选配置；缺失配置应按空集合处理
- 最小复现：`AgentRuntimeAdapterUtf8Tests.malformedNullAndBlankArgumentsFallBackToAdapterDefaults`、`AgentRuntimeServiceTests.jsonLiteralNullCurrentlyProducesNullCollections`
- 输入条件：数据库 JSONB 字段包含 JSON 字面量 `null`，而不是 SQL NULL
- 预期行为：与 SQL NULL、空白和损坏 JSON 一致，统一降级为空 `List` 或空 `Map`
- 实际行为：Jackson 返回 Java `null`；adapter 随后调用 `args.isEmpty()` 触发 `NullPointerException`，响应映射器也会输出 `null` 集合
- 影响范围：Agent runtime 执行及管理员模型运行时配置响应；手工写入或迁移产生 JSON 字面量 `null` 时可触发
- 当前处理：characterization test 锁定当前行为，不在覆盖率 change 中修改业务逻辑
- 建议 change：`normalize-agent-runtime-null-json-config`
