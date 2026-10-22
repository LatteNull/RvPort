## ADDED Requirements

### Requirement: 源码部署记录必须可作为多环境构建输入
源码部署运行时 SHALL 为构建验证提供明确、可审计的远端源码输入，并 SHALL 支持同一源码版本在多个环境分别被构建。

#### Scenario: 构建验证引用源码部署记录
- **WHEN** 构建验证任务引用 `source_deploy_runs.id`
- **THEN** 后端 SHALL 使用该记录的 `remote_path` 作为远端构建目录
- **AND** 后端 SHALL 校验该源码部署记录状态为 `SUCCEEDED`
- **AND** 后端 MUST NOT 接受客户端提交的任意远端构建目录覆盖该值

#### Scenario: 同一源码版本多环境构建
- **WHEN** 同一源码版本已经部署到 x86 和 RISC-V 环境
- **THEN** 构建验证 SHALL 能分别引用两条源码部署记录创建构建运行
- **AND** 每条构建运行 SHALL 保留对应环境和源码部署记录的关联
