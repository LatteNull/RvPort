## 1. 结果范围收敛

- [x] 1.1 盘点依赖分析结果生成路径，定位 `compile_database_define`、`strace_execve_define`、`compiler_flag_probe`、`compile-db`、`build-ninja` 等结果项来源
- [x] 1.2 修改依赖事实到结果项的转换逻辑，禁止 flag、宏和构建元数据文件本身进入 `dependency_analysis_results`
- [x] 1.3 保留必要的构建元数据 evidence 或日志，确保调试信息不丢失但不进入迁移输入候选
- [x] 1.4 调整建议文案和 locationLabel 生成，避免展示 `define:*`、`compile-db:*`、`build-ninja:*` 等依赖位置

## 2. ELF/SO 源侧 provider 解析

- [x] 2.1 增加或扩展源侧 provider resolver，支持通过包数据库解析 ELF/SO 文件 owner package 和 owner version
- [x] 2.2 对无法解析 owner package 的 ELF/SO，提取 SONAME、库文件名版本、symlink 版本、readelf evidence 和路径 evidence
- [x] 2.3 对本次构建新增产物继续作为排除 evidence，不生成依赖结果项
- [x] 2.4 对源码仓库自带的 ELF/SO 和构建事实中的 `NEEDED`/`SONAME` 继续进入 provider 匹配流程

## 3. 目标 provider 匹配和风险映射

- [x] 3.1 扩展目标侧匹配逻辑，按目标已安装包、目标软件源包、provides/whatprovides、alias 和 normalized package name 查找 target provider
- [x] 3.2 实现 rpm/deb 版本优先解析和宽松 major 版本降级比较
- [x] 3.3 实现 `SAME_MAJOR -> INFO`、`TARGET_NEWER -> LOW`、`TARGET_OLDER -> HIGH`、`TARGET_PACKAGE_AVAILABLE_SOURCE_UNOWNED -> MEDIUM`、`NO_TARGET_VERSION_FOUND -> CRITICAL` 映射
- [x] 3.4 将 source provider、target provider、versionRelation、riskMappingRule 和 matchEvidence 写入结果 evidence
- [x] 3.5 按 source package、target provider 和版本关系对重复 ELF/SO 命中做聚合，并在详情 evidence 中保留完整路径证据

## 4. API、报告和迁移输入展示

- [x] 4.1 调整依赖分析列表和详情 API 响应，返回 provider package 版本匹配字段且不暴露服务器真实路径
- [x] 4.2 调整依赖分析 JSON artifact，输出 provider package 匹配结果和聚合 evidence
- [x] 4.3 调整依赖分析 HTML artifact 和真实验证汇总 HTML，重点展示源包、源版本、目标包、目标版本、版本关系和风险等级
- [x] 4.4 调整迁移输入导入逻辑，使 `detectedLevel` 使用 `riskLevel + "/" + versionRelation`
- [x] 4.5 确认旧 SBOM deprecated 能力不受本 change 破坏

## 5. 测试覆盖

- [x] 5.1 补充单元测试正常流程：源有包且目标同大版本、目标更高、目标更低
- [x] 5.2 补充单元测试异常流程：源 owner 查询失败、目标 provides 查询失败、版本解析失败、目标能力证据不足
- [x] 5.3 补充单元测试 edge case：同包多 SO 聚合、源无 owner 但可提取版本、源无 owner 且目标无版本、跨发行版包名 alias
- [x] 5.4 补充依赖分析 E2E 模块，验证 flag/macro/build metadata 不进入结果列表和制品
- [x] 5.5 补充依赖分析 E2E 模块，验证 ELF/SO provider package 版本匹配、风险映射、分页详情和迁移输入导入

## 6. 验证

- [x] 6.1 运行相关单元测试
- [x] 6.2 运行 `mvn test`
- [x] 6.3 运行依赖分析 E2E 模块
- [x] 6.4 使用 make、cmake、ninja、rpmbuild 真实项目重新跑依赖分析
- [x] 6.5 生成轻量 HTML 汇总，人工确认结果不再包含 flag/macro/build metadata 噪声，并包含 provider package 版本匹配
- [x] 6.6 运行 `openspec validate improve-elf-provider-package-version-matching --strict`
- [x] 6.7 运行 `openspec validate --specs --strict`
