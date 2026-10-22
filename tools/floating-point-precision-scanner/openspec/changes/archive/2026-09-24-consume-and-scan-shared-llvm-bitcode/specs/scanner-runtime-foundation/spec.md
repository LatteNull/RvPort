## MODIFIED Requirements

### Requirement: 扫描器提供最小且可版本化的 CLI
扫描器 SHALL 提供 `scan`、`validate-request`、`profiles` 和 `version` 命令，并 SHALL 在版本输出中分别公开工具版本、请求/结果 schema、AST canonical facts、共享 BC manifest、LLVM facts、AST↔IR evidence、profile schema 版本以及兼容的 Clang、LLVM reader/extractor 版本。CLI SHALL 只编排应用用例，不得包含 AST/IR 解析、evidence 绑定或风险规则判断。

#### Scenario: 查询版本
- **WHEN** 用户执行 `fp-precision-scanner version`
- **THEN** CLI 输出机器可解析的全部协议与 toolchain 版本信息，并以退出码 0 结束

#### Scenario: 不支持的子命令
- **WHEN** 用户提供未知子命令或缺少必填参数
- **THEN** CLI 输出不包含堆栈的双语使用诊断，并以 `invalid_request` 对应退出码结束

### Requirement: 基础扫描只生成事实而不发布风险结论
本阶段的扫描器 SHALL 对所有计划 C/C++ 翻译单元执行 AST canonical facts 提取；当请求提供共享 BC 时，还 SHALL 执行 manifest 消费、LLVM facts 提取和 AST↔IR evidence 绑定。扫描器 MUST 保持 `findings` 为空，并 SHALL 在 metadata 中公开 `analysis_scope=facts_only`、`enabled_rule_count=0`、`ir_analysis`、请求/完成 profiles 和 source-mapping 状态。空 findings MUST NOT 被描述为已经完成风险检测或工程不存在浮点风险。

#### Scenario: 所有 AST 与共享 BC facts 完成
- **WHEN** 有效请求中的所有 C/C++ 翻译单元均成功产生所请求的 AST facts、LLVM facts 和必需 evidence
- **THEN** 结果状态为 `complete`、`findings` 为空，且 metadata 明确只完成事实和证据提取、未执行风险规则

#### Scenario: AST-only facts 完成
- **WHEN** 请求未提供共享 BC 且所有 AST canonical facts 成功
- **THEN** 结果可以为 `complete`，同时明确 `ir_analysis=not_requested`，不得暗示已验证最终 IR 行为

#### Scenario: 用户请求具体规则
- **WHEN** 本 change 请求包含非空规则启用列表
- **THEN** 扫描器在分析前返回 `invalid_request` 和双语 `rules_not_available` 诊断，而不是静默忽略

### Requirement: 运行时协议严格校验并独立演进
扫描器 SHALL 使用 JSON Schema Draft 2020-12 校验 request、result、AST canonical facts、共享 BC manifest、LLVM facts、AST↔IR evidence 和 profile 文档；各文档 SHALL 具有独立 schema 版本和固定 kind。未知字段、缺少必填字段、不兼容主版本、digest 不一致或跨文档身份/引用不一致 MUST 在安全可行时聚合报告，并在相关 AST/LLVM/evidence 工作启动前拒绝该层输入。

#### Scenario: 有效版本化 source 与 BC 请求
- **WHEN** 请求及其 manifest、facts/evidence schema 均受支持且所有跨文档版本、摘要和引用一致
- **THEN** 扫描器构造不可变的规范化请求并保留原始 `request_id` 与 artifact-set 身份

#### Scenario: 同时存在多个协议错误
- **WHEN** 请求或 manifest 包含未知字段、不支持的主版本和缺少的必填字段
- **THEN** 验证器聚合可安全发现的错误并返回 `invalid_request`，且不启动 Clang 或 LLVM worker

### Requirement: 稳定身份与确定性排序不依赖运行环境
扫描器 SHALL 使用规范化 schema/producer/profile 版本、artifact/bundle digest、仓库相对 POSIX 路径、语义位置和语义载荷的 SHA-256 摘要生成稳定 facts、evidence 和未来 finding 身份，并 SHALL 使用显式稳定键排序 findings、diagnostics、source/IR facts、bindings、unknowns 和相关位置。绝对项目根、artifact root、临时目录、时间戳、进程 ID、locale 和并发完成顺序 MUST NOT 影响身份或语义输出。

#### Scenario: 相同制品重复生成身份
- **WHEN** 相同 source/IR facts 和 evidence 候选在不同绝对工作区、artifact root 与调度顺序下生成
- **THEN** facts/evidence ID、semantic digest 和序列化集合顺序完全相同

#### Scenario: 语义或制品身份发生变化
- **WHEN** 规范化源码位置、BC artifact key、IR 语义、binding method 或 schema 主版本变化
- **THEN** 相应 facts/evidence 身份或 semantic digest 发生变化，避免与原证据错误合并
