## 1. 固化范围与实验依据

- [x] 1.1 核验 ARM 原始包及代表文件 hash，将环境、命令、源码和代表报告子集迁入本项目证据目录，保存原始与派生文件来源，不依赖在线 SSH。
- [x] 1.2 更新 DevKit 实测文档、构建适配范围和 openspec/config.yaml：保留历史阻塞日期，纳入 47 份报告的正确含义，明确 GCC/Clang、当前独立开发容器和后续生产合并边界。
- [x] 1.3 创建 requirement/scenario 到测试用例的验收映射，列出全部自有执行代码及覆盖率模块划分，明确现有 probe_bc.py 纳入统计。

## 2. 独立开发容器与构建骨架

- [x] 2.1 验证 LLVM 21 候选发行可获取且编译/reader/SDK 可协同使用，锁定具体版本、基础镜像 digest、依赖来源/校验信息与许可证；若不能满足先记录并更新设计，不假定已兼容。
- [x] 2.2 在本项目创建 Dockerfile.dev、.dockerignore 和依赖锁定文件，安装 GCC/G++、同发行 Clang/LLVM SDK/工具、Python、CMake/Ninja 和测试工具，不引用兄弟镜像或修改生产 Dockerfile。
- [x] 2.3 建立 C++20 CMake 库/worker 与 Python 包骨架，配置容器内非 root、只读源码和可写输出路径；新增启动/路径逻辑的单元测试。
- [x] 2.4 实际构建独立开发镜像，验证 GCC/Clang 的 C/C++ compile-only 和同版本 LLVM 读取/校验，记录镜像 ID、工具版本、命令及结果，不运行并发样例。
- [x] 2.5 实现 doctor 版本/路径/工具链一致性检查及单元测试，覆盖缺工具、发行不匹配、探测失败和正确环境。

## 3. 数据契约与受限执行基础

- [x] 3.1 定义 BuildSnapshot、TUManifest、BCArtifact、ModuleFacts、ScopeManifest、ScopeIndex 和 RunReport 的版本化 schema 与字段说明。
- [x] 3.2 实现契约校验、确定性序列化、身份引用和错误分类，单元测试缺字段、未知版本、非法引用及重复序列化稳定性。
- [x] 3.3 实现不经 shell 的 argv runner、工作目录/环境白名单、输出限额和超时进程组终止，单元测试成功、非零、超时、超量日志和启动失败。
- [x] 3.4 实现任务临时目录、原子发布及范围受限的残片处理，单元测试异常中断、路径越界和已有用户文件不被覆盖。

## 4. GCC/Clang 编译上下文

- [x] 4.1 实现编译数据库结构校验与 arguments 优先规则，补充多记录、空输入、缺 file/directory、非字符串参数等单元测试。
- [x] 4.2 实现受支持 POSIX command 拆分、驱动/wrapper 识别及响应文件展开，单元测试引号/空格、递归/大小限制和 shell 语义/MSVC/未知 wrapper 拒绝。
- [x] 4.3 实现生产驱动版本、默认配置、GCC 安装/sysroot/SDK 和相关环境探测，补充超时/缺工具/隐式头文件路径测试，避免批量泄露环境信息。
- [x] 4.4 实现有序参数适配和逐项保留/转换/移除/不支持日志，单元测试 -D/-U、include 顺序、目标/ABI、优化/LTO、未知语义参数和原输出参数隔离。
- [x] 4.5 实现 CompileContextId 与原记录映射，单元测试条目重排稳定、同源码不同配置不覆盖、相同重复记录去重和外部同 basename 路径不碰撞。
- [x] 4.6 实现同配置依赖发现、ArtifactKey 与保守缓存校验，单元测试普通/系统头变化、响应文件变化、新 include 遮蔽、SDK 未锁定及输入变动重试失败。

## 5. BC 生成与读取

- [x] 5.1 实现 collect 的 source-preserving/build-faithful compile-only profiles，单元测试选项与产物身份分离，不执行原生链接和目标程序。
- [x] 5.2 实现成功产物校验、计数和缓存发布；测试退出 0 但无文件、空文件、编译失败、残片和缺生成头文件，失败 TU 留在计划集合。
- [x] 5.3 基于 LLVM API 实现 BC parse/verify worker 和 import-bc，单元测试无效格式、verify 失败、target/layout 与 manifest 不符、来源缺失及 reader 错误。
- [x] 5.4 实现模块、函数、全局声明/定义、linkage、CFG 和调用事实；单元测试重载、内部符号、直接调用、间接调用及确定性身份。
- [x] 5.5 实现 load/store、volatile/atomic、RMW、CAS 双 ordering/weak、fence syncscope、内存 intrinsic 事件和有限地址表达；为每种语义及 unknown/opaque effect 提供单元测试。
- [x] 5.6 实现 debug/inline 链读取、源码 hash 校验与映射降级，单元测试无 debug 仍保留 IR 事件、源码不符、系统头路径和同一行多个事件。
- [x] 5.7 验证 O0 C++ atomic 包装的调用/CFG 原始事实和能力声明，不做未经实现的调用点特化，测试不同 profile 不被合并为执行证据。

## 6. 目标范围与跨 TU 基础关联

- [x] 6.1 实现 scope manifest 校验、ScopeId 和成员索引，单元测试缺范围、不同目标隔离、成员变更与输入去重。
- [x] 6.2 实现范围内唯一强符号的直接调用/全局引用绑定，单元测试跨模块 extern、同名 static、C++ 重载、缺函数体和重复强定义。
- [x] 6.3 为 weak/COMDAT/ifunc、间接调用、未知指针及动态/归档边界输出候选/unknown，测试不会猜唯一目标或清空影响，且能力声明不包含函数效果/线程分析。
- [x] 6.4 实现显式范围 llvm-link 适配、兼容性预检、输出 verify 和 lineage，测试 target/layout/互斥配置冲突、链接失败及 object/linked 重复来源拒绝。
- [x] 6.5 实现按 ScopeId/成员内容/索引版本的索引失效，单元测试只改范围时更新绑定而不无条件重编译 TU。

## 7. CLI 与完整性报告

- [x] 7.1 串联 doctor、collect、import-bc、index、link 公共入口，单元测试参数、机器输出与 stderr 日志分离、schema 不兼容和失败报告。
- [x] 7.2 实现 build/IR/source/scope 分层状态和完整计划集计数，单元测试部分失败、零分母、缓存命中、映射缺失及来源未知。
- [x] 7.3 实现退出码 0/2/1 约定和操作级完整性判定，测试部分成功返回 2、全失败返回 1、未请求 scope 的 collect 不被误判为已解析全程序。
- [x] 7.4 保证本阶段所有报告 semantic_analysis=not_run、safety=not_evaluated、findings=null，测试成功编译/零事件不能输出安全结论。

## 8. 单元测试覆盖率门槛与集成验收

- [x] 8.1 为现有 probe_bc.py 自有逻辑补充单元测试，必要时做保持语义的可测性重构，覆盖失败、超时、产物和固定探针断言；不改历史 evidence.json 或将正则迁为生产 reader。
- [x] 8.2 接入 GoogleTest/llvm-cov 和 pytest/coverage.py branch 统计，枚举全部自有源文件并分离单元/集成 profile，测试未加载文件仍在统计范围。
- [x] 8.3 实现全项目、每种语言及受影响模块 >=90% 行/分支门槛与 JSON/HTML 汇总；单元测试 89.99/90、分支不足、报告缺失、非法排除及计数合并逻辑。
- [x] 8.4 增加 GCC/Clang × C11/C17/C++17/C++20 的编译数据库集成夹具，以及真实多物理文件的调用/extern/static/重载/配置隔离和 object/linked 对照。
- [x] 8.5 增加完整性回归：缺头、零退出无产物、无 debug、源码变更、无效/不兼容 BC、未知调用、超时和缓存遮蔽；以 schema/事实/状态为断言，不以 DevKit 屏障建议为正确性真值。
- [x] 8.6 在本 change 构建的开发镜像中从干净输出目录实际运行完整单元测试、覆盖率门槛及离线集成测试，记录命令、镜像 ID、测试数、全项目/模块行分支覆盖率和报告路径；任何失败不勾选验收完成。

## 9. 文档与交付核验

- [x] 9.1 更新项目 README、doc 索引、构建上下文、BC 流水线、跨 TU 和 DevKit 文档，区分历史实验、当前已完成基础设施和未来判定能力，删除过时的统一“DevKit 未验证”当前状态但保留历史段落。
- [x] 9.2 增加开发容器、CLI/schema、scope manifest 和测试/覆盖率复现说明，明确 Dockerfile.dev 当前已交付、生产合并另立 change，检查所有本地链接与证据 hash。
- [x] 9.3 核对所有 requirement/scenario 的实施及测试映射、严格 OpenSpec 校验、改动范围与归档项目隔离；汇总未支持项及真实验收结果，只有全部通过后提示 sync/archive 命令。
