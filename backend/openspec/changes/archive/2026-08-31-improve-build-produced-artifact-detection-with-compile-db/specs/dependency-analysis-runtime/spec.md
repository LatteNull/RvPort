## ADDED Requirements

### Requirement: 依赖分析必须使用 compile database 辅助识别本次构建产物
依赖分析运行时 SHALL 在可用时使用同一源码版本、同一 source/x86 成功构建产生的 `compile_commands.json` 建立源码到 object 的构建关系，并 SHALL 将该关系作为识别本次构建生成 ELF/SO 的辅助证据。

#### Scenario: 从 compile database 建立 object 索引
- **WHEN** 依赖分析输入包含可用 `compile_commands.json` 构建上下文 artifact
- **THEN** worker SHALL 解析其中的 `file`、`directory`、`command` 或 `arguments`
- **AND** worker SHALL 从编译命令中提取 `-o` object 输出路径
- **AND** worker SHALL 建立项目源码相对路径到 object 相对路径的内部索引
- **AND** worker MUST NOT 将完整 `compile_commands.json`、完整编译命令或远端绝对路径写入依赖分析结果

#### Scenario: compile database 辅助过滤项目自产共享库
- **WHEN** `compile_commands.json` 证明项目源码被编译为 object 文件
- **AND** 构建日志、strace、build graph 或 ELF 事实证明这些 object 参与生成 `libfoo.so` 或 `libfoo.so.1`
- **THEN** 依赖分析 SHALL 将该共享库标记为本次构建产物
- **AND** 依赖分析 SHALL 过滤该共享库自身的 `elfSoname` 结果
- **AND** 依赖分析 SHALL 过滤其他本次构建产物对该共享库的内部 `elfNeeded` 结果
- **AND** evidence SHALL 记录 compile database 参与了构建产物归因

#### Scenario: 保留自产产物对外部库的依赖
- **WHEN** 本次构建生成的 ELF 或 SO 依赖 `libc.so.6`、`libgcc_s.so.1` 或其他外部系统库
- **THEN** 依赖分析 SHALL 继续生成对应外部库依赖结果
- **AND** 依赖分析 MUST NOT 因该引用发生在本次构建产物内就过滤外部依赖

#### Scenario: compile database 缺失或无效时降级
- **WHEN** `compile_commands.json` artifact 不存在、读取失败、格式非法或超过受控解析限制
- **THEN** 依赖分析 SHALL 继续使用 `buildProducedElf`、`repositoryBundledElf`、构建日志、strace 和 ELF metadata 执行现有分析
- **AND** 依赖分析 MUST NOT 因 compile database 不可用而失败
- **AND** 依赖分析 SHALL 记录安全 warning 或内部 evidence 摘要

#### Scenario: 不得仅凭 compile database 过滤 ELF/SO
- **WHEN** 某个 `.so` 或 ELF 文件没有 `buildProducedElf`、明确链接日志、strace linker 输出、build graph 或等效产物证据
- **AND** 仅能观察到同一目录附近存在 compile database object 输出
- **THEN** 依赖分析 MUST NOT 将该 `.so` 或 ELF 判定为本次构建产物
- **AND** 该文件 SHALL 按现有 repository bundled 或 unknown 规则继续分析

#### Scenario: 仓库原本携带的 prebuilt ELF/SO 不被误过滤
- **WHEN** 构建前 manifest 已经包含 `vendor/libbar.so` 或 `build/prebuilt/libbar.so`
- **AND** 构建后该文件没有强覆盖证据
- **THEN** 依赖分析 SHALL 保留该 ELF/SO 作为依赖候选
- **AND** 依赖分析 MUST NOT 因文件路径位于 `build/`、`out/` 或 compile database 工作目录下而过滤该文件

#### Scenario: 构建前已存在但被本次覆盖的产物
- **WHEN** 构建前 manifest 已经包含某个 ELF/SO
- **AND** 构建后 manifest、hash、mtime、strace 或链接日志能证明该路径被本次构建重新生成
- **THEN** 依赖分析 MAY 将该文件标记为本次构建产物
- **AND** evidence SHALL 记录覆盖判断来源
- **AND** 如果覆盖证据不足，依赖分析 SHALL 保持保守并继续按仓库原有 ELF/SO 分析
