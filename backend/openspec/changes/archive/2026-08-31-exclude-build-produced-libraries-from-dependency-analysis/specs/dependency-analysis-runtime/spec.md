## ADDED Requirements

### Requirement: 依赖分析必须排除本次构建生成共享库的内部依赖
依赖分析运行时 SHALL 使用构建前后 ELF manifest 区分本次构建生成的共享库，并 MUST NOT 将这些共享库自身或其他本次构建产物对这些共享库的内部链接关系保存为外部依赖分析结果。

#### Scenario: 本次构建生成共享库的 SONAME 不进入依赖结果
- **WHEN** 构建事实包含 `RVPORT_OBSERVATION buildProducedElf build/libfoo.so.1.2.3`
- **AND** 同一路径包含 `RVPORT_OBSERVATION elfSoname build/libfoo.so.1.2.3	libfoo.so.1`
- **THEN** 依赖分析 MUST NOT 生成 `libfoo.so.1` 或 `libfoo.so` 的外部依赖结果项
- **AND** 依赖分析 MAY 将该 SONAME 作为本次构建产物排除 evidence 使用

#### Scenario: 本次构建产物依赖本次构建共享库不进入依赖结果
- **WHEN** 构建事实包含本次构建生成共享库 `libfoo.so.1`
- **AND** 构建事实包含本次构建生成可执行文件 `build/tests/foo_test`
- **AND** `build/tests/foo_test` 的 `elfNeeded` 包含 `libfoo.so.1`
- **THEN** 依赖分析 MUST NOT 将 `libfoo.so.1` 保存为外部运行依赖
- **AND** 结果列表、详情、HTML artifact 和 JSON artifact MUST NOT 展示该库为缺失依赖

#### Scenario: 本次构建产物的外部系统库依赖仍需分析
- **WHEN** 本次构建生成可执行文件 `build/tests/foo_test`
- **AND** `build/tests/foo_test` 的 `elfNeeded` 包含 `libc.so.6`、`libm.so.6` 或 `libgcc_s.so.1`
- **AND** 这些库不是本次构建生成共享库的 SONAME 或归一化文件名
- **THEN** 依赖分析 SHALL 继续对这些外部系统库执行 source owner package 和 target provider package 匹配
- **AND** 依赖分析 SHALL 保留对应风险等级、版本关系和 evidence

#### Scenario: 仓库原本携带共享库仍需分析
- **WHEN** 构建事实包含 `RVPORT_OBSERVATION repositoryBundledElf vendor/libfoo.so`
- **AND** 该路径不属于 `buildProducedElf`
- **THEN** 依赖分析 SHALL 将该仓库原有共享库作为依赖候选分析
- **AND** 后端 MUST NOT 仅凭路径包含 `build`、`vendor` 或 `.so` 后缀就跳过分析

#### Scenario: 构建产物标记缺失时保持降级行为
- **WHEN** 构建事实没有 `buildProducedElf` 信息
- **AND** 存在 `elfNeeded` 或 `elfSoname` 观测
- **THEN** 依赖分析 SHALL 按现有外部依赖匹配逻辑处理
- **AND** 依赖分析 MUST NOT 因缺少构建产物 manifest 而失败
