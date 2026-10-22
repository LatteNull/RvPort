## MODIFIED Requirements

### Requirement: schema 设计必须由机器合同和代表性示例冻结
schema v2 capability SHALL 继续以 JSON Schema 2020-12、引用完整性规则、字段词汇表、v1/v2 合同差异与消费者迁移清单，以及 complete、partial、ambiguous、inactive、unknown 和 AVX explanation 示例作为规范合同。生产 v2 Projector SHALL 直接消费同一次 staged pipeline 的 context、workspace、knowledge、frontend、normalized facts、analysis、detection、classification、assessment 和 diagnostics snapshots，MUST NOT 读取、转换或补全 schema v1 JSON、v1 Finding、自由形态 `trace` 或字符串 Diagnostic。Projector SHALL 在序列化和 artifact 发布前构造封闭 v2 model、投影有界源码上下文、验证 Finding 内引用完整性，并只在全部请求 artifact 成功生成后原子发布；所有实现与合同资产 SHALL 在唯一 `kb-scanner-test` 容器中验证。

#### Scenario: 执行 schema v2 运行时合同门禁
- **WHEN** 独立测试容器用生产 v2 mapper/projector 处理设计正例、定向反例和合成 staged snapshots
- **THEN** 所有有效结果 SHALL 通过 JSON Schema 与引用完整性验证，所有无效引用、状态、上下文或排序输入 SHALL 因预期 reason 失败
- **AND** schema、example、reference rules、vocabulary、production model 或 serializer 漂移 SHALL 使门禁失败

#### Scenario: 从真实 AVX snapshots 生成 explanation
- **WHEN** 完整 staged pipeline 以默认 schema `2.0` 扫描人工审计的 AVX fixture
- **THEN** 生产 v2 Projector SHALL 在单个 Finding 内投影 build/source、macro 或 intrinsic Evidence、knowledge、Classification 和 Assessment 的可解析链路及每个代码型 step 的逐行上下文
- **AND** AVX 回归 SHALL 校验 symbol、span、occurrence、primaryPath、edge、break、knowledge provenance 和 Assessment impact，不得以 Finding 总数代替字段与引用正确性

#### Scenario: v2 直接投影且不依赖 v1
- **WHEN** 测试向 v2 Projector 提供 staged snapshots，同时使 v1 mapper 不可用或令任何 v1 访问立即失败
- **THEN** v2 Projector SHALL 仍能生成合法 schema 2.0 result 和请求的 renderer 内容
- **AND** 生产依赖图 MUST NOT 包含 v1 payload、v1 Finding、兼容 `trace` 或 v1 Diagnostic parser

#### Scenario: 上下文文件不可用或越界
- **WHEN** Evidence 具有合法 span，但文件已消失、无法解码、超过上下文预算或解析路径位于项目根外
- **THEN** Projector SHALL 保留可验证 Finding 与 span，使用稳定 reason 将 context 和 chain 标记为 partial/unavailable
- **AND** 它 MUST NOT 读取项目根外文件、复制其他 step 的上下文或把缺失上下文解释为没有风险

## ADDED Requirements

### Requirement: schema v2 运行时模块必须具有隔离单元测试与容器覆盖门禁
result version selector、v2 report model、Finding mapper、evidence-chain builder、source-context projector、Diagnostic projector、summary reducer、referential-integrity validator、serializer、renderers 和 artifact publisher 的每个新增或实质修改业务模块 SHALL 登记到机器可读 test inventory，并 SHALL 具有直接实例化该模块的隔离 unit suite。第三方 JSON Schema validator、文件读取、文件 replace 和 pipeline/projector 边界 SHALL 使用 fake、mock 或临时目录；component、contract、AVX 和端到端测试 MUST NOT 替代单元测试。

#### Scenario: 执行逐模块覆盖门禁
- **WHEN** `kb-scanner-test` 容器运行 schema v2 projection unit inventory
- **THEN** inventory 中每个业务模块 SHALL 被对应 isolated unit suite 执行并达到至少 90% line 和 80% branch coverage
- **AND** 缺失模块映射、未执行测试、覆盖不足或只由高层测试间接覆盖 SHALL 使门禁失败

#### Scenario: 验证投影无副作用
- **WHEN** fixture 包含可执行 build/test 文本、路径穿越候选、恶意 renderer 内容或失败的 artifact replace
- **THEN** 单元与 component tests SHALL 证明 v2 投影只读 snapshots 和项目根内源码上下文，并在失败时回滚 artifact
- **AND** scanner MUST NOT 执行项目命令、访问网络、修改输入、安装本机依赖或发布半套结果
