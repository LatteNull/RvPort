## 1. 回归基线与验证准备

- [x] 1.1 复核 backend 的 AGENTS、现有事务边界和 KB 结果消费者，记录改动包清单与设计状态矩阵对应的回归用例；确认本次仅操作 backend 独立 OpenSpec 根。
- [x] 1.2 按 design.md 与开发指南准备专用测试容器、数据库、网络、volume、报告目录及资源上限；从当前源码构建测试镜像并取得 backend Java/Python 单元与覆盖率基线，历史缺口超出范围时报告并请求扩大范围。
- [x] 1.3 补充首次上传无构建、同源码切换环境、旧扫描成功但当前构建缺失的失败回归测试，分别断言创建副作用、overview、readiness 与 latest 的预期行为。

## 2. 执行上下文持久化

- [x] 2.1 增加 Liquibase 迁移，保存 source_environment_id、runtime_environment_version、build_run_id，添加外键、全空或完整的约束及上下文查询索引，保持旧数据为空且不回填推测值。
- [x] 2.2 在独立 Docker 数据库验证空库初始化、旧数据升级、重复迁移、约束失败和历史数据保留；容器内生成 jOOQ，导出并审查生成差异。
- [x] 2.3 更新 KB 输入、运行视图、repository 与任务快照映射，同步补充完整上下文、旧空值、部分非法值、归属错误以及查询排序/分页/计数单元测试。

## 3. 构建前置与创建事务

- [x] 3.1 实现共用 KB 上下文解析器，按项目、待扫描源码、源环境、运行环境版本及 SOURCE_ONLY 范围选择构建；补充活动优先、最近终态、时间并列、失败不回退、BOTH 不替代等单元测试。
- [x] 3.2 将 KB readiness 接入同一解析器，覆盖源码/环境/构建缺失，以及排队、运行、失败、取消、超时、成功的 prerequisite 状态与原因码。
- [x] 3.3 在创建入口强制校验并固定构建；保留显式本项目历史源码支持，覆盖跨项目拒绝、工作副本异常和前端旧 readiness 无效的测试。
- [x] 3.4 实现创建事务的一致读取与提交前条件重验或共享锁；补充上下文变化、写入异常和回滚单元测试，断言没有遗留 task、scan run、event 或队列消息，并补充独立数据库并发验证。

## 4. worker 固定输入与证据降级

- [x] 4.1 worker 以运行记录固定上下文为事实源，开始时校验任务快照一致性、构建归属和执行前置；测试旧队列载荷、构建被替代及环境版本变化时不启动 scanner、不导入 findings、不标成功。
- [x] 4.2 compile database 只读取绑定构建，保留 USED、成功构建无数据库的 NOT_AVAILABLE、artifact 异常的 FALLBACK；替换旧“无成功构建也扫描成功”的测试，覆盖缺失 ID、所有权不符、下载/解析失败及脱敏。
- [x] 4.3 测试排队期间仅 active source 切换仍可执行历史源码、运行期间上下文变化保留真实终态但不成为当前结果，以及取消、超时、零 finding 成功等边界。

## 5. 当前结果、overview 与报告一致性

- [x] 5.1 实现统一当前扫描选择与失效原因，接入 KB latest、默认 currentOnly 列表和当前性标记；测试 CURRENT/STALE/EMPTY、旧空上下文、无 active source、当前失败不回退、历史读取与数据隔离。
- [x] 5.2 将 overview 的 KB 状态接入同一结果，保证仅当前有效成功扫描为 DONE，旧结果为 PENDING/KB_SCAN_STALE；将 x86 推荐顺序置于 KB 之前，补充整套状态矩阵单元测试。
- [x] 5.3 统一报告 readiness 的 KB 前置、当前 finding 自动选择和新报告输入解析，阻止隐式复用过期 KB 或历史 confirmed 引用；补充保留旧报告快照与历史确认记录的测试。
- [x] 5.4 增加安全执行上下文/失效原因 DTO 和中文、英文说明；维护控制器序列化、权限、reasonCode、单次响应上下文一致性测试，保持 API 路径、任务枚举和 latest 外壳兼容。

## 6. Docker 单元测试与覆盖率验收

- [x] 6.1 从当前源码重建 backend unit-test 镜像，在专用容器运行完整 Maven clean verify；保留 JaCoCo BUNDLE/PACKAGE 的 LINE 和 BRANCH 均至少 0.90 的自动门槛，确认全部自有 Java 类包括未加载类纳入统计。
- [x] 6.2 导出 Surefire、JaCoCo HTML/XML/CSV 和失败日志到 .migration-reports/fix-kb-scan-workflow-consistency，分别报告整体以及 kb、kb.runtime、workflow、project 和实际受影响的报告/迁移包行、分支覆盖率与 covered/total。
- [x] 6.3 按开发指南在 Docker 运行后端资源 Python 单元测试和全量覆盖率，对整体及每个脚本检查行/分支至少 90%；若修改了其他自有执行代码，同步纳入对应模块完整测试及门槛，不能以 Java 通过替代。
- [x] 6.4 核对生成 jOOQ 和第三方依赖等排除理由，确保没有排除自有业务逻辑或缩小统计分母；任何测试失败、覆盖不足或环境阻塞均保留验收未完成，不以历史报告代替当前源码结果。

## 7. 完整运行验证与阶段交接

- [x] 7.1 从 D:\projects\RvPort 根目录，使用专用 Compose project、测试 env 与资源受限的本地 override 顺序完成完整 Compose build；确认默认服务全部纳入且不连接已有部署数据库或真实 SSH。
- [x] 7.2 以一次 docker compose up -d --wait 启动全部默认服务，检查健康、日志和首次上传无构建时的 API 拒绝/状态一致性；成功扫描与失效路径由已执行单元测试及独立数据库验证提供证据，不新增 E2E 或真实 SSH 支持设施。
- [x] 7.3 更新 backend 范围内中文接口/运维说明，记录 nullable 迁移、旧任务处理、历史结果失效规则和 API/worker 协同升级及回滚步骤；执行内容、链接与 OpenSpec 严格校验。
- [x] 7.4 汇总实际命令、测试数量、退出码、行/分支覆盖率、统计范围、排除理由、报告位置和 Compose 服务结果；只有全部任务及验收通过才提示归档，否则提供继续 apply 或修复验证的完整聊天指令。
