## Why

项目归档已具备后端任务、归档快照、归档项和下载接口，但工作流中尚未开放归档节点。用户无法创建可追溯的交付快照，或查看和下载已收集的项目成果。

## What Changes

- 开放“归档”工作流节点，展示最新归档摘要和项目归档历史。
- 支持创建当前源码版本的归档任务，并展示任务执行状态与失败提示。
- 支持在 Drawer 内查看归档详情、归档项和下载归档包或可下载的单项制品。

## Capabilities

### New Capabilities

- `project-archive-stage`: Create, inspect, and download project archive snapshots from the existing archive APIs.

### Modified Capabilities

- None.

## Impact

- Affected frontend workflow topology, stage routing, project API client, project types, and a new archive Drawer.
- Uses existing project archive endpoints without backend changes.
