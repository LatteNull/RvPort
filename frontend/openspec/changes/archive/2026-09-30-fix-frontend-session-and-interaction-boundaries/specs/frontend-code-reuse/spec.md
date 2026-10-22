## ADDED Requirements

### Requirement: 复杂页面按实际职责分离且仅保留有效入口

依赖分析与模型配置页面 SHALL 将数据查询和提交、复杂列表、绑定表单及展示转换分离至领域 Hook、components 和 presentation 模块，页面入口 SHALL 组合实际视图。迁移后的 API 与类型 SHALL 由调用方直接使用具体模块，SHALL NOT 保留兼容 re-export、旧实现或纯转发包装。

#### Scenario: 模型配置与依赖分析结构调整

- **WHEN** 页面数据与展示职责分离
- **THEN** 查询及提交 SHALL 保持唯一所有权，既有缓存 key、刷新规则、业务文案、导航与样式 SHALL 保持有效
- **AND** 原入口中的被替代代码及无生产调用方的旧构建解析、旧 Agent 结果读取封装 SHALL 删除，测试 SHALL 随实际模块迁移

### Requirement: 跨阶段详情展示使用公共依赖边界

多个阶段共同使用的详情展示组件及其必要展示依赖 SHALL 位于最近的公共 components/ 或 utils/；阶段 SHALL 直接依赖公共模块，不横向引用其他阶段内部组件、工具或 CSS Module。领域专属文案与动作 SHALL 保留明确归属。

#### Scenario: 报告与业务阶段复用详情

- **WHEN** 报告与知识库或依赖分析展示相同 Finding 或依赖结果详情
- **THEN** 调用方 SHALL 使用公共详情实现，保留现有数据、代码定位、加载/错误状态、导航和视觉
- **AND** 公共组件 SHALL 通过类型化数据与回调接收业务能力，不反向依赖具体阶段

#### Scenario: 移动共享组件及样式

- **WHEN** 共享详情被提升到公共目录
- **THEN** 其必要展示依赖与共同样式 SHALL 一并建立公共归属，调用方与就近测试 SHALL 同步导入
- **AND** 前端 SHALL 不保留旧阶段路径的兼容 re-export 或仅转发的包装组件
