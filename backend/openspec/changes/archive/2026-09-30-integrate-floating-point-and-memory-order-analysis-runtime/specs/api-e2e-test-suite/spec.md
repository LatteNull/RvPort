## ADDED Requirements

### Requirement: E2E 必须覆盖真实浮点分析流程
独立 API E2E 模块 SHALL 使用真实 C/C++ fixture、真实 x86 构建、真实 `compile_commands.json`、真实 Shared LLVM BC v2 和容器内浮点扫描器完成端到端验证。

#### Scenario: 正常浮点分析
- **WHEN** E2E 通过 API 准备源码与构建并创建浮点分析
- **THEN** Worker SHALL 运行真实工具并生成 schema v2 结果
- **AND** E2E SHALL 校验运行、Finding、详情、latest、readiness、日志、JSON/HTML、迁移输入和归档候选

#### Scenario: 浮点异常和边界流程
- **WHEN** 输入缺少 BC、profile 无法解析、manifest 损坏、工具返回 partial、结果为空或任务取消
- **THEN** E2E SHALL 校验受控状态、无半导入数据和旧输入保留语义

### Requirement: E2E 必须覆盖真实内存序统一分析流程
独立 API E2E 模块 SHALL 调用真实 `analyze-project`，不得用 fixture 结果替代工具执行，并 SHALL 验证退出码 0、2、3 和失败路径。

#### Scenario: 发现内存序风险
- **WHEN** 真实 fixture 产生 memory-order exit 3 和 risk Finding
- **THEN** 任务 SHALL 成功而不是重试
- **AND** E2E SHALL 校验 Finding evidenceChain、迁移输入、报告和归档

#### Scenario: 部分分析
- **WHEN** 开放 Scope、AST-only 或受控预算产生 exit 2
- **THEN** 运行 SHALL 以 PARTIAL 可查询
- **AND** E2E SHALL 校验 frontier、diagnostics 和已完成 Finding 被保留

#### Scenario: 统一报告失败
- **WHEN** 请求无效、所有 Scope 失败或 status/verdict/exit_code 冲突
- **THEN** 任务 SHALL 失败
- **AND** MUST NOT 写入成功态 Finding 或刷新旧迁移输入

### Requirement: E2E 必须覆盖权限和查询合同
专项分析 E2E SHALL 覆盖项目权限、分页、过滤、排序、Finding 详情、制品下载和非法参数。

#### Scenario: 多条 Finding 查询
- **WHEN** 真实或受控工具输入产生多风险、多路径和多规则 Finding
- **THEN** E2E SHALL 验证运行与 Finding 分页总数、过滤和稳定排序

#### Scenario: 跨项目访问
- **WHEN** 普通用户访问其他项目的运行、Finding 或制品
- **THEN** API SHALL 拒绝访问且不泄漏资源存在性

### Requirement: E2E 必须清理专项分析数据
专项分析 E2E 在成功或失败后 SHALL 清理本次创建的数据库记录、对象存储对象、工具 cache namespace 和 runtime 临时目录。

#### Scenario: 测试结束清理
- **WHEN** E2E 模块结束或中途失败
- **THEN** runner SHALL 按本次 run ID 清理任务、事件、日志、运行、Finding、迁移输入、归档候选和 stored artifacts
- **AND** MUST NOT 清理非本次测试创建的数据
