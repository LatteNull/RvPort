## ADDED Requirements

### Requirement: 环境 Drawer 保持稳定功能入口

系统 SHALL 将环境 Drawer 的内部实现按状态编排、展示和输入转换拆分，同时保持既有环境管理交互与调用入口不变。

#### Scenario: 用户执行既有环境操作

- **WHEN** 用户在环境 Drawer 中创建、编辑、检查、采集、运行脚本或查看执行记录
- **THEN** 既有视图切换、确认、反馈、缓存刷新和返回行为保持不变
