## ADDED Requirements

### Requirement: Document the AST and IR authority boundary

项目 SHALL 在 README、文档索引、路线图和 `doc/AST_CROSS_TU_EVIDENCE.md` 说明 source facts、program entity、AST–IR binding、LLVM memory facts、P3 execution relations 与 P4 publication conclusions各自能证明和不能证明的内容，并明确 `compile_commands.json` 不是 target/link 图、AST source order 不是 SB/SW/HB、BC 编译或零 finding 不是安全证明。

#### Scenario: A reader follows one cross-TU finding

- **WHEN** 读者查看文档中的跨 TU publication 示例
- **THEN** 能从 source declaration/definition、canonical object、IR access、thread relation 到 finding 逐层定位证据和 unknown 边界

### Requirement: Publish reproducible AST-assisted validation results

`doc/AST_CROSS_TU_EVIDENCE_VALIDATION.md` SHALL 记录实际环境、锁定 Clang/LLVM 与输入 hash、命令、测试/覆盖率分母、IR-only 与 AST-assisted truth 指标、source/binding 完整性、TinyCThread cold/warm 性能/缓存、未运行项和限制；未执行结果 MUST 标为 not_run。面向用户的诊断、原因与建议示例 SHALL 同时提供中文和英文字段。

#### Scenario: Validation is not yet complete

- **WHEN** 任一 90% 覆盖率、truth、确定性、真实工程或文档门禁尚未通过
- **THEN** 文档标明实际失败/未运行状态，不写成已实现、已验证或可归档

#### Scenario: AST-assisted exact match improves

- **WHEN** 固定 truth 中的实际指标优于 IR-only 基线
- **THEN** 文档发布精确 case/分母和代价，同时保留非全程序安全声明及未支持 fence/RMW/std::thread 边界
