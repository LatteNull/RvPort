## Context

KB Scanner 当前通过 `tools/kb-scanner` 独立 CLI 扫描源码版本，并将 finding 导入后端。现有文件发现覆盖 C/C++、汇编和部分构建文件，但没有发现 `*.spec`；现有 `language: build` 规则也没有 RPM spec 的 section、架构条件和宏语义。

RPM 打包项目的迁移风险可能不在 C/C++ 源码中，而在 spec 文件中：`ExclusiveArch`、`ExcludeArch`、`%ifarch`、`%ifnarch`、`%build`、`%install`、`%check` 都可能决定 RISC-V 是否被构建、安装或测试。因此这次需要补齐 RPM spec 专属扫描能力。

## Goals / Non-Goals

**Goals:**

- KB Scanner 发现并扫描 `*.spec` 文件。
- 使用单独的 YAML 规则文件定义 RPM spec 扫描规则。
- 增加 RPM spec 匹配能力，覆盖 section、架构条件、架构限制、x86-only 编译参数和测试阶段逻辑。
- `%check` 与 `%build` 同等纳入检测，确保迁移后测试阶段风险能被发现。
- 默认基于原始 spec 静态文本和架构相关局部宏识别，不依赖完整 RPM 宏展开。
- findings 继续复用现有 KB 扫描入库、代码上下文、报告和归档链路。
- 补充正常流程、异常流程和 edge case 测试。

**Non-Goals:**

- 不在 KB 扫描中实现完整 RPM spec 解释器或真正执行 rpmbuild。
- 不将 `rpmspec --parse` 或完整 RPM 宏展开作为第一版必需流程。
- 不把普通 `BuildRequires` / `Requires` 全量转换为 KB finding；依赖可用性仍由构建驱动依赖分析负责。
- 不处理跨发行版包名映射或依赖替代性判断。
- 不修改 KB Scanner 输出文件格式，不新增替代 `scan-result.json`、`scan-report.html` 或 `scan.log` 的输出文件。
- 不修改前端页面。

## Decisions

### 1. RPM spec 使用独立扫描类型

将 `*.spec` 加入 KB Scanner 文件发现，但不简单依赖现有 `language: build` 规则。实现上可以增加 `rpm_spec` 类型或等效 source kind，使 `.spec` 能被专属规则匹配。

理由：

- RPM spec 的 section 和宏语义与 Make/CMake/Shell 不同。
- 独立类型可以控制误报，不会让通用 build 规则误命中 spec 注释、changelog 或宏文本。
- 后续如果增加 Debian packaging、Meson option 等，也可以按输入类型扩展。

### 2. RPM spec 规则必须使用独立 YAML 文件

规则集应新增独立 YAML 文件，例如：

- `rules/rpm_spec/rpm-spec-arch-constraints.yaml`
- `rules/rpm_spec/rpm-spec-x86-build-and-check.yaml`

或者在现有目录下使用清晰命名的单独文件，但不得把 RPM spec 规则混入 `x86-build-feature-macro.yaml`。

理由：

- 规则所有权清晰，便于后续审计和调整 severity。
- 匹配范围能明确限定 `*.spec`。
- 满足当前要求：单独 YAML 文件和对应匹配规则。

### 3. 先做轻量 RPM spec facts，不做完整 parser 或完整宏展开

scanner 可以按行解析出以下轻量 facts：

- 当前 section：`%prep`、`%build`、`%install`、`%check`、`%files`、`%changelog`
- 架构限制：`ExclusiveArch`、`ExcludeArch`
- 条件块：`%ifarch`、`%ifnarch`、`%if`、`%else`、`%endif`
- 架构相关宏定义：`%global`、`%define` 中的 `_target_cpu`、`_host_cpu`、`_build_cpu`、`optflags`、`build_cflags`、`build_cxxflags`、`build_ldflags`、架构 token 和 x86-only 编译参数
- 普通命令行：section 内的 shell-like 文本

第一版不需要完整理解或展开所有 RPM 宏，只需要围绕架构迁移相关宏做局部识别，并保留原始行、section、条件栈和命中 token。`%{name}`、`%{version}`、`%{release}`、`%{_bindir}`、`%{_libdir}`、`%{buildroot}` 等普通包元信息和安装路径宏默认不作为风险来源。

### 4. `%check` 必须作为高优先级扫描区域

`%check` 中的 x86-only 测试选择、RISC-V 跳过逻辑和 x86 编译参数都应生成 finding。

建议风险语义：

- `ExcludeArch: riscv64`：`critical` 或 `high`
- `ExclusiveArch` 不包含 `riscv64` 且只包含 x86：`high`
- `%build` / `%check` 中出现 `-mavx`、`-msse*`、`-mfma`、`-march=x86-64`：`high`
- `%check` 中显式跳过 RISC-V 测试：`medium`
- `%ifarch x86_64` 中有测试或构建逻辑但存在 portable/riscv sibling：`low` 或 `info`
- 普通测试依赖线索：`info`

### 5. 注释和 changelog 默认不产生 finding

RPM spec 中 `%changelog` 和注释行经常包含历史架构名或命令片段。默认必须忽略：

- `#` 注释行
- `%changelog` section 内文本

如果将来需要审计历史信息，可以作为显式扫描选项，而不是默认行为。

### 6. 普通依赖行不重复依赖分析职责

`BuildRequires`、`Requires` 本身不应默认成为迁移风险 finding。只有当依赖行位于架构条件块中，或依赖名称/条件明确表达 x86-only 行为时，才作为 KB finding。

普通依赖是否存在、版本是否满足、目标环境是否可安装，仍由依赖分析节点处理。

### 7. 不修改 scanner 输出文件格式

RPM spec finding 必须复用现有 KB Scanner 输出结构，继续写入 `scan-result.json` 中的 findings，并继续由现有 `scan-report.html` 和 `scan.log` 表达报告与日志。

允许新增 rule id、source kind、evidence 字段内容和 finding trace，但不得新增新的主输出文件，也不得破坏后端当前对 `scan-result.json` 的解析契约。

理由：

- 后端 KB 扫描运行时、artifact 存储、下载接口和归档登记都已经围绕现有输出文件建立。
- 修改输出文件格式会扩大变更范围，并引入前后端兼容风险。
- 本 change 的目标是增加 RPM spec 检测能力，不是重构 scanner 输出协议。

### 8. `rpmspec --parse` 仅作为后续可选增强

完整 RPM 宏展开不是第一版必需能力。当前范围内，scanner 不应依赖 `rpmspec --parse` 才能产生 RPM spec finding。

如果后续真实样本证明原始静态扫描无法覆盖关键风险，可以再引入 `rpmspec --parse --target x86_64` 和 `rpmspec --parse --target riscv64` 作为辅助 evidence。但该增强必须保持 finding 主位置指向原始 `.spec` 文件，并且不能改变现有输出文件契约。

## Risks / Trade-offs

- [Risk] 不做完整宏展开可能漏掉间接拼接出的架构参数。
  Mitigation: 第一版优先覆盖显式架构条件、架构宏定义和 x86 参数；复杂间接宏后续按真实样本评估是否引入可选 `rpmspec --parse` 辅助 evidence。

- [Risk] `ExclusiveArch` 的严重程度可能与项目策略相关。
  Mitigation: 将 severity 固定在规则 YAML 中，后续可按规则集版本调整；finding 保留 evidence 便于人工确认。

- [Risk] `%check` 中跳过测试不一定代表迁移阻断。
  Mitigation: 默认使用 `medium`，进入报告但允许人工撤回。

- [Risk] 把普通依赖行纳入 KB 扫描会和依赖分析重复。
  Mitigation: 明确规则只处理架构相关依赖线索，普通依赖交给依赖分析。
