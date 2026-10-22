## MODIFIED Requirements

### Requirement: 项目卡片交互

项目列表页 SHALL 提供视觉交互状态、创建入口，以及从项目卡片通过鼠标进入项目流水线工作台的导航能力，但 MUST NOT 实现报告导航或流水线执行流程。

#### Scenario: 用户悬停项目卡片

- **WHEN** 用户悬停或聚焦项目卡片
- **THEN** 卡片 SHALL 展示与设计参考一致的清晰交互视觉状态

#### Scenario: 用户点击项目卡片

- **WHEN** 用户在项目列表中点击项目卡片
- **THEN** 应用 SHALL 导航到该项目对应的 `/projects/:projectId`

#### Scenario: 用户打开新建项目弹窗

- **WHEN** 用户点击新建项目按钮
- **THEN** 页面 SHALL 打开新建项目弹窗

#### Scenario: 用户看到报告提示入口

- **WHEN** 项目条目已有可用报告
- **THEN** 卡片 SHALL 展示报告相关文本或提示，但本 change 中 MUST NOT 导航到报告页

### Requirement: 项目列表范围控制

本 change 中，项目列表首页 SHALL 保持在项目列表展示、项目创建入口和项目流水线工作台导航范围内。

#### Scenario: 审查 change 范围

- **WHEN** 审查者检查本 change
- **THEN** 报告页导航、流水线执行、键盘激活卡片和 US18 看板能力 SHALL 保持在范围外
