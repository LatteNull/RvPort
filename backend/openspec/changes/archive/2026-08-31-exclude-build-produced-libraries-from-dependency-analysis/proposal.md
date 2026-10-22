## Why

`test2` 的真实依赖分析中，`libcjson.so.1` 和 `libcjson_utils.so.1` 被标记为高风险/缺失依赖，但这些库实际是项目本次构建产生的共享库。依赖分析需要关注外部构建、链接和运行依赖，而不是把当前源码构建出的产物再次当成迁移依赖。

## What Changes

- 依赖分析在解析构建日志时识别 `RVPORT_OBSERVATION buildProducedElf`。
- 对本次构建生成的 ELF/SO：
  - 不将其自身 `SONAME` 生成依赖结果。
  - 不将其他本次构建产物对该 `SONAME` 的 `NEEDED` 关系生成依赖结果。
- 继续保留源码仓库原本携带的 ELF/SO 分析能力。
- 继续分析本次构建产物依赖的外部系统库，例如 `libc.so.6`、`libm.so.6`、`libgcc_s.so.1`。
- 增加正常流程、异常流程和 edge case 测试，防止自产共享库再次污染依赖结果。

## Capabilities

### New Capabilities

- None

### Modified Capabilities

- `dependency-analysis-runtime`: 明确依赖分析必须排除本次构建生成的共享库及其内部 SONAME/NEEDED 派生项，只保留外部依赖。

## Impact

- Affected code:
  - `src/main/java/cn/rvport/backend/dependency/DependencyFactExtractor.java`
  - `src/test/java/cn/rvport/backend/dependency/DependencyFactExtractorTests.java`
- Affected behavior:
  - 依赖分析结果列表、详情、HTML/JSON artifact 中不再出现本项目构建产出的共享库作为外部依赖。
  - `test2` 这类 CMake 项目中自产 `libcjson*.so` 不应再进入依赖分析结果。
- APIs:
  - 无新增 API。
  - 现有依赖分析 API 返回结果内容会更准确，减少误报。
