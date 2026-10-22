## Context

后端已经具备项目、源码版本、KB 扫描、SBOM 分析、迁移输入合并、任务运行时、任务日志、SSE 和对象存储制品能力。迁移输入通过 `migration_input_sets` 和 `migration_input_refs` 按 `source_revision_id` 隔离，并通过 `CONFIRMED`、`CANDIDATE`、`EXCLUDED` 表达人工确认状态。

数据库已经存在 `reports` 和 `report_inputs` 表，但当前代码没有 report 模块，也没有报告生成任务类型。现有 `reports` 表只关联 `project_id` 和 `task_id`，没有显式保存 `source_revision_id`，对后续同项目多源码版本报告追溯不够明确。

## Goals / Non-Goals

**Goals:**

- 提供迁移评估报告生成闭环，报告只消费指定源码版本下人工确认的迁移输入。
- 报告生成使用现有任务、worker、RabbitMQ、任务事件和 SSE 机制。
- 报告结果是不可变快照，后续迁移输入状态或原始分析结果变化不影响已生成报告。
- 支持报告列表、最新报告、详情、输入快照分页查询和 HTML/JSON 下载。
- 报告 HTML/JSON 通过 `stored_artifacts` 保存到对象存储，API 不暴露服务器真实路径、bucket 或 object key，不返回未确认迁移输入。
- 单元测试和 E2E 测试覆盖正常流程、异常流程和 edge case。

**Non-Goals:**

- 本 change 不实现复检、源码版本对比报告或 diff item 生成。
- 本 change 不实现 PDF、Word 或飞书文档导出。
- 本 change 不实现 AI 总结或外部 LLM 生成报告。
- 本 change 不重新设计 KB/SBOM 原始结果表。
- 本 change 不把报告内容拆成可编辑的问题状态表；报告只消费迁移输入快照。

## Decisions

### 1. 报告绑定源码版本

`reports` 增加 `source_revision_id`，并建立 `reports(project_id, source_revision_id, generated_at desc)` 索引。报告创建时请求可提交 `sourceRevisionId`；未提交时使用项目当前 active source revision。

选择这个方案的原因是源码版本是报告事实边界。只从 `project_id` 推导最新源码版本会在代码重新上传后让旧报告失去明确归属。

替代方案是不改表，在 `summary` JSON 中保存源码版本。该方案查询和约束能力弱，不利于 latest、列表过滤和审计，因此不采用。

### 2. 报告生成走异步任务

新增任务类型 `REPORT_GENERATE`。创建报告 API 在事务内创建 `tasks` 和 `reports` 初始记录，提交后投递队列。worker 认领任务后执行报告生成，成功后将 `reports.status` 更新为 `SUCCEEDED`，并写入 `summary`、`risk_level` 和 `generated_at`，同时为 HTML/JSON 报告写入 `stored_artifacts` 元数据。

选择异步任务是为了和 KB/SBOM/源码同步的运行时模型保持一致，并自然复用任务 SSE、日志、取消和失败处理。

### 3. 报告只消费 confirmed migration input references

报告 worker 使用 `migration_input_refs` 查询 `project_id + source_revision_id + status='CONFIRMED'`。查询结果为空时任务失败，错误码使用 `REPORT_NO_CONFIRMED_INPUTS`，不生成空报告。

选择失败而不是空报告，是为了避免用户误以为“没有风险项”。如果后续产品需要空报告，可以作为显式选项扩展。

### 4. `report_inputs` 保存生成时快照

每个 confirmed migration input 写入一条 `report_inputs`：

- `input_type = MIGRATION_INPUT_REF`
- `input_id = migration_input_refs.id`
- `input_snapshot` 保存 reference 展示字段、确认状态、备注，以及根据 `source_type + source_ref_id` 回查到的真实来源详情。

这样报告详情和下载都可以复现生成时内容。即使后续用户把迁移输入改成 `EXCLUDED`，或者原始扫描结果发生补充，旧报告仍保持稳定。

### 5. 报告 artifact 使用对象存储

报告 JSON 和 HTML 通过已完成的对象存储制品能力保存，`stored_artifacts.owner_type = MIGRATION_REPORT`，`owner_id = reports.id`，`artifact_type` 使用稳定值表达 HTML 和 JSON 两种报告输出。下载接口根据 reportId 和 format 查询对应 `stored_artifacts`，校验项目权限后由后端代理读取对象内容。

HTML 作为可读报告，JSON 作为前端或归档流程可机器处理的报告快照。列表和详情接口只返回摘要和安全 artifact 摘要，不直接返回大文件内容，不暴露 bucket、object key、endpoint 或服务器路径。

已有 `reports.html_path` 和 `reports.json_path` 若存在，仅作为历史兼容字段处理；本 change 的新报告不依赖本地路径字段表达输出位置。

### 6. 总体风险等级由输入快照聚合

报告 `risk_level` 从 confirmed 输入的 `detected_level` 聚合得到。KB 来源按 `CRITICAL > HIGH > MEDIUM > LOW > INFO > COMMENT` 排序；SBOM 来源若 `detected_level` 形如 `HIGH/TARGET_PRESENT`，取 `/` 前的风险等级参与聚合。

该聚合只用于报告摘要，不替代单条迁移输入的详细等级和匹配状态。

### 7. API 权限沿用项目访问校验

创建、列表、latest、详情、输入快照和下载接口都必须校验当前用户对项目或报告所属项目有访问权限。报告详情和下载通过 reportId 反查 projectId 后校验，避免用户猜测 reportId 读取其他项目报告。

## Risks / Trade-offs

- [Risk] 报告生成期间迁移输入被用户修改，导致生成前后状态不一致。→ Mitigation: worker 在读取 confirmed refs 后立即写入 `report_inputs` 快照，报告以快照为准。
- [Risk] HTML 报告内容包含用户源码路径或服务器路径。→ Mitigation: 使用 migration input 的 `location_label` 和脱敏后的 source detail，下载接口不返回本地路径。
- [Risk] 单份报告输入数量较大，详情接口返回过大。→ Mitigation: 报告输入快照提供分页列表；报告详情只返回 summary 和 metadata。
- [Risk] 报告对象上传成功但数据库元数据写入失败会留下孤儿对象。→ Mitigation: 复用 `StoredArtifactService` 的上传后元数据失败清理能力；报告任务失败时尽力删除本次写入的对象。
- [Risk] 报告 JSON schema 后续变化影响历史解析。→ Mitigation: JSON 中保存 `schemaVersion`，MVP 使用 `migration-report/v1`。

## Migration Plan

1. 新增 Liquibase 迁移，为 `reports` 增加 `source_revision_id` nullable 字段、外键和索引。
2. 对历史报告保留 `source_revision_id=null`；MVP 当前未实现报告业务，不需要回填。
3. 新报告创建时必须写入非空 `source_revision_id`，应用层保证。
4. 报告输出复用已有 `stored_artifacts` 表，不新增报告专用大文件内容字段。
5. 如果需要回滚代码，新增字段可保留，不影响旧逻辑。

## Open Questions

- 报告 HTML 的视觉模板是否由后端长期维护，还是后续由前端按 JSON 渲染后导出。
- 空 confirmed 输入未来是否需要支持“生成空报告”，当前建议明确失败。
