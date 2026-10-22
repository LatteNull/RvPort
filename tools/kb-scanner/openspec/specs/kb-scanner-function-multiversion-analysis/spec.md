# KB Scanner 函数多版本分析规范

## Purpose

定义 KB Scanner 在纯静态分析范围内识别函数多版本机制、可靠函数身份、default 状态和版本体依赖的合同，明确配置隔离、证据完整性、资源预算与兼容报告边界。

## Requirements

### Requirement: 函数多版本必须按受支持机制与可靠函数身份分组

Scanner SHALL 对可定位的 `target` 与 `target_clones` 属性建立带机制、规则版本、作用域、语言、配置和来源的版本组，区分单个 target 特化、多定义版本组和单体 clone 列表。绑定 MUST 基于可验证声明/定义关系而非裸名、文件家族或路径相似；不支持的机制及语法 SHALL 保留候选与 unknown 原因。

#### Scenario: 普通 target 特化
- **WHEN** 只有一个自由函数定义带 `target("avx2")`，没有其他多版本证据
- **THEN** SHALL 保留属性及既有 x86 feature 事实，记录单特化状态
- **AND** MUST NOT 仅因此生成缺少 default 的问题

#### Scenario: 不同作用域或重载同名
- **WHEN** 同名函数具有不同参数类型、namespace、内部 linkage 或独立 static 文件作用域
- **THEN** SHALL 隔离身份；类型别名或复杂签名无法确定时保留 ambiguous
- **AND** MUST NOT 按 basename 或首次遍历结果合并

#### Scenario: 一个 clone 定义
- **WHEN** 一个函数体具有完整 `target_clones("avx2,default")` 或等价多字符串/混合字面量列表
- **THEN** SHALL 记录多个版本描述及一个真实共用源函数体
- **AND** MUST NOT 创建多个虚假函数定义或重复计算同一个 body fact

#### Scenario: 不支持的分发机制
- **WHEN** 输入具有 cpu_dispatch/cpu_specific、target_version、pragma 属性栈、手写 resolver、模板或无法展开的属性宏
- **THEN** SHALL 保留可定位原始事实和明确的 unknown/unsupported 范围
- **AND** MUST NOT 套用 target 的 default 缺失规则或将 ARM 专用版本当作 x86 迁移问题

### Requirement: Default 状态必须区分声明定义完整性和目标适用性

版本组 SHALL 分别表达 group completeness、default presence、default definition、body dependency 和按 configuration 的 target selection/applicability。缺失判定 SHALL 依赖明确的范围闭合与有官方来源的适用 compiler/language/target 语义规则；源侧构建成功或 default 标签 MUST NOT 证明 RISC-V 适用性。

#### Scenario: Default 只有声明
- **WHEN** 找到 `target("default")` 声明但没有唯一有效的对应定义
- **THEN** SHALL 表示 default 存在且为 declaration_only/unknown 实现状态
- **AND** MUST NOT 宣称可执行 fallback 已具备或全项目不存在定义

#### Scenario: 有界完整组缺少 default
- **WHEN** 受支持局部组和属性列表完整，适用规则明确要求 default，且同一配置范围内未提供该版本
- **THEN** SHALL 记录 absent_in_scope、范围边界、规则来源和支持该缺口的证据
- **AND** MUST NOT 扩大为全项目缺少 RISC-V/通用实现

#### Scenario: 工具链或输入不足
- **WHEN** compiler profile 未知、跨 TU 定义不闭合、相关预处理条件未知、输入排除或解析/预算不完整
- **THEN** 缺口结论 SHALL 保持 unknown 并列出具体原因
- **AND** MUST NOT 通过执行编译器、项目命令或远程工具来补证据

#### Scenario: Default 函数体含 AVX
- **WHEN** default 定义内存在已确认的 x86 intrinsic fact
- **THEN** SHALL 同时展示 default 定义存在与真实 x86 依赖
- **AND** MUST NOT 因 default 名称覆盖、删除或降低原依赖事实

### Requirement: 版本依赖必须复用精确事实并保持配置隔离

Scanner SHALL 按文件、最近有效函数体、精确 span 和 configuration 索引关联已有 fact、Knowledge provenance 和 source/build proof；MUST NOT 重新创建知识词表、扩大到任意跨函数递归，或把运行时版本选择推导为编译期排除。

#### Scenario: 相同行及嵌套函数体
- **WHEN** 同一行存在多个函数或某版本体含 lambda，且调用只属于其中一个真实 body
- **THEN** SHALL 按字节范围与归属绑定，不把内层依赖自动吸附到外层版本
- **AND** 无法唯一定位的调用 SHALL 保留 unknown

#### Scenario: 不同配置选择不同
- **WHEN** 同一源码在两个现有配置中分别 selected 和 inactive
- **THEN** SHALL 分别绑定对应证明，不用一份状态覆盖另一份
- **AND** source file selected MUST NOT 自动成为某个运行时 clone selected

### Requirement: 函数多版本处理必须确定性且具备资源门禁

Scanner SHALL 使用一次轻量声明索引、签名分桶和精确依赖索引，限制声明、组、版本、属性大小、关联和输出预算；发现、绑定与输出截断 SHALL 独立保留数量及稳定原因。MUST NOT 做全函数两两比较、每 Finding 重扫源码/全图或全 root×terminal proof 重搜；身份 MUST 不含绝对根路径或遍历时序。

#### Scenario: 预算与乱序
- **WHEN** 输入乱序、根目录变更或任何具名预算被耗尽
- **THEN** 同一语义输入的稳定 ID/排序 SHALL 不变；超限 SHALL 有界结束并保留 partial 与计数
- **AND** 截断 MUST 阻止 default 缺失推理而不删除原事实

### Requirement: 多版本能力必须通过隔离单元和人工字段验收

全部新增/实质修改业务模块 SHALL 有机器可读隔离 unit 映射；独立 scanner 测试容器中，所有自有可执行源码（含未加载模块）整体及每个受影响模块的行/分支覆盖率 SHALL 均至少 90%。高层回归、真实 parser 或性能结果 MUST NOT 替代隔离单元；两份 compiler fact JSON SHALL 保持原字节。

#### Scenario: 申请实施验收
- **WHEN** 实现申请完成
- **THEN** SHALL 提交实际命令、单元/覆盖报告、范围/排除理由、字段级人工 oracle、完整回归及 10000/20000 规模性能记录
- **AND** 失败、覆盖不足或映射缺失 SHALL 阻止验收，不得收窄范围或安装宿主依赖绕过
