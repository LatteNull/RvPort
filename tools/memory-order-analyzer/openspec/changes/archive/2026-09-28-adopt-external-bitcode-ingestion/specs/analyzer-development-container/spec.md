## MODIFIED Requirements

### Requirement: Pin and verify the analysis toolchain
项目 SHALL 继续锁定开发构建、测试和覆盖率所需的 Clang/LLVM SDK 及依赖，但运行时 readiness MUST 按职责拆分：外部 BC ingestion 只核对 LLVM reader/worker、ModuleFacts 协议和必要运行库；可选 AST 路径单独核对 source worker；开发/质量环境另行核对 compiler、llvm-cov 和构建工具。纯 ingestion MUST NOT 因 GCC、Clang driver、opt、llvm-link 或覆盖率工具缺失而报告不可用，且生产路径不得调用这些工具生成或转换 BC。

#### Scenario: Reader is ready without compiler drivers
- **WHEN** 运行环境具有匹配协议的 reader/worker，但没有 GCC、Clang driver、opt 或 llvm-link
- **THEN** external ingestion readiness 通过，开发/AST/coverage readiness 可分别报告未就绪

#### Scenario: Worker protocol does not match
- **WHEN** reader 使用相同 LLVM 主版本但 ModuleFacts/extractor/policy 协议不匹配
- **THEN** ingestion readiness 非零并给出预期/实际身份，不读取或发布伪兼容 facts

### Requirement: Run isolated development and quality checks
开发容器 SHALL 支持非 root、只读被分析源码和外部 bundle、独立可写构建/缓存/报告目录；质量入口 SHALL 不依赖网络、SSH、DevKit、特权模式或 Docker socket。测试 MAY 在调用产品 CLI 前使用锁定 Clang 预生成 fixture BC，但 SHALL 将 fixture preparation 与产品进程隔离，并验证 ingestion/index/P1–A6/R1–R3 不执行 compiler、dependency generator、llvm-link、configure/build 或目标程序。

#### Scenario: Validate inside the built image
- **WHEN** 在已构建镜像中使用全新输出目录运行项目质量入口和 ingestion/index 冒烟测试
- **THEN** 编译项目本身、单元测试、覆盖率门槛和独立集成实际执行；产品冒烟只读取预生成 bundle，报告写入输出目录且不修改源码/bundle

#### Scenario: Fixture bitcode is prepared for an integration test
- **WHEN** 集成 harness 需要真实 C/C++ BC
- **THEN** harness 在产品 CLI 启动前记录并完成 fixture 编译，后续受审计产品 argv 只包含 worker/reader操作
