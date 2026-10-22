## 1. 数据库与代码生成

- [x] 1.1 新增 Liquibase changeset，将 `sbom_runs.source_snapshot_id` 和 `sbom_runs.target_snapshot_id` 调整为可空并保留外键与索引
- [x] 1.2 运行 Liquibase 校验迁移可以应用到当前 PostgreSQL
- [x] 1.3 重新运行 jOOQ 生成脚本，确保 `sbom_runs` nullable 字段映射正确

## 2. SBOM 创建 API

- [x] 2.1 调整 `SbomAnalysisRequest`，只接收 `sourceEnvironmentId` 和 `targetEnvironmentId`，移除或拒绝 snapshot 与分析选项输入
- [x] 2.2 调整 `SbomService.create`，只校验项目、源环境和目标环境访问权限
- [x] 2.3 创建 `SBOM_ANALYSIS` 任务时只接收环境 ID，并由后端写入默认仓库策略和默认全量采集范围
- [x] 2.4 创建 `sbom_runs` 时允许快照 ID 为空，并记录初始状态
- [x] 2.5 更新 API 文档中 SBOM 创建请求、响应和错误说明

## 3. 环境采集复用接口

- [x] 3.1 从 `SshRuntimeService.collectEnvironment` 抽取返回快照 ID 的内部采集方法
- [x] 3.2 保持独立 `ENV_COLLECT` handler 原有行为不变
- [x] 3.3 确认内部采集方法复用脱敏、组件写入、仓库证据、ELF metadata、provider 证据和 unmanaged 工具证据逻辑
- [x] 3.4 确认采集日志和 tool run 关联到当前执行任务

## 4. SBOM Worker 流程

- [x] 4.1 调整 `SbomAnalysisRuntimeService.analyze`，先执行源环境采集并回填 `source_snapshot_id`
- [x] 4.2 调整 `SbomAnalysisRuntimeService.analyze`，再执行目标环境采集并回填 `target_snapshot_id`
- [x] 4.3 仅基于本轮回填的快照构造 analyzer 输入
- [x] 4.4 为 `SOURCE_COLLECT`、`TARGET_COLLECT`、`ANALYZE` 和 `IMPORT_RESULT` 阶段写入进度、日志和失败摘要
- [x] 4.5 确认取消任务时能中止当前 SSH 命令或本地 analyzer 进程，并将 `sbom_runs` 标记为 `CANCELLED`

## 5. 查询接口兼容

- [x] 5.1 调整 SBOM 列表和详情响应，支持快照 ID 为空的运行记录
- [x] 5.2 调整 `collection-detail`，支持采集中、部分快照存在和采集失败状态
- [x] 5.3 确保所有 SBOM 查询接口继续执行项目访问权限校验并不泄漏无权资源

## 6. 测试

- [x] 6.1 补充 Java 单元测试覆盖 SBOM 创建不需要 snapshot ID
- [x] 6.2 补充 Java 单元测试覆盖源环境采集成功、目标环境采集成功和快照回填
- [x] 6.3 补充异常流程测试覆盖源采集失败、目标采集失败、analyzer 失败和结果导入失败
- [x] 6.4 补充 edge case 测试覆盖采集中查询 `collection-detail`、取消时部分快照已生成、空组件清单和日志脱敏
- [x] 6.5 更新 API E2E SBOM 模块，验证创建 SBOM 分析任务后由后端自动采集并完成分析
- [x] 6.6 运行 Maven 测试、API E2E 相关模块和必要的真实联通验证，记录结果
