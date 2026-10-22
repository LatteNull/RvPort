## Context

见 `proposal.md`。项目已具备共享请求客户端、TanStack Query、React Router、BaseDrawer/BaseModal 等稳定边界；本 change 仅恢复工程质量并优化这些边界的使用方式。

## Goals / Non-Goals

**Goals:**

- 让 OpenSpec、格式、lint、类型检查恢复为可重复通过的质量门禁。
- 降低大型 UI 模块的维护和渲染风险，且不改变用户可观察业务行为。
- 用已有 Ant Design、React 与 CSS 能力修复可访问性和大内容表现。

**Non-Goals:**

- 不重写领域 API、替换 UI 库或引入新的状态管理/虚拟列表依赖。
- 不改变页面信息架构、产品文案或后端数据语义。

## Decisions

### 先恢复可验证性，再做结构拆分

规格元数据、格式、lint 和 typecheck 是后续重构的安全网，因此优先修复；每一组类型修复都与测试 fixture 同步，避免以放宽类型掩盖 API 不一致。

### 以责任边界拆分 Stage Drawer

将详情、历史列表、日志/表单和数据 orchestration 拆为同目录模块，`index.tsx` 保持组合入口。不会按行数机械拆分，也不会把领域请求移动进共享组件。

### 保持 Ant Design 的公开样式接口

优先使用组件 token、`styles` 与 `classNames`，局部 SCSS 仅负责页面布局与业务视觉。编辑器和第三方画布的全局 class 因没有公开 slot 而保留在局部根选择器下。

### 用无依赖的分段渲染保护日志

日志初次只渲染有限行数，用户可显式展开其余内容；完整下载、复制和顺序不变。这比引入新的虚拟列表运行时依赖更适合当前日志组件。

## Risks / Trade-offs

- [Risk] 模块拆分遗漏透传状态。→ Mitigation：先补齐既有行为测试并逐模块迁移。
- [Risk] 样式迁移造成视觉回归。→ Mitigation：保留局部根 class，并在受影响 Drawer 上进行视觉检查。
- [Risk] 日志分段渲染隐藏诊断信息。→ Mitigation：提供明确的“显示全部”及完整复制/下载入口。

## Migration Plan

1. 修复规格和质量门禁，建立全绿基线。
2. 分批拆分大型 Stage Drawer 并运行对应测试。
3. 迁移样式、表单和日志表现，执行全套验证；每项均可独立回退。
