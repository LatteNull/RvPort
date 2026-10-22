## Why

源码对比作为人工修复后的独立节点，业务价值较弱且会让流程显得冗余。用户真正需要的是在评估报告页查看历史报告，并比较当前报告与历史报告之间的问题变化。

## What Changes

- 将“源码对比/复检”从主流程独立节点降级为评估报告页面中的报告比较能力。
- 评估报告 API 增加历史报告查看和报告比较入口，前端可在报告页查看过往报告并发起对比。
- 报告比较基于报告生成时固化的 `report_inputs.input_snapshot`，而不是动态读取当前迁移输入。
- 保留现有 recheck/diff 底层模型和兼容 API，但主流程文档不再要求独立“代码比较页”。
- 报告比较结果继续表达 `RESOLVED`、`UNCHANGED`、`NEW`、`CHANGED`，并支持分页、排序和过滤。

## Capabilities

### New Capabilities

- `report-comparison-runtime`: 定义评估报告历史比较能力，包括比较创建、自动选择上一份可比较报告、差异项查询和详情。

### Modified Capabilities

- `migration-report-runtime`: 增加历史报告列表和报告比较入口要求。
- `manual-fix-source-update-flow`: 移除源码对比作为人工修复后的独立主流程节点要求，改为引导用户回到评估报告查看历史比较。
- `backend-api-design`: 增加报告比较 API 契约，并标记源码比较 API 为兼容能力而非主流程入口。

## Impact

- 影响报告模块 API、报告比较服务、报告输入快照比较逻辑和相关 E2E。
- 可能复用现有 `recheck_runs`、`diff_items`、`RecheckDiffRuntimeService`，但对外入口需要从 source-oriented 调整为 report-oriented。
- 前端后续需要在评估报告页展示历史报告列表和“与历史报告对比”按钮，但本 change 只约束后端契约。
