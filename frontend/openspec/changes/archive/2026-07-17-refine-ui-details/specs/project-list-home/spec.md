## ADDED Requirements

### Requirement: Project card grid adapts to available width

项目列表页 SHALL 使用自适应项目卡片网格，在保持卡片最小可读宽度的同时填满可用内容区域。

#### Scenario: Project grid has fewer columns on medium viewport

- **WHEN** `/home` 在中等宽度窗口中只能展示三列或四列项目卡片
- **THEN** 项目卡片列 SHALL 自动拉伸填满可用内容宽度
- **AND** 页面右侧 SHALL NOT 因固定卡片列宽出现明显大块空白

#### Scenario: Project grid keeps minimum card width

- **WHEN** `/home` 项目卡片网格根据窗口宽度重新排布
- **THEN** 每个项目卡片列 SHALL 保持足够的最小宽度以承载项目名称、风险数、阶段条和状态字段
