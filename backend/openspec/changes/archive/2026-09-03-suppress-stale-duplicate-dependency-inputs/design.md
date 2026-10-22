## Context

当前依赖分析结果表中，最新成功 run 已经能把同一个 `gcc` 收敛为一条结果，但历史 run 和历史迁移输入中仍可能存在早期逻辑写入的重复项。例如同一源码版本下可能同时存在 `build:gcc`、`compile-db:gcc`、`execve:gcc` 或旧的 `MEDIUM/REPO_AVAILABLE` 引用。由于评估报告只读取 `CONFIRMED` 迁移输入，旧引用一旦被确认，就可能在后续报告中继续出现。

现有 `MigrationInputService.syncSourceRefs()` 已按 `project_id + source_revision_id + source_type` 删除并重建，但仍需要补齐两类边界：一是当前输入池读取时不能消费过期依赖结果；二是已有数据库中的重复 `DEPENDENCY_RESULT` 需要一次性收敛或清理。

## Goals / Non-Goals

**Goals:**
- 当前源码版本下，依赖分析重跑成功后，`DEPENDENCY_RESULT` 迁移输入只指向本次最新成功 run 的结果。
- 报告 readiness、输入预览和报告生成不得默认消费旧 run 的依赖输入。
- 对已有重复依赖输入进行安全清理：保留最新有效结果对应引用，删除或排除同语义旧引用。
- 保持历史报告快照不变，避免改变用户已下载或已归档的报告内容。
- 测试覆盖正常流程、异常流程和 edge case。

**Non-Goals:**
- 不删除历史依赖分析 run 和历史 result item。
- 不修改历史报告 `report_inputs` 快照。
- 不引入跨发行版依赖 alias 或更复杂的依赖语义合并。
- 不改变前端展示结构，只保证后端返回的当前输入池和报告输入收敛。

## Decisions

### 1. 用“当前有效依赖 run”作为报告输入边界

报告生成、readiness 和输入预览在读取 `DEPENDENCY_RESULT` 时，应确认对应 `source_ref_id` 属于同一项目、同一源码版本下最新成功依赖分析 run。这样可以避免旧 run 的 `CONFIRMED` 引用继续进入新报告。

替代方案是只依赖重跑时清表。这个方案对未来数据有效，但不能解决已有数据库里的旧 confirmed 引用，因此不足够。

### 2. 清理当前输入池，不清理历史报告快照

已有重复迁移输入应在迁移脚本或受控维护逻辑中清理当前 `migration_input_refs`。历史 `report_inputs` 已经是不可变快照，不能被回写修改。

清理策略优先级：
- 保留属于最新成功依赖分析 run 的引用。
- 同一语义重复时，优先保留 `CONFIRMED`，其次保留最新创建的引用。
- 被删除的引用不得影响已生成报告快照。

### 3. 语义重复 key 使用稳定展示语义

当前输入池层面的重复判断不需要复刻完整依赖分析 dedupe 逻辑，可使用迁移输入可见字段形成稳定 key：`project_id + source_revision_id + source_type + issue_title + location_label`。对工具类重复可额外归一化 `build:gcc`、`compile-db:gcc`、`execve:gcc` 为 `tool:gcc`，避免同一工具多来源重复。

替代方案是直接用 `source_ref_id` 去重，但旧数据每条 result item id 都不同，无法解决重复。

### 4. 新同步路径继续以完整替换为准

依赖分析成功后仍走 `deleteBySourceType()` 再插入本次 result ids。这个行为符合之前“重跑清空旧输入、不继承旧排除”的决策。新 change 不回退到继承旧状态。

## Risks / Trade-offs

- [Risk] 清理逻辑误删用户手动确认的旧输入。→ 只清理当前源码版本、当前 source type，并优先保留 latest run 的结果；历史报告快照不变。
- [Risk] “同语义重复 key”过粗导致不同依赖被合并。→ 工具类做有限归一化，库和包仍保留具体 location/name；测试覆盖 gcc 多来源重复、libgcc/libgcc_s 不应互相合并。
- [Risk] 报告读取增加关联查询复杂度。→ 将过滤封装在 repository/service 层，避免前端或 report runtime 分散实现。
- [Risk] 旧报告仍展示重复项。→ 这是有意保留的历史快照行为；如果需要修改历史报告，应单独设计再生成或重新归档流程。

## Migration Plan

1. 新增 Liquibase 清理脚本或受控启动迁移，将当前 `migration_input_refs` 中的重复 `DEPENDENCY_RESULT` 收敛。
2. 更新报告 readiness、输入预览和报告生成查询，过滤不属于最新成功依赖 run 的依赖输入。
3. 更新依赖分析同步测试，确认重跑后旧依赖输入清空且不继承旧状态。
4. 增加 E2E fixture：构造旧 run confirmed gcc + 新 run candidate gcc，确认报告 readiness 和输入预览只返回当前有效结果。
5. 部署后无需修改历史报告 artifact。

## Open Questions

- 是否需要给管理员提供显式“清理当前输入池”的测试/维护 API？当前倾向不需要，使用迁移脚本即可。
- 工具类 location 归一化范围是否只覆盖 `build:`、`compile-db:`、`execve-summary:`、`execve:`？当前建议先限制在这些已观测来源。
