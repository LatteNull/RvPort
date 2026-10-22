# KB Scanner Containerized Toolchain Specification

## Purpose

定义 KB Scanner 技术候选在独立测试容器中的依赖锁定、可复现验证、运行隔离和无副作用边界，并明确该测试环境不得修改或替代生产镜像定义。

## Requirements

### Requirement: 扫描器依赖必须在容器内安装和验证
KB Scanner 的 Python、原生解析器和测试依赖 SHALL 在容器镜像构建过程中安装并锁定，正式构建和验证流程 MUST NOT 要求修改开发者宿主机的 Python 或系统工具环境。

#### Scenario: 开发者构建扫描器测试环境
- **WHEN** 开发者需要安装或更新 Tree-sitter、LLVM/Clang、图存储或模型校验依赖
- **THEN** 依赖 SHALL 通过 Docker build stage 安装
- **AND** 开发者宿主机 MUST NOT 执行对应的 pip、npm 或系统包安装命令

#### Scenario: 宿主机没有分析器依赖
- **WHEN** 宿主机仅安装受支持的容器构建和运行工具
- **THEN** 开发者 SHALL 仍能构建并运行 KB Scanner 的正式测试环境

### Requirement: 项目必须提供独立的 kb-scanner-test 容器
项目 SHALL 在 `tools/kb-scanner/Dockerfile.test` 提供名为 `kb-scanner-test` 的独立 image target。项目 SHALL 通过专属 `tools/kb-scanner/compose.test.yml` 将该镜像作为一次性测试容器运行，而 MUST NOT 将测试服务合并到现有根 Compose，也 MUST NOT 为此修改 `backend/Dockerfile` 或生产镜像。

#### Scenario: 运行默认容器测试
- **WHEN** 开发者使用专属 Compose 文件启动 `kb-scanner-test` 容器
- **THEN** 容器 SHALL 运行现有 KB Scanner 单元测试和兼容契约测试后退出
- **AND** 任一必需测试失败 SHALL 产生非零容器退出码

#### Scenario: 独立管理测试生命周期
- **WHEN** 开发者构建、启动、停止或清理 `kb-scanner-test`
- **THEN** 操作 SHALL 只作用于专属测试 Compose project 及其临时资源
- **AND** 现有 Compose 中的 API、worker、数据库、消息队列、缓存和对象存储服务 SHALL 保持不变

#### Scenario: 测试容器保持运行隔离
- **WHEN** `kb-scanner-test` 容器启动
- **THEN** 它 MUST NOT 依赖或加入现有 Compose 的网络和业务卷
- **AND** 它 MUST NOT 获得现有服务的数据库、消息队列、缓存或对象存储凭据

#### Scenario: 验证技术候选
- **WHEN** change 增加 Tree-sitter/Clang、GraphStore、构建解析或 RPM 安全 spike
- **THEN** 对应测试 SHALL 在独立的 `kb-scanner-test` 容器或由其复用的容器依赖环境中执行
- **AND** 选型证据 MUST NOT 依赖宿主机已安装的同名包或命令

### Requirement: 测试依赖必须可复现
`kb-scanner-test` SHALL 从锁定文件和固定原生包版本获得候选 scanner runtime 依赖；测试专用依赖 MAY 在独立层叠加，但 MUST NOT 替代或改变已锁定的 runtime 候选版本。

#### Scenario: 更新扫描器依赖
- **WHEN** 任一扫描器候选依赖版本发生变化
- **THEN** `kb-scanner-test` SHALL 在相同版本上重新运行
- **AND** 版本变更 SHALL 记录兼容性、安全性和许可证影响

#### Scenario: 候选技术进入生产
- **WHEN** 后续工作准备把已验证候选加入生产 worker
- **THEN** 该生产接入 SHALL 由独立 change 定义和验证
- **AND** 本 change 的测试 Dockerfile MUST NOT 被视为生产镜像定义

### Requirement: 容器化不得放宽不可信代码执行边界
即使分析依赖已安装在容器内，默认 KB Scan 仍 MUST NOT 执行不可信项目中的 Make、M4、RPM、CMake、编译器插件或其他任意命令路径。

#### Scenario: 扫描包含命令执行构造的项目
- **WHEN** Makefile、Autoconf、RPM spec、CMake 或 compilation database 包含可能执行外部代码的构造
- **THEN** scanner SHALL 将其作为静态 Evidence、unsupported expression 或 diagnostic 处理
- **AND** scanner MUST NOT 执行该构造

#### Scenario: 未来需要完整求值
- **WHEN** 后续能力必须执行项目配置或宏求值才能获得结果
- **THEN** 该能力 SHALL 由独立 change 定义无业务凭据、受限网络、只读输入和资源限制的一次性沙箱
- **AND** 普通容器本身 MUST NOT 被视为充分的执行隔离

### Requirement: 知识生产和数据验证必须在独立测试容器中执行
新增 source extractor、curation validator、schema/lint、deterministic renderer、Provider 和 matcher 的正式验证 SHALL 只在 `kb-scanner-test` 镜像环境中执行。宿主机 MUST NOT 安装或执行其 Python、parser 或 toolchain 依赖，生产镜像和根 Compose MUST NOT 因知识采集而修改。

#### Scenario: 验证知识生产模块
- **WHEN** 开发者运行 extractor、curation 或数据质量测试
- **THEN** 测试 SHALL 通过专属 `compose.test.yml` 使用锁定环境和最小只读上游 fixture
- **AND** 任一 unit coverage、schema、provenance、hash 或 determinism gate 失败 SHALL 返回非零状态

#### Scenario: 刷新真实知识数据
- **WHEN** 维护者从固定上游修订刷新 generated 或 curated source
- **THEN** extractor SHALL 在同一测试镜像依赖环境中读取显式提供的只读 source root/archive
- **AND** 它 MUST NOT 依赖宿主机 compiler、assembler、linker 或 Python package

#### Scenario: 运行默认扫描测试
- **WHEN** `kb-scanner-test` 验证提交后的知识和 scanner
- **THEN** 容器 SHALL 保持无业务凭据、与根 Compose 隔离且不执行被扫描项目代码
- **AND** 知识 Provider MUST NOT 因数据刷新能力而获得运行时网络或 subprocess 权限

### Requirement: 测试容器必须验证 Tree-sitter 原生兼容与 Point 禁用合同
独立 `kb-scanner-test` 容器 SHALL 记录并验证 Python binding、C grammar 与 C++ grammar 的锁定版本和 ABI 元数据，且 SHALL 运行能够证明正式 Scanner 路径不读取 Node `start_point`/`end_point` 的自动化测试。版本或 ABI 范围验证 MUST NOT 替代真实解析回归。

#### Scenario: grammar ABI 超出 binding 支持范围
- **WHEN** C 或 C++ grammar ABI 不在当前 binding 声明的支持范围内
- **THEN** 测试容器 SHALL 在执行扫描回归前以非零状态失败
- **AND** 输出 SHALL 标识 binding、grammar package 版本和 ABI 值

#### Scenario: 正式代码读取 Point
- **WHEN** 普通 Evidence、宏、枚举 guard、ERROR 或 MISSING 处理路径尝试读取 fake Node 的 Point getter
- **THEN** 对应隔离单元测试 SHALL 失败
- **AND** 该测试 SHALL 只在 `kb-scanner-test` 环境运行而不向宿主机安装依赖

#### Scenario: 仅版本校验通过
- **WHEN** binding 与 grammar ABI 元数据相容但真实项目回归崩溃、超时或产生失控 Evidence
- **THEN** 完整容器门禁 SHALL 仍以非零状态失败

### Requirement: 三个固定真实项目必须形成进程级崩溃回归
`kb-scanner-test` SHALL 对 cJSON `fb16e5cf358798aabb049655975cde8427101056`、zlib `e3dc0a85b7032e98380dec011bc8f2c2ee0d8fca` 和 libarchive `c4cfba676d2b86d6a2a7c508cd90a75c4dfaa1d9` 的许可合规只读 fixture 运行 Scanner 进程级回归。测试 SHALL 固定来源、修订和 provenance，MUST NOT 在运行时联网或执行项目的配置、编译、链接或测试。

#### Scenario: 扫描三个无 compilation database 的项目
- **WHEN** Scanner 仅使用 Tree-sitter baseline 扫描三个固定 fixture
- **THEN** 每个 Scanner 子进程 SHALL 正常退出且不得返回信号退出或 exit code 139
- **AND** 每个结果 SHALL 生成可解析的 `scan-result.json`、`scan-report.html` 和 `scan.log`

#### Scenario: 验证宽泛选择误采集
- **WHEN** fixture 包含 cJSON 的字符 case、zlib 的状态分支或 libarchive 的数字 case
- **THEN** 这些没有可验证 enum member binding 的节点 MUST NOT 产生 selection Evidence 或架构枚举链路
- **AND** 固定的真实架构 enum 正例 SHALL 继续产生 declaration、member、reference 和 condition 链路

#### Scenario: 回归性能与证据规模
- **WHEN** 三个真实项目回归在目标测试容器中运行
- **THEN** 每个扫描 SHALL 满足仓库固定的宽松墙钟预算和确定的 Evidence 数量上限
- **AND** 超时、持续高 CPU、未处理文件或恢复全 condition/case 采集 SHALL 使门禁失败

#### Scenario: 验证版本化输出兼容
- **WHEN** 真实项目先使用默认 schema 再显式请求 V1
- **THEN** 默认结果 SHALL 为 Schema V2，显式请求 SHALL 产生兼容 V1，且二者沿用现有三类 artifact 与状态语义
- **AND** 测试 MUST NOT 要求任何后端变更或第二个主结果文件

### Requirement: 原生崩溃修复必须具备逐模块隔离覆盖门禁
为本 change 新增或修改的源位置、Tree-sitter adapter 与 enum selection 业务模块 SHALL 在测试清单中逐项映射到隔离单元测试，并 SHALL 在独立 `kb-scanner-test` 容器中达到每模块至少 90% 行覆盖率和 80% 分支覆盖率；组件、真实项目或端到端测试 MUST NOT 代替该门禁。

#### Scenario: 新增源位置模块
- **WHEN** 实现新增或拆分 byte-offset 位置索引模块
- **THEN** 测试清单 SHALL 映射其空输入、LF/CRLF、UTF-8、EOF 和无效范围单元测试
- **AND** 缺失映射或覆盖率不足 SHALL 返回非零状态

#### Scenario: 修改 adapter 与枚举选择逻辑
- **WHEN** Tree-sitter adapter 移除 Point 访问并收紧 selection Evidence
- **THEN** 隔离单元测试 SHALL 使用 fake parser/Tree/Node 覆盖正常、partial、ambiguous 和异常分支
- **AND** 第三方 parser、文件系统和下游投影边界 SHALL 被 fake/mock，不得以真实项目测试替代

#### Scenario: 运行完整兼容回归
- **WHEN** 隔离覆盖门禁通过
- **THEN** 同一测试容器 SHALL 继续运行现有 AVX、Frontend、Evidence Graph、Detector、V2 默认、V1 兼容和 artifact 合同回归
- **AND** Clang/GCC 两份生成事实 JSON SHALL 分别保持既有 SHA-256 `ADF187416C006B120E43F2D2CE0677EE2104A4C27DE4DD9CABD1DF12ADD352F7` 与 `89775341EE880B13AC4F10A30558FF5D52875B25A3233114A5765601F0A9DAD9`
