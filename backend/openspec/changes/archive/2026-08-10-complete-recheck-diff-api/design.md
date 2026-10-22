## Context

现有后端已经具备源码版本、迁移输入 reference、任务运行时、latest compare 查询和 `diff_items` 分页查询能力。但当前 latest compare 只是复检状态入口，`POST /api/projects/{projectId}/rechecks` 仍停留在 API 文档占位，缺少实际复检任务创建和差异生成运行时。

本次需要明确：前端关心的不是源码文件行级 diff，而是“上次检测并人工确认的问题，在本次检测后是否修复、是否仍存在、是否新增、是否发生变化”。因此复检差异必须基于已确认迁移输入，而不是原始扫描全集，也不是源码文本 diff。

## Goals / Non-Goals

**Goals:**

- 提供复检任务创建 API，支持 latest 和显式 base/target source revision。
- 基于 base/target 源码版本下 `CONFIRMED` 的迁移输入 reference 生成差异。
- 生成 `RESOLVED`、`UNCHANGED`、`NEW`、`CHANGED` 差异项。
- 让差异列表支持分页、过滤和排序，并返回前端审计需要的摘要字段。
- 提供单条 diff item 详情 API，返回 old/new 两侧快照和匹配证据。
- 建立 issue identity / matching 模型，避免因代码行号变化导致同一 issue 被误判为 resolved + new。

**Non-Goals:**

- 不实现源码文本行级 diff viewer。
- 不实现自动修复或在线 patch。
- 不重新设计迁移输入合并页面。
- 不要求 SBOM 分析本身绑定源码版本；只有进入迁移输入后的 SBOM reference 绑定源码版本。
- 不做复杂 AI 语义匹配；本期使用稳定字段和规则化模糊匹配。

## Decisions

### 1. 复检对比已确认迁移输入，而不是源码文本

复检任务读取两个源码版本对应迁移输入集合中 `confirmation_status=CONFIRMED` 的 reference。未确认候选和已排除项不参与对比。

理由：

- 报告内容只依赖人工确认后的问题。
- 用户关注的是迁移问题是否修复，而不是源码是否发生文本变化。
- 源码文本 diff 无法直接表达“问题是否仍存在”。

### 2. 沿用 `recheck_runs` / `diff_items`

继续使用现有 `recheck_runs` 记录一次复检任务，`diff_items` 记录每条差异。新增字段或扩展 JSON 快照，而不是引入另一套 source compare 表。

建议扩展：

- `diff_items.title`
- `diff_items.location_label`
- `diff_items.recommendation`
- `diff_items.confirmation_status`
- `diff_items.match_confidence`
- `diff_items.match_reason`
- `diff_items.old_snapshot`
- `diff_items.new_snapshot`

如果不希望立即增加大量列，可将 `old_snapshot/new_snapshot` 放在 JSONB 中，列表必要字段单独列化以支持分页、过滤和排序。

### 3. fingerprint 不依赖绝对行号

代码类 finding 的稳定身份应优先使用：

```text
source_type + rule_id + normalized_relative_path + symbol_name + normalized_anchor
```

行号只用于展示和低权重辅助匹配，不作为主 fingerprint 的唯一组成部分。

SBOM 类输入的稳定身份应优先使用：

```text
source_type + item_type + normalized_component_name + normalized_package_or_location
```

### 4. 匹配采用 exact + fuzzy 两阶段

第一阶段使用 exact fingerprint 匹配。第二阶段对 unmatched old/new 输入按同来源类型进行规则化模糊匹配。

代码类 finding 的模糊匹配优先级：

1. 相同 `ruleId` + 相同相对路径 + 相同符号 + 相同 anchor。
2. 相同 `ruleId` + 相同相对路径 + 相同 anchor，符号变化。
3. 相同 `ruleId` + 相似路径 + 相同 anchor。
4. 相同 `ruleId` + 相似上下文或 message hash。

匹配结果必须记录：

- `matchConfidence`: `HIGH`、`MEDIUM`、`LOW`
- `matchReason`: 机器可读原因，如 `EXACT_FINGERPRINT`、`SAME_RULE_PATH_SYMBOL_ANCHOR`、`SAME_RULE_ANCHOR_MOVED_PATH`

### 5. diff status 生成规则

- `RESOLVED`: base 有匹配项，target 无匹配项。
- `NEW`: target 有匹配项，base 无匹配项。
- `UNCHANGED`: base/target 匹配成功，且核心展示字段和风险字段无变化。
- `CHANGED`: base/target 匹配成功，但风险、位置、标题、建议、来源快照中的关键字段发生变化。

对于 `matchConfidence=LOW` 的匹配，仍可生成 `CHANGED` 或 `UNCHANGED`，但详情中必须暴露置信度和原因，供前端提示人工确认。

### 6. latest compare 保留，但语义收敛

`GET /api/projects/{projectId}/source/compare/latest` 继续作为代码比较页入口，但文档与实现语义应改为“latest recheck diff”，即查询当前 active source revision 相对上一可比较 source revision 的复检差异状态。

如果不存在复检结果，则返回 `NOT_STARTED`，前端可调用 `POST /api/projects/{projectId}/rechecks/latest` 创建任务。

### 7. 任务和 SSE

创建复检返回 `TaskResponse`。任务完成后写入 `recheck_runs.status`、`summary` 和 `diff_items`，并通过既有 task/project SSE 推送状态变化。前端通过 latest compare 或 task 查询恢复状态。

## Risks / Trade-offs

- [Risk] fingerprint 过强会把移动后的同一问题误判为 `RESOLVED + NEW`。  
  Mitigation: exact 失败后使用同 rule/anchor/symbol 的 fuzzy matching，并记录 match reason。

- [Risk] fingerprint 过弱会把不同问题误合并。  
  Mitigation: 分来源类型制定匹配规则，低置信度匹配必须暴露给前端，必要时后续增加人工确认。

- [Risk] old/new snapshot JSON 过大。  
  Mitigation: 列表字段列化，详情才返回 snapshot；必要时后续将大快照转存 artifact storage。

- [Risk] 旧数据缺少 symbol/anchor 字段，导致匹配质量不稳定。  
  Mitigation: 对缺失字段降级为低置信度匹配；新生成的迁移输入 reference 开始补齐 normalized identity 字段。

- [Risk] 复检任务重复创建。  
  Mitigation: 同一 project/base/target 若存在 `PENDING/QUEUED/RUNNING/SUCCEEDED` 复检，应返回已有记录或复用任务，避免重复写入 diff。

## Migration Plan

- 使用 Liquibase 扩展 `diff_items` 和必要的 migration input identity 字段。
- 为历史数据保留兼容路径：缺少 identity 字段时，复检任务基于现有 `fingerprint`、`sourceType`、`sourceRefId` 和 snapshot 尽力匹配。
- jOOQ 代码通过既有脚本重新生成并纳入源码。
- 回滚时可保留新增列，不影响旧接口；新增 API 可停止调用。

## Open Questions

- `CHANGED` 的关键字段集合是否需要按来源类型进一步细分。
- 低置信度匹配是否需要前端单独展示“需确认”，还是本期只展示 match confidence。
- 是否需要为复检结果增加下载导出能力，本期暂不纳入。
