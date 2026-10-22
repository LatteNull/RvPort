## Decisions

使用既有 StagePresentationContext 决定容器。表单及执行详情共享同一内容定义，Workflow 交给 StageSurface，Step 交给 BaseModal。TableViewStateProvider 保持位于共同边界，历史与日志往返不丢失分页。移除独立执行 Drawer 及其样式；不新增数据 Hook 或兼容实现。

Workflow 非列表标题提供内部返回，日志返回所属历史，表单返回走既有草稿确认并在 busy 时禁用；阶段整体关闭仍走既有路由与草稿保护。
