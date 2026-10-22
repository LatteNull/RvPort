## ADDED Requirements

### Requirement: 兼容 Finding 必须投影完整语义与引用闭包
Compatible Report Projector SHALL 在不改变 schema 1.0 必需字段和既有 Finding identity 的前提下，从结构化 Evidence、KnowledgeEntry、Relation 和 ProofPath 恢复语义 `symbol`，并 SHALL 在可选 `trace` 字段中保留主 Evidence 的完整 start/end span 及该 Finding 引用的完整证据闭包。Projector MUST NOT 重新扫描 snippet、源码或构建文件来猜测缺失信息。

#### Scenario: intrinsic 和向量类型具有结构化 symbol
- **WHEN** 主 Evidence 或被引用的 KnowledgeEntry/终端 Relation 提供唯一语义 symbol
- **THEN** Finding `symbol` SHALL 使用该结构化值
- **AND** 相同输入乱序 MUST NOT 改变 symbol、主位置或 Finding identity

#### Scenario: 宏调用引用定义和终端 intrinsic
- **WHEN** Classification 引用从宏调用到宏定义和终端 x86 intrinsic 的完整 proof
- **THEN** `trace.evidence` SHALL 包含调用、定义与终端 Evidence 对象，并保留全部 Relation/ProofPath 引用
- **AND** 用户 MUST NOT 需要读取内部 snapshot 才能定位宏定义

#### Scenario: 内部 Evidence 具有结束位置
- **WHEN** 主 Evidence 提供完整 start/end 坐标
- **THEN** 顶层 `location.file/line/column` SHALL 保持兼容，且 `trace` SHALL 以可选字段保留完整 span
- **AND** 旧 schema 1.0 消费者忽略该字段时仍能读取报告

#### Scenario: 引用闭包断裂
- **WHEN** 任一被引用对象不存在、类型冲突或 traversal 超限
- **THEN** Projector SHALL 保留可验证的局部 Finding 并产生 partial/failed Diagnostic
- **AND** 它 MUST NOT 伪造 symbol、span、Evidence 或 complete trace

### Requirement: 聚合 Finding 必须保留全部底层 occurrence
当多个位置按既有策略合并为一个 Finding 时，Projector SHALL 保持现有 Finding 数量、主位置和 summary 计数语义，并 SHALL 在可选 `trace` 中提供稳定的 occurrence count 和逐 occurrence path、span、configuration、selection status 与 Evidence 引用。

#### Scenario: 同一构建参数在多个位置出现
- **WHEN** 24 个构建参数 occurrence 被按 4 个 Makefile 根因聚合
- **THEN** 兼容结果 SHALL 继续产生 4 个 Finding，并在对应 trace 中覆盖全部 24 个 occurrence
- **AND** occurrence 顺序 MUST NOT 依赖文件系统或输入遍历顺序

#### Scenario: occurrence 信息不完整
- **WHEN** 某个 occurrence 缺少 configuration、结束位置或选择状态
- **THEN** trace SHALL 保留该 occurrence 及明确的 completeness/unknown reason
- **AND** Projector MUST NOT 删除它或复制其他 occurrence 的字段

### Requirement: 重复关系诊断必须可追溯地聚合
Compatible Report Projector SHALL 对同一扫描中具有相同 code、reason、relation kind、stage 和 severity 的重复关系 Diagnostic 做确定性聚合，并 SHALL 保留原始数量、代表位置和稳定引用；聚合 MUST NOT 丢失 failed/partial 状态或改变扫描退出码语义。

#### Scenario: 大量 include 关系以相同原因未解析
- **WHEN** 多个 `unresolved-include` Diagnostic 具有相同聚合键
- **THEN** 对外 diagnostics SHALL 使用一条聚合记录表达，并包含总数与可追溯引用
- **AND** HTML/log SHALL 展示摘要而不是重复相同文案

#### Scenario: 原因或严重性不同
- **WHEN** Diagnostic 的 reason、relation kind、stage 或 severity 任一不同
- **THEN** 它们 SHALL 保持为不同聚合组
- **AND** 聚合 MUST NOT 把 failed 与 warning/partial 合并

### Requirement: 投影修正必须保持 schema 1.0 并通过隔离单元门禁
本 change 修改的 reference index、Finding mapper、summary mapper、Diagnostic aggregator 和 renderer SHALL 分别映射到隔离单元测试，并 SHALL 在唯一 `kb-scanner-test` 容器中达到每模块至少 90% line / 80% branch。`scan-result.json` 的 `schemaVersion: "1.0"`、既有顶层字段、必需 Finding 字段、三个 artifact 和旧消费者行为 SHALL 保持兼容。

#### Scenario: 运行投影模块单元门禁
- **WHEN** 独立容器执行本 capability 的 unit inventory
- **THEN** 每个新增或实质修改业务模块 SHALL 被执行并分别满足 line/branch 门槛
- **AND** component、AVX 或全量回归 MUST NOT 替代隔离单元覆盖

#### Scenario: 旧消费者读取增强结果
- **WHEN** 结果包含新增 trace span、occurrences 或聚合 diagnostic details
- **THEN** 旧消费者 SHALL 继续读取既有字段、summary 和 artifacts
- **AND** scanner MUST NOT 输出 schema 2.0 或第二个主结果文件
