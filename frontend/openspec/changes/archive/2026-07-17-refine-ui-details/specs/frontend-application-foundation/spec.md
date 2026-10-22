## ADDED Requirements

### Requirement: Authenticated content container

认证后主布局 SHALL 为路由页面提供统一的内容容器，用于控制普通业务页面的最大宽度、居中显示和横向留白。

#### Scenario: Authenticated page renders in main layout

- **WHEN** 认证后的普通业务页面通过 `MainLayout` 渲染
- **THEN** 页面内容 SHALL 位于统一内容容器内
- **AND** 内容容器 SHALL 居中显示并限制最大宽度

#### Scenario: Medium viewport uses restrained horizontal padding

- **WHEN** 浏览器处于中等宽度窗口或右侧打开调试面板
- **THEN** 主布局 SHALL 避免使用过大的固定横向 padding 造成有效内容区域明显缩小

#### Scenario: Header and content align

- **WHEN** 主布局 Header 和内容区同时渲染
- **THEN** Header 的横向留白 SHALL 与内容区保持一致的视觉对齐关系
