## Why

Schema v2 的合同、引用规则和代表性样例已经冻结，但当前运行时仍只能投影 schema 1.0，消费者尚不能从真实扫描结果中取得 Finding 自包含的完整证据链。现在需要实现独立的 v2 投影路径，并把 v2 设为 Scanner 默认结果，使同一套 staged snapshots 能直接生成可验证、可展示且确定性的 schema 2.0，而不是先生成或转换 v1。

## What Changes

- 实现独立的 schema v2 Projector，直接消费当前 staged pipeline 的 context、facts、analysis、detection、classification、assessment 和 diagnostics snapshots；禁止读取、解析或转换 v1 JSON/Finding/`trace`。
- 实现 Finding mapper、evidence-chain builder、source-context projector、summary reducer、结构化 Diagnostic projector、引用完整性 validator 和确定性 JSON serializer。
- 让每个 v2 Finding 直接包含 `fact`、`conclusion`、`occurrences[]` 和自包含 `evidenceChain`，其中主链、分支、断点及每个代码型 step 的行列、代码上下文和命中高亮均可由详情页直接展示。
- **BREAKING**：增加结果版本选择并将未指定版本时的 Scanner 默认输出切换为 schema `2.0`；需要旧合同的调用方必须显式选择 `1.0`。同一次 scan 只产生所选版本的 `scan-result.json`、`scan-report.html` 和 `scan.log`。
- 实现 v2 HTML/log renderer，使三个固定 artifact 与同一 v2 JSON 的 Finding、summary、status 和 Diagnostic 保持一致；v2 失败时不得静默回退 v1或发布半套 artifact。
- 保留 schema 1.0 Projector、artifact 文件名和显式兼容/回滚能力；本 change 不移除 v1，也不修改后端或前端消费者，消费者适配由后续 change 完成。
- 保持现有 Clang/GCC compiler-derived facts、curated knowledge、Evidence Graph、detector/classifier/assessor 判定与静态分析边界不变。
- 为 version selector、v2 mapper、chain builder、context projector、validator、serializer、summary reducer、renderers 和发布事务分别建立隔离单元测试映射，并在唯一 `kb-scanner-test` 容器中执行覆盖率、合同、AVX 字段级、v1 回归和无副作用门禁。

## Capabilities

### New Capabilities

<!-- None. This change implements the already-defined schema-v2 capability. -->

### Modified Capabilities

- `kb-scanner-report-schema-v2`: 将已冻结的 schema v2 设计合同落实为直接消费 staged snapshots 的运行时投影、上下文提取、引用验证、确定性序列化和 renderer 行为。
- `kb-scanner-compatible-projection-and-cutover`: 增加独立 v1/v2 版本选择并把 v2 设为默认，同时保持显式 v1 兼容、固定 artifact 名称、单次扫描单版本输出、失败不回退和原子发布/回滚合同。

## Impact

- 主要影响 `kb_scanner/projection/`、CLI/request adapter、pipeline profile/version selection、JSON/HTML/log renderer、schema-v2 validators 和对应测试 inventory。
- 复用 `schemas/scan-result-v2.schema.json`、`scan-result-v2-reference-rules.json`、`scan-result-v2-vocabulary.json` 及现有 v2 examples；若实现暴露合同矛盾，只允许作向后兼容的设计勘误并增加回归测试。
- 默认 `scan-result.json` 改为 schema 2.0；依赖旧合同的调用方可显式选择 `--schema-version 1.0`，继续取得原 schema 1.0 字段、计数语义和三个同名 artifact。
- 不新增本机依赖；所有依赖安装、单元测试、合同测试、AVX 验证和完整回归只在独立 `kb-scanner-test` 容器中执行。
- 不涉及真实 RISC-V 编译/链接/测试，不涉及 OS、内核、系统调用、驱动或板级迁移，也不重新实现 RVWMO 分析。
