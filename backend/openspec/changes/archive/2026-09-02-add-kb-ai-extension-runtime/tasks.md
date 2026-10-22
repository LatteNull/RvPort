## 1. 数据库与生成代码

- [x] 1.1 新增 Liquibase 迁移，创建 `kb_ai_extension_runs` 表，包含项目、源码版本、KB scan、task、模型 profile、agent runtime、状态、summary、artifact、开始结束时间和审计字段
- [x] 1.2 新增 Liquibase 迁移，创建 `kb_ai_extension_results` 表，按 finding 粒度保存 AI summary、suggestion、confidence、action type、raw payload 和时间字段
- [x] 1.3 扩展模型阶段绑定允许 `KB_AI_EXTENSION`，扩展 artifact owner 允许 KB AI 扩展产物
- [x] 1.4 运行 Liquibase 和 jOOQ 生成脚本，提交生成后的 jOOQ 源码

## 2. 模型阶段与 Agent Runtime

- [x] 2.1 扩展 `ModelProfileStage`，新增 `KB_AI_EXTENSION`
- [x] 2.2 扩展阶段绑定查询和保存逻辑，使管理员可配置 `KB_AI_EXTENSION` 的模型 profile 与 agent runtime
- [x] 2.3 扩展 agent runtime 受控阶段白名单，允许 KB AI 扩展通过统一 adapter 执行
- [x] 2.4 扩展 agent probe 分项，增加 KB AI 扩展输出 schema 的最小兼容性测试

## 3. KB AI 扩展运行时

- [x] 3.1 新增 `KB_AI_EXTENSION` task type、task input、handler、repository、service 和状态枚举
- [x] 3.2 实现 readiness 检查，覆盖 KB scan 成功状态、finding 数量、阶段绑定、模型 profile 和 agent runtime 可用性
- [x] 3.3 实现 agent workspace 准备逻辑，导出 `manifest.json` 和 `findings-*.jsonl`
- [x] 3.4 将当前 source revision 源码提供给 agent 读取，并避免 agent 修改真实源码工作副本
- [x] 3.5 编写 KB AI 扩展 prompt，明确允许信息不足时读取源码，禁止修改源码，要求输出结构化 JSONL 和 summary
- [x] 3.6 调用统一 agent adapter 执行任务，保存 stdout、stderr、`mergedOutput`、退出码和超时状态
- [x] 3.7 实现输出解析和逐条校验，允许合法可追溯结果部分入库，并记录缺失、重复、未知和非法条目诊断
- [x] 3.8 将 AI 扩展结果逐条入库，并保存输入、输出、执行摘要 artifact
- [x] 3.9 在失败、超时、取消、输出非法和部分成功时正确更新 task 与 run 状态，并写入脱敏日志

## 4. API 与响应

- [x] 4.1 新增 `POST /api/projects/{projectId}/kb-scans/{scanId}/ai-extensions` 启动接口
- [x] 4.2 新增 `GET /api/projects/{projectId}/kb-scans/{scanId}/ai-extension-readiness` 查询接口
- [x] 4.3 新增项目维度 AI 扩展运行记录列表接口，支持分页、过滤和排序
- [x] 4.4 新增 AI 扩展运行详情和 artifact 下载接口
- [x] 4.5 扩展 `GET /api/kb-scans/{scanId}/findings`，直接返回每条 finding 的最新成功 `aiExtension`
- [x] 4.6 扩展 `GET /api/findings/{findingId}`，直接返回该 finding 的最新成功 `aiExtension`
- [x] 4.7 确保所有接口执行项目权限校验，并且不返回 API key、完整 prompt、agent 命令或服务器真实路径

## 5. 报告与归档

- [x] 5.1 扩展评估报告输入构建逻辑，在已确认 KB finding 存在 AI 扩展建议时附带 AI summary 和 AI suggestion
- [x] 5.2 确保 AI 扩展不改变 migration input reference 的确认状态
- [x] 5.3 按全局约束登记可归档的 AI 扩展输入、输出和执行摘要 artifact，作为后续报告和审计的必要输入之一

## 6. 测试与验证

- [x] 6.1 增加单元测试，覆盖正常流程、异常流程和 edge case
- [x] 6.2 增加 repository/service 测试，验证 AI 结果逐条入库、最新成功结果选择、旧源码版本和旧 KB scan 不串用
- [x] 6.3 增加 agent runtime 测试，验证输入文件生成、源码读取提示、输出 JSONL 校验、重复/缺失/未知 finding ID 诊断和部分结果入库
- [x] 6.4 增加 API 测试，验证 readiness、启动、运行详情、artifact 下载、finding 列表和 finding 详情响应
- [x] 6.5 增加 API E2E 模块，使用测试 agent fixture 跑通 KB scan 后的 AI 扩展扫描，并验证 finding 响应直接包含 `aiExtension`
- [x] 6.6 运行 Maven 测试、OpenSpec validate、后端容器构建和必要的 E2E 验证
