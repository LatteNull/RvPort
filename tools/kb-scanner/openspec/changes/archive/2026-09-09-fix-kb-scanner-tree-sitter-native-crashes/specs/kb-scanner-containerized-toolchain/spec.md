## ADDED Requirements

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
