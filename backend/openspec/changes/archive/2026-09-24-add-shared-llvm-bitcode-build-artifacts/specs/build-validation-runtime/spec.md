## ADDED Requirements

### Requirement: x86 构建必须执行非阻断共享 BC 后处理
构建验证 worker SHALL 在当前 source/x86 构建成功后执行共享 LLVM BC 后处理，但真实构建退出码 MUST 是决定构建成功或失败的唯一依据。

#### Scenario: BC 成功且构建成功
- **WHEN** 用户构建命令退出码为 `0`
- **AND** BC artifact-set 状态为 `READY` 或 `PARTIAL`
- **THEN** 构建运行 SHALL 标记为 `SUCCEEDED`
- **AND** `build_facts.bitcode` SHALL 保存安全状态摘要和 stored artifact 引用

#### Scenario: BC 失败但构建仍成功
- **WHEN** 用户构建命令退出码为 `0`
- **AND** BC 生成、验证、回收或持久化失败
- **THEN** 构建运行 SHALL 标记为 `SUCCEEDED`
- **AND** BC 状态 SHALL 为 `FAILED`、`UNSUPPORTED` 或适用的非成功状态
- **AND** worker SHALL 记录 warning 而不是抛出改变构建结果的异常

#### Scenario: 构建失败不被 BC 状态覆盖
- **WHEN** 用户构建命令退出码非 `0`
- **THEN** 构建运行 SHALL 按现有构建失败语义结束
- **AND** BC 状态 MUST NOT 将构建改为成功

#### Scenario: 构建任务等待 BC 达到终态
- **WHEN** 用户构建命令已经成功且 worker 已进入 BC 后处理
- **THEN** 构建任务 SHALL 保持运行状态并更新进度和安全日志
- **AND** 构建任务只在 BC 达到 `READY`、`PARTIAL`、`FAILED` 或 `UNSUPPORTED` 后结束

### Requirement: 构建查询必须返回共享 BC 安全摘要
构建列表、详情和 latest 响应 SHALL 返回统一 `bitcode` 摘要，供前端识别 BC 是否可用和生成质量。

#### Scenario: 返回当前 BC 摘要
- **WHEN** 用户查询包含 BC 构建事实的构建记录
- **THEN** 响应 SHALL 返回 `available`、`status`、artifact-set ID、planned/succeeded/failed/skipped 数量、toolchain ID、schema/profile、reason code、warning count 和 generated at
- **AND** 响应 MUST NOT 返回 BC 内容、完整 manifest、远端绝对路径、服务器本机路径、bucket 或 object key

#### Scenario: latest 返回 BC 摘要
- **WHEN** 用户查询 source-only 或 validation 构建 latest
- **THEN** latest 的构建结果 SHALL 使用与详情接口相同的 `bitcode` 摘要结构

#### Scenario: 兼容没有 BC 字段的历史记录
- **WHEN** 历史构建记录不存在 `build_facts.bitcode`
- **THEN** 响应 SHALL 返回 `available=false`、`status=NOT_ATTEMPTED` 和 `reasonCode=LEGACY_RECORD`
- **AND** 后端 MUST NOT 为读取历史记录临时生成 BC
