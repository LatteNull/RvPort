# frontend-quality-baseline Specification

## Purpose

定义 RvPort 前端持续可验证的工程质量、可访问性、样式边界与大内容渲染基线，使业务功能演进不会累积无法构建、难维护或难访问的技术债务。

## Requirements

### Requirement: Frontend quality gates remain passing

前端仓库 SHALL 使 OpenSpec 严格校验、格式检查、lint 和 TypeScript 类型检查通过。规格 SHALL 提供有效且非占位的 Purpose。

#### Scenario: Maintainer validates the frontend

- **WHEN** 维护者运行项目规定的质量检查
- **THEN** OpenSpec、format、lint 与 typecheck SHALL 全部通过

### Requirement: Forms use accessible native input semantics

表单 SHALL 保留可访问标签，并为账号、邮箱、URL、密码等输入提供相应的 `type`、`autocomplete` 和拼写检查行为。
编辑或新增类弹层的表单 SHALL 在关闭后卸载并清除字段状态，避免下次打开携带上次输入。表单初始化和重置 SHALL 仅在其已打开时执行，避免对未挂载表单实例进行操作。

#### Scenario: User edits identity and connection fields

- **WHEN** 用户在用户管理、邮件配置或源码导入中填写账号、邮箱或地址
- **THEN** 浏览器 SHALL 提供与字段语义相符的键盘和自动填充能力

#### Scenario: Modal form closes and reopens

- **WHEN** 用户关闭后再次打开新增或编辑表单
- **THEN** 上一次未提交的字段状态 SHALL 不被保留
- **AND** 当前实体的初始值 SHALL 在弹层打开后设置

### Requirement: Long log content remains usable

日志查看器 SHALL 在大量日志行时避免一次性创建无界 DOM，同时保留用户查看、复制和下载完整日志的能力。

#### Scenario: User opens a long log

- **WHEN** 日志行数超过初始显示上限
- **THEN** 查看器 SHALL 显示初始内容和明确的展开操作
- **AND** 用户 SHALL 能查看、复制或下载完整内容

### Requirement: Layout primitives preserve semantic and styling boundaries

前端 SHALL 按布局职责选择原语：工具栏、按钮组和简单的一维对齐 SHOULD 使用 Ant Design 的 `Flex`；桌面列布局 MAY 使用 Ant Design 的 `Row`、`Col` 或组件私有 CSS Grid。具有内容语义的区域 SHALL 使用原生 `section`、`header`、`nav`、`article`、`ul` 或 `ol` 等元素。组件私有的复杂视觉、桌面宽度规则和 CSS Grid SHALL 保留在对应的 CSS Module 中，而不是散落为 JSX 内联样式或为布局而添加无语义包装层。

#### Scenario: Maintainer implements a simple action bar

- **WHEN** 页面需要排列按钮、筛选器或标题和操作项
- **THEN** 实现 SHOULD 使用 Ant Design `Flex` 的对齐、间距和换行能力

#### Scenario: Maintainer implements a semantic content region

- **WHEN** 页面需要构建日志、详情、导航或列表等内容区域
- **THEN** 实现 SHALL 选择与内容相符的原生语义元素
- **AND** 复杂 Grid、桌面宽度媒体查询与私有视觉样式 SHALL 位于该组件的 CSS Module 中

#### Scenario: Maintainer adapts a layout to desktop widths

- **WHEN** 页面需要针对可用宽度调整布局
- **THEN** 实现 SHALL 使用 Ant Design 的 1200px、1600px 和 1920px 三个桌面断点
- **AND** 1024–1199px SHALL 作为紧凑桌面兜底，1200–1599px SHALL 作为标准桌面，1600–1919px SHALL 作为宽屏桌面，1920px 以上 SHALL 作为超宽屏桌面
- **AND** 紧凑差异 SHALL 使用 `max-width: 1199px`，宽屏与超宽屏差异 MAY 按需使用 `min-width: 1600px` 和 `min-width: 1920px`
- **AND** 低于 1024px 时 SHALL 保持桌面最小宽度并允许页面横向滚动，不渲染移动端专用布局

### Requirement: Ant Design 样式通过公开接口定制

Ant Design 组件内部样式 SHALL 优先使用公开的 `classNames`、`styles`、Design Token、`className` 或 `style`。仅在公开接口无法表达必要布局或兼容需求时 MAY 使用受组件根类名约束的 `:global(.ant-*)`，并在相邻代码说明原因。

#### Scenario: Maintainer customizes an Ant Design component

- **WHEN** 实施者需要调整任意 Ant Design 组件的内部布局、间距或外观
- **THEN** 实现 SHALL 优先通过该组件公开的 `classNames`、`styles` 或 Token 接口传入样式
- **AND** 不得仅为此使用 `:global(.ant-*)` 选择器

#### Scenario: Public component styling interfaces are insufficient

- **WHEN** Ant Design 的公开样式接口无法表达某个必要的兼容性或布局需求
- **THEN** 实现 MAY 使用受组件根类名约束的 `:global(.ant-*)` 选择器
- **AND** 相邻代码 SHALL 说明无法使用公开接口的原因

### Requirement: 主内容可被键盘快速定位

应用 SHALL 在每个包含主内容的共享 layout 中提供跳过导航链接和唯一的 `main` 地标。跳过链接在普通视觉状态下可以隐藏，但在键盘焦点可见时必须可见，且跳转后焦点目标不得被固定 Header 遮挡。

#### Scenario: 键盘用户跳过站点框架

- **WHEN** 用户在页面起始位置通过 Tab 获得跳过链接焦点并激活该链接
- **THEN** 焦点移动到当前路由页面的主内容起点
- **AND** 用户无需遍历 Header 或管理 Tab 才能访问主内容

### Requirement: 远程数据表提供一致的整表空状态

共享远程数据表在请求成功且当前结果为空时 SHALL 默认保留筛选与业务操作，并以独立状态面板替代表头、分页和滚动区域。筛选无结果 SHALL 提供清空筛选操作，请求失败且没有可显示的缓存数据时 SHALL 提供重新加载操作。只有表头本身承担数据结构说明时 MAY 显式保留表格内空状态。

#### Scenario: 用户打开没有数据的列表

- **WHEN** 远程数据请求成功且返回零条记录
- **THEN** 页面 SHALL 显示独立空状态面板
- **AND** 表头、分页和表格滚动区域 SHALL 不显示
- **AND** 工具栏中的筛选与业务操作 SHALL 保留

#### Scenario: 当前筛选条件没有匹配记录

- **WHEN** 用户应用筛选后远程数据请求返回零条记录
- **THEN** 空状态 SHALL 明确说明没有匹配结果
- **AND** 用户 SHALL 能清空筛选并重新加载未筛选的数据

#### Scenario: 空列表请求失败

- **WHEN** 远程数据请求失败且没有可显示的缓存数据
- **THEN** 页面 SHALL 显示与普通空状态同层级的错误状态
- **AND** 用户 SHALL 能重新加载数据

### Requirement: 共享浮层和动效不会破坏用户控制

共享 Modal 与 Drawer 的可滚动正文 SHALL 阻止 overscroll 传递到页面背景。循环工作流动效 SHALL 在用户请求减少动态效果时停止，并保留非动态的状态辨识。

#### Scenario: 用户启用减少动态效果

- **WHEN** 系统媒体查询 `prefers-reduced-motion` 为 `reduce`
- **THEN** 工作流边线不得播放无限循环动画
- **AND** 当前激活或悬浮关联关系仍可通过静态样式辨识

### Requirement: 共享生成的输入控件具有可访问语义

共享筛选表单和脱离 `Form.Item` 的编辑输入 SHALL 具有可访问名称和稳定标识；原生输入 SHALL 提供 HTML `name`，复合控件 SHALL 提供稳定 `id`，并按用途配置 autocomplete。仅在用户明确进入编辑时 MAY 进行受控聚焦，且不得使用无条件 `autoFocus` 抢占焦点。

#### Scenario: 使用辅助技术访问筛选和构建配置输入

- **WHEN** 用户聚焦任一共享筛选控件或构建配置输入
- **THEN** 辅助技术能读取该控件的用途
- **AND** 浏览器可从 `name` 与 autocomplete 获得正确的输入语义
