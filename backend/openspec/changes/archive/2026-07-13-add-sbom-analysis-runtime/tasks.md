## 1. 范围与配置

- [x] 1.1 确认本 change 允许实现根目录 `tools/sbom-analyzer`，如 OpenSpec edit root 限制阻断则先调整规划范围或获得特别授权
- [x] 1.2 增加 SBOM 分析器配置项，包括可执行文件路径、工作目录、超时时间和输出大小限制
- [x] 1.3 检查现有 Liquibase schema 是否足够承载 SBOM 运行结果，只有确认缺字段时才新增迁移并重新运行 jOOQ codegen

## 2. 环境采集增强

- [x] 2.1 扩展 `ENV_COLLECT` 内置脚本，采集已安装包、已安装库、基础工具版本和 native/so 文件摘要
- [x] 2.2 为 `TARGET_RISCV` 环境增加仓库可用包和 provides/so 能力采集，并记录无法采集时的解析警告
- [x] 2.3 将采集结果写入 `environment_components`，统一 `source` 值为 `INSTALLED_PACKAGE`、`INSTALLED_LIBRARY`、`TOOL_VERSION`、`NATIVE_FILE`、`REPOSITORY_PACKAGE`、`REPOSITORY_PROVIDE`
- [x] 2.4 确保环境采集日志、事件和 API 摘要不暴露凭据、敏感路径或用户 home 文件内容
- [x] 2.5 补充环境采集单元测试，覆盖正常流程、异常流程和 edge case

## 3. 独立 SBOM 分析器

- [x] 3.1 在根目录 `tools/sbom-analyzer` 创建独立 CLI 工具结构、README 和示例输入输出
- [x] 3.2 实现分析器输入 JSON 解析和 schema version 校验
- [x] 3.3 实现源侧组件与目标已安装组件、目标仓库组件的匹配逻辑
- [x] 3.4 生成 `TARGET_PRESENT`、`DIRECT_AVAILABLE`、`UPGRADE_AVAILABLE`、`SOURCE_BUILD_REQUIRED`、`NO_ALTERNATIVE`、`MANUAL_CONFIRM_REQUIRED` 替代结论
- [x] 3.5 实现分析器输出 JSON、退出码、stdout/stderr 和错误摘要约定
- [x] 3.6 补充分析器测试，覆盖正常流程、异常流程和 edge case

## 4. Java SBOM Runtime

- [x] 4.1 新增 `cn.rvport.backend.sbom` 包结构和 repository/service/runtime 基础类
- [x] 4.2 实现 SBOM 分析任务创建逻辑，校验项目访问、环境归属、快照归属和输入参数
- [x] 4.3 注册 `SBOM_ANALYSIS` 任务类型和 worker handler
- [x] 4.4 实现分析器输入导出，不包含明文凭据、服务器真实路径或完整任务日志
- [x] 4.5 实现受控进程调用分析器，保存 `tool_runs`、stdout/stderr 任务日志和安全摘要
- [x] 4.6 实现分析器结果解析、版本校验和输出大小限制
- [x] 4.7 将成功结果导入 `sbom_runs`、`sbom_components` 和 `replacement_candidates`
- [x] 4.8 确保失败路径不会写入成功态结果，且不会改变历史 SBOM 运行事实
- [x] 4.9 通过任务执行上下文写入进度事件、日志摘要和终态事件，确保项目级 SSE 可观察

## 5. SBOM API

- [x] 5.1 实现 `POST /api/projects/{projectId}/sbom-analyses`
- [x] 5.2 实现 `GET /api/projects/{projectId}/sbom-analyses`
- [x] 5.3 实现 `GET /api/sbom-analyses/{analysisId}`
- [x] 5.4 实现 `GET /api/sbom-analyses/{analysisId}/components`，支持风险、替代结论、名称和类型筛选
- [x] 5.5 实现 `GET /api/sbom-analyses/{analysisId}/collection-detail`
- [x] 5.6 确保所有 SBOM API 执行项目访问守卫，越权时返回安全错误且不暴露资源存在性
- [x] 5.7 暂不实现 `POST /api/sbom-analyses/{analysisId}/components:add-to-issues`，如保留路由则返回明确未实现

## 6. 测试与验证

- [x] 6.1 补充 Java 单元测试，覆盖 SBOM service、runtime、handler、repository 映射和权限校验
- [x] 6.2 补充 API E2E 测试，覆盖登录、创建项目、创建环境快照、创建 SBOM 分析、等待任务完成、查询列表、详情、组件和采集详情
- [x] 6.3 补充越权 E2E 测试，验证普通用户不能访问其他用户项目的 SBOM 分析和组件结果
- [x] 6.4 补充异常 E2E 测试，覆盖快照不存在、环境不属于项目、分析器失败和输出 JSON 无效
- [x] 6.5 运行 Maven 单元测试、分析器测试和 API E2E，并记录实际结果
- [x] 6.6 验证任务 SSE 能收到 SBOM_ANALYSIS 的进度和终态事件

## 7. 文档与收尾

- [x] 7.1 更新 `backend/docs/API_DESIGN.md` 中 SBOM API 的请求、响应、权限和 MVP 不包含内容
- [x] 7.2 更新后端 README 或开发说明，记录分析器配置、运行前置条件和本地验证命令
- [x] 7.3 清理临时测试数据、临时分析输入输出和 runtime 工作目录中无用文件
- [x] 7.4 运行 `openspec validate --all`，确认 specs 可归档
