## ADDED Requirements

### Requirement: KB Scanner 必须扫描 RPM spec 文件
KB Scanner SHALL 将 RPM spec 文件作为知识库扫描输入，并 SHALL 对 `*.spec` 使用 RPM spec 专属匹配语义。

#### Scenario: 发现 RPM spec 文件
- **WHEN** 项目源码版本中存在 `*.spec` 文件
- **THEN** KB Scanner SHALL 将该文件纳入扫描文件集合
- **AND** scanner SHALL 将该文件标记为 RPM spec 类型或等效 source kind
- **AND** scanner MUST NOT 因默认语言为 `c,cpp` 而跳过该文件

#### Scenario: RPM spec 文件被排除
- **WHEN** 用户提交的扫描排除路径命中某个 `*.spec` 文件
- **THEN** KB Scanner SHALL 跳过该 RPM spec 文件
- **AND** scanner MUST NOT 为该文件生成 finding

### Requirement: RPM spec 扫描必须使用独立 YAML 规则
RPM spec 检测规则 SHALL 使用独立 YAML 文件定义，并 SHALL 只匹配 RPM spec 文件或 RPM spec facts。

#### Scenario: 使用独立 RPM spec 规则文件
- **WHEN** 规则集包含 RPM spec 检测能力
- **THEN** 规则集 SHALL 使用单独 YAML 文件保存 RPM spec 规则
- **AND** 该规则文件 SHALL 具有稳定 rule id、language 或 source kind、severity、confidence、match 和 message 字段
- **AND** RPM spec 规则 MUST NOT 混入通用 build 规则文件

#### Scenario: RPM spec 规则不影响普通构建文件
- **WHEN** 项目中存在 `Makefile`、`CMakeLists.txt`、`meson.build` 或 shell 构建脚本
- **THEN** RPM spec YAML 规则 MUST NOT 匹配这些非 RPM spec 文件
- **AND** scanner MUST NOT 因 RPM spec 规则导致普通构建文件新增误报

### Requirement: RPM spec 扫描必须识别 section 和架构条件
KB Scanner SHALL 识别 RPM spec 中的 section、架构限制和条件块，并 SHALL 将命中位置和条件栈写入 finding evidence。

#### Scenario: 识别 RPM spec section
- **WHEN** RPM spec 中出现 `%prep`、`%build`、`%install`、`%check`、`%files` 或 `%changelog`
- **THEN** scanner SHALL 记录后续命中所在 section
- **AND** finding evidence SHALL 包含 section 名称

#### Scenario: 识别架构限制
- **WHEN** RPM spec 中出现 `ExclusiveArch` 或 `ExcludeArch`
- **THEN** scanner SHALL 解析该行中的架构 token
- **AND** scanner SHALL 能识别 `x86_64`、`amd64`、`i386`、`i686`、`%{ix86}`、`riscv64` 和 `riscv` 等常见 token
- **AND** finding evidence SHALL 保存原始行摘要和解析后的架构 token

#### Scenario: 识别架构条件块
- **WHEN** RPM spec 中出现 `%ifarch`、`%ifnarch`、`%if`、`%else` 或 `%endif`
- **THEN** scanner SHALL 维护当前条件栈
- **AND** 条件块内生成的 finding SHALL 保存命中的条件栈摘要

### Requirement: RPM spec 扫描默认不得依赖完整宏展开
RPM spec 扫描 SHALL 默认基于原始 spec 静态文本和架构相关局部宏识别，不得要求完整 RPM 宏展开才能发现基础迁移风险。

#### Scenario: 不依赖 rpmspec parse
- **WHEN** 运行环境未安装 `rpmspec`
- **THEN** scanner SHALL 继续扫描原始 `*.spec` 文件
- **AND** scanner SHALL 能发现显式 `ExclusiveArch`、`ExcludeArch`、`%ifarch`、`%ifnarch` 和 x86-only 编译或测试参数
- **AND** scanner MUST NOT 因缺少完整宏展开工具导致整次 KB 扫描失败

#### Scenario: 只识别架构相关局部宏
- **WHEN** RPM spec 中存在 `%global`、`%define` 或 `%{...}` 宏引用
- **THEN** scanner SHALL 只将 `_target_cpu`、`_host_cpu`、`_build_cpu`、`optflags`、`build_cflags`、`build_cxxflags`、`build_ldflags`、架构 token 和 x86-only 参数作为默认风险相关宏处理
- **AND** scanner MUST NOT 将 `%{name}`、`%{version}`、`%{release}`、`%{_bindir}`、`%{_libdir}`、`%{buildroot}` 等普通包元信息或安装路径宏作为默认风险来源

#### Scenario: 未解析宏保留为诊断
- **WHEN** scanner 发现无法静态判断的复杂 RPM 宏表达式
- **THEN** scanner MAY 在 diagnostics 或 finding evidence 中记录安全摘要
- **AND** scanner MUST NOT 因无法完整展开该宏而阻断扫描

### Requirement: RPM spec 扫描必须发现架构迁移风险
KB Scanner SHALL 从 RPM spec 中发现会影响 RISC-V 构建、安装或测试的架构迁移风险。

#### Scenario: ExclusiveArch 不包含 RISC-V
- **WHEN** RPM spec 中存在 `ExclusiveArch`
- **AND** 该行允许的架构只包含 x86 或不包含 RISC-V
- **THEN** scanner SHALL 生成 RPM spec finding
- **AND** finding severity SHALL 至少为 `high`
- **AND** finding suggestion SHALL 提示检查是否需要补充 RISC-V 构建支持

#### Scenario: ExcludeArch 排除 RISC-V
- **WHEN** RPM spec 中存在 `ExcludeArch`
- **AND** 该行包含 `riscv64`、`riscv` 或等效 RISC-V token
- **THEN** scanner SHALL 生成 RPM spec finding
- **AND** finding severity SHALL 至少为 `high`
- **AND** finding evidence SHALL 标明 RISC-V 被显式排除

#### Scenario: build 或 install 阶段出现 x86 参数
- **WHEN** RPM spec 的 `%build` 或 `%install` section 中出现 `-mavx`、`-mavx2`、`-mavx512*`、`-msse*`、`-mfma`、`-mxsave`、`-march=x86-64` 或等效 x86-only 参数
- **THEN** scanner SHALL 生成 RPM spec finding
- **AND** finding severity SHALL 至少为 `high`
- **AND** finding evidence SHALL 包含 section、命中 token 和脱敏后的原始行摘要

#### Scenario: check 阶段出现 x86 测试逻辑
- **WHEN** RPM spec 的 `%check` section 中出现 x86-only 测试选择、RISC-V 跳过逻辑或 x86-only 编译/运行参数
- **THEN** scanner SHALL 生成 RPM spec finding
- **AND** finding SHALL 标明该风险来自测试阶段
- **AND** finding suggestion SHALL 提示迁移后需要补充或调整 RISC-V 测试路径

#### Scenario: 架构条件块存在兼容分支
- **WHEN** RPM spec 中 x86 架构条件块命中风险
- **AND** 同一条件结构存在 RISC-V、portable、generic 或 fallback 分支
- **THEN** scanner MAY 降低 finding severity 或将其标记为 hint
- **AND** finding evidence SHALL 标明存在兼容分支

### Requirement: RPM spec 扫描必须控制误报
KB Scanner SHALL 忽略 RPM spec 中默认不代表当前迁移风险的文本，并 SHALL 避免与依赖分析职责重复。

#### Scenario: 忽略注释和 changelog
- **WHEN** x86、RISC-V 或构建参数只出现在注释行或 `%changelog` section 中
- **THEN** scanner MUST NOT 因这些文本生成默认 finding

#### Scenario: 普通依赖行不生成 KB finding
- **WHEN** RPM spec 中存在普通 `BuildRequires`、`Requires` 或 `Requires(post)` 依赖行
- **AND** 该依赖行不在架构条件块中
- **AND** 该依赖名称不表达 x86-only 行为
- **THEN** scanner MUST NOT 将该普通依赖行生成为 KB finding
- **AND** 依赖可用性 SHALL 继续由构建驱动依赖分析节点处理

#### Scenario: 架构相关依赖行生成 finding
- **WHEN** `BuildRequires`、`Requires` 或等效依赖行位于 x86-only 条件块中
- **OR** 依赖行明确表达 x86-only 依赖
- **THEN** scanner SHALL 生成 RPM spec finding 或 hint
- **AND** finding evidence SHALL 标明依赖行、section 和条件栈

### Requirement: RPM spec 扫描不得修改 KB Scanner 输出文件契约
RPM spec 扫描 SHALL 复用现有 KB Scanner 输出文件，不得新增或替换主输出文件格式。

#### Scenario: 复用现有 scan-result.json
- **WHEN** RPM spec 扫描生成 finding
- **THEN** scanner SHALL 将该 finding 写入现有 `scan-result.json` findings 结构
- **AND** scanner MAY 增加 rule id、source kind、evidence 或 trace 字段内容
- **AND** scanner MUST NOT 要求后端读取新的 RPM spec 专属结果文件

#### Scenario: 复用现有报告和日志文件
- **WHEN** RPM spec 扫描完成
- **THEN** scanner SHALL 继续使用现有 `scan-report.html` 和 `scan.log` 表达报告和日志
- **AND** scanner MUST NOT 用新的输出文件替代现有 KB artifact 下载契约

#### Scenario: 后端解析契约保持兼容
- **WHEN** 后端导入 RPM spec findings
- **THEN** 后端 SHALL 使用现有 KB Scanner result parser 读取结果
- **AND** 后端 MUST NOT 因 RPM spec 能力要求修改 KB Scanner 主输出文件名、主 JSON 顶层结构或 artifact 类型集合

### Requirement: RPM spec 扫描必须配套测试覆盖
RPM spec KB 扫描实现 SHALL 覆盖正常流程、异常流程和 edge case。

#### Scenario: 正常流程测试
- **WHEN** fixture 项目包含 RPM spec 文件，并在 `%build`、`%check` 或架构限制中包含 x86-only 逻辑
- **THEN** 测试 SHALL 验证 scanner 生成对应 RPM spec finding
- **AND** 测试 SHALL 验证 finding 通过后端 KB findings API 可查询

#### Scenario: 异常流程测试
- **WHEN** RPM spec 文件语法不完整、条件块未闭合或包含未知宏
- **THEN** scanner SHALL 尽可能继续扫描可解析内容
- **AND** scanner MUST NOT 因单个 spec 文件格式问题导致整次 KB 扫描失败

#### Scenario: edge case 测试
- **WHEN** x86 token 只出现在注释、changelog、普通依赖行或带兼容分支的条件块中
- **THEN** 测试 SHALL 验证 scanner 不误报或按预期降级
- **AND** 测试 SHALL 验证 finding evidence 包含 section、条件栈和命中 token
