## MODIFIED Requirements

### Requirement: 项目自有代码必须具备单元测试
后续实现 SHALL 为所有项目自有可执行代码提供单元测试，并覆盖正常行为、边界条件和异常路径。解析适配、规则判断、证据构造、finding 去重、v2 projection、引用完整性校验、协议序列化、退出码映射和失败聚合 MUST 可在不启动完整端到端环境的情况下独立测试。

本次结果协议切换是明确批准的破坏性替换，因此测试 MUST 证明项目内全部生产者、消费者、fixtures、validation/oracle、benchmark 和文档已原子迁移到 v2，并证明不存在旧结果 serializer、版本选择、fallback 或 `schema_version: "1.4"` 结果消费路径；本次变更不要求保留旧结果的向后兼容测试。后续修改 v2 或其他已使用协议时，仍 SHALL 提供适用的兼容性、无效输入、序列化稳定性和双语完整性测试。

#### Scenario: 新增检测规则
- **WHEN** 后续实现新增或修改一条浮点检测规则
- **THEN** 同一变更包含命中、非命中、边界、unknown/unsupported 和异常证据的单元测试

#### Scenario: 本次结果协议直接替换
- **WHEN** `FloatingPointPrecisionScanResult@1.4` 被结果 v2 取代
- **THEN** 正常、partial、invalidRequest、failed 和 internalError 均只输出 v2，全部项目内消费者已切换，且测试确认不存在双写、旧 serializer、fallback 或版本选择参数

#### Scenario: 修改 v2 协议字段
- **WHEN** 本次切换完成后的变更修改结果 v2 或其他已使用输入输出协议
- **THEN** 同一变更包含适用的兼容演进、无效输入、序列化稳定性、引用完整性和双语字段完整性单元测试

## ADDED Requirements

### Requirement: 结果 v2 必须通过结构、引用和确定性合同测试
实现 SHALL 提供独立于完整扫描流程的 v2 contract tests，覆盖 JSON Schema、registered extensions、跨字段计数、主 occurrence、typed references、evidence-chain steps/edges/path/breaks、diagnostic finding references、双语字段、路径边界、稳定 ID、规范化排序和 semantic digest。测试 MUST 包含正常、空 finding、facts-only、聚合 finding、heuristic、suppressed、expired suppression、partial、invalid request、预算截断、缓存命中、悬空引用、重复 ID、非法 namespace 和输出大小边界。

#### Scenario: Evidence edge 指向不存在的 step
- **WHEN** fixture 的 evidence-chain edge、primary path 或 impact step 引用不存在的 step ID
- **THEN** contract validator 以稳定诊断拒绝该结果，测试不得只依赖 JSON Schema 的形状校验

#### Scenario: 不同绝对工作区生成结果
- **WHEN** 相同语义输入从不同绝对项目根和 artifact root 执行
- **THEN** v2 finding/occurrence/step/edge IDs、排序和 semantic digest 完全一致，默认结果不泄露任一绝对根

#### Scenario: 仅中英文展示文本变化
- **WHEN** 规则的中英文标题、说明或建议调整但语义证据不变
- **THEN** finding、occurrence、evidence-chain 和 assessment IDs 保持不变，contract tests 仍验证两种语言字段非空且语义对应

### Requirement: 旧结果协议必须从项目内完全移除
交付验收 SHALL 扫描项目自有源码、Schema、tests、fixtures、validation、benchmark 和文档中的旧结果生产/消费路径。除变更说明、历史归档或明确的负向测试数据外，不得保留旧结果 Schema、旧 serializer、`schema_version: "1.4"` 结果断言、旧 snake_case 顶层字段读取或兼容 fallback。负向 fixture MUST 明确标识为 unsupported legacy result，且不能被生产代码接受。

#### Scenario: 项目内仍存在旧结果读取
- **WHEN** 非归档生产代码或测试辅助代码仍读取旧顶层 `request_id`、`assessments`、`suppressions`、`facts`、`ir_facts`、`evidence` 或 `metadata`
- **THEN** 协议切换验收失败，相关任务不得标记完成

#### Scenario: 旧结果作为输入被接受
- **WHEN** validator 收到 `schema_version: "1.4"` 的旧扫描结果
- **THEN** 以稳定 unsupported-result-version 诊断拒绝，不尝试转换或回退解析
