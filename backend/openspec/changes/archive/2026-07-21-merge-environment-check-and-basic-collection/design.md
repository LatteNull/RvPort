## Context

当前后端已经有三类环境相关任务：`ENV_TEST_CONNECTION`、`ENV_RUN_SCRIPT` 下的 `ENV_CHECK`、以及 `ENV_COLLECT`。其中 `ENV_CHECK` 只保存检查结果、任务日志和连接状态；`ENV_COLLECT` 才会写入 `environment_snapshots` 和 `environment_components`。

前端后续会移除独立“采集信息”入口，但环境列表和详情仍需要展示 OS、版本、架构、包管理器、基础工具和最近检查结果。因此后端需要把轻量环境基础信息采集合并到环境检查中，同时保留重型采集能力给 SBOM 分析内部使用。

## Goals / Non-Goals

**Goals:**

- 环境检查成功后生成可查询的轻量环境基础快照。
- 环境列表、详情、快照和任务详情能返回环境检查产生的基础信息。
- 环境检查失败不覆盖上一轮成功信息。
- 保留 `ENV_COLLECT` 作为 SBOM 分析需要的重型采集任务。
- 后端测试覆盖正常流程、异常流程和 edge case。

**Non-Goals:**

- 不实现前端页面改造。
- 不删除 `ENV_COLLECT` 后端能力。
- 不把全量 package、repo provides、native library、ELF metadata 采集放入普通环境检查。
- 不改变 SSH 凭据加密、项目权限模型或任务队列模型。

## Decisions

### 1. 环境检查写入轻量 snapshot

`ENV_CHECK` 成功后复用 `environment_snapshots` 保存轻量环境事实，字段包括 OS、OS version、kernel、arch、package manager、tool versions、check results、working directory 和 parse warnings。`raw_snapshot` 中增加 `snapshotKind=BASIC_CHECK` 或等效字段，用于区分轻量检查快照和重型采集快照。

备选方案是新增 `environment_basic_info` 表。暂不采用，因为现有快照表已经具备任务关联、时间排序、OS/kernel/arch/package manager 等字段，复用能减少迁移和查询复杂度。

### 2. 不在 ENV_CHECK 写入 environment_components

普通环境检查只写轻量快照，不写 `environment_components`。原因是组件表用于 SBOM 分析，需要表达 package/library/tool/native/repository provide 等细粒度事实；如果检查任务写入部分组件，容易让后续分析误以为已有完整组件清单。

### 3. ENV_COLLECT 保留为后端内部重型采集

`ENV_COLLECT` 继续负责 SBOM 所需的全量组件、仓库候选、ELF metadata、provider 证据和 unmanaged tool 证据。普通前端流程可以不暴露独立采集入口，但 SBOM 分析仍可依赖已有快照或触发重型采集。

### 4. API 返回 latest basic information

环境列表和详情响应增加或填充环境基础信息摘要。优先从该环境最近一次成功快照读取；若只有旧数据，则返回旧数据；若没有快照，则返回 `null` 或空摘要。API 不返回敏感路径、明文凭据、完整 raw snapshot 或远程敏感输出。

### 5. 失败不覆盖成功结果

`ENV_CHECK` 失败时只写失败任务、日志和 `tool_runs`，并更新连接状态为不可用。不得创建成功快照，不得删除旧快照，也不得把 `last_collected_at` 更新为失败时间。

## Risks / Trade-offs

- [Risk] 复用 `environment_snapshots` 后，列表中会同时出现轻量检查快照和重型采集快照。  
  Mitigation: 在 `raw_snapshot.snapshotKind` 或等效摘要字段中区分，并在查询最新基础信息时允许两类成功快照都作为来源。

- [Risk] `last_collected_at` 名称语义偏“采集”，用于检查生成的基础快照可能不够准确。  
  Mitigation: MVP 可继续兼容该字段；若实现时发现语义冲突明显，再增加 `last_checked_at` 迁移并保持旧字段兼容。

- [Risk] 环境检查加入 OS/package manager 命令后耗时略增。  
  Mitigation: 只执行轻量、无 sudo、无全量扫描的命令；全量采集继续由 `ENV_COLLECT` 承担。

- [Risk] 旧前端仍可能调用 `/collect`。  
  Mitigation: 后端继续保留该 API 和任务，不在本 change 删除兼容能力。

## Migration Plan

1. 优先复用现有表结构实现；如需要 `last_checked_at` 或快照类型索引，再通过 Liquibase 增量迁移添加。
2. 更新 `ENV_CHECK` 命令和解析逻辑，使其输出 OS/package manager/tool/check results。
3. 成功时写入轻量快照并更新环境状态；失败时保持旧快照不变。
4. 更新环境查询 API 映射，返回最新基础信息。
5. 补充单元测试和必要的 E2E 模块测试。

Rollback 时可保留历史轻量快照，只回退 API 使用逻辑；这些快照不包含敏感信息，不影响旧的重型采集流程。

## Open Questions

- 是否新增 `environments.last_checked_at` 字段，还是继续复用 `last_collected_at` 表达最近成功基础信息更新时间？实现前需要结合现有前端字段和 API 响应确认。
