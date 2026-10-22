## Why

当前前端已有 `BaseModal` 对 Ant Design Modal 做二次封装，用于统一弹窗的 `visible` API、标题区、主体滚动区和底部操作区样式。后续项目详情、流水线阶段信息、表单编辑和结果查看等场景会频繁使用侧边抽屉；如果直接使用 Ant Design Drawer，会重复处理 `open` / `visible` 映射、白色主体、header/body/footer 分区、滚动行为和 footer 布局。

因此需要新增 `common-ui` 能力，并在其中沉淀 `BaseDrawer`，作为通用 UI 组件层的一部分。Drawer 主体视觉以 Figma `node-id=28-475` 的白色主体容器为基础，封装方式对齐现有 `BaseModal`。

## What Changes

- 新增 `common-ui` capability，用于承载通用 UI 二次封装组件。
- 新增 `BaseDrawer` 组件，基于 Ant Design `Drawer` 进行轻量封装。
- `BaseDrawer` 提供与 `BaseModal` 一致的 `visible`、`title`、`footer`、`children` 使用方式，并继续透传 Ant Design Drawer 的其他 props。
- `BaseDrawer` 默认右侧弹出，提供白色主体、固定 header/footer、可滚动 body 的基础布局。
- `BaseDrawer` 支持 `styles` 覆盖，并与默认 styles 合并。
- 不迁移现有业务页面，不新增具体业务抽屉，不引入新依赖。

## Capabilities

### New Capabilities

- `common-ui`: 定义前端通用 UI 组件二次封装能力，包括 BaseModal、BaseDrawer 以及后续可复用 UI 容器。

### Modified Capabilities

- 无。

## Impact

- 影响前端通用组件目录：`src/components/BaseDrawer/`。
- 可能在后续 change 中逐步把业务抽屉使用方迁移到 `BaseDrawer`。
- 不影响 API、路由、mock、状态管理或现有业务行为。
