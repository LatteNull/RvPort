# analysis-validation-corpus

## Purpose

定义可离线复现、带人工真值且版本化的 C/C++ 分析验证语料和真实工程输入，使准确性与完整性评估具有稳定分母和可审计来源。

## Requirements

### Requirement: Define strict versioned validation suites and truth annotations

系统 SHALL 为 `ValidationSuiteManifest` 与 `TruthAnnotation` 提供严格 v1 schema，记录 suite/case 身份、source/IR hash、物理 TU、语言标准、编译器与版本、target/layout、优化/debug 配置、显式 scope、适用模型、人工审阅依据和期望。未知字段、未来版本、重复 case、悬空注解或 digest 不一致 MUST 被拒绝，不得用当前分析输出补齐 truth。

#### Scenario: A truth annotation matches its exact input profile

- **WHEN** case 的源码、编译配置、scope 和 truth digest 与 suite 清单一致
- **THEN** runner 接受该注解并登记完整来源和审阅身份

#### Scenario: A source changes without truth review

- **WHEN** 源码、编译命令、语言标准或 scope 任一 digest 改变而 truth 仍引用旧身份
- **THEN** runner 拒绝该 case，不把旧期望套用到新输入

### Requirement: Provide an offline C and C++ semantic matrix

项目 SHALL 提供无需网络、SSH、DevKit 或外部后端的 C11/C17/C++17/C++20 固定语料，覆盖单 TU、至少三个物理 TU、正确发布、已支持风险及 unknown/unsupported；每个 case SHALL 声明 required/forbidden finding code、允许的 verdict/完整性、关键对象/线程/证据关系和预期退出语义。

#### Scenario: The complete fixed suite runs in the development image

- **WHEN** 在独立开发容器离线执行全部固定 case
- **THEN** 四种语言 profile、单/跨 TU、正确/风险/unknown 类别都有明确分母和可验证期望，且不运行目标程序或原生链接

#### Scenario: An unsupported pattern is intentional

- **WHEN** case 使用首版未支持的 fence、RMW/release sequence、`std::thread` 或多写者边界
- **THEN** truth 要求明确 unknown/unsupported 及原因，不把缺少 finding 记为正确安全结论

### Requirement: Keep truth independent from analyzer and backend observations

truth SHALL 来自明确的 C/C++ 语义依据与人工核对，保存 reviewer、方法、日期和解释；当前 P4、GenMC、herdtools7、DevKit、编译成功或运行频率只能作为 observation。系统 MUST NOT 以多数工具一致、零 finding 或历史 success 自动批准或修改 truth。

#### Scenario: All tools agree with a stale expectation

- **WHEN** 多个工具输出相同结果但 source/profile hash 或人工依据已失效
- **THEN** truth 状态仍为 invalid/pending-review，不能因工具一致而继续计入准确率

#### Scenario: A backend disagrees with reviewed truth

- **WHEN** 外部后端结果与已审核 truth 不一致
- **THEN** 保存差异、输入映射和限制供复核，不自动覆盖任一方

### Requirement: Pin one auditable real CMake project profile

实施 SHALL 选择恰好一个许可允许、上游 URL 与不可变 revision 可追溯、源树 hash 可验证、使用 CMake 且适合 GCC/Clang 的真实 C/C++ 工程。profile SHALL 保存许可证、必要未修改源码快照、预生成 `compile_commands.json`、路径重映射、显式 scope、roots、纳入/排除规则、已知生成物和选择偏差；runner MUST NOT 下载源码或执行 CMake/configure/build/install/目标程序。

#### Scenario: A candidate project passes the audit gate

- **WHEN** 候选的许可证、revision、源树、编译数据库、scope 和离线预算均完成审核
- **THEN** 固定其 profile 和 hash，并只对该不可变输入发布规模基线

#### Scenario: The candidate cannot be reproduced offline

- **WHEN** 候选依赖缺失生成文件、动态下载、不可提交许可证或无法闭合编译输入
- **THEN** 审核失败且真实工程任务保持未完成，不能临时忽略缺失项或把部分快照标成完整项目

### Requirement: Validate compilation database and explicit scope separately

真实工程清单 SHALL 分别校验原始编译记录、去重计划 TU、路径根、依赖存在性、配置身份和显式 scope 成员；`compile_commands.json` MUST NOT 被解释为完整 target/link 图。跨 TU 关联只使用现有 scope 规则，缺失/歧义成员必须留在计划分母。

#### Scenario: A compile record exists outside the selected scope

- **WHEN** 编译数据库包含合法 TU 但显式 scope 未纳入该成员
- **THEN** runner 记录 input 与 scope 分母差异，不擅自扩大分析范围

#### Scenario: A scoped translation unit is unavailable

- **WHEN** scope 引用的源码、头依赖或编译配置在快照中缺失
- **THEN** 该 TU 记为 failed/partial 并保留原因，不从完成率分母删除

### Requirement: Version corpus changes without rewriting historical evidence

新增、修改或删除 case、truth、真实项目 revision、编译 profile 或 scope SHALL 产生新的 suite/profile identity；历史清单、运行报告和裁决 SHALL 保持可读取且不被覆盖。相同输入的枚举、排序和 semantic digest MUST 确定。

#### Scenario: A case expectation is corrected

- **WHEN** 人工复核修正某 case 的预期 finding 或 unknown 原因
- **THEN** 新 suite version 保存理由和新 digest，旧运行继续引用旧 truth，不进行原地改写

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

+### Requirement: Validate degraded analysis independently for four language profiles

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

### Requirement: Maintain an offline C++ thread lifecycle truth corpus

项目 SHALL 建立带人工裁决的 C++17/C++20 单 TU 与物理跨 TU 生命周期语料，覆盖锁定 libstdc++/libc++ profile、自由函数、lambda、成员函数、简单 functor、move、join、detach、joinable、析构、构造失败/异常、无 debug、开放 scope、profile/ABI mismatch、递归/循环和预算。truth SHALL 分别声明预期 callable、对象 lineage、ThreadContext、ThreadInstance、生命周期关系和 unknown 原因，不以编译成功、执行频率或外部工具作为 oracle。

#### Scenario: A joined lambda case is reviewed
- **WHEN** 人工 truth 指定唯一 lambda callback、一个动态实例和条件化 join relation
- **THEN** 验证器逐项比较身份、关系、guard、证据与完整性，而非只检查命令退出零

#### Scenario: A detached member-function case is reviewed
- **WHEN** truth 预期对象/成员 callback 可绑定但 detach 后仍可能并行
- **THEN** 断言存在 detach、没有 join-complete/not-parallel，并保存 receiver provenance

### Requirement: Preserve independent C pthread regression denominators

A3 语料 SHALL 持续运行 C11/C17 直接 `pthread_create`/`pthread_join` 正反与 unknown 基线，并将 C11、C17、C++17、C++20 的 planned/completed/failed/unknown 分母分别报告。C 夹具不得加载 C++ 标准库模型，C++ 新能力不得被用于补全 C 路径。

#### Scenario: C++ lifecycle cases pass while a C baseline regresses
- **WHEN** C++17/C++20 A3 truth 全部匹配但任一 C11/C17 pthread 基线身份或关系改变
- **THEN** required semantic gate 失败，不以合并分母或 C++ 结果掩盖回归

### Requirement: Add independent four-language mutex and RAII truth sets

离线语料 SHALL 分别为 C11、C17、C++17、C++20 定义 planned、eligible、expected mode、mutex/owner/thread identity、proof/unknown 及风险结果。C SHALL 覆盖直接 pthread lock/unlock、跨 TU wrapper、全局和 struct/union 字段、相同/不同 mutex、未知 kind 与无锁反例；C++ SHALL 覆盖 `mutex`、`lock_guard`、受限 `unique_lock/scoped_lock`、move、异常、字段、跨 TU、no-debug、开放 scope、profile mismatch 和预算。

#### Scenario: C++ cases pass while C regresses
- **WHEN** C++17/C++20 A4 truth 全部匹配但 C11 或 C17 直接 pthread mutex identity/proof 改变
- **THEN** required semantic gate 失败，不以合并分母或 C++ 新能力掩盖 C 回归

#### Scenario: An unsupported ownership form is present
- **WHEN** fixture 使用 try/timed/recursive/robust mutex、未闭合 adopt/release 或通用指针别名
- **THEN** truth 明确要求 unknown/unsupported，不将其放入支持范围 risk/discharged 分母

### Requirement: Lock and review the archived mutex regression locally

项目 SHALL 保存 `memory-model-ir-checker/samples/safe/03_pthread_mutex.cpp` 的本地最小副本、来源路径、内容 hash、人工 truth 和 capability 声明；日常测试 MUST NOT 读取 sibling archive。只有 A4 完整证据链成立时才期望受限消解，历史工具输出不得作为 oracle。

#### Scenario: Local fixture hash changes
- **WHEN** 本地副本内容与记录 hash 或人工 truth 版本不一致
- **THEN** 验收失败并要求重新审核，不静默接受新的安全期望

### Requirement: Validate required standard-library profiles with real compilation

C++ truth SHALL 至少用锁定开发镜像实际编译一个 libstdc++ 和一个 libc++ profile，并执行 source/IR 提取、binding、A4 图和结果断言。合成 schema 数据 MAY 用于单元错误路径，但 MUST NOT 计入 runtime support 或 required truth 分母。

#### Scenario: A vendor fixture cannot compile
- **WHEN** required vendor/profile 因环境缺失无法真实编译和提取
- **THEN** 对应 profile 标记未完成且 required gate 失败，不用另一 vendor 或合成 fixture 替代
