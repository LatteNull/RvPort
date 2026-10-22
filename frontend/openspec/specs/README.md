# 前端当前能力索引

本目录记录当前已交付的前端能力，按 2026-09-21 的实现、测试与已落地变更校准。未完成、已移除或已被替代的要求不作为当前规范保留；历史决策仅在 `../changes/archive/` 中追溯。

## 维护方式

- 修改行为前，从下表找到对应能力及实现入口。每项行为只有一个主要规范归属，阶段规范引用共享规则，避免重复维护。
- 当前规范描述持续有效的行为，不写“本 change 暂不实现”等一次性范围限制，也不将重构过程记录为产品能力。
- 新需求先由 change 定义，交付后同步当前规范；替换旧行为时同步删除旧要求，而不是只追加新要求。
- 根目录产品文档和历史原型提供背景，不覆盖这里已经校准的当前能力。实现差异需结合测试与变更记录核实，不自动将缺陷写入规范。

## 应用与共享能力

实现入口均相对 `frontend/`。

| 能力规范                                                                       | 职责                                         | 主要实现入口                                                                                    |
| ------------------------------------------------------------------------------ | -------------------------------------------- | ----------------------------------------------------------------------------------------------- |
| [frontend-application-foundation](frontend-application-foundation/spec.md)     | 工具链、API 代理、会话、路由守卫、登录与邀请 | `vite.config.ts`、`src/router/`、`src/store/authStore.ts`、`src/pages/auth/`                    |
| [request-client](request-client/spec.md)                                       | 响应包络、CSRF、请求失败与错误路由           | `src/api/request.ts`、`src/types/index.ts`                                                      |
| [common-ui](common-ui/spec.md)                                                 | 共享弹层、受控搜索与代码工作区               | `src/components/`                                                                               |
| [frontend-code-reuse](frontend-code-reuse/spec.md)                             | 领域模块、纯逻辑复用和职责拆分               | `src/api/project/`、`src/types/project/`、`src/utils/`                                          |
| [frontend-quality-baseline](frontend-quality-baseline/spec.md)                 | 质量门禁、语义、可访问性和样式边界           | `src/layouts/`、共享组件与检查配置                                                              |
| [frontend-performance-optimization](frontend-performance-optimization/spec.md) | 编辑器按需加载、表格测量与渲染边界           | `src/components/CodeMirrorEditor/`、`src/components/MonacoEditor/`、`src/components/BaseTable/` |
| [frontend-unit-testing](frontend-unit-testing/spec.md)                         | 隔离测试环境、契约与行为验证                 | `vitest.config.ts`、`src/test/`、领域就近测试                                                   |
| [frontend-container-deployment](frontend-container-deployment/spec.md)         | 开发 API 代理容器与生产 Nginx                | `deploy/docker/`、根目录 `docker-compose.yml`                                                   |

## 账户与管理

| 能力规范                                                         | 职责                                 | 主要实现入口                                                        |
| ---------------------------------------------------------------- | ------------------------------------ | ------------------------------------------------------------------- |
| [account-profile](account-profile/spec.md)                       | 个人资料、显示名称和常规改密码       | `src/pages/settings/profile/`                                       |
| [password-reset-flow](password-reset-flow/spec.md)               | 邮件重置密码及 token 处理            | `src/pages/auth/forgot-password/`、`src/pages/auth/reset-password/` |
| [admin-center](admin-center/spec.md)                             | 管理权限、用户、邮件与 Worker        | `src/pages/admin/`                                                  |
| [model-configuration-center](model-configuration-center/spec.md) | 模型 Profile、Agent 兼容性与阶段绑定 | `src/pages/admin/models/`                                           |

## 项目入口与共享运行规则

| 能力规范                                                                     | 职责                                          | 主要实现入口                                                                                                                         |
| ---------------------------------------------------------------------------- | --------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| [project-list-home](project-list-home/spec.md)                               | 项目筛选、分页卡片和导航                      | `src/pages/home/`                                                                                                                    |
| [project-creation](project-creation/spec.md)                                 | 创建字段与创建后入口                          | `src/pages/home/components/CreateProjectModal/`                                                                                      |
| [project-configuration](project-configuration/spec.md)                       | 项目资料和描述编辑                            | `src/pages/project-detail/StageDrawer/Project/`                                                                                      |
| [project-pipeline-workbench](project-pipeline-workbench/spec.md)             | 固定流程拓扑、画布、展示辅助状态和阶段导航    | `src/pages/project-detail/Workflow/`、`src/pages/project-detail/StageDrawer/index.tsx`                                               |
| [project-overview-current-context](project-overview-current-context/spec.md) | 当前源码、运行环境、最近任务与项目 SSE        | `src/pages/project-detail/useProjectOverview.ts`、`src/pages/project-detail/useProjectTaskEvents.ts`                                 |
| [project-stage-runtime](project-stage-runtime/spec.md)                       | readiness、latest、历史、状态反馈与刷新所有权 | `src/pages/project-detail/StageDrawer/`、`src/pages/project-detail/queryKeys.ts`                                                     |
| [task-log-viewer](task-log-viewer/spec.md)                                   | 实时增量、终态分页、连接恢复与日志阅读        | `src/pages/project-detail/StageDrawer/components/TaskLogPanel.tsx`、`src/pages/project-detail/StageDrawer/hooks/useTaskLogStream.ts` |

## 阶段业务

| 能力规范                                                               | 职责                                     | 主要实现入口                                                     |
| ---------------------------------------------------------------------- | ---------------------------------------- | ---------------------------------------------------------------- |
| [environment-management](environment-management/spec.md)               | 环境资源、当前环境、连接检查与脚本       | `src/pages/project-detail/StageDrawer/Environment/`              |
| [source-artifact-management](source-artifact-management/spec.md)       | 当前源码、来源锁定、压缩包与 Git 更新    | `src/pages/project-detail/StageDrawer/Assets/`                   |
| [knowledge-base-scan](knowledge-base-scan/spec.md)                     | 当前扫描、结果、历史与 AI 建议任务       | `src/pages/project-detail/StageDrawer/KnowledgeBase/`            |
| [knowledge-base-finding-detail](knowledge-base-finding-detail/spec.md) | Finding 判断、代码证据、多位置与 AI 补充 | `src/pages/project-detail/StageDrawer/KnowledgeBase/components/` |
| [build-readiness-stages](build-readiness-stages/spec.md)               | x86 单端构建与记录                       | `src/pages/project-detail/StageDrawer/X86Build/`                 |
| [dependency-analysis](dependency-analysis/spec.md)                     | 依赖分析、证据、自动修复与报告输入入口   | `src/pages/project-detail/StageDrawer/DependencyAnalysis/`       |
| [assessment-report](assessment-report/spec.md)                         | 报告输入、生成及模块—文件—Finding 阅读   | `src/pages/project-detail/StageDrawer/AssessmentReport/`         |
| [manual-repair](manual-repair/spec.md)                                 | 依赖/源码修复和验证路径引导              | `src/pages/project-detail/StageDrawer/ManualRepair/`             |
| [build-validation](build-validation/spec.md)                           | 双端构建门禁、配置与记录                 | `src/pages/project-detail/StageDrawer/Build/`                    |
| [automated-test-stage](automated-test-stage/spec.md)                   | 双端批次、构建输入、结果比较与历史       | `src/pages/project-detail/StageDrawer/AutomatedTest/`            |
| [optimization-cycle-stage](optimization-cycle-stage/spec.md)           | 本轮收敛、历史轮次与下一步               | `src/pages/project-detail/StageDrawer/OptimizationCycle/`        |
| [project-archive-stage](project-archive-stage/spec.md)                 | 当前源码交付、归档历史与下载             | `src/pages/project-detail/StageDrawer/Archive/`                  |

## 校验

在 `frontend/` 中运行：

```sh
openspec validate --specs --strict --no-interactive
pnpm exec prettier --check openspec/config.yaml openspec/project.md 'openspec/specs/**/*.md'
```

严格校验用于发现格式和结构问题；行为是否准确仍须对照当前实现、相关测试和服务端契约核实。
