## Context

当前实现有三处独立判断：

1. `SourceService`、`SourceFetchRuntimeService` 在激活源码时创建或复用轮次；`ProjectWorkflowStatusService.optimize` 却以轮次存在直接返回 `DONE`。
2. `OptimizationCycleRepository.summary` 对构建和测试仅按项目、源码聚合；比较查询允许任意一侧源码匹配。旧环境、单侧执行和不属于同一验证链的成功结果可能组合成“已完成”。
3. `OptimizationCycleService.latest` 将可空 active 源码传给可省略过滤条件的查询，无 active 源码时可能命中历史并标记 `CURRENT`。

前端流程图直接消费 workflow 状态；优化抽屉使用 `summary.build.latestStatus`、`summary.test.latestStatus` 以及 `summary.testComparison.overallStatus ?? status` 自行计算下一步。只增加后端新字段而不修正这些旧字段无法修复抽屉。现有比较枚举为 `EQUIVALENT`、`DIFFERENT_ACCEPTABLE`、`DIFFERENT_BLOCKING`、`INCONCLUSIVE`；前端另兼容 `CONSISTENT`，本次不新增该后端枚举。

相关源码入口位于 `src/main/java/cn/rvport/backend/{optimization,project,workflow,buildvalidation,automatedtest,testcomparison}`。本 change 属于 backend 独立 OpenSpec 根；前端仅用于只读核对消费协议。

## Goals / Non-Goals

**Goals:**

- 统一当前轮次的有效验证事实，使项目 overview、优化 overview、latest 及当前轮次详情在同一数据快照下得出一致结论。
- 明确闭环完成、尚缺前置、正在比较、失败或比较不通过的状态，以及历史记录的保留和失效规则。
- 在不修改前端的条件下修复流程图提前完成及当前轮次误导归档的提示。
- 完成可重复的 Docker 单元测试、全量及受影响模块覆盖率门槛、隔离数据库查询验证与完整 Compose 验收。

**Non-Goals:**

- 不判断业务优化是否收敛，不自动触发修复、构建、测试或比较，不新增轮次 `PASSED/FAILED/CONVERGED` 状态，不改变归档 API 的准入规则。
- 不修改前端代码、前端规范、前端展示文案或工具业务逻辑；不新增 CI/E2E、真实环境或真实 SSH 测试设施。
- 不把整个项目所有领域 latest 重构纳入此次修复；共享查询调整须局限于本验证链需要，并回归既有调用方。

## Decisions

### 1. 源码轮次与验证事实分开表达

保留源码激活即创建轮次、同源码复用以及 ACTIVE/SUPERSEDED/ARCHIVED 生命周期。优化闭环 `DONE` 仅表示本轮当前验证链满足，不代表收敛；由查询计算，不回写生命周期或 `completedAt`。迁移输入、报告、复检和部署保留事实摘要，不以它们存在、Finding 数量为零或轮次被归档代替验证通过。

曾考虑延迟创建轮次至验证成功，但会失去未完成轮次的可视化和历史组织能力，因此不采用。

### 2. 一个共享解析结果驱动所有当前读取入口

增加专门的优化验证事实解析组件（具体类名由实施确定），一次接收项目当前 Context、运行环境配置和轮次，返回构建两侧、选中测试批次及两侧测试、比较引用、有效性、workflow 状态及原因。业务判定为可单测的纯规则；数据库选择集中在有界查询中。各读取入口不得各写一份成功条件。

当前查询必须先确认 active 源码及两侧环境存在，再使用必填条件查询；禁止以 `null` 表示“当前上下文缺失”同时省略 SQL 条件。历史查询使用独立且明确的入口。

采用单次只读一致快照（沿用项目 overview 的 REPEATABLE_READ；优化读取入口使用等效边界），将 Context 和结果引用放在同一事务内。不同 HTTP 请求之间若实际发生变更可以不同；相同快照中的外壳 Context、summary 与 workflow 不得混用新旧数据。

### 3. 验证链及确定性记录选择

验证链依次为：

`active 源码 → 当前双端 BOTH 构建 → 绑定上述构建的同批次双端测试 → 精确绑定两侧测试的比较`

| 环节 | 必须匹配的事实 | 满足条件 |
|---|---|---|
| 构建 | 项目、active 源码、各侧环境 ID、当前环境配置版本、`buildScope=BOTH` | SOURCE 和 TARGET 两侧选中记录均 `SUCCEEDED` |
| 测试 | 项目、源码、环境 ID/版本、同一非空 `testBatchId`、正确 SOURCE/TARGET 角色、各自 `buildRunId` 等于选中构建 ID | 同批次两侧选中测试均 `SUCCEEDED` |
| 比较 | 项目、选中批次、精确的 `sourceTestRunId` 与 `targetTestRunId`；两侧源码和环境关系均正确 | `status=SUCCEEDED` 且 `overallStatus=EQUIVALENT` |

构建复用现有各侧 `BOTH` 选择语义：活动执行（PENDING/QUEUED/RUNNING）优先，其次创建时间降序、ID 降序；不能把 `SOURCE_ONLY` 成功视为双端构建完成，也不凭时间相近臆造不存在的构建批次。

测试先在当前源码和环境上下文中确定最新候选批次，再校验该批次是否完整以及构建引用是否精确有效。活动批次优先，批次按其最新任务创建时间和稳定 ID 排序；批次内各角色同样活动优先，再按任务创建时间和运行 ID 排序。缺少批次、角色、环境版本、任务创建依据或构建引用的旧记录不能作为通过证据；无法证明当前有效的候选不得促使回退至更早完整成功批次。`startedAt=null` 的排队执行不得被忽略。

比较按精确两侧测试 ID 和批次选择，活动优先，再按创建时间、ID；不能使用“任一侧源码相同”的 OR 条件，也不能先筛选成功结果。选中失败、取消、超时、不可用或无结论记录时，不回退旧成功比较。`DIFFERENT_ACCEPTABLE` 表示存在可接受差异，但本次不把它视为自动通过；当前前端也不会因此提示归档。后续若要纳入通过集合，应作为明确的产品规则变更。

### 4. workflow 状态和 readiness 含义

按最早未满足环节决定原因；后续历史成功不能覆盖前序缺口。

| 当前事实 | OPTIMIZE 状态 | 后续动作摘要 |
|---|---|---|
| 无 active 源码或无对应轮次 | PENDING | 补齐源码或轮次事实，不能归档 |
| 缺少可解析的当前环境或环境快照版本不匹配 | PENDING | nextAction 为空，保留缺失事实 |
| 当前环境可解析但缺少构建，或构建仍活动 | PENDING | 构建验证 |
| 当前选中构建失败、取消或超时 | BLOCKED | 构建验证 |
| 构建通过，但测试缺失、失效、不成对或仍活动 | PENDING | 自动化测试 |
| 当前选中测试失败、取消或超时 | BLOCKED | 自动化测试 |
| 双端测试通过，比较缺失 | PENDING | 查看自动化测试/比较 |
| 同一验证链比较排队或运行 | RUNNING | 查看自动化测试/比较 |
| 比较失败、不可用、无结论或不是 EQUIVALENT | BLOCKED | 查看自动化测试/比较 |
| 整条当前验证链通过 | DONE | 归档入口 |

状态保留项目既有枚举；原因码区分 SOURCE、BUILD、TEST、COMPARISON 的缺失、失效、活动和失败，不将原始异常文本当原因。所需展示说明同时提供中文、英文（例如 `reason` 与 `reason_en`），不泄漏日志或路径。已有其他阶段推荐顺序继续优先处理前序阶段。

`readiness?stageId=optimize` 表示可查看聚合事实：保留 `ACTIVE_SOURCE` 前置及既有外壳，不要求双端测试通过才能打开。不在 readiness 放按钮、推荐动作或 `ready`；验证未完成应在摘要中可见。

### 5. 兼容摘要与原始历史事实分别保留

保留 `summary.build/test` 的形状。其 `latestStatus` 表示当前有效双端阶段的汇总，仅两侧均成功才能为 `SUCCEEDED`。活动优先，其次失败终态，再缺失，最后双端成功；存在缺失侧且另一侧成功时返回空状态，不能返回单侧 `SUCCEEDED`。若前序链已失效，下游有效摘要为空。状态原因和两侧真实记录引用在增量的验证事实中给出。

`latestRunId` 和时间必须来自实际选中的代表记录：活动/失败时指向决定汇总状态的记录；双端成功时按确定性排序选代表；缺失导致空状态时引用与时间也为空，不伪造一个不存在的执行。`total/byStatus` 仅统计本次有效候选集合，原始历史总次数通过独立历史摘要保留，不能与当前摘要混为同一口径。

增加只读 `validation` 摘要（包含状态、原因码、双语说明和两侧安全引用）及 `historicalSummary` 原始历史事实摘要。旧字段承担现有客户端兼容，增量字段用于解释与审计。比较未成功时，兼容 `summary.testComparison.overallStatus` 不得泄露遗留 `EQUIVALENT` 而使前端错误跳到归档；真实原值保留于历史摘要和既有比较详情，不修改数据库事实。合法但未通过的已完成比较保留其真实枚举，不改写为 EQUIVALENT。

当前轮次的 overview/latest/list/get 使用同一有效摘要。历史轮次的 list/get 及 STALE latest 保留该源码的原始事实摘要，并以增量 validation 明确不适用于当前验证链，不给出当前归档建议；轮次身份、分页、过滤、资源详情访问不变。现有前端只从 CURRENT latest 取当前轮次，历史详情已有“只读记录”标记且不显示操作按钮，因此不需要清空历史摘要。历史详情仍可能使用旧前端通用的“本轮验证通过”等标题描述该历史轮次，精确区分历史结论文案属于后续前端需求，不影响当前 workflow 判定。

latest 的 `result.nextAction` 按既有规范补齐为后端的安全动作摘要，与 validation 一致；它是增量兼容字段，不能假设旧前端已经消费它。缺少源码或轮次时不能推荐归档。字段只表达阶段和双语说明，不下发可执行命令或绕过权限的链接。

### 6. 轮次新鲜度与历史失效规则

| 变更/情况 | latest 外壳 | 当前验证链 |
|---|---|---|
| 当前源码对应轮次存在，尚无构建 | CURRENT | 未完成；CURRENT 不表示 DONE |
| 同源码环境 ID 或配置版本变化 | CURRENT（轮次仍属于当前源码） | 旧构建及其下游证据失效 |
| 同上下文重新 BOTH 构建 | CURRENT | 以新选中构建为准；旧构建所绑定的测试/比较失效 |
| 新测试批次仅一侧、失败或仍运行 | CURRENT | 不回退旧批次成功结果 |
| 仅存在其他源码的历史轮次 | STALE | 历史只读，不驱动当前完成 |
| 无 active 源码，但有历史轮次 | STALE | 显式历史分支，禁止 null 条件命中 CURRENT |
| 完全没有轮次 | EMPTY，result/execution 为 null | 未完成 |

同源码轮次 CURRENT 是容器归属，子证据新鲜度由 validation 表达；不把旧环境的子结果当成 CURRENT 成功事实。切回历史源码时复用原轮次，但按此刻环境和最新候选重算有效性，不恢复缓存的 DONE。失效只改变读取资格，不删除、不改写执行状态，不根据时间猜填历史关联字段。优化轮次没有自身执行任务，latest 的 `execution` 保持 null。

### 7. 验证与验收范围

- 单元测试覆盖解析纯规则、查询过滤/排序、服务一致性、DTO 序列化、权限和空数据；使用真实有效断言，参数矩阵覆盖每一种失败、失效、缺失及新旧候选竞争路径。
- 用后端契约测试重现现有前端的三个字段判定条件，断言其是否进入归档与后端 DONE 一致；同时断言正确双端关联，不能只测试两个同实现函数互相相等。
- 独立 Docker PostgreSQL 作为补充验证真实 SQL、跨源码比较隔离和快照并发行为，不替代单元测试，不连接部署库。
- Java 在当前源码构建的 backend `unit-test` 镜像中执行 `mvn -B clean verify`，保留 JaCoCo BUNDLE/PACKAGE 以及已有 CLASS 更严格规则；全部自有 Java 源码纳入分母，自动生成 jOOQ 和第三方依赖明确排除理由。
- 后端资源 Python 按根开发指南执行全量 `coverage run --branch --source=src/main/resources/analysis,src/main/resources/bitcode -m pytest src/test/python`，分别检查整体和每个脚本行/分支至少 90%，不能用综合百分比代替两个指标。
- 行/分支覆盖率分别报告后端整体、optimization/project/workflow 及实际改动的 buildvalidation/automatedtest/testcomparison 等完整包；保留全包门槛而非仅变更行。无分支代码标明无适用分支，不伪造百分比。若发现大规模历史缺口，报告并请求扩大范围，验收保持未完成。
- 按根开发指南顺序执行 Docker 构建/测试并限制 CPU、内存和编译并发。最后从根目录使用独立 Compose project、专用测试 env、网络、卷及安全端口完成全部默认服务构建；一次 `docker compose up -d --wait` 启动全部默认服务，检查健康、日志、登录/建项目/配置环境/上传源码后状态以及历史查询。完整成功链与失效矩阵可由已执行单元测试和隔离数据库验证证明，不能声称完成未执行的真实 SSH 端到端链路。
- 报告保存到根 `.migration-reports/fix-optimization-cycle-workflow-consistency/`，包括源码标识、命令、退出码、Surefire、JaCoCo、Python 分母和门槛、Compose 配置与服务结果；私有日志不提交公开仓库。

## Risks / Trade-offs

- [收紧有效性后历史成功不再显示完成] → 保留原始事实和详情入口，给出失效原因，不回填无法证明的关联；在对接说明中明确需要重新验证。
- [旧前端忽略新增 validation/nextAction/historicalSummary] → 修正当前 summary 消费点，保留历史只读摘要；新原因细节及更精确的历史标题需要后续前端工作，本次不承诺这些展示能力。
- [旧前端构建文案固定提及 RISC-V] → 后端实际按双端验证，不通过伪造状态迎合文案；该文案精确性不在本次修复范围。
- [增加查询导致列表 N+1 或快照变长] → 查询使用有界条件和批量读取可用事实，复用同次请求 Context；通过查询验证检查无全表逐轮扫描，必要索引变更须另补迁移验证。
- [共享查询行为影响其他调用方] → 优先新增严格查询或解析适配，不全局改变 nullable 历史检索含义；维护相关服务回归测试。

## Migration Plan

1. 先完成规则、兼容契约与测试，再接入读取入口；默认无数据库迁移，不重写历史记录。
2. API 与 worker 使用同一版本镜像，按完整 Docker 验收记录发布依据。上线后已有轮次自动按当前事实重新计算，无数据回填脚本。
3. 如实施发现必须补充索引/schema，先更新设计与任务，并在 Docker 验证空库初始化、已有数据升级、重复迁移和 jOOQ 生成；不得仅手工改生成文件。
4. 回滚后端镜像不会丢失历史，但旧错误完成判断会恢复，回滚说明必须列明；有迁移时另行验证兼容回滚边界。

## Open Questions

无阻塞提案的问题。当前按严格 `EQUIVALENT` 定义验证通过，保持历史只读展示；实施若发现满足这些约束必须修改前端，应报告具体消费点并保持本次前端零改动，不自行扩展范围。
