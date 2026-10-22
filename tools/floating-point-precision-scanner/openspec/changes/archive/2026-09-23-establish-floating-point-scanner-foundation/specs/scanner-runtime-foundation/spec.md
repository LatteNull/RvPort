## ADDED Requirements

### Requirement: 扫描器提供最小且可版本化的 CLI
扫描器 SHALL 提供 `scan`、`validate-request`、`profiles` 和 `version` 命令，并 SHALL 在版本输出中分别公开工具版本、请求/结果 schema 版本、canonical facts 版本、profile schema 版本和兼容的 Clang 版本。CLI SHALL 只编排应用用例，不得包含前端解析或风险规则判断。

#### Scenario: 查询版本
- **WHEN** 用户执行 `fp-precision-scanner version`
- **THEN** CLI 输出机器可解析的全部版本信息，并以退出码 0 结束

#### Scenario: 不支持的子命令
- **WHEN** 用户提供未知子命令或缺少必填参数
- **THEN** CLI 输出不包含堆栈的双语使用诊断，并以 `invalid_request` 对应退出码结束

### Requirement: 基础扫描只生成事实而不发布风险结论
本阶段的扫描器 SHALL 对所有计划 C/C++ 翻译单元执行 canonical facts 提取，但 MUST 保持 `findings` 为空，并 SHALL 在 metadata 中公开 `analysis_scope=facts_only` 与 `enabled_rule_count=0`。空 findings MUST NOT 被描述为已经完成风险检测或工程不存在浮点风险。

#### Scenario: 所有翻译单元完成事实提取
- **WHEN** 有效请求中的所有 C/C++ 翻译单元均成功产生 canonical facts
- **THEN** 结果状态为 `complete`、`findings` 为空，且 metadata 明确未执行风险规则

#### Scenario: 用户请求具体规则
- **WHEN** P1 请求包含非空规则启用列表
- **THEN** 扫描器在分析前返回 `invalid_request` 和双语 `rules_not_available` 诊断，而不是静默忽略

### Requirement: 运行时协议严格校验并独立演进
扫描器 SHALL 使用 JSON Schema Draft 2020-12 校验请求、结果、canonical facts 和 profile 文档；各文档 SHALL 具有独立 schema 版本和固定 kind。未知字段、缺少必填字段、不兼容主版本或跨文档引用不一致 MUST 在安全可行时聚合报告并在分析前拒绝。

#### Scenario: 有效版本化请求
- **WHEN** 请求符合受支持 schema 且所有跨文档版本和引用一致
- **THEN** 扫描器构造不可变的规范化请求并保留原始 `request_id`

#### Scenario: 同时存在多个协议错误
- **WHEN** 请求包含未知字段、不支持的主版本和缺少的必填字段
- **THEN** 验证器聚合可安全发现的错误并返回 `invalid_request`，且不启动 Clang

### Requirement: 稳定身份与确定性排序不依赖运行环境
扫描器 SHALL 使用规范化 schema/规则版本、仓库相对 POSIX 路径、语义位置和语义载荷的 SHA-256 摘要生成稳定 finding ID，并 SHALL 使用显式稳定键排序 findings、diagnostics、facts 和相关位置。绝对项目根、临时目录、时间戳、进程 ID、locale 和并发完成顺序 MUST NOT 影响身份或语义输出。

#### Scenario: 合成 finding 重复生成身份
- **WHEN** 相同 finding 候选在不同绝对工作区和不同调度顺序下生成
- **THEN** `finding_id` 完全相同，且序列化后的集合顺序相同

#### Scenario: 语义位置发生变化
- **WHEN** finding 的规范化源码位置或规则主版本变化
- **THEN** `finding_id` 发生变化，避免与原结论错误合并

### Requirement: 结果原子写出且保留既有有效文件
文件输出 SHALL 在目标文件同目录写入唯一临时文件，完整序列化并 flush/fsync 后执行原子替换。序列化、同步或替换失败时，扫描器 MUST NOT 截断或覆盖既有正式结果，并 SHALL 清理本次临时文件或留下可识别、不可被误读为正式结果的受控残留。

#### Scenario: 正常发布结果
- **WHEN** 结果成功完成序列化、同步和原子替换
- **THEN** 正式路径只呈现完整、符合 schema 的新结果

#### Scenario: 原子替换失败
- **WHEN** 文件系统在替换阶段返回错误且目标路径已有有效结果
- **THEN** 既有结果字节保持不变，扫描状态映射为安全的失败诊断

### Requirement: 状态与退出码完整映射
运行时 SHALL 使用 `complete=0`、`invalid_request=2`、`failed=3`、`partial=4`、`internal_error=5` 的固定映射。CLI 适配器 MUST 保留应用层状态，不得用 finding 数量或日志严重性改写退出码。

#### Scenario: 部分事实可用
- **WHEN** 至少一个计划翻译单元完成且至少一个失败
- **THEN** 结果状态为 `partial`、退出码为 4，并公开 planned/completed/failed/unknown 分母

#### Scenario: 未分类异常
- **WHEN** 未预期异常越过应用边界
- **THEN** CLI 返回 `internal_error` 和退出码 5，默认结果不包含堆栈、环境变量或根外绝对路径
