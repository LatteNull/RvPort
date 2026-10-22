# project-list-home Specification

## Purpose

定义当前项目首页的查询筛选、分批加载、卡片摘要和工作台导航。项目创建行为由 project-creation 定义。

## Requirements

### Requirement: 项目列表与筛选

`/home` SHALL 为登录用户提供项目列表、新建入口、关键词、项目状态与阶段筛选，并通过 TanStack Query 调用服务端分页 API。

#### Scenario: 提交筛选

- **WHEN** 用户提交名称或描述关键词、切换进行中/已归档状态或流程阶段
- **THEN** 页面 SHALL 重新从首批请求匹配项目，并显示已加载数与总数
- **AND** 重置操作 SHALL 清空全部筛选

#### Scenario: 分批加载与恢复

- **WHEN** 当前列表有后续页且用户点击继续加载
- **THEN** 页面 SHALL 追加下一批项目
- **WHEN** 后续页失败
- **THEN** 页面 SHALL 保留已加载卡片并提供重试

#### Scenario: 初始加载、失败与空列表

- **WHEN** 首次查询尚未完成、失败或无结果
- **THEN** 页面 SHALL 分别展示卡片骨架、可重试错误或空状态

### Requirement: 项目卡片摘要

卡片 SHALL 展示项目名称、架构方向、项目状态、当前阶段、最近扫描时间、最近构建和测试状态，并对缺失结果展示中性占位。

#### Scenario: 展示项目

- **WHEN** 项目数据加载成功
- **THEN** 卡片 SHALL 将架构与状态映射为用户可读文案，目标 `riscv64` 展示为 `RISC-V`
- **AND** 长名称 SHALL 可通过受控提示查看

### Requirement: 原生项目导航

项目卡片 SHALL 使用 Link 导航到 `/projects/:projectId`，保留键盘及浏览器原生链接行为。

#### Scenario: 进入工作台

- **WHEN** 用户点击、按 Enter、使用 Cmd/Ctrl 点击或中键点击项目卡片
- **THEN** 应用 SHALL 按链接语义打开项目工作台
- **AND** hover 与 focus-visible SHALL 提供可见反馈
