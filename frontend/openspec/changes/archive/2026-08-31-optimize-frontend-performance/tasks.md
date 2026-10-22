## 1. 建立性能回归基线

- [x] 1.1 为 CodeMirror 与 Monaco 的延迟加载边界补充测试，并验证未渲染编辑器时不会请求实现模块、渲染后显示加载占位并恢复既有 props 行为。

## 2. 优化资源与按需加载

- [x] 2.1 将 `CodeMirrorEditor` 的重型实现与语言扩展移至稳定的 `lazy()` 加载边界，并在需要编辑器的视图按实际渲染触发加载；生产构建确认轻量外壳约 1.6 KB，536 KB 实现独立为异步 chunk。
- [x] 2.2 复核 Monaco 的共享加载 Promise 与可选预加载路径，确保未提前加载到普通项目浏览；为高亮行数组提供稳定默认引用，保留既有按需加载与预加载路径。

## 3. 消除重复渲染工作

- [x] 3.1 提升编辑器非原始默认 props 并稳定高亮扩展依赖；CodeMirror 与 Monaco 均使用模块级空数组，避免未传入高亮行时因父组件重渲染重建等价配置。
- [x] 3.2 在 `useTableViewportHeight` 中跳过相同测量结果的状态更新；相同高度回写当前状态，避免触发额外 React 更新。

## 4. 验证

- [x] 4.1 执行 `pnpm format:check`、`pnpm lint`、`pnpm typecheck` 与 `pnpm test`，并验证全部通过。
- [x] 4.2 执行 `pnpm build`，比较编辑器 chunk 的构建产物和加载边界，确认 CodeMirror 外壳 gzip 为 873 B、实现 gzip 为 172 KB，重型实现不在外壳 chunk 中；认证背景按产品要求保持当前资源。
- [x] 4.3 执行 `openspec validate optimize-frontend-performance --strict`，验证该 change 完整且通过。
