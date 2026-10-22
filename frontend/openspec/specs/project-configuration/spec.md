# project-configuration Specification

## Purpose

定义工作台 project 节点的基础资料展示、描述编辑和环境/源码入口，使用户能核对当前项目身份、保存说明信息，并在结束编辑后继续配置迁移所需资源。

## Requirements

### Requirement: 项目基础资料

`project` Drawer SHALL 使用 `GET /api/projects/{projectId}` 展示项目名称、源架构、目标架构和描述。

#### Scenario: 查看项目

- **WHEN** 用户打开项目基础配置
- **THEN** 名称与架构 SHALL 只读，描述默认只读并提供编辑入口
- **AND** 请求失败 SHALL 展示项目详情读取失败状态

### Requirement: 编辑项目描述

描述编辑 SHALL 通过 `PATCH /api/projects/{projectId}` 保存，并支持取消恢复最近已保存内容。

#### Scenario: 保存或取消

- **WHEN** 用户确认保存描述且请求成功
- **THEN** Drawer SHALL 更新资料并退出编辑状态
- **WHEN** 用户取消编辑
- **THEN** Drawer SHALL 恢复最近已保存描述

### Requirement: 基础配置后续入口

Drawer SHALL 提供进入环境管理和源码管理的操作，描述编辑期间 SHALL 禁用这两个入口。

#### Scenario: 进入下一配置视图

- **WHEN** 描述未处于编辑态且用户选择入口
- **THEN** 工作台 SHALL 切换至 `env` 或 `assets` Drawer
