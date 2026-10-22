## ADDED Requirements

### Requirement: 人工修复阶段 Drawer

项目流水线工作台 SHALL 在用户点击 `manual` 节点或从评估报告进入人工修复时，打开专属人工修复 Drawer，并使用当前 `projectId` 查询最新源码对比状态。

#### Scenario: 展示线下修复上下文

- **WHEN** 人工修复 Drawer 加载成功
- **THEN** Drawer SHALL 展示当前 active 源码版本、上一可比较源码版本和最近复检状态
- **AND** SHALL 明确提示用户在线下完成源码修改后回到源码管理更新源码

#### Scenario: 暂无可比较源码版本

- **WHEN** 项目不存在上一可比较源码版本或最近复检尚未开始
- **THEN** Drawer SHALL 展示对应状态说明
- **AND** SHALL 保留前往源码管理的入口

### Requirement: 不提供在线修复

人工修复 Drawer SHALL NOT 提供在线代码编辑、自动 patch、一键修复、处理备注或修复记录保存能力。

#### Scenario: 用户需要修复问题

- **WHEN** 用户需要处理迁移问题
- **THEN** Drawer SHALL 引导用户在线下修改源码
- **AND** SHALL 将源码提交行为委托给源码管理阶段

### Requirement: 返回源码管理更新修复版本

人工修复 Drawer SHALL 将源码更新操作导向 `assets` 阶段的源码管理 Drawer，而不在人工修复 Drawer 内嵌上传或 Git 更新表单。

#### Scenario: 前往源码管理

- **WHEN** 用户在人工修复 Drawer 确认“前往源码管理”
- **THEN** 系统 SHALL 关闭当前人工修复 Drawer 并聚焦或打开 `assets` 阶段
