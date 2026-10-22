## Purpose

定义 RvPort 前端持续可验证的工程质量、可访问性、样式边界与大内容渲染基线，使业务功能演进不会累积无法构建、难维护或难访问的技术债务。

## ADDED Requirements

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

前端 SHALL 按布局职责选择原语：工具栏、按钮组和简单的一维对齐 SHOULD 使用 Ant Design 的 `Flex`；响应式列布局 SHOULD 使用 Ant Design 的 `Row` 与 `Col`。具有内容语义的区域 SHALL 使用原生 `section`、`header`、`nav`、`article`、`ul` 或 `ol` 等元素。组件私有的复杂视觉、响应式规则和 CSS Grid SHALL 保留在对应的 CSS Module 中，而不是散落为 JSX 内联样式或为布局而添加无语义包装层。

所有 Ant Design 组件（包括但不限于 Form、Table、Drawer、Modal、Input、Button 和 Tag）需要调整内部样式时，实施者 SHALL 依次优先使用组件公开的 `classNames`、`styles`、Design Token、组件自身 `className` 或 `style` 属性。Form 的语义化结构槽位只是这一规则的示例，并非唯一适用组件。`:global(.ant-*)` SHALL 仅在公开接口无法覆盖时使用，并在相邻代码中说明原因和受影响的 Ant Design 结构；不得将其作为常规样式手段。

#### Scenario: Maintainer implements a simple action bar

- **WHEN** 页面需要排列按钮、筛选器或标题和操作项
- **THEN** 实现 SHOULD 使用 Ant Design `Flex` 的对齐、间距和换行能力

#### Scenario: Maintainer implements a semantic content region

- **WHEN** 页面需要构建日志、详情、导航或列表等内容区域
- **THEN** 实现 SHALL 选择与内容相符的原生语义元素
- **AND** 复杂 Grid、媒体查询与私有视觉样式 SHALL 位于该组件的 CSS Module 中

#### Scenario: Maintainer customizes an Ant Design component

- **WHEN** 实施者需要调整任意 Ant Design 组件的内部布局、间距或外观
- **THEN** 实现 SHALL 优先通过该组件公开的 `classNames`、`styles` 或 Token 接口传入样式
- **AND** 不得仅为此使用 `:global(.ant-*)` 选择器

#### Scenario: Public component styling interfaces are insufficient

- **WHEN** Ant Design 的公开样式接口无法表达某个必要的兼容性或布局需求
- **THEN** 实现 MAY 使用受组件根类名约束的 `:global(.ant-*)` 选择器
- **AND** 相邻代码 SHALL 说明无法使用公开接口的原因
