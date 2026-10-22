# Frontend 全量代码复核（2026-09-30）

## 范围与方法

以当前未提交工作区为准，范围覆盖整个 frontend：src 中全部 TS/TSX/SCSS、测试、依赖和构建配置、清理脚本、Docker/Nginx 前端部署配置。未读取或修改后端实现。

这次是全量静态检查、按模块人工审查和完整自动回归，不是只复查上一轮改动，也不是宣称逐个页面完成了真实服务浏览器验收。TS 导入图从 main.tsx 追踪静态导入、动态 import 与 re-export；扫描全部源码中的请求、mutation、query key、事件监听、计时器、存储、下载、异步校验和高风险类型断言，再沿实际调用方核查生命周期。

人工检查覆盖认证与路由、请求/CSRF/缓存、首页及个人中心、用户/Worker/邮箱/模型管理、Workflow/Step、全部阶段的数据 Hook 与主要页面、日志和编辑器、公共表格/弹窗、样式边界及前端部署配置。静态导入图无未解析本地引用、无业务阶段对另一业务阶段内部文件的横向引用。

## 本轮确认并处理的问题

| 编号 | 触发与影响                                                                                     | 处理及验证                                                                                        |
| ---- | ---------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------- |
| A1   | 构建日志详情只持有列表快照，执行结束后状态/退出码仍旧                                          | 增加按 build ID 的详情查询，日志完成刷新该详情；回归验证列表 RUNNING 与详情终态不一致时使用新数据 |
| A2   | Worker 并发与用户密码弹窗在异步校验前没有锁定提交，目标切换还可能保留密码草稿                  | 校验纳入 useSubmissionSession，目标/可见性/身份共同约束；校验失败恢复编辑，切换用户清空密码       |
| A3   | 环境行检查过程中打开编辑层会失去提交归属，返回列表残留 loading 并阻止后续操作                  | 行操作归属绑定实际仍挂载的列表生命周期；回归覆盖检查中进入编辑、请求完成、返回与再次检查          |
| A4   | x86 构建更新没有刷新依赖它的知识库扫描 readiness                                               | x86 构建事件失效范围增加 kb readiness，事件测试验证                                               |
| A5   | 公共表格的 keepPreviousData 无资源边界，切换资源时短暂显示旧行                                 | 仅在相同领域 query key 内保留分页数据；回归同时检查分页保留、资源切换清空                         |
| A6   | “纳入报告”在不同列表/详情入口有不同刷新范围，依赖详情遗漏报告 readiness                        | 报告 readiness 与优化轮次失效由公共操作统一负责；消费方仅提供其记录与列表 key                     |
| A7   | 活动模型探测的首次详情请求失败且没有 data 时，轮询返回 false，停止观察未完成任务               | 没有详情时使用已知活动任务状态继续观察；受控时钟验证首次失败后的再次读取                          |
| A8   | 环境表单预加载附加 then 没有失败处理，会产生额外未处理拒绝                                     | 附加预加载回调显式处理拒绝，实际 lazy 加载失败仍交给路由错误边界                                  |
| A9   | 无生产调用的 LogViewer、首页聚合出口，以及 DatePicker 值类型错误且无调用的 date/dateRange 分支 | 删除旧组件及其废弃测试、聚合出口、未使用日期筛选分支；更新 BaseTable 类型与说明，不保留兼容包装   |

## 保留的设计和限制

- 风险分析示例页是当前另一活动 change 的明确预览实现，有“示例数据”提示和真实调用，不能当成废弃代码删除；人工修复阶段是线下修复导航，不擅自新增在线编辑业务。
- report-list-fixtures.ts 只有测试引用，属于测试夹具，不是无用生产实现。
- Monaco/CodeMirror 已按需加载，但编辑器 chunk 仍超过 500 kB。保留构建告警，不调大阈值掩盖；进一步裁剪需要实际编辑器功能和加载性能基线，本轮没有性能收益的量化结论。
- project.ts、SSE 路由和部分页面仍较长。当前没有证据证明仅按行数拆分会改善行为；本轮优先修复实际边界，未进行无行为收益的大面积重排。
- API 类型与适配器仅按前端声明和测试契约核查，没有据此声称后端实际响应完全吻合。
- 本轮未执行真实登录态、跨账号、SSE 重连和三档桌面浏览器验收，也未构建/运行 Docker 镜像。8.2 与主规范同步继续保持待完成。

## 文件覆盖清单

下表是完整源码清单的模块分组。计数包含 src/test 支持文件和测试 fixture，排除 `*.test.*`；SCSS 纳入静态检查和构建，不代表视觉验收。修改后的快照为 269 个 TS/TSX、60 个 SCSS。

| 目录/模块（相对 src）                               | 文件数 | 行数 |
| --------------------------------------------------- | -----: | ---: |
| src 根入口                                          |      4 |  114 |
| api                                                 |     21 | 1749 |
| components/BaseDrawer                               |      2 |  175 |
| components/BaseModal                                |      2 |  165 |
| components/BaseTable                                |     10 |  937 |
| components/CodeMirrorEditor                         |      4 |  201 |
| components/ContentState                             |      3 |  177 |
| components/DebouncedSearchInput                     |      1 |  107 |
| components/EllipsisText                             |      1 |   45 |
| components/FeedbackBridge                           |      1 |   26 |
| components/MonacoEditor                             |      3 |  489 |
| components/ProjectArchitectureFlow                  |      2 |   67 |
| components/ShortIdentifier                          |      1 |   10 |
| config                                              |      1 |   93 |
| hooks                                               |      4 |  203 |
| layouts                                             |      4 |  390 |
| pages/admin/mail                                    |      3 |  575 |
| pages/admin/models                                  |     13 | 1622 |
| pages/admin                                         |      1 |    6 |
| pages/admin/users                                   |      4 |  506 |
| pages/admin/workers                                 |      4 |  627 |
| pages/auth                                          |      6 |  521 |
| pages/error                                         |      4 |   75 |
| pages/home                                          |      7 |  962 |
| pages/project-detail                                |     27 | 4795 |
| pages/project-detail/StageDrawer/Archive            |      8 | 1473 |
| pages/project-detail/StageDrawer/AssessmentReport   |     18 | 3291 |
| pages/project-detail/StageDrawer/Assets             |      6 |  702 |
| pages/project-detail/StageDrawer/AutomatedTest      |     11 | 1389 |
| pages/project-detail/StageDrawer/Build              |      6 |  810 |
| pages/project-detail/StageDrawer/Default            |      1 |   39 |
| pages/project-detail/StageDrawer/DependencyAnalysis |     12 | 1700 |
| pages/project-detail/StageDrawer/Environment        |     12 | 2106 |
| pages/project-detail/StageDrawer/KnowledgeBase      |     12 | 2675 |
| pages/project-detail/StageDrawer/ManualRepair       |      2 |  235 |
| pages/project-detail/StageDrawer/OptimizationCycle  |      7 | 1015 |
| pages/project-detail/StageDrawer/Project            |      2 |  235 |
| pages/project-detail/StageDrawer/RiskAnalysis       |      7 |  817 |
| pages/project-detail/StageDrawer/X86Build           |      7 |  876 |
| pages/project-detail/StageDrawer                    |      9 |  819 |
| pages/project-detail/StageDrawer/components         |     36 | 3805 |
| pages/project-detail/StageDrawer/hooks              |      1 |  245 |
| pages/project-detail/StageDrawer/utils              |      2 |  100 |
| pages/settings                                      |      3 |  372 |
| router                                              |      8 |  720 |
| store                                               |      3 |  120 |
| styles                                              |      5 |  150 |
| test                                                |      3 |  133 |
| types                                               |     11 | 1798 |
| utils                                               |      4 |  173 |

## 验证记录

实际最终命令和数量见 [verification.md](verification.md) 的“全量复核”节。全量 TypeScript 检查、ESLint、格式检查、单元/组件/契约回归和 Vite 构建均覆盖现有工作区；没有将其他未提交 change 的全部修改归为本轮修复。
