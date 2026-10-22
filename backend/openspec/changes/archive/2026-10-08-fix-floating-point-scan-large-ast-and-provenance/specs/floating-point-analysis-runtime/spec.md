## ADDED Requirements

### Requirement: 浮点扫描必须有界处理大型 Clang AST
浮点扫描器 SHALL 在任务级临时文件中承接 Clang AST 输出，并在输出写入期间执行可配置硬预算；系统 MUST NOT 截断 AST 字符串后继续将其作为完整 JSON 解析。

#### Scenario: 大于旧默认限制的合法 AST
- **WHEN** Clang 为翻译单元生成超过 16 MiB但未超过当前硬预算的合法 AST JSON
- **THEN** 扫描器 SHALL 完整解析该 AST 并继续生成 source facts
- **AND** MUST NOT 返回 `frontend_invalid_json`

#### Scenario: AST 超过硬预算
- **WHEN** Clang AST 输出超过 `max_frontend_output_bytes`
- **THEN** 扫描器 SHALL 终止该翻译单元的 frontend 进程并返回 `frontend_output_limit_exceeded`
- **AND** 诊断 SHALL 包含翻译单元身份并标记为不可重试
- **AND** MUST NOT 将输出超限描述为 JSON 损坏

#### Scenario: 完整 AST 确实损坏
- **WHEN** Clang 成功退出、输出未被截断且完整输出无法解析为合法 JSON 对象
- **THEN** 扫描器 SHALL 返回 `frontend_invalid_json`
- **AND** SHALL 保留与输出超限不同的稳定原因码

#### Scenario: AST 临时文件清理
- **WHEN** 翻译单元处理成功、失败、取消或超时
- **THEN** 扫描器 SHALL 清理对应任务级 AST 临时文件
- **AND** MUST NOT 删除源码、compile database、共享 BC 或已发布制品

### Requirement: 浮点源码事实和 provenance 必须收敛到项目语义
浮点扫描器 SHALL 仅将项目根内源码和项目头文件产生的事实作为 source facts，并 SHALL 只把规则结论直接依赖的去重事实写入 Finding provenance；系统头文件和标准库实现细节 MUST NOT 作为独立 Finding 事实批量进入结果。

#### Scenario: 项目源码包含标准库头文件
- **WHEN** 项目翻译单元包含 C++ 标准库或系统头文件并产生大量外部 AST 节点
- **THEN** 扫描器 SHALL 保留项目源码节点及其必要的有界外部符号摘要
- **AND** SHALL 排除 project root 外部节点形成的独立 source facts

#### Scenario: Finding 使用直接证据
- **WHEN** 某条规则基于少量项目 facts 形成 Finding
- **THEN** Finding fact、occurrence 和 evidence chain SHALL 只引用该结论的直接证据
- **AND** 引用 SHALL 去重并按稳定顺序输出
- **AND** MUST NOT 引用整个翻译单元的全部 source facts

#### Scenario: 直接证据超过协议上限
- **WHEN** 合法直接证据数量仍超过结果 Schema 的 provenance 上限
- **THEN** 扫描器 SHALL 使用确定性的聚合或分组表达并记录 provenance budget frontier
- **AND** SHALL 将相关结果标记为 partial 或 unknown
- **AND** MUST NOT 静默截断后声称证据链完整或发布不符合 Schema 的结果

#### Scenario: 结果原子发布前校验
- **WHEN** 扫描器准备发布浮点结果 JSON
- **THEN** 结果 SHALL 通过随工具发布的 v2 Schema 和引用闭包校验
- **AND** 合法业务扫描 MUST NOT 因生成器自身产生超过 `maxItems` 的 provenance 而转为 `internal_error`

### Requirement: 浮点分析失败必须保留可审计根因
后端 SHALL 对扫描器已原子发布、大小合规且可安全脱敏的失败结果 JSON进行不可变制品保存，并 SHALL 根据诊断因果阶段向任务错误和运行摘要公开最接近根因的诊断，而不是固定选择 diagnostics 数组第一项。

#### Scenario: frontend 失败产生派生 evidence 错误
- **WHEN** 同一结果同时包含 `frontend_invalid_json` 或 frontend budget 错误和 `source_fact_bundle_missing`
- **THEN** 后端 SHALL 将 frontend 诊断作为主失败原因
- **AND** 运行摘要 SHALL 返回主原因码和完整诊断数量

#### Scenario: 失败结果可安全保存
- **WHEN** 扫描器退出码表示失败但已发布可解析、大小合规且完成路径脱敏的结果 JSON
- **THEN** 后端 SHALL 保存该原始结果制品并关联失败运行
- **AND** 有权限用户 SHALL 能通过既有制品访问机制审计完整 diagnostics

#### Scenario: 失败结果包含不安全内容
- **WHEN** 失败结果无法通过路径、凭据或内容安全校验
- **THEN** 后端 MUST NOT 保存不安全原文
- **AND** SHALL 保存脱敏的最小诊断摘要并完成失败状态写入

#### Scenario: 不可重试错误不重复投递
- **WHEN** 主诊断属于输入无效、协议不支持、Schema 错误、AST 输出预算或其他 `retryable=false` 分类
- **THEN** worker SHALL 将任务直接标记为失败且不重新投递
- **AND** 数据库运行状态和任务状态 SHALL 保持一致

#### Scenario: 可重试瞬时错误
- **WHEN** 主诊断明确标记 `retryable=true` 且尚未达到既有重试上限
- **THEN** worker MAY 按现有任务重试策略重新投递
- **AND** 每次尝试 SHALL 保留可区分的任务事件和最终原因

### Requirement: 浮点扫描修复必须通过独立单元测试和覆盖率门禁
浮点扫描器与后端运行时修复 SHALL 使用 mock 的进程、对象存储、数据库和任务连接返回值完成独立单元测试，测试 MUST NOT 依赖真实外部服务，且项目整体与受影响模块行覆盖率和可用分支覆盖率 SHALL 均至少为 90%。

#### Scenario: 覆盖正常异常和边界流程
- **WHEN** 执行本变更的单元测试
- **THEN** 测试 SHALL 覆盖小型 AST、大于 16 MiB 的合法 AST、硬预算超限、进程失败、取消、超时、损坏 JSON、系统头文件过滤、provenance 超限、失败制品安全处理、诊断优先级和重试分类
- **AND** 测试 SHALL 对原因码、翻译单元身份、Schema 合法性、清理、制品关联和任务状态进行有效断言

#### Scenario: 覆盖率未达门槛
- **WHEN** 项目整体或受影响模块的行覆盖率低于 90%，或工具支持的分支覆盖率低于 90%
- **THEN** 本 change MUST NOT 标记实现和质量验收完成
