## 1. 冻结实现基线与测试门禁

- [x] 1.1 复核 schema v2 JSON Schema、词汇、引用规则、complete/partial/ambiguous/inactive/unknown 样例、AVX explanation 和 v1/v2 consumer 差异，记录实现不得改写的字段、状态、预算、排序与 facts 哈希基线。
- [x] 1.2 创建 schema-v2-projection 机器可读 unit inventory，把 version selector、models、Finding mapper、chain builder、source context、Diagnostic、summary、validator、serializer、renderers、publisher、Projector 和 CLI adapter 分别映射到隔离测试文件及 90% line / 80% branch 门槛。
- [x] 1.3 扩展 `tests/run_container_tests.py` 增加独立 schema-v2-projection unit gate，并用 inventory 自检拒绝漏映射、未执行模块和只依赖 component/E2E 的伪覆盖；不在本机安装依赖，不修改生产镜像或根 Compose。

## 2. 建立 v2 输出模型与源码上下文

- [x] 2.1 在独立 `kb_scanner/projection/v2/` 包中实现封闭、不可变的 schema v2 report model、枚举词汇、typed provenance、稳定 ID 和排序 helper，禁止自由 `trace` 与未知核心字段。
- [x] 2.2 为 v2 models 和 ID/排序 helper 编写隔离单元测试，覆盖必填/禁止字段、枚举状态、相同语义稳定 ID、遍历顺序扰动和绝对路径/时间/随机值不进入 identity。
- [x] 2.3 实现 `SourceContextProjector`：只读项目根内文件，按前后各 2 行、最多 16 行/4096 字符生成真实行号、完整 span 和一基 end-exclusive highlight，并缓存同一文件读取。
- [x] 2.4 为 source context 编写 fake reader/临时目录单元测试，覆盖单行、多行、文件首尾、Unicode、预算截断、文件缺失、解码失败、路径穿越和不同 step 不复制位置。

## 3. 实现 Finding 与 evidenceChain 投影

- [x] 3.1 实现只读 snapshot index，将 Entity、Evidence、KnowledgeEntry、Relation、ProofPath、Observation、Classification 和 Assessment 按稳定 ID 建索引并验证基础类型引用。
- [x] 3.2 实现 `EvidenceChainBuilder` 的有界闭包、step/edge/break 投影和语义 `primaryPath` 选择，覆盖 build/source、macro replacement、intrinsic/builtin knowledge、classification、assessment、inactive branch、替代分支和测试链路。
- [x] 3.3 为 snapshot index 和 chain builder 编写合成 graph/proof 单元测试，覆盖 complete、inactive、partial、ambiguous、unknown、多候选、冲突、循环、缺失引用、类型冲突和 depth/path/visited 截断。
- [x] 3.4 实现 `V2FindingMapper`，以 Classification/Observation 语义根因为 Finding 边界，分离 fact/conclusion，聚合无损 occurrences，确定性选择 primary occurrence，并嵌入当前 Finding 的自包含 evidenceChain。
- [x] 3.5 为 Finding mapper 编写隔离单元测试，覆盖不同配置/状态不误合并、同根因多 occurrence、主位置选择、Knowledge 紧凑 provenance、Assessment impact 和 4 个 Finding 恢复 24 个 Make flag occurrence。

## 4. 实现 Diagnostic、summary 与引用验证

- [x] 4.1 实现 `V2DiagnosticProjector`，输出 code、stage、severity、status、reasonCodes、count、代表位置和 typed refs，并只按完整聚合键合并同类诊断。
- [x] 4.2 为 Diagnostic projector 编写隔离单元测试，覆盖相同原因聚合、不同 reason/stage/severity 不聚合、全部引用保留和 failed 不被 warning/partial 吞并。
- [x] 4.3 实现 `V2SummaryReducer`，仅从 v2 Findings、Assessment 和输入完整性归约 Finding 计数、occurrence 统计、readiness 与固定静态范围声明，禁止读取 v1 summary 或从零命中推断 ready。
- [x] 4.4 为 summary reducer 编写隔离单元测试，覆盖完整、x86-only、inactive、partial/unknown、零 Finding 但输入不完整，以及 `compiled/linked/testsExecuted=false`。
- [x] 4.5 实现 `V2ReferentialIntegrityValidator`，执行 Finding/occurrence/step 唯一性、primary/root/path/edge/impact/break 解析、code/non-code source、完成状态、排序和 extension namespace 规则。
- [x] 4.6 为 validator 编写全部引用规则的定向正反例单元测试，确保错误返回稳定 rule/reason 且任何无效对象都不能进入序列化结果。

## 5. 实现序列化、renderer 和原子 Projector

- [x] 5.1 实现确定性 v2 JSON serializer，冻结 UTF-8、字段名、排序、紧凑格式和结尾换行，并用顺序扰动测试证明相同输入字节一致。
- [x] 5.2 实现只消费同一 v2 report model 的 HTML/log renderers，展示 summary、Finding 主位置、conclusion、primaryPath、occurrences、breaks 和结构化 Diagnostic，不在 renderer 中重新分类。
- [x] 5.3 为 serializer/renderers 编写隔离单元测试，覆盖转义、Unicode、complete/inactive/partial/ambiguous/unknown、代码上下文、高亮、Diagnostic 和 JSON/HTML/log 语义一致性。
- [x] 5.4 抽取或复用窄 `AtomicArtifactPublisher`，在全部内容完成后一次发布 `scan-result.json`、`scan-report.html`、`scan.log`，并在 replace 中途失败时恢复原完整集合。
- [x] 5.5 为 publisher 编写 fake replace 与临时目录单元测试，覆盖新建、覆盖、摘要 digest、渲染前失败、第一/中间/最后 artifact 写入失败、回滚成功和回滚失败诊断。
- [x] 5.6 实现 `SchemaV2ReportProjector`，按 model → context → Finding/chain → Diagnostic/summary → reference validation → render → atomic publish 的顺序直接消费 staged snapshots；任何阶段失败均返回非零 failed Diagnostic 且不得调用 v1。
- [x] 5.7 为 v2 Projector 编写隔离单元和 component tests，使用 spy/fake 证明不读取 v1 payload/Finding/trace、不修改 snapshots、不执行项目命令，并只在验证成功后返回完整 ArtifactRef。

## 6. 接入显式版本选择并保护 v1

- [x] 6.1 为 `ScanRequest`、`ScanContext` 和 CLI 增加 `--schema-version {1.0,2.0}`，默认 `2.0`，在 workspace/analysis/knowledge 开始前拒绝不支持版本。
- [x] 6.2 实现薄 `VersionedReportProjector` 并装配到 default profile：默认和显式 `2.0` 只委托 `SchemaV2ReportProjector`，显式 `1.0` 只委托现有 `CompatibleReportProjector`，不转换字段或修改 snapshots。
- [x] 6.3 为 CLI/request/context/selector 编写隔离单元测试，覆盖默认、显式 v1、显式 v2、非法版本、单次扫描单 Projector、单版本 artifact 和 v2 失败绝不回退 v1。
- [x] 6.4 运行显式 v1 consumer-contract/字节级回归，确认 schema 1.0 顶层字段、Finding/summary/字符串 Diagnostic、三个 artifact 名称、格式和退出码保持不变；同时验证默认调用产生 schema 2.0。

## 7. 容器合同、真实基线与文档验收

- [x] 7.1 在 `kb-scanner-test` 容器中使用生产 v2 Projector 运行全部 schema v2 正例和定向反例，确保 JSON Schema 2020-12、引用完整性、词汇、上下文预算、稳定排序和 extension 合同全部通过。
- [x] 7.2 在容器中使用默认 v2 扫描人工审计 AVX fixture，逐字段核对 build/source、macro/intrinsic、Knowledge、Classification、Assessment、primaryPath、steps/edges/breaks、代码上下文及 24 个 Make flag occurrences，并验证显式 `2.0` 与默认输出字节一致。
- [x] 7.3 在容器中运行 schema-v2-projection 逐模块 90% line / 80% branch 门禁、所有既有 unit/component/contract tests、v1 回归、无副作用/故障回滚测试和完整回归，并在结束后关闭独立测试容器。
- [x] 7.4 更新 README、schema-v2 设计基线和 consumer migration 文档，明确默认切换为 v2 的 breaking change、`--schema-version 1.0` 兼容/回滚方式、v2 直接 snapshots 投影、自包含 Finding、固定 artifact、失败语义、静态范围和后续 backend/frontend change。
- [x] 7.5 验证 `clang-x86-entries.json` 与 `gcc-x86-entries.json` 的 bytes/SHA-256、分类和加载路径未变化，确认没有恢复 Legacy/YAML 运行依赖或修改 detector/classifier/assessor policy。
- [x] 7.6 运行 `openspec validate implement-kb-scanner-schema-v2-projection --strict`，确认 proposal/design/spec/tasks 与实际实现、测试 inventory 和容器验证结果一致。
