## 1. 共享契约与配置

- [x] 1.1 定义 `llvm-bitcode-artifact-set.v1` manifest schema、BC 状态枚举、TU 状态、reason code、artifact type 和安全摘要模型，并实现严格 schema/哈希/计数校验。
- [x] 1.2 在 Backend 配置中增加工具链 ID、bundle 路径与 SHA-256、远端缓存相对目录、启用开关、TU/字节/单 TU/总阶段/传输超时等预算，提供安全默认值和启动期配置校验。
- [x] 1.3 扩展 Backend Dockerfile，以可复现方式准备锁定的 x86_64 LLVM/Clang 21.1.8 远端工具链 bundle、版本清单和 SHA-256；不得替换现有 KB Scanner 使用的 Clang 18。

## 2. 远端工具链管理

- [x] 2.1 扩展 SSH 运行时的受控 SFTP 上传与下载能力，支持流式传输、大小限制、超时、取消、临时文件和安全错误分类，不通过 stdout/base64 传输大型二进制。
- [x] 2.2 实现远端 LLVM 工具链缓存探测与完整性校验，覆盖 toolchain ID、架构、bundle SHA-256、必需可执行文件和 `clang --version`。
- [x] 2.3 实现缺失工具链的临时上传、远端 SHA-256 校验、受控解包、并发锁和原子发布；确保不调用系统包管理器且不覆盖用户工具链。
- [x] 2.4 实现损坏缓存隔离、锁等待超时和任务取消处理，并在所有路径保留可审计但不泄露真实路径的 reason code。

## 3. 编译数据库与 BC 生产

- [x] 3.1 实现 compile database 解析和 C/C++ TU 规划器，支持 `arguments`、受控 `command` 拆分、response file、语言识别、路径规范化和远端允许根校验。
- [x] 3.2 实现 C/C++ 编译命令规范化，将 compiler 切换为托管 `clang-21`/`clang++-21`，保留语义参数并加入 source-preserving BC 参数，拒绝 shell 注入和未解释的危险路径。
- [x] 3.3 实现远端逐 TU 隔离执行、超时与取消、非空检查、LLVM verifier、稳定 context/artifact key、SHA-256 和脱敏诊断；单 TU 失败后继续其余 TU。
- [x] 3.4 实现任务级资源预算和 `READY`、`PARTIAL`、`FAILED`、`UNSUPPORTED`、`NOT_ATTEMPTED` 聚合，准确统计 planned/succeeded/failed/skipped/warnings。
- [x] 3.5 生成确定性 `manifest.json`、诊断摘要和 BC bundle，确保排序稳定、路径均为安全相对路径且不包含完整命令、环境变量值或凭据。

## 4. 制品回收与持久化

- [x] 4.1 通过 SFTP 将远端 manifest 和 bundle 下载到后端受控临时目录，校验总大小、归档条目预算、路径穿越、符号链接、重复条目、manifest schema、bundle 哈希和逐 BC 哈希。
- [x] 4.2 使用 `StoredArtifactService` 保存 `LLVM_BITCODE_MANIFEST_JSON` 和 `LLVM_BITCODE_BUNDLE_TGZ`，owner 为 `BUILD_VALIDATION` 和对应 build run，并保证重试和同 owner/type 的幂等性。
- [x] 4.3 将安全 BC 摘要写入 `build_runs.build_facts.bitcode`，处理对象存储失败和不完整上传，确保数据库不保存二进制、完整 manifest、真实路径或 object key。
- [x] 4.4 实现同一 artifact-set identity 的完整性校验与复用、并发单飞和损坏制品拒绝，并在成功、失败、取消和超时后清理远端与本地任务临时目录。

## 5. 构建运行时和 API 集成

- [x] 5.1 在 `BuildValidationHandler` 中仅对当前 source/x86 成功构建执行 BC 后处理，安排构建、compile database、BC 和完成进度阶段，并将整个 BC 流程放入不改变主构建状态的异常边界。
- [x] 5.2 为构建失败、非 source/x86、编译数据库缺失、无 C/C++ TU 和历史记录生成明确的非可用 BC 摘要，不触发重复或无意义编译。
- [x] 5.3 扩展构建列表、详情和 latest 的 `BuildValidationResponse`，统一返回 `bitcode` 安全摘要，并将没有字段的历史记录映射为 `NOT_ATTEMPTED/LEGACY_RECORD`。
- [x] 5.4 更新构建日志、任务进度和必要的 SSE 结果摘要，使前端可区分远端构建与 BC 后处理，同时不暴露远端工作目录、工具链缓存路径和服务器路径。
- [x] 5.5 更新构建归档候选登记，使可用 BC manifest/bundle 作为构建相关报告制品引用被登记，且归档摘要只包含安全聚合信息。

## 6. 单元测试与质量门禁

- [x] 6.1 为 manifest、命令解析/规范化、路径校验、归档校验、状态聚合、reason code 和历史响应兼容补充正常流程、异常流程及 edge case 单元测试。
- [x] 6.2 使用 mock 的 SSH/SFTP、远端进程、对象存储和数据库返回值测试工具链缓存命中、首次部署、损坏缓存、并发锁、取消、超时、预算、READY、PARTIAL、FAILED 和 UNSUPPORTED，不依赖真实外部服务。
- [x] 6.3 增加构建 handler 单元测试，证明 BC 的任意失败不会把退出码为 0 的 x86 构建改为失败，同时构建失败不会被 BC 状态覆盖。
- [x] 6.4 运行受影响模块和 backend 全量单元测试与 JaCoCo，确保项目整体及受影响模块行覆盖率至少 90%，工具支持的分支覆盖率至少 90%，并记录命令、数值、统计范围和报告位置。

## 7. 真实环境验证与文档

- [x] 7.1 在真实 source/x86 环境执行首次工具链部署和缓存命中两轮 API 构建，验证远端不修改系统包、工具链版本一致、BC manifest/bundle 已进入 MinIO 且构建响应返回正确摘要。
- [x] 7.2 使用包含多个 C/C++ TU 和至少一个不可被 Clang 重放条目的项目验证 `PARTIAL`，并模拟工具链、传输和对象存储失败，确认真实 x86 构建仍为 `SUCCEEDED`。
- [x] 7.3 下载真实 manifest 和 bundle，复核源码相对路径、TU 计数、SHA-256、LLVM verifier、无路径泄露和临时目录清理，并保存脱敏验证记录。
- [x] 7.4 更新后端启动、配置和构建验证 API 文档，说明托管工具链缓存、资源预算、BC 状态、非阻断语义及后续分析器的消费边界。
- [x] 7.5 运行 `openspec validate add-shared-llvm-bitcode-build-artifacts --strict --no-interactive`、格式检查和链接检查，所有门禁通过后再标记任务完成。
