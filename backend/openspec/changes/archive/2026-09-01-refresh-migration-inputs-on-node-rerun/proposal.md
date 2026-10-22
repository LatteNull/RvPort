## Why

当前依赖分析等节点重跑后，只会把新结果追加同步到迁移输入，不会清理同一源码版本下上一轮已经不存在的旧输入。这样会导致已经被新分析排除的问题仍以 `CONFIRMED` 状态进入评估报告，污染当前报告内容。

## What Changes

- 将节点结果到迁移输入的同步语义从“追加新增”调整为“当前版本替换刷新”。
- 当节点在同一 `project_id + source_revision_id + source_type` 范围内成功重跑后，先清空该来源类型下旧的当前迁移输入，再写入本次最新结果。
- 重建迁移输入时继续使用现有风险策略：`LOW` 默认为 `CANDIDATE`，其他风险等级默认为 `CONFIRMED`。
- 历史评估报告中的 `report_inputs` 快照保持不可变，不随当前迁移输入刷新而修改。
- 不新增 `STALE` 状态；当前产品语义认为源码或环境未更新前的节点重跑是刷新当前版本内容。

## Capabilities

### New Capabilities
- `migration-input-refresh`: 约束分析节点重跑后迁移输入如何按当前源码版本和来源类型刷新。

### Modified Capabilities

## Impact

- 影响后端迁移输入同步逻辑、依赖分析完成后的迁移输入写入流程，以及对应单元测试和 E2E 验证。
- 不改变报告历史快照结构，不改变前端 API 路径。
- 需要验证依赖分析重跑后旧的 `DEPENDENCY_RESULT` 输入不会继续进入新报告。
