## Purpose

定义 RvPort 前端在重型编辑器和高频布局计算上的资源加载边界，确保性能优化不改变既有业务交互或编辑能力。

## ADDED Requirements

### Requirement: Heavy editors load only when their interface is rendered

应用 SHALL 不在普通项目浏览或仅打开不含编辑器内容的 Drawer 视图时下载 CodeMirror 或 Monaco 的实现及语言资源；当用户进入需要编辑器的视图时，应用 SHALL 显示稳定的加载占位，并在资源就绪后保留既有编辑、只读、语言和行号行为。

#### Scenario: User browses without opening an editor

- **WHEN** 用户访问项目工作台或打开未渲染编辑器的 Drawer 视图
- **THEN** 应用 SHALL NOT 因此下载对应编辑器的实现和语言资源

#### Scenario: User enters an editor view

- **WHEN** 用户打开需要 CodeMirror 或 Monaco 的编辑、脚本或日志视图
- **THEN** 应用 SHALL 显示不造成明显布局跳动的加载状态
- **AND** 编辑器资源加载完成后 SHALL 呈现该视图原有的内容与交互能力

### Requirement: Repeated layout and editor renders avoid avoidable work

自适应表格和编辑器 SHALL 在输入未实质变化时避免重复状态更新、DOM 测量结果提交或编辑器扩展重建。

#### Scenario: Table dimensions are measured repeatedly

- **WHEN** ResizeObserver、窗口尺寸事件或组件重渲染产生与当前值相同的表格高度
- **THEN** 表格 SHALL NOT 因相同高度再次提交 React 状态更新

#### Scenario: Editor parent rerenders with unchanged input

- **WHEN** 编辑器父组件重渲染且编辑器内容、语言和高亮行没有变化
- **THEN** 编辑器 SHALL 保留其既有扩展和内容状态，而不重新创建等价配置
