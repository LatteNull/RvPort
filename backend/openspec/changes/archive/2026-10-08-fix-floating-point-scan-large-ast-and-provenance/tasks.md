## 1. 固化失败样本与协议边界

- [x] 1.1 为 `demo-test1` 的三类翻译单元建立脱敏回归 fixture，记录大 AST、标准库密集 facts、直接 evidence 和当前 v2 Schema 边界，不提交真实服务器路径或运行制品
- [x] 1.2 增加失败链路测试，复现 AST 输出超过 16 MiB 后被截断、误报 `frontend_invalid_json`、派生 `source_fact_bundle_missing` 以及 provenance 超过 128 导致 `internal_error` 的现状
- [x] 1.3 明确并测试稳定诊断 code、阶段因果优先级、`retryable` 分类及中英文诊断字段

## 2. 修复 Clang AST 大输出处理

- [x] 2.1 在 `tools/floating-point-precision-scanner` 中实现任务级文件承接的 Clang stdout 运行路径，保留有界 stderr、退出码、超时和取消语义
- [x] 2.2 在子进程执行期间执行 `max_frontend_output_bytes` 硬限制，超限时终止进程并返回 `frontend_output_limit_exceeded`，禁止截断后继续 JSON 解析
- [x] 2.3 调整 frontend 状态判定顺序，分别处理进程不可用、非零退出、超时、取消、输出超限、完整 JSON 损坏和非法顶层结构
- [x] 2.4 确保每个翻译单元及任务结束时清理 AST 临时文件，并覆盖成功、失败、超时和取消边界
- [x] 2.5 更新后端浮点请求 adapter 和配置，为 frontend 输出预算提供可配置默认值与 worker 硬上限，避免无界提高内存和磁盘使用

## 3. 收敛源码事实与结果 provenance

- [x] 3.1 在 fact 建模入口按 `project_root` 过滤标准库和系统头文件节点，只保留项目源码、项目头文件及必要的有界 external symbol/type 摘要
- [x] 3.2 修改 Finding、occurrence 和 evidence chain 的 provenance 构建逻辑，仅引用规则 assessment 的直接 evidence，并执行稳定去重和排序
- [x] 3.3 对合法直接证据超过 Schema 上限的情况实现确定性聚合或分组及 `provenance_budget_exceeded` frontier，禁止静默丢失后声明 complete
- [x] 3.4 在原子发布前使用随包 v2 Schema 和引用闭包验证最终结果，保证生成器不会发布自身不合法的 provenance
- [x] 3.5 增加结果确定性测试，验证相同输入重复执行时 Finding ID、直接证据集合、聚合摘要和 semantic digest 稳定

## 4. 完善后端失败审计与重试分类

- [x] 4.1 调整专项分析运行时，在退出码/状态验收前读取、限制并结构化脱敏扫描结果；对安全的失败结果 JSON 创建不可变制品并关联失败运行
- [x] 4.2 实现诊断因果优先级选择器，使 frontend/input/budget/resource 根因优先于 source/evidence 派生错误，并在任务错误和运行摘要中返回主 code、双语消息和诊断总数
- [x] 4.3 对无法安全保存的失败结果拒绝上传原文，只保存脱敏最小摘要，同时保证任务、运行和事件状态一致
- [x] 4.4 将扫描器 `retryable` 分类映射到任务异常策略，使输入、协议、Schema 和预算错误直接失败，仅对明确可重试的瞬时错误沿用既有重试上限
- [x] 4.5 校验失败结果制品的项目权限、路径脱敏和下载行为，不新增绕过既有 stored artifact 权限边界的接口

## 5. 单元测试与覆盖率门禁

- [x] 5.1 使用 mock `ProcessRunner` 和临时目录补齐扫描器正常流程测试：小型 AST、大于 16 MiB 但低于预算的完整 AST、项目源码 facts 和合法直接 provenance
- [x] 5.2 补齐扫描器异常流程测试：进程不可用、非零退出、超时、取消、硬预算超限、完整 JSON 损坏、Schema 校验失败和清理失败
- [x] 5.3 补齐扫描器 edge case 测试：标准库密集 AST、无位置节点、重复 evidence、恰好 128 条 provenance、超过 128 条证据及多 occurrence 聚合
- [x] 5.4 使用 mock 进程、对象存储、repository 和任务上下文补齐后端失败制品、诊断优先级、路径脱敏、不可重试及可重试流程测试，不连接真实外部服务
- [x] 5.5 运行工具与后端完整单元测试和覆盖率统计，确保项目整体及受影响模块行覆盖率和可用分支覆盖率均至少为 90%，并记录命令、统计范围和报告位置
  - 后端：`mvn verify`，1685 个测试通过、2 个显式跳过；整体行覆盖率 96.79%、分支覆盖率 91.02%，`analysis` 及全部包级门禁均不低于 90%；报告位于 `target/site/jacoco/index.html`
  - 浮点扫描器：`ruff check src tests`、`mypy src`、`coverage run --branch -m pytest`、`coverage html`、`coverage report`；230 个测试通过、15 个因 Windows 本机缺少锁定 Clang/LLVM 21.1.8 而显式跳过；整体覆盖率 96%，报告位于 `tools/floating-point-precision-scanner/htmlcov/index.html`

## 6. 容器与真实回归验证

- [x] 6.1 重建 backend/worker 镜像并验证锁定 Clang、浮点扫描器、IR worker 和新增配置均能通过工具健康检查
- [x] 6.2 使用 `demo-test1` 当前源码版本、真实 compile database 和共享 BC 制品重新运行浮点精度扫描，确认三个翻译单元均不再因 AST 截断失败
- [x] 6.3 验证真实结果满足 v2 Schema、provenance 有界、失败或成功制品可审计、任务不发生不可重试错误的重复投递，并记录 JSON/HTML 与任务事件结果
- [x] 6.4 检查 OpenSpec 任务、规格和实现一致性；全部单元测试、容器健康检查、`demo-test1` 真实回归、v2 Schema 校验和 90% 覆盖率门禁均已通过，可归档
