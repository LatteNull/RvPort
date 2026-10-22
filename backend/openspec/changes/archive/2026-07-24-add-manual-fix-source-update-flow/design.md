## Context

当前系统已经具备源码版本管理、源码包上传、Git 同步、迁移输入合并、评估报告、复检运行和差异项表。人工修复不适合在 MVP 阶段做成在线代码修改工作台，因为真实修复通常发生在开发者本地 IDE、Git 分支、代码评审和团队流程中。

本 change 将人工修复节点收敛为轻量指引页：展示当前迁移输入摘要和最近源码版本，提示用户在线下完成修复，然后跳转源码管理更新源码。源码更新成功后，系统进入代码比较页，由后端根据项目源码版本关系返回 latest compare。

## Goals / Non-Goals

**Goals:**

- 明确人工修复节点只负责展示摘要、提示线下修复和引导源码更新。
- 源码更新后由后端创建新的 active `source_revisions`。
- 提供 `GET /api/projects/{projectId}/source/compare/latest`，由后端选择当前版本和上一版。
- 只有一个源码版本时返回明确空态，前端不需要自行判断。
- 输出后端 API 契约，供前端和 prototype 后续按契约调整。

**Non-Goals:**

- 不实现在线代码编辑器。
- 不实现一键修复、自动 patch 或 DevKit autofix 应用。
- 不实现 PR/MR 平台集成、多人任务分派或复杂修复看板。
- 不要求前端传入两个源码版本 ID 作为主流程。
- 不新增源码制品存储模型。

## Decisions

### 人工修复节点作为轻量过渡页

人工修复页展示：

- 当前迁移输入摘要：总数、高风险数、待确认数、未忽略数。
- 最近源码版本：版本 ID、来源类型、版本标签、Git 分支/提交摘要或源码包名称、创建时间。
- 线下修复提示：用户需要在本地或外部 Git 流程中修改代码。
- 主按钮 `更新源码`：跳转源码管理页。
- 次按钮 `查看迁移输入`、`查看评估报告`。

理由：

- 人工修复不是平台内自动修改行为，页面不应承担复杂工作台职责。
- 迁移输入页已经负责列出问题，源码管理页已经负责更新源码，代码比较页负责验证修复效果。
- 这样可以降低 MVP 实现复杂度，并避免和 AI Agent 后续能力重叠。

备选方案：

- 独立人工修复工作台：信息完整，但需要状态流转、备注、责任人、验证状态等大量交互，当前阶段投入过高。
- 直接从评估报告跳源码管理：更简单，但缺少明确的“人工修复”流程节点，不利于流水线表达。

### latest compare 由后端决定版本对

新增主流程 API：

```http
GET /api/projects/{projectId}/source/compare/latest
```

后端选择规则：

1. 校验当前用户对项目有访问权限。
2. 查找项目 active `source_revision` 作为 `currentRevision`。
3. 查找同项目中创建时间早于当前版本的最近一个成功源码版本作为 `previousRevision`。
4. 如果没有上一版，返回 `emptyReason=NO_PREVIOUS_REVISION`。
5. 如果存在上一版，优先返回 `recheck_runs` 中 `base_source_revision_id=previousRevision.id` 且 `target_source_revision_id=currentRevision.id` 的最新记录。
6. 如果比较尚未生成，返回 `status=NOT_STARTED` 或 `status=RUNNING`，并允许前端展示等待状态。

理由：

- 前端不应负责版本配对，否则更换页面、刷新、历史跳转时容易拿错 revision。
- 后端能基于数据库一致性选择最新版本对，避免越权和跨项目误用。

备选方案：

- `GET /source-revisions/{old}/compare/{new}`：适合审计和历史对比，不适合作为主流程。
- 前端从版本列表自行取前两项：逻辑脆弱，无法处理 active 切换、失败导入和比较任务状态。

### 源码更新后的跳转约定

源码包上传或 Git 同步成功后，API 响应继续返回新建 `sourceRevision`。前端可跳转到代码比较页面，页面调用 latest compare 获取真实比较状态。

如果源码更新触发了复检任务：

- latest compare 返回运行中状态和关联任务 ID。
- 项目级 SSE 继续通知任务状态。
- 代码比较页在任务完成后重新拉取 latest compare。

如果源码更新没有立即触发复检：

- latest compare 返回 `NOT_STARTED`。
- 页面展示“当前版本已更新，尚未生成对比结果”。

## Risks / Trade-offs

- [Risk] 用户期望在人工修复页直接处理单条问题。  
  Mitigation: 页面提供 `查看迁移输入` 入口，单条问题仍在迁移输入或 finding 详情页查看。

- [Risk] latest compare 使用“上一版”可能和用户希望比较的历史版本不同。  
  Mitigation: MVP 主流程只做 latest；历史任意版本比较可后续增加显式 API。

- [Risk] 新源码版本创建成功但复检失败，代码比较页没有可用结果。  
  Mitigation: latest compare 返回失败状态、任务错误摘要和可重试提示。

- [Risk] active source revision 被手动切换后 latest compare 语义变化。  
  Mitigation: 后端始终以 active revision 为 current，并在响应中返回 current/previous 的完整摘要。

## Migration Plan

1. 更新后端 API 文档和 OpenSpec 规格。
2. 实现 latest compare 查询服务，复用现有 `source_revisions`、`recheck_runs`、`diff_items`。
3. 更新源码上传/Git 同步响应或后续跳转说明，确保前端可进入代码比较页。
4. 补充单元测试和 E2E 模块测试，覆盖正常流程、异常流程和 edge case。

回滚策略：

- 保留现有源码上传和 Git 同步 API 不变。
- 如果 latest compare 出现问题，可暂时让前端继续展示源码版本列表和空态，不影响源码更新功能。

## Open Questions

- 是否需要在源码更新成功后自动创建复检任务，还是由代码比较页显式触发？
- latest compare 是否需要同时返回代码文件 diff 和 finding/SBOM 差异，还是先只返回已有 `recheck_runs` 结果？
