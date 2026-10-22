## 1. 数据库与 jOOQ

- [x] 1.1 新增 Liquibase migration，使 `stored_artifacts.owner_type` 支持 `BUILD_VALIDATION`
- [x] 1.2 为构建上下文查询路径补充必要索引，支持按项目、源码版本、构建范围、状态和完成时间查找最新成功构建
- [x] 1.3 运行 Liquibase 更新本地数据库，并重新生成 jOOQ 代码
- [x] 1.4 补充数据库迁移测试或 schema 断言，覆盖 owner type 和索引约束

## 2. 构建上下文 artifact 保存

- [x] 2.1 增加构建上下文 artifact 类型常量和安全 summary 结构
- [x] 2.2 在 `BuildValidationHandler` 成功构建后检测远端 `compile_commands.json`
- [x] 2.3 通过 SSH/SFTP 下载 compile database 到后端受控临时目录，并校验大小和 JSON 顶层数组
- [x] 2.4 使用 `StoredArtifactService` 保存 compile database 到对象存储，owner type 为 `BUILD_VALIDATION`，owner id 为 `build_runs.id`
- [x] 2.5 将 compile database 可用状态、artifact ID、sha256、size bytes、command count 和来源摘要写入 `build_runs.build_facts`
- [x] 2.6 确保 compile database 缺失、无效、下载失败或对象存储失败时只记录 warning，不改变成功构建状态

## 3. KB 扫描自动复用

- [x] 3.1 实现按 `projectId + sourceRevisionId` 查找最新成功 source/x86 构建上下文的 repository/service 方法
- [x] 3.2 在 `KbScanRuntimeService` 执行 scanner 前解析可用 compile database artifact
- [x] 3.3 下载 compile database 到受控临时文件，并调用 KB Scanner 时传入 `--compile-commands`
- [x] 3.4 在无可用上下文、artifact 下载失败或内容不可用时降级为源码上下文扫描
- [x] 3.5 将 `compileCommands` 使用状态、来源 build run、artifact ID、sha256、command count 或降级原因写入 `kb_scan_runs.summary`
- [x] 3.6 确保 KB 扫描结束后清理临时 compile database 文件，且日志、summary、artifact 响应不暴露真实路径

## 4. API 响应与文档

- [x] 4.1 更新构建详情响应，返回 compile database 安全摘要
- [x] 4.2 更新 KB 扫描详情响应，返回 compile database 使用摘要
- [x] 4.3 更新 `docs/API_DESIGN.md` 中构建和 KB 扫描相关接口说明
- [x] 4.4 更新 README 或开发文档中 KB 扫描自动复用构建上下文的说明，如现有文档已有对应章节则只补充最小内容

## 5. 测试

- [x] 5.1 补充构建上下文保存单元测试，覆盖正常流程、缺失文件、非法 JSON、超限文件和对象存储失败
- [x] 5.2 补充 KB 扫描运行时单元测试，覆盖自动传入 `--compile-commands`、无上下文降级、artifact 下载失败降级和源码版本隔离
- [x] 5.3 补充 API 层测试，覆盖构建详情和 KB 扫描详情的安全摘要字段及无权限访问
- [x] 5.4 补充 E2E case：source-only 构建生成 `compile_commands.json` 后，KB 扫描不传参数但 summary 显示 `compileCommands.mode=USED`
- [x] 5.5 补充 E2E 降级 case：构建未生成 compile database 时 KB 扫描不失败且 summary 表达 `NOT_AVAILABLE`
- [x] 5.6 确保 E2E 清理项目、源码版本、部署运行、构建运行、KB scan、findings、tasks、stored artifacts 和对象存储测试对象

## 6. 验证

- [x] 6.1 运行相关 Java 单元测试
- [x] 6.2 运行 KB 模块和构建/依赖相关 E2E
- [x] 6.3 运行 `openspec validate add-build-context-artifact-for-kb-scan --strict`
- [x] 6.4 运行 `openspec validate --specs --strict`
