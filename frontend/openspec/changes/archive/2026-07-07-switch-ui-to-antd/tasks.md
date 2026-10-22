## 1. 依赖与构建边界

- [x] 1.1 在前端依赖中用 `antd` 替换 `@douyinfe/semi-ui`。
- [x] 1.2 移除 `@semi-bot/semi-theme-ryrepo` 和 `@douyinfe/semi-vite-plugin`。
- [x] 1.3 从 Vite 配置中移除 `semiTheming`。
- [x] 1.4 从应用入口移除 `@douyinfe/semi-ui/react19-adapter`。
- [x] 1.5 确认运行时代码不再从 `@douyinfe/*semi*` 或 `@semi-bot/*` 导入。

## 2. Ant Design Provider 与主题

- [x] 2.1 新增顶层 Ant Design `ConfigProvider`。
- [x] 2.2 新增基于 `message.useMessage()` 的 `contextHolder`，用于 message 反馈 API。
- [x] 2.3 新增轻量 `src/theme.ts`，集中维护 Ant Design `colorPrimary` 和 `borderRadius`。
- [x] 2.4 确定默认数据录入 `variant`，并允许在具体场景覆盖。
- [x] 2.5 暂不新增 `variables.scss` 或 `--rvport-*` CSS Variables。

## 3. 组件迁移

- [x] 3.1 将 `MainLayout` 从 Semi Layout / Button / Spin 迁移到 Ant Design 组件。
- [x] 3.2 迁移登录页的 Form / Button / Typography / message 使用。
- [x] 3.3 迁移首页的 Button / Empty / Skeleton / Typography 使用。
- [x] 3.4 将 `BaseModal` 改为封装 Ant Design Modal。
- [x] 3.5 将 `CreateProjectModal` 迁移到 `Form.useForm`、`Form.Item`、`Input`、`Input.TextArea` 和 `Select`。
- [x] 3.6 将请求层 `Toast.error` 替换为项目级反馈桥接。

## 4. 样式迁移

- [x] 4.1 将 SCSS Modules 中的 `--semi-*` 变量替换为局部样式或 Ant Design token 能力。
- [x] 4.2 删除或废弃 `src/styles/semi-vars.scss`。
- [x] 4.3 将 `.semi-*` 选择器覆盖替换为必要的 `.ant-*` 外壳样式，且只用于 BaseModal / 布局等集中场景。
- [x] 4.4 视觉确认登录页、首页、项目卡片、弹窗 header / body / footer 和移动端 footer 布局。

## 5. OpenSpec 与验证

- [x] 5.1 更新 foundation specs，要求使用 Ant Design 而不是 Semi UI。
- [x] 5.2 更新项目创建 specs / design，确保共享弹窗外壳和创建表单不再提 Semi。
- [x] 5.3 更新 `openspec/project.md` 和 `openspec/config.yaml` 中的技术栈描述。
- [x] 5.4 运行 `openspec validate switch-ui-to-antd`。
- [x] 5.5 运行 `pnpm format:check`、`pnpm lint` 和 `pnpm typecheck`。
- [x] 5.6 运行 `pnpm build`，因为本变更影响依赖和 Vite 配置。
