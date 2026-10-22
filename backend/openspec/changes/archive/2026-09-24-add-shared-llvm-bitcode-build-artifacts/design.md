## Context

当前 `BUILD_VALIDATION` worker 会先把源码部署到 source/x86 远端环境，执行用户构建脚本，并在成功后收集远端 `compile_commands.json` 到对象存储。Backend 与 Worker 共享本地源码卷，但本地容器不具备远端构建产生的头文件、系统开发包、SDK、sysroot 和构建目录；在本地重放编译数据库会产生大量非源码原因失败。

浮点精度扫描和强弱内存序分析都需要 LLVM BC。两个工具当前均以 LLVM/Clang 21.1.8 为锁定基线，而 Backend 镜像中的 Clang 18 只服务现有 KB Scanner，不能作为共享 BC 的生产工具链。共享 BC 必须是独立于任一消费者的中立构建制品，并保持源码版本、构建上下文和工具链可追溯。

## Goals / Non-Goals

**Goals:**

- 在 source/x86 真实构建目录中复用已经安装的项目依赖和生成文件，统一生产一次可被多个分析器消费的 LLVM BC。
- 由 RvPort 管理锁定版本的 Clang/LLVM 工具链，不默认修改远端系统软件包和软件源。
- 将 BC 生产作为 x86 构建的非阻断副产物，准确表达全部成功、部分成功、失败、不支持和未尝试。
- 使用版本化 manifest、内容哈希和对象存储引用形成稳定、安全、可校验的消费者契约。
- 在重复构建或并发处理中复用经过完整性校验的远端工具链缓存和内容寻址 BC artifact-set。

**Non-Goals:**

- 不在本 change 实现浮点精度或强弱内存序扫描逻辑。
- 不要求 BC 成功才能启动后续分析，也不改变分析 readiness。
- 不把用户项目强制改为使用 Clang 构建，不改变用户真实 x86 构建命令。
- 不默认执行 `llvm-link`，不运行 BC 或项目产物，也不声称独立 TU BC 等价于完整程序。
- 不为远端系统安装或升级 RPM/DEB，不覆盖 `/usr/bin/clang`、`gcc` 或用户工具链。
- 不把远端绝对路径、编译命令全文、环境变量值或 BC 二进制写入数据库。

## Decisions

### 1. 在 source/x86 远端构建成功后生成 BC

生成顺序固定为：源码部署、真实远端构建、收集 `compile_commands.json`、生成共享 BC、回收制品、完成构建任务。BC 后处理使用同一远端部署目录和构建目录，因此可以读取构建产生的头文件、配置文件和已安装开发依赖。

只有当前项目运行环境中的 source 环境且架构为 x86/x86_64 的成功构建才尝试生成 BC。RISC-V 构建、失败构建和没有合法编译数据库的构建分别记录 `NOT_ATTEMPTED` 或 `UNSUPPORTED`，不得额外生成。

选择远端生成而非 Backend 本地生成，是因为复制 `compile_commands.json` 无法复制完整 sysroot 和构建时文件。选择成功构建后处理而非 compiler wrapper，是为了不改变用户真实构建过程和结果。

### 2. 使用 RvPort 托管的锁定 LLVM 工具链

Backend Worker 镜像携带版本化 x86_64 LLVM 21 工具链 bundle、SHA-256 和 manifest。worker 首先探测远端缓存：

```text
<environment.workingDirectory>/.rvport/toolchains/<toolchain-id>/
```

缓存命中必须同时满足目录标记、bundle SHA-256、`clang --version`、目标架构和必需可执行文件校验。未命中时通过受控 SFTP 上传临时 bundle，校验后解包到临时目录，再以原子 rename 发布。并发任务使用原子目录锁；等待超时后本次 BC 生成失败，但不得影响主构建。

默认不调用 `apt`、`dnf`、`yum` 或 `zypper`。这样避免修改用户软件源和系统包，同时保证生产端与消费者的 LLVM 主版本一致。工具链 bundle URL、期望 SHA-256、toolchain ID、远端缓存相对目录和超时可由部署配置覆盖，但响应和日志不得泄露服务器本机路径。

### 3. 逐翻译单元生成 source-preserving BC

生产器解析 `compile_commands.json` 的 `arguments` 或受控拆分后的 `command`，只处理 C/C++ compile entries。每个条目执行以下规范化：

- 将 compiler 替换为锁定的 `clang-21` 或 `clang++-21`；
- 保留宏、include、语言标准、target、ABI、response file 和项目语义参数；
- 移除原输出参数及原 `-c`/`-emit-llvm`，加入 `-emit-llvm -c -g -O0 -Xclang -disable-O0-optnone` 和受控输出路径；
- 不通过 shell 拼接执行，不静默丢弃未知或 GCC 专属语义参数；Clang 不接受时记录该 TU 的安全诊断；
- 输出路径只能位于本次任务远端临时目录，源码、工作目录和 response file 必须经过规范化及允许根校验。

每个 TU 独立执行、校验非空文件并运行 `llvm-dis` 或 `opt -passes=verify` 等价验证。一个 TU 失败不终止其余 TU。首期只生产 `source-preserving` BC；需要复现优化后 IR 时可在后续引入独立标识的 `build-faithful` profile，二者不得混用。

### 4. 发布中立的版本化 artifact-set

全局契约命名为 `llvm-bitcode-artifact-set.v1`，不直接复用浮点扫描器或内存序分析器的内部 schema。artifact-set identity 由以下稳定输入决定：

- source revision ID；
- compile database SHA-256；
- toolchain ID 和 bundle SHA-256；
- producer/schema/profile 版本；
- 规范化 TU 上下文及必要输入摘要。

manifest 包含总体状态、计数、生成时间和每个 TU 的 `contextId`、`artifactKey`、源码相对路径、语言、target、ABI、BC bundle 相对路径、大小、SHA-256、状态与脱敏诊断。它不得包含远端绝对路径、完整命令、环境变量值或凭据。

远端输出形成：

```text
manifest.json
bitcode/
  <artifact-key>.bc
diagnostics/
  summary.json
```

worker 将其打包为 `tar.gz`，通过 SFTP 下载到后端受控临时目录，执行大小预算、条目数量、防路径穿越、manifest/schema、每个 BC 哈希和 bundle 哈希校验后写入 MinIO。数据库通过两个 `stored_artifacts` 保存 `LLVM_BITCODE_MANIFEST_JSON` 和 `LLVM_BITCODE_BUNDLE_TGZ`，owner 均为 `BUILD_VALIDATION` 和对应 `build_runs.id`。

### 5. 主构建状态与 BC 状态完全分离

真实构建退出码唯一决定 `build_runs.status` 和 `exit_code`。BC 生成放在隔离的异常边界中，任何工具链上传、缓存、编译、验证、打包、下载或对象存储异常只更新 `build_facts.bitcode` 并写 warning，不得抛出导致成功构建改为失败的异常。

状态定义：

- `NOT_ATTEMPTED`：真实构建未成功、不是 source/x86 构建或处理被取消前未进入该阶段；
- `UNSUPPORTED`：没有合法 compile database、没有 C/C++ TU 或平台不受支持；
- `READY`：全部计划 TU 成功并已持久化 manifest 和 bundle；
- `PARTIAL`：至少一个 TU 成功、至少一个 TU 失败，且成功制品已持久化；
- `FAILED`：已尝试但没有可消费 BC，或回收/完整性/持久化失败。

`available=true` 仅用于 `READY` 和 `PARTIAL`。构建任务在 BC 后处理达到终态后结束，因此列表、详情和 latest 不会返回悬空的 BC 生成状态；代价是构建任务会比远端构建命令多等待一个后处理阶段。

### 6. API 只公开安全摘要

构建响应新增 `bitcode` 对象，至少包含 `available`、`status`、artifact-set ID、planned/succeeded/failed/skipped 计数、toolchain ID、schema/profile、reason code、warning count 和 generated at。响应不返回 bundle 内容、对象存储位置、远端路径或逐 TU 完整命令。

现有构建列表、详情和 latest 统一通过 `BuildValidationResponse` 映射该字段。旧记录没有 `build_facts.bitcode` 时映射为 `NOT_ATTEMPTED` 和 `LEGACY_RECORD`，无需回填历史 BC。

### 7. 清理与复用边界

每次任务的远端 BC 临时目录在成功、失败、取消和超时后都尽力清理。版本化工具链缓存不随任务删除；后续由独立保留策略清理不再引用的旧版本。对象存储 artifact-set 为不可变制品，消费者只能读取和验证，不得原地修改。

同一 artifact-set identity 已存在且完整性校验通过时可直接复用；损坏、部分上传或版本不兼容的制品不得作为缓存命中。并发相同 identity 通过单飞锁只允许一个生产者，其他请求等待已有结果或在超时后记录失败，不创建互相覆盖的输出。

## Risks / Trade-offs

- [托管 LLVM bundle 可能无法在部分旧 glibc 环境运行] → 启动前探测动态链接和版本；失败记录 `TOOLCHAIN_INCOMPATIBLE`，不修改系统包、不影响构建。
- [GCC 专属参数导致 Clang 重放失败] → 逐 TU 隔离并返回 `PARTIAL`；保留脱敏失败分类，不通过激进删参伪造成功。
- [大型项目产生大量 BC 并延长构建任务] → 设置 TU 数、单文件、总字节、单 TU、总阶段和下载超时预算；计数超限时安全失败或部分完成。
- [远端缓存并发写入或损坏] → 使用原子锁、临时目录、SHA-256 校验和原子发布；损坏缓存隔离后重新部署。
- [对象存储压力增长] → 内容寻址复用、bundle 存储、不可变引用和后续保留策略；数据库不保存二进制。
- [编译数据库路径或压缩包条目越界] → 所有路径规范化后执行允许根校验，下载解包时拒绝绝对路径、`..`、符号链接逃逸和重复条目。
- [构建成功但对象存储暂时不可用] → BC 状态为 `FAILED`，真实构建仍成功；后续可通过重新运行 x86 构建恢复，不虚构可用引用。

## Migration Plan

1. 增加配置项、托管 LLVM bundle、远端传输与工具链缓存组件，但默认仅在 source/x86 成功构建中启用。
2. 增加中立 manifest schema、生成器、校验器和 stored artifact 类型。
3. 扩展 `build_facts.bitcode` 和 API DTO；旧记录按 `LEGACY_RECORD` 兼容读取。
4. 在真实 x86 测试环境验证工具链首次部署、缓存命中、全部成功、部分成功、失败和构建状态隔离。
5. 后续由各分析器单独 change 接入 manifest 消费；本 change 不提前修改其业务结果。

回滚时可关闭 BC 生成配置并保留已生成不可变制品；新增 JSON 摘要对旧应用无破坏性，数据库无需删除历史数据。

## Open Questions

无阻断性开放问题。默认锁定 LLVM/Clang 21.1.8、生产 `source-preserving` BC、使用 `tar.gz` bundle，并允许部署时覆盖工具链来源和资源预算。
