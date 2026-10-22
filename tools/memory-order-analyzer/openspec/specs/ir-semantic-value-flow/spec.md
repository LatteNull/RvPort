# ir-semantic-value-flow

## Purpose

规范确定且有类型的 IR 值图、操作数关系、条件控制流与调用接口，以及有界提取和未知语义的保守表达。

## Requirements

### Requirement: Preserve typed value identities and exact constants

系统 SHALL 通过 LLVM API 为语义所需根及其操作数闭包建立模块局部值节点和显式引用，涵盖参数、常量、指令结果与函数返回；同一 artifact/extractor 的引用 SHALL 确定且不依赖源码显示名、内存地址或遍历容器随机顺序。整数 SHALL 保留位宽与精确位模式字符串，不强制赋予源语言 signedness；null、undef、poison、freeze 与 unsupported SHALL 可区分，不以零代替未知。

#### Scenario: Wide integers survive JSON serialization

- **WHEN** 所需值包含超过 64 位的整数常量和不同位宽的相同低位模式
- **THEN** JSON 保留完整位模式及位宽，值不会因浮点或 int64 转换截断，不同类型的值不会错误合并

#### Scenario: Special values and unmodeled values remain distinct

- **WHEN** 操作数包含 null、undef、poison、freeze 和当前未支持的值类型
- **THEN** 输出独立节点种类或带原因的 unsupported，freeze 保留其输入而不选择运行值，不能把这些值都序列化为零

#### Scenario: Repeated extraction preserves references after module destruction

- **WHEN** 相同 BC、artifact 和 extractor 被重复提取并在 LLVM Module 释放后序列化
- **THEN** 节点身份和语义内容一致，引用仍合法，字符串不因借用存储释放而变化

### Requirement: Export operand relations without solving paths

系统 SHALL 导出 phi、select、cast、GEP、icmp、相关整数算术/位运算和 aggregate extract/insert 的有序操作数与适用属性；phi SHALL 保留前驱块，比较 SHALL 保留 predicate，转换 SHALL 保留源/目标类型，算术 SHALL 保留适用的 nsw/nuw/exact。循环关系 SHALL 用引用表达，未实现语义 SHALL 带原因保留，不能声称完成值传播、路径求解或调用点特化。

#### Scenario: Loop phi references a backedge result

- **WHEN** phi 引用后向边上的计算结果，且计算又使用该 phi
- **THEN** 两遍登记生成有限的闭合引用图并保留每个 incoming 的前驱，不递归展开到耗尽资源

#### Scenario: Select and casts distinguish signed interpretation

- **WHEN** 值链含 select、sext/zext、signed/unsigned icmp 及带溢出约束的整数运算
- **THEN** 保留条件/两候选、转换类型、比较 predicate 和适用 flags，不把链折叠成猜测常量或必然可行路径

### Requirement: Preserve conditional control-flow and call interfaces

系统 SHALL 保留原有 CFG，并为 br/switch 输出带后继序号、目标与条件/case/default 的边；SHALL 区分 ret/void/unreachable。call/invoke SHALL 保存 called operand、有序实参、形参接口、返回结果或 void、函数类型、调用约定以及 invoke 的 normal/unwind 后继。适用 ABI 属性、tail 标记和 operand bundles SHALL 结构化保留或显式诊断不支持，不能静默抹除。未支持 terminator SHALL 保留后继和未知原因。

#### Scenario: Switch cases share a successor

- **WHEN** 两个不同 switch case 指向同一个块且存在 default 边
- **THEN** 保留两个精确 case 值和各自后继序号以及 default 含义，不因目标块相同而合并条件

#### Scenario: Invoke has an exceptional successor

- **WHEN** 调用产生返回值并包含正常及异常后继
- **THEN** 保存实参/返回引用和两个不同类型的后继，异常边不转换成普通返回，函数 ret 引用可解析

#### Scenario: Indirect and opaque call features are present

- **WHEN** 调用目标是函数指针，或调用携带未支持的 bundle/ABI 语义，或出现未支持的终结指令
- **THEN** 保存目标操作数、原始参数和可见后继，保留 indirect/unsupported 原因，不猜测唯一被调函数或完整控制语义

### Requirement: Bound semantic graph extraction without dangling references

系统 SHALL 使用显式且版本化的提取 policy 限制节点、引用、常量深度与输出，并用 visited/引用处理循环。局部不能解释的值 SHALL 保留带原因节点并标记 partial；节点/引用或输出总预算耗尽 SHALL 使该 TU 事实提取失败，不发布残缺图。初始 policy SHALL 明确为最多 100000 值节点、500000 值操作数引用、常量深度 64，worker 输出上限沿用 16 MiB，时间预算继续生效。

#### Scenario: A constant exceeds the nesting limit

- **WHEN** 初始化聚合的嵌套深度超过 policy 上限而总体图预算仍可满足
- **THEN** 用可引用的 depth-limit unknown 叶节点保留边界并将 extraction 标为 partial，不把未展开元素视为零

#### Scenario: Total graph or output budget is exhausted

- **WHEN** 值节点、值操作数引用或 JSON 输出超过 policy 总预算
- **THEN** 报告 extraction_budget_exceeded，该 TU 不发布成功 facts 或悬空引用，其他独立 TU 可继续且完整计划分母不变
