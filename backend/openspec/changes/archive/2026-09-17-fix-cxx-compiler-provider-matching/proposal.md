## Why

当前依赖分析虽然能够从 `compile_commands.json` 和 `strace execve` 观测到实际执行的 `c++`，但目标能力匹配会把已安装的 `gcc` 当作 `c++` 的可满足别名，导致目标环境缺少 C++ 编译驱动和 `gcc-c++` 时仍被误判为 `TARGET_INSTALLED/LOW`。这会隐藏真实构建依赖，并使一键修复候选和迁移报告失真。

## What Changes

- 将“实际执行工具”“编译器能力”和“provider package”分层匹配，保留实际观测到的工具名称，同时使用源环境 provider package 判断目标是否已安装或仓库可用。
- 修正 C++ 编译器别名规则，禁止使用裸 `gcc` 满足 `c++` 或 `g++`，并按源侧编译器家族约束等价工具匹配。
- 当源侧 `c++` 由 `gcc-c++` 提供、目标未安装 C++ 驱动但仓库存在 `gcc-c++` 时，返回 `REPO_AVAILABLE/MEDIUM` 及准确的双方 provider 信息。
- 收敛重复的工具别名定义，确保 compile database、execve 和工具文本提取共享同一套匹配规则。
- 补充正常流程、异常流程和 edge case 的单元测试与真实 API E2E 回归，并执行项目整体及受影响模块至少 90% 的行/分支覆盖率验收。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `dependency-analysis-runtime`: 修正 C/C++ 编译器工具与 provider package 的目标能力匹配、状态和风险映射要求。
- `api-e2e-test-suite`: 增加 C++ 构建依赖在目标环境仅安装 `gcc`、但仓库提供 `gcc-c++` 时的真实 API 回归验证。

## Impact

- 主要影响 `DependencyFactExtractor` 的工具证据解析、provider 解析、目标能力匹配和去重逻辑。
- 依赖分析结果中的 `targetMatchStatus`、`riskLevel`、`targetProviderPackage` 和推荐信息可能因修复而变化，但不新增或破坏现有 API 字段。
- 一键修复候选将能够依据 `gcc-c++` 的仓库可用结果正确派生。
- 需要扩展依赖分析单元测试、API E2E fixture 和覆盖率验收；不引入新的外部服务依赖。
