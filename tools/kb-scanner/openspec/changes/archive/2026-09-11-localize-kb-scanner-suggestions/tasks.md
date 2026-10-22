## 1. 冻结基线与测试范围

- [x] 1.1 在独立 kb-scanner-test 容器冻结当前默认 V2/显式 V1、中文 HTML 展示入口、建议模板及 GCC/Clang 事实哈希，确定只允许两个建议字段变化的逐字段对照基线；不改写旧样例。
- [x] 1.2 为 suggestions、mapper、models、producer 校验接线及复用 renderer 登记隔离 unit suite、fake/mock 边界与人工文案预期；接入现有整体及每个受影响模块 90% 行/90% 分支自动化门禁，统计纳入未加载的 kb_scanner/scripts/tools 源码，不降低或缩小范围。

## 2. 成对建议策略与生产映射

- [x] 2.1 实现 V2 独立纯展示 suggestions 模块，同键返回中文/英文非空文案；补隔离单测覆盖全部模板、技术标识、未知类型和缺少 observation 的保守兜底，无在线翻译、V1 依赖或额外图查询。
- [x] 2.2 实现基于已有 conclusion status/impact/findingType 的优先级，覆盖 unknown/partial/ambiguous、inactive、hint、blocking、局部非阻断与选择/测试缺口；逐语言断言不升级候选、不宣称执行编译/测试、不把所有未知项称作 codec。
- [x] 2.3 将 mapper 接入成对建议，保证 suggestion 固定中文、suggestion_en 固定英文，不因 locale 交换；用 fake index/chain/context 的 mapper 单测证明其余 conclusion、ID、occurrence 和证据链不变。
- [x] 2.4 在独立容器运行建议与 mapper 隔离测试/逐模块覆盖，确认正常、边界、异常路径均有有效断言；未达 90/90 不完成本阶段。

## 3. V2 模型与新旧生产读取合同

- [x] 3.1 更新 Conclusion 模型及 Schema/vocabulary，使历史可省略 suggestion_en，显式 null/空白/错误类型被一致拒绝；补模型隔离单测，验证旧英文 suggestion 仍可读取、往返不补空值、核心额外字段仍被拒绝。
- [x] 3.2 接入新 producer 的双语必填校验并与历史 reader 分离；为实际修改的 validator/projector 模块补 fake mapper/publisher 隔离单测，验证遗漏英文或空白建议不会发布半套 artifact。
- [x] 3.3 保留旧 V2 样例作为读取兼容测试，补当前双语正例、历史缺省、非法值和生产遗漏反例；人工冻结语言语义，不用生成结果自动充当真值。
- [x] 3.4 在独立容器运行 models/validator/projector 逐模块单元门禁，再单独运行真实 JSON Schema/引用合同验证；确认历史 reader 宽容不等于当前 producer 可遗漏。

## 4. 中文展示与结果不变性

- [x] 4.1 用 renderer 独立单测验证新 JSON 双语、HTML 默认中文、UTF-8/HTML 转义和历史缺省读取；优先复用现有 renderer，必要业务修改必须同步登记测试和 90/90 覆盖。
- [x] 4.2 加入默认/非默认 locale 的组件对照及 unknown、inactive、hint、RPM 软依赖、enum、Make/test 缺口代表样例，证明两种语言传递相同确定程度，且未改标题/原因/诊断等非目标文案。
- [x] 4.3 完成固定 snapshots/输入差异账本：仅 suggestion 与 suggestion_en 可以变化，其他 V2 字段、源码链及上下文全等，V1 全字段/规范化哈希、scan.log 和两份 compiler JSON 哈希不变；按批准差异更新 current-producer golden，不覆盖历史基线。
- [x] 4.4 在独立容器执行上述组件/合同测试，确认默认 V2、显式 V1、三个 artifact 及原子发布不变，不扫描或修改其他任务目录。

## 5. 完整验收与文档交付

- [x] 5.1 在独立容器实际运行整体隔离覆盖门禁及全部受影响模块门禁，使整体和逐模块均达到至少 90% 行/90% 分支；保留 summary、完整行/分支数据及 HTML 报告，报告统计范围、排除理由与无分支指标，不用集成数量抵充覆盖。
- [x] 5.2 运行既有完整回归及受影响 schema/enum/候选门禁，涵盖 AVX、RPM、候选保守性和 V1；失败或覆盖不足时保持相关任务未完成，历史大范围缺口需用户另行授权。
- [x] 5.3 更新消费者迁移与建议验收记录，说明新 producer 双语必填、新 reader 接受历史省略、旧严格 reader 须升级；记录实际测试命令/结果/覆盖路径、允许字段差异及不变哈希，不修改后端/前端或生产容器。
- [x] 5.4 在 tools/kb-scanner 根严格验证 OpenSpec、检查文档格式/链接及文件范围；仅全部实施与验证完成后提供实际 change 的 sync/archive 下一阶段命令，不自动同步归档、commit/push 或部署。
