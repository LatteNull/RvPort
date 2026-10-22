## 1. 建立回归基线

- [x] 1.1 使用 `demo-test1` 首份依赖分析的数据构造最小回归 fixture，固定源侧 `c++ -> gcc-c++`、目标仅安装 `gcc`、目标仓库提供 `gcc-c++` 的误判场景
- [x] 1.2 增加失败优先的单元测试，证明当前实现会错误返回 `TARGET_INSTALLED/LOW` 并命中 `matchedAlias=gcc`

## 2. 重构工具与 provider 匹配

- [x] 2.1 收敛 `DependencyFactExtractor` 中重复的工具别名定义，建立单一的严格工具和同家族等价工具规则
- [x] 2.2 调整工具提取顺序，在目标匹配前解析源侧工具 owner、provider package、provider version 和编译器家族
- [x] 2.3 扩展目标工具匹配入口，使其按严格同名工具、同家族等价工具、源 provider 已安装包、源 provider 仓库包的顺序解析
- [x] 2.4 删除 `c++/g++ -> gcc` 的错误满足路径，并确保 GCC 与 Clang C++ 家族不会交叉误配
- [x] 2.5 保持实际观测工具名作为 `dependencyName`，同时正确填写源/目标 provider package、版本、匹配证据、状态、风险和推荐信息

## 3. 统一证据与去重行为

- [x] 3.1 让构建命令、compile database、execve summary 和 execve tool 使用统一的 provider-aware 匹配入口
- [x] 3.2 验证多种证据同时观测 `c++` 时只保留一个语义唯一条目，并优先保留高置信度真实执行证据
- [x] 3.3 确认 `compilerBuiltinMacros` 继续只参与宏分类，不会单独创建未被构建使用的工具依赖
- [x] 3.4 验证 `REPO_AVAILABLE/MEDIUM` 的 `gcc-c++` 结果可由现有一键修复候选逻辑正确消费

## 4. 单元测试

- [x] 4.1 覆盖目标已安装 `gcc-c++` 或同家族 C++ 驱动时返回 `TARGET_INSTALLED` 的正常流程
- [x] 4.2 覆盖目标仅安装 `gcc`、仓库提供 `gcc-c++` 时返回 `REPO_AVAILABLE/MEDIUM` 的正常流程
- [x] 4.3 覆盖目标仅安装 `gcc` 且仓库无 C++ provider 时不得判定已满足的异常流程
- [x] 4.4 覆盖源 provider 缺失、GCC/Clang 家族隔离、多证据去重和宏采样不生成依赖等 edge case
- [x] 4.5 回归验证 `cc`、binutils、`ninja`、`rpmbuild`、`configure` 及既有库 provider 匹配规则
- [x] 4.6 所有单元测试 mock 数据库、环境快照和其他 service connection 返回值，不连接 PostgreSQL、Redis、RabbitMQ、MinIO、SSH 或外部 HTTP 服务

## 5. API E2E 与质量验收

- [x] 5.1 扩展独立依赖分析 E2E 模块，通过真实 API、真实 CMake C++ 构建和环境快照验证 `gcc-c++` 仓库候选结果
- [x] 5.2 覆盖目标只有裸 `gcc` 的异常流程、多证据去重 edge case、权限校验及测试数据/制品清理
- [x] 5.3 运行依赖分析相关单元测试和完整后端单元测试，确认全部通过且没有依赖外部服务
- [x] 5.4 运行覆盖率统计并确认项目整体与受影响模块的行覆盖率至少 90%，分支覆盖率至少 90%，报告未加载源码及所有合理排除项
- [x] 5.5 重新构建后端容器，在 `demo-test1` 等价真实环境中重跑依赖分析，确认 `c++` 返回 `gcc-c++` provider、`REPO_AVAILABLE/MEDIUM` 且 API 结果与数据库一致
