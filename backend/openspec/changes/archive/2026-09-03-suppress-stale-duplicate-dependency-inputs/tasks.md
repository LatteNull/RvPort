## 1. 数据现状确认

- [x] 1.1 复查 `dependency_analysis_result_items` 和 `migration_input_refs` 中历史重复 `DEPENDENCY_RESULT` 数据，确认重复 key 与保留优先级。
- [x] 1.2 确认最新成功依赖分析 run 的查询逻辑能按 `project_id + source_revision_id` 稳定返回唯一 run。

## 2. 当前输入池收敛

- [x] 2.1 在迁移输入读取或清理路径中实现 `DEPENDENCY_RESULT` 当前有效 run 过滤。
- [x] 2.2 为工具类依赖实现有限语义归一化，合并 `build:gcc`、`compile-db:gcc`、`execve-summary:gcc`、`execve:gcc` 这类同名工具重复项。
- [x] 2.3 确保不同库依赖如 `libgcc.so` 和 `libgcc_s.so` 不被误合并。
- [x] 2.4 保持依赖分析成功重跑后的 `deleteBySourceType + insert current run refs` 行为，不继承旧 `EXCLUDED` 或 `CONFIRMED` 状态。

## 3. 报告读取边界

- [x] 3.1 更新评估报告 readiness，使 confirmed 统计排除旧 run 的过期依赖输入。
- [x] 3.2 更新评估报告输入预览，使默认结果只展示当前有效依赖输入。
- [x] 3.3 更新报告生成读取逻辑，防止旧 `CONFIRMED` 依赖输入进入新报告。
- [x] 3.4 确认历史报告详情和下载仍使用不可变 `report_inputs` 快照。

## 4. 历史数据清理

- [x] 4.1 新增 Liquibase 清理脚本或受控维护逻辑，收敛已有当前输入池中的重复 `DEPENDENCY_RESULT` 引用。
- [x] 4.2 清理逻辑必须只作用于 `migration_input_refs`，不得修改 `report_inputs` 或历史 dependency result items。
- [x] 4.3 对清理 SQL 或维护逻辑补充可重复执行保护，避免重复运行造成错误。

## 5. 测试

- [x] 5.1 补充单元测试：依赖分析成功重跑后旧依赖输入被替换为本次 run 的引用。
- [x] 5.2 补充单元测试：新依赖分析失败或取消时保留当前输入池。
- [x] 5.3 补充 edge case 测试：旧 confirmed `gcc` 与新 candidate `gcc` 同时存在时，报告不消费旧 confirmed。
- [x] 5.4 补充 edge case 测试：多来源 `gcc` 合并，但 `libgcc.so` 和 `libgcc_s.so` 保持独立。
- [x] 5.5 补充 E2E fixture：构造历史重复依赖输入，验证 readiness、输入预览和报告生成结果。

## 6. 验证

- [x] 6.1 运行 `mvn test`。
- [x] 6.2 运行相关 E2E 模块。
- [x] 6.3 运行 `openspec validate suppress-stale-duplicate-dependency-inputs --strict`。
- [x] 6.4 如涉及容器运行路径，重建后端容器并验证接口返回不再出现旧重复 `gcc`。
