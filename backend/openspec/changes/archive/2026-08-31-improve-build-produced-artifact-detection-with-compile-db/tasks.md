## 1. Compile Database 解析

- [x] 1.1 实现 compile database 受控读取入口，确保只读取当前项目、当前源码版本、成功 source/x86 构建关联的 artifact。
- [x] 1.2 解析 `compile_commands.json` 的 `file`、`directory`、`command` 和 `arguments` 字段。
- [x] 1.3 从编译命令中提取 `-o` object 输出路径，并归一化为内部可比较路径。
- [x] 1.4 建立源码相对路径到 object 相对路径的内部索引，并限制 entry 数量、字段长度和 evidence 大小。
- [x] 1.5 确保完整 compile database、完整编译命令、远端绝对路径和敏感参数不会出现在 API 结果或依赖结果明细中。

## 2. 构建产物归因

- [x] 2.1 将 compile object 索引接入现有构建产物归因逻辑。
- [x] 2.2 将 `buildProducedElf`、CMake/Make/Ninja 链接日志、strace linker 事实和 compile object 关系合并为统一的 build-produced 判断。
- [x] 2.3 对确认由当前项目源码 object 链接生成的 SO/ELF 标记为本次构建产物。
- [x] 2.4 过滤本次构建产物自身的 `elfSoname` 结果。
- [x] 2.5 过滤其他本次构建产物对自产 SO 的内部 `elfNeeded` 结果。
- [x] 2.6 保留本次构建产物对外部系统库的 `elfNeeded` 结果。
- [x] 2.7 保留仓库构建前已存在且无覆盖证据的 prebuilt ELF/SO 依赖候选。

## 3. 降级与安全

- [x] 3.1 compile database 不存在时保持当前依赖分析行为。
- [x] 3.2 compile database artifact 读取失败、JSON 非法或超限时记录 warning 并降级，不使依赖分析失败。
- [x] 3.3 仅有 compile database object 或路径邻近证据时，不将 SO/ELF 判定为本次构建产物。
- [x] 3.4 构建前已存在但构建后被覆盖的同路径 ELF/SO，在证据不足时保持保守并继续作为依赖候选。

## 4. 测试

- [x] 4.1 增加正常流程单元测试：compile database object 加链接证据时过滤项目自产 SO。
- [x] 4.2 增加异常流程单元测试：compile database 缺失或无效时保持现有降级行为。
- [x] 4.3 增加 edge case 单元测试：仓库原本携带的 prebuilt SO 位于 build 目录时不被误过滤。
- [x] 4.4 增加 edge case 单元测试：自产产物依赖外部系统库时只过滤自产库，保留外部库。
- [x] 4.5 覆盖路径归一化：`libfoo.so`、`libfoo.so.1`、`libfoo.so.1.2.3` 和 object 相对路径匹配。

## 5. 验证

- [x] 5.1 运行 `mvn -Dtest=DependencyFactExtractorTests test`。
- [x] 5.2 运行 OpenSpec strict validation。
- [x] 5.3 如条件允许，重建后端容器。
- [x] 5.4 如条件允许，使用真实 CMake/Bear 生成 `compile_commands.json` 的项目运行依赖分析，确认项目自产 SO 不再展示为外部依赖。
