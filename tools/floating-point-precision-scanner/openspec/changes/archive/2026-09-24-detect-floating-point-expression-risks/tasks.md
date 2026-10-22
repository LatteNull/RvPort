## 1. 协议版本与领域模型

- [x] 1.1 新增 scan request/result 1.3、canonical facts 1.3、LLVM facts 1.1、evidence 1.1 和 `FloatingPointBuildContext` 1.0 schema/版本常量，保留 1.0-1.2 请求的四规则默认语义并补兼容性单元测试。
- [x] 1.2 扩展纯数据领域模型，加入表达式/use refs、函数摘要、build-context fingerprints、`evidence_origin`、structured `validation_plan` 和 suppression audit records，并测试 canonical serialization、未知字段拒绝和双语必填路径。
- [x] 1.3 演进 result metadata/summary/analysis scope，支持十规则 registry 依赖、suppressed 分母和各层计数一致性；补齐完整、partial、facts-only、旧版本结果契约测试。
- [x] 1.4 更新 CLI `version` 与 request validation，公开全部新 schema/analysis 版本并覆盖不兼容主版本、版本缺失、规则版本冲突和 build-context 冲突异常路径。

## 2. C/C++ canonical expression facts

- [x] 2.1 扩展 Clang AST fixture/helper 输出及 Python mapper，记录转换 source/destination type、implicit/explicit、cast kind、常量规范值/可表示性、整数位宽/符号和 storage/use 边界；覆盖 C11/C17、C++17/C++20、`auto`、显式 cast、模板及失败恢复。
- [x] 2.2 增加 comparison facts 的 operand provenance、零/常量/epsilon 形态、NaN/Inf guard 和 branch/loop/assert use links；覆盖同一行多表达式、宏 spelling/expansion、短路条件和 unsupported use。
- [x] 2.3 增加 loop/algorithm/reduction facts，表达 accumulator recurrence、sum/product/dot-product、循环范围、并行/向量提示和受支持 Kahan/Neumaier 补偿形态；覆盖单元素、固定小表达式、嵌套循环和歧义递推。
- [x] 2.4 增加 fenv pragma/API actions、函数直接调用边和 `reads/changes/tests/restores/unknown` 环境摘要；实现有界、确定的直接调用传播并覆盖递归、函数指针、虚调用、外部调用与线程入口边界。
- [x] 2.5 增加 resolved declaration、namespace、builtin/intrinsic ID、definition header、target features、模板实例、active preprocessor guard 和数学调用参数域线索 facts；测试名称相同但声明不同、条件编译、宏/模板及未知参数域。
- [x] 2.6 更新 facts schema/golden fixtures、稳定 ID、排序、digest 和 unknown/frontier 测试，证明临时目录、locale、遍历顺序和并发顺序不影响输出。

## 3. LLVM BC facts 与 AST↔IR evidence

- [x] 3.1 扩展锁定 LLVM 21.1.8 worker 协议和 C++ extractor，输出 conversion/comparison operand-use links、branch/select uses、phi recurrence、scalar/vector reduction groups、constrained FP/fenv calls 和函数摘要。
- [x] 3.2 为 LLVM use-chain、phi candidates、调用摘要深度和输出大小实现独立预算、稳定候选排序与 frontier；覆盖预算恰好命中、超限、递归、无 debug info 和 unsupported intrinsic。
- [x] 3.3 更新 LLVM facts schema、Python reader 和 golden BC/JSON fixtures，覆盖 `fptrunc/fpext/sitofp/uitofp`、`fcmp`、phi、`llvm.vector.reduce.*`、reassoc flags 和 external libm call。
- [x] 3.4 扩展 evidence binder，建立 conversion-lowering、comparison-use、environment-call、reduction-lowering、math-call 和 architecture-api 多对多关系，并测试 explicit sidecar、唯一 derived binding、优化删除和内联链。
- [x] 3.5 实现新关系的 ambiguity/unknown 传播，覆盖同行多候选、宏 spelling/expansion 冲突、模板实例、缺失列/inline provenance、digest 冲突和绑定预算耗尽。
- [x] 3.6 为 C++ worker 和 Python evidence 层补充稳定身份、排序、摘要和版本兼容单元测试，确保名称/源码文本相似度不会单独产生 exact/strong binding。

## 4. Build context 与 profile 比较

- [x] 4.1 实现 `FloatingPointBuildContext` loader/validator、source/target 独立绑定、base-profile fingerprint 校验和不含绝对 sysroot/materialization 路径的稳定 context fingerprint。
- [x] 4.2 建模 libm implementation/version、errno、exception、special-value、environment/thread-local 和 target-feature capability 的 known/unknown/provenance 视图，不从宿主或 target triple 自动补值。
- [x] 4.3 增加经过来源校验的最小 build-context fixtures；若锁定环境没有可靠 libm 元数据，则只交付 unknown fixtures 和保守诊断，不伪造 glibc/musl/vendor 能力。
- [x] 4.4 覆盖同一架构绑定不同 libm、overlay/profile/ABI 冲突、缺少来源、无关字段 unknown 和序列化重现性单元测试。

## 5. Registry、运行时与公共 finding pipeline

- [x] 5.1 将 `RuleDescriptor` 扩展为声明 source/IR fact kinds、profile/build-context fields、IR capability、assessment scope、evidence mode、default-enabled、预算键和稳定 order，并更新 registry digest/选择/版本冲突测试。
- [x] 5.2 注册六条 1.0 新规则，使 schema 1.3 默认集合为十条、旧 schema 默认集合保持四条、显式子集/空集合保持兼容；更新 `rules_not_available` 双语诊断测试。
- [x] 5.3 扩展 `RuleContext`/assessment pipeline 以提供 facts graph、函数摘要、build contexts 和每规则依赖检查；保证无关 unknown 不阻断、决定性缺失产生 unknown、可隔离异常产生 failed。
- [x] 5.4 实现公共 deterministic/heuristic finding builder、severity/confidence/人工确认约束和结构化 validation plan，测试 heuristic 永不覆盖 deterministic、业务阈值保持 unknown/project-policy/user-provided。
- [x] 5.5 扩展稳定 finding/assessment ID、跨 TU 聚合和确定性排序，使适用 build-context fingerprints/evidence origin 参与语义身份而双语文案、绝对路径与 suppression 理由不参与。

## 6. Floating environment 规则

- [x] 6.1 实现 `floating-environment` 候选与 assessment，结合 pragma、fenv actions、effective options、profile capabilities、constrained FP/IR behavior 和有界函数摘要。
- [x] 6.2 覆盖动态 rounding 与优化假设冲突、异常标志读取/清除、完整保存恢复、pragma 作用域、线程边界、间接/外部调用、AST↔IR 冲突和缺失 profile 的正常/边界/unknown/failed 测试。
- [x] 6.3 提供该规则稳定中英文 finding/diagnostic 模板及 validation plan，包含 rounding modes、exceptions、特殊值、优化级别和跨平台重复策略。

## 7. Mixed precision 与架构 API 规则

- [x] 7.1 实现整数/浮点常量精确可表示性和 precision/range 比较工具，覆盖 signed/unsigned 边界、零、次正规、溢出、NaN/Inf 常量、十六进制浮点字面量和不可恢复值域。
- [x] 7.2 实现 `mixed-precision-conversion`，覆盖隐式窄化、整数转浮点、usual arithmetic conversions、后续存储边界、精确常量、显式 cast、`auto`、宏/模板和类型 unknown。
- [x] 7.3 实现 `architecture-specific-fp-api`，仅依据 resolved declaration/builtin/intrinsic、header、target feature 与 active guard 命中，并支持项目配置的可验证 portable-wrapper 语义。
- [x] 7.4 覆盖无保护 x86 intrinsic、向量数学 API、x86/RISC-V 条件分支、可移植 wrapper、泄露架构类型、名称碰撞、死/未知分支和宏 provenance 歧义测试。
- [x] 7.5 为两条规则补齐双语 finding/diagnostic、替代调查/精度损失说明与 input classes/error metrics/threshold source/repeat strategy 验证计划测试。

## 8. Comparison 与 reduction 规则

- [x] 8.1 实现 `fragile-fp-comparison` 的 deterministic NaN 错误模式和 heuristic 精确比较/epsilon 模式，结合 operand origin、guard 与控制流用途，不自动生成业务 epsilon。
- [x] 8.2 覆盖计算值精确相等、同源值、零比较、`x == NAN`/`x != NAN`、标准分类 API、绝对/相对 epsilon 近零边界、领域 helper、unknown use 和 suppression 测试。
- [x] 8.3 实现 `reduction-reassociation` 的 AST recurrence 分类、补偿算法排除和 AST↔IR reduction/reassoc 对比；仅 AST 候选保持 heuristic，可靠 build-faithful 差异按证据强度评估。
- [x] 8.4 覆盖 sum/product/dot-product、并行/向量归约、固定小表达式、单元素、Kahan/Neumaier、fast-math 破坏补偿、phi 歧义、IR 缺失/冲突和预算 frontier 测试。
- [x] 8.5 为两条规则验证固定 rationale、medium/low confidence、强制人工确认、病态输入/顺序/ULP 或相对误差计划，以及未知业务阈值不被填值。

## 9. Math library variance 规则

- [x] 9.1 实现标准/受支持 vendor 数学声明分类和 `math-library-variance`，组合解析后调用、可证明参数域、source/target build-context capability 与 profile fingerprints。
- [x] 9.2 覆盖特殊值、极值、次正规、domain/range error、errno/exception 差异、精确函数/语义一致、vector math、名称碰撞、参数域 unknown 和 libm identity unknown。
- [x] 9.3 保证只有调用与已验证 context 差异共同支持 deterministic finding；缺少库身份返回 unknown，不能把每个 `sin`/`exp` 调用泛化为风险。
- [x] 9.4 增加中英文诊断和 validation plan 测试，覆盖 classification/ULP/errno/exceptions metrics、标准/profile 阈值来源和跨平台重复策略。

## 10. Suppression、聚合与输出

- [x] 10.1 实现 request suppression 校验与规范化，要求稳定 code、仓库相对 POSIX path pattern、可选行范围和非空理由，拒绝未知 code、越界、冲突和全规则通配。
- [x] 10.2 实现严格源码注释 `fp-precision-scanner: ignore <code> -- <reason>` 的提取与相邻范围绑定，保留 spelling/expansion/template provenance；歧义时诊断且不扩大抑制范围。
- [x] 10.3 在稳定 candidate ID 生成后应用 suppression，生成有界 audit records 和 `summary.suppressed`，确保 suppression 不改变其他 finding ID、assessment 或排序。
- [x] 10.4 更新 result schema、application aggregation、atomic output 和双语模板，覆盖无匹配、多匹配、宏/模板歧义、记录预算、序列化失败、原子替换失败及既有结果保留。

## 11. Fixtures、回归与确定性验证

- [x] 11.1 建立固定 C/C++ source/AST/BC/evidence/build-context truth fixtures 和六规则 matched/not-matched/unknown/suppressed golden results，记录生成器/Clang/LLVM 版本和摘要。
- [x] 11.2 增加 schema/contract tests，逐一拒绝缺少 evidence origin、人工确认、双语字段、validation-plan 字段、suppression reason、context fingerprint 或分母不一致的结果。
- [x] 11.3 增加旧 1.0-1.2 request/result、四规则 registry、现有 P3 finding IDs 和 facts-only 行为回归测试；不兼容语义变化必须通过新 schema/analysis/rule version 隔离。
- [x] 11.4 增加重复运行、翻译单元/BC/规则顺序打乱、不同绝对工作区/artifact root、locale 和并发顺序测试，验证 byte-stable semantic IDs、排序与 digests。
- [x] 11.5 运行锁定 Clang/LLVM 集成测试验证真实 AST/BC lowering；工具链不可用时记录明确阻塞，不得用编译成功或 mock 替代相应验收。

## 12. 质量门禁与交付文档

- [x] 12.1 运行 `ruff check src tests`、`mypy src` 以及全部 unit/contract tests，修复所有失败；集成测试不能替代任何项目自有代码的单元测试。
- [x] 12.2 使用 `coverage run -m pytest tests/unit tests/contract` 统计完整 `src/floating_point_precision_scanner`，生成 JSON/XML/HTML 报告，并用 `coverage_gate` 对项目整体及 facts、IR/evidence、profiles/build-context、rules、application/protocol/suppression 等受影响模块分别执行 line/branch ≥90% 门禁。
- [x] 12.3 使用锁定容器运行 `make cpp-coverage`，统计全部 `src/cpp` 项目源码并确保 C++ worker 整体及受影响文件 line/branch 均 ≥90%；仅排除第三方、生成文件和固定 fixtures，并记录理由。
- [x] 12.4 汇总 Python 与 C++ 项目自有源码的 line/branch 分母，确认项目整体两项均 ≥90%，且没有通过缩小 source、漏计未加载文件或无断言测试绕过门禁。
- [x] 12.5 更新 README、设计/roadmap 状态及 `docs/detect-floating-point-expression-risks-verification.md`，记录实际命令、测试数量、整体/受影响模块 line/branch、统计范围、排除项理由、报告位置和已知 unknown 边界。
- [x] 12.6 执行 `openspec validate detect-floating-point-expression-risks --strict --no-interactive` 和全部 schema/golden consistency checks；只有测试、覆盖率、文档和严格验证全部通过后才将任务标记完成并进入 sync/archive。
