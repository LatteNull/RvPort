## Why

环境模块未区分 Workflow 与 Step，表单固定使用弹窗、执行记录固定另开抽屉，破坏 Workflow 单个阶段抽屉的交互一致性。

## What Changes

- Workflow 在同一个阶段 Drawer 内切换列表、新建/编辑、脚本、历史及日志；内部返回保留列表状态。
- Step 保留环境列表面板，表单、历史与日志使用局部 Modal。
- 保留提交锁、草稿退出确认、历史分页与失败重试，不改变 API 或凭据行为。

## Capabilities

### Modified Capabilities

- `environment-management`: 明确两种视图的容器及内部返回规则。

## Impact

仅 frontend 环境阶段组合、标题导航、回归测试和对应 OpenSpec；不涉及后端。
