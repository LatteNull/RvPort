## ADDED Requirements

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
