# 优化闭环状态与结果有效性

优化轮次按源码创建和复用。`ACTIVE`、`SUPERSEDED`、`ARCHIVED` 是轮次生命周期，不能用来判断验证是否完成；读取接口不写入通过或收敛结论，也不自动创建任务。

## 完成条件

当前 active 源码必须具备以下完整关联链：

1. 当前源、目标环境和配置版本下各自选中的 `BOTH` 构建均成功。
2. 当前候选测试批次包含 SOURCE/TARGET 两侧成功测试，各自精确绑定上述构建。
3. 比较精确绑定该批次及两条测试，执行状态为 `SUCCEEDED`，结论为 `EQUIVALENT`。

只满足上述全部条件，项目 overview 的 `optimize` 才为 `DONE`。`DIFFERENT_ACCEPTABLE` 暂不自动视为通过。报告存在、Finding 为零、单侧成功或归档过轮次均不能替代验证链。

| 事实 | optimize 状态 |
|---|---|
| 缺源码、环境、构建或测试；前序构建/测试仍活动 | PENDING |
| 当前构建或测试失败、取消、超时 | BLOCKED |
| 双端测试通过，比较缺失 | PENDING |
| 当前比较排队或运行 | RUNNING |
| 比较失败、不可用、无结论或不等价 | BLOCKED |
| 当前完整验证链通过 | DONE |

## API 与兼容字段

- `/api/projects/{projectId}/overview`、`/optimization/overview`、`/optimization-cycles/latest` 和当前轮次列表/详情复用同一验证解析。
- latest 的 `CURRENT` 表示轮次属于当前源码，不表示其验证已完成；环境变化不会改变轮次归属，但会使其旧证据失效。无 active 源码而有历史时返回 `STALE`，完全无轮次返回 `EMPTY`；优化轮次没有独立执行任务，`execution` 为 null。
- `summary.build/test.latestStatus` 是双端有效状态，只有两侧成功才为 `SUCCEEDED`。`latestRunId` 和时间引用决定状态的真实代表记录；缺失导致空状态时引用为空。`total/byStatus` 统计选中的有效候选，不代表历史执行总次数。
- `summary.testComparison` 仅为当前精确验证链的比较。比较执行未成功时，不将遗留的 EQUIVALENT 作为当前 `overallStatus` 返回。
- `historicalSummary` 保留原始历史摘要；`validation` 提供状态、稳定原因码、`reason/reason_en` 及安全的双侧引用；`nextAction` 提供阶段及 `description/description_en`。源码或运行环境上下文无法解析时 nextAction 为空，避免基于不完整上下文推导动作；旧客户端仍可沿用其构建页引导。它们不携带凭据、日志或执行命令。
- 非当前轮次列表/详情及 STALE latest 保留历史摘要；validation 标记历史不适用于当前验证，nextAction 为空。分页、过滤、排序、项目权限和资源详情保持原有协议。
- `readiness?stageId=optimize` 的 ACTIVE_SOURCE 仅表示可打开查看，验证尚未通过时仍可查看缺失/失败事实。

现有前端直接读取 workflow 状态，并用 build/test 的 latestStatus 和比较 overallStatus 判断下一步。本修复修正这些现有字段，不要求前端消费新增字段。历史详情已有只读标记和操作限制。前端固定的 RISC-V 文案、历史结论标题和新增原因的精细展示保持现状；本次不修改前端。

## 历史失效与选择

活动执行优先，再按创建时间降序和稳定 ID 排序。测试以任务创建时间选批次，不能按 startedAt 忽略尚未启动的任务；先选候选批次，再检查双侧和构建引用。新批次缺少一侧、失败或关联错误时，不能回退旧成功批次或跨批次拼接。

源码、环境 ID/配置版本变化后重算当前资格；重建后旧构建所绑定的测试和比较失效；重测后旧测试对的比较不能复用。缺少批次、角色、版本、构建引用等旧数据保留历史可读性，不凭时间猜填。切回历史源码也重新解析，不恢复缓存的 DONE。

所有失效均不删除、不改写历史执行状态。当前查询为有界 SQL，按项目及上下文过滤；单次读取使用 REPEATABLE_READ，避免响应混合不同上下文。不同 HTTP 请求间真实状态变化允许返回不同快照。

## 验证与部署

实施仅涉及 optimization 与 project 生产代码；复用既有 buildvalidation 查询，workflow、automatedtest、testcomparison 作为关联回归范围。无需 schema 迁移、jOOQ 生成或历史数据回填。

从仓库根目录按[开发指南](../../docs/开发指南.md)重建 backend unit-test 镜像，在 Docker 执行完整 Maven clean verify 和资源 Python 单元测试。JaCoCo 保留整体、所有包及既有类的行/分支 90% 门槛；生成 jOOQ 与第三方依赖不计入自有业务分母，未加载自有类和脚本仍纳入。独立数据库补充测试通过 `-Dtest=OptimizationEvidenceDatabaseIT test` 显式执行，使用 `RVPORT_TEST_JDBC_URL`、`RVPORT_TEST_DB_USER`、`RVPORT_TEST_DB_PASSWORD` 指向本次隔离库；该验证在随机专用 schema 内操作并清理，不替代单元测试。

API 与 worker 使用同版本镜像。按[安装指南](../../docs/安装指南.md)在独立 Compose project、网络、卷和端口完成根目录完整构建及一次全部默认服务启动，验证首次上传但未构建的状态。运行报告保存在 `.migration-reports/fix-optimization-cycle-workflow-consistency/`；实际结果以本次验证记录为准。

回滚镜像无需恢复历史数据，但会恢复旧版本的错误完成判断；部署时明确此限制。未完成测试、门槛或完整 Docker 验收时不能归档。
