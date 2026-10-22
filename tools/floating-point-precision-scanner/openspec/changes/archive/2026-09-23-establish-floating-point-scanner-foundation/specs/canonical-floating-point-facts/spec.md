## ADDED Requirements

### Requirement: 前端版本固定且不得静默回退
前端适配器 SHALL 只调用请求或锁定环境中明确解析到的 Clang 21.1.8，并 SHALL 校验实际版本。缺少编译器、版本不匹配或版本输出不可解析时 MUST 产生结构化失败，且不得搜索 PATH 中其他版本继续分析。

#### Scenario: 锁定 Clang 可用
- **WHEN** 明确路径的 Clang 报告版本 21.1.8
- **THEN** 前端记录可复现的 producer 信息并开始处理翻译单元

#### Scenario: 宿主只有其他 Clang
- **WHEN** 锁定路径不存在但 PATH 中存在其他 Clang
- **THEN** 前端返回 `frontend_unavailable`，不调用 PATH 中的替代版本

### Requirement: Canonical fact bundle 与 Clang 原始节点解耦
每个成功翻译单元 SHALL 生成符合版本化 schema 的 `FloatingPointFactBundle`，包含 producer/profile 版本、稳定翻译单元 ID、规范化编译上下文、浮点类型、字面量、算术与比较表达式、显式/隐式转换、函数与内建调用、源码/宏位置、浮点相关选项以及 unknown/unsupported 记录。规则层 MUST NOT 接收 Clang 原始 JSON 节点或进程对象。

#### Scenario: 最小 C 翻译单元
- **WHEN** C11/C17 fixture 包含基本浮点声明、算术和隐式转换
- **THEN** bundle 以 canonical 类型和 fact kinds 表达相应事实，并通过 schema 校验

#### Scenario: 最小 C++ 翻译单元
- **WHEN** C++17/C++20 fixture 包含重载调用、显式转换和浮点表达式
- **THEN** bundle 保留解析后的被调用声明、转换种类和标准版本，不暴露 Clang 节点 ID

### Requirement: 源位置同时表达拼写与宏展开
Fact 位置 SHALL 使用仓库相对 POSIX 路径、1-based 行列和可选字节范围，并在宏参与时分别保留 spelling location、expansion location 与宏名称。缺失位置不得伪造为行列 0。

#### Scenario: 宏内浮点表达式
- **WHEN** 浮点运算来自项目内宏展开
- **THEN** fact 同时包含宏定义的 spelling location 与调用点 expansion location

#### Scenario: 无可用源码位置
- **WHEN** Clang 节点没有可验证的文件位置
- **THEN** mapper 产生显式 unknown location 或诊断，不构造虚假项目路径

### Requirement: Unknown 与 unsupported 必须保守且可审计
mapper 不认识节点形状、类型语义、编译选项或目标属性时 SHALL 生成带 stage、reason、provenance 和影响范围的 unknown/unsupported 记录。未知事实 MUST NOT 被默认值补齐，也 MUST NOT 被解释为“未发现风险”。

#### Scenario: 新增的 Clang 节点形状
- **WHEN** AST fixture 包含 mapper 未注册但与浮点相关的节点形状
- **THEN** bundle 记录 unsupported fact 和受影响范围，扫描状态按阻断性保守传播

#### Scenario: 无关的未知节点
- **WHEN** 未识别节点与任何浮点类型、表达式或位置无关
- **THEN** mapper 可记录非阻断诊断而不降低状态，但不得把节点误分类为浮点事实

### Requirement: Facts 身份、摘要和排序具有确定性
每个 fact SHALL 具有由 facts schema 版本、翻译单元 ID、fact kind、规范化位置和语义载荷计算的稳定标识。bundle SHALL 按明确键排序 facts、diagnostics 和 locations，并 SHALL 计算不包含绝对路径、时间戳、进程 ID 或并发顺序的语义摘要。

#### Scenario: 重复映射同一 AST
- **WHEN** 同一 AST、编译上下文和 profiles 在不同临时目录重复映射
- **THEN** fact IDs、bundle 摘要和序列化字节完全一致

#### Scenario: 编译语义发生变化
- **WHEN** 生效语言标准、宏、target 或浮点选项改变
- **THEN** 翻译单元 ID 和 bundle 语义摘要发生变化

### Requirement: 前端失败按翻译单元隔离并脱敏
Clang 超时、非零退出、无效 JSON、资源超限或诊断不可解析 SHALL 转换为结构化双语诊断并关联稳定翻译单元 ID。默认结果 MUST 限制 stderr 大小并移除凭据、环境变量值和项目根外绝对路径；单个失败不得删除其他成功 bundle。

#### Scenario: 一个翻译单元产生无效 AST JSON
- **WHEN** 多个计划翻译单元中一个 Clang 输出被截断
- **THEN** 该单元计入 failed，其他单元继续，最终状态为 `partial` 且没有伪造 bundle

#### Scenario: 所有前端调用失败
- **WHEN** 所有计划翻译单元均未产生可用 bundle
- **THEN** 最终状态为 `failed`、退出码为 3，并明确未分析范围
