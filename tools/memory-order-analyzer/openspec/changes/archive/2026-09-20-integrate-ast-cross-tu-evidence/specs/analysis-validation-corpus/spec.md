## ADDED Requirements

### Requirement: Version an AST and IR cross-TU truth matrix

验证语料 SHALL 新增独立 suite version，覆盖 C11/C17/C++17/C++20、GCC/Clang 编译记录、单 TU 和至少三个物理 TU、external/internal/static 同名、匿名 namespace、C tentative/common、inline/template/ODR、weak/COMDAT/TLS、宏/profile、debug/no-debug、跨 TU wrapper、pthread handle、路径映射、歧义和预算。每个 case SHALL 声明 source entity、definition resolution、AST–IR binding、canonical object、P3/P4 期望及 unknown/frontier。

#### Scenario: A cross-TU publication case has reviewed mappings

- **WHEN** case 的源码、profile、scope、source/IR digest 和人工注解一致
- **THEN** runner 可分别核对实体解析、绑定、候选与 finding，而不是只比较最终风险代码

#### Scenario: A compiler profile changes

- **WHEN** GCC/Clang 版本、宏、include、target、debug 或优化配置任一 digest 变化
- **THEN** 旧 truth 不适用并要求新 suite/profile identity，不原地更新期望

### Requirement: Compare IR-only and AST-assisted modes without rewriting truth

同一 eligible truth case SHALL 在固定预算下分别执行 IR-only 与 AST-assisted 模式，并保存各自产物、完整性、exact match、TP/FP/FN、strict recall 和 abstention。AST-assisted 结果、外部后端一致或预期改进 MUST NOT 自动修改人工 truth；unsupported fence/RMW/std::thread 等边界继续按原期望计入 unknown/frontier。

#### Scenario: AST-assisted mode resolves a former cross-TU abstention

- **WHEN** 新模式形成完整可审核证据链并匹配既有 truth
- **THEN** 报告记录该模式的增量命中与证据层变化，旧 IR-only observation 保持原样

#### Scenario: Both modes abstain on a fence case

- **WHEN** case 依赖本 change 明确不支持的 fence/RMW 语义
- **THEN** 两种模式均按 reviewed truth 记录 unsupported/abstention，不把 AST 可解析性当作语义支持

#### Scenario: Supported cross-TU regression cases are rerun after correction

- **WHEN** 修复后在同一 reviewed truth 和预算下重跑 `c11-risk-multi` 与 `cpp20-risk-multi`
- **THEN** AST-assisted 模式两个 case 均输出 risk，两者的 publication protocol 候选分母均非零，不新增 false positive，且 fence/CAS unsupported case 仍保持 unknown
