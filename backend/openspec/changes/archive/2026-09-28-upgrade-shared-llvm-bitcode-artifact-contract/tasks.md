## 1. 协议与测试向量

- [x] 1.1 定义 `SharedLlvmBitcodeArtifactSet@2.0` JSON Schema、枚举、bundle 布局和协议说明，明确顶层、planned record、produced/missing/failed、scope、profile、通用 capability、typed sidecar、producer host、target、DataLayout、ABI、多 profile 计数及安全字段。
- [x] 1.2 增加 v2 有效/无效 fixture 与 canonical identity 测试向量，覆盖 READY、PARTIAL、FAILED、路径安全、重复成员、计数和哈希不一致。
- [x] 1.3 定义 source identity、raw compile database hash、normalized compile context、physical TU ID、context ID、artifact key 和 artifact-set ID 的 UTF-8 canonical JSON 算法，并固定多 profile、sidecar、排序和路径规范化规则。
- [x] 1.4 编写浮点精度与 `memory-order-analyzer` 消费者兼容矩阵和字段映射，明确后者 ExternalBitcodeBundleManifest/ArtifactRecord 所需 planned 分母、scope、producer、target、language/standard、optimization/debug、module kind、source/compile/input digests 及内部 ArtifactKey 边界。

## 2. 后端协议模型与校验

- [x] 2.1 将现有共享 BC Java manifest 模型升级为 v2，并增加 schema version、producer、source/compile context identity、planned record、typed sidecar、scope、双语 failure diagnostic 和 legacy 摘要模型。
- [x] 2.2 实现可复用 canonical identity 组件，使用测试向量验证 Java 计算结果稳定且不包含 generated at、诊断文本、bundle 哈希或 RvPort 业务主键。
- [x] 2.3 升级 manifest 和 bundle 校验器，验证 JSON Schema、身份、计数、相对路径、成员唯一性、size/hash、声明文件集合、归档类型及资源预算。
- [x] 2.4 确保校验器拒绝绝对路径、父目录/反斜杠逃逸、符号链接、硬链接、设备文件、重复条目、未声明文件和损坏归档，并保持真实构建状态隔离。

## 3. 远端 v2 生产

- [x] 3.1 升级 `produce_bitcode.py`，规范化 `compile_commands.json` 与 response file 上下文，生成 source identity、raw hash、normalized digest、稳定 TU/record 身份和完整 produced/missing/failed 计划分母。
- [x] 3.2 为 produced record 写入 production compiler、BC producer/host、source hash、compile/input digests、language/standard、optimization/debug、module kind、target triple/DataLayout/ABI、`source-preserving@1`、通用 capabilities、相对路径、大小与 SHA-256；为 missing/failed 写入稳定 reason code 和双语脱敏诊断。
- [x] 3.3 保持每 TU/每 profile 独立 raw module，支持同一 context 的多 profile 身份和可选 source-binding/symbol-index sidecar，不默认预链接全部 BC；无法证明 closed scope 时按 target triple 生成覆盖全部计划 records 的开放 fallback scope。
- [x] 3.4 按固定 bundle 布局生成 `manifest.json`、record、`bitcode/<record_id>.bc`、scope 和声明的 sidecar，并保证新构建不再写入 v1 manifest。
- [x] 3.5 增加 Python 协议单元测试，并使用同一测试向量验证 Python 与 Java 的 canonical identity 完全一致。

## 4. 构建事实、存储与查询兼容

- [x] 4.1 更新 BC 后处理和 `StoredArtifactService` 元数据，保存 v2 schema、artifact-set ID、source identity digest、compile context digest、外部 bundle SHA-256 和安全摘要，业务关联只保留在数据库中。
- [x] 4.2 更新 `build_runs.build_facts.bitcode` 与构建列表、详情、latest DTO 映射，返回 v2 安全摘要及 `legacy=false`，不得返回完整 manifest、对象存储位置或真实路径。
- [x] 4.3 为历史 v1 摘要实现只读 `legacy=true` 映射，v2-only digest 返回 `null`；无 BC 字段记录继续映射为 `NOT_ATTEMPTED/LEGACY_RECORD`。
- [x] 4.4 验证对象存储失败、部分上传、重试和同 owner/type 幂等行为不会产生可查询的残缺制品，也不会改变真实构建结果。

## 5. 单元测试与覆盖率门禁

- [x] 5.1 使用 mock 的 SSH/SFTP、对象存储、数据库和进程返回值补齐正常流程测试，覆盖稳定 v2 生产、READY/PARTIAL、存储和 API 摘要。
- [x] 5.2 补齐异常流程测试，覆盖 schema/identity/hash/计数错误、损坏 bundle、对象存储失败、producer 异常和主构建隔离。
- [x] 5.3 补齐边界测试，覆盖零计划、部分 produced、最大预算、重复/排序、Unicode 与路径规范化、多 profile、typed sidecar、开放/闭合 scope、跨 TU linkage、producer-host/target 冲突、provenance 缺口、历史 v1、无 BC 字段及 source-preserving capability 边界。
- [x] 5.4 使用真实 `memory-order-analyzer` external-bitcode schema fixture 验证 v2 到 bundle/record/scope 的确定性映射，确保 planned failure 不丢失且平台 artifact key 不被当作分析器内部 ArtifactKey。
- [x] 5.5 运行项目完整单元测试和覆盖率统计，确保未加载源码纳入统计，项目整体与受影响模块行覆盖率及可用分支覆盖率均至少为 90%；保存并报告覆盖率报告路径。

## 6. 真实验证与文档

- [x] 6.1 重新构建 backend/worker 镜像，在真实 source/x86 项目通过 API 执行构建，验证新制品为 v2、BC 仍为构建非阻断副产物且不需要独立扫描容器或 `docker.sock`。
- [x] 6.2 下载真实 manifest 和 bundle，核对 planned records、source/compile/input identity、producer host、target/DataLayout/ABI、language/standard、optimization/debug、module kind、scope/profile/capabilities、atomic/fence 等内存序信息、浮点信息、哈希、计数、相对路径、MinIO 元数据和敏感路径清理。
- [x] 6.3 对同一输入重复构建验证稳定身份，对编译参数变化验证 compile context 与 artifact-set identity 变化，并检查历史 v1 构建查询兼容。
- [x] 6.4 更新后端开发文档与共享 BC 协议说明，明确后续 Worker 内扫描工具的消费边界以及 resolver/materializer 不属于本 change。
- [x] 6.5 运行 `openspec validate upgrade-shared-llvm-bitcode-artifact-contract --strict --no-interactive`、格式和链接检查，全部通过后才标记实现完成。
