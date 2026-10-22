## Context

项目工作流在人工修复后需要独立的源码对比阶段。后端已经提供 latest compare、latest recheck、diff item 分页和详情接口；前端目前仅在人工修复 Drawer 中展示少量 latest compare 摘要，且工作流将 `diff` 标记为延后节点。

后端的 compare 是基于已确认迁移输入的复检：比较当前 active 源码版本和上一版本中的问题状态，不是 Git 或文件行级 diff。

## Goals / Non-Goals

**Goals:**

- 以独立 Drawer 展示前后源码版本、复检状态、差异统计和可分页筛选的差异列表。
- 在同一 Drawer 内查看单项前后记录，避免叠加 Drawer。
- 按后端状态引导用户更新源码、发起复检、等待结果、重试或进入构建验证。
- 将人工修复 Drawer 收敛为线下修复和回到源码管理的入口。
- 在画布启用源码对比节点，并使用“人工修复 -> 源码对比 -> 构建验证”的主链路；人工修复到源码管理的反馈边保留。

**Non-Goals:**

- 不实现 Git 或文件文本行级 diff、在线修改、自动 patch 或 AI Agent 重写。
- 不修改后端复检、源码版本、任务或差异项的数据模型和 API。
- 不在本 change 中实现构建验证本身。

## Decisions

### 独立源码对比 Drawer

`SourceCompare` 将拥有 latest compare 查询及其展示状态。人工修复不再请求或展示复检摘要，只说明修复后需通过源码管理导入并激活新版本。

这样阶段职责清晰，避免同一复检数据在两个 Drawer 中产生相互独立的加载、空态和操作逻辑。

### 以状态驱动操作，而非让用户选择版本

Drawer 固定使用后端定义的当前 active 版本和上一版本：

- `NOT_STARTED`：提供“开始复检”。
- `RUNNING`：展示进行中状态，轮询或刷新 latest compare 直到终态。
- `FAILED`：提供“重新复检”。
- `SUCCEEDED`：展示差异明细，并允许进入构建验证。
- 无 active 或 previous revision：说明缺失前提，提供前往源码管理的入口。

不向用户暴露任意 old/new revision 选择器，避免与 latest compare 的流程语义冲突。显式版本复检 API 保留给未来审计型工作流。

### 统一的列表布局与 Drawer 内视图切换

成功态用 `BaseTable` 承载 diff item 列表，遵循筛选栏、表格、选择/分页栏的项目级布局。筛选条件由后端分页 API 执行，至少覆盖差异状态、来源类型、风险等级和匹配置信度。

行级“详情”在同一个 SourceCompare Drawer 中切换为详情视图，展示当前状态、匹配依据、修复前记录和修复后记录；返回列表不关闭 Drawer。含表格的主视图宽度使用 1100px。

### 摘要优先于明细

版本上下文和“已解决、未变化、已变化、新增”统计位于列表前方。统计以紧凑的状态摘要展示，不将每个计数设计为大型页面卡片。差异明细中的状态和严重等级沿用项目统一 tag 映射。

## Risks / Trade-offs

- [首次上传或只有单版本时没有可比数据] → 明确展示 `NO_ACTIVE_REVISION` 或 `NO_PREVIOUS_REVISION` 的原因和源码管理入口，不渲染空表格。
- [复检为异步任务] → 用 latest compare 状态作为唯一真相；创建复检后失焦或重新打开 Drawer 仍能恢复正确状态。
- [后端 diff item 不提供文本 diff] → 详情只使用 old/new finding 快照和匹配信息，界面不暗示提供代码行级对比。
- [人工修复与源码对比均需要源码版本信息] → 只允许 SourceCompare 管理复检查询，人工修复仅跳转源码管理，消除重复请求和语义重叠。

## Migration Plan

1. 启用拓扑中的 `diff` 节点并调整边和分组布局。
2. 新增 SourceCompare Drawer、请求封装与类型；保留现有后端接口不变。
3. 从 ManualRepair 移除 latest compare 查询与摘要 UI。
4. 补充状态、筛选和详情交互测试，执行前端类型检查与测试。

回滚时可恢复 `diff` 为延后节点并保留后端 API；不涉及数据迁移。

## Open Questions

- 无。当前交互以 latest compare 的固定版本对为准。
