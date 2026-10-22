# frontend-code-reuse Specification

## Purpose

定义跨阶段纯逻辑复用、领域模块边界与复杂视图的职责拆分。阶段交互规范由 project-stage-runtime 定义。

## Requirements

### Requirement: Semantically equivalent frontend logic is shared

当多个前端模块对相同输入应用相同规则并期望相同输出时，应用 SHALL 通过类型化共享模块提供该常量或纯函数。共享模块 SHALL 不依赖 React 组件状态、Ant Design 渲染实例或领域 API 请求。

#### Scenario: Build drawers display shared data

- **WHEN** 构建相关 Drawer 展示通用任务状态、解析环境变量或格式化构建时间范围
- **THEN** 它们 SHALL 使用共享的类型化实现
- **AND** 空值、同日时间范围和键值解析的展示结果 SHALL 保持一致

### Requirement: Business-specific semantics remain local

应用 SHALL NOT 仅因名称或枚举值相似而合并具有不同领域文案、错误策略或交互副作用的实现。

#### Scenario: Stage-specific status text is rendered

- **WHEN** 不同业务阶段需要体现其专有状态语义
- **THEN** 阶段 SHALL 能够保留该语义
- **AND** 共享基础设施 SHALL 不覆盖或改变该文案

### Requirement: 领域 API 与类型边界

领域 API 和类型 SHALL 按业务模块组织；页面维护时 SHALL 从具体领域模块导入，不把聚合 barrel 的兼容出口视为必须长期保留的产品契约。

#### Scenario: 维护领域调用方

- **WHEN** 页面或 hook 使用项目 API
- **THEN** 调用方 SHALL 依赖对应领域模块，共享组件通过数据和回调接收业务能力

### Requirement: 复杂视图按职责拆分

复杂 Drawer SHALL 将组合入口、数据编排、输入转换与独立展示区域分离；简单表单或纯展示视图 MAY 保留轻量入口，不要求机械创建包装模块。

#### Scenario: 维护环境或业务阶段 Drawer

- **WHEN** 模块同时承担多个独立展示区域与领域状态编排
- **THEN** 维护者 SHALL 按职责拆分，并保留由对应业务规范定义的操作、反馈和请求语义

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
