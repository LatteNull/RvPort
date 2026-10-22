## MODIFIED Requirements

### Requirement: Document production compiler adaptation limits

文档 SHALL 区分生产编译器与分析 Clang，按保留、转换、移除和不支持分类说明参数适配，覆盖语言标准、宏、目标/ABI、sysroot、包含路径、工作目录、response file 和隐式环境；SHALL 说明预定义宏和编译器扩展可能造成语义偏差。当前实现范围 SHALL 限定 GCC/Clang 的用户态 C/C++，明确不支持 MSVC/clang-cl，并区分首轮已验收标准/配置与未验证扩展。

#### Scenario: Replay a GCC compilation with analysis Clang

- **WHEN** 原始命令来自 GCC 工具链
- **THEN** 文档要求说明适配依据、隐式 GCC 安装/头文件信息、缺失信息和不支持项，明确成功生成 BC 不证明与生产编译器语义完全等价

#### Scenario: A user supplies an MSVC or clang-cl command

- **WHEN** 读者希望导入 MSVC 或 clang-cl 的 C/C++ 构建
- **THEN** 文档明确当前不支持，不提供伪装为已实现兼容的重放示例
