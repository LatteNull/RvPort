# 十节点请求与刷新所有权矩阵

> 记录时间：2026-09-04，最近校准：2026-09-07。本文描述 frontend 当前实现和后续约束，覆盖环境管理、源码管理、x86 构建、知识库扫描、依赖分析、评估报告、构建验证、自动化测试、优化闭环和归档。backend 事件契约仅用于解释 frontend 路由，本记录不修改 backend。

## 1. 读取职责先分开

| 读取类型             | 唯一职责                                                                     | 不得承担的职责                                      |
| -------------------- | ---------------------------------------------------------------------------- | --------------------------------------------------- |
| `overview`           | 项目当前 Context、页面级当前任务摘要和 SSE cursor                            | 不作为具体 Stage 的执行门禁，不替代领域 latest/List |
| `readiness(stageId)` | 判断该 Stage 的操作此刻是否允许执行，并提供 prerequisite 原因与 reference ID | 不表示阶段已完成，不用 overview 字段在前端重复推导  |
| 领域 `latest`        | 当前 Context 下最近一次领域执行事实；允许承担明确的轻量初始化用途            | 不替代完整历史，不通过固定轮询推进状态              |
| 分页 `List`          | 用户主动查看的记录集合、筛选和分页                                           | 不使用 `pageSize=1` 模拟 latest                     |
| `Detail/Log`         | 用户进入详情后读取单条内容、产物或日志                                       | 不在列表或默认视图预取全部详情                      |

## 2. 已接入节点对照

| 节点       | 打开默认视图读取                                                                                                             | readiness / latest                                                                                                                 | 会产生 SSE 的操作                                                                                                                                   | mutation 成功后的当前策略                                                                                 | SSE 刷新策略                                                                                                                         | 当前结论与风险                                                                                                                                                                         |
| ---------- | ---------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 环境管理   | 共享 `overview.runtimeEnvironments`；Drawer 动画完成后读取环境 List                                                          | 不提供通用 readiness；不读取领域 latest                                                                                            | 连接预检、已保存环境连接测试、环境检查/采集/脚本执行产生 `stageId=environment` 的任务事件；选择当前环境或编辑已选环境产生 `project.context.changed` | 新建/编辑后返回列表，由列表重新挂载读取；异步任务提交不抢跑刷新；选择当前环境只把 PATCH 响应写入 overview | 环境事实任务终态刷新 List/选项；自定义脚本按环境 ID 刷新执行记录；Context 事件刷新 overview 和 Context 下游                          | mutation 不再提前失效 Context 下游；表单输入受保护；环境 List、脚本执行记录和日志继续只按当前视图读取                                                                                  |
| 源码管理   | 共享 overview 中的 `activeSourceRevision`                                                                                    | 不提供通用 readiness；不读取领域 latest                                                                                            | Git 同步产生 `stageId=source` 生命周期事件，激活成功另发 `project.context.changed`；上传并激活源码直接产生 Context 事件                             | 上传响应只写 overview 提供即时反馈；Git 同步提交成功只提示，均不失效 Context 下游                         | source 生命周期只更新 overview；`project.context.changed` 是 Context 下游的唯一刷新者                                                | 上传和 Git 同步均已消除 mutation/source terminal 与 Context SSE 的重复下游失效                                                                                                         |
| x86 构建   | `readiness?stageId=x86-build`、当前 Context 的 `SOURCE_ONLY` 分页 List、`SOURCE_ONLY latest`                                 | readiness 是执行门禁和创建请求源码 ID 来源；latest 只初始化最近 `command` 并标记当前记录                                           | 创建/取消构建产生 `stageId=x86-build`、`resource.type=build_run`、`mode=SOURCE_ONLY` 生命周期事件                                                   | 创建或取消成功只提示，不失效查询                                                                          | 非终态事件 250ms 内按 Query Key 合并，terminal 立即刷新；同一前缀会同时刷新 List 与 latest；overview 独立批处理                      | List + latest 成对请求是当前明确用途，不是重复历史读取；创建、取消后的事实刷新只由 SSE 负责，不叠加 mutation 失效或固定轮询                                                            |
| 知识库扫描 | 结果页读取 `readiness?stageId=kb` 与 `kb-scans/latest`；配置页只读取 readiness；历史、详情、产物和 Finding List 按视图读取   | readiness 的 `ACTIVE_SOURCE` 是唯一门禁；latest 是当前扫描事实                                                                     | 新建扫描产生 `stageId=kb-scan`、`resource.type=kb_scan_run` 生命周期事件                                                                            | 创建成功只切回结果视图并提示，不主动失效 latest                                                           | latest 与历史 List 共用扫描父 key；SSE 失效父 key 后只由当前可见视图发起读取，terminal 立即刷新                                      | mutation 不与 SSE 争夺刷新所有权；不可见 latest 不保持 active；Finding 纳入状态是同步编辑，使用本地 cache 同步加一次权威校准                                                           |
| 依赖分析   | 默认页读取 `readiness?stageId=rv-dependency-analysis` 与 `dependency-analyses/latest`；历史、结果和产物按视图读取            | readiness 的 `X86_BUILD/TARGET_ENVIRONMENT` 是唯一门禁；latest 是当前分析事实                                                      | 新建分析产生 `dependency_analysis_run` 事件；自动修复产生 `dependency_auto_fix_run`，默认还会创建新的分析任务                                       | 创建分析和自动修复成功都只提示并切换视图，不失效 latest/List                                              | 分析任务失效共同父 key；latest 与历史 List 只有可见一方保持 active；自动修复不冒充分析 latest                                        | x86 生命周期和源码/环境 Context 变化会刷新本阶段 readiness；历史/详情不受不可见 current 查询的 loading/error 阻断；自动修复运行详情仍待独立契约                                        |
| 评估报告   | 默认页读取 `readiness?stageId=report` 与 `reports/evaluation/latest`；报告输入快照和来源详情按需读取                         | `KB_SCAN/DEPENDENCY_ANALYSIS/INCLUDED_FINDINGS` 是生成门禁；`COMPARABLE_REPORT` 只服务比较；latest 是当前报告事实                  | 新建报告产生 `stageId=evaluation-report`、`resource.type=report` 生命周期事件                                                                       | 创建成功只提示，不失效 latest                                                                             | 仅 `resource.type=report` 的生命周期刷新 latest；KB/依赖生命周期及 Context 变化精确刷新 readiness；来源详情中 current 查询保持停用   | 不再读取 overview 或 `pageSize=1` List 推算当前报告；报告比较/复检不误刷报告 latest；纳入状态同步编辑后精确校准 report readiness                                                       |
| 构建验证   | 默认页读取展示 Context、`readiness?stageId=build`、`builds/latest?mode=VALIDATION` 与 `BOTH` 分页 List；日志按视图读取       | readiness 的 `ACTIVE_SOURCE/SOURCE_ENVIRONMENT/TARGET_ENVIRONMENT` 是唯一门禁和创建源码 ID 来源；latest 只初始化命令并标记当前记录 | 新建/取消构建产生 `stageId=build-validation`、`resource.type=build_run`、`mode=BOTH` 生命周期事件                                                   | 创建和取消成功只提示，不失效 latest/List                                                                  | 构建生命周期失效 `VALIDATION` 父 key，非终态合并、terminal 立即刷新；terminal 同时刷新自动化测试 readiness；日志视图不读取主视图查询 | 不再读取 `pageSize=100` List 推算门禁或固定轮询；List 直接承担完整构建记录主视图，latest 只提供明确的当前标记和构建命令初始化，不重复展示结果                                          |
| 自动化测试 | 当前页读取 `readiness?stageId=test`、`automated-tests/latest`、当前源码测试 List 与比较 List；历史、批次详情和日志按视图读取 | readiness 的 `BUILD_VALIDATION` 是唯一执行门禁和源码 Context 来源；latest 是当前批次锚点并初始化命令，List 不选择当前批次          | 成对创建/取消测试产生 `stageId=automated-test` 的 `automated_test_run` 生命周期事件；双端完成后产生 `test_comparison_run` 事件                      | 创建和取消成功只提示，不失效 latest/List                                                                  | 测试与比较事件失效各自父 key，非终态合并、terminal 立即刷新；terminal 精确刷新归档 readiness；历史/详情/日志/关闭态停用 current 查询 | backend latest 只返回单侧运行，且 tests List 暂无 batch 过滤，因此 List 仍辅助补齐同批另一侧；readiness 详情缺少双 build ID 时暂以构建 List 补齐 POST 输入，均不参与门禁或当前批次选择 |
| 优化闭环   | 当前页读取 `readiness?stageId=optimize` 与 `optimization-cycles/latest`；历史只在历史视图分页读取，历史详情复用所选记录      | readiness 的 `ACTIVE_SOURCE` 只判断当前源码前置；仅 `CURRENT latest` 可作为当前轮次，STALE 只进入历史，不读取旧 overview 聚合      | 本节点没有异步写操作；轮次由源码 Context 自动创建，上游报告/复检、构建、测试和比较任务会改变聚合内容                                                | 纳入/排除迁移问题是无 SSE 的同步编辑，响应更新来源缓存后精确失效优化轮次父 key                            | 上游相关生命周期失效优化轮次父 key；Context 变化刷新 readiness 与父 key；历史/详情/关闭态停用 current readiness/latest               | 删除 frontend `/optimization/overview` 读取；latest execution 当前为空，页面下一步仍由 latest result 的汇总字段保守计算；历史 List 不参与当前轮次选择                                  |
| 归档       | 当前页读取 `readiness?stageId=archive` 与 `archives/latest`；历史仅在历史视图分页读取，详情按归档 ID 读取                    | readiness 的 `ARCHIVE_CANDIDATES` 是唯一创建门禁；latest freshness 判断归档是否属于当前源码，STALE 可下载但不冒充当前交付事实      | 创建归档产生 `stageId=archive`、`resource.type=project_archive` 生命周期事件                                                                        | 创建成功只提示，不主动 refetch latest/List，也不刷新 project overview                                     | 归档生命周期失效 archives 父 key；会登记候选的上游任务仅在 succeeded 时刷新 archive readiness；历史/详情/关闭态停用 current 查询     | 删除 frontend `/archives/overview` 与项目 overview 读取；历史刷新只刷新当前可见 List；latest execution 状态覆盖 result 状态；无候选时引导回优化闭环                                    |

## 3. 写操作必须先归类，再选择一个刷新所有者

| 写操作类型                                                | mutation 成功时                                                             | SSE 到达时                                                                           | 推荐所有者                                        |
| --------------------------------------------------------- | --------------------------------------------------------------------------- | ------------------------------------------------------------------------------------ | ------------------------------------------------- |
| 同步实体写入，响应就是新事实                              | 使用 `setQueryData/setQueriesData` 合并响应，或让返回视图的 List 只读取一次 | 无事件则按需做一次精确失效                                                           | mutation 响应                                     |
| 同步 Context 写入，backend 发布 `project.context.changed` | 可以本地合并 overview 提供即时反馈；不要同时广泛失效全部 Context 下游       | Context 事件批量刷新 overview，并按 changedFields 精确失效下游 readiness/latest/List | `project.context.changed`；mutation 只负责即时 UI |
| 异步任务创建，POST 只返回 task/run                        | 成功提示、锁定本地输入，不即时失效领域 key                                  | `created/queued/started` 合并刷新，terminal 立即刷新                                 | SSE                                               |
| 同步业务状态编辑且没有任务事件                            | 先同步已知缓存，再精确失效需要服务端重算的聚合或 readiness                  | 不等待不存在的 SSE                                                                   | mutation 响应 + 一次精确校准                      |

任何操作不得同时采用“mutation 广泛 invalidate + 每个 SSE 生命周期 invalidate + 固定 `refetchInterval`”三条刷新链路。

## 4. SSE 刷新路由基线

| 事件                          | overview                          | 领域查询                                                                           | readiness                                                                           |
| ----------------------------- | --------------------------------- | ---------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------- |
| `task.created/queued/started` | 5 秒固定窗口内合并一次            | 同一 Query Key 在 250ms 内合并一次，并使用 `cancelRefetch: false` 避免重启在途请求 | 仅当该事件已经改变另一 Stage 的 prerequisite 时刷新，不机械刷新当前 Stage readiness |
| `task.progress`               | 最多每 10 秒刷新一次当前任务摘要  | 默认不请求领域 latest/List；后续若采用按 taskId 局部写 cache，必须集中实现         | 不刷新                                                                              |
| terminal                      | 立即刷新并显示通知                | 清除待执行的非终态 timer，并立即读取最终领域事实                                   | 只刷新依赖此结果的下游 Stage readiness                                              |
| `project.context.changed`     | 250ms 固定窗口内合并权威 overview | 按 changedFields 失效受 Context 影响的领域查询                                     | 按依赖图失效对应 Stage readiness                                                    |
| `task.log`                    | 不刷新，只推进 cursor             | 日志详情由用户当前视图读取或手动刷新                                               | 不刷新                                                                              |

## 5. 稳定约束

1. readiness：源码或环境 Context 变化、x86/KB 等上游 terminal 成功时，只失效真正依赖它们的下游 readiness；不得把所有 readiness 绑定到所有事件。
2. Query Key：List 与 latest 刷新节奏不同时使用显式的 `records` 与 `latest` key；只有确实需要二者同时更新时才失效共同父前缀。

## 6. 新节点或新操作检查表

- [ ] 明确页面事实来自 overview、readiness、latest、List 还是 Detail，不重复读取同一事实。
- [ ] 标记写接口是同步写入、Context 写入还是异步任务创建。
- [ ] 核对 backend 是否发布 `task.*`、`project.context.changed`，以及 stageId、resource.type/id/mode。
- [ ] 为 mutation 与 SSE 指定唯一主要刷新所有者；异步任务创建成功不抢跑刷新领域事实。
- [ ] 非终态 SSE 使用共享合并机制，terminal 立即刷新，不自行增加定时器。
- [ ] readiness 只在 prerequisite 可能变化时失效，latest/List 只在对应领域事实可能变化时失效。
- [ ] 历史、详情、产物和日志仅在对应视图打开时读取。
- [ ] 分页 List 不因窗口重新聚焦或网络重连隐式刷新；实时事实由 SSE、视图挂载和用户手动刷新负责。
- [ ] 用户编辑中的表单不被 SSE、手动刷新或异步查询覆盖。
- [ ] 测试至少断言：打开时请求集合、mutation 后请求次数、连续生命周期事件合并次数、terminal 最终刷新、Drawer 状态变化不卸载。
- [ ] 使用浏览器 Network 验证一次完整链路，并区分“不同职责的成对请求”和“同一职责的重复请求”。
