## Context

RvPort 的 US21 要求在 x86→RISC-V 迁移中识别浮点表示、舍入、编译优化和架构专用数学入口造成的数值差异。当前目录只有独立 OpenSpec 根，没有实现代码；因此本 change 的职责是固定首期边界、协议、失败语义和质量门禁，在 `docs/floating-point-precision-scanner-design.md` 形成可评审的总体设计，并以 `docs/floating-point-precision-scanner-roadmap.md` 固定后续独立 changes 的实施顺序。

设计仅面向 C 与 C++ 两种源语言，首期标准基线为 C11、C17、C++17 与 C++20，输入以真实编译数据库为主。静态扫描提供风险证据与对比测试建议，但不宣称证明两个架构的数值等价。

## Goals / Non-Goals

**Goals:**

- 定义 x86→RISC-V 浮点精度风险分类及稳定 finding code。
- 将扫描语言族固定为 `c` 和 `c++`；其他源语言不进入扫描计划。
- 定义可版本化、确定、双语且可审计的 JSON 输入输出契约。
- 区分 complete、partial、failed、invalid_request 与 internal_error，防止缺失分析被误报为安全。
- 给出分层架构，使编译上下文、语义事实、检测规则、证据和协议可独立测试。
- 固定正常、边界、异常路径的单元测试要求，以及整体和受影响模块行/分支覆盖率均至少 90% 的门禁。

**Non-Goals:**

- 本 change 不创建扫描器代码、CLI、schema、测试或构建配置。
- 不支持或推断非 C/C++ 源语言的浮点语义。
- 不运行 x86/RISC-V 二进制，不替代动态数值对比、性能基准或正式验证。
- 不自动修改源码、编译参数或容差阈值。
- 不保证所有数学库实现或任意输入域上的位级等价。
- 不将 AI 推断作为确定性结论；AI 仅是未来可选证据来源。

## Decisions

### 1. 以编译上下文驱动的 AST 作为首期事实源

首期设计使用 `compile_commands.json` 恢复 C/C++ 翻译单元的宏、包含路径、语言标准、目标和浮点选项，并通过 Clang 兼容前端生成类型化语义事实。规则只消费稳定的内部事实模型，不直接依赖前端节点对象；非 C/C++ 条目在规划阶段排除并产生可审计诊断。

选择该方案是因为文本匹配无法可靠区分类型、隐式转换、宏展开和生效编译选项；直接以 LLVM IR 为唯一输入又会丢失源码表达、宏、部分 ABI 意图和未被实例化的路径。未来可以补充 IR 或动态证据，但必须通过相同 evidence contract 合并。

### 2. 使用 profiles 显式描述源端与目标端浮点语义

请求必须指定 `source_profile` 与 `target_profile`。profile 至少描述目标三元组、数据布局、`long double` 格式与 ABI、FMA 能力/收缩策略、默认浮点求值方式、数学库标识和编译器浮点选项。规则比较两个 profile 后给出迁移风险，不能以宿主环境默认值代替任一端。

相比把“x86”和“RISC-V”写死在规则中，profile 可版本化、可测试，也能表达编译器、ABI 和数学库差异。同一架构的不同 toolchain 仍可能产生不同数值行为，因此架构名不能成为唯一判断依据。

### 3. finding code 稳定，证据与规则版本显式化

首期规则族包括：`long-double-abi`、`x87-excess-precision`、`fma-contraction`、`unsafe-fp-optimization`、`floating-environment`、`mixed-precision-conversion`、`fragile-fp-comparison`、`reduction-reassociation`、`math-library-variance` 和 `architecture-specific-fp-api`。finding 绑定源码范围、编译上下文、profile 差异、规则版本和测试建议。

稳定 code 供抑制、去重、趋势和下游迁移报告使用；展示文字可以演进，但 code 语义发生不兼容变化时必须提升规则主版本或发布新 code。

### 4. 风险报告与运行策略解耦

完整扫描即使发现高风险项也返回退出码 0；CLI 退出码只表示分析是否完整可用。是否因 `high` finding 阻断 CI，由独立策略层配置。这避免“发现风险”与“工具执行失败”混为一谈，也允许同一结果被交互界面和 CI 采用不同策略。

### 5. partial/unknown 是一等状态

解析失败、不支持语义和预算耗尽必须进入诊断与统计分母。部分结果公开 planned/completed/failed/unknown，且以退出码 4 返回。没有任何可用结果时使用 failed；未预期异常使用 internal_error。任何失败路径都不得发布“零风险”结论。

### 6. 双语协议字段在生产边界生成

所有用户可见 finding 和 diagnostic 同时携带中文/英文，不依赖前端即时翻译。内部 rule code、枚举、schema 字段保持英文。这样下游报告可离线渲染，且中英文内容随规则版本一起审核。

### 7. 单元测试和覆盖率作为后续实现的硬门禁

后续实现按编译上下文、facts、rules、evidence、aggregation、protocol 和 CLI adapter 分层，每层均提供无外部网络依赖的单元测试。覆盖率必须显式指定全部项目源码并启用 branch 统计；整体与受影响模块的 line/branch 均以 90% 为最低门槛。第三方及纯生成代码的排除需要逐项记录理由。

## Risks / Trade-offs

- [静态分析无法证明实际数值误差] → 结论表述为迁移风险，附带输入、阈值和重复运行建议，并要求高风险人工确认。
- [编译数据库缺失或不准确] → 将相关结果标记 unknown/partial，公开未分析分母，不回退到静默默认参数。
- [不同 Clang 版本产生事实差异] → 锁定并记录前端版本，以 canonical facts 和 fixture oracle 做兼容测试。
- [启发式规则误报] → 显式标记 evidence origin 与 confidence，采用稳定抑制协议，不用启发式结果覆盖确定性事实。
- [双语文字增加维护成本] → 规则元数据集中管理，测试校验字段成对存在并共享证据参数。
- [严格双覆盖率门禁增加初期成本] → 从首个实现 change 即接入门禁，避免后期补测导致架构不可测试。

## Migration Plan

本 change 只有文档，不涉及部署或运行时迁移。后续实施阶段、建议 change 名称、依赖和退出门槛以 `docs/floating-point-precision-scanner-roadmap.md` 为准：先建立协议、profiles 和 facts，再逐类加入检测规则，完成可靠性验证后接入 RvPort 分析流水线。每个实现 change 均须独立通过单元测试和双覆盖率门禁。

文档回滚只需撤销本 change 产物；由于没有生产代码、数据库或 API 变更，不存在数据迁移。

## Open Questions

- 首期支持的 Clang 主版本和 profile 发布流程由实现 change 决定。
- RvPort 主服务如何传递编译产物、如何持久化人工确认结果，留给集成 change 设计。
- 动态 x86/RISC-V 对比执行器、容差策略学习和 AI 扩展均需要独立提案。
