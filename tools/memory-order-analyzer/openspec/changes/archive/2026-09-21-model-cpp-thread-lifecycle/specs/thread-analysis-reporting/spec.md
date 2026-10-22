## ADDED Requirements

### Requirement: Report C++ lifecycle overlays without changing P3 reports

系统 SHALL 发布独立 `CppThreadLifecycleReport v1`，引用而不内嵌重写既有 P3 报告，并分别列出标准库 profile、计划/完成 TU、callable、对象、context/instance、construct/start/join/detach 关系、gap、frontier、缓存和预算。报告 SHALL 保持确定排序、canonical digest、`safety=not_evaluated` 和 `findings=null`。

#### Scenario: A complete graph has no join
- **WHEN** 所有计划构造均成功建模但程序只 detach 或不 join
- **THEN** 报告可说明 join relation 为零并列出实际生命周期，不表述为安全或无并发问题

#### Scenario: P3 and A3 are both present
- **WHEN** scope 同时包含 C pthread 与 C++ `std::thread` 关系
- **THEN** 报告以来源和协议身份分别展示并提供去重/组合引用，不改写原 P3 JSON

### Requirement: Provide bilingual actionable lifecycle diagnostics

每个 A3 failure/gap/unknown SHALL 同时提供稳定 code、中文 detail/suggestion 和对应英文 `detail_en`/`suggestion_en`，并引用 TU、实体、对象、调用、profile、路径和缺失证据。诊断 MUST 区分不支持标准库、ABI mismatch、callable ambiguous、object provenance、异常结果、scope 缺失和预算耗尽。

#### Scenario: A library profile is unsupported
- **WHEN** TU 使用未注册或未验证的标准库/ABI profile
- **THEN** 报告中英文说明实际 fingerprint、缺少的注册资格和可复现建议，不把它归类为没有线程
