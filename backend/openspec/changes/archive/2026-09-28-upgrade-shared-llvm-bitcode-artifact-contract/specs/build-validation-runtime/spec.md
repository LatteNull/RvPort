## MODIFIED Requirements

### Requirement: 构建查询必须返回共享 BC 安全摘要
构建列表、详情和 latest 响应 SHALL 返回统一 `bitcode` 安全摘要，供前端识别 BC 是否可用、生成质量、协议版本、可移植源码身份和编译上下文身份。

#### Scenario: 返回当前 v2 BC 摘要
- **WHEN** 用户查询包含 v2 BC 构建事实的构建记录
- **THEN** 响应 SHALL 返回 `available`、`status`、artifact-set ID、planned/succeeded/failed/skipped 数量、toolchain ID、schema/profile、source identity digest、compile context digest、reason code、warning count、generated at 和 `legacy=false`
- **AND** 响应 MUST NOT 返回 BC 内容、完整 manifest、完整编译命令、远端绝对路径、服务器本机路径、bucket 或 object key

#### Scenario: latest 返回 BC 摘要
- **WHEN** 用户查询 source-only 或 validation 构建 latest
- **THEN** latest 的构建结果 SHALL 使用与详情接口相同的 `bitcode` 摘要结构

#### Scenario: 兼容 v1 历史记录
- **WHEN** 历史构建事实包含 v1 BC 安全摘要
- **THEN** 响应 SHALL 返回已有状态、可用性、计数和协议版本
- **AND** SHALL 返回 `legacy=true`
- **AND** 不存在于 v1 的 v2 digest 字段 SHALL 返回 `null`，不得伪造

#### Scenario: 兼容没有 BC 字段的历史记录
- **WHEN** 历史构建记录不存在 `build_facts.bitcode`
- **THEN** 响应 SHALL 返回 `available=false`、`status=NOT_ATTEMPTED`、`reasonCode=LEGACY_RECORD` 和 `legacy=true`
- **AND** 后端 MUST NOT 为读取历史记录临时生成 BC
