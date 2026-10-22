## Context

项目已经具备 `source_revisions`、KB 扫描、SBOM 分析和报告相关基础模型。KB findings 已经绑定 `source_revision_id`，SBOM 分析结果绑定 `sbom_run_id` 和环境快照。用户现在需要一个位于报告之前的人工确认层：前序任务结果只是候选，只有加入并确认到当前源码版本迁移输入中的条目才进入报告。

源码会被多次上传或 Git 同步。每次成功源码入库都会生成新的 `source_revisions`。迁移输入和后续扫描结果如果只按项目聚合，会导致旧版本候选问题污染新版本分析和报告。

## Goals / Non-Goals

**Goals:**

- 为每个源码版本维护独立迁移输入集合。
- 用轻量 reference 表统一迁移输入列表展示、分页、过滤、排序和确认状态。
- 支持批量导入真实结果记录到迁移输入，单条导入使用同一个 list 接口。
- 支持“合并迁移输入”按钮按来源类型自动导入当前源码版本相关的当前结果。
- 支持 SBOM 结果加入迁移输入时绑定当前源码版本，但不要求 SBOM run 本身绑定源码版本。
- 报告生成只消费 `CONFIRMED` 迁移输入 reference。

**Non-Goals:**

- 不实现冲突检测或冲突解决。
- 不实现用户手工指定 `assigned_risk_level`。
- 不重构现有 KB findings、SBOM result items 或报告表为通用结果表。
- 不物理删除旧源码版本的迁移输入和历史扫描结果。
- 不实现前端页面变更。

## Decisions

### 1. 迁移输入以 source_revision 为作用域

每个 `source_revision` 对应一个迁移输入集合。源码首次上传后该集合为空；用户修复后再次上传或 Git 同步成功生成新的 `source_revision` 时，新的集合也为空。

这样前端按当前 active source revision 查询时天然不会看到旧版本输入。旧版本输入仍保留，用于历史审计和后续版本对比。

### 2. 使用 reference 表而不是复制完整来源详情

新增 `migration_input_refs` 作为统一列表索引。该表保存列表所需的稳定展示字段：

- 问题：`issue_title`
- 来源：`source_type`
- 真实来源 ID：`source_ref_id`
- 风险/状态：`detected_level`
- 路径/组件：`location_label`
- 建议处理：`recommendation_summary`
- 确认状态：`status`

详情接口根据 `source_type + source_ref_id` 回查真实记录。这样列表查询简单，详情仍然保持来源事实，不把不同来源的大量字段揉到一张表中。

### 3. source_ref_id 由应用层校验

`source_ref_id` 可能指向 `findings`、`sbom_analysis_result_items` 或后续代码类结果表。数据库层不适合建立单一外键。服务层必须按 `source_type` 校验：

- 来源记录存在。
- 来源记录属于 URL 中的 `projectId`。
- 代码类来源记录的 `source_revision_id` 必须等于 URL 中的 `sourceRevisionId`。
- SBOM 来源不要求本身绑定源码版本，但加入 reference 时必须绑定 URL 中的 `sourceRevisionId`。

为避免重复导入，使用 `unique(input_set_id, source_type, source_ref_id)`。

### 4. detected_level 按来源生成展示字符串

代码类来源的 `detected_level` 使用 finding severity 原值，当前 KB scanner 输出为小写：

- `critical`
- `high`
- `medium`
- `low`
- `info`

SBOM 来源的 `detected_level` 使用 `risk_level + "/" + target_match_status`，例如：

- `LOW/TARGET_PRESENT`
- `MEDIUM/UPGRADE_AVAILABLE`
- `HIGH/SOURCE_BUILD_REQUIRED`

详情接口仍返回 SBOM 的结构化 `riskLevel` 和 `targetMatchStatus`，reference 表只保留统一展示值。

### 5. location_label 按来源生成

代码类来源：

- 有单行：`src/main.c:42`
- 有范围：`src/main.c:42-45`
- 无行号：`src/main.c`

SBOM 来源：

- 软件包：`package:gcc@12.3.0`
- 独立库文件：`lib:/usr/local/lib/libfoo.so.1`
- native 文件：`native:/opt/vendor/bin/tool`
- 工具：`tool:gcc@14.1.0`

SBOM 优先使用包名和版本；没有包名时使用路径；再没有路径时 fallback 到组件名。

### 6. 自动合并不选择历史 run

“合并迁移输入”是当前页面按钮。请求只选择来源类型，例如知识库扫描 + AI 扩展、纯 AI 扫描、弱弱内存模型扫描、SBOM 替代性分析。后端基于当前项目和当前源码版本找到对应来源的当前有效结果：

- 代码类来源：查当前源码版本下最新成功扫描结果。
- SBOM 来源：查当前项目最新成功 SBOM 分析结果。

本期不处理冲突；重复项幂等跳过。新导入项默认 `CANDIDATE`。

### 7. 报告生成只消费 confirmed refs

报告生成时不直接读取 KB/SBOM 原始结果作为问题来源，只读取当前源码版本下 `status=CONFIRMED` 的迁移输入 reference，再按来源回查真实详情构造报告内容。

## Risks / Trade-offs

- [Risk] `source_ref_id` 没有数据库外键，错误数据只能由服务层防住。  
  Mitigation: 所有导入和详情查询都走统一 resolver，按 `source_type` 做存在性、项目和源码版本校验。

- [Risk] 自动合并的“当前有效结果”定义不清会导致前端看到非预期条目。  
  Mitigation: 本期明确按最新成功 run 解析，并在响应中返回导入来源 run 的摘要计数。

- [Risk] `detected_level` 作为展示字符串不适合复杂风险排序。  
  Mitigation: 第一版支持按 `createdAt`、`sourceType`、`status`、`detectedLevel` 字符串过滤/排序；后续如需严格风险排序再新增派生 rank 字段。

- [Risk] 旧报告流程可能仍直接读取扫描结果。  
  Mitigation: 在 API/design/spec 中明确报告只消费 confirmed migration inputs，实施时补单元测试和 E2E。

## Migration Plan

1. 通过 Liquibase 新增 `migration_input_sets` 和 `migration_input_refs`。
2. 生成 jOOQ 代码。
3. 实现 service/repository/controller。
4. 在源码版本成功创建路径中确保对应 input set 可按需创建或首次查询时懒创建。
5. 实现批量导入、自动合并、列表、详情、状态更新。
6. 调整报告生成输入来源。
7. 补齐单元测试和 E2E。

回滚时可先停止使用迁移输入 API；新增表不影响现有 KB/SBOM 原始结果表。
