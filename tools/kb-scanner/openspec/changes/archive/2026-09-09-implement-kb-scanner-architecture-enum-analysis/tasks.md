## 1. 冻结缺口基线与逐模块测试门禁

- [x] 1.1 记录现有 `cpp_x86_constexpr_arch_branch` 在默认 Schema V2 下为 0 Finding、产生 2 个 normalization unsupported Evidence 诊断的基线，并冻结对应源码位置、旧 V1 rule identity、AVX 结果和两份 compiler fact SHA-256。
- [x] 1.2 建立 architecture-enum 机器可读 test inventory，将本 change 新增或实质修改的 frontend vocabulary/Tree-sitter/Clang、Normalizer、detector definitions/matcher/local detector、graph analyzer、classifier 和 V1/V2 projection 模块分别映射到隔离 unit suite 及适用高层测试。
- [x] 1.3 扩展 `tests/run_container_tests.py` 增加独立 architecture-enum unit gate，拒绝漏映射、模块无 executed lines、只由 component/E2E 间接覆盖，以及任一模块低于 90% line / 80% branch。
- [x] 1.4 建立 C/C++ enum 行为矩阵和 fixtures，覆盖 scoped/unscoped、initializer、qualified/unqualified、if/if constexpr、switch/case、RISC-V/generic sibling、跨文件、歧义、parser recovery、注释/字符串/变量和 near-miss。

## 2. 提取有界 enum 与 selection Evidence

- [x] 2.1 扩展 C/C++ Evidence vocabulary，加入 enum declaration、member declaration 和 member reference，定义稳定 identity、metadata、binding status 与排序合同，不增加全 identifier Evidence。
- [x] 2.2 在 Tree-sitter adapter 中两阶段提取 C/C++ enum/member，并为同文件唯一限定/非限定使用建立 declaration reference；将 `constexpr_condition` 缩小到真实 condition value/token span。
- [x] 2.3 为 Tree-sitter enum 提取编写隔离单元测试，覆盖 C/C++ AST 节点、精确 span、同文件唯一绑定、重名歧义、switch/case context、错误恢复、顺序稳定和普通 identifier/comment/string 零 Evidence。
- [x] 2.4 扩展 Clang adapter，使用 `ENUM_DECL`、`ENUM_CONSTANT_DECL` 和引用到 enum constant 的 `DECL_REF_EXPR` 产生带 compilation context 的语义 Evidence，同时保留 Tree-sitter 降级路径。
- [x] 2.5 为 Clang enum enrichment 编写 fake cursor 单元测试，覆盖声明、成员、跨文件引用、workspace 外位置、TU error、缺失 referenced cursor、重复 producer 和 translation-unit 不保留。
- [x] 2.6 更新 Frontend composition/deduplication 测试，证明 Tree-sitter 与 Clang 对同一 member 可保留独立 provenance 而不覆盖不同 context/binding，并维持原 Frontend 状态传播。

## 3. 规范化并检测疑似架构枚举

- [x] 3.1 扩展 `CppEvidenceNormalizer`，将 enum declaration/member/reference 和 `constexpr_condition` 无损映射为稳定 facts，验证 declaration Evidence 引用并保留 qualified name、reference context、binding/completeness 和 compilation context。
- [x] 3.2 为 Normalizer 编写隔离单元测试，覆盖声明/引用 identity、多个 producer/context、complete/partial/ambiguous、悬空 declaration、非字符串/空值，以及不再产生 constexpr unsupported 诊断。
- [x] 3.3 实现 enum identifier component normalization，以完整 spelling、qualified member 末段、分隔符和 camel/digit 边界匹配，禁止任意 substring 与输入顺序影响结果。
- [x] 3.4 增加 enum member/reference DetectorDefinition 与 matcher，复用现有 `targetFeatures`、`architectureAliases`、适用 `platformMacros` KnowledgeEntry，并确保 knowledge-backed 或强 family token 结果初始仍为 candidate。
- [x] 3.5 为 definitions/matcher 编写隔离单元测试，覆盖 `avx2`、`BACKEND_AVX2`、`X86_AESNI`、qualified name、case variation、accepted knowledge provenance，以及 `avx2_counted`、普通 enum/type/变量和 deferred alias 负例。
- [x] 3.6 为 Local Detector 编写隔离单元测试，覆盖 enum candidate Observation 的 Evidence/Knowledge/binding metadata、同一事实多 provenance 去重、hint 隔离、未知/歧义保持和无 fake knowledge。

## 4. 建立枚举声明—引用—选择—依赖关系

- [x] 4.1 扩展 graph entity index，确定性建立 enum type、enum member 和 selection predicate Entity，并验证 declaration/reference/subject 类型与项目边界。
- [x] 4.2 在 Evidence Graph Analyzer 中使用 `defines`、`contains`、`selects` 和 `guarded_by` 连接 enum 声明、成员引用、if/constexpr/switch/case condition 与下游 call/type/include/asm Evidence。
- [x] 4.3 将 RISC-V、generic、portable、scalar member 仅作为 sibling/alternative role 纳入 proof，将 ARM member 仅作为上下文；禁止它们单独形成 x86 Finding。
- [x] 4.4 为 template-dependent condition 保留语法 guard 但将 selection 标为 unknown；对唯一 Clang/local binding 标 complete，对重名、缺失、动态表达式、类型冲突和 parser recovery 标 ambiguous/partial/unknown。
- [x] 4.5 为 enum graph 编写隔离单元测试，覆盖 complete chain、unknown template、switch sibling、inactive alternative、跨文件 Clang binding、歧义/缺失引用、循环、输入乱序和 depth/visited/path 截断。
- [x] 4.6 扩展 proof/graph component fixture，验证单个 enum 根因可以闭合到实际 x86 intrinsic/API/type/asm Evidence，且不存在源码读取、编译、模板实例化或项目命令副作用。

## 5. 保守分类 enum candidate

- [x] 5.1 扩展 ClassificationPolicy，使孤立 enum candidate 为 unknown/non-actionable，完整 guarded x86 dependency 且目标未知为 actionable non-blocking，RISC-V selected 为 blocking，RISC-V excluded/compatible sibling 为 guarded inactive。
- [x] 5.2 让 incomplete/ambiguous/dynamic/truncated enum relation 保持 unknown，并使 Assessor 将未决 enum selection 计入 provisional/unknown completeness，禁止从零 blocker 推断 ready。
- [x] 5.3 为 Classifier 编写隔离单元测试，覆盖孤立名称、真实下游 x86 dependency、selected、inactive、compatible sibling、ARM context、冲突与 proof 不完整的完整决策矩阵。
- [x] 5.4 为 Assessor/分类集成编写隔离单元测试，验证 enum unknown 单调降低 readiness、guarded 不成为 blocker、selected 成为 blocking dimension，并保持静态范围声明。

## 6. 投影自包含 V2 链路并保护 V1

- [x] 6.1 扩展 V2 Finding mapper，将 enum 根因投影为已有 `architecture_probe` fact，并以 occurrences 无损保留 declaration/reference/condition 位置和确定性 primary occurrence。
- [x] 6.2 扩展 V2 chain builder，将 enum declaration/member/reference/condition/downstream/knowledge/classification/assessment 投影为已有 `source_evidence` 与既有 edge kinds，并写入 `org.rvport.kb-scanner.architecture-enum` extension。
- [x] 6.3 为 V2 mapper/chain/context/validator 编写隔离单元测试，覆盖完整、partial、ambiguous、inactive、unknown、多 occurrence、每 step 独立源码上下文、合法 extension 和所有引用失败。
- [x] 6.4 更新 JSON/HTML/log renderer 测试，证明三个 artifact 从同一 V2 model 展示 enum 链路、代码上下文、break 和 Diagnostic，且 renderer 不重新匹配或分类。
- [x] 6.5 扩展显式 V1 ProjectionPolicy/mapper：if constexpr 枚举分支使用 `CPP.X86.CONSTEXPR_ARCH_BRANCH`，其他枚举候选使用稳定 `C_CPP.X86.ARCH_ENUM_CANDIDATE`，并保持 Schema 1.0 顶层和必需 Finding 字段。
- [x] 6.6 为 V1/V2 version selector 与 projection 编写隔离回归，覆盖默认/显式 V2、显式 V1、单 projector、失败不回退、固定 artifact、原子发布及非枚举结果不漂移。

## 7. 容器验收、文档与 OpenSpec 校验

- [x] 7.1 在 `kb-scanner-test` 容器中运行 architecture-enum 逐模块 90% line / 80% branch 门禁，确认 inventory 中每个实质修改业务模块均由隔离 unit suite 直接执行。
- [x] 7.2 使用生产默认 V2 扫描 C/C++ enum 行为矩阵，逐字段核对 Evidence、facts、Knowledge、Relations、Classification、Finding occurrences、primaryPath、steps/edges/breaks 和源码上下文。
- [x] 7.3 验证既有 constexpr fixture 从 0 Finding 恢复为可追溯结果、两个 unsupported 诊断消失；同时验证普通 enum/identifier/comment/string 不产生 architecture enum Finding。
- [x] 7.4 运行显式 V1 consumer contract，确认 `CPP.X86.CONSTEXPR_ARCH_BRANCH`、Schema 1.0 顶层字段、summary 计数单位、Diagnostic、三个 artifact 和退出码语义保持兼容。
- [x] 7.5 运行 AVX、compiler facts、knowledge、evidence graph、classification、Schema V2、无副作用与完整回归，确认非枚举结果没有未解释漂移，并在结束后关闭独立测试容器。
- [x] 7.6 验证 `clang-x86-entries.json` 与 `gcc-x86-entries.json` 的 bytes/SHA-256、category、source identity 和加载路径未变化，且没有引入 Legacy/YAML runtime、宿主机依赖、生产镜像或 backend 修改。
- [x] 7.7 更新 Frontend/knowledge/graph/classification/Schema V2 文档与行为矩阵，说明 enum candidate、关系升级条件、known limitations、V1 兼容和静态范围。
- [x] 7.8 运行 `openspec validate implement-kb-scanner-architecture-enum-analysis --strict`，确认 proposal/design/spec/tasks、测试 inventory 与实现验收一致。
