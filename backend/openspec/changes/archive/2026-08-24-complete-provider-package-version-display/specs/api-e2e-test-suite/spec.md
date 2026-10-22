## ADDED Requirements

### Requirement: API E2E 必须覆盖依赖分析 provider 版本展示
API E2E 测试套件 SHALL 覆盖构建驱动依赖分析中 provider package/version、detected version、provider version status 和 HTML/JSON 展示字段。

#### Scenario: 正常流程校验 provider 版本字段
- **WHEN** E2E 运行依赖分析模块并产生构建工具、ELF 或 SO 依赖结果
- **THEN** 测试 SHALL 查询依赖分析结果列表和详情
- **AND** 测试 SHALL 校验响应包含源 provider package/version、目标 provider package/version、detected version、provider version status、目标匹配状态和风险等级字段
- **AND** 测试 SHALL 校验 JSON artifact 中包含同一组字段
- **AND** 测试 SHALL 校验 HTML artifact 或真实验证 HTML 展示同一组可审计字段

#### Scenario: 异常流程校验 provider 版本缺失
- **WHEN** E2E 构造或运行源 owner 查询失败、目标 provider 查询失败或版本解析失败的依赖分析场景
- **THEN** 测试 SHALL 验证 API 和 artifact 返回 `UNKNOWN`、warning 或明确空值
- **AND** 测试 SHALL 验证任务不会因为单条 provider 版本缺失而整体失败
- **AND** 测试 SHALL 验证响应中不包含明文凭据、远端真实敏感路径或完整构建日志

#### Scenario: edge case 校验 ELF 和工具版本来源
- **WHEN** E2E 覆盖 ELF/SO、命令行工具、目标软件源可用但未安装、源无 owner package 但有 detected version 的场景
- **THEN** 测试 SHALL 验证 ELF/SO 不依赖默认 `--version` 输出
- **AND** 测试 SHALL 验证工具命令版本只作为 detected version 或 evidence 保存
- **AND** 测试 SHALL 验证风险等级与 `providerVersionStatus` 的映射一致
