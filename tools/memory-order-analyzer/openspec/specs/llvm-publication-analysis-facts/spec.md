# llvm-publication-analysis-facts

## Purpose

规范 P4 发布模式局部事实的独立版本化提取、受限观察值与控制依赖证明、跨 TU 直接返回包装组合，以及预算和证据闭包要求。

## Requirements

### Requirement: Produce independent versioned publication-local facts
系统 SHALL 从已校验 BC、P1 `ModuleFacts v2` 及所需 P2/P3 依赖生成独立 `PublicationLocalFacts v1`，记录 LLVM/worker/analysis/policy、artifact、scope/profile、输入 digest、实际预算、能力、诊断和 frontier；SHALL 复用原始 SourceRef 并为 LLVM 分析生成证明使用独立 AnalysisRef，不修改 P1/P2/P3 文件、身份或报告语义。

#### Scenario: Existing P1 through P3 products are analyzed
- **WHEN** 合法 ModuleFacts、EffectSummary 和 ThreadContextGraph 被 P4 消费
- **THEN** 生成独立 publication sidecar，旧产物逐字节不变且 P3 仍为 `safety=not_evaluated`、`findings=null`

#### Scenario: The local fact generation is unavailable
- **WHEN** sidecar 缺失、worker 不支持 P4 policy 或输入 digest 在分析期间变化
- **THEN** 相关计划项失败或 partial，不把缺少局部事实解释为没有发布模式

### Requirement: Extract exact flag initial and written values conservatively
worker SHALL 使用 LLVM Constant、DataLayout、对象基址、偏移和访问范围提取可证明的 flag 静态初值与 store 写值，保存位宽、字节范围及原始证明。动态初始化、部分重叠、padding/endian 无法解释、未知聚合、值被截断或对象不可解析 MUST 保持 unknown，不得按零初始化或源码类型猜测。

#### Scenario: A zero-initialized atomic flag is accessed exactly
- **WHEN** 全局 atomic flag 的访问范围与可验证常量初始化子对象一致，发布 store 写入精确整数值
- **THEN** 局部事实输出精确初值、发布值、位宽、对象范围和初始化器/写指令证据

#### Scenario: The initializer bytes cannot be mapped to the access
- **WHEN** flag 位于未知布局聚合、访问动态偏移或 DataLayout 缺失
- **THEN** 初值为 unknown 并带原因，后续不得据此唯一化 reads-from

### Requirement: Derive bounded observation value dependencies and success gates
worker SHALL 从 plain/atomic load 结果沿有限 `icmp`、zero/nonzero、布尔反转、语义保持 cast、phi/select 和直接 return 传播到 branch/switch，登记成功谓词、成功/失败 edge、循环重试、edge dominance、被成功 edge 控制的区域和证明。名称、debug 文本和源码邻近 MUST NOT 参与判定。

#### Scenario: An acquire load controls a polling loop exit
- **WHEN** load 结果经受支持比较决定循环继续/退出，payload 访问只在成功 edge 后可达
- **THEN** 输出 observation、谓词、重试 edge、成功 edge及其对 payload 区域的控制证明

#### Scenario: A value transform is unsupported
- **WHEN** load 结果经过可能改变比较含义的算术、未知 cast、内存暂存或候选数超限后才到达分支
- **THEN** 保留原始 read 和已知依赖，未解释部分进入 frontier，不能伪造成功 gate

### Requirement: Separate successful observations from repeated IR nodes
系统 SHALL 为“某次读取满足成功谓词并沿成功 edge 到达消费”的条件事件创建独立、稳定的分析节点；该节点 SHALL 引用原始 read、invocation、ThreadInstance、谓词和成功 edge，但 MUST NOT 改写原始 load 的 repeated/may 语义，也不得表示运行时必然发生或读取来源已确定。

#### Scenario: A static load executes repeatedly before success
- **WHEN** 轮询 load 位于循环且退出后的 payload read 受成功 edge 支配
- **THEN** 原始 load 保持 repeated，另建条件化成功观察节点用于 P4 顺序组合

#### Scenario: No success path controls the payload
- **WHEN** payload 在成功/失败两条路径均可到达或先于观察发生
- **THEN** 不创建可保护该 payload 的成功观察关系，并登记排除或 unknown 原因

### Requirement: Compose only verified direct return wrappers
局部事实 SHALL 描述 observation 到函数直接正常 return 的受限依赖；跨调用组合 SHALL 仅沿 P2 已采用且 P3 invocation/anchor 一致的确定直接调用、兼容 ABI 和 closed scope 定义传播 caller 结果。间接、多定义、递归未收敛、异常/不返回或调用结果经未知存储传播 MUST 保持 unknown。

#### Scenario: A cross-TU wrapper returns an atomic observation
- **WHEN** callee 内 atomic load 经支持变换直接返回，caller 的确定直接调用被合法跨 TU 绑定且结果控制成功分支
- **THEN** 输出跨 invocation 的观察依赖和全部 callee/callsite/caller 证据

#### Scenario: A wrapper target is ambiguous
- **WHEN** 调用为间接、多候选、开放边界可替换或 callee return 依赖不完整
- **THEN** 不任选一个 wrapper，相关 gate 和候选降为 unknown

### Requirement: Bound local publication analysis without dangling evidence
worker SHALL 对局部节点、值/谓词候选、wrapper/SCC 轮次、输出字节和墙钟应用请求中的实际预算；成功产物 MUST 通过原始/分析节点命名空间、函数/调用归属、输入引用、digest、排序和闭包校验。超限 SHALL 保留已知结果及非空 frontier，无法形成合法闭包时该 job MUST failed。

#### Scenario: Predicate expansion reaches its limit
- **WHEN** phi/select 或 wrapper 组合超过候选或 SCC 预算
- **THEN** 记录实际计数、已知候选和未处理前沿，status 不为 complete

#### Scenario: An analysis node cites a foreign function
- **WHEN** 成功观察或 gate 的 AnalysisRef 输入属于另一未连接 invocation、错误 artifact 或陈旧 sidecar
- **THEN** 消费者拒绝产物，不让该证据参与风险分析
