## Context

KB Scanner 当前的 `cli.run_scan()` 直接完成路径解析、compilation database 加载、规则加载、项目解析、规则评估和报告输出。`cpp_frontend.py` 产生 `ProjectFacts`，`rules.py` 同时完成匹配、可达性、替代实现、分类和去重，`report.py` 再把 `ProjectFacts` 与 `Finding` 投影成现有报告。这个结构已经能够支撑当前 61 项测试和 24 个规则，但后续若直接替换其中任一大模块，很难区分是输入事实变化、关系推理变化还是分类策略变化导致回归。

前一个技术选型 change 已验证 Tree-sitter、libclang、NetworkX、Pydantic 和安全构建语法技术，并建立独立 `kb-scanner-test` 容器；这些验证模块仍位于 `kb_scanner/technology`，尚不是正式运行时架构。本 change 只建立稳定核心合同和迁移接缝，不把技术 spike 直接接入正式扫描路径。

本阶段必须满足以下约束：

- 当前 CLI、退出码、三个 artifact 和 `schemaVersion: "1.0"` 保持兼容。
- 当前 YAML 规则、`generatedSet` 及 Clang/GCC compiler-derived facts 原样加载。
- 所有正式验证在独立 `kb-scanner-test` 容器中运行，不修改宿主机依赖、生产镜像或根 Compose。
- 只处理 C/C++ 软件静态迁移分析；不增加真实编译、测试执行、操作系统迁移或 RVWMO 实现。
- 旧实现已保存到 `archive/2026-09-04-pre-rewrite`，但快照仅供参考，不参与正式模块发现或运行。

## Goals / Non-Goals

**Goals:**

- 建立不依赖 parser、图库、验证库或 legacy DTO 的核心领域对象。
- 让路径、目标架构、选项、compile context 和版本信息通过统一 `ScanContext` 显式传递。
- 定义可独立替换和测试的阶段 protocol，以及确定性的 orchestrator 生命周期。
- 统一阶段 diagnostic 和失败传播方式，同时保留当前 CLI 退出码语义。
- 通过 legacy compatibility profile 让 CLI 进入新 orchestrator，而扫描行为仍由当前实现提供。
- 为后续 change 逐阶段替换 frontend、knowledge、graph、classifier 和 assessor 提供稳定接缝。
- 使用契约测试证明新入口没有改变当前检测资产、事实数据和报告合同。

**Non-Goals:**

- 不在本 change 内让 Tree-sitter 或 libclang 成为正式 frontend。
- 不建立或遍历正式 Evidence Graph，不接入 NetworkX GraphStore。
- 不重写 YAML rule evaluator、RPM parser、Make/Autoconf 分析或替代实现算法。
- 不实现测试覆盖关系和项目 readiness 分类。
- 不删除 `cpp_frontend.py`、`rules.py`、`models.py`、`report.py` 或其他仍承担兼容行为的模块。
- 不把 legacy DTO 公开为新阶段 protocol 的长期合同。
- 不修改报告 schema、后端解析器、生产 Dockerfile 或部署拓扑。

## Decisions

### 1. 新增 core、pipeline 和 adapters 三类边界

正式结构按职责分为：

```text
kb_scanner/
  core/
    context.py          # ScanContext 与输入选项
    diagnostics.py      # 结构化 Diagnostic
    evidence.py         # Entity / Evidence / Relation
    observations.py     # Observation / Assessment
    results.py          # StageResult / PipelineResult
    protocols.py        # 阶段 protocol
  pipeline/
    orchestrator.py     # 固定生命周期、失败和 diagnostic 汇总
    profile.py          # 组件集合与 profile 选择
  adapters/
    legacy.py           # 当前实现的兼容包装
```

`core` 只能依赖 Python 标准库和同层模块；不得导入 Tree-sitter、Clang、NetworkX、Pydantic、YAML loader 或当前 `ProjectFacts`/`Finding`。`pipeline` 依赖 core protocol，不依赖具体 parser。`adapters` 可以依赖当前实现和第三方库，并负责类型转换。

备选方案是继续在现有 `models.py` 增加字段。该方案会让 legacy parser DTO 逐渐成为所有新阶段的隐式合同，难以在后续替换，因此不采用。

### 2. 内部高数量领域对象使用不可变 slots dataclass

`Entity`、`Evidence`、`Relation`、`Observation` 和 `Diagnostic` 使用 `dataclass(frozen=True, slots=True)` 或等价标准库结构。所有公开字段必须是 JSON-safe 标量、不可变集合或 scanner 自有值对象；可扩展信息使用受限 metadata mapping，但 metadata 不得承载 parser 或图库实例。

核心对象至少表达：

- 稳定 ID 和 kind。
- 项目相对 source location/span（适用时）。
- producer、parse mode、confidence 和 provenance（适用时）。
- Evidence/Relation 引用，而不是复制无法关联的文本描述。
- partial/unknown 等确定性状态。

`Assessment` 在本阶段只定义通用的 assessment kind、state、Evidence/Relation 引用、confidence 和 metadata，不预先固定阶段 6 才会实现的 readiness 状态机。

Pydantic 继续作为后续边界模型候选，但不用于每个图节点，也不成为本阶段核心合同的必要依赖。

### 3. 稳定 ID 使用项目相对的规范化身份材料

核心提供统一 ID factory。ID 从对象 kind、项目相对路径、规范化 source span、producer 和领域自然键构造规范化 tuple，再计算完整的小写 SHA-256；不得包含机器绝对路径、对象内存地址、遍历序号或非确定时间。ID 字符串对消费者保持 opaque，消费者不得解析 ID 获取业务字段。

对没有 source span 的项目级实体使用显式领域自然键。相同输入、配置和知识版本必须产生相同 ID；不同 producer 可产生不同 Evidence ID，并通过后续合并逻辑保留来源集合。

备选方案是 UUID4。它实现简单但无法支持跨次扫描比较和确定性 fixture，因此不采用。

### 4. ScanContext 是一次扫描的只读显式输入

`ScanContext` 在进入 pipeline 前一次性构造，至少包含：

- 规范化输入根目录和输出目录。
- 目标架构。
- language、exclude、exclude-path、context-infer、inactive branch 和 comment hint 等当前选项。
- compilation database 路径及已经安全加载的 compile context 引用。
- rule pack 路径、manifest identity 和 knowledge identity。
- scanner/version 信息。

阶段不得重新解析 CLI 参数，也不得通过全局变量修改 context。阶段产生的信息进入 `StageResult` 或 pipeline state，而不是回写 `ScanContext`。

### 5. 阶段 protocol 使用 scanner 自有输入输出

定义 Workspace Collector、Frontend、Knowledge Provider、Normalizer、Analyzer、Detector、Classifier、Assessor 和 Report Projector protocol。每个阶段接收 `ScanContext`、必要的前序 scanner 自有结果和显式依赖，返回 `StageResult[T]`。

`StageResult` 包含阶段值、结构化 diagnostics 和 completion status。protocol 不得出现 Tree-sitter node、Clang cursor、NetworkX graph、Pydantic model、legacy `ProjectFacts` 或 legacy `Finding` 类型。

本 change 只要求 protocol、最小无操作实现和注入测试存在；后续 change 才逐个提供正式实现。

### 6. ScanApplication 通过 profile 选择 runner，StagedPipelineRunner 固定阶段生命周期

`ScanApplication` 负责构造 context、选择 profile、调用统一 `PipelineRunner` 并把 `PipelineResult` 转换为 CLI 退出状态。profile 可以提供 `LegacyPipelineRunner` 或 `StagedPipelineRunner`；两者实现同一个 runner protocol，但 legacy runner 不伪装成已经完成分层的新实现。

`StagedPipelineRunner` 负责以下固定生命周期：

```text
validate context
  → collect workspace
  → run frontends
  → normalize facts/evidence
  → analyze relations
  → run local detectors
  → classify observations
  → assess project
  → project compatible reports
  → return PipelineResult
```

阶段顺序由 `StagedPipelineRunner` 固定，具体实现通过 `PipelineProfile` 注入。测试可以注入 recording/stub stages，验证顺序、输入传递、diagnostic 聚合、跳过行为和失败隔离，而不调用真实 parser。本阶段完成 staged runner 的编排合同，但默认 CLI 仍选择 legacy runner；阶段 2 开始逐步提供正式 staged profile。

不得建立通用事件总线、服务定位器或动态 plugin 系统；当前只需要显式构造组件集合。这样可以避免为尚未出现的扩展场景提前引入复杂基础设施。

### 7. LegacyCompatibilityProfile 保持行为并建立迁移接缝

本阶段默认 profile 是 `LegacyCompatibilityProfile`，其中的 `LegacyPipelineRunner` 通过 adapter 调用现有 compilation database loader、`parse_project()`、规则加载、`evaluate_rules()` 和 `write_reports()`，并向 `ScanApplication` 返回统一 `PipelineResult`。

为了避免把 `ProjectFacts` 和 legacy `Finding` 固化到新 protocol，adapter 内部可以维护私有 `LegacyRunState`；该类型不得从 `adapters.legacy` 导出，也不得传给未来正式阶段。对外只暴露：

- 结构化 diagnostics。
- 是否成功及兼容退出码原因。
- 已生成 artifact 的路径与 identity。
- 已生成 artifact 的确定性引用；兼容测试直接读取 `scan-result.json` 验证语义，adapter 不重复构造第二份结果摘要。

核心阶段 protocol 和 `StagedPipelineRunner` 在本阶段由 no-op/recording 组件验证；后续 change 以完整的新组件逐阶段替换 legacy profile 内相应职责。第一阶段不强行把当前单体逻辑机械拆成不真实的中间对象。

### 8. Diagnostic 结构化，但报告文本保持兼容

`Diagnostic` 至少包含稳定 code、stage、severity、message、可选 source location、producer、details 和 `affects_exit_code`。orchestrator 汇总 diagnostics 时保持原始顺序稳定，并区分：

- 可降级：保留部分结果并继续后续允许阶段。
- 阶段不可用：跳过依赖该值的阶段并生成 unknown/partial，而不是伪造空结果。
- 输入/规则错误：按照当前兼容语义影响 CLI 退出码。
- 内部不变量失败：终止 pipeline 并返回非零退出码。

本阶段投影到 `scan-result.json`/`scan.log` 的文本仍保持现有表现；结构化字段首先用于内部控制和测试，不强制新增报告字段。

### 9. 兼容 Report Projector 是唯一输出出口

`StagedPipelineRunner` 只允许 Report Projector 写入正式 artifact。`LegacyPipelineRunner` 通过私有 `LegacyReportProjectorAdapter` 调用当前 `report.py`；写报告的行为仍被隔离在 projector 职责内。核心 Entity/Evidence/Relation/Observation/Assessment 不直接序列化为第二个主 JSON。

后续需要保留的新信息遵循既有投影规则：关系证明进入 Finding `trace`，项目评估进入可选 `summary.readiness`。本阶段不产生新的关系或 readiness，因此预期报告结构和 Finding 语义不变。

### 10. 用 golden semantic contract 而不是脆弱的整文件字节比较

兼容测试固定：

- `schemaVersion` 和顶层字段。
- Finding 的 rule ID、类型、severity、blocking、文件、行号和关键 trace 字段。
- 三个 artifact 的存在与基本内容。
- CLI 退出码和 diagnostic 行为。
- 24 个规则的 fixture 覆盖。
- Clang/GCC JSON 文件 SHA-256、六类计数、来源和 `generatedSet` 行为。

报告若包含路径、排序或未来允许的可选字段，不要求整个文件逐字节一致；但任何既有必需字段、类型或语义变化都视为回归。

### 11. 本阶段不新增运行时依赖，只使用独立测试容器验证

核心合同和 orchestrator 使用 Python 标准库。所有正式测试通过：

```text
docker compose -f tools/kb-scanner/compose.test.yml run --rm kb-scanner-test
```

如新增测试文件，更新独立测试镜像后运行；不得在宿主机执行 scanner Python 测试或安装依赖。`backend/Dockerfile`、根 Compose 和生产镜像不属于本 change。

## Risks / Trade-offs

- [风险] 第一阶段新增了较多抽象，却没有立即提升检测能力。→ 将范围限定为后续阶段实际需要的最小对象和 protocol，并用下一阶段的 frontend 接入验证接口，不建立通用 plugin 框架。
- [风险] legacy adapter 变成长期旁路，新阶段始终无法接管。→ 为每个后续 change 明确替换的 stage，并在最终 cut-over change 删除 compatibility profile；本阶段只允许一个默认 legacy profile。
- [风险] 为保持旧行为而让 legacy DTO 泄漏到 core。→ `LegacyRunState` 保持 adapter-private，通过 import boundary 测试禁止 core/pipeline 导入 legacy 或第三方类型。
- [风险] 新 orchestrator 改变 diagnostic 顺序或 CLI 退出码。→ 建立兼容 fixture，显式测试规则加载失败、compile context 降级和成功扫描三类退出路径。
- [风险] 稳定 ID 过早固定不合适的自然键。→ 对外把 ID 视为 opaque，并集中使用 factory；字段可通过版本化 canonicalization 调整，但同一版本内必须确定。
- [风险] 新快照目录被误当正式输入或测试。→ 正式文件发现和 unittest 根目录保持不变，并增加边界测试确认 `archive/` 不进入扫描器模块或默认 fixture discovery。
- [风险] 兼容测试只验证 JSON 形状而遗漏语义退化。→ 同时比较关键 Finding 分类、阻断状态、位置、trace 和事实数据哈希，而不是只跑 schema validator。

## Migration Plan

1. 固化当前 CLI、61 项测试、规则 fixture、artifact 和 compiler facts 基线，确认 archive 快照完整。
2. 新增 `core` 领域值对象、稳定 ID factory、`ScanContext`、`Diagnostic` 和 `StageResult`，先用纯单元测试验证不变量和 JSON-safe 边界。
3. 新增阶段 protocols、recording/no-op 实现和 `PipelineProfile`，验证依赖注入与阶段顺序。
4. 新增 orchestrator，验证 diagnostic 聚合、降级、跳过、fatal 和退出码决策。
5. 新增 `LegacyCompatibilityProfile`，把当前扫描链封装在 adapter 内，并让 CLI 通过 orchestrator 调用它。
6. 在独立 `kb-scanner-test` 容器中运行新旧兼容 fixture、全部现有测试、输出合同和事实数据合同。
7. 更新开发计划的阶段 1 状态；不删除 legacy 模块，为阶段 2 保留可回退路径。

回滚时把 CLI 恢复为直接调用当前 `run_scan` 链，并移除尚未被其他模块使用的 core/pipeline/adapter 文件。因为结果 schema、事实数据、数据库和生产镜像均未改变，不需要数据迁移或部署回滚。

## Open Questions

无。本阶段的领域对象保持最小通用字段，稳定 ID 使用完整小写 SHA-256，兼容语义由生成后的现有 `scan-result.json` 直接验证。
