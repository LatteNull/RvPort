## ADDED Requirements

### Requirement: E2E 必须覆盖 KB 自动复用 compile database
API E2E 测试套件 SHALL 覆盖 source/x86 构建生成 compile database 后，KB 扫描自动复用该构建上下文的端到端行为。

#### Scenario: 成功复用 compile database
- **WHEN** E2E 创建项目、上传或同步源码、部署 source 环境并运行 source-only 构建
- **AND** 构建在远端工作目录生成合法 `compile_commands.json`
- **THEN** E2E SHALL 等待构建成功
- **AND** E2E SHALL 创建 KB 扫描且不提交 compile database 参数
- **AND** E2E SHALL 校验 KB 扫描成功
- **AND** E2E SHALL 校验 KB scan summary 中 `compileCommands.mode=USED`

#### Scenario: 没有 compile database 时降级
- **WHEN** E2E 运行构建但未生成 `compile_commands.json`
- **THEN** 后续 KB 扫描 SHALL 成功或按 scanner 结果进入终态
- **AND** E2E SHALL 校验 KB scan summary 中 `compileCommands.mode=NOT_AVAILABLE` 或等效降级状态
- **AND** E2E SHALL 校验任务没有因为缺少 compile database 失败

#### Scenario: compile database artifact 异常
- **WHEN** E2E 或测试支持能力制造 compile database artifact 缺失、不可下载或内容非法
- **THEN** KB 扫描 SHALL 降级为源码上下文扫描
- **AND** summary SHALL 记录 `FALLBACK` 和安全原因码
- **AND** API 响应 MUST NOT 暴露对象存储 key、服务器真实路径或远端路径

#### Scenario: 清理测试数据
- **WHEN** compile database 复用 E2E 成功或失败
- **THEN** runner SHALL 清理本次 run id 创建的项目、源码版本、部署运行、构建运行、KB scan、findings、tasks、stored artifacts 和对象存储测试对象
