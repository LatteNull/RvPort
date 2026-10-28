# KB 扫描上下文与历史结果

## 当前结果的判定

KB 扫描必须绑定本项目源码在当前源环境、项目运行环境版本下选中的成功 `SOURCE_ONLY` x86 构建。构建按活动状态优先，再按创建时间及 ID 降序选择；新失败或活动构建不会回退到旧成功构建，`BOTH` 不能替代 `SOURCE_ONLY`。

`kb_scan_runs` 和任务输入保存 `source_environment_id`、`runtime_environment_version`、`build_run_id`。其中运行环境版本来自 `project_runtime_environments.version`，不是单台环境的配置版本。创建时在同一事务内取得项目上下文锁，再校验和创建任务；源码、运行环境、构建写入的数据库 trigger 使用同一事务锁。

| 情况 | overview KB | latest | 能否创建扫描 |
| --- | --- | --- | --- |
| 首次上传，无构建、无扫描 | PENDING / KB_SCAN_MISSING | EMPTY | 409，X86_BUILD_MISSING |
| 只有旧扫描或缺少绑定的历史扫描 | PENDING / KB_SCAN_STALE | STALE，保留原执行状态 | 按当前构建独立判定 |
| 当前有效扫描排队或运行 | RUNNING | CURRENT | 当前成功构建满足前置 |
| 当前有效扫描成功，包括零 finding | DONE | CURRENT | 当前成功构建满足前置 |
| 当前有效扫描失败、取消、超时 | BLOCKED | CURRENT | 不以更早成功替代 |

环境和源码已就绪时，overview 将 x86 构建排在 KB 扫描之前。overview、KB latest 和 readiness 采用可重复读事务，避免单个响应混用并发变更前后的上下文。

## API 与历史读取

创建入口未满足前置时返回 `409 PREREQUISITE_NOT_SATISFIED`，details 包含 `stageId=kb` 和 prerequisite 的 key、status、reasonCode。不会留下 task、event、scan 或队列消息。显式指定本项目历史源码仍受同一构建前置约束；跨项目请求仍拒绝。

KB 响应增加 `executionContext`、`current`、`message`、`message_en`，不提供服务器路径、凭据或存储 key。`currentSourceRevision` 仅表示源码 ID 是否相同，完整有效性以 `current` 为准。失效原因包括：

- `KB_SCAN_CONTEXT_UNKNOWN`：旧记录或绑定不完整。
- `KB_SCAN_SOURCE_CHANGED`：项目或当前源码不匹配。
- `KB_SCAN_ENVIRONMENT_CHANGED`：源环境或运行环境版本变化。
- `KB_SCAN_BUILD_NOT_READY`：当前选中构建不满足成功前置。
- `KB_SCAN_BUILD_CHANGED`：绑定构建已被新构建替代。

默认 `currentOnly` 列表只返回完整匹配当前上下文的记录；`includeStale=true` 可以读取历史。latest 无当前记录时返回按创建时间最近的历史记录，即使项目已无 active source；没有任何记录才返回 EMPTY。历史详情、finding、artifact 和既有报告快照继续保留。

报告阶段 readiness 的 KB 前置只接受当前有效成功扫描。自动选择和新报告的输入解析过滤过期 KB finding，包括已经 confirmed 的历史引用；过滤不会删除这些确认记录。零 finding 仍是有效扫描结果。

## worker 行为

worker 启动前以扫描记录为事实源，对比任务输入和当前构建、环境版本；旧载荷或失效上下文受控失败，记录 `KB_SCAN_CONTEXT_INVALID` 和中英文说明，不启动 scanner。仅 active source 切换时，只要绑定历史源码的构建和环境仍有效，可以继续执行。

compile database 只读取绑定构建：可用且归属正确为 USED；成功构建未提供数据库为 NOT_AVAILABLE；artifact 缺失、归属错误、下载或内容校验失败为 FALLBACK。没有成功构建不属于降级路径。scanner 启动后发生上下文变化，保留原输入及真实终态，由查询规则将结果判为历史。

## 升级与回滚

1. 备份数据库并停止接收新的 KB 任务，等待活动任务结束或按既有取消流程结束；API 和 worker 应共同升级。
2. 由新 API 执行 Liquibase `0128`，再启动同版本 worker。三个新增字段允许全部为空，禁止部分填写；历史记录不推测回填。旧排队任务由新 worker 判为失效，应在构建前置满足后重新提交。
3. 验证创建拒绝、latest、overview、readiness，以及已有历史详情可读。只允许新版本写入完整绑定。
4. 如需回滚，先停止新任务并停止 API/worker，恢复已验证的数据库备份与对应旧版本镜像。不要在仍有新 worker 的情况下删除列或 trigger；旧版本恢复后不再具备本变更的一致性保证，应继续禁用 KB 创建直到修复版本部署。

## 验证入口

从仓库根目录执行 Docker 单元测试和 Python 覆盖率命令，见 [开发指南](../../docs/开发指南.md)。Java `clean verify` 保持全部自有包及整体 LINE/BRANCH ≥90%，仅排除生成的 jOOQ 类型。独立数据库测试 `KbScanDatabaseTests,LiquibaseMigrationTests` 需显式提供 `RVPORT_MIGRATION_TEST_ENABLED=true` 及测试 JDBC 参数，不能指向部署数据库。

本变更实际执行记录见 [验收记录](../openspec/changes/archive/2026-10-28-fix-kb-scan-workflow-consistency/verification.md)；原始报告位于根目录 `.migration-reports/fix-kb-scan-workflow-consistency/`（不纳入公开源码）。
