## ADDED Requirements

### Requirement: E2E 必须覆盖 compile database 派生 KB finding
API E2E 测试套件 SHALL 覆盖 KB 扫描从 `compile_commands.json` 派生 finding 的正常流程、异常流程和 edge case。

#### Scenario: 正常流程生成 compile command finding
- **WHEN** E2E 创建项目、准备源码版本并完成 source/x86 构建
- **AND** 构建产物中保存的 compile database 包含明确 x86/SIMD 编译参数
- **AND** E2E 创建 KB 扫描且不手动提交 compile database 参数
- **THEN** KB 扫描 SHALL 成功或按 scanner 结果进入终态
- **AND** E2E SHALL 校验 scan summary 中 `compileCommands.mode=USED`
- **AND** E2E SHALL 校验 findings 列表或详情中存在来源为 compile command 的 finding

#### Scenario: 源码无文本风险但编译命令有风险
- **WHEN** E2E fixture 的源码正文不包含 x86/SIMD 风险文本
- **AND** compile database 中包含 `-mavx2`、`-msse`、`-march=x86-64` 或等效参数
- **THEN** KB 扫描 SHALL 生成 compile command 派生 finding
- **AND** finding evidence SHALL 包含命中 token、token 类型、源码相对路径和 compile command 索引

#### Scenario: compile database 不减少既有源码 finding
- **WHEN** E2E 对同一源码版本分别运行不带 compile database 和带 compile database 的 KB 扫描
- **THEN** 带 compile database 的扫描 MUST NOT 隐藏不带 compile database 时已经产生的源码 finding
- **AND** E2E SHALL 校验源码 finding 数量或 fingerprint 集合不被减少

#### Scenario: 非法 compile database 降级
- **WHEN** E2E 或测试支持能力制造缺失、不可下载或非法 JSON 的 compile database artifact
- **THEN** KB 扫描 SHALL 降级为源码上下文扫描或按受控错误进入终态
- **AND** E2E SHALL 校验 API 响应、任务日志和 summary 不暴露对象存储 key、服务器真实路径或远端路径

#### Scenario: 过滤内部构建探测 entry
- **WHEN** E2E fixture 的 compile database 包含 CMake、Meson、Ninja 或编译器内部探测文件 entry
- **AND** 这些 entry 不关联项目源码扫描范围
- **THEN** KB 扫描 MUST NOT 为这些 entry 生成 compile command finding

#### Scenario: 清理 compile command finding 测试数据
- **WHEN** compile command 派生 finding E2E 成功或失败
- **THEN** runner SHALL 清理本次 run id 创建的项目、源码版本、构建运行、KB scan、findings、任务、stored artifacts、对象存储测试对象和 runtime 临时文件
