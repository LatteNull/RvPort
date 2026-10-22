## Why

缩放后实测端点带有小数偏移，自身竖线被误判为交叉线，导致“修复后更新源码”标签靠在竖线上。

## What Changes

- 按边 ID 排除自身竖线，使标签保持在横线段上方。
- 补充小数端点偏移的回归测试。

## Capabilities

### Modified Capabilities

- `frontend-workflow-readability`: 缩放后回流标签仍位于横线段上方。

## Impact

仅修改 frontend 工作流路由及测试，不改变节点位置或业务关系。
