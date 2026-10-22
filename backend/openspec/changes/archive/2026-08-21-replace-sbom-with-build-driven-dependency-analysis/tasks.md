## 1. 文档与兼容策略

- [x] 1.1 更新后端 API 文档，将旧 SBOM 分析标记为 deprecated，并补充依赖分析 API、分页过滤排序、artifact 下载和 `buildScope` 参数
- [x] 1.2 更新数据库设计文档，补充依赖分析运行表、逐条结果表、构建事实引用和 artifact/归档候选关系，并明确旧 `sbom_*` 表保留兼容
- [x] 1.3 更新任务流文档，说明新主流程使用 `SOURCE_ONLY` x86 构建事实驱动依赖分析，正式构建验证仍默认双环境运行
- [x] 1.4 更新 E2E 覆盖文档，将 SBOM E2E 标记为 deprecated 兼容验证，并新增依赖分析模块覆盖清单

## 2. 构建运行范围

- [x] 2.1 增加构建范围模型，支持 `BOTH` 和 `SOURCE_ONLY`，未传参数时默认 `BOTH`
- [x] 2.2 使用 Liquibase 为构建运行记录补充 `build_scope`、source 构建事实引用所需字段和必要索引
- [x] 2.3 运行 jOOQ 生成脚本，提交更新后的生成代码
- [x] 2.4 修改构建创建 API，使 `SOURCE_ONLY` 只创建 source/x86 构建运行并拒绝 MVP 不支持的范围值
- [x] 2.5 修改构建 worker，使源码部署作为构建内部步骤复用，并在 source 构建成功后保存日志引用、脚本摘要、环境版本和构建事实摘要
- [x] 2.6 补充构建范围单元测试，覆盖默认双环境、source-only、非法范围、缺少 source 环境和环境权限边界

## 3. 依赖分析运行时

- [x] 3.1 使用 Liquibase 新增 `dependency_analysis_runs` 和 `dependency_analysis_result_items`，每条依赖结果独立落库并建立项目、源码版本、任务、状态、风险、类型和创建时间索引
- [x] 3.2 运行 jOOQ 生成脚本，提交依赖分析相关生成代码
- [x] 3.3 新增 `DEPENDENCY_ANALYSIS` 任务类型、队列投递、worker handler、状态事件、取消处理和失败重试策略
- [x] 3.4 实现依赖分析创建 API，校验项目权限、当前源码版本、运行双环境和成功 source/x86 构建事实
- [x] 3.5 实现依赖分析列表、详情、结果列表、结果详情和 artifact 下载 API，支持分页、过滤、排序和敏感信息脱敏
- [x] 3.6 实现源码树和构建脚本静态探测，识别 `CMakeLists.txt`、`Makefile`、`*.spec`、`configure`、`meson.build`、`build.ninja` 等构建系统 hint
- [x] 3.7 实现构建 wrapper 的 `PS4` + `set -x` shell trace，记录脱敏后的命令、工作目录和脚本行号摘要
- [x] 3.8 实现可选 `strace -f -e execve` 采集，支持构建前受控有限安装、超时、失败降级和 `straceUnavailable` warning
- [x] 3.9 实现自然生成编译数据库采集，解析 `compile_commands.json`、`CMakeCache.txt` 和 `build.ninja` 的脱敏摘要
- [x] 3.10 实现可选 Bear 包裹构建脚本生成 `compile_commands.json`，支持受控有限安装、失败降级和 `bearUnavailable` warning
- [x] 3.11 实现构建事实提取，覆盖命令、工作目录、环境变量名、merged/stdout/stderr 日志、编译器参数、linker 参数、pkg-config、头文件、ELF NEEDED/SONAME 和 owner package
- [x] 3.11.1 实现 source/x86 实际编译器内置宏采集，用于区分编译器内置宏、构建系统参数探测宏和项目自定义宏
- [x] 3.12 实现 RISC-V 目标能力查询，覆盖已安装包、仓库候选、provides/whatprovides、pkg-config、头文件和库文件提供者
- [x] 3.13 实现逐条匹配状态与风险计算，输出 `TARGET_INSTALLED`、`REPO_AVAILABLE`、`PROVIDES_MATCH`、`VERSION_MISMATCH`、`SOURCE_BUILD_REQUIRED`、`MISSING` 和 `MANUAL_CONFIRM_REQUIRED`
- [x] 3.14 生成依赖分析 JSON/HTML artifact 并写入对象存储，同时登记当前源码版本的归档候选
- [x] 3.15 补充依赖分析单元测试，覆盖正常流程、异常流程和 edge case

## 4. SBOM deprecated 兼容

- [x] 4.1 保留旧 SBOM 查询、结果、artifact 和历史任务展示能力，并在响应或文档中标记 deprecated
- [x] 4.2 确保新迁移主流程、自动合并、报告和归档默认不再创建新的 `SBOM_ANALYSIS` 任务
- [x] 4.3 明确旧 SBOM 创建入口的兼容策略，避免静默把旧请求改写为依赖分析请求
- [x] 4.4 补充 SBOM deprecated 兼容测试，确认旧历史数据仍可查询且新流程不依赖 SBOM

## 5. 迁移输入、报告与归档

- [x] 5.1 扩展迁移输入来源，支持 `DEPENDENCY_RESULT` 并校验结果属于当前项目和 URL 中的 `sourceRevisionId`
- [x] 5.2 修改自动合并逻辑，新流程默认合并当前源码版本的依赖分析结果，并保持历史 `SBOM_RESULT` 查询兼容
- [x] 5.3 修改迁移输入展示字段，依赖分析的 `detectedLevel` 使用 `riskLevel + "/" + targetMatchStatus`，`locationLabel` 表达工具、包、库或测试依赖位置
- [x] 5.4 修改迁移报告生成，读取 confirmed 的 `DEPENDENCY_RESULT` 并展示依赖类型、目标匹配状态、风险等级、建议和 evidence 摘要
- [x] 5.5 修改报告摘要统计，补充依赖分析输入总数、按风险等级统计、按目标匹配状态统计和主要依赖风险
- [x] 5.6 修改归档运行时，归档当前源码版本下的依赖分析 HTML、JSON、统计摘要和结果引用，并保留历史 SBOM 归档项兼容

## 6. E2E 与验证

- [x] 6.1 新增依赖分析 E2E 模块，创建项目、源码版本、运行双环境和 `SOURCE_ONLY` 构建运行
- [x] 6.2 E2E 调用依赖分析创建 API，等待 `DEPENDENCY_ANALYSIS` 任务终态，并验证任务事件、日志、运行记录、结果明细和 artifact
- [x] 6.3 E2E 覆盖依赖分析列表、详情、结果列表、结果详情、artifact 下载、分页、过滤、排序和敏感信息边界
- [x] 6.4 E2E 覆盖异常流程，包括没有成功 source/x86 构建、缺少双环境、环境不属于项目和用户无权限
- [x] 6.5 E2E 覆盖将 `DEPENDENCY_RESULT` 批量加入迁移输入、重复导入幂等和详情 evidence 回查
- [x] 6.6 运行 `mvn test`，确认后端单元测试通过
- [x] 6.7 重新构建后端 Docker 镜像并启动 compose，确认 Liquibase、jOOQ 生成代码和 worker 启动正常
- [x] 6.8 运行相关 E2E 模块，确认 source-only 构建、依赖分析、迁移输入、报告和归档链路通过
- [x] 6.9 运行 `openspec validate replace-sbom-with-build-driven-dependency-analysis --strict`
