## 1. 数据模型和代码生成

- [x] 1.1 新增 Liquibase 迁移，使项目事件流支持节点/资源元数据，并允许项目上下文事件不绑定具体 task
- [x] 1.2 重新运行 jOOQ codegen，确保新增字段和 nullable task_id 在生成代码中可用
- [x] 1.3 更新 `TaskEventView`、repository mapper 和响应序列化，返回 `stageId`、`resource`、`taskId` 可空字段

## 2. 事件元数据接入

- [x] 2.1 扩展 `TaskCreateCommand` 和 `TaskRepository.create`，支持持久化任务级 `stageId` 与资源元数据
- [x] 2.2 为现有 task type 建立集中映射，避免各业务模块手写不一致的 stage/resource 字符串
- [x] 2.3 更新源码、环境、构建、依赖分析、知识库扫描、报告、自动化测试、归档等任务创建路径，写入对应节点和资源元数据
- [x] 2.4 保留 deprecated `SBOM_ANALYSIS`、`SOURCE_DEPLOY`、`RECHECK_DIFF` 等历史任务类型的事件兼容映射

## 3. 项目上下文变更事件

- [x] 3.1 增加 `project.context.changed` 事件类型和 TaskEventService 写入方法
- [x] 3.2 在源码上传激活、源码手动激活、Git 同步激活路径写入 active source 变更事件
- [x] 3.3 在项目运行环境选择更新路径写入 runtime environment 变更事件
- [x] 3.4 在环境配置影响当前运行环境版本时写入 environment config version 变更事件
- [x] 3.5 确保所有上下文事件在事务提交后才通过 SSE 发布

## 4. SSE API 行为

- [x] 4.1 更新 `TaskSseController` 和 `TaskSseBroker`，确保上下文事件和任务事件都按 projectId 推送
- [x] 4.2 保持无 cursor 时以当前项目最新事件 ID 作为 baseline，不默认补发旧事件
- [x] 4.3 保持 `afterEventId` 优先于 `Last-Event-ID`，并继续拒绝非法游标
- [x] 4.4 确认 SSE `data` 为 JSON，且不包含完整业务结果、完整日志、服务器真实路径或敏感信息

## 5. 测试和验证

- [x] 5.1 补充单元测试：任务事件元数据映射、上下文事件可无 taskId、非法 cursor、事务后发布
- [x] 5.2 补充 E2E：源码激活触发 `project.context.changed`
- [x] 5.3 补充 E2E：运行环境选择更新触发 `project.context.changed`
- [x] 5.4 补充 E2E：不同项目 SSE 不接收对方任务事件或上下文事件
- [x] 5.5 运行 Maven 单元测试和相关 E2E 模块，记录结果
