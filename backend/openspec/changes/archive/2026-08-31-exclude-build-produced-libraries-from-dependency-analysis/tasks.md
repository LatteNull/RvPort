## 1. 构建产物识别

- [x] 1.1 在 `DependencyFactExtractor` 中解析 `RVPORT_OBSERVATION buildProducedElf`，建立本次构建产物路径集合。
- [x] 1.2 从本次构建产物的 `elfSoname` 和共享库文件名中建立自产共享库标识集合。
- [x] 1.3 确保路径和 SONAME 归一化逻辑可以兼容 `libfoo.so`、`libfoo.so.1`、`libfoo.so.1.2.3`。

## 2. 依赖结果过滤

- [x] 2.1 过滤本次构建生成共享库自身的 `elfSoname` 结果。
- [x] 2.2 过滤任意 ELF 对本次构建生成共享库的 `elfNeeded` 内部链接结果。
- [x] 2.3 保留本次构建产物对外部系统库的 `elfNeeded` 分析结果。
- [x] 2.4 保留 `repositoryBundledElf` 对仓库原有 ELF/SO 的分析结果。

## 3. 测试覆盖

- [x] 3.1 增加正常流程单元测试：本次构建生成的 `libcjson.so.1` 不进入依赖结果。
- [x] 3.2 增加异常流程单元测试：缺少 `buildProducedElf` 信息时保持现有降级行为。
- [x] 3.3 增加 edge case 单元测试：同一构建产物同时依赖自产库和系统库时，只过滤自产库。
- [x] 3.4 检查 `test2` 真实依赖分析数据路径，确认修复后 `libcjson.so.1` 和 `libcjson_utils.so.1` 不再作为外部依赖展示。

## 4. 验证

- [x] 4.1 运行依赖分析相关单元测试。
- [x] 4.2 运行 OpenSpec strict validation。
- [x] 4.3 如条件允许，重建后端容器并对 `test2` 重新运行依赖分析验证结果。
