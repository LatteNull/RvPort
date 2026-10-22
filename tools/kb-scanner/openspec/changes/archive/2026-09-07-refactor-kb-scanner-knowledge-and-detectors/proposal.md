## Why

正式 C/C++ Frontend 已能稳定产生可追溯 Evidence，但当前知识加载、局部匹配、可达性判断和最终 Finding 分类仍耦合在 legacy `rules.py` 中。现在需要先建立独立的 Knowledge Provider、Evidence Normalizer 和 Local Detector，使后续关系图、构建选择和项目评估能够消费稳定 Observation，而不会把“局部命中”提前等同于 RISC-V 阻断问题。

## What Changes

- 新建版本化、严格 JSON 的 knowledge manifest；本 change 的正式 Knowledge Provider 只读取 manifest 以及 Clang/GCC 两份编译器派生 x86 事实 JSON，并在运行时去重时保留全部来源与知识身份。
- 新 staged 路径对现有 24 个 YAML rule 保持零依赖，不解析、包装、转换或建立逐 rule migration inventory；这些 YAML 仅保持字节冻结并继续服务默认 legacy CLI 的兼容回归。
- manifest 只描述生成事实 source、版本、逻辑路径和内容摘要，不承载 detector recipe、matcher operator、regex、分类或展示文案；Detector 定义和匹配算法由 Python 代码及单元测试维护。
- 新建 Evidence Normalizer，把不同 frontend producer 的等价局部事实归一到 scanner 自有类型，同时保留原 Evidence ID、producer、compilation context、位置和 confidence；缺失证据继续表达为 unknown/partial。
- 为正式 C/C++ Frontend 补充 Local Detector 必需但当前缺失的 declaration/target attribute Evidence；编译参数事实由 Normalizer 从只读 `CompilationUnitContext` 转换，不重新执行或解析 command。
- 将局部检测拆为可注入 Detector，只产生带 Knowledge/Evidence 引用的 Observation；本 change 对两份现有 JSON 提供的 header、intrinsic、builtin、vector type、平台宏和编译参数做事实支持的精确匹配，对尚无权威知识支持的结构信号只产生 candidate/hint 或明确 deferred。
- 明确 comment 中的 x86/SSE/AVX 只能产生非阻断 hint；模糊宏、变量或枚举只能形成候选，不得在缺少后续关系证据时升级为 blocker、严重程度或 readiness 结论。
- 在 staged qualification profile 中接入真实 Frontend、Knowledge Provider、Normalizer 和 Local Detector，并继续使用 recording/no-op 的后续 Analyzer/Classifier/Assessor/Projector；默认 CLI 仍保持 legacy compatibility profile。
- 为每个新增或实质修改的业务模块同步提供隔离单元测试、模块映射和容器内行/分支覆盖率门禁，并保留现有 component/integration/compatibility 回归。
- 保持 `scan-result.json` 的 `schemaVersion: "1.0"`、既有顶层字段、Finding 关键语义及 `scan-result.json`、`scan-report.html`、`scan.log` 三个 artifact，不引入第二主结果结构。
- 不修改或包装五个冻结 legacy 文件；不改变、转换或重生成两份编译器事实数据；不执行被扫描项目的 compiler、构建、配置、插件、response file 或测试。
- 当前尚不存在的 `curatedSets` 不在本 change 中创建、填充或接入；其选源、采集、审校、溯源和扩展接入由后续独立 change `collect-kb-scanner-curated-knowledge-sets` 完成。

## Capabilities

### New Capabilities

- `kb-scanner-knowledge-and-local-detection`: 定义 generated-facts-only JSON manifest、知识加载与来源追踪、code-owned Detector、Evidence 归一化、局部 Observation 检测、hint/候选降级语义、行为验收矩阵、确定性身份以及逐模块单元测试合同。

### Modified Capabilities

- `kb-scanner-core-pipeline`: 允许 staged qualification 使用真实 Knowledge Provider、Normalizer 和 Local Detector，同时规定在关系分析、分类、评估和兼容投影尚未完成前不得切换默认 CLI。
- `kb-scanner-cpp-frontends`: 补充可稳定提取 declaration/target attribute 的 Evidence kind，使 target attribute 与固定向量宽度检测不需要重新读取源码或绕过 Frontend。

## Impact

- 主要新增 `kb_scanner/knowledge/`、`kb_scanner/normalization/`、`kb_scanner/detectors/` 及其 `tests/unit/`、fixture、inventory 和 staged qualification 测试。
- 可能扩展 scanner 自有 Knowledge/Normalized/Observation 领域合同或 adapter protocol，但不得把 JSON schema model、YAML、Pydantic、legacy DTO 或 parser 原生对象泄漏到 core 接口。
- 新增独立的 generated-facts manifest，继续原样复用 `rulesets/riscv-porting/generated/clang-x86-entries.json`、`gcc-x86-entries.json`；现有 YAML 不修改，继续只服务默认 legacy CLI 和兼容回归。
- 开发计划新增后续 change `collect-kb-scanner-curated-knowledge-sets`；本 change 不提交伪造的空 `curatedSets`、示例条目或隐藏人工词表。
- 测试依赖和验证只进入独立 `kb-scanner-test` 容器；不修改或构建 `backend/Dockerfile`、根 Compose 或生产镜像。
- 本 change 只覆盖 C/C++ 软件静态迁移分析，不涉及操作系统、内核、系统调用、驱动、板级迁移、真实 RISC-V 编译或项目测试执行。
