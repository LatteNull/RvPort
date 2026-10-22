## 1. 固化测试基线与分层清单

- [x] 1.1 记录当前 120 项容器测试及其中 38 项 frontend 新增测试的 unit/component/integration/contract 实际分类，明确测试总数不是单元覆盖完成条件。
- [x] 1.2 建立机器可读 frontend test inventory，将 vocabulary、workspace、compilation database、arguments、Tree-sitter adapter、Clang adapter、composite frontend 映射到对应 unit 和适用的高层测试。
- [x] 1.3 增加 inventory 合同测试，双向验证七个正式业务模块、单元测试文件及清单记录，不允许新增模块没有单元测试映射或清单悬空。
- [x] 1.4 固化默认 CLI、legacy 五文件字节、三个 artifact、两份事实 JSON 哈希/六类计数/source 与 YAML `generatedSet` 的 change 起点。

## 2. 建立容器内单元测试与覆盖率入口

- [x] 2.1 在 `requirements/test.lock` 固定 coverage.py 测试专用版本，不修改 runtime lock、生产镜像或宿主机依赖。
- [x] 2.2 创建可独立发现的 `tests/unit/frontends/cpp` unittest 目录结构和共享的 core context、fake、fixture helper，禁止 helper 启动外部命令。
- [x] 2.3 实现测试专用 runner，先单独运行 frontend unit suite 并采集 `kb_scanner/frontends/cpp` 行/分支覆盖，再运行完整回归，两个阶段分别输出结果且任一步失败均非零退出。
- [x] 2.4 将 coverage 数据和 JSON 临时输出限定到容器 `/tmp`，验证只读 workspace 下不会写入 `.coverage`、HTML、JSON 或其他测试产物。
- [x] 2.5 在唯一 `kb-scanner-test` 服务中接入 runner，不新增第二个 Compose 服务，不连接网络/业务凭据，不修改根 Compose 或 `backend/Dockerfile`。
- [x] 2.6 记录补测前逐模块 unit coverage 基线，确认真实 Tree-sitter/libclang 和 staged tests 不计入该数字。

## 3. 补齐 Vocabulary 单元测试

- [x] 3.1 为 `make_source_file_entity` 覆盖语言去重排序、scanner version、POSIX 相对路径和重复调用稳定 ID。
- [x] 3.2 为 `make_evidence` 覆盖全部允许 kind、context/no-context identity、metadata 冻结、producer/parse mode/confidence 与稳定 ID。
- [x] 3.3 覆盖非法 Evidence kind、无效 subject/span 和非 JSON-safe value/metadata 的失败行为。
- [x] 3.4 覆盖 Entity/Evidence 的有位置、无位置、不同 producer/context 和相同 span 情况下的确定性排序键。

## 4. 补齐 Workspace 与 Compilation Database 单元测试

- [x] 4.1 为 workspace suffix/language candidates 建立 C、C++、歧义 header、大小写、不支持后缀和禁用语言的表驱动测试。
- [x] 4.2 覆盖空目录、嵌套 exclude、精确 exclude-path、名称前缀不误排除、重复路径和确定性排序。
- [x] 4.3 使用 mock 精确触发 workspace discovery/read 元数据异常，断言 failed/partial Diagnostic、无绝对路径身份泄漏和其他有效文件保留。
- [x] 4.4 覆盖单文件 symlink、directory symlink/path escape、缺失输入、目录伪装文件及不支持单文件。
- [x] 4.5 为 compilation database 覆盖 root 非数组、非 object entry、缺失/非字符串 file、非标量 arguments、空 command 和 command tokenize 失败。
- [x] 4.6 覆盖相对/绝对 directory/file、paired/joined include 类别、重复 define/undef、language/standard/compiler 和原始 tokens 的确定性解析。
- [x] 4.7 覆盖部分有效、全部无效、不存在 database、workspace 外 source 和同一 source 多 entry 的状态与 Diagnostic 顺序。
- [x] 4.8 覆盖 context identity 的 entry/define/standard/token 差异、Windows/POSIX 路径、project/command/external path redaction，确保机器根路径不影响 ID。

## 5. 补齐 Clang Argument Policy 单元测试

- [x] 5.1 以表驱动方式覆盖全部 safe exact、paired、joined、target/sysroot、standard、define/undef 和已审计 `-m*` 参数。
- [x] 5.2 逐组覆盖 `-Xclang`、plugin/load、response、PCH/module、输出/dependency/diagnostic/trace/save-temps、offload、linker、assembler、未知参数及 paired 缺值。
- [x] 5.3 验证 compiler/source/`-c` 和 driver operands 完整移除，安全与危险参数混合时只保留安全子集且 Diagnostic 顺序确定。
- [x] 5.4 验证 paired/joined 相对路径按 command directory 规范化、绝对路径处理一致，Diagnostic 仅包含 context identity/option 而不泄漏参数值或机器路径。

## 6. 补齐 Tree-sitter Adapter 隔离单元测试

- [x] 6.1 使用 fake/patch 隔离 grammar、Language、Parser 和 package version，验证 C/C++ 初始化、bytes 输入、producer version 与 parser 返回值转换。
- [x] 6.2 精确触发 grammar/version/parser 初始化异常和文件读取异常，断言 failed/partial 状态、affects-exit-code 和结构化 Diagnostic。
- [x] 6.3 覆盖 C/C++ 明确后缀、direct compilation context、同名不同目录 context 不串用、歧义 header 双 grammar 错误评分和固定 tie-break。
- [x] 6.4 使用 fake node 覆盖全部 Evidence kind、字段 value 提取、include 去引号、源码片段截断、source span 行列和 comment 开关。
- [x] 6.5 覆盖 ERROR/MISSING 计数、首错误位置、统一 medium confidence、可恢复 Evidence 和两个 grammar 均 partial 的候选选择。
- [x] 6.6 覆盖同 producer/context 完全重复去重、宏定义祖先不误记为 expansion、普通宏使用 expansion 以及重复执行 ID/顺序一致。

## 7. 补齐 Clang Adapter 隔离单元测试

- [x] 7.1 建立轻量 fake cindex/Index/TranslationUnit/Cursor/Diagnostic/location，并证明可在不加载真实 libclang 的情况下驱动 adapter 控制流；仅在必要时增加行为不变的私有 loader/injection seam。
- [x] 7.2 验证 adapter 只把 normalization 后的参数和 `PARSE_DETAILED_PROCESSING_RECORD` 传给 parse，不调用 compiler executable。
- [x] 7.3 精确触发 cindex import、Index 创建和 translation-unit parse 异常，断言单 TU partial、context identity Diagnostic 与空 enrichment。
- [x] 7.4 覆盖 Clang diagnostic info/warning/error/fatal severity、项目内/外/无文件 location、路径去敏和 has-error confidence/status。
- [x] 7.5 覆盖 macro definition/expansion、include、call/type/template cursor 映射、未知 cursor、无 location、非法/反向 extent 和 workspace 外过滤。
- [x] 7.6 覆盖 include 项目内相对值、外部绝对路径 basename、普通 cursor spelling/displayname fallback 及 JSON-safe metadata。
- [x] 7.7 覆盖游标遍历顺序、同 context 重复去重、不同 context 独立 ID、translation unit 生命周期和一个 TU 失败不影响后续调用。
- [x] 7.8 保留并运行真实 libclang integration tests，确认 fake/seam 没有改变默认 binding、宏 provenance、include 或安全参数行为。

## 8. 补齐 Composite Frontend 单元测试

- [x] 8.1 使用 fake Tree-sitter/Clang adapters 覆盖空 workspace、无 compilation context、不匹配/outside context 和一个 source 多 context 的调用次数与顺序。
- [x] 8.2 覆盖 Tree-sitter complete/partial/failed/no-value 和 Clang complete/partial/unavailable/failed 的整体状态传播，确保允许降级时 baseline 不丢失。
- [x] 8.3 覆盖多文件、多 adapter Diagnostic 的稳定首见顺序和完全重复去重。
- [x] 8.4 覆盖合法 subject、未知 subject、跨 producer 相同事实、同 producer/context 重复及 Entity/Evidence 最终排序。
- [x] 8.5 验证同一个只读 ScanContext/WorkspaceSnapshot 传入所有 adapter，Frontend 不重新解析 CLI、不加载 Knowledge、不产生 Finding/Relation/Observation/Assessment。
- [x] 8.6 保留 staged qualification integration，确认真实 Workspace/Frontend 继续向 downstream 传值、projector 不写 artifact、默认 application 仍为 legacy profile。

## 9. 覆盖率、兼容回归与收尾

- [x] 9.1 使隔离 unit suite 对正式 frontend 包达到行覆盖率至少 90%、分支覆盖率至少 80%，并验证七个业务模块均有 executed lines。
- [x] 9.2 增加低于行门槛、低于分支门槛、模块完全未执行和 inventory 不匹配时 runner 非零退出的自测试。
- [x] 9.3 只在独立 `kb-scanner-test` 容器运行 unit gate 与完整回归，确认原 120 项测试全部保留且新增测试通过。
- [x] 9.4 回归默认 CLI 成功/规则失败/compile context 降级、`schemaVersion: "1.0"`、顶层字段、Finding 关键语义与三个 artifact，确认没有第二主结果。
- [x] 9.5 复核 legacy 五文件字节冻结以及 Clang/GCC 事实 JSON 的哈希、六类计数、source 和全部 `generatedSet` 引用不变。
- [x] 9.6 更新测试与容器文档，分别记录 unit test 数、行/分支覆盖率、component/integration/contract 数和 full regression 总数。
- [x] 9.7 确认未安装宿主机依赖，未修改/构建生产镜像、根 Compose，未执行 compiler、构建、配置、plugin、response、项目测试或真实 RISC-V 编译。
- [x] 9.8 运行 `openspec validate harden-kb-scanner-cpp-frontend-unit-tests --strict` 并修复全部格式和一致性问题。
