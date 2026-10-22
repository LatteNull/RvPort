## 1. 数据库和配置

- [x] 1.1 检查现有 `kb_scan_runs`、`findings` schema 与本 change 要求的字段、约束和索引是否一致
- [x] 1.2 如需要，新增 Liquibase 迁移补充 KB artifact metadata 表或等效报告元数据表
- [x] 1.3 如需要，新增或调整 `kb_scan_runs`、`findings` 的状态、过滤、排序相关索引
- [x] 1.4 增加 KB Scanner 配置项，包括 Python 命令、scanner 根路径、默认规则集路径、输出目录、默认超时、默认语言和目标架构
- [x] 1.5 更新 jOOQ 生成代码并确认生成产物进入源码目录

## 2. API 和领域模型

- [x] 2.1 新增 `RvPortTaskTypes.KB_SCAN`
- [x] 2.2 新增 KB scan request/response、finding response、list request 和 artifact summary DTO
- [x] 2.3 新增 `KbScanRepository`，支持创建运行、更新状态、写 summary、批量写 findings、查询列表、查询详情和查询 finding
- [x] 2.4 新增 `KbScanService`，实现项目权限校验、源码版本校验、默认 active source 选择、任务创建和扫描运行创建
- [x] 2.5 新增 `KbScanController`，实现 `POST /api/projects/{projectId}/kb-scans`
- [x] 2.6 实现 `GET /api/projects/{projectId}/kb-scans`，支持分页、过滤和排序白名单
- [x] 2.7 实现 `GET /api/kb-scans/{scanId}`
- [x] 2.8 实现 `GET /api/kb-scans/{scanId}/findings`，支持分页、过滤和排序白名单
- [x] 2.9 实现 `GET /api/findings/{findingId}`
- [x] 2.10 实现 `GET /api/findings/{findingId}/code-context`，返回上下文起止行、命中高亮行范围和逐行代码内容
- [x] 2.11 明确 `POST /api/kb-scans/{scanId}/findings:add-to-issues` 暂不实现或不暴露路由

## 3. Worker Runtime

- [x] 3.1 新增 `KbScanHandler` 并注册为 `KB_SCAN` task handler
- [x] 3.2 新增 `KbScanRuntimeService`，从任务输入读取 scan run、project、source revision 和扫描配置
- [x] 3.3 实现 scanner 输出目录准备，目录与 `projectId/taskId/scanRunId` 绑定
- [x] 3.4 实现受控本地进程调用 `tools/kb-scanner`，登记 local process 支持取消
- [x] 3.5 捕获 stdout/stderr，写入 `task_logs` 和 `task_log_events`
- [x] 3.6 解析 `scan-result.json`，校验 schemaVersion、tool、rulePack、summary 和 findings
- [x] 3.7 将 scanner findings 映射并批量写入 `findings`
- [x] 3.8 保存 `scan-result.json`、`scan-report.html` 和 `scan.log` 的 artifact metadata 或等效报告摘要
- [x] 3.9 写入 `tool_runs`，记录工具名、退出码、版本、耗时和安全摘要
- [x] 3.10 在成功、失败、取消和超时时同步更新 `kb_scan_runs.status`、`started_at`、`finished_at` 和 summary

## 4. 安全和边界

- [x] 4.1 确保所有 KB API 都执行项目访问守卫，越权返回安全错误
- [x] 4.2 确保 API 响应、任务事件、日志摘要和 artifact summary 不返回 `working_copy_path`、scanner 输出目录或服务器真实路径
- [x] 4.3 确保任务输入快照不保存完整 scanner 命令、源码工作副本路径、输出路径或完整 scanner input/output
- [x] 4.4 实现 scanner 输出、diagnostics、evidence 和日志的脱敏与大小控制
- [x] 4.5 确保取消运行中 `KB_SCAN` 时不会写入成功态 findings 或 artifact
- [x] 4.6 实现 finding 代码上下文路径 normalize、工作副本边界校验、固定上 20 行下 20 行范围和源码文件不可用的安全错误

## 5. 单元测试和轻量集成测试

- [x] 5.1 测试创建 KB scan 使用当前 active source revision 的正常流程
- [x] 5.2 测试创建 KB scan 使用指定 source revision 的正常流程
- [x] 5.3 测试无权限、source revision 不存在、跨项目 source revision、无 active source 和 working copy 缺失
- [x] 5.4 测试 KB scan 列表、详情、finding 列表和 finding 详情的分页过滤排序
- [x] 5.5 测试 finding 代码上下文接口返回固定上 20 行下 20 行范围、实际起止行、命中行高亮标记和逐行代码
- [x] 5.6 测试 finding 代码上下文的文件开头不足 20 行、文件结尾不足 20 行、源码文件缺失和路径逃逸
- [x] 5.7 测试 scanner 成功输出解析和 findings 批量入库
- [x] 5.8 测试空 findings、重复 fingerprint、非法 JSON、不兼容 schemaVersion 和 scanner 非零退出码
- [x] 5.9 测试任务进度、任务日志事件、tool run 和 artifact metadata 写入
- [x] 5.10 测试取消运行中 scanner 本地进程和 `kb_scan_runs` 取消状态
- [x] 5.11 测试路径、日志、evidence、代码上下文和错误摘要脱敏

## 6. E2E 和文档

- [x] 6.1 新增 `kb` E2E module/case，支持 `node e2e/runner.js run --module=kb`
- [x] 6.2 E2E 准备测试项目和源码版本，触发真实 `KB_SCAN` 并等待终态
- [x] 6.3 E2E 校验 `kb_scan_runs`、`findings`、artifact metadata、`tasks`、`task_events`、`task_log_events` 和 `tool_runs` 副作用
- [x] 6.4 E2E 覆盖 KB 查询 API、分页过滤排序和越权访问
- [x] 6.5 E2E 覆盖 finding 代码上下文接口，校验高亮行范围、上下文行数组和不返回服务器真实路径
- [x] 6.6 E2E 清理本次 run id 创建的数据库记录和本地测试输出
- [x] 6.7 更新 `backend/docs/API_DESIGN.md` 的 KB 扫描 API 和代码上下文接口细节
- [x] 6.8 更新 E2E 覆盖矩阵和运行文档

## 7. 验证

- [x] 7.1 运行 KB Scanner 自身测试
- [x] 7.2 运行 Maven 单元测试
- [x] 7.3 启动后端 worker 和基础设施，运行 KB E2E module
- [x] 7.4 使用一个真实源码版本执行一次 KB 扫描，记录 scan id、task id、finding 数量、summary 和查询 API 结果
- [x] 7.5 运行 `openspec validate add-kb-scan-runtime`
