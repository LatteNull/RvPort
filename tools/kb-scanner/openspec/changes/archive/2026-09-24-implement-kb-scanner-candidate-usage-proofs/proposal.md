## Why

现有候选语义准入只能消费显式 `has_semantic_role` 证明，默认分析管线尚无自动 producer，因此人工确认的数据用途仍通常表现为 unknown。本 change 在保留全部原始 fact 的前提下补齐有界用途证据生成，让分类能够区分已证明的局部纯数据用途、已有执行依赖以及尚无法判断的用途。

## What Changes

- 复用现有 Tree-sitter、可选 Clang、NormalizedFact 和 Evidence Graph，增加候选相关的声明绑定、读取/写入、简单赋值、条件控制与逃逸记录；不引入第二套解析器或全程序分析引擎。
- 从已有候选事实需求生成局部使用闭包，覆盖宏/枚举/标识符候选，不用 codec、SHA、CRC、x86 等名称白名单直接排除。首版只证明有界、无逃逸、无未知调用的局部纯数据用途；跨函数、复杂宏或开放作用域保持 unknown。
- 扩展内部准入支持不强行命名为算法/格式的 `non_execution_data` 角色，明确数据用途与实现可移植性是两个问题。数据选择分支含 AVX、asm 或未知调用时，不可仅凭 selector 是数据 ID 排除该候选。
- 保留原 Evidence、NormalizedFact、Observation 和已有执行 proof；只在分类阶段应用完整、同配置且覆盖全部相关 occurrence 的用途证明。已确认 high/blocker 不得降级。
- V2 使用现有命名空间 `extensions` 展示有界用途与排除审计，在仍保留的 Finding 内自包含必要源码链；保留默认 V2、显式 V1、三个 artifact，不修改核心 schema、后端或前端接入。
- 新增人工用途 oracle、对照 ledger、隔离单元与规模门禁。CC-0006 有符号移位不在本 change，仍为低优先级末项。

## Capabilities

### New Capabilities

- `kb-scanner-candidate-usage-proofs`: 候选驱动的局部用途采集、绑定、闭包、冲突和预算判定，以及自动生成可消费的用途证明。

### Modified Capabilities

- `kb-scanner-cpp-frontends`: 提供候选用途所需的可定位语法事实，保持原生解析安全、原事实稳定和配置隔离。
- `kb-scanner-candidate-semantic-admission`: 从仅消费手工构造证明扩展为消费自动 producer，纳入纯数据角色并强化完整性检查。
- `kb-scanner-evidence-graph`: 增加非执行性质的用途关系与证明，隔离目标可达性和替代实现证明。
- `kb-scanner-report-schema-v2`: 在既有 extensions 中补充自包含用途说明和被排除候选审计，不增加核心必填字段或枚举。

## Impact

范围仅 `tools/kb-scanner`：C/C++ frontend、normalization、候选需求选择、usage analyzer、composite pipeline、semantic admission、分类/评估边界及 V2 投影/HTML。每个新增或实质修改业务模块均需隔离单测映射；整个 `kb_scanner/`、`scripts/`、`tools/` 自有可执行源码（包括未加载模块）以及每个受影响模块的行/分支覆盖率均须至少 90%。真实 parser、CLI 和固定项目扫描另作组件/回归验证，不代替单元覆盖。

不新增宿主依赖、不修改生产容器/根 Compose、不运行被扫描项目、编译器或测试。不扩展到 OS、ARM 迁移、RVWMO、浮点分析或 uname 交叉编译误选。Clang/GCC 两份 generated facts 与 curated 知识资产继续复用，内容及哈希不变。

遵循当前已实现的默认 schema 2.0/显式 schema 1.0；配置背景中的早期 V1 描述不代表回退默认输出。V1 字段合同及 JSON/HTML/log 名称保持，允许经过逐字段审校的分类数量和说明变化，不宣称报告字节完全不变。
