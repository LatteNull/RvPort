## ADDED Requirements

### Requirement: API E2E 必须验证 C++ 编译器 provider 匹配
独立 API E2E 套件 SHALL 使用真实构建和环境快照验证 C++ 编译工具不会被目标环境中的裸 `gcc` 错误满足，并 SHALL 覆盖正常流程、异常流程和 edge case。

#### Scenario: 正常流程验证目标仓库 gcc-c++ 候选
- **WHEN** E2E 项目使用 CMake 构建 C++ 源码，源环境实际执行 `c++` 且 provider 为 `gcc-c++`，目标环境仅安装 `gcc` 但仓库提供 `gcc-c++`
- **THEN** 依赖分析 API SHALL 返回 `BUILD_TOOL c++`
- **AND** 结果 SHALL 为 `REPO_AVAILABLE/MEDIUM`
- **AND** 目标 provider package 和版本 SHALL 来自目标仓库中的 `gcc-c++`

#### Scenario: 异常流程验证裸 gcc 不满足 C++ 构建
- **WHEN** 目标环境只有 `gcc`，且不存在目标 C++ 工具或可用 C++ provider package
- **THEN** API 结果 MUST NOT 返回 `TARGET_INSTALLED`
- **AND** 结果 SHALL 清楚表示依赖未满足且不泄露远端路径或凭据

#### Scenario: Edge case 验证多证据去重
- **WHEN** compile database、execve 和日志中同时出现同一 `c++` 工具
- **THEN** API SHALL 只返回一个语义唯一的 C++ 构建工具结果
- **AND** 结果 SHALL 保留实际工具名、源 provider、目标 provider 和最高质量证据

#### Scenario: E2E 清理测试数据
- **WHEN** C++ provider 匹配 E2E 完成或中途失败
- **THEN** 套件 SHALL 清理创建的项目、环境、任务、分析结果和相关制品
- **AND** 测试 MUST NOT 在共享环境中遗留凭据或测试数据
