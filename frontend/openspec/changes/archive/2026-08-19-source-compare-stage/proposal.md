## Why

人工修复后的源码版本与复检结果目前混在人工修复 Drawer 中，用户无法独立查看前后版本、问题变化和差异明细，也无法在复检完成后清晰地进入构建验证。

## What Changes

- 新增“源码对比”阶段 Drawer，展示当前激活源码版本与上一源码版本的复检上下文。
- 接入现有 latest compare、创建 latest recheck、差异项分页和差异详情 API，呈现已解决、未变化、新增和已变化的问题。
- 按复检状态提供空态、复检中、失败重试和完成态，并在完成后提供进入构建验证的入口。
- 将复检摘要从人工修复 Drawer 中移除；人工修复仅保留线下修复说明与前往源码管理入口。
- 在工作流中启用独立的源码对比节点，使其位于人工修复之后、构建验证之前。

## Capabilities

### New Capabilities

- `source-compare-stage`: 修复后源码版本复检、差异浏览和构建验证衔接。

### Modified Capabilities

- 无。

## Impact

- 前端工作流拓扑、StageDrawer 分发和人工修复 Drawer。
- 前端项目源码对比 API 类型与请求封装，复用已有后端 `/source/compare/latest`、`/rechecks/latest` 和 diff item 接口。
- 不新增依赖，不修改后端接口或数据模型。
