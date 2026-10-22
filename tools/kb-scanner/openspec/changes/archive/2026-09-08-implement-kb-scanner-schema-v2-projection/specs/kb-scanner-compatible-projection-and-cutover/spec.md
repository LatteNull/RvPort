## MODIFIED Requirements

### Requirement: 正式 Projector 必须生成现有 schema 1.0 结果和三个 artifact
版本选择器 SHALL 把同一次 staged scan 的 ScanContext、WorkspaceSnapshot、KnowledgeSnapshot、FrontendSnapshot、NormalizedSnapshot、AnalysisSnapshot、DetectionSnapshot、ClassificationSnapshot、AssessmentSnapshot 和 Diagnostic 直接交给所选版本的独立 Projector。ScanRequest/ScanContext SHALL 接受结果版本 `1.0` 或 `2.0`，未指定时 MUST 使用 `2.0`；v1 Projector SHALL 保持 `schemaVersion: "1.0"` 及既有顶层语义，v2 Projector SHALL 从内部 snapshots 直接生成 `kb-scanner-report-schema-v2`，MUST NOT 读取、解析或转换 v1 JSON。两种版本均 SHALL 使用现有 `scan-result.json`、`scan-report.html`、`scan.log` artifact 名称，同一次 scan MUST NOT 创建第二个主结果；v1 SHALL 作为显式兼容和回滚版本保留。

#### Scenario: 默认扫描成功投影
- **WHEN** 用户未显式选择结果版本，且完整 staged pipeline 对受支持项目完成静态扫描
- **THEN** 版本选择器 SHALL 委托 v2 Projector 直接从 staged snapshots 生成通过 schema 与引用完整性验证的 schema 2.0 artifact，并返回具有正确摘要的 ArtifactRef
- **AND** 默认 json/html 格式 SHALL 产生 `scan-result.json`、`scan-report.html` 和 `scan.log`

#### Scenario: 显式请求 schema v1
- **WHEN** 调用方显式请求结果版本 `1.0`
- **THEN** 版本选择器 SHALL 委托现有 v1 Projector 并生成原 schema 1.0 合同
- **AND** 结果字段、Finding/summary 计数、字符串 Diagnostic、artifact 名称和既有 v1 消费者行为 MUST 保持不变

#### Scenario: 旧消费者忽略可选新字段
- **WHEN** v1 结果包含可选 `summary.readiness` 或更丰富的 Finding `trace`
- **THEN** 既有 schema 1.0 消费者 SHALL 仍可读取既有字段和 Finding
- **AND** 可选字段 MUST NOT 改变既有字段的名称、类型、计数语义或 artifact 名称

#### Scenario: 调用方显式请求 schema v2
- **WHEN** 调用方通过 CLI 或 ScanRequest 明确请求 `2.0`，或未指定版本而使用默认值
- **THEN** 版本选择器 SHALL 把原始 staged snapshots 交给 v2 Projector，后者 SHALL 生成通过 v2 schema 与引用完整性验证的 `scan-result.json`，并使 HTML/log 与同一 v2 result model 一致
- **AND** 它 MUST NOT 同时生成 v1 主结果、把 v2 伪装为 v1 可选字段或改变上游分析阶段

#### Scenario: v2 生成不依赖 v1 中间结果
- **WHEN** 同一组 staged snapshots 可供 v1 和 v2 Projector 使用
- **THEN** 两个 Projector SHALL 分别从内部模型投影自己的结果合同
- **AND** v2 MUST NOT 把 v1 Finding、`trace` 或字符串 Diagnostic 作为输入事实

#### Scenario: v2 投影或写入失败
- **WHEN** v2 从 staged snapshots 直接投影、上下文读取、引用验证、序列化、渲染或任一 artifact replace 失败
- **THEN** Projector SHALL 返回 failed Diagnostic 和非零结果且不报告未完成的 ArtifactRef，并 SHALL 恢复本次发布前已有的完整 artifact 集合
- **AND** 它 MUST NOT 静默回退 v1 或留下会被误认为本次成功扫描的半套 artifact

#### Scenario: 回滚到 schema v1
- **WHEN** v2 消费者尚未就绪或部署需要回滚
- **THEN** 调用方 SHALL 能显式选择 v1 并取得既有合同和 artifact
- **AND** 回滚 MUST NOT 要求修改扫描知识、Evidence Graph、事实数据、检测策略或上游 snapshots

## ADDED Requirements

### Requirement: v1/v2 版本选择和发布边界必须具有独立回归门禁
版本值验证、默认选择、显式委托、固定 artifact 名称、单版本输出、渲染一致性、失败不回退和原子发布/回滚 SHALL 分别由隔离 unit tests 覆盖，并 SHALL 由 v1 consumer contract 与 v2 JSON Schema/component tests 共同验证。共享 artifact publisher MAY 被两个 Projector 复用，但 MUST NOT 合并或转换两个版本的 mapper、report model 或 renderer。

#### Scenario: 版本选择器只负责委托
- **WHEN** 单元测试分别请求默认、`1.0`、`2.0` 和不支持的版本
- **THEN** 默认与 `2.0` SHALL 只调用 v2 Projector，`1.0` SHALL 只调用 v1 Projector，不支持版本 SHALL 在分析或写入前失败
- **AND** selector MUST NOT 修改 snapshots、投影字段或生成 artifact 内容

#### Scenario: 同一输入分别验证两个合同
- **WHEN** 独立容器对同一确定性 staged fixture 分别运行显式 v1 和显式 v2
- **THEN** v1 artifact SHALL 继续通过现有 schema 1.0 consumer contract，v2 artifact SHALL 通过 schema 2.0 与 Finding 内引用完整性合同
- **AND** 两次扫描都 SHALL 使用固定 artifact 名称且各自只发布一个版本
