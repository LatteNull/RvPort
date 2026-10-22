## Context

`result_v2.py::_evidence_chain` 当前仅从 typed reference 生成步骤，所有步骤固定 complete，缺少标题及原因。工具 v2 Schema 的 step 禁止额外属性，因而需要生成器和 Schema 配套变更。后端 `SpecializedAnalysisRuntimeService.imported` 将整个 Finding 保存为 detail；前端直接读取步骤 title/reason。本次不修改前端。

## Goals / Non-Goals

**Goals:**
- 为每个实际输出步骤提供准确、非空、双语可读说明，与引用证据一致。
- 不新增网络请求，通过现有详情和不可变 JSON 提供同一内容。
- 遵守现有证据预算、路径安全、确定性和历史记录约束。

**Non-Goals:**
- 不改变浮点规则、风险等级或证据图拓扑，不统一三个扫描器全部协议，不增加 AI 生成说明。
- 不回填旧结果，不修改前端、KB 或内存序工具，不新增数据库列或报告类型。

## Decisions

### 1. 工具生成说明，后端保留内容

在 v2 step 增加必填非空字符串 `title`、`titleEn`、`reason`、`reasonEn`，中文为默认展示字段。标题最多 512 字符、说明最多 4096 字符；生成时使用有界的事实摘要而非整个源码或 AST。保留现有 kind/references/reasonCodes 等字段。拒绝后端按 kind 补固定文案的方案，避免导出的工具结果与 API 不一致。

### 2. 使用本次扫描内的事实索引

在 `project_result_v2` 已有的 source facts、IR facts、evidence、profiles、build context 和 assessments 范围建立按类型与 ID 区分的只读索引，再向步骤生成传递解析上下文。每次扫描只构建一次，不从文件、网络或数据库逐条查找。只呈现直接引用的证据，不把整个事实集合注入 Finding。

| 步骤 | 标题与原因的依据 |
|---|---|
| sourceObservation | 事实类型、真实运算/类型/相对位置；解释观察到了什么，而非断言迁移必然失败 |
| irObservation | 已记录的 LLVM opcode、浮点属性及位置；不存在的 fast-math 标志不得补造 |
| binding | 实际源码与 IR 对应状态、匹配依据及歧义限制 |
| profile | 被引用的源/目标浮点模型差异；不能仅列 fingerprint |
| buildContext / compileOption | 实际编译配置或选项及与该结论有关的语义 |
| assessment | 对应 assessment 的状态、支持证据和限制；不自动把未知提升为已确认 |
| conclusion | 已有 Finding 双语 title/message/impact，可复用但不能用于替代其他步骤说明 |
| observation | 根据已解析事实生成摘要；无法解释时明确说明证据类型和限制 |

引用缺失或无法解释时提供双语限制说明和稳定 reasonCode；不能生成虚构的事实。遵守既有引用闭包校验，真正悬空的引用仍不得发布为合法完整结果。仅展示信息不可用但引用有效时，允许保留原始证据；步骤/链状态遵守既有 partial/unknown 传播规则，不因为本功能强行标为 complete。

### 3. 身份、协议与缓存

保持 schemaVersion 2.0 和既有外层结构，工具和严格 Schema 同步发布，说明这是扩展后的 v2 合同。新生成的每一步必须满足新增字段约束；历史落库记录继续读取原文，不拿新版生成要求阻止历史详情读取。工具版本/发布记录需记录合同变化。

不将展示文案加入 Finding/step 的 ID 计算。现有结果 semantic digest 若包含证据链则随新内容正常重新计算，不伪造旧摘要；同一输入同一版本重复输出稳定。检查缓存保存的是 facts 还是最终结果，仅对会复用缺字段最终结果的缓存升级，不无关清空共享 BC。

### 4. 后端与验证边界

保留现有 detail 透传，补充解析、入库和详情响应测试，确保 UTF-8 双语不丢失。不额外添加顶层 reason 替代 steps.reason，不新增接口。既有 JSON 制品携带新字段，复用当前报告/归档登记；不新增报告布局工作。

Linux Docker 独立单测覆盖各 step 类型、空/缺失/歧义证据、长度、Unicode、确定性、Schema 严格校验、截断及引用闭包。外部连接只 mock 返回值。整体与受影响模块的行/分支均至少 90%，含未加载自有源码；记录第三方及生成代码排除项。真实 Clang AST-only 与 AST+BC 用例验证描述来自实际事实，后端真实 API 验证不能替代单测。

## Risks / Trade-offs

- 证据对象只有摘要而没有语义 → 在已有内存输入层传入最小解析上下文，不扩大为全量事实输出；不可解释时诚实提示。
- 描述把潜在风险写成确定错误 → 区分观察、评估、结论，保留置信度和限制。
- 文案变化影响 semantic digest → 按现有摘要规则重新计算，稳定 ID 不依赖文案。
- 旧 Schema 拒绝新字段 → 工具/Schema 同镜像发布，文档说明合同扩展；旧记录不回填。
- 输出变大或泄漏路径 → 有界摘要、相对路径及既有脱敏校验；覆盖整体输出预算。

## Migration Plan

本次工具版本为 0.5.1，Python 与 IR worker 版本同步；后端运行记录的浮点工具版本常量同步为 0.5.1，并增加断言，避免实际制品与列表版本不一致。后端其余生产逻辑和 API 不变。工具已有源码归属判断只补充 bool | None 类型标注，不改行为。事实缓存可以继续复用，但不存在最终结果缓存，结果始终使用新描述逻辑投影。

明确工具范围授权后实现工具生成与协议，更新工具自身 spec/docs，执行 Docker 单测及覆盖率，再验证后端透传。重建 worker，用现有真实项目新建浮点扫描，保留新旧 runId、原始 JSON 与详情响应作对照。无需数据库迁移，回滚镜像不改历史制品。

## Open Questions

无产品阻塞问题；apply 时需明确 `tools/floating-point-precision-scanner` 为本 change 特别允许范围。若真实环境不可用，记录阻塞，不用 fixture 冒充真实 API 成果。
