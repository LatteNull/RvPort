## 1. Schema 和代码生成

- [x] 1.1 增加 Liquibase 变更，为 `build_runs` 补充 `source_deploy_run_id` 外键、脚本摘要相关字段和必要索引。
- [x] 1.2 运行 Liquibase 更新本地 PostgreSQL schema，确认新字段和索引创建成功。
- [x] 1.3 运行 jOOQ 代码生成脚本，将生成代码更新到 `src/generated/java`。
- [x] 1.4 检查 `DATABASE_DESIGN.md` 中 `build_runs` 字段说明与实际 schema 保持一致。

## 2. 构建验证 API

- [x] 2.1 新增构建验证 DTO，定义创建请求、列表查询参数、列表项、详情和取消响应。
- [x] 2.2 实现 `BuildValidationRepository`，支持创建、详情查询、分页查询、状态更新和日志引用写回。
- [x] 2.3 实现 `BuildValidationService`，校验项目权限、源码部署归属、源码版本一致性、部署状态和环境启用状态。
- [x] 2.4 实现 `POST /api/projects/{projectId}/builds`，根据 `sourceDeploymentIds` 为每个部署创建独立构建任务。
- [x] 2.5 实现 `GET /api/projects/{projectId}/builds`，支持分页、排序和按源码版本、环境、状态、时间范围过滤。
- [x] 2.6 实现 `GET /api/builds/{buildId}` 和 `POST /api/builds/{buildId}/cancel`，并对详情和取消执行项目访问守卫。
- [x] 2.7 更新 `API_DESIGN.md` 中构建验证接口说明，将输入调整为 `sourceDeploymentIds` 和构建脚本。

## 3. 构建脚本存储

- [x] 3.1 复用或扩展 `task_script_payloads` 写入构建脚本密文，确保完整脚本不进入 `tasks.input_snapshot`。
- [x] 3.2 在 `build_runs.command` 保存脱敏命令摘要或脚本哈希，不保存明文密码、token 或私钥。
- [x] 3.3 增加构建脚本输入校验，覆盖空脚本、纯空白脚本、超长脚本和重复部署 ID。

## 4. Worker Runtime

- [x] 4.1 新增 `RvPortTaskTypes.BUILD_VALIDATION`。
- [x] 4.2 实现 `BuildValidationHandler`，注册到统一任务 worker 分发机制。
- [x] 4.3 Worker 读取 `build_runs`、`source_deploy_runs`、环境和脚本 payload，并在执行前重新校验部署状态为 `SUCCEEDED`。
- [x] 4.4 Worker 通过 SSH 在远端源码部署目录创建临时脚本、执行构建命令，并在完成、失败、超时或取消后尝试删除远端临时脚本。
- [x] 4.5 Worker 将 stdout/stderr 写入任务日志体系，并追加可用于项目级 SSE 的任务进度和终态事件。
- [x] 4.6 Worker 根据退出码和异常类型写回 `build_runs.status`、`exit_code`、`failure_category`、日志引用、`started_at` 和 `finished_at`。
- [x] 4.7 构建取消复用运行中任务取消机制，确保取消后 `build_runs.status` 最终与任务状态一致。

## 5. 单元测试

- [x] 5.1 为构建验证 service 增加正常流程测试：单环境创建、双环境创建、脚本加密保存和队列投递。
- [x] 5.2 为构建验证 service 增加异常流程测试：无权限、跨项目部署、失败部署、环境禁用、源码版本不一致和空脚本。
- [x] 5.3 为构建验证 service 增加 edge case 测试：重复部署 ID、非法分页排序、超长脚本、取消已完成构建。
- [x] 5.4 为构建验证 worker 增加正常流程测试：远端命令退出码为 0 时写回成功和日志。
- [x] 5.5 为构建验证 worker 增加异常流程测试：SSH 失败、远端工作目录不存在、非 0 退出码、超时和取消。
- [x] 5.6 为 controller 增加参数校验和权限隔离测试。

## 6. E2E 和真实联通验证

- [x] 6.1 新增可单独运行的构建验证 E2E 模块。
- [x] 6.2 E2E 正常流程通过 API 创建项目、源码版本、x86/RISC-V 环境、源码部署和构建验证，并校验任务、构建运行、日志和 SSE 事件。
- [x] 6.3 E2E 异常流程覆盖失败源码部署、跨项目部署、普通用户越权和非 0 退出码脚本。
- [x] 6.4 E2E edge case 覆盖空脚本、重复 `sourceDeploymentIds`、非法分页排序和取消行为。
- [x] 6.5 更新 E2E 清理脚本，删除测试项目相关的构建运行、脚本 payload、日志、任务、源码部署和运行目录。
- [x] 6.6 使用真实可访问的 x86 和 RISC-V 环境跑一次双环境源码部署和构建验证，记录实际 API 请求、任务 ID、构建 ID、退出码、日志摘要和远端目录。

## 7. 验证

- [x] 7.1 运行 `mvn test`，确认单元测试通过。
- [x] 7.2 运行构建验证 E2E 模块，确认模块化 E2E 可独立执行。
- [x] 7.3 启动后端和 worker，确认构建任务能从 RabbitMQ 消费并写回终态。
- [x] 7.4 检查 OpenSpec 变更状态，确保 proposal、design、specs 和 tasks 均完成。
