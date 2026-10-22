## 1. 数据库与模型

- [x] 1.1 新增 Liquibase 变更，创建 `dependency_auto_fix_runs` 和 `dependency_auto_fix_items` 表，包含运行状态、安装计划、安装结果、重跑依赖分析关联、summary 和必要索引。
- [x] 1.2 更新 `tasks_type_chk`，新增 `DEPENDENCY_AUTO_FIX` 任务类型，并保持历史任务类型兼容。
- [x] 1.3 运行 Liquibase 并执行 jOOQ 代码生成，确认新表和新字段可以被后端编译引用。
- [x] 1.4 为自动修复运行、条目、状态枚举、请求 DTO 和响应 DTO 增加 Java 模型。

## 2. 候选项与 API

- [x] 2.1 实现自动修复候选项派生服务，基于依赖分析结果计算 `selectable`、`defaultSelected`、`installPackageName`、`installVersionConstraint` 和 `reason`。
- [x] 2.2 实现 `GET /api/dependency-analyses/{analysisId}/auto-fix-candidates`，支持分页、过滤、排序和项目权限校验。
- [x] 2.3 实现 `POST /api/dependency-analyses/{analysisId}/auto-fixes`，校验 result item 归属、候选合法性、active source revision 和当前 environment config version。
- [x] 2.4 实现自动修复详情、条目分页和项目历史查询 API。
- [x] 2.5 增加审计日志，记录自动修复任务创建、选择条目数量和目标环境摘要。

## 3. Worker 与远端安装

- [x] 3.1 新增 `DEPENDENCY_AUTO_FIX` handler，并接入现有 worker 分发、任务进度、任务事件、任务日志和取消机制。
- [x] 3.2 实现包名和版本约束白名单校验，拒绝包含 shell 注入风险的安装计划。
- [x] 3.3 实现 RPM 包生态安装适配，优先支持 `dnf` 和 `yum` 的包查询、主版本匹配和安装。
- [x] 3.4 实现中风险条目安装逻辑，使用目标侧 provider package/version 作为优先安装依据。
- [x] 3.5 实现高风险条目安装逻辑，使用源侧 package name 和 source major version 在目标源中尝试匹配。
- [x] 3.6 逐条写入安装状态、exit code、错误摘要和 evidence，并确保单条失败不阻断其他条目。
- [x] 3.7 处理已安装或已满足场景，写入 `SKIPPED_ALREADY_SATISFIED` 或等效状态。

## 4. 修复后重跑依赖分析

- [x] 4.1 在修复任务有成功或已满足条目时，自动创建新的 `DEPENDENCY_ANALYSIS` 任务。
- [x] 4.2 将重跑依赖分析 run/task ID 写回自动修复运行记录。
- [x] 4.3 所有条目失败时不重跑依赖分析，并返回失败统计和主要原因。
- [x] 4.4 重跑依赖分析创建失败时保留安装结果，并写入可诊断失败摘要。

## 5. 测试

- [x] 5.1 为候选项派生规则补充单元测试，覆盖正常流程、异常流程和 edge case。
- [x] 5.2 为 API 权限、过期上下文、非法 result item、分页过滤排序和请求校验补充单元或 Web 层测试。
- [x] 5.3 为安装计划安全校验和 RPM 安装命令生成补充单元测试。
- [x] 5.4 为 worker 成功、部分失败、全部失败、取消和重跑分析创建失败补充单元测试。
- [x] 5.5 新增 API E2E 模块，覆盖候选查询、创建修复任务、任务日志、运行详情、条目详情、自动重跑分析和清理。

## 6. 验证

- [x] 6.1 运行 `mvn test`，确认 Java 单元测试通过。
- [x] 6.2 使用 Docker 后端容器运行相关 API E2E 模块。
- [x] 6.3 使用真实 target 环境验证至少一个可安装候选项的安装、日志记录和修复后依赖分析重跑。
- [x] 6.4 确认任务输入、日志、API 响应和 summary 不包含明文凭据、私钥、token 或服务器真实路径。
- [x] 6.5 运行 `openspec status --change add-dependency-auto-fix-runtime`，确认 artifacts 和 tasks 状态符合 apply/archive 要求。
