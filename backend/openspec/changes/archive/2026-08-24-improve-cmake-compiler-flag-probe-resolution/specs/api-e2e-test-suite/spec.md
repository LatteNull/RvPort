## ADDED Requirements

### Requirement: API E2E 必须覆盖 CMake compiler flag probe 解析
API E2E 测试套件 SHALL 覆盖 CMake compiler flag probe 动态映射的正常流程、异常流程和 edge case。

#### Scenario: 覆盖真实 CMake flag probe 映射
- **WHEN** E2E 使用包含 `check_c_compiler_flag` 或 `check_cxx_compiler_flag` 的真实 CMake 项目运行 source-only 构建和依赖分析
- **THEN** 依赖分析结果 SHALL 将命中映射的 define 标记为 `compiler_flag_probe`
- **AND** 结果 evidence SHALL 包含真实 compiler flag 和 CMake 来源文件

#### Scenario: 覆盖多层级 CMake 文件
- **WHEN** E2E 或 fixture 项目的 compiler flag 检测调用位于子目录 `CMakeLists.txt` 或 `cmake/*.cmake`
- **THEN** 后端 SHALL 能采集到对应映射
- **AND** 依赖分析 SHALL 正确解释后续 compile command 中的 define

#### Scenario: 覆盖前缀误判防护
- **WHEN** 测试项目定义了以 `FLAG_SUPPORTED_` 开头但没有 CMake 检测映射的普通宏
- **THEN** 依赖分析 MUST NOT 将其判定为 `compiler_flag_probe`
- **AND** 该结果 SHALL 按项目/构建自定义宏处理

#### Scenario: 覆盖冲突映射
- **WHEN** 测试 fixture 中同一 CMake 变量映射到多个不同 compiler flag
- **THEN** 依赖分析 SHALL 将对应结果标记为需要人工确认
- **AND** evidence SHALL 保存冲突来源
