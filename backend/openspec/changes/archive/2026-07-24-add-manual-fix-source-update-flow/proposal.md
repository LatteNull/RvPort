## Why

当前人工修复节点如果做成独立工作台，会和迁移输入、源码管理、前后对比页面产生职责重叠。MVP 阶段更需要清晰闭环：用户线下修复代码后回到源码管理更新源码，由后端创建新源码版本并进入代码比较。

同时，代码比较不应要求前端传入旧版本和新版本 ID；后端已经掌握项目源码版本关系，应提供项目级 latest compare 主入口，降低前端状态耦合和误用风险。

## What Changes

- 将人工修复节点定义为轻量过渡页，而不是在线修复工作台。
- 人工修复页展示当前迁移输入摘要、最近源码版本和线下修复提示。
- 人工修复页主操作为 `更新源码`，跳转源码管理页执行源码包上传或 Git 更新。
- 源码更新完成后，后端创建新的 active `source_revisions`，并引导前端进入代码比较页。
- 新增项目级 latest compare API：`GET /api/projects/{projectId}/source/compare/latest`。
- latest compare 由后端选择当前 active source revision 和它的上一版 revision；前端不传两个 revision ID。
- 当项目只有一个源码版本时，latest compare 返回明确空态 `NO_PREVIOUS_REVISION`。
- Prototype 和前端页面改造不在本 backend change 内实施，由前端侧后续按 API 契约完成。

## Capabilities

### New Capabilities

- `manual-fix-source-update-flow`: 定义人工修复节点、源码更新跳转、latest source compare API 和无基线空态。

### Modified Capabilities

- 无。

## Impact

- 后端 API 文档与实现：新增 latest compare 查询入口，复用现有 `source_revisions`、`recheck_runs` 和 `diff_items` 数据。
- 源码管理流程：源码包上传或 Git 更新成功后继续创建源码版本，并可触发或返回最近比较状态。
- 前端交互契约：人工修复页只负责引导更新源码；代码比较页通过项目级 API 获取比较结果。
