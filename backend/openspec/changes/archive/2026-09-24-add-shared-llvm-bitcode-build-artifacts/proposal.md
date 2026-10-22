## Why

浮点精度扫描和强弱内存序分析都需要 LLVM bitcode，但如果各分析节点独立生成 BC，会重复编译源码、形成不一致的工具链和制品身份，并增加远端依赖缺失导致的失败。x86 构建环境已经具备真实构建依赖、生成头文件和构建目录，因此应在 x86 构建成功后以非阻断副产物方式统一生成、回收并保存共享 BC，供后续分析复用。

## What Changes

- 在 source/x86 远端构建成功并收集到 `compile_commands.json` 后，使用 RvPort 锁定的 Clang/LLVM 工具链执行 compile-only BC 后处理。
- 增加远端托管 LLVM 工具链的探测、版本校验、按环境工作目录部署和缓存；默认不修改系统软件源、不安装系统 RPM/DEB，也不覆盖用户已有编译器。
- 为每个可识别的 C/C++ 翻译单元生成独立、保留源码位置的 BC，并生成版本化、中立的 artifact-set manifest；单个翻译单元失败不阻断其他翻译单元。
- 将 manifest 和 BC bundle 作为 `BUILD_VALIDATION` 所有的受控制品回收到对象存储，并在构建事实中保存安全摘要与制品引用。
- BC 生成结果采用 `NOT_ATTEMPTED`、`READY`、`PARTIAL`、`FAILED`、`UNSUPPORTED` 状态；任何 BC 状态都不得覆盖或改变真实 x86 构建的成功或失败。
- 扩展构建列表、详情和 latest 响应，返回 `bitcode.available`、状态、成功/失败翻译单元数量、工具链版本、失败原因和 artifact-set 引用摘要，供前端展示。
- 后续分析节点可以校验并复用共享 BC；BC 缺失、部分成功或失败时允许分析器降级，不把 BC 设置为分析 readiness 的强制前置条件。
- 补充正常流程、异常流程、边界条件、路径安全、缓存复用、部分成功和非阻断语义的单元测试，并维持项目整体及受影响模块至少 90% 的行/分支覆盖率。

## Capabilities

### New Capabilities
- `shared-llvm-bitcode-artifacts`: 定义远端托管 LLVM 工具链、逐翻译单元 BC 生成、版本化 manifest、bundle 回收、对象存储、完整性校验、缓存复用和消费者降级契约。

### Modified Capabilities
- `build-validation-runtime`: x86 构建成功后增加非阻断 BC 后处理，并在构建 API 响应和构建事实中公开 BC 状态摘要。
- `backend-database-design`: 构建事实和 `stored_artifacts` 增加共享 LLVM BC artifact-set 的安全引用、归属和查询约束。

## Impact

- 影响构建验证 handler、构建响应 DTO、构建事实、远端 SSH/SFTP 制品传输、对象存储和归档摘要。
- Backend Worker 镜像或运行资源需要携带可部署的、锁定版本的 x86_64 Clang/LLVM 工具链包及其校验信息。
- 远端 source/x86 环境工作目录会增加 `.rvport/toolchains` 缓存和任务级临时 BC 输出；缓存需要版本隔离、原子发布、并发保护和受控清理。
- MinIO 将保存 manifest 和 BC bundle；数据库只保存安全摘要、计数、哈希和 stored artifact 引用，不保存 BC 二进制或远端绝对路径。
- 后续浮点精度和强弱内存序分析将消费中立 manifest，不直接依赖彼此或构建 handler 的内部实现。
