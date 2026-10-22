## ADDED Requirements

### Requirement: 构建验证必须采集 CMake compiler flag probe 映射
构建验证运行时 SHALL 在构建事实采集中扫描 CMake 脚本并输出 compiler flag probe 映射，供依赖分析准确解释构建 define。

#### Scenario: 输出 CMake flag probe 观测
- **WHEN** 构建 wrapper 解析到 CMake compiler flag 检测调用
- **THEN** wrapper SHALL 输出结构化 `cmakeCompilerFlagProbe` 观测
- **AND** 观测 SHALL 包含变量名、语言、真实 compiler flag 和来源文件
- **AND** 观测 MUST NOT 包含服务器真实路径或明文凭据

#### Scenario: CMake probe 采集失败不影响构建
- **WHEN** CMake 脚本解析失败、文件不可读或扫描超出限制
- **THEN** 构建验证 SHALL 继续按用户脚本结果决定构建状态
- **AND** wrapper SHALL 记录 warning 或跳过不可解析文件
- **AND** CMake probe 采集失败 MUST NOT 导致成功构建变为失败

#### Scenario: 非 CMake 项目不输出 probe
- **WHEN** 源码树和构建目录不存在 CMake 文件
- **THEN** wrapper SHALL 不输出 `cmakeCompilerFlagProbe` 观测
- **AND** 依赖分析 SHALL 继续使用其他构建事实信号
