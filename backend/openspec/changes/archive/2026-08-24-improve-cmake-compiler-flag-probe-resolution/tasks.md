## 1. CMake Probe 采集

- [x] 1.1 在构建 wrapper 中增加 CMake 文件扫描，覆盖多层级 `CMakeLists.txt` 和 `*.cmake`，排除 `.git`、构建缓存和明显无关目录
- [x] 1.2 实现轻量 CMake tokenizer，支持注释剥离、括号块、多行、单双引号和基础参数拆分
- [x] 1.3 解析 `check_c_compiler_flag`、`check_cxx_compiler_flag` 和 `check_compiler_flag`，输出 `RVPORT_OBSERVATION cmakeCompilerFlagProbe`
- [x] 1.4 对无法解析、变量展开或冲突映射输出 warning/evidence，确保采集失败不影响构建任务状态

## 2. 依赖分析分类

- [x] 2.1 在 `DependencyFactExtractor` 中解析 `cmakeCompilerFlagProbe` 观测并建立 define 变量映射
- [x] 2.2 调整 define 分类顺序：CMake probe 映射优先，其次编译器内置宏采集，最后项目/构建自定义宏
- [x] 2.3 移除 `FLAG_SUPPORTED_` 前缀强判定，未命中动态映射的前缀宏不得自动归类为 `compiler_flag_probe`
- [x] 2.4 在结果 evidence 中写入 `compilerFlag`、`probeSource`、`probeFile`、`probeLanguage`、冲突候选和置信度来源
- [x] 2.5 更新依赖分析 JSON/HTML 摘要生成逻辑，避免把 compiler flag probe 展示成编译器内置宏

## 3. 测试覆盖

- [x] 3.1 补充 CMake tokenizer 单元测试，覆盖单行、多行、引号、注释、子目录文件和无法解析变量
- [x] 3.2 补充依赖分析单元测试，覆盖命中 CMake 映射、未命中 `FLAG_SUPPORTED_` 前缀、编译器内置宏、项目自定义宏和冲突映射
- [x] 3.3 补充构建 wrapper 相关测试，确认 CMake probe 采集失败不会改变构建状态
- [x] 3.4 补充 API E2E 或真实 fixture，覆盖 CMake 多层级 probe 映射和前缀误判防护

## 4. 验证

- [x] 4.1 运行 `mvn -Dtest=DependencyFactExtractorTests test`
- [x] 4.2 运行 `mvn test`
- [x] 4.3 重新构建 backend Docker 容器并确认健康状态
- [x] 4.4 使用真实 CMake 项目重新跑依赖分析，确认 `FLAG_SUPPORTED_fstackprotectorstrong` 映射为 `-fstack-protector-strong`
- [x] 4.5 生成新的 HTML 汇总供审计
- [x] 4.6 运行 `openspec validate improve-cmake-compiler-flag-probe-resolution --strict`
- [x] 4.7 运行 `openspec validate --specs --strict`
