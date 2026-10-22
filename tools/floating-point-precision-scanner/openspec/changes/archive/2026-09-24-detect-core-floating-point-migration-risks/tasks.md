## 1. 协议、版本与领域模型

- [x] 1.1 盘点现有 request/result、facts、profile、evidence 和 version schema 的兼容基线，记录本 change 需要提升的次版本及旧 facts-only 请求/结果 fixtures。
- [x] 1.2 扩展 scan request schema 与不可变模型，支持默认规则集合、稳定 code 子集、显式空规则集合和可选规则版本约束，并对未知、重复冲突或不支持规则做聚合校验。
- [x] 1.3 扩展 scan result schema 与模型，增加 registry digest、规则版本、逐状态 assessment 分母、typed evidence refs、双语 impact/suggestion/test suggestion 和规则聚合元数据。
- [x] 1.4 定义 `RuleDescriptor`、`RuleContext`、`RuleAssessment`、assessment 状态、稳定 scope/frontier 和 finding 候选领域类型，确保规则层不接收 Clang/LLVM 原始对象。
- [x] 1.5 更新 version 输出、schema registry、兼容矩阵和 example 文档，明确默认四规则、显式 facts-only 以及旧消费者不得静默忽略的新字段。
- [x] 1.6 为 request/result/version 的有效默认、子集、空集合、未知规则、版本冲突、未知字段和双语字段补齐 schema/contract 单元测试。

## 2. Canonical facts 与 profile 输入

- [x] 2.1 扩展 AST canonical facts schema/model，表达 `long double` 精确类型属性、linkage/visibility/语言链接、参数/返回/变参、记录字段和持久化或二进制边界。
- [x] 2.2 扩展 AST facts mapper，识别乘加/乘减候选、连续浮点运算链及赋值、volatile、显式 cast 等存储舍入边界，并保留宏 spelling/expansion provenance。
- [x] 2.3 实现按 Clang 21.1.8 命令行覆盖顺序计算的有效浮点语义选项，至少覆盖 fast-math/Ofast 展开、否定覆盖、excess precision、FP contract、errno 和异常相关选项。
- [x] 2.4 扩展 x86_64/RISC-V profile schema、内置数据和比较视图，提供 long-double 格式/存储/精度/对齐/ABI/变参、x87/FLT_EVAL_METHOD/evaluation 和 FMA contraction 必需字段及字段级来源。
- [x] 2.5 为新增 AST facts 和 profile 字段实现 canonical serialization、稳定 ID/digest、unknown/unsupported 记录和跨字段一致性校验。
- [x] 2.6 为 C11/C17/C++17/C++20 的公开 ABI、`extern "C"`、变参、记录布局、局部 long double、乘加、volatile/cast、宏位置和选项覆盖补齐正常、边界与异常路径单元 fixtures。
- [x] 2.7 为完整 profile、字段 unknown、来源缺失、矛盾 long-double/evaluation/contraction 配置和跨目录稳定指纹补齐单元测试。

## 3. Rule registry、assessment 与确定性基础设施

- [x] 3.1 实现只注册 `long-double-abi`、`x87-excess-precision`、`fma-contraction`、`unsafe-fp-optimization` 的版本化 registry、默认启用集合、依赖声明和稳定执行顺序。
- [x] 3.2 实现规则配置归一化和 registry digest，保证同义配置得到相同语义摘要，未实现 roadmap 规则返回双语 `rules_not_available`。
- [x] 3.3 实现逐 rule/scope assessment pipeline，严格区分 `matched`、`not_matched`、`unknown`、`skipped` 和 `failed`，并限制只有 matched 生成 finding。
- [x] 3.4 实现 assessment/finding 稳定身份、显式排序键和 typed evidence ref 校验，使绝对路径、artifact root、展示文本、进程和并发顺序不影响语义身份。
- [x] 3.5 实现规则特定 aggregation key、有界 related locations、稳定主位置和受影响总数，避免跨 TU 配置风险重复报告。
- [x] 3.6 实现总 assessment、单规则候选、证据引用、聚合位置、诊断和 wall/CPU 预算，按稳定候选顺序截断并记录 frontier。
- [x] 3.7 实现逐规则异常隔离、不可隔离 registry/identity/schema 错误升级和默认脱敏诊断。
- [x] 3.8 为 registry、选择/拒绝、状态转换、身份/乱序重放、聚合、预算截断、异常隔离和脱敏补齐正常、边界与异常路径单元测试。

## 4. `long-double-abi` 规则

- [x] 4.1 实现 source/target profile 的 long-double 格式、storage bits、precision、alignment、ABI class、calling convention 和 variadic 语义比较器，并保留字段级 provenance。
- [x] 4.2 实现公开函数参数/返回、`extern "C"`、变参、外部可见记录字段及持久化/二进制边界候选识别，排除纯局部计算。
- [x] 4.3 实现 `long-double-abi` matched/not_matched/unknown assessment、high 严重性、人工确认、双语影响/建议和 ABI/序列化测试建议。
- [x] 4.4 为 C/C++ 公开边界命中、相同 ABI 不命中、局部变量不命中、嵌套记录、typedef/模板、变参、字段 unknown 和 provenance 缺失补齐单元测试。

## 5. `x87-excess-precision` 规则

- [x] 5.1 实现 evaluation method、x87 extended precision、`FLT_EVAL_METHOD`、excess-precision 选项和目标求值策略比较器。
- [x] 5.2 实现 AST 运算链与存储舍入边界分析，并用 verified IR 中间类型、`fpext`/`fptrunc` 和 evidence binding 核对实际范围。
- [x] 5.3 实现 `x87-excess-precision` matched/not_matched/unknown assessment、双语一次/二次舍入说明、人工确认和边界值差分测试建议。
- [x] 5.4 为扩展中间精度命中、每步存储/截断不命中、volatile/cast 边界、标准精度选项、缺少 IR、ambiguous binding、profile unknown 和多运算链补齐单元测试。

## 6. `fma-contraction` 规则

- [x] 6.1 实现 AST 乘加/乘减候选与显式 `fma`/`std::fma` 分类，保留 operand、类型、位置和表达式关系的稳定引用。
- [x] 6.2 实现 source-preserving/build-faithful IR 中 `fmul`+`fadd/fsub`、`llvm.fma`、constrained FMA、优化删除和一对多/多对一 evidence 的规范化比较。
- [x] 6.3 实现 source/target contraction policy、有效选项和实际 lowering 的联合判断，以及 `fma-contraction` matched/not_matched/unknown finding 与双语测试建议。
- [x] 6.4 为隐式融合命中、融合展开命中、两端一致不命中、显式 FMA 不误报、build-faithful 缺失、debug 缺失、ambiguous binding、宏/内联和多候选预算补齐单元测试。

## 7. `unsafe-fp-optimization` 规则

- [x] 7.1 实现 effective option semantics 到 reassociation、no-NaNs、no-Infs、no-signed-zeros、reciprocal/approximate functions、finite-math-only、contract、errno 和异常语义的规范化映射。
- [x] 7.2 实现 AST option facts 与 build-faithful IR fast-math flags 的范围核对、冲突分类和 evidence refs，避免用原始 token 直接下结论。
- [x] 7.3 实现 TU/共享配置级 `unsafe-fp-optimization` 聚合、matched/not_matched/unknown assessment、双语语义影响和针对 NaN/Inf/±0/边界输入的测试建议。
- [x] 7.4 为 `-ffast-math`、`-Ofast`、单独子选项、后续否定覆盖、全部关闭、单指令 IR flag、AST/IR 冲突、多 TU 聚合和 related-location 截断补齐单元测试。

## 8. 应用编排、状态与输出

- [x] 8.1 将 application pipeline 接入 registry 和四条规则，在 facts/evidence 校验后构建不可变 RuleContext，并保留显式空规则集合的 facts-only 路径。
- [x] 8.2 实现按启用规则依赖决定 AST-only、source-preserving 和 build-faithful IR 的规划，不请求无关 profile，也不让未请求能力缺失降低状态。
- [x] 8.3 实现 facts/evidence/assessment/finding 多层 planned/completed/matched/not_matched/unknown/skipped/failed 分母和 complete/partial/failed/internal_error 聚合。
- [x] 8.4 将规则 findings、unknowns 和 diagnostics 接入现有确定性排序及原子输出，保证 finding 数量或严重性不改变固定退出码。
- [x] 8.5 更新 CLI `scan`/`validate-request`/`version`、README、共享 BC 运维说明、示例请求/结果和 roadmap 状态说明。
- [x] 8.6 为默认四规则、显式子集、facts-only、AST-only、AST+IR、单规则失败、全部规则不可评估、发现 high finding 仍退出 0、原子写失败和重复扫描补齐应用/CLI 单元测试。

## 9. 集成、质量与验收

- [x] 9.1 增加锁定 Clang/LLVM 21.1.8 的 C/C++ fixtures，覆盖 long-double ABI、x87 求值/存储、FMA 融合/展开和 fast-math flags 的真实 AST→IR→evidence→finding 链路。
- [x] 9.2 增加 schema/example contract tests、确定性跨目录/乱序/并发重放测试以及损坏/缺失/不兼容 facts、evidence、profile 和规则版本的失败测试。
- [x] 9.3 运行格式化、lint、typecheck、schema/example 校验、Python/C++ 单元测试和锁定工具链集成测试；集成测试不得替代任一规则的单元测试。
- [x] 9.4 以 source-inclusive 配置统计全部项目自有 Python/C++ 可执行源码，明确仅排除第三方依赖、自动生成文件、构建目录和覆盖率输出；确认未被测试加载的源码仍计入分母。
- [x] 9.5 生成并保存项目整体及受影响模块的 line/branch coverage 报告，二者均须至少 90%；任何指标不足或测试失败时保持质量任务未完成。
- [x] 9.6 编写中文验收报告，记录命令、测试数量与结果、line/branch 百分比、统计范围、排除理由、HTML/XML 报告位置、锁定 toolchain 版本和已知限制。
- [x] 9.7 执行 `openspec validate detect-core-floating-point-migration-risks --strict --no-interactive` 和仓库 diff/格式检查；仅在全部任务、测试与双覆盖率门禁通过后才允许 sync/archive。
