## ADDED Requirements

### Requirement: 项目创建阶段详情

项目流水线工作台 SHALL 在用户点击 `project` 节点后打开阶段抽屉，并根据 `projectId` 与 `stageId` 获取项目创建阶段详情数据。

#### Scenario: 请求项目创建阶段详情

- **WHEN** 用户点击 Workflow 中的 `project` 节点
- **THEN** 系统 SHALL 使用当前 `projectId` 与 `stageId=project` 请求阶段详情接口

#### Scenario: 展示项目基本信息

- **WHEN** 项目创建阶段详情加载成功
- **THEN** 抽屉 SHALL 展示项目名称、项目描述、源架构、目标架构、C/C++ 源码来源和首批语言

#### Scenario: 仅项目描述可编辑

- **WHEN** 用户查看项目创建阶段基本信息
- **THEN** 抽屉 SHALL 默认以只读文本展示项目描述，并在项目描述标签旁提供编辑入口
- **AND** 用户点击编辑入口后，系统 SHALL 仅将项目描述切换为可编辑输入框
- **AND** 项目名称、源架构、目标架构、C/C++ 源码来源和首批语言 SHALL 只读展示

#### Scenario: 保存项目描述

- **WHEN** 用户在项目描述编辑态确认保存
- **THEN** 系统 SHALL 调用项目创建阶段更新接口保存项目描述
- **AND** 系统 SHALL 在保存成功后恢复项目描述展示态

#### Scenario: 取消编辑项目描述

- **WHEN** 用户取消项目描述编辑
- **THEN** 系统 SHALL 恢复最近一次已保存的项目描述
- **AND** 系统 SHALL 恢复项目描述展示态

#### Scenario: 展示项目状态信息

- **WHEN** 项目创建阶段详情加载成功
- **THEN** 抽屉 SHALL 展示 x86 源环境、RISC-V 目标环境、知识库扫描、SBOM 替代性分析、迁移问题和构建验证状态

#### Scenario: 展示项目创建阶段操作

- **WHEN** 项目创建阶段详情加载成功
- **THEN** 抽屉 footer SHALL 展示继续环境管理和查看最近结果操作入口
- **AND** 保存和取消编辑操作 SHALL 位于项目描述编辑区域

#### Scenario: 继续环境管理

- **WHEN** 用户确认继续环境管理，且项目描述不处于编辑态
- **THEN** 系统 SHALL 调用项目创建阶段推进接口
- **AND** 系统 SHALL 将 workflow 当前阶段更新为环境管理

#### Scenario: 编辑期间阻止推进

- **WHEN** 用户编辑项目描述时尝试继续环境管理
- **THEN** 系统 SHALL 阻止推进操作
- **AND** 系统 SHALL 提示用户先保存或取消编辑
