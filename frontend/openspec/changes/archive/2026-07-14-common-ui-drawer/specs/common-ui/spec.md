## ADDED Requirements

### Requirement: 通用 Drawer 封装

前端 SHALL 提供通用 `BaseDrawer` 组件，对 Ant Design Drawer 进行轻量二次封装，并与现有 `BaseModal` 保持一致的基础使用方式。

#### Scenario: BaseDrawer 使用 visible 控制显隐

- **WHEN** 业务组件向 `BaseDrawer` 传入 `visible`
- **THEN** `BaseDrawer` SHALL 将该值映射到 Ant Design Drawer 的 `open`

#### Scenario: BaseDrawer 渲染基础内容槽位

- **WHEN** 业务组件传入 `title`、`children` 和 `footer`
- **THEN** `BaseDrawer` SHALL 将它们分别渲染为 Drawer 标题区、主体区和底部区

#### Scenario: BaseDrawer 渲染标题对象

- **WHEN** 业务组件向 `BaseDrawer` 传入 `title={{ title, subTitle }}`
- **THEN** `BaseDrawer` SHALL 使用统一标题样式渲染主标题和副标题

#### Scenario: BaseModal 渲染标题对象

- **WHEN** 业务组件向 `BaseModal` 传入 `title={{ title, subTitle }}`
- **THEN** `BaseModal` SHALL 使用统一标题样式渲染主标题和副标题
- **AND** `BaseModal` SHALL continue to accept the existing ReactNode `title` usage

#### Scenario: BaseDrawer 默认右侧弹出

- **WHEN** 业务组件未显式传入 `placement`
- **THEN** `BaseDrawer` SHALL 默认从右侧弹出

#### Scenario: BaseDrawer 使用白色主体容器

- **WHEN** `BaseDrawer` 渲染
- **THEN** Drawer 主体 SHALL 使用白色背景、相对定位和占满抽屉区域的基础容器样式，以对齐 Figma `node-id=28-475`

#### Scenario: BaseDrawer 主体区域可滚动

- **WHEN** Drawer 主体内容超过可见高度
- **THEN** `BaseDrawer` SHALL 保持 header 和 footer 分区稳定，并使 body 区域可滚动

#### Scenario: BaseDrawer 合并样式覆盖

- **WHEN** 业务组件传入 Ant Design Drawer `styles`
- **THEN** `BaseDrawer` SHALL 将业务 styles 与默认 styles 合并
- **AND** 业务 styles SHALL 能覆盖默认 slot 样式

#### Scenario: BaseDrawer 透传 Ant Design Drawer 能力

- **WHEN** 业务组件传入其他 Ant Design Drawer props
- **THEN** `BaseDrawer` SHALL 将这些 props 透传给底层 Drawer，除非该 prop 已被 BaseDrawer 明确接管

#### Scenario: BaseDrawer 不内置业务操作

- **WHEN** `BaseDrawer` 渲染 footer
- **THEN** `BaseDrawer` SHALL NOT 内置保存、取消、确认或其他业务按钮文案
