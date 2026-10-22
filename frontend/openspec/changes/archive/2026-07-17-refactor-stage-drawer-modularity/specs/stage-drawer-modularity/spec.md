## ADDED Requirements

### Requirement: 复杂阶段 Drawer 使用稳定的职责边界

系统 SHALL 将同时拥有多视图、本地表单状态或领域请求编排的 StageDrawer 模块按组合入口、状态编排和展示区域拆分。公开 `StageDrawerProps` 调用方式以及用户可观察的业务行为必须保持不变。

#### Scenario: 用户操作已迁移的阶段 Drawer

- **WHEN** 用户在已迁移的阶段 Drawer 中提交表单、切换视图、确认危险操作或关闭 Drawer
- **THEN** 原有 API 调用、缓存刷新、反馈文案、确认语义、返回和关闭行为保持不变

### Requirement: 展示组件不选择领域 API

系统 SHALL 将领域 query、mutation、缓存失效和操作回调保留在阶段模块的编排边界；抽出的展示组件通过显式 props 接收数据、加载状态和回调。

#### Scenario: 渲染阶段内容区域

- **WHEN** 阶段 Drawer 渲染表单、列表、详情、标题或 Footer
- **THEN** 对应展示组件不直接调用项目领域 API，并由编排边界提供其所需状态和操作

### Requirement: 简单阶段 Drawer 不进行机械拆分

系统 SHALL 仅在模块存在独立状态/API 编排或多个独立展示区域时增加 hook 或组件目录；纯展示或简单单表单 Drawer MAY 保持轻量入口结构。

#### Scenario: 维护简单阶段 Drawer

- **WHEN** 阶段 Drawer 只展示静态阶段信息或没有可独立拆分的职责
- **THEN** 系统不要求创建无实际职责的 hook、chrome 或包装组件
