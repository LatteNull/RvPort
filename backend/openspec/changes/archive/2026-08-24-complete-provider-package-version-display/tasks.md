## 1. 数据模型和生成代码

- [x] 1.1 盘点 `dependency_analysis_result_items` 当前字段、DTO、JSON artifact 和 HTML artifact，确认 provider/version 字段缺口
- [x] 1.2 设计并新增 Liquibase 迁移，补充源 provider、目标 provider、detected version、provider version status 和 evidence confidence 字段
- [x] 1.3 运行 Liquibase 更新本地 PostgreSQL schema
- [x] 1.4 运行 jOOQ 生成脚本并确认生成代码同步 schema
- [x] 1.5 补充数据库迁移测试，验证新增字段、约束和回滚兼容性

## 2. 源端和目标端 provider 解析

- [x] 2.1 扩展源端 provider resolver，支持构建工具、ELF 和 SO 的 owner package/version 查询
- [x] 2.2 扩展目标端 provider resolver，支持已安装包、软件源、provides/whatprovides 的 provider package/version 查询
- [x] 2.3 实现 ELF/SO 版本探测降级链：SONAME、文件名、symlink、readelf、objdump、strings
- [x] 2.4 实现工具命令 detected version 采样白名单、超时、输出长度限制和脱敏
- [x] 2.5 确保 `.so` 不默认执行 `--version`，并为该行为补充测试

## 3. 版本关系和风险映射

- [x] 3.1 实现 rpm/deb 版本优先解析和宽松 major 版本降级比较
- [x] 3.2 实现 `SAME_MAJOR`、`TARGET_NEWER`、`TARGET_OLDER`、`TARGET_PACKAGE_AVAILABLE_SOURCE_UNOWNED`、`NO_TARGET_VERSION_FOUND`、`UNKNOWN` 状态
- [x] 3.3 将 provider version status 映射到 `INFO`、`LOW`、`HIGH`、`MEDIUM`、`CRITICAL` 或 warning
- [x] 3.4 将版本解析方式、匹配来源和 warning 写入 evidence 摘要
- [x] 3.5 对同一 provider package 的重复 ELF/SO 命中保持聚合，并保留路径 evidence 供详情审计

## 4. API 和制品展示

- [x] 4.1 更新依赖分析列表 API DTO，返回源/目标 provider package/version、detected version、provider version status 和风险等级
- [x] 4.2 更新依赖分析详情 API DTO，返回完整 provider 版本 evidence 且不暴露敏感路径或凭据
- [x] 4.3 更新依赖分析 JSON artifact，输出结构化 provider/version 字段
- [x] 4.4 更新依赖分析 HTML artifact，展示双方软件包名、版本、detected version、版本关系和风险等级
- [x] 4.5 更新真实验证汇总 HTML 脚本，避免只展示单个 provider 名称

## 5. 测试覆盖

- [x] 5.1 补充单元测试正常流程：源/目标都有包且同大版本、目标更高、目标更低
- [x] 5.2 补充单元测试异常流程：源 owner 查询失败、目标 provider 查询失败、版本解析失败、版本命令失败
- [x] 5.3 补充单元测试 edge case：SO 不执行 `--version`、strings 低置信度、同包多 SO 聚合、目标源可用但未安装
- [x] 5.4 补充依赖分析 E2E，验证 API 列表、详情、JSON artifact 和 HTML artifact 均返回 provider/version 字段
- [x] 5.5 补充 E2E 敏感信息检查，确认响应和 artifact 不泄露凭据、私钥、token、服务器真实路径或完整远端日志

## 6. 验证

- [x] 6.1 运行相关单元测试
- [x] 6.2 运行 `mvn test`
- [x] 6.3 运行依赖分析 E2E 模块
- [x] 6.4 重新构建 backend Docker 容器并确认应用启动
- [x] 6.5 使用 make、cmake、ninja、rpmbuild 四个真实项目重新跑依赖分析
- [x] 6.6 生成轻量 HTML 汇总，人工确认页面展示源/目标包名、版本、detected version 和版本关系
- [x] 6.7 运行 `openspec validate complete-provider-package-version-display --strict`
- [x] 6.8 运行 `openspec validate --specs --strict`
