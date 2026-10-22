## ADDED Requirements

### Requirement: 构建验证必须支持前置 source-only 构建
构建验证运行时 SHALL 在保持默认双环境构建行为不变的前提下，支持用于依赖分析前置的 source/x86 单环境构建范围。

#### Scenario: 默认双环境构建
- **WHEN** 用户创建构建验证且未提交 `buildScope`
- **THEN** 后端 SHALL 使用 `BOTH` 作为默认构建范围
- **AND** 后端 SHALL 继续为 source/x86 和 target/RISC-V 创建构建运行
- **AND** 该行为 SHALL 与现有正式构建验证节点兼容

#### Scenario: 创建 source-only 构建
- **WHEN** 用户创建构建验证并提交 `buildScope=SOURCE_ONLY`
- **THEN** 后端 SHALL 只为项目当前 source/x86 环境创建构建运行
- **AND** 后端 SHALL 自动执行或复用 source 环境源码部署
- **AND** 后端 MUST NOT 为 target/RISC-V 环境创建构建运行

#### Scenario: source-only 构建作为依赖分析前置
- **WHEN** source-only 构建成功
- **THEN** 构建运行 SHALL 保存源码版本、source 环境、环境配置版本、构建日志引用、构建脚本摘要和产物事实摘要
- **AND** 这些事实 SHALL 能被依赖分析任务引用

#### Scenario: 拒绝不支持的构建范围
- **WHEN** 构建创建请求提交 MVP 不支持的 `buildScope`
- **THEN** 后端 SHALL 返回统一参数校验错误
- **AND** 后端 MUST NOT 创建构建运行、任务或队列消息

#### Scenario: 正式构建验证仍使用双环境
- **WHEN** 前端进入正式构建验证节点
- **THEN** 前端 SHALL 默认调用 `buildScope=BOTH` 或省略该参数
- **AND** 后端 SHALL 同时验证 source/x86 和 target/RISC-V 构建结果
