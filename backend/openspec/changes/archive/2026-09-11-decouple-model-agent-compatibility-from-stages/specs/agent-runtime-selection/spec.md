## MODIFIED Requirements

### Requirement: Agent Runtime Probe 必须支持按模型 Profile 批量执行
后端 agent runtime 选择能力 SHALL 支持模型 profile 针对多个指定 agent runtime 执行阶段无关的通用兼容性 probe，并 SHALL 使用统一 adapter 返回一致的分项结果。

#### Scenario: 按 Runtime 列表执行 Probe
- **WHEN** 模型 profile agent probe run 包含多个 agent runtime
- **THEN** 后端 SHALL 对每个 runtime 使用对应 agent adapter 执行兼容性 probe
- **AND** 每个 runtime SHALL 生成独立的 probe 状态、通用分项结果、耗时和脱敏消息
- **AND** 单个 runtime 失败 SHALL NOT 阻止其他 runtime 执行

#### Scenario: Runtime 不可用
- **WHEN** 请求中的 agent runtime 不存在、未启用或没有已注册 adapter
- **THEN** 后端 SHALL 拒绝创建 probe run 或将对应 runtime 标记为受控失败
- **AND** 响应 MUST NOT 泄漏完整命令、内部路径或 provider secret

#### Scenario: Probe 输出统一
- **WHEN** 任意 agent runtime 执行 profile 兼容性 probe
- **THEN** 后端 SHALL 使用统一结果结构保存 Agent 模型响应、workspace 读取、workspace 写入和基础 JSON 解析分项结果
- **AND** 聚合兼容状态 SHALL 只由这些通用分项计算
- **AND** probe MUST NOT 执行或返回 `TEST_COMPARE_SCHEMA`、`KB_AI_EXTENSION_SCHEMA` 或其他业务阶段专属检查

#### Scenario: Workspace 写入闭环
- **WHEN** Agent Runtime 执行通用 workspace 写入检查
- **THEN** Agent SHALL 根据中性输入文件写出受控 JSON 结果文件
- **AND** 后端 SHALL 校验文件存在、JSON 合法且 marker 与预期一致
- **AND** 临时 workspace SHALL 在 probe 完成、失败或超时后按现有安全策略清理

#### Scenario: 容器内 Agent CLI 完整安装
- **WHEN** 构建后端运行镜像
- **THEN** 镜像 SHALL 安装与 Codex CLI 版本匹配的平台二进制依赖
- **AND** 构建过程 SHALL 实际执行各内置 Agent CLI 的版本命令
- **AND** backend 与 backend-worker SHALL 使用包含相同 Agent CLI 的同一后端镜像
