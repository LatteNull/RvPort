## 1. 数据模型和迁移

- [x] 1.1 盘点现有 `test_runs`、`task_logs`、`task_log_events` 和 `stored_artifacts` 字段，确认自动化测试输出和报告产物回收缺口
- [x] 1.2 如缺少输出摘要、报告 artifact 引用或必要索引，新增 Liquibase changelog 兼容扩展 `test_runs`
- [x] 1.3 刷新 jOOQ 生成代码，并确认生成源码提交到 `src/generated/java`
- [x] 1.4 确认数据库设计文档同步描述测试输出、报告 artifact、日志引用、索引和敏感信息约束

## 2. API 和服务

- [x] 2.1 新增自动化测试请求、响应、可选 `environmentVariables`、可选 `reportTargets` 数组和列表过滤排序 DTO
- [x] 2.2 实现 `POST /api/projects/{projectId}/tests` 创建 `AUTOMATED_TEST` 任务
- [x] 2.3 实现 `GET /api/projects/{projectId}/tests` 分页查询测试运行列表
- [x] 2.4 实现 `GET /api/tests/{testRunId}` 查询测试运行详情
- [x] 2.5 实现 `POST /api/tests/{testRunId}/cancel` 复用任务取消机制
- [x] 2.6 对项目、源码版本、执行环境、可选构建运行执行归属和状态校验
- [x] 2.7 校验 `reportTargets` 数组中每个条目的 `type` 和 `path`，支持 `FILE` 与 `DIRECTORY`，拒绝绝对路径、`..` 越界、空值和不允许的目录扫描
- [x] 2.8 为构建和测试请求新增 `environmentVariables` 校验，限制变量名格式和值长度
- [x] 2.9 确保所有响应不暴露服务器真实路径、远端敏感绝对路径、环境变量明文值、明文凭据或完整任务输入快照

## 3. 任务运行时

- [x] 3.1 在 `RvPortTaskTypes` 中新增 `AUTOMATED_TEST`
- [x] 3.2 实现自动化测试 task input、可选 `environmentVariables`、可选 `reportTargets` 数组解析和脱敏摘要
- [x] 3.3 实现 `AUTOMATED_TEST` handler，调用 SSH runtime 执行远程测试命令或临时脚本
- [x] 3.4 捕获 stdout/stderr，写入任务日志事件和完整日志文件元数据
- [x] 3.5 在测试命令结束后按 `reportTargets` 从远端回收 `FILE` 报告文件和 `DIRECTORY` 报告输出目录中的受控文件，并保存为受控制品
- [x] 3.6 保存 `test_runs` 退出码、状态、耗时、stdout/stderr 日志引用、报告 artifact 摘要和输出摘要
- [x] 3.7 支持报告数量、单文件大小、总大小和无匹配文件的受控处理
- [x] 3.8 支持超时处理，超时后尝试终止远程命令并写入受控终态
- [x] 3.9 支持取消处理，取消后保留已产生的输出、日志和已回收报告事实

## 4. 文档

- [x] 4.1 更新 `docs/API_DESIGN.md` 中构建/测试 `environmentVariables`、自动化测试 `reportTargets`、响应、过滤排序和错误边界
- [x] 4.2 更新 `docs/DATABASE_DESIGN.md` 中 `test_runs` 字段、报告 artifact、索引和日志回收说明
- [x] 4.3 更新 `docs/api-e2e-coverage.md`，补充自动化测试模块覆盖范围
- [x] 4.4 明确本 change 不实现日志比较、测试结果对比、用例级解析和失败用例重跑

## 5. 测试

- [x] 5.1 补充正常流程单元测试：创建测试任务、远程执行成功、环境变量注入、退出码保存、日志引用保存、报告文件和报告目录回收、SSE 事件写入
- [x] 5.2 补充异常流程单元测试：无权限、资源不属于项目、构建运行无效、SSH 执行失败、日志保存失败、非法报告目标、非法环境变量名
- [x] 5.3 补充 edge case 单元测试：非 0 退出码、空日志、大日志摘要截断、stdout 很少但报告存在、报告目录无匹配、报告数量或大小超限、环境变量敏感值脱敏、超时、重复取消、敏感信息脱敏
- [x] 5.4 补充 E2E 模块用例，覆盖真实后端下创建测试任务、等待完成、查询详情、下载或查询报告 artifact 摘要和清理测试数据
- [x] 5.5 运行相关 Maven 单元测试和可用 E2E 模块测试

## 6. 验证和收尾

- [x] 6.1 运行 `openspec validate add-automated-test-runtime --strict`
- [x] 6.2 确认本 change 未实现 Codex 日志比较、x86/RISC-V 差异分析、结构化测试报告解析或用例级 API
