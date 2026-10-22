## 1. 环境刷新能力接入

- [x] 1.1 盘点 `SshRuntimeService.collectEnvironment`、`EnvironmentCollectHandler`、`EnvironmentRepository` 和依赖分析 worker 当前调用边界
- [x] 1.2 抽取或封装可由内部 worker 调用的环境刷新方法，避免 controller/service 互相调用
- [x] 1.3 为 source/x86 刷新构造安全采集输入，使用默认完整 collect scopes
- [x] 1.4 为 target/RISC-V 刷新构造安全采集输入，并确保采集包含 repository evidence
- [x] 1.5 确保刷新过程记录任务日志和 tool run 摘要，且不暴露凭据、私钥、token 或完整远端日志

## 2. 依赖分析 worker 流程

- [x] 2.1 在 `DependencyAnalysisHandler` 开始分析后、读取环境组件前刷新 source/x86 环境
- [x] 2.2 在 `DependencyAnalysisHandler` 开始分析后、读取环境组件前刷新 target/RISC-V 环境
- [x] 2.3 使用本次刷新返回的 source snapshot id 和 target snapshot id 读取组件
- [x] 2.4 移除默认使用旧 latest succeeded snapshot 的成功路径
- [x] 2.5 source 刷新失败时将依赖分析运行和任务标记为失败，并写入明确错误摘要
- [x] 2.6 target 刷新失败时将依赖分析运行和任务标记为失败，并写入明确错误摘要
- [x] 2.7 在任务进度中展示刷新 source、刷新 target、提取构建事实、生成制品等阶段

## 3. 制品和响应审计

- [x] 3.1 在依赖分析 JSON artifact 中记录 `environmentRefresh=true`
- [x] 3.2 在 JSON artifact 中记录本次使用的 `sourceSnapshotId`、`targetSnapshotId` 和采集时间
- [x] 3.3 在 HTML artifact 中展示或摘要标注本次环境刷新和快照时间
- [x] 3.4 在依赖分析运行 summary 或 warnings 中记录刷新失败、刷新耗时或快照来源
- [x] 3.5 确认响应和 artifact 不泄露 SSH 密码、私钥、token、服务器真实敏感路径或完整远端日志

## 4. 测试覆盖

- [x] 4.1 补充单元测试：依赖分析 handler 使用刷新返回的新 source/target snapshot
- [x] 4.2 补充单元测试：source 刷新失败时任务失败且不使用旧 snapshot
- [x] 4.3 补充单元测试：target 刷新失败时任务失败且不使用旧 snapshot
- [x] 4.4 补充单元测试：artifact 包含本次刷新快照 ID 和采集时间
- [x] 4.5 补充 E2E：旧 target snapshot 含已安装工具，实时环境删除后重新分析不再返回 `TARGET_INSTALLED`
- [ ] 4.6 补充 E2E：刷新失败时依赖分析失败且无成功态结果
- [ ] 4.7 确认 E2E 清理本 change 创建的项目、任务、快照、组件、日志和 runtime 临时文件

## 5. 验证

- [x] 5.1 运行相关单元测试
- [x] 5.2 运行 `mvn test`
- [x] 5.3 重新构建 backend Docker 容器并确认应用健康
- [x] 5.4 在 RISC-V 目标环境删除 `gcc` 后重新运行依赖分析真实流程，确认结果不再使用旧 snapshot
- [x] 5.5 重新跑 make、cmake、ninja、rpmbuild 四个真实项目并生成 HTML 汇总
- [ ] 5.6 运行依赖分析 E2E 模块
- [x] 5.7 运行 `openspec validate refresh-environment-before-dependency-analysis --strict`
- [x] 5.8 运行 `openspec validate --specs --strict`
