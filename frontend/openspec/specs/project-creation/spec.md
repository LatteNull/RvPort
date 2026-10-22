# project-creation Specification

## Purpose

定义从首页创建迁移项目的字段、校验、请求和创建后入口，明确进入工作台与直接开始配置环境两个动作的导航结果。共享弹窗外壳由 common-ui 定义。

## Requirements

### Requirement: 创建项目弹窗

首页 SHALL 通过弹窗采集名称、可选描述、源架构和目标架构。名称 SHALL 去除首尾空白、非空且不超过 160 字符，描述 SHALL 不超过 2000 字符；当前架构选项为 `x86_64` 到 `riscv64`。

#### Scenario: 打开或取消创建

- **WHEN** 用户点击新建项目
- **THEN** 表单 SHALL 初始化为空名称和描述及默认架构
- **WHEN** 用户取消
- **THEN** 弹窗 SHALL 关闭且不创建项目，重新打开时清除上次未提交输入

#### Scenario: 提交不合法表单

- **WHEN** 名称为空白或字段超过长度限制
- **THEN** 表单 SHALL 阻止请求并显示字段错误

### Requirement: 创建项目并选择后续入口

前端 SHALL 通过 `POST /api/projects` 提交 `name`、可选 `description`、`sourceArch` 和 `targetArch`，并提供进入工作台或开始配置环境两个创建动作。

#### Scenario: 创建并进入工作台

- **WHEN** 用户选择创建并进入工作台且创建成功
- **THEN** 应用 SHALL 关闭弹窗、提示成功、失效首页项目列表并导航至 `/projects/:projectId`

#### Scenario: 创建并开始配置环境

- **WHEN** 用户选择创建并开始配置环境且创建成功
- **THEN** 应用 SHALL 导航至 `/projects/:projectId?panel=env`，打开环境管理

#### Scenario: 创建失败

- **WHEN** 创建请求失败
- **THEN** 弹窗 SHALL 保留输入、解除提交中状态并显示错误反馈
