## Why

`cJSON`、`zlib` 和 `libarchive` 三个彼此独立的真实 C/C++ 项目都会在 Scanner V2 的公共 Tree-sitter 解析链路中以退出码 139 崩溃。复现表明，崩溃不是项目源码或 libclang 导致的，而是当前 Python 绑定读取 Tree-sitter `Point` 字段时可能破坏原生内存；普通 `case`/条件节点又被无条件采集为架构选择证据，扩大了触发面、证据数量和扫描耗时。因此需要修复公共前端的位置计算与选择证据边界，并用真实项目建立容器化回归门禁。

## What Changes

- 用每个源文件一次构建的字节偏移位置索引统一计算行号和字节列号；生产扫描链路不再读取 Tree-sitter `Node.start_point` 或 `Node.end_point`，并覆盖普通节点、宏范围、`ERROR`/`MISSING` 恢复节点和架构枚举守卫范围。
- 收紧架构枚举与构建选择证据：先识别枚举声明、成员及其引用，仅当 `if`、`if constexpr`、`switch`/`case` 的守卫或分支确实引用已绑定的架构相关枚举成员时才生成选择链路；普通字符、数字和状态机 `case` 不再产生架构选择证据。
- 明确 Tree-sitter 原生对象的所有权与生命周期：解析期间保持 `Tree` 有效，尽早把后续阶段所需数据快照成 Python 自有的基础值和字节范围，避免长期保留任意 `Node` 集合。
- 在独立 `kb-scanner-test` 容器中增加 Tree-sitter/grammar ABI 元数据校验、禁止 Point 访问的单元测试、位置索引边界测试、正反架构枚举测试、错误恢复测试，以及来自三个已固定上游提交的真实项目回归和性能/证据规模门禁。
- 保持现有产品边界：只做 C/C++ 静态分析，不编译、链接或运行被扫描项目，不处理操作系统迁移，也不讨论交叉编译选错分支。
- 保持现有输出契约：Schema V2 仍为默认输出，V1 仅作为显式兼容输出；三类既有产物、状态语义和证据链表达不引入第二套主结果结构，现有 Clang/GCC x86 事实数据保持字节级不变。
- 原生解析器进程隔离不纳入本次紧急修复；它作为后续独立 change，用于把未来不可恢复的原生崩溃降级为文件级部分诊断。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `kb-scanner-cpp-frontends`: 将 SourceSpan/诊断位置改为基于字节偏移的安全计算，收紧架构枚举选择证据的生成条件，并约束 Tree-sitter 原生对象的持有范围。
- `kb-scanner-containerized-toolchain`: 在独立测试容器中增加原生解析依赖兼容性校验，以及固定版本真实 C/C++ 项目的崩溃、正确性、性能和资源回归门禁。

## Impact

- 主要影响 `kb_scanner/frontends/cpp/tree_sitter_adapter.py` 及可能新增的源位置索引模块、对应单元测试和回归夹具。
- 仅在确有验证依据时调整测试容器依赖锁定；`tree-sitter==0.25.2` 只作为应急回退记录，不作为本 change 的目标方案。
- 真实项目回归固定到：cJSON `fb16e5cf358798aabb049655975cde8427101056`、zlib `e3dc0a85b7032e98380dec011bc8f2c2ee0d8fca`、libarchive `c4cfba676d2b86d6a2a7c508cd90a75c4dfaa1d9`，夹具需记录来源与许可证。
- 测试和依赖安装只发生在独立 `kb-scanner-test` 容器；不修改根 Compose、现有生产镜像或宿主机 Python 环境。
- 不修改后端；Schema V2 默认投影、显式 V1 兼容投影和现有三类产物必须通过回归验证。
- `rulesets/riscv-porting/generated/clang-x86-entries.json` 与 `gcc-x86-entries.json` 不修改，并以既有哈希建立防变更检查。
