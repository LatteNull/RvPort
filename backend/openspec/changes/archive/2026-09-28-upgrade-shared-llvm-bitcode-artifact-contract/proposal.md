## Why

当前后端生成的 `llvm-bitcode-artifact-set.v1` 与浮点精度扫描工具期望的 BC manifest 在字段、命名、身份计算和校验规则上不兼容，虽然 BC 文件本身有效，后续分析器仍无法可靠复用；`memory-order-analyzer` 已有严格的 `ExternalBitcodeBundleManifest/ArtifactRecord v1` 导入协议，还要求完整计划分母、显式 scope、producer host/target、语言标准、优化/debug、module kind、源码/编译记录/依赖摘要及 provenance 边界。需要先把共享 LLVM BC 定义为平台级、与 RvPort 业务模型及单一分析器解耦的稳定协议，并保证它可以确定性适配浮点精度和强弱内存序两类消费者。

## What Changes

- **BREAKING**：将共享 BC manifest 升级为 `SharedLlvmBitcodeArtifactSet@2.0`，明确版本、状态、producer、计数、成员、失败项及完整性字段。
- 使用 `source_identity_digest` 和 `compile_context_digest` 表达可移植的源码与编译上下文身份；项目 ID、源码版本 ID、构建记录 ID 等 RvPort 业务标识仅保存在数据库制品元数据中，不进入中立 manifest。
- 为每个计划翻译单元统一定义稳定 record/member identity、`physical_tu_id`、`context_id`、平台 artifact key、源码相对路径与摘要、编译记录摘要、输入依赖摘要、producer/production compiler、target triple/DataLayout/ABI、语言标准、优化/debug、module kind、生成 profile、capabilities、大小和 SHA-256。
- 明确 `source-preserving` 与 `build-faithful` profile 的语义、版本及通用能力声明，覆盖浮点指令/fast-math、原子指令/内存序/`syncscope`/fence、debug source mapping、target/data layout 和跨 TU linkage，避免消费者根据隐含编译参数猜测 BC 可用性。
- 允许同一编译上下文发布多个 profile，并提供版本化的通用 sidecar 描述，供源码绑定和跨 TU 符号索引复用；协议不写死浮点或内存序工具的私有字段。
- 保存 produced/missing/failed 全部计划分母，并允许登记显式 target scope、成员、闭合状态和外部边界，使 `memory-order-analyzer` 不通过扫描现存 BC 猜测完整性。
- 明确平台 artifact key 与 `memory-order-analyzer` 内部 `ArtifactKey` 是不同身份域；适配器只传递可验证 record 语义，由分析器按自身 extractor/schema/policy 重新计算内部 key。
- 增加 v2 manifest、bundle 布局、路径安全、计数一致性、哈希完整性和稳定身份的严格校验，并将协议版本和摘要写入现有构建事实与制品元数据。
- 保留历史 v1 构建记录的只读兼容映射；新生成的共享 BC 只发布 v2，不回填或改写历史制品。
- 本 change 不实现分析制品 resolver/materializer、等待唤醒、浮点扫描任务、finding 入库或独立扫描容器；扫描工具未来直接在 `backend-worker` 内运行，不引入 `docker.sock`。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `shared-llvm-bitcode-artifacts`: 将共享 BC manifest、成员身份、profile/capability、bundle 布局和完整性校验升级为中立 v2 协议。
- `build-validation-runtime`: 新生成的构建结果必须返回 v2 协议摘要，并对历史 v1 记录提供稳定的只读兼容状态。
- `backend-database-design`: 数据库继续保存 RvPort 业务关联，同时补充 v2 协议、源码身份和编译上下文摘要，不把业务主键写入中立 manifest。

## Impact

- 影响共享 BC Java 模型、远端 BC 生成脚本、manifest/bundle 校验、构建事实映射、对象存储元数据及相关构建响应。
- 新增平台级 v2 JSON Schema、浮点精度与强弱内存序消费者兼容矩阵和可复用协议示例，后续两个分析器按同一协议消费。
- 不新增数据库二进制存储，不改变真实 x86 构建成败判定，也不要求 BC 成功才能完成构建。
- 单元测试必须覆盖正常、异常和边界路径，mock SSH/SFTP、对象存储及数据库连接返回值；项目整体与受影响模块行覆盖率及可用分支覆盖率均须至少达到 90%。
