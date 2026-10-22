## Context

依赖分析当前从构建命令、`compile_commands.json`、`strace execve` 和环境快照中提取工具依赖。对于 `demo-test1`，源构建真实执行 `/usr/bin/c++`，源快照确认其 provider 为 `gcc-c++`；目标环境仅安装 `gcc`，但仓库提供 `gcc-c++`。现有 `c++ -> g++ -> clang++ -> gcc` 别名链在目标匹配阶段命中了已安装的 `gcc`，产生 `TARGET_INSTALLED/LOW`，掩盖了目标缺少 C++ 编译驱动的事实。

当前实现还存在两项结构性问题：源 provider 在目标匹配完成后才被读取，因此无法参与决策；工具别名规则在 extractor 和 target index 内重复定义，容易发生行为漂移。修复必须保持现有 API schema，不把编译器宏采样误当作构建使用证据，并确保一键修复仍可从仓库可用的软件包结果派生候选。

## Goals / Non-Goals

**Goals:**

- 准确区分实际执行工具、所需编译能力和 provider package。
- 使用源环境采集到的 provider package 优先判断目标已安装或仓库可用状态。
- 禁止裸 `gcc` 满足 C++ 编译驱动需求，并按源侧编译器家族限制等价工具。
- 保留实际观测名称 `c++`，同时正确返回 `gcc-c++` provider 和 `REPO_AVAILABLE/MEDIUM`。
- 统一 compile database、execve summary、execve tool 和文本工具提取的匹配行为。
- 通过隔离外部连接的单元测试、真实 API E2E 和至少 90% 覆盖率验收修复。

**Non-Goals:**

- 不新增依赖分析 API 字段，也不修改前端展示。
- 不把环境中可执行的宏采样工具自动视为构建实际依赖。
- 不重新设计所有发行版之间的软件包别名；仍遵循源和目标属于同类发行版的既有前提。
- 不自动修改历史分析结果；修复后的结果通过重新运行依赖分析生成。

## Decisions

### 1. 以实际工具为展示事实，以 provider package 为目标解析依据

依赖条目的 `dependencyName` SHALL 保留构建证据中的真实工具名，例如 `c++`。源侧 `toolEvidence` 解析出的 `sourceProviderPackage=gcc-c++` SHALL 在目标匹配前传入匹配器，用于查找目标已安装包和仓库包。

不把 `dependencyName` 强行改成 `g++`，因为 CMake 和 execve 实际记录的是 `/usr/bin/c++`；provider 字段负责表达安装单元。该方案不需要增加新的中英文字段，也不会破坏现有 API DTO。

### 2. 采用“严格工具、同家族等价工具、源 provider package”的匹配顺序

目标匹配顺序为：

1. 完全同名的目标工具；
2. 与源 provider 家族一致的等价工具；
3. 同名源 provider package 的已安装记录；
4. 同名源 provider package 的仓库记录；
5. 无可靠 provider 时才使用保守别名；
6. 均未命中则返回 `MISSING` 或既有快照不可用状态。

GCC C++ 家族允许 `c++` 与 `g++` 互认，并映射到 `gcc-c++`；Clang C++ 家族允许 `c++` 与 `clang++` 互认，并映射到对应 Clang provider。`gcc` 不属于 C++ 驱动等价工具，MUST NOT 满足 `c++` 或 `g++`。

备选方案是仅从别名列表移除 `gcc`。该方案能修复当前误判，但无法利用已采集的 `gcc-c++` provider，目标仓库明明有包时仍可能返回 `MISSING`，因此不采用。

### 3. 统一工具匹配规则的单一来源

重复的 `toolAliases` 规则 SHALL 收敛到单一实现，并由源 provider 解析和目标能力匹配共同使用。compile database、execve summary、execve tool 和文本工具检测 SHALL 调用同一匹配入口，避免不同证据产生矛盾状态。

### 4. 保持风险映射和一键修复契约

修复沿用现有风险映射：目标已安装为 `TARGET_INSTALLED/LOW`，目标仓库可用为 `REPO_AVAILABLE/MEDIUM`，目标无匹配为 `MISSING/HIGH`。当目标仓库存在 `gcc-c++` 时，`targetProviderPackage` 和版本 SHALL 指向 `gcc-c++`，使现有一键修复候选逻辑无需新增分支即可工作。

### 5. 宏采样只用于宏分类

`compilerBuiltinMacros g++` 只证明采集时该工具可执行，不证明项目构建使用了它。修复 SHALL 继续仅从构建命令、compile database 和 execve 证据创建工具依赖，防止把环境工具清单扩散成项目依赖。

## Risks / Trade-offs

- [源快照缺少 provider 元数据时无法准确确定 GCC 或 Clang 家族] → 回退到严格同名工具和保守别名，不再使用 `gcc` 这类能力不足的替代项，并降低置信度。
- [部分发行版的 C++ provider 包名不是 `gcc-c++`] → 优先使用源快照真实 owner package，不硬编码跨发行版包名；本变更不承诺跨发行版映射。
- [同一工具由多个证据重复发现] → 保持现有按依赖类型和工具名去重，并验证高置信度 execve/compile database 证据优先。
- [历史结果仍保留误判状态] → 不迁移历史审计数据；用户重新运行依赖分析后产生新结果，既有当前输入刷新机制负责替换当前轮输入。
- [收敛重复别名方法可能影响 `cc`、binutils 等既有工具] → 为既有 C 编译器、binutils、ninja、rpmbuild 和 configure 别名增加回归测试。
