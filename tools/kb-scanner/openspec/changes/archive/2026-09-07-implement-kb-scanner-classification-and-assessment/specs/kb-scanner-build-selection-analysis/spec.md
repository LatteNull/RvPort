## ADDED Requirements

### Requirement: 构建选择必须为测试资产提供可追溯角色和目标关系
Build Frontend/Selection Analyzer SHALL 从已有 Make、CMake、Meson、CTest、compilation database 和 RPM `%check` 静态输入恢复 test target、test source、test argument/dependency、configuration 和 package section role，并 SHALL 将其以 scanner-owned Evidence/Relation/ProofPath 提供给 Test Selection Analyzer；动态命令或仅凭名称得到的角色 MUST 保持 unknown/candidate。

#### Scenario: CTest metadata 关联测试源码与目标
- **WHEN** 已有 CTest/CMake/Meson metadata 明确声明 test、target、source 和 configuration
- **THEN** Build Selection Analyzer SHALL 建立 configuration 到 test target/source 的选择关系
- **AND** 每条关系 SHALL 保留 JSON pointer、producer、selection status 和 Evidence 引用

#### Scenario: Make test target 对 RISC-V inactive
- **WHEN** 完整架构条件证明含 x86 依赖的 test target 对 RISC-V inactive/not_selected
- **THEN** build proof SHALL 保留该测试路径和 x86 Evidence
- **AND** Test Classifier MAY 据此形成 `x86_test_guarded`，但不得声明项目整体 ready

#### Scenario: 测试 recipe 包含可执行命令
- **WHEN** Make/RPM/CTest 测试定义包含 recipe、shell、Lua 或 test command
- **THEN** scanner SHALL 只恢复声明、参数和选择 Evidence，并将需执行部分保持 unsupported/unknown
- **AND** scanner MUST NOT 运行测试、构建工具或项目命令
