## Context

RvPort 前端当前以 Ant Design 作为唯一运行时 UI 组件库。`src/components/BaseModal` 已经提供了一个较薄的 Modal 二次封装：保留 Ant Design 组件能力，只统一 `visible` API、默认宽度、header/body/footer 的基础样式和 `styles` 合并规则。

Drawer 与 Modal 同属于高频反馈/容器组件。后续工作台阶段详情、编辑表单、扫描结果、报告明细等场景都适合以右侧 Drawer 承载。如果每个业务模块直接使用 Ant Design `Drawer`，会导致样式和 API 约定分散。

用户指定 Figma `node-id=28-475` 作为主体参考。当前可读取到的设计上下文显示该节点是白色、相对定位、占满父容器的主体矩形。因此本 change 将其理解为 Drawer 的 `section` / body 基础主体，而不是完整抽屉结构。

## Goals / Non-Goals

**Goals:**

- 新增通用 `BaseDrawer`，封装方式对齐 `BaseModal`。
- 使用 `visible` 作为项目内统一显隐 API，并映射到 Ant Design Drawer 的 `open`。
- 默认右侧弹出，保留 Ant Design Drawer 的 `placement` 可覆盖能力。
- 统一 Drawer 的白色主体、header/body/footer 分区、body 滚动和 footer 对齐。
- 支持 `styles` 与默认 styles 合并，允许业务场景局部覆盖。
- 支持 `BaseDrawer` 与 `BaseModal` 统一的标题对象写法，用于渲染主标题和副标题。
- 保持组件为轻量基础封装，不承载业务按钮文案或业务流程。

**Non-Goals:**

- 不迁移现有业务页面到 `BaseDrawer`。
- 不新增业务抽屉内容组件。
- 不引入新的设计 token 层、CSS 变量体系或新依赖。
- 不破坏 `BaseModal` 的现有 title ReactNode 用法。
- 不统一所有 Ant Design overlay 组件。

## Decisions

### capability 使用 `common-ui`

通用 Drawer 属于可复用 UI 组件能力，不应继续放在 `frontend-application-foundation`。`frontend-application-foundation` 覆盖 package、router、provider、request、mock 和质量自动化，范围过大且名称偏重；通用 UI 组件应由更聚焦的 `common-ui` capability 承载。

后续可逐步把 `BaseModal`、`BaseDrawer`、反馈桥接和其他通用容器纳入 `common-ui` 规格中。

### BaseDrawer 保持薄封装

`BaseDrawer` 应像 `BaseModal` 一样保留 Ant Design Drawer 的能力，而不是创建复杂业务抽象。它只统一项目内基础 API 和结构样式：

- `visible` -> `open`
- `title` -> `title`
- `footer` -> `footer`
- `children` -> `children`
- `styles` -> 与默认 Drawer styles 合并

业务 footer 按钮、表单提交、异步状态、关闭确认等仍由业务组件负责。

`BaseDrawer` 和 `BaseModal` 的 `title` 应保持兼容：既允许继续传入原有 `ReactNode`，也允许传入 `{ title, subTitle }` 对象，由 Base 层统一渲染主标题和副标题。业务组件不应为常见标题结构重复编写 header DOM。

抽屉尺寸同样属于业务页面策略。`BaseDrawer` 只提供默认 `size` 和透传能力；当不同阶段或不同业务内容需要不同宽度时，应由页面层根据业务上下文动态传入 `size`，而不是在 `BaseDrawer` 内部感知业务阶段。

抽屉内容也属于业务页面策略。以项目流水线为例，Workflow 节点点击只负责暴露阶段标识，Project Detail 页面根据 `stageId` 选择对应内容区、标题和尺寸。`BaseDrawer` 不感知 Workflow、阶段状态或业务表单结构。

由于每个 Workflow 节点后续展示的表单、结果和操作都不同，阶段抽屉内容应按节点拆分为独立组件，而不是集中在一个大型 `switch` 文件中。页面层只持有选中阶段状态；`StageDrawer` 负责标题、宽度和内容组件调度；具体节点内容组件负责各自业务展示。

### 使用 Ant Design semantic styles

Ant Design 6 的 Drawer 支持 semantic `styles` 槽位，包括 `section`、`header`、`body`、`footer`、`wrapper`、`mask` 等。因此 `BaseDrawer` 可以复用 `BaseModal` 的 styles merge 模式，避免散落全局 CSS 覆盖。

建议默认结构：

```text
Drawer
  root / mask
    wrapper
      section: 白色主体，display flex column，overflow hidden
        header: 固定顶部，底部分割线
        body: flex 1，可滚动
        footer: 固定底部，顶部分割线，操作按钮右对齐
```

### 主体视觉参考 `node-id=28-475`

Figma `node-id=28-475` 当前可读信息为白色主体容器。实现时应将 Drawer `section` 或主体容器默认设置为白色、相对定位、占满抽屉区域，并在其内部建立 header/body/footer 分区。

如果后续需要更完整的抽屉视觉细节，应补充完整 Drawer 节点或截图，而不是从 `28-475` 单个白色矩形推导 header/footer 设计。

## Risks / Trade-offs

- [Risk] `BaseDrawer` 过早内置业务 footer 按钮会限制复用。→ Mitigation: footer 只接受 ReactNode，不内置按钮文案。
- [Risk] Figma 节点只提供主体矩形，缺少完整 Drawer 结构。→ Mitigation: 将其仅作为主体白色容器依据，其他结构对齐 `BaseModal` 和 Ant Design semantic slots。
- [Risk] 业务场景可能需要不同宽度或 placement。→ Mitigation: 默认右侧弹出，并使用 Ant Design Drawer 推荐的 `size` 控制抽屉尺寸，同时允许业务覆盖 `placement` 等非接管 props。
- [Risk] 与 `BaseModal` 的样式合并工具重复。→ Mitigation: 本 change 可先各自实现小型 merge 函数；后续若重复明显，再抽公共 helper。
