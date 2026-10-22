# 设计：x86 当前源码重新部署

## 交互

当当前源码已有成功部署记录时，x86 构建前置条件卡片在部署目录事实区域提供次级按钮“重新部署”。点击后通过确认框说明“将覆盖 x86 源环境中的当前源码目录”，确认才创建任务。按钮进行中禁用并显示加载状态。

当不存在成功部署记录时，既有“部署当前源码”主恢复操作保持不变，不额外展示“重新部署”。

## 请求与缓存

现有 `createProjectSourceDeployments` 扩展为接受 `force` 选项，默认仍为 `false`，避免改变缺失部署时的既有语义。重新部署传入 `true`，请求体为：

```json
{
  "sourceRevisionId": "当前源码 ID",
  "force": true,
  "timeoutSeconds": 3600
}
```

mutation 成功后失效当前源码的 `sourceDeployments` 查询键和项目 overview 查询键；成功部署后的最终就绪状态仍由用户的明确刷新或任务事件刷新获得，前端不臆测任务完成。

## 性能与边界

- 保持一个 mutation，参数化区分首次部署与重新部署，避免重复请求状态与重复缓存失效逻辑。
- 按 `vercel-react-best-practices` 的 `rerender-move-effect-to-event`，部署仅由用户事件触发；不使用 `useEffect` 自动发起重新部署。
- 不引入新依赖或全局状态；服务端任务和 TanStack Query 缓存仍是部署状态的唯一事实来源。
