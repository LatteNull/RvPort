## 1. 固化故障基线与测试边界

- [x] 1.1 在测试清单中登记本 change 修改或新增的源位置、Tree-sitter adapter、enum selection 模块及其隔离单元测试，固定每模块 90% 行覆盖率和 80% 分支覆盖率门禁。
- [x] 1.2 为 cJSON、zlib、libarchive 的最小触发内容和可选完整项目 fixture 记录上游 URL、固定 commit、许可证、文件来源与完整性校验，确保默认测试离线、只读且不执行项目代码。
- [x] 1.3 加入进程级失败基线，能够区分正常退出、超时、信号退出和 exit code 139，并记录三个项目当前触发文件/语法而不把 Python 表面栈误判为根因。

## 2. 实现安全且统一的字节位置索引

- [x] 2.1 新增不可变的每文件 byte-offset 位置索引，使用 line-start 索引和二分查找生成现有 1-based 行号、1-based UTF-8 字节列号及 end-byte SourceSpan，并对无效范围返回受控错误。
- [x] 2.2 为位置索引添加隔离单元测试，覆盖空文件、LF、CRLF、多字节 UTF-8、空行、行首/行尾、EOF、超长单行、负数、逆序和越界输入，并使该模块达到 90% 行/80% 分支覆盖率。
- [x] 2.3 将普通 node、declaration attribute、宏 token/range、枚举 declaration/reference/guard 和 ERROR/MISSING Diagnostic 的位置计算全部迁移到统一索引，删除生产 C/C++ Frontend 对 `start_point`/`end_point` 的读取。
- [x] 2.4 使用 Point getter 会抛出异常的 fake Node 为 adapter 添加隔离单元测试，分别覆盖正常 Evidence、宏附件、枚举 guard 和 partial parse 路径，并使修改后的 adapter 达到 90% 行/80% 分支覆盖率。

## 3. 收敛 Tree-sitter 对象生命周期

- [x] 3.1 重构单文件 parse session，在全部遍历期间保持 Tree 强引用，不再持久化整棵树的 Node tuple，并只用 Python 自有的字符串、整数、byte range、稳定 ID 与 core DTO 跨 pass/返回。
- [x] 3.2 为 parser/Tree/Node 生命周期和异常降级添加 fake/mock 单元测试，断言 Node/Tree 不进入 `_ParseCandidate`、FrontendSnapshot、Evidence 或 Diagnostic，并覆盖多 grammar candidate、partial 和失败状态。
- [x] 3.3 更新测试清单和模块覆盖命令，使生命周期相关业务分支参与独立 frontend unit gate，而不依赖真实 Tree-sitter 集成测试获得覆盖率。

## 4. 修复架构枚举选择 Evidence 边界

- [x] 4.1 从通用 node-kind 提取中移除所有 condition clause/case statement 的无条件 selection 映射，保留 enum declaration/member/reference 的局部符号绑定与 partial/ambiguous 状态。
- [x] 4.2 实现由已绑定 enum member reference 驱动的 guard 提取与去重，用 byte range 定位并显式关联 reference Evidence ID，保持 `Backend::avx2` 的 declaration → member → reference → condition 链路。
- [x] 4.3 添加隔离负例单元测试，验证 `case '0'`、`case 0`、无可验证 enum 绑定的状态常量和普通 if 不产生 selection Evidence 或架构枚举链。
- [x] 4.4 添加隔离正例/降级单元测试，验证 C++ `if constexpr (B == Backend::avx2)`、C enum switch、重名/跨文件 ambiguous candidate、ERROR/MISSING 恢复的 Evidence、关系、位置和确定排序，并达到相关模块 90% 行/80% 分支覆盖率。

## 5. 加固独立测试容器与真实项目门禁

- [x] 5.1 在 `kb-scanner-test` 中增加 Tree-sitter binding、C/C++ grammar package 版本和 ABI 范围审计；不修改宿主机依赖、根 Compose、生产镜像或后端，并把 0.25.2 仅记录为应急回退而非目标依赖。
- [x] 5.2 在独立容器中运行三个固定项目的 Tree-sitter-only 子进程扫描，断言无 signal/139、exit 0、全部预期文件被处理且三个正式 artifact 可解析。
- [x] 5.3 为真实项目固定宽松墙钟预算、Evidence 数量上限和误采集断言，确保 cJSON 字符 case、zlib 状态分支和 libarchive 数字 case 不恢复为宽泛 selection Evidence。
- [x] 5.4 为容器审计、进程结果分类和回归 fixture loader/runner 添加对应隔离单元测试与测试清单映射；对新增业务模块执行 90% 行/80% 分支覆盖率门禁。

## 6. 验证兼容合同与完整回归

- [x] 6.1 在三个项目和既有 AVX/架构枚举 fixture 上验证 Schema V2 仍为默认、显式 V1 仍兼容，`scan-result.json`、`scan-report.html`、`scan.log` 仍为唯一正式 artifact，且不需要后端变更。
- [x] 6.2 运行知识资产防变更检查，确认 Clang/GCC x86 事实 JSON 的内容与既有 SHA-256 完全不变，并验证静态分析没有执行配置、编译、链接、测试或项目命令。
- [x] 6.3 通过专属 `compose.test.yml` 依次运行本 change 的隔离 unit/coverage gate、Frontend/parser/component、Evidence Graph、Detector、V2/V1 contract、三个真实项目和全量回归；保存版本、ABI、耗时、Evidence 数量和测试结果作为验收证据。
- [x] 6.4 更新 KB Scanner 测试/维护文档，说明 byte-position 合同、Point 禁用原则、enum selection 边界、真实项目复现方式、临时依赖回滚限制，以及 parser 子进程隔离属于后续 change。
