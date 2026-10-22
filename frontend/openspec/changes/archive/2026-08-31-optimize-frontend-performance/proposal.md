## Why

生产构建显示编辑器依赖产生 536 KB gzip 的 CodeMirror chunk 与 927 KB gzip 的 Monaco API chunk。现有路由和多数 Drawer 已懒加载，但编辑器的下载触发点与少量高频渲染路径仍可进一步收敛，需要在不改变业务流程的前提下建立可验证的性能基线。认证背景按产品要求保持现有资源与视觉，不属于本 change 的优化范围。

## What Changes

- 将 CodeMirror 等重型编辑器资源的加载时机收敛到实际显示编辑器的交互，保留 Monaco 的现有按需加载与预加载体验。
- 消除编辑器和自适应表格中的不必要计算、状态更新与重渲染触发。
- 为生产构建增加面向关键资源和按需加载边界的可重复检查，防止后续回归。

## Capabilities

### New Capabilities

- `frontend-performance-optimization`: 定义认证资源、重型编辑器与高频渲染路径的可观察性能边界和验证要求。

### Modified Capabilities

<!-- 无。现有业务能力的功能契约不变。 -->

## Impact

- 受影响区域：`src/components/CodeMirrorEditor/`、`src/components/MonacoEditor/`、`src/components/BaseTable/`，以及相关 stage Drawer 和测试。
- 不变更 API、数据模型、权限语义或运行时依赖；构建配置仅在需要记录可验证产物边界时调整。
