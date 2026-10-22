## ADDED Requirements

### Requirement: API E2E 必须覆盖依赖分析前环境刷新
API E2E 测试套件 SHALL 覆盖依赖分析默认刷新环境快照的正常流程、异常流程和 stale snapshot edge case。

#### Scenario: 正常流程验证刷新快照
- **WHEN** E2E 运行依赖分析模块
- **THEN** 测试 SHALL 创建或复用 source/x86 和 target/RISC-V 环境
- **AND** 测试 SHALL 调用依赖分析创建 API
- **AND** 测试 SHALL 验证依赖分析任务执行期间产生新的 source 和 target 环境快照
- **AND** 测试 SHALL 验证依赖分析 artifact 使用的是本次新快照 ID

#### Scenario: stale snapshot 不再被使用
- **WHEN** E2E 准备一个旧 target snapshot，其中某工具被记录为已安装
- **AND** E2E 改变实时 target 环境使该工具不再安装但软件源仍可提供
- **THEN** 重新运行依赖分析后，测试 SHALL 验证该工具不再返回 `TARGET_INSTALLED`
- **AND** 测试 SHALL 验证结果来自本次刷新后的 target snapshot

#### Scenario: 采集失败导致分析失败
- **WHEN** E2E 使 source 或 target 环境采集失败
- **THEN** 依赖分析任务 SHALL 进入 `FAILED`
- **AND** E2E SHALL 验证错误摘要说明是 source 或 target 环境刷新失败
- **AND** E2E SHALL 验证后端没有使用旧 snapshot 生成成功态依赖分析结果

#### Scenario: 敏感信息边界
- **WHEN** E2E 验证环境刷新日志、依赖分析结果和 artifact
- **THEN** 响应和制品 MUST NOT 暴露 SSH 密码、私钥、token、服务器真实敏感路径或完整远端日志
