# 验证语料与性能基线

[English](validation.md) | 简体中文

以下 Python/Make 命令仅在 Docker 开发容器内执行；构建入口见工具 README。历史接受基线与本次运行报告分开保存，不由测试自动重写 oracle。

<a id="doc-validation-corpus"></a>

## 固定输入与独立预期

归约粒度的当前源码验收使用 `tests/fixtures/validation/reduction-granularity-oracle-v1.json`
与 `tests/integration/test_reduction_granularity.py`。预期按源码独立编写，`make integration`
执行真实 Clang 扫描并导出 `artifacts/validation/reduction-*-observed.json`，覆盖独立循环、
同循环独立累加器、抑制、冷暖缓存及匹配/无关 IR。单元测试另外覆盖负例、unknown、failed、
歧义与预算。本报告不能代替十规则完整语料的 precision/recall 验收。

`make validation` 先执行 `corpus_runner`，再评分。输入为
`tests/fixtures/validation/executable-inputs-v1.json`，预期为独立编写的
`executable-corpus-v1.json`。182 个输入都包含真实 C/C++ 源码；运行器在独立临时目录中使用
锁定的 Clang 扫描，需要 IR 的 case 当场生成共享 bitcode 并进入正式证据流水线。
libm overlay 明确为测试契约，不宣称代表真实平台运行库。运行器不读取 oracle。

评分比较全部候选状态、结果位置与重数、affectedCount、诊断、扫描状态和抑制审计数量。
状态混合时先报告 matched，但仍精确比较完整 assessment 状态多重集，不能隐藏 unknown。
位置 key 为 `文件:行#同一行第几个结果`，避免依赖实现生成的 Finding 哈希；列、引用归属、
置信度和稳定身份另外由单元/契约测试严格验证。重复输出计入 FP，不能经集合去重消失。

`artifacts/validation/current-observed.json` 记录当前源码/协议资源与每个输入的摘要，
`artifacts/validation/cases/` 保留各 case 的完整结果 v2；评分器拒绝源码摘要、输入摘要或
case 集合不一致的 observed。命令失败立即阻止门禁，不用旧报告继续评分。
历史 `reviewed-corpus-v1.json` / `reviewed-observed-v1.json` 原样保留为旧评分器回归基线，
不再作为交付准确率证据。新预期及修订理由纳入正常代码审查；不声称已完成人工批准，
禁止运行后自动回填 oracle。

十条规则各包含至少 6 个正例、6 个反例和 3 个 unknown/unsupported case，并覆盖 C11、C17、
C++17、C++20、x86/RISC-V profiles、AST-only、共享 BC、AST↔IR evidence、suppression、预算及
异常生命周期。strict recall 把本应判断的正例 abstain 计入 FN；supported-only 只排除 oracle
明确声明不支持的 case；零分母输出 `null`。

```text
make validation
python -m floating_point_precision_scanner.corpus_runner --inputs tests/fixtures/validation/executable-inputs-v1.json --output artifacts/validation/current-observed.json
python -m floating_point_precision_scanner.validation --corpus tests/fixtures/validation/executable-corpus-v1.json --observed artifacts/validation/current-observed.json --output artifacts/validation/validation-result.json
```

每条规则 strict precision/recall 必须至少 90%，整体 exact match 至少 95%，lifecycle case 必须
100% exact。报告按 case/rule 稳定排序，并记录 corpus、oracle、tool 和协议版本摘要。

`repair-floating-point-evidence-pipeline` 不新增规则或改写 oracle 真值，只增加证据边界回归族：
Clang 虚拟位置、系统数学头、项目宏/头、typedef/auto、指针/函数指针/容器、真实类型缺失、同 TU
matched+unknown、系统 long-double 洪泛、真实多 ABI 边界、旧 facts 缓存和 AST-only。质量指标不得
通过删除 unknown、改变支持分母或隐藏诊断提高；candidate scope/rule version 改变后应显式更新
review revision 与观察集。

<a id="doc-benchmark"></a>

## 固定性能基线

benchmark 只在 `Dockerfile.dev` 锁定的 Linux/amd64、Clang/LLVM 21.1.8、4 vCPU、4 GiB、禁网
环境中验收。S/M/L 分别固定 20/100/500 个 TU 和约 10k/50k/250k 源码行；每个 TU 含一个
可分析浮点函数及确定性源码填充。每档运行三次冷缓存、三次热缓存并取中位数，另在不同绝对
工作区运行一次以验证语义身份不依赖 materialization path。

绝对门禁为冷缓存 wall 60/240/900 秒、CPU 180/720/2700 秒、RSS 1.5/2.5/3.5 GiB、结果
16/64/256 MiB。热缓存 wall 不得超过冷缓存 60%；wall、CPU、RSS 相对
`tests/fixtures/benchmark/accepted-baseline-v1.json` 的回退均不得超过 20%。接受基线只能在同一
锁定镜像、相同 workload digest 下由维护者审阅更新。

```text
docker build -f Dockerfile.dev -t rvport-fp-scanner:validate .
docker run --rm --cpus=4 --memory=4g --network=none -v <artifact-dir>:/workspace/artifacts rvport-fp-scanner:validate sh -lc "make benchmark"
```

若环境资源不足，报告必须标记 `environment_applicable=false` 且门禁失败，不得换用宽松阈值。
报告保存在 `artifacts/benchmark/benchmark-result.json`。确定性比较直接使用结果 v2 的
`scan.semanticDigest`；实际 wall/CPU/RSS、cache 热冷计数和双语展示文本不进入该摘要，也不影响
finding/evidence-chain identity。

本次证据加固不调整 S/M/L workload 或资源预算。facts 1.4 首次运行允许因旧缓存安全 miss 形成
冷缓存重算，但新版本第二次热运行仍必须满足既有 60% wall 比例，并与冷运行语义等价。新增的
候选级 assessment 数量纳入结果大小和 rule-assessment 预算，不得通过聚合丢失 matched/unknown
分母，也不得为通过 benchmark 隐藏诊断。
