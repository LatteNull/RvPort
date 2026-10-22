## ADDED Requirements

### Requirement: 项目流水线摘要卡片视觉层级

项目流水线工作台 SHALL 为顶部项目摘要卡片提供与信息语义对应的轻量背景图，并保持摘要文本和页面交互清晰可读。

#### Scenario: 摘要卡片展示对应背景图

- **WHEN** 项目概览数据加载成功并展示顶部四张摘要卡片
- **THEN** 项目、总体风险、风险问题数量和当前阶段卡片 SHALL 分别展示对应的背景图
- **AND** 背景图 SHALL 位于卡片右下角且不占用内容布局空间

#### Scenario: 摘要文本展示状态颜色

- **WHEN** 项目概览数据加载成功
- **THEN** 摘要卡片主标题 SHALL 使用 `16px/20px` 和 `500` 字重，辅助文本 SHALL 使用 `12px/20px`
- **AND** 总体风险和风险问题数量 SHALL 使用红色 `#FF3737`
- **AND** 当前阶段 SHALL 使用当前 Ant Design 主题主色

#### Scenario: 背景图不改变工作台行为

- **WHEN** 用户查看或刷新项目流水线工作台
- **THEN** 摘要卡片背景图 SHALL NOT 改变项目概览数据、Workflow 状态或页面操作能力
