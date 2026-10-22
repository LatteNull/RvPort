## Context

环境 Drawer 已包含列表、创建/编辑、检查、脚本、执行记录和日志六种视图。现有入口同时承担状态机、服务端操作和 JSX 组合，职责混杂。

## Design

### 保持入口稳定

`Environment/index.tsx` 保持默认导出与 `StageDrawerProps` 调用方式不变，仅作为状态和领域操作的编排边界。

### 按职责拆分

- `views.tsx`：检查结果与日志等纯展示视图。
- `drawer-chrome.tsx`：标题、Footer 和确认交互；通过显式 props 接收状态与回调，不调用领域 API。
- `environment-input.ts`：表单到请求模型的转换函数。
- `useEnvironmentDrawer.ts`：视图切换、TanStack Query/mutation、缓存失效与操作回调。

现有 `Form`、`List`、`ScriptForm` 和 `Executions` 保持职责不变。

## Risks

- Drawer 的 Footer 依赖表单 dirty 状态；拆分后仍由同一 Form 实例传入，避免改变取消确认语义。
- mutation 完成后的缓存失效、反馈与返回视图必须保持原有时序。

## Validation

运行环境列表既有测试，补充纯输入转换和视图行为测试；执行格式、Lint、类型、全量测试与 OpenSpec 校验。
