# scanner-runtime-foundation Specification

## Purpose

定义仅面向 C/C++ 的浮点精度扫描器基础运行时，包括最小 CLI、facts-only 边界、版本化协议、稳定身份、原子输出以及状态和退出码。

## Requirements

### Requirement: 扫描器提供最小且可版本化的 CLI
扫描器 SHALL 提供 `scan`、`validate-request`、`profiles` 和 `version` 命令，并 SHALL 在版本输出中分别公开工具版本、请求/结果 schema、AST canonical facts、共享 BC manifest、LLVM facts、AST↔IR evidence、profile schema 版本以及兼容的 Clang、LLVM reader/extractor 版本。CLI SHALL 只编排应用用例，不得包含 AST/IR 解析、evidence 绑定或风险规则判断。

#### Scenario: 查询版本
- **WHEN** 用户执行 `fp-precision-scanner version`
- **THEN** CLI 输出机器可解析的全部版本信息，并以退出码 0 结束

#### Scenario: 不支持的子命令
- **WHEN** 用户提供未知子命令或缺少必填参数
- **THEN** CLI 输出不包含堆栈的双语使用诊断，并以 `invalid_request` 对应退出码结束

### Requirement: 运行时执行已注册核心规则并保留 facts-only 兼容模式
扫描器 SHALL 在 source facts、IR facts、evidence、profiles 和可选 build contexts 通过各自 schema/摘要校验后，按 registry 稳定顺序执行请求启用的十条规则，并将每个 rule/scope 的结果记录为 `matched`、`not_matched`、`unknown`、`skipped` 或 `failed` assessment。descriptor SHALL 驱动所需 source/IR fact kinds、profile/build-context fields、IR capability、assessment scope、evidence mode 和预算；运行时不得为规则硬编码未声明依赖。只有 `matched` SHALL 形成 finding candidate；`unknown`、`skipped` 和 `failed` MUST 进入独立分母和诊断，且不得被统计为安全。有效 suppression 在稳定 candidate 身份生成后应用。空规则集合 SHALL 跳过规则层、保持 `findings=[]` 并明确 `analysis_scope=facts_only`。

#### Scenario: schema 1.3 默认规则全部完成
- **WHEN** schema 1.3 请求省略规则配置，十条默认规则的必需 facts/evidence/profile/build-context 均完整且执行成功
- **THEN** 结果标记 `analysis_scope=migration_risks`，公开十条规则、依赖摘要及逐状态 assessment 分母，并发布或审计抑制所有 matched candidates

#### Scenario: 显式空规则集合
- **WHEN** 请求设置 `rules.enabled=[]`
- **THEN** 扫描器只完成 facts/evidence pipeline，结果标记 `facts_only`，且不把空 findings 描述为无迁移风险

#### Scenario: 规则只依赖 AST
- **WHEN** 启用规则的 descriptor 不要求 IR，且所需 source facts/profile 完整
- **THEN** 该规则可完成 assessment，不因请求未提供共享 BC 而无关地变为 unknown

#### Scenario: 单条规则发生可隔离异常
- **WHEN** 一条规则在某个 scope 内抛出已分类的可隔离异常，而其他规则输入有效
- **THEN** 该 scope assessment 为 `failed`，其他规则继续，整体状态按可用与失败 assessment 保守聚合

### Requirement: 运行时协议严格校验并独立演进
扫描器 SHALL 使用 JSON Schema Draft 2020-12 校验 request、result、AST canonical facts、共享 BC manifest、LLVM facts、AST↔IR evidence 和 profile 文档；各文档 SHALL 具有独立 schema 版本和固定 kind。未知字段、缺少必填字段、不兼容主版本、digest 不一致或跨文档身份/引用不一致 MUST 在安全可行时聚合报告，并在相关 AST/LLVM/evidence 工作启动前拒绝该层输入。

#### Scenario: 有效版本化 source 与 BC 请求
- **WHEN** 请求及其 manifest、facts/evidence schema 均受支持且所有跨文档版本、摘要和引用一致
- **THEN** 扫描器构造不可变的规范化请求并保留原始 `request_id` 与 artifact-set 身份

#### Scenario: 同时存在多个协议错误
- **WHEN** 请求或 manifest 包含未知字段、不支持的主版本和缺少的必填字段
- **THEN** 验证器聚合可安全发现的错误并返回 `invalid_request`，且不启动 Clang 或 LLVM worker

### Requirement: 稳定身份与确定性排序不依赖运行环境
扫描器 SHALL 使用规范化 schema/producer/profile/rule 版本、artifact/bundle digest、仓库相对 POSIX 路径、语义位置和语义载荷的 SHA-256 摘要生成稳定 facts、evidence、assessment 和 finding 身份，并 SHALL 使用显式稳定键排序 findings、diagnostics、assessments、source/IR facts、bindings、unknowns 和相关位置。finding ID MUST 包含 rule code/version、规范化 scope、主要位置、排序后的语义 evidence refs 与 profile fingerprints，但 MUST NOT 包含展示文本。绝对项目根、artifact root、临时目录、时间戳、进程 ID、locale 和并发完成顺序 MUST NOT 影响身份或语义输出。

#### Scenario: 相同证据重复执行规则
- **WHEN** 相同 source/IR facts、evidence、profiles 和规则版本在不同绝对工作区、artifact root 与调度顺序下执行
- **THEN** facts/evidence/assessment/finding ID、semantic digest 和序列化集合顺序完全相同

#### Scenario: 规则或语义证据发生变化
- **WHEN** 规范化源码位置、BC artifact key、IR 语义、binding method、profile fingerprint、rule major version 或语义 evidence refs 变化
- **THEN** 相应 assessment/finding 身份或 semantic digest 发生变化，避免与原结论错误合并

#### Scenario: 只有双语展示文本变化
- **WHEN** rule code/version、scope 和语义证据不变，仅中文或英文文案被修正
- **THEN** finding ID 保持不变，但完整输出文档摘要可以反映展示内容变化

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

### Requirement: 函数摘要和表达式规则执行必须有界且确定
运行时 SHALL 对函数摘要传播深度、调用边、comparison/reduction candidates、IR use-chain、related locations、suppression records 和每规则 wall/CPU 设置显式预算。所有候选 MUST 在截断前按 rule order、scope、规范化位置和 semantic fact IDs 排序；达到预算 MUST 保留已完成结果并记录最后稳定 frontier，且并发完成顺序不得改变输出。

#### Scenario: fenv 调用传播达到深度上限
- **WHEN** 直接调用摘要链超过配置传播深度
- **THEN** 已完成摘要保留，剩余调用边产生 unknown assessment/诊断和稳定 frontier

#### Scenario: 归约候选顺序变化
- **WHEN** 相同输入以不同 worker 完成顺序产生相同归约候选集合
- **THEN** 预算截断保留相同 candidates，assessment/finding/suppression 顺序和摘要完全一致

### Requirement: 全流程预算必须由统一协调器执行
扫描器 SHALL 为每个请求建立统一 BudgetCoordinator，以共享 monotonic deadline、CPU/RSS sampler 和稳定逻辑计数约束 Clang 前端、LLVM worker、facts 映射、evidence、规则、诊断、suppression、缓存及输出。全局 wall time MUST 从请求开始累计且不得按 TU/worker 重置；CPU 和内存预算 MUST 同时约束扫描器及其子进程。平台无法强制某项请求预算时 MUST 在分析前公开 unsupported 能力或保守失败，不得声称预算已执行。

#### Scenario: 多个 TU 共用 wall deadline
- **WHEN** 前几个 TU 已消耗大部分全局 wall budget
- **THEN** 后续 TU 只能使用剩余时间，达到 deadline 后停止启动新工作并产生稳定预算 frontier

#### Scenario: Clang 超出内存预算
- **WHEN** AST 前端子进程超过请求的内存上限
- **THEN** 进程被隔离终止，对应 TU 计入 failed/unknown，其他已完成结果被保留

### Requirement: 逻辑预算必须在稳定排序后截断
文件数、artifact/BC 字节、worker 输出、facts、evidence candidates、rule candidates、assessment、evidence refs、related locations、diagnostic 和 suppression records SHALL 在候选按规范稳定键排序后执行限制。预算耗尽 MUST 记录预算名称、limit、稳定逻辑用量、受影响 rule/scope 和最后完成 frontier；未处理范围不得计为 not_matched。

#### Scenario: rule candidate 上限
- **WHEN** 稳定排序后的候选数量超过 `max_rule_candidates`
- **THEN** 只处理确定的前缀，剩余范围计入 unknown，重复运行产生相同 frontier

#### Scenario: diagnostic 上限
- **WHEN** 普通诊断达到 `max_rule_diagnostics`
- **THEN** 扫描器聚合或截断普通诊断并保留一个终止槽发布预算耗尽诊断

### Requirement: 易波动资源观测不得污染语义身份
scan result SHALL 记录预算 limit、稳定逻辑用量和 frontier，但实际 wall、CPU、RSS 样本 MUST 写入独立 validation/benchmark telemetry，不得进入 finding/assessment/cache key 或 scan semantic digest。相同输入因调度抖动产生不同采样值时语义结果仍须稳定。

#### Scenario: 两次运行耗时不同
- **WHEN** 相同输入两次运行的 wall time 或峰值 RSS 不同且均未超限
- **THEN** scan semantic digest、stable IDs 和集合排序保持相同，差异只出现在独立 telemetry
