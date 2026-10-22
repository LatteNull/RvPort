# 切换 UI 组件库到 Ant Design

## 概要

将前端 UI 组件库从 Semi UI 全量切换到 Ant Design。切换完成后不混用 Semi 和 antd，也不保留 Semi DSM 主题链路。

## 动机

RvPort 正在变成典型的后台操作型 Web 应用：登录、受保护的应用外壳、项目列表、弹窗表单、字段校验、反馈消息，后续大概率还会继续增加表格、抽屉、上传、步骤条和流水线控制。

这些工作流更贴近 Ant Design 的组件模型和表单生态。继续通过 Semi DSM 和组件级覆盖去调整 Input、Select、TextArea、hover、focus、error 等状态，会带来较高配置和维护成本。

Ant Design 提供统一的 `ConfigProvider` 主题边界，数据录入组件也支持 `outlined`、`filled` 等 variant。这样可以按场景区分“表单录入”和“轻量筛选”，而不是在 DSM 中逐个状态维护。

## 范围

- 移除所有运行时 `@douyinfe/semi-ui` 使用。
- 移除 Semi 主题包和 Semi Vite 插件。
- 引入 Ant Design 作为唯一应用 UI 组件库。
- 新增顶层 Ant Design 主题和 provider 边界。
- 迁移现有 Semi 组件使用点：
  - `src/main.tsx`
  - `src/App.tsx`
  - `src/layouts/MainLayout`
  - `src/pages/login`
  - `src/pages/home`
  - `src/components/BaseModal`
  - `src/pages/home/components/CreateProjectModal`
  - `src/api/request.ts`
- 将 `--semi-*` 样式依赖替换为 RvPort 自有 CSS 变量或 Ant Design token。
- 更新 OpenSpec 中仍把 Semi 描述为前端 UI 基础设施的内容。

## 非目标

- 不重新设计 RvPort 的产品流程。
- 不在本变更中引入 Ant Design Pro、Umi、ProComponents 或其他应用框架。
- 不实现项目详情、环境管理、源码上传、流水线执行等新页面。
- 不把 Semi 和 Ant Design 作为长期混用状态。
- 切换后不继续把 Semi DSM 主题文档作为样式真相来源。

## 影响

- 依赖清单和 lockfile 会在安装或卸载依赖时变化。
- 现有组件 import 和部分 props 会变化，因为 Semi 和 Ant Design API 不同。
- `create-project` artifacts 当前仍提到 Semi Modal / Form，需要在归档前更新或由本变更覆盖。
- 需要对登录页、首页项目列表、loading / empty / error 状态、新建项目弹窗做视觉验收。
