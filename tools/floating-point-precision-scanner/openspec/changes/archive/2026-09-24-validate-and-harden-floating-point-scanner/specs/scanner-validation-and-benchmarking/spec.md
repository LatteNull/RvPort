## ADDED Requirements

### Requirement: Reviewed validation corpus 必须版本化且有显式真值
扫描器 SHALL 提供本地、离线、版本化的 C/C++ validation corpus 和 oracle，覆盖 C11、C17、C++17、C++20、x86/RISC-V profiles、AST-only、共享 LLVM BC 和 AST↔IR evidence。每条规则 MUST 至少包含 6 个正例、6 个反例、3 个预期 unknown/unsupported，以及 suppression、边界或异常 case；每个 oracle case MUST 固定输入摘要、规则/范围、预期 assessment、semantic finding key、允许的 diagnostic code、reviewer 和 review revision。oracle MUST NOT 由待测实现自动生成。

#### Scenario: 固定 case 被重复验证
- **WHEN** 相同 corpus、oracle、工具和 schema 版本在不同绝对工作区运行
- **THEN** case 身份、预期语义、实际 assessment/finding 集和验证结论保持一致

#### Scenario: 规则缺少负例
- **WHEN** 任一规则没有达到规定的正例、反例、unknown 或生命周期 case 数量
- **THEN** corpus 完整性门禁失败，且该规则的质量验收不得标记完成

### Requirement: 检测质量指标必须公开严格分母
验证器 SHALL 以 oracle rule/scope 为评价单元，按 finding code 输出 TP、FP、FN、strict precision、strict recall、supported-only precision/recall、exact-match 和 abstention/unknown。预期 matched 但实际为 unknown、skipped 或 failed MUST 同时计入 strict FN 和 abstention；意外 finding 和 strict 模式下在预期保守 abstain 范围发布的确定 finding MUST 计入 FP。supported-only 只能排除 oracle 明确标记为固有 unsupported 的 case，不得排除扫描器意外产生的 unknown/failed。任一零分母指标 MUST 为 JSON `null`，不得伪造 0 或 100%。

#### Scenario: 正例意外返回 unknown
- **WHEN** oracle 标记为可判定 matched 的 case 实际返回 unknown
- **THEN** 该 case 增加 FN 和 abstention，strict recall 降低，不能从 supported-only 分母中移除

#### Scenario: 指标零分母
- **WHEN** 某个合法筛选维度没有预测正例或真值正例
- **THEN** 对应 precision 或 recall 输出 `null`，同时公开分子和分母计数

### Requirement: 质量验收必须按规则和失败语义门禁
每条规则的 strict precision 和 strict recall MUST 均不低于 90%，整体 exact-match rate MUST 不低于 95%，并且失败、预算、缓存和 suppression 生命周期 case MUST 100% exact match。启发式规则的 oracle SHALL 评价候选证据、confidence、rationale 和人工确认要求，不得臆造业务容差或把未经确认的业务缺陷作为真值。

#### Scenario: 整体达标但单规则漏检
- **WHEN** 整体指标超过门槛但任一 finding code 的 strict recall 低于 90%
- **THEN** 验证门禁失败并报告该规则的 TP/FP/FN/abstention 分母

#### Scenario: 失败状态不匹配
- **WHEN** finding 指标达标但某个预算或内部错误 case 的 status、退出码或 diagnostic code 与 oracle 不同
- **THEN** exact-match 强制门禁失败

### Requirement: Benchmark 必须使用固定环境和数值预算
benchmark SHALL 在锁定的 Linux/amd64 容器、Clang/LLVM 21.1.8、4 vCPU、4 GiB memory、禁用网络的环境运行三次并取中位数。固定档位 MUST 为 S=20 TU/约 10,000 行、M=100 TU/约 50,000 行、L=500 TU/约 250,000 行；冷缓存 wall 上限分别为 60/240/900 秒，CPU 上限为 180/720/2700 秒，峰值 RSS 上限为 1.5/2.5/3.5 GiB，结果大小上限为 16/64/256 MiB。热缓存 wall 中位数 MUST 不超过同档冷缓存的 60%，且 wall、CPU 或 RSS 相对已接受基线回退不得超过 20%。

#### Scenario: 冷热缓存结果一致
- **WHEN** 同一 benchmark 输入先以空缓存、再以完整有效缓存运行
- **THEN** 两次 scan 语义输出逐字节一致，独立 telemetry 记录不同耗时且热缓存满足比例门禁

#### Scenario: 宿主资源不满足固定环境
- **WHEN** 执行环境不能提供 4 vCPU、4 GiB 或要求的 Linux/amd64 隔离
- **THEN** benchmark 报告环境不适用且性能验收保持未完成，不使用宽松阈值替代

### Requirement: 验证报告必须版本化并可审计
验证器 SHALL 输出 `validation-result@1.0`，包含 corpus/oracle/tool/schema/profile/container digests、逐 case 结果、逐 finding code 指标、总体指标、benchmark telemetry、预算、环境适用性和最终门禁结论。报告集合 MUST 稳定排序，不能包含凭据、根外绝对路径或系统当前时间参与的语义字段。

#### Scenario: Oracle 内容变化
- **WHEN** fixture 或 oracle 内容发生变化
- **THEN** corpus/oracle digest 和验证报告身份相应变化，不能与旧报告错误合并
