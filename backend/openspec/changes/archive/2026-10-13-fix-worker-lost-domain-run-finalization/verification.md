# 最终验收记录

日期：2026-10-13。范围仅 backend；未修改前端和工具，未重启用户业务容器，未修改真实项目数据。

## 单元测试与覆盖率

在 Linux Docker `rvport-backend-quality:local` 中执行（工作目录 `/workspace/backend`）：

```sh
ln -s /usr/bin/python3 /usr/local/bin/python
mvn -B -o verify
```

挂载整个仓库到 `/workspace`，Maven 缓存到 `/root/.m2`。仅为已有用例提供容器内 python 命令，不改变宿主环境。

- 1764 项：0 失败，0 错误，2 个既有外部测试跳过。
- 跳过项为 `LiquibaseMigrationTests` 和 `RealAdapterEnvironmentInfoSmokeTest`；不计入本轮独立单测通过数量，数据库验证另行执行。
- JaCoCo 纳入所有自有编译代码，包括未加载代码，共 858 个类；仅保留原有生成的 jOOQ 代码排除，不排除业务代码。
- 整体行覆盖率 **96.6542%**（24844/25704），分支 **91.0436%**（9230/10138）。JaCoCo `check` 成功。
- 报告：`backend/target/site/jacoco/index.html`、`jacoco.xml`；测试明细：`backend/target/surefire-reports/`；完整命令日志：`backend/target/worker-finalization-verify.log`。

| 受影响包（cn.rvport.backend 下） | 行覆盖率 | 分支覆盖率 |
|---|---:|---:|
| worker | 96.29% | 90.29% |
| task | 96.16% | 90.38% |
| artifact | 93.53% | 93.14% |
| analysis | 96.09% | 90.42% |
| dependency | 96.01% | 90.44% |
| dependency.autofix | 99.33% | 90.49% |
| kb.runtime | 96.30% | 90.78% |
| kb.ai | 97.40% | 90.40% |
| environment.runtime | 91.71% | 90.23% |
| buildvalidation | 96.71% | 90.39% |
| buildvalidation.bitcode | 96.12% | 90.59% |
| automatedtest.runtime | 100.00% | 95.24% |
| testcomparison.runtime | 98.35% | 92.78% |
| source.runtime | 95.82% | 90.29% |
| source.deploy | 96.37% | 90.26% |
| report.runtime | 97.27% | 90.51% |
| reportcomparison.runtime | 96.13% | 90.62% |
| archive.runtime | 100.00% | 100.00% |
| sbom.runtime（兼容历史任务） | 96.17% | 91.27% |

## 真实事务与并发

隔离 PostgreSQL 18.4，由 `TaskAttemptDatabaseIT` 使用 Liquibase 的 110 个 changeset 初始化，不手工创建 schema。显式开启外部集成测试，不加入默认单测集：

```sh
RVPORT_FINALIZATION_DB_TEST=true \
RVPORT_FINALIZATION_JDBC_URL=jdbc:postgresql://rvport-finalization-db:5432/finalization_test \
mvn -B -o -Dtest=TaskAttemptDatabaseIT -Djacoco.skip=true surefire:test
```

测试专用数据库用户 `fixture`，密码 `fixture-test-only`，不对宿主开放端口。7 项全部通过：清理先赢、发布持锁先赢、两个清理器竞争、心跳恢复、发布回滚及新旧尝试隔离、领域写入失败整体回滚、Worker 已删除的历史对账及成功 Task 仅审计。实际数据库同时执行全部领域适配 SQL。

真实数据库验证发现并修复 `test_runs.output_summary` 为 TEXT 而非 JSONB 的问题：保留原文本并追加安全原因。摘要 JSON 继续合并，已有终态和部分结果不覆盖。日志：`backend/target/worker-finalization-database.log`。

## 分进程 E2E

同一最新 JAR 启动独立 API 和 Worker 容器，共用隔离 PostgreSQL、Redis、RabbitMQ（网络 `rvport-finalization-check`），对象存储关闭。Worker 心跳正常。API cleanup 周期设置为 3000ms，其他阈值沿用默认值。

测试数据：`backend/src/test/e2e/worker-finalization.sql`；客户端：`backend/src/test/e2e/worker-finalization.py`。仅允许在上述隔离数据库执行 SQL；用户名/密码是默认测试种子，不是生产凭据。客户端挂载目标输出目录到 `/results`，连接 `http://rvport-finalization-api:8080`。

先创建 fixture，启动客户端，收到 READY 后执行：

```sql
UPDATE worker_instances SET last_heartbeat_at=now()-interval '1 hour'
WHERE instance_id='fixture-e2e-lost';
```

结果：

- Task 和 KB run 同时 `FAILED`，错误码 `WORKER_LOST`，run 结束时间补齐，`summary.retained=true` 保留。
- `kb-scans/latest` 的 execution/result 都为 `FAILED`。
- overview KB 节点从 `RUNNING` 变为 `BLOCKED`，原因 `KB_SCAN_FAILED`。
- readiness 使用真实参数 `stageId=kb`，仍准确返回 fixture 缺少源环境/x86 构建前提，不伪造就绪；不再存在运行中领域状态。
- 项目 SSE 收到 `project.context.changed` 和 `task.failed`；终态日志 SSE 返回 `task.log.completed`、状态 FAILED。
- 空日志游标仍为 0，`hasMore=false`；迟到日志拒写由独立单测覆盖。

历史对账复现：删除 fixture Worker，将 fixture Task/run 暂置 RUNNING；使用 `FIXTURE_HISTORY=true` 启动客户端并等待 READY，再仅将 Task 置 FAILED 并设置 finished_at。定时器自动收尾 run，只推送 `project.context.changed`。最终复跑中 `task.failed` 计数保持 3→3（含前几轮测试），未重复补发。

原始返回保存在 `backend/target/worker-finalization-e2e.json` 和 `worker-finalization-e2e-history.json`。E2E 模拟失联记录，不杀真实任务，不声称验证了 SSH 远端进程的退出。各领域按 taskId 的隔离、终态过滤和旧尝试拒写由单测及数据库竞争测试共同覆盖。

## 静态验收

在 backend 目录执行 `openspec validate fix-worker-lost-domain-run-finalization --strict` 通过；仓库 `git diff --check -- backend` 通过。未执行 sync、archive、commit 或 push，这些留待用户确认。

## 限制与附带观察

- 发布前必须排空旧 Worker；旧镜像仍可能绕过新尝试校验。
- 数据库失败不等于远端进程停止，远端已产生副作用不回滚。
- 无原生结束列的 source_imports 通过关联 Task 提供结束时间；其他此类记录另合并 summary.finishedAt。不新增冗余 schema。
- 提交结果未知的对象、已移动源码目录保留供核对，不冒险删除有效制品。
- E2E 首次误用 `stage` 而非 `stageId`，发现缺少必填参数时现有全局异常处理返回 500；已修正测试参数，未在本 change 扩大范围修改错误响应合同。
- 本轮没有运行全部真实 SSH/模型任务；外部连接返回值通过单测 mock，实际状态同步使用隔离服务验证。
