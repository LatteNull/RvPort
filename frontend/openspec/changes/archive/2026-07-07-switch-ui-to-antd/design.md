# 设计：切换 UI 组件库到 Ant Design

## 当前状态

前端当前在四个层面依赖 Semi：

```text
Semi 依赖面
├─ package / build
│  ├─ @douyinfe/semi-ui
│  ├─ @semi-bot/semi-theme-ryrepo
│  └─ @douyinfe/semi-vite-plugin
├─ 应用入口
│  └─ @douyinfe/semi-ui/react19-adapter
├─ 组件
│  ├─ Layout, Button, Spin
│  ├─ Form, Input, Select, TextArea
│  ├─ Modal
│  ├─ Toast
│  ├─ Typography, Skeleton, Empty
│  └─ BaseModal wrapper
└─ 样式
   ├─ --semi-color-* 变量
   └─ .semi-* 选择器覆盖
```

目标是收敛为一个 Ant Design provider 边界，并用轻量 `src/theme.ts` 集中维护当前需要传给 Ant Design 的主题值。当前只保留 `colorPrimary` 和 `borderRadius`，不建立完整项目 token 层。

```text
目标依赖面
├─ package / build
│  └─ antd
├─ 应用 providers
│  ├─ ConfigProvider
│  └─ FeedbackBridge
├─ 组件
│  ├─ Layout, Button, Spin
│  ├─ Form, Input, Select
│  ├─ Modal
│  ├─ message
│  ├─ Typography, Skeleton, Empty
│  └─ BaseModal wrapper
└─ 样式
   └─ 只在 BaseModal / layout 必要场景使用少量 .ant-* 外壳样式
```

## 决策

RvPort-Frontend 使用 Ant Design 作为唯一 UI 组件库。

不保留 Semi + Ant Design 混用状态。实现过程中允许工作区短暂出现未迁移的 import，但变更完成时必须满足：

- 运行时代码不再 import `@douyinfe/semi-ui`
- 不再使用 Semi Vite plugin
- 不再使用 Semi theme package
- 样式不再依赖 `--semi-*`

## Provider 策略

在应用树顶部增加 Ant Design provider 边界：

```text
main.tsx
└─ App
   └─ ConfigProvider theme / variant / locale
      ├─ FeedbackBridge(message.useMessage contextHolder)
      └─ QueryClientProvider
         └─ RouterProvider
```

`src/theme.ts` 只负责维护当前 Ant Design 全局主题入口：

- `theme.token.colorPrimary`
- `theme.token.borderRadius`

`ConfigProvider` 负责：

- 应用 `src/theme.ts` 中的 Ant Design theme
- 数据录入组件的默认 `variant`
- 后续确有全局影响的 Ant Design component token

`FeedbackBridge` 使用 Ant Design 推荐的 `message.useMessage()` 创建 `contextHolder`，并把 `messageApi` 注册到项目级 message bridge。请求层反馈不应在任意非 React 模块中直接 import 静态 UI API，而应通过 bridge 转发。

## Variant 策略

RvPort 可以同时支持经典描边输入和现代填充输入，但按场景使用：

| 场景                     | Ant Design variant                        |
| ------------------------ | ----------------------------------------- |
| Modal 表单、主要数据录入 | `outlined`                                |
| 搜索、筛选、轻量控制     | `filled`                                  |
| 只读展示字段             | 本地展示组件，或 disabled / readonly 样式 |

这样可以避免把一种全局视觉规则强压到所有输入控件上。

## 组件映射

| Semi 使用点                    | Ant Design 目标                                                       | 说明                                |
| ------------------------------ | --------------------------------------------------------------------- | ----------------------------------- |
| `Button theme="solid"`         | `<Button type="primary" />`                                           | 主操作按钮。                        |
| `Button theme="outline"`       | `<Button variant="outlined" color="primary" />` 或默认 Button + class | 保持按钮语义清晰。                  |
| `SemiLayout`                   | `Layout`                                                              | 应用外壳概念一致。                  |
| `Spin`                         | `Spin`                                                                | 直接迁移。                          |
| `Toast.success/error`          | 通过 app-level bridge 调用 `message.success/error`                    | 避免静态 API 丢失 provider 上下文。 |
| `Typography.Title heading={4}` | `Typography.Title level={4}`                                          | API 名称不同。                      |
| `Form.Input`                   | `Form.Item name` + `Input`                                            | 改为显式组合。                      |
| `Form.TextArea`                | `Form.Item name` + `Input.TextArea`                                   | 保留 autosize。                     |
| `Form.Select optionList`       | `Form.Item name` + `Select options`                                   | options 结构基本兼容。              |
| `FormApi.submitForm()`         | `Form.useForm()` + `form.submit()`                                    | 替换 Semi Form ref API。            |
| `Modal visible`                | `Modal open`                                                          | API 名称不同。                      |
| `Empty title/description`      | `Empty description` + 必要本地标题                                    | Ant Empty API 不同。                |
| `Skeleton.Button/Title`        | `Skeleton.Button/Input/Node`                                          | 以卡片骨架视觉为准。                |

## 样式策略

不新增 `variables.scss`，也不新增 `--rvport-*` CSS Variables。当前阶段不建立完整项目 token 层，避免为了少量样式制造过重抽象。

Ant Design 组件外观优先通过最小 `antdTheme` 控制；业务卡片、布局和弹窗壳层中的颜色、阴影、边框和局部圆角暂时保留在对应 SCSS Module 中。只有 `BaseModal` 这类业务组合组件确实需要壳层布局时，才写少量 wrapper CSS。

如果后续 UI 规范稳定，再单独评估是否扩展 `src/theme.ts` 或引入项目级 token 层。

## OpenSpec 对齐

当前 `create-project` change 已完成，但仍描述了 Semi Modal 和 Semi Form。antd 迁移应选择以下方式之一处理：

- 在归档前更新 `create-project` artifacts；或
- 在本变更的 spec 中覆盖这些 Semi 细节，并以最终 Ant Design 实现归档。

最终被接受的 specs 中不应再要求 Semi UI。

## 风险

- Ant Design v5 / v6 的版本选择会影响 variant 和 component token 等 API。
- 静态 `message` API 可能拿不到 provider theme，需要通过 `message.useMessage()` 和项目 bridge 处理。
- Form API 不是 1:1 迁移，校验行为和提交回调需要重点 QA。
- Skeleton 和 Empty 的视觉密度会变化，可能需要少量本地样式调整。
- 移除 Semi 变量后，可能暴露隐藏的业务 SCSS 依赖。
