## Context

后端已经有 `archives`、`archive_items`、`stored_artifacts` 和对象存储基础能力，但归档节点仍停留在 API 文档占位层面。当前报告、KB、SBOM、构建、测试和比较等节点分别拥有自己的业务表和输出制品，若归档模块直接查询每个节点的“最新结果”，后续新增节点时必须持续修改归档核心逻辑。

本设计将归档拆成两层：各业务节点负责登记“当前源码版本下可归档的最新候选内容”，归档节点只负责读取候选、固化快照、打包下载。所有优化和归档事实边界以 `source_revision_id` 为准，源码或配置变更后必须进入新的源码版本边界。

## Goals / Non-Goals

**Goals:**

- 支持归档页面上的全局“归档当前状态”按钮。
- 支持归档 overview 展示最新归档记录及其包含内容。
- 支持归档记录列表、详情、单项报告查看/下载和归档包下载。
- 引入可插拔归档候选机制，使后续节点只需登记 candidate 即可被归档纳入。
- 保证归档当前状态只读取当前 active 源码版本下的 active candidates。
- 将归档包保存到对象存储，并通过业务 API 代理下载。

**Non-Goals:**

- 不实现通用 artifact API。
- 不归档源码包、源码工作副本、明文凭据、完整任务输入快照或服务器真实路径。
- 不要求所有阶段都已执行后才能归档。
- 不在归档节点中重新计算报告、重新扫描、重新构建或重新测试。
- 不用优化轮次 ID 作为归档候选隔离键；优化轮次只是源码版本上的展示聚合。

## Decisions

### 1. 使用 `archive_candidates` 作为可插拔归档候选表

各节点在成功产生可归档结果后 upsert 一条候选记录。候选记录只保存展示摘要和资源引用，不保存大内容。

核心字段：

- `project_id`
- `source_revision_id`
- `node_type`
- `candidate_type`
- `candidate_key`
- `resource_type`
- `resource_id`
- `title`
- `summary`
- `artifact_refs`
- `status`

唯一槽位：

```text
project_id + source_revision_id + node_type + candidate_type + candidate_key
```

这样同一源码版本下每个节点可以维护自己的 latest、source、target 或其他稳定槽位；重新激活新源码版本后，归档当前状态天然不会读取旧版本候选。

### 2. 区分 `node_type` 和 `candidate_type`

`node_type` 表示来源节点，例如 `KB_SCAN`、`SBOM_ANALYSIS`、`MIGRATION_REPORT`、`BUILD_VALIDATION`、`AUTOMATED_TEST`、`TEST_COMPARISON`。

`candidate_type` 表示前端展示组件，例如 `REPORT`、`RAW_RESULT`、`BUILD_SUMMARY`、`TEST_SUMMARY`、`COMPARISON_REPORT`、`LOG`。

前端可用 `candidate_type` 决定展示方式，用 `node_type` 做来源分组和筛选。

### 3. 归档记录绑定源码版本并固化 candidate 快照

点击“归档当前状态”时：

1. 后端解析项目 active source revision。
2. 创建 `ARCHIVE_PROJECT` 任务和 `archives` 记录。
3. worker 查询当前 `project_id + active source_revision_id + status=ACTIVE` 的 candidates。
4. 将 candidates 固化为 `archive_items`。
5. 读取候选中的 `storedArtifactId` 或业务资源摘要，生成 `manifest.json`、`summary.json` 和报告文件目录。
6. 打包为 zip 或 tar.gz，写入 `stored_artifacts(owner_type=ARCHIVE)`。
7. 更新 `archives.status`、`summary`、`size_bytes`、`sha256`。

旧归档不依赖当前 candidate 状态；candidate 更新后不影响已生成归档。

### 4. 任意阶段可归档

归档不检查流程阶段完整性。某阶段没有候选时：

- overview 不展示该阶段。
- 归档详情不包含该 item。
- 归档包不包含该阶段文件。
- 创建归档仍可成功；若当前版本没有任何候选，则返回明确业务错误或生成只含 manifest 的空归档，实施时优先选择业务错误以减少无意义归档。

### 5. 归档下载通过业务接口代理对象存储

归档包本身作为 `ARCHIVE` 制品进入对象存储。API 只返回安全摘要和下载响应，不暴露 bucket、object key、服务器路径或远端路径。

单项报告查看/下载优先使用 candidate 或 archive item 中固化的 `storedArtifactId`。如果历史数据缺少对象存储制品，后端可按受控兼容路径读取，但 API 仍不得暴露路径。

## Risks / Trade-offs

- [Risk] 各节点忘记登记 candidate，导致归档缺失内容。 → Mitigation: 为每个已实现节点补测试，并在 E2E 中检查归档详情包含预期 item。
- [Risk] `artifact_refs` JSONB 结构失控。 → Mitigation: 定义统一 schema，最小包含 `format`、`storedArtifactId`、`artifactType`、`contentType`、`filename`。
- [Risk] 归档包生成读取对象存储失败。 → Mitigation: 任务失败并写入 `archives.status=FAILED` 与脱敏错误摘要，不影响原始报告。
- [Risk] 大归档包导致内存压力。 → Mitigation: 使用流式 zip/tar 生成，不将所有文件一次性加载到内存。
- [Risk] 旧源码版本候选被误归档。 → Mitigation: 所有当前归档查询必须显式使用 active `source_revision_id`，并增加跨版本 E2E。
