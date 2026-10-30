## 1. 固化回归场景与后端兼容契约

- [x] 1.1 在 backend 独立 OpenSpec 根核对当前实现和受影响调用方；记录 optimization/project/workflow 以及实际涉及的 buildvalidation/automatedtest/testcomparison 测试与覆盖率范围，确认前端零修改。
- [x] 1.2 增加源码激活即创建轮次但尚未构建时的回归单元测试，明确 overview 为 PENDING、latest 为 CURRENT 容器、有效摘要未通过、readiness 可查看。
- [x] 1.3 定义并测试验证状态、原因码、双语说明、有效引用和 nextAction 契约，区分轮次生命周期、容器新鲜度和子证据有效性；保留已有 API 路径与字段类型。

## 2. 实现当前验证链的查询与共享解析

- [x] 2.1 增加严格的当前上下文查询入口，先检查 active 源码及环境存在，禁止缺失参数隐式省略过滤；为 null、错误项目、旧源码和旧环境添加查询单元测试。
- [x] 2.2 复用双端 BOTH 构建选择语义，按源码、各侧环境 ID、配置版本、范围查询，活动优先后创建时间与 ID；测试 SOURCE_ONLY、仅一侧成功、活动与失败不回退旧成功。
- [x] 2.3 实现先选测试候选批次、再选两侧执行并验证各自 buildRunId 的规则；测试新批次不完整、跨批次、重复角色、旧构建引用、缺少批次/角色/版本及 startedAt 为空。
- [x] 2.4 以精确 sourceTestRunId/targetTestRunId 和批次选比较，验证两侧项目、源码、环境和角色；移除任一侧源码匹配即可通过的当前聚合路径，并测试活动优先、失败不回退、跨源码和错误关联。
- [x] 2.5 实现可单测的共享验证解析和最早未满足环节优先规则；覆盖所有任务终态、比较不可用/无结论/各 overallStatus，仅完整链加 SUCCEEDED/EQUIVALENT 为 DONE。

## 3. 接入 overview、latest 与当前摘要

- [x] 3.1 将 ProjectWorkflowStatusService.optimize 从“轮次存在即 DONE”改为共享解析，回归前序阶段推荐顺序和其他 workflow 阶段。
- [x] 3.2 将优化 overview、latest、当前轮次 list/get 接入同一解析，维护只读一致快照边界，并测试相同快照下 Context、记录引用、状态的一致性。
- [x] 3.3 修复 latest 无 active 源码时的历史分支，覆盖 CURRENT/STALE/EMPTY、result/execution 的空值、同源码环境改变及切回旧源码。
- [x] 3.4 实现兼容的双端 build/test StageRunSummary，明确代表记录、时间、total/byStatus 统计口径；增加 validation、historicalSummary 和 nextAction 的安全 DTO 及中文/英文字段。
- [x] 3.5 防止未成功比较携带遗留 EQUIVALENT 触发旧前端归档；保留真实历史值与详情，测试兼容字段成功组合当且仅当后端 DONE，并独立断言正确关联链。
- [x] 3.6 保留 optimize readiness 的 ACTIVE_SOURCE 查看语义和既有事实协议，测试未构建、未测试、失败时仍可查看；查询不得触发任务、修改轮次状态或回写 completedAt。

## 4. 历史失效与访问控制回归

- [x] 4.1 覆盖环境 ID/版本变化、重建、重测、新候选失败或不完整造成的下游失效，断言旧成功链不能补齐当前缺口，历史事实没有被删除或修改。
- [x] 4.2 保留非当前轮次列表/详情和 STALE latest 的原始历史摘要；新增验证事实标明不适用于当前 Context，不给出当前归档通过建议，回归分页、过滤、排序与资源引用。
- [x] 4.3 增加 DTO/控制器序列化及权限单元测试，覆盖无子数据、非法轮次归属、无项目权限、不泄漏敏感字段和既有字段类型兼容。
- [x] 4.4 用后端契约测试复现已核对的前端三个摘要字段判定，验证当前轮次下一步为 build/test/archive 的矩阵；记录历史详情现有只读行为及固定文案限制，不修改前端。

## 5. 独立数据库与查询验证

- [x] 5.1 在独立、资源受限的 Docker PostgreSQL 中验证实际过滤、活动优先排序、批次配对和比较两侧关联；不得连接已有部署数据库。
- [x] 5.2 验证读取期间源码/环境切换和任务写入的快照边界，确保单次响应不混用上下文；检查列表查询有界且不引入逐轮全表扫描。
- [x] 5.3 核实无需 schema 迁移且无需历史回填；若实际必须新增索引/schema，先更新设计任务，再在 Docker 完成空库、升级、重复迁移、历史保留及 jOOQ 生成验证，并记录依据。

## 6. Docker 单元测试与至少 90% 覆盖率门槛

- [x] 6.1 从 D:\projects\RvPort 根目录按开发指南重建 backend unit-test 镜像；在专用容器执行完整 mvn -B clean verify，限制 CPU/内存和编译并发，不用旧镜像或定向测试代替最终完整测试。
- [x] 6.2 保留并执行 JaCoCo BUNDLE/PACKAGE 的 LINE、BRANCH 各至少 0.90 及已有 CLASS 门槛，确认未被测试加载的全部自有 Java 类纳入统计，不缩小分母。
- [x] 6.3 导出 Surefire、JaCoCo HTML/XML/CSV 和日志到 .migration-reports/fix-optimization-cycle-workflow-consistency，列出整体、optimization、project、workflow 和实际受影响完整包的行/分支 covered/total 及百分比。
- [x] 6.4 在 Docker 按开发指南执行后端资源 Python 完整单元测试，以 analysis 和 bitcode 源目录纳入未加载脚本，分别执行整体及每个脚本的行、分支至少 90% 自动检查并导出报告。
- [x] 6.5 审核生成 jOOQ、第三方等排除理由，确认无自有业务逻辑被排除；新增可执行验证脚本也同步提供单元测试和覆盖率，不以无断言测试或综合比例凑门槛。
- [x] 6.6 汇总所有测试数量、命令、退出码和门槛结果；无适用分支明确注明，任何失败/阻塞/覆盖率不足保持任务未完成；如需大规模修补无关历史缺口，先报告差距并请求扩大范围。

## 7. 完整 Docker 运行验收

- [x] 7.1 从 D:\projects\RvPort 根目录准备专用 Compose project、测试 env、独立网络/卷/端口及资源受限 override；逐模块顺序完成完整 Compose build，纳入全部默认服务，不使用真实凭据或真实 SSH。
- [x] 7.2 按根开发指南执行适用的既有前端 lint、类型检查、普通单元测试与生产构建，保持前端代码零修改；不额外引入前端覆盖率验收或新测试设施。
- [x] 7.3 使用上述同一隔离配置，以一次 docker compose up -d --wait 启动全部默认服务，记录服务健康、退出状态及脱敏日志，发现失败先修复并重新验证。
- [x] 7.4 验证登录、建项目、配置环境、上传/激活源码后尚未构建时 overview/latest/readiness 一致，优化闭环不提前完成；验证历史查询与无当前结果响应。
- [x] 7.5 汇总完整成功链、失效、失败、不完整批次的单元测试与隔离数据库证据，和实际 Compose 业务验证分开记录；不以构造数据库事实宣称真实 SSH 端到端流程通过。
- [x] 7.6 导出本次源码标识、实际完整命令、测试报告、服务状态和场景结果；只清理本次专用资源，保留必要报告，避免影响已有部署。

## 8. 文档与阶段交接

- [x] 8.1 更新 backend 范围内中文对接说明，包含状态表、完成条件、失效矩阵、当前与历史摘要口径、双语说明字段、前端既有消费点及文案限制；明确不需要前端改代码即可修复本次当前流程状态。
- [x] 8.2 记录 API/worker 同版本部署、无历史回填的理由和回滚边界；校验内容、文件引用及 openspec validate fix-optimization-cycle-workflow-consistency --strict。
- [x] 8.3 核对实现仅修改 backend 范围内代码/测试/文档，前端无修改；汇总覆盖率分母、排除理由和报告位置，全部必需任务及验收通过后才提示 sync/archive，否则提供继续 apply 的完整聊天命令。
