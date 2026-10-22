## MODIFIED Requirements

### Requirement: 正式 Projector 必须生成现有 schema 1.0 结果和三个 artifact
迁移期版本选择器 SHALL 把同一次 staged scan 的 ScanContext、WorkspaceSnapshot、KnowledgeSnapshot、FrontendSnapshot、NormalizedSnapshot、AnalysisSnapshot、DetectionSnapshot、ClassificationSnapshot、AssessmentSnapshot 和 Diagnostic 直接交给所选版本的独立 Projector。v1 Projector SHALL 保持 `schemaVersion: "1.0"` 及既有顶层语义；v2 Projector SHALL 从这些内部 snapshots 直接生成 `kb-scanner-report-schema-v2`，MUST NOT 读取、解析或转换 v1 JSON。两种版本均 SHALL 使用现有 `scan-result.json`、`scan-report.html`、`scan.log` artifact 名称，同一次 scan MUST NOT 创建第二个主结果，且默认版本在独立 cut-over change 前 SHALL 保持 v1。

#### Scenario: 默认扫描成功投影
- **WHEN** 用户未显式选择结果版本，且完整 staged pipeline 对受支持项目完成静态扫描
- **THEN** Projector SHALL 继续生成 schema 1.0 和请求格式对应的现有 artifact，并返回具有正确摘要的 ArtifactRef
- **AND** 默认 json/html 格式 SHALL 产生 `scan-result.json`、`scan-report.html` 和 `scan.log`

#### Scenario: 旧消费者忽略可选新字段
- **WHEN** v1 结果包含可选 `summary.readiness` 或更丰富的 Finding `trace`
- **THEN** 既有 schema 1.0 消费者 SHALL 仍可读取既有字段和 Finding
- **AND** 可选字段 MUST NOT 改变既有字段的名称、类型、计数语义或 artifact 名称

#### Scenario: 调用方显式请求 schema v2
- **WHEN** 后续实现提供版本选择且调用方明确请求 `2.0`
- **THEN** v2 Projector SHALL 直接从 staged snapshots 生成通过 v2 schema 与引用完整性验证的 `scan-result.json`，并使 HTML/log 与同一 v2 结果一致
- **AND** 它 MUST NOT 同时生成 v1 主结果或把 v2 伪装为 v1 可选字段

#### Scenario: v2 生成不依赖 v1 中间结果
- **WHEN** 同一组 staged snapshots 可供 v1 和 v2 Projector 使用
- **THEN** 两个 Projector SHALL 分别从内部模型投影自己的结果合同
- **AND** v2 MUST NOT 把 v1 Finding、`trace` 或字符串 Diagnostic 作为输入事实

#### Scenario: v2 投影或写入失败
- **WHEN** v2 从 staged snapshots 直接投影、引用验证、序列化或任一 artifact 写入失败
- **THEN** Projector SHALL 返回 failed Diagnostic 和非零结果且不报告未完成的 ArtifactRef
- **AND** 它 MUST NOT 静默回退 v1 或留下会被误认为本次成功扫描的半套 artifact

#### Scenario: 回滚到 schema v1
- **WHEN** v2 消费者尚未就绪或部署需要回滚
- **THEN** 调用方 SHALL 能显式选择 v1 并取得既有合同和 artifact
- **AND** 回滚 MUST NOT 要求修改扫描知识、Evidence Graph 或事实数据
