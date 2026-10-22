## ADDED Requirements

### Requirement: Validate degraded analysis independently for four language profiles

固定离线语料 SHALL 分别覆盖 C11、C17、C++17、C++20 的 ast-ir、ir-only、ast-only、failed，包含单 TU/至少三物理 TU、无关失败 TU、缺失 include/宏/生成物、GCC replay 不兼容、IR/P2/P3/P4 失败、预算和 cache 损坏。每种 profile SHALL 有独立 planned/eligible truth 分母，C case MUST NOT 依赖 C++ AST 或标准库模型。

#### Scenario: C17 and C++17 both exercise AST-only

- **WHEN** 两个 profile 均形成可信 AST 且受控 IR 阶段失败
- **THEN** 两者分别产生 source-only unknown 候选、对应 C/C++ 源事实和独立 truth observation，不合并为一个语言结果

#### Scenario: A fatal C source error has recovery nodes

- **WHEN** C11 fixture 缺失声明或必需头文件且 Clang 仍产生错误恢复 AST
- **THEN** truth 要求 failed 而非 AST-only，不把恢复节点计入候选准确率

### Requirement: Add mutex conservatism regressions without adopting invalid archived truth

语料 SHALL 包含最小化、人工复核的 C pthread mutex 正反例和 C++ unknown RAII 回归。归档 `memory-model-ir-checker/samples` 只作为来源/外部观察；Windows、不可编译、超出 capability 或未经复核 case MUST 被标为 excluded/unsupported，不进入 TP/FP/FN 分母。

#### Scenario: Direct C mutex protects accesses

- **WHEN** C11/C17 producer 与 consumer 使用受支持的同一 pthread mutex 且证据完整
- **THEN** 不产生无同步风险，并断言没有 unknown RAII gap 取代已支持 C mutex

#### Scenario: C accesses have no synchronization

- **WHEN** 等价 C pthread 线程对同一普通对象冲突访问且没有同步或相关未知 gap
- **THEN** 在现有支持规则满足时保留正式风险期望，而不是因新增降级协议一律 abstain

#### Scenario: Archived Windows case is discovered

- **WHEN** 外部回归枚举到 Windows/MSVC API 或相应无效源码
- **THEN** 记录 excluded 及原因，不尝试 AST 兜底、工具链适配或准确率评价
