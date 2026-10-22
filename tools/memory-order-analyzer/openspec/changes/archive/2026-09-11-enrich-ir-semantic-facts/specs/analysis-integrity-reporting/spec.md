## MODIFIED Requirements

### Requirement: Publish versioned and deterministic artifact contracts

系统 SHALL 为 manifest、facts、scope/index 和 RunReport 提供可校验的版本化 schema、显式对象引用及确定性排序；消费者 SHALL 按 kind 验证主 schema 版本：ModuleFacts 与 RunReport 使用 v2，其他已有 kind 保持 v1。消费者 SHALL 拒绝 v1 ModuleFacts/RunReport 和不支持的未来版本，不以填默认值伪造新事实或历史报告的提取状态。相同输入、extractor 和 policy 的语义事实及引用 SHALL 稳定，时间戳等运行字段 SHALL 与语义身份分离；机器输出不得混入日志文本。

#### Scenario: A consumer receives a future schema version

- **WHEN** worker 或编排层输入不支持的主 schema 版本
- **THEN** 输出版本不兼容诊断而非按旧字段静默解析

#### Scenario: Repeat fact extraction for the same artifact

- **WHEN** 相同 BC、extractor 版本和配置被重复读取
- **THEN** 事件/符号身份、语义内容和排序一致，运行时间等字段不改变 artifact 引用

#### Scenario: Old facts and unchanged manifests are consumed

- **WHEN** 输入 v1 ModuleFacts 及仍合法的 v1 BCArtifact/ScopeManifest
- **THEN** 拒绝旧 facts 并提示从 BC 重提取，不对合法未升级 kind 一律要求 v2；保留旧文件且不虚构缺失字段

## ADDED Requirements

### Requirement: Distinguish new reports from historical v1 reports

新输出 RunReport SHALL 使用 schema v2 且包含 fact_extraction；新消费者 SHALL 明确拒绝将 v1 历史报告按 v2 解释，不自动填入 complete/not_run 伪造未记录的状态，历史文件 SHALL 保留不变。

#### Scenario: A historical report lacks extraction information

- **WHEN** 新消费者收到未记录 fact_extraction 的 v1 RunReport
- **THEN** 返回版本不兼容诊断，不升级或覆盖该历史文件；新运行生成独立 v2 报告

### Requirement: Validate semantic references at every consumption boundary

系统 SHALL 在 worker 输出和磁盘事实消费入口执行结构及引用校验，验证唯一 ID、被引用节点存在、参数/指令所属函数、phi 前驱及 CFG 边一致性。unknown 节点 SHALL 是合法可引用对象，不等于悬空引用；结构不合法 SHALL 拒绝而非降级为空图。

#### Scenario: An index input has a dangling or foreign value reference

- **WHEN** index/link 读取的事实含悬空引用、重复 ID、错误函数归属或与 CFG 不一致的 phi/边
- **THEN** 返回 invalid_reference 或对应结构错误，不输出成功 index/link，不依赖该文件过去曾通过 collect 的假设

#### Scenario: An unsupported node has a valid identity

- **WHEN** 值图引用一个具有合法 ID 与原因的 unsupported 节点
- **THEN** 引用校验允许保留此节点，同时内容完整性仍为 partial，不将它伪装成已知值

### Requirement: Isolate extractor generations across artifact paths

系统 SHALL 以一致的 facts/extractor/policy 元数据驱动 worker 协议检查与 collect、import-bc、index、link 身份，初始新 extractor 版本为 0.2.0。旧 worker 或不同 policy SHALL 不因 LLVM 版本相同而被接受。版本变化 SHALL 隔离缓存与输出；迁移 SHALL 通过重采集或 BC 重提取完成，不覆盖旧产物、不抬高 provenance、不丢失已有 lineage。重键后的 scope 成员 SHALL 由显式映射供用户更新，不能自动猜目标范围。

#### Scenario: A worker has the right LLVM but the wrong protocol

- **WHEN** worker 使用 LLVM 21.1.8 却不支持 ModuleFacts v2 或预期 extractor/policy
- **THEN** doctor 及实际读取入口报告协议不兼容，不发布伪装新版本事实

#### Scenario: Collection encounters an old cache generation

- **WHEN** 相同源码配置和输入曾由旧 extractor 缓存
- **THEN** 新 collect 使用不同 ArtifactKey 且不计为旧缓存命中，旧文件不删除，新产物保留原始配置/profile 和重新依赖发现行为

#### Scenario: Old manifested bitcode is re-extracted

- **WHEN** 通过 import-bc 导入具有有效旧 manifest 的 BC
- **THEN** 验证 hash/来源后确定性重键，保留旧 key 与既有 lineage、context/profile/provenance，并提供映射；不覆写旧产物，重复导入不无限增长祖先

#### Scenario: Raw imports and linked modules change extractor generation

- **WHEN** 无 manifest 导入或显式 link 在新 extractor 下运行
- **THEN** 身份包含当前 facts/extractor/policy；原始导入仍为 unknown provenance，linked 产物重读为 v2 且保留所有祖先，index/link 拒绝异代事实混合和祖先重叠

### Requirement: Report fact extraction completeness without semantic verdicts

ModuleFacts SHALL 记录 extraction policy、complete/partial 状态、所需根/节点/unknown 计数及可定位诊断。RunReport SHALL 增加独立 fact_extraction 状态 complete/partial/failed/not_run、模块计数与原因，区分 parse/verify、源码映射和事实解释完整性；分母 SHALL 明确且零分母不为 100%。有可用但部分事实的请求 SHALL 退出 2，全部不可用或非法请求退出 1，无相关缺口退出 0；语义分析 SHALL 仍为 not_run，safety 为 not_evaluated，findings 为 null。

#### Scenario: Parsing succeeds with unsupported semantic operands

- **WHEN** BC parse/verify 成功且部分所需值被表示为 unknown
- **THEN** 保留可用事件/引用，fact_extraction 为 partial、提供原因并退出 2，不把 IR 读取成功等同于事实全部可解释

#### Scenario: One translation unit exceeds the extraction budget

- **WHEN** 多 TU 请求中一个 TU 因预算失败而其他 TU 产生可用事实
- **THEN** 保留完整计划分母、失败原因及成功事实，报告 partial 并退出 2，不将失败 TU 从统计中移除

#### Scenario: Complete facts still do not constitute a safety scan

- **WHEN** 所需范围内所有支持的 v2 事实提取完成，或仅运行 doctor
- **THEN** 前者 fact_extraction 为 complete、后者为 not_run；两者均保持 semantic_analysis not_run、safety not_evaluated、findings null，过程间/线程/内存模型能力不启用
