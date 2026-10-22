## Why

当前依赖分析已经能基于构建前后 ELF manifest 和部分链接日志排除本次构建生成的 `.so`/ELF，但在构建目录残留、marker 缺失或链接日志不完整时，仍可能把项目自身构建出来的库误判为外部依赖。`compile_commands.json` 已经作为构建上下文被保存，可以作为补充证据提升“项目构建产物”归因准确度。

## What Changes

- 从可用的 `compile_commands.json` 中提取源码文件、object 输出、工作目录和编译命令摘要，建立源码到 object 的构建关系。
- 将 compile database 证据并入本次构建产物识别链路，用于辅助判断 ELF/SO 是否由当前项目源码编译并链接生成。
- 在依赖分析中继续过滤确认属于本次构建产物的 `elfSoname` 和内部 `elfNeeded` 结果。
- 保持仓库原本携带的 prebuilt ELF/SO 分析行为，不能仅因文件位于 build 目录或出现在 compile database 附近就过滤。
- 保持安全约束：不在 API 结果、日志摘要或依赖结果中暴露完整 `compile_commands.json`、远端绝对路径或敏感参数。

## Capabilities

### New Capabilities

### Modified Capabilities
- `dependency-analysis-runtime`: 增强本次构建产物识别规则，允许使用 compile database 中的源码到 object 关系辅助过滤项目自产 ELF/SO。

## Impact

- 影响依赖分析构建事实解析和 `DependencyFactExtractor` 的构建产物过滤逻辑。
- 影响构建验证产生的 compile database artifact 在依赖分析阶段的使用方式。
- 影响依赖分析单元测试和 API E2E 覆盖，尤其是 CMake/Bear 产生 `compile_commands.json` 的真实构建场景。
- 不改变现有依赖分析 API 结构；新增内容应体现在内部 evidence、过滤行为和测试覆盖中。
