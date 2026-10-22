## Context

当前扫描器只面向 C/C++，已经具备版本化 scan request/result、x86/RISC-V profile registry、`compile_commands.json` 归一化、Clang AST canonical facts、共享 LLVM 21.1.8 BC 消费、canonical IR facts、AST↔IR evidence、稳定身份、双语诊断和保守失败状态。运行时仍声明 `analysis_scope=facts_only` 且拒绝所有规则，因此即使已经观察到 `long double` 类型、x87 求值策略、FMA lowering 或 fast-math flags，也不会发布迁移风险 finding。

本 change 是 roadmap P3，只把现有事实层提升为四条确定性核心规则。规则层必须消费版本化 immutable facts/evidence/profile，不接触 Clang AST 节点、LLVM C++ 对象、worker 进程或原始命令行字符串。共享 BC 的生产、等待和发布仍由上游 x86 构建与编排负责。

## Goals / Non-Goals

**Goals:**

- 实现 `long-double-abi`、`x87-excess-precision`、`fma-contraction` 和 `unsafe-fp-optimization` 四条版本化规则。
- 建立稳定 rule registry、默认启用集合、显式选择、依赖声明、执行顺序和逐规则 assessment。
- 让每条 finding 同时引用可核验的 source/IR/profile/compile-option 证据，提供双语说明、影响、建议与测试建议。
- 对命中、明确非命中、证据不足、事实冲突、预算耗尽和规则异常分别建模，不把 unknown/skipped/failed 计为“未发现风险”。
- 保持 finding ID、聚合、排序和序列化在不同绝对路径、并发顺序与本地 artifact materialization 下确定。
- 为新增和修改的项目自有代码提供正常、边界与异常路径单元测试，并让项目整体及受影响模块的 line/branch coverage 均达到至少 90%。

**Non-Goals:**

- 不实现 fenv/动态舍入、隐式窄化、混合精度比较、epsilon、归约、libm、SIMD/架构专用 API 等后续规则。
- 不执行 x86/RISC-V 二进制、不做数值差分测试，不根据运行结果自动调整静态 finding。
- 不生成、修改或等待共享 BC，不改变 x86 构建成功状态和 artifact-set 生命周期。
- 不使用 AI/LLM 生成规则结论，不自动修复源码，不实现 RvPort UI 或策略门禁。
- 不把缺少 build-faithful IR、debug mapping 或 profile 字段降级为宿主默认值或文本启发式确定结论。

## Decisions

### 1. 规则层使用纯数据 assessment pipeline

新增规则领域层接收 `RuleContext`：规范化请求、source/target profiles、单个 physical TU/context 的 AST facts、按 profile 分组的 IR facts、evidence bindings 和有效编译选项。每条规则返回一个或多个 `RuleAssessment`，状态限制为 `matched`、`not_matched`、`unknown`、`skipped` 或 `failed`，并携带稳定 scope、reason code、证据 refs 与 frontier。

选择纯数据 pipeline，而不是让规则直接查询前端或 worker，是为了保持可单元测试、可重放和版本隔离。备选方案是规则按需访问 Clang/LLVM 对象；该方案会把生命周期、版本兼容和异常隔离重新带入规则层，因此不采用。

### 2. 首期 registry 只暴露四条规则

registry 为每条规则固定 `finding_code`、`rule_version`、依赖的事实/profile 字段、是否需要 source-preserving/build-faithful IR、默认启用状态和稳定排序键。省略规则选择时默认启用全部四条；显式列表可以选择其子集。未知 code、重复冲突配置或后续 roadmap 中尚未实现的 code 在分析前返回 `invalid_request/rules_not_available`。

选择显式有限 registry，而不是把主规格中所有未来规则声明为可运行，是为了让协议的“支持”与真实实现一致。registry 元数据进入 version 输出、结果 metadata 和 finding identity。

### 3. Finding 只由 `matched` assessment 生成

`matched` 产生 finding；`not_matched` 仅在规则全部必需证据完成且可证明未命中时成立；`unknown`、`skipped` 和 `failed` 进入独立分母与 diagnostics，不生成“安全”finding。每个 finding 引用 assessment ID、rule version、source/target profile fingerprints、source/IR fact IDs、evidence binding IDs 和规范化有效选项。

finding ID 使用 rule code/version、规范化 scope、主要位置、排序后的语义 evidence refs 和 profile fingerprints 计算 SHA-256。诊断文本、绝对路径、artifact root、时间戳和调度顺序不参与身份。跨 TU 的相同配置风险先按规则定义的 semantic aggregation key 合并，再稳定选择主位置并保存 related locations。

### 4. 四条规则采用分层证据策略

#### `long-double-abi`

规则比较 source/target profile 的 `long double` 格式、storage bits、precision、alignment、ABI class、calling convention 和 variadic 语义，并查找 AST facts 中公开可见参数/返回值、`extern "C"`、可变参数、具有外部/持久化边界的记录字段、显式二进制序列化或布局依赖。只有存在边界且 profile 存在确定差异时命中；纯函数内部局部值不命中。关键字段 unknown 或边界分类不完整时返回 unknown。公开 ABI、持久化或变参边界默认 `high` 且要求人工确认。

#### `x87-excess-precision`

规则比较 source/target profile 的 evaluation method、x87 extended precision、FLT_EVAL_METHOD、强制存储语义和有效 excess-precision 选项，并结合 AST 运算链/赋值/volatile/显式 cast 等存储舍入边界及 IR 的 `fpext`/`fptrunc`/中间类型。只有 source 端可能保留扩展中间精度、target 行为不同且存在可观察运算链时命中；明确强制标准精度或每步已存储/截断时不命中。缺少决定性 profile 或 IR 证据时返回 unknown。默认 `medium` 并要求人工确认和边界数值对比。

#### `fma-contraction`

规则从 AST 识别乘加/乘减候选，并通过 evidence 判断 source-preserving 与 build-faithful IR 中是独立 `fmul`+`fadd/fsub`、`llvm.fma`/constrained FMA，还是因优化删除或映射歧义而未知。显式 `std::fma`/`fma*` 调用单独标识，不把它误报为编译器隐式 contraction。只有 source/target contraction policy、有效选项或实际 IR lowering 表明迁移后可能发生融合/展开差异时命中；两端策略与 lowering 可证明一致时不命中。缺少所请求 build-faithful profile或可靠 binding 时返回 unknown/partial。默认 `medium`。

#### `unsafe-fp-optimization`

规则消费编译上下文归一化后的有效语义开关与 IR 每指令 fast-math flags；支持 `-ffast-math`、`-Ofast` 展开后的 reassociation、no-NaNs、no-Infs、no-signed-zeros、reciprocal/approximate functions、finite-math-only、FP contract 和 errno/exception 相关事实。命令行覆盖顺序必须先归一化，规则不得仅搜索原始字符串。仅当危险语义实际生效时命中，并按 TU 或共享配置 scope 聚合；后续否定选项已关闭相应语义时不得误报。AST 选项和 IR flags 冲突时返回 unknown/partial 并诊断。默认 `medium`，若与公开 ABI 无关不自动升级为 high。

### 5. AST-only 与共享 BC 模式按规则依赖区分

`long-double-abi` 在 profile 与 AST 边界事实完整时可产生确定 assessment；`unsafe-fp-optimization` 可以根据规范化有效选项命中，但若结论声称实际 IR 生效范围则需要 IR 佐证。`x87-excess-precision` 和 `fma-contraction` 默认要求对应 IR profile/evidence 才能得出确定的 `not_matched`，AST-only 模式最多产生保守 matched（存在明确源码/profile 风险）或 unknown，不能声明无风险。

请求未提供共享 BC 本身不必使所有扫描失败；状态由启用规则的必需证据决定。若至少一个 assessment 可用但其他启用规则因必需 IR 缺失而阻断，则整体为 `partial`；若没有任何启用规则产生可用 assessment，则为 `failed`。用户可以只选择 AST 可满足的规则以获得 complete。

### 6. 协议增加逐规则分母与兼容元数据

scan request 的规则配置使用稳定 code 列表与可选版本约束，不允许任意脚本或插件。result summary/metadata 增加 enabled/completed/matched/not_matched/unknown/skipped/failed assessment 分母、registry digest、规则版本映射和 `analysis_scope=core_migration_risks`。Finding evidence 保存 typed refs 而不是复制整个 facts bundle；用户可见标题、message、impact、suggestion 和 test_suggestion 均提供中文/英文字段。

schema 进行向后兼容次版本演进；旧 AST-only/facts-only 请求若未指定规则，将按新版本的默认规则集合执行，因此 CLI/version 文档必须明确行为变化。若需要完全复现旧行为，提供空规则集合 `rules.enabled=[]`，结果标记 `analysis_scope=facts_only`。

### 7. 预算、异常和确定性在 rule boundary 隔离

新增总 assessment 数、单规则候选数、证据 refs、聚合位置、诊断和 wall/CPU 预算。候选先按稳定键排序再截断，frontier 记录最后处理键。单条规则异常只将其 scope 标为 failed，其他规则继续；规则代码不得吞掉 `MemoryError`、取消或请求级预算信号。所有集合在输出前按显式键排序。

选择逐规则隔离而不是“任意规则异常即全局 internal_error”，可以保留已验证结论；只有 registry/schema 损坏、身份算法不一致或无法安全序列化等不可隔离错误才升级为 `internal_error`。

### 8. 测试和覆盖率统计覆盖全部自有源码

单元测试分为 rule-domain、registry/config、protocol/schema、aggregation/identity、application/status 五组。每条规则至少覆盖确定命中、明确非命中、profile unknown、事实缺失、AST/IR 冲突、重复/乱序输入和预算截断；C 与 C++、宏/内联/多 TU、source-preserving/build-faithful 差异分别提供 fixtures。锁定工具链集成测试验证真实 Clang/LLVM 事实链，但不替代规则单元测试。

Python 与 C++ 项目自有可执行源码全部进入覆盖率统计，包括未被测试导入的文件；仅排除第三方依赖、生成的 schema/覆盖率输出、构建目录和不可执行文档。项目整体及本次受影响模块的 line/branch coverage 分别至少 90%，任何一项未达标时任务不得完成。

## Risks / Trade-offs

- [静态证据无法证明实际数值误差] → finding 只描述语义差异和潜在影响，附差分/边界测试建议，不虚构 ULP 大小或业务后果。
- [AST↔IR 绑定歧义导致 FMA/x87 误配] → 只消费 exact 或规则允许的唯一 verified binding；歧义保留 unknown，不按函数名或行号任意绑定。
- [profile 内容不足导致大量 unknown] → 在实现前补齐并校验四条规则的必需字段，仍缺失时以字段级 provenance 诊断，不使用宿主默认值。
- [fast-math 选项覆盖顺序复杂] → 复用编译上下文 token 化和归一化层，保存 effective semantics；IR flags 作为实际 lowering 证据而非覆盖全部 TU 语义。
- [同一配置产生大量重复 finding] → 使用规则特定 aggregation key 聚合并限制 related locations，保留受影响数量和确定性代表位置。
- [默认启用规则改变旧请求输出] → schema/analysis version 次版本升级，version 和 metadata 明确默认规则集合；允许显式空集合保留 facts-only 行为。
- [覆盖率门槛受历史未加载源码影响] → 继续使用 source-inclusive 配置和缺失文件检测，不通过缩小统计范围或排除业务代码规避门禁。

## Migration Plan

1. 先扩展 facts/profile/schema 与 fixtures，保持旧 facts-only 路径可运行。
2. 引入 rule registry、assessment/finding 模型、身份与聚合逻辑，并先用合成 immutable facts 做单元测试。
3. 依次接入四条规则，再把 application pipeline 从 facts-only 扩展到规则执行和状态聚合。
4. 更新 CLI version、README/examples 和双语诊断，加入空规则集合的兼容路径。
5. 运行全部单元/契约/锁定工具链集成测试、lint/typecheck、schema/example 校验和 Python/C++ 双覆盖率门禁。
6. 严格验证 OpenSpec 后再允许归档。回滚时可在请求中显式配置 `rules.enabled=[]` 回到 facts-only；已产生的新版本结果仍保留，旧消费者不得静默忽略新增 assessment 元数据。

## Open Questions

- 无阻断性开放问题；四条规则的 code、首期版本、证据依赖和默认启用策略在本设计中固定。后续若要引入项目自定义严重性或 CI risk threshold，应通过独立 change 设计策略层，不并入扫描执行状态。
