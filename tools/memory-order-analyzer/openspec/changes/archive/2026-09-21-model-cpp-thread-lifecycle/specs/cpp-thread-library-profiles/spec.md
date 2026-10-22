## ADDED Requirements

### Requirement: Register exact C++ thread library profiles

系统 SHALL 以严格 `CppThreadLibraryProfile v1` 注册可支持的 libstdc++/libc++ 模型，身份至少包含 C++ 标准、vendor/version、C++ ABI、target triple、DataLayout/指针宽度、异常/RTTI/线程后端配置、关键头文件与 wrapper signature digest、工具链 lineage 和模型版本。只有全部资格匹配的 profile 才能采用；首版验收 SHALL 在锁定开发环境实际验证至少一个 libstdc++ profile 和一个 libc++ profile。

#### Scenario: A locked libstdc++ profile matches
- **WHEN** TU 的标准库、版本、target、ABI、配置和 wrapper digest 与已验证注册项逐项一致
- **THEN** 采用对应模型并在产物和缓存身份中记录注册项及全部资格证据

#### Scenario: A libc++ wrapper layout changes
- **WHEN** vendor/version 名称匹配但任一 broker 签名、参数角色、calling convention 或布局 digest 不同
- **THEN** 拒绝模型采用并产生 `abi-wrapper-mismatch`，不得按相似符号继续分析

### Requirement: Normalize verified standard-library boundaries without hiding evidence

已采用模型 SHALL 将标准库内部路径归约为带来源的规范化角色，包括 construct-attempt、entry-broker、join-attempt、detach-attempt 和 handle-transfer；每个角色 MUST 引用实际 AST/IR/system-header 证据及 profile。系统边界 SHALL 防止无界展开，同时不得把 broker 内底层 pthread 调用重复计为用户直接 pthread create/join。

#### Scenario: A broker calls pthread_create internally
- **WHEN** 已采用的标准库 entry broker 包含底层 `pthread_create`
- **THEN** 该调用标记为 A3 标准库实现证据并与一个规范化 construct 候选关联，不另建第二个用户 pthread ThreadInstance

#### Scenario: A call leaves the verified boundary
- **WHEN** wrapper 调用未知函数、参数逃逸或控制流超出模型摘要
- **THEN** 保存已知边界、调用与 frontier，相关生命周期降为 partial/unknown

### Requirement: Version and invalidate profile models conservatively

标准库 profile、模型注册表和采用结果 SHALL 进入请求、依赖、缓存和报告 identity；注册项更新、工具链/头文件/target/ABI 变化或模型预算变化 MUST 使旧采用缓存失效。系统 MUST NOT 把未安装、未实测或只有合成 fixture 的 profile 报告为已支持。

#### Scenario: The development image upgrades its standard library
- **WHEN** libstdc++/libc++ 版本或关键头文件 digest 与旧 acceptance 不同
- **THEN** 旧 profile cache 失效，必须重新提取、验证和记录 truth 后才能标为 supported

#### Scenario: libc++ is unavailable during acceptance
- **WHEN** 环境无法安装或实际编译验证要求的 libc++ profile
- **THEN** libc++ required gate 保持未完成并记录阻塞，不以合成 schema 测试宣称支持
