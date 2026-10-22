## Why

KB Scanner 当前由 CLI 直接串联 `parse_project()`、`evaluate_rules()` 和 `write_reports()`，源码采集、事实解析、匹配、关系判断、分类和报告职责集中在少数模块中，后续无法安全地逐步接入已经选定的双层 C/C++ 前端、Evidence Graph 和项目评估。现在需要先建立稳定的核心领域合同和可替换管线，同时通过 legacy adapter 保持现有行为可运行，避免一次性重写造成检测覆盖或结果兼容性退化。

## What Changes

- 建立正式核心领域模型，定义 `Entity`、`Evidence`、`Relation`、`Observation`、`Assessment` 和结构化 `Diagnostic` 的最小公共字段、稳定身份和来源语义。
- 建立统一 `ScanContext`，承载输入根目录、目标架构、扫描选项、compile context、版本信息和运行期 diagnostics，避免各阶段从 CLI 参数或其他模块的私有对象中读取隐式状态。
- 定义 Workspace Collector、Frontend、Knowledge Provider、Analyzer、Detector、Classifier、Assessor 和 Report Projector 的 scanner 自有 protocol；领域接口不得暴露 Tree-sitter、Clang、NetworkX、Pydantic 或 legacy parser 的私有类型。
- 增加显式 pipeline orchestrator，按照固定阶段顺序执行组件、合并 diagnostics，并允许单元测试注入替代实现。
- 使用 legacy adapter 包装现有 `parse_project()`、`evaluate_rules()` 和报告逻辑，让 CLI 先切换到新 orchestrator，但本 change 不改变现有检测、分类和输出行为。
- 增加新旧路径兼容契约测试，固定 CLI、退出码、Finding 关键语义、三个 artifact、`schemaVersion: "1.0"` 和两份 compiler-derived fact 数据。
- 保留 `tools/kb-scanner/archive/2026-09-04-pre-rewrite` 作为只读参考；本 change 不通过覆盖快照恢复代码，也不删除仍承担兼容行为的旧实现。
- 本 change 只搭建管线骨架，不接入正式 Tree-sitter/libclang 前端、Evidence Graph、构建选择分析、测试覆盖分析或 readiness 分类。

## Capabilities

### New Capabilities

- `kb-scanner-core-pipeline`: 定义 KB Scanner 核心领域对象、统一扫描上下文、阶段 protocol、orchestrator、diagnostic 传播和 legacy-compatible 过渡行为。

### Modified Capabilities

无。现有 `kb-scanner-analysis-architecture` 已要求分层管线、证据可追溯和结果兼容，本 change 在新的核心管线 capability 中细化并实现这些要求，不改变既有 requirement 语义。

## Impact

- 影响 `tools/kb-scanner/kb_scanner` 内的领域模型、CLI 编排和新增 pipeline/adapter 模块，以及 `tools/kb-scanner/tests` 中的核心合同与兼容测试。
- 现有 `cpp_frontend.py`、`rules.py` 和 `report.py` 暂时保留，并通过 adapter 接入新管线；不在本 change 内删除或重写其检测逻辑。
- 不新增第三方 runtime 依赖；继续使用已存在的独立 `kb-scanner-test` 容器进行所有正式测试，不在宿主机安装依赖。
- 不修改 `backend/Dockerfile`、根 Compose、生产 API/worker 镜像、后端 API、任务模型或 CLI 调用方式。
- 继续原样加载 `clang-x86-entries.json`、`gcc-x86-entries.json`、现有 YAML 规则和 `generatedSet`；不重生成或转换事实数据。
- 保持 `scan-result.json` 的 `schemaVersion: "1.0"` 和现有顶层结构，继续生成 `scan-result.json`、`scan-report.html` 与 `scan.log`，不引入第二个主结果文件。
- 分析范围继续限定为 C/C++ 软件静态迁移分析，不包含操作系统迁移、真实 RISC-V 编译或测试执行，也不建模交叉编译时 `uname` 选择错误。
