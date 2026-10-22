## Why

归档节点需要让用户在任意阶段点击“归档当前状态”，生成一条可查看、可下载、可审计的项目快照。当前文档只有归档 API 占位，缺少可插拔的归档候选登记机制，后续新增节点时会导致归档逻辑持续堆叠业务查询。

## What Changes

- 新增项目归档运行时能力：支持归档当前 active 源码版本下已经产生的可归档内容。
- 新增 `archive_candidates` 待归档表，由各业务节点在生成报告、摘要或可下载制品后主动登记最新候选内容。
- 归档候选按 `project_id + source_revision_id` 隔离；重新提交并激活新源码版本后，归档当前状态不得读取上一源码版本的候选内容。
- 归档候选同时包含 `node_type` 和 `candidate_type`：
  - `node_type` 表示来源节点。
  - `candidate_type` 表示前端展示方式。
- 归档按钮创建异步归档任务，从当前 active 源码版本的 active candidates 生成归档记录、归档明细和归档包。
- 归档详情支持查看每个归档项，并按 HTML、JSON、LOG 等格式查看或下载单项报告内容。
- 归档包下载汇总本次归档内存在的 HTML/JSON/LOG 等内容；未执行阶段不出现在详情或归档包中。
- 归档包保存到对象存储，通过业务 API 下载，不暴露 bucket、object key 或服务器路径。

## Capabilities

### New Capabilities

- `project-archive-runtime`: 定义项目归档候选、归档快照、归档详情和归档包生成下载能力。

### Modified Capabilities

- `backend-api-design`: 补充归档 overview、归档候选驱动的归档详情、单项内容查看/下载和归档包下载 API 约定。
- `backend-database-design`: 补充 `archive_candidates` 表、归档记录源码版本绑定、归档明细候选快照和对象存储归档包元数据约束。
- `object-storage-artifacts`: 补充 `ARCHIVE` 归档包作为后端输出制品的存储和下载约束。
- `api-e2e-test-suite`: 补充归档节点 E2E 模块，覆盖任意阶段归档、源码版本隔离、详情和打包下载。

## Impact

- 数据库：新增 `archive_candidates` 表，补充 `archives` 与 `archive_items` 的源码版本、候选快照和对象存储引用字段。
- 后端 API：新增归档 overview、创建归档任务、归档列表、归档详情、归档项内容下载、归档包下载。
- 后端 runtime：新增归档任务 handler，从候选表读取当前源码版本候选并生成压缩包。
- 业务节点：报告、KB、SBOM、复检、构建、自动化测试、测试比较等节点在成功产生可归档内容后登记候选。
- 对象存储：归档包作为 `StoredArtifactOwnerType.ARCHIVE` 制品保存。
- 测试：新增单元测试和独立 E2E 模块，覆盖正常流程、异常流程和 edge case。
