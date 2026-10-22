# 验证记录（2026-09-14）

## 范围与不变项

- OpenSpec 根：`D:/projects/RvPort/tools/kb-scanner`，本 change 仅修改 scanner 自有实现/测试/文档。
- 用户最终约束优先：未新增 CLI、manifest 输入协议或后端接入；默认 V2、显式 V1 与三个 artifact 不变。
- 未安装宿主机 scanner 依赖，未更新生产镜像/Compose/后端容器，未 commit/push/sync/archive；其他任务的 `tools/memory-order-analyzer/` 未触碰。
- 所有 scanner 测试使用已有独立镜像 `rvport-kb-scanner-test:local`，ID `sha256:6239c14ed91b006edb5e6298348deb19cd60f87aa9b3bb85043db35767e5e05a`。源码/输入只读、禁网络、cap-drop ALL、no-new-privileges，临时目录仅 /tmp、产物仅 /out。
- 当前工作树基线 HEAD：`1b693f666201af80090400ce8be5c6aaa2380fcd`；最近 scanner 提交 `7129fe9e35ebb4acde6d126fe073311281e7783c`。

## 单元测试与覆盖率

基线：493 个隔离 unit 通过；129 个文件，行 97.8292%、分支 93.3957%。最终：522 个隔离 unit 通过，135 个文件，整体行 **97.9296%**、分支 **93.7880%**；所有 inventory 模块均达到 90/90。

| 本次新增/直接受影响模块 | 行 % | 分支 % |
| --- | ---: | ---: |
| autoconf/syntax.py | 100 | 100 |
| autoconf/values.py | 100 | 100 |
| autoconf/flow.py | 98.3051 | 96.5278 |
| autoconf/project.py | 100 | 98.6111 |
| analyzers/autoconf_selection.py | 100 | 100 |
| frontends/build/frontend.py | 97.8261 | 93.75 |
| frontends/build/workspace.py | 100 | 100 |
| normalization/build.py | 100 | 100 |
| analyzers/build_selection.py | 99.1379 | 95.9184 |
| detectors/build_selection.py | 95.5224 | 93.75 |
| classifiers/policy.py | 98.3871 | 97.5 |
| projection/v2/mapper.py | 96.6667 | 100 |
| projection/v2/chain.py | 98.9247 | 97.5 |
| 复用 build/adapters.py | 95.6098 | 91.6667 |
| 复用 build/vocabulary.py、core/ids.py | 100 | 100 |

统计包括未加载的全部 `kb_scanner` / `scripts` / `tools` 自有源码；`exclude_lines=[]`。无分支文件的分支指标为不适用。测试/fixtures、非部署 archive、纯规则数据和容器第三方依赖排除，理由见 inventory；未缩小业务分母。C/C++、Make、Bash/Autoconf/RPM 原生解析在 unit gate 使用 fakes；真实 grammar/CLI 另列组件。保留历史 runpy warning，不影响断言与覆盖结果。

报告根：`D:/projects/RvPort/.codex-tmp/autoconf-target-support-20260914`。

- 基线：`before-unit/summary.json`、`coverage.json`、`html/index.html`。
- 最终门禁：`unit-final-accepted/summary.json`、`coverage.json`、`html/index.html`。
- 中间失败记录保留：unit-pass-2 的 fake index 缺失字段已修正；没有把失败轮次当成最终通过。

## 可复制命令

以下是 PowerShell 终端命令，工作目录为 `D:/projects/RvPort`；不安装依赖或重建镜像。

```powershell
$taskDocker = @('run','--rm','--network','none','--read-only','--tmpfs','/tmp:size=512m,mode=1777','--cap-drop','ALL','--security-opt','no-new-privileges:true','--mount','type=bind,source=D:/projects/RvPort/tools/kb-scanner,target=/workspace/tools/kb-scanner,readonly','--mount','type=bind,source=D:/projects/RvPort/.codex-tmp/autoconf-target-support-20260914,target=/out','--env','PYTHONDONTWRITEBYTECODE=1')
docker @taskDocker rvport-kb-scanner-test:local tests/run_source_chain_unit_tests.py --output /out/unit-final-accepted
docker @taskDocker rvport-kb-scanner-test:local -m unittest tests.test_autoconf_target_component -v
docker @taskDocker --mount 'type=bind,source=D:/projects/RvPort/backend/runtime/kb-scan-real/avx-avx2-example-code,target=/fixtures/avx-avx2-example-code,readonly' rvport-kb-scanner-test:local tests/run_container_tests.py --regression-only
docker @taskDocker rvport-kb-scanner-test:local -m kb_scanner scan --input tests/fixtures/autoconf-target/bound-rejection --rules rulesets/riscv-porting --output /out/bound-rejection-v2
docker @taskDocker rvport-kb-scanner-test:local -m kb_scanner scan --input tests/fixtures/autoconf-target/gnu --rules rulesets/riscv-porting --output /out/gnu-v2
docker @taskDocker --mount 'type=bind,source=D:/projects/RvPort/.codex-tmp/kbscanner-sources-clean-20260909/libarchive,target=/inputs/libarchive,readonly' rvport-kb-scanner-test:local -m tests.performance.child /inputs/libarchive /out/libarchive-accepted
```

运行中用 `--entrypoint sh ... -c 'python ... > /out/...log 2>&1'` 持久化完整回归、组件与性能事件日志；执行的是测试入口，不执行被扫描项目。

## 人工 oracle、合同与差异审校

- `autoconf-components-final.log`：4 个真实 grammar / pipeline 组件测试通过（含 12 个独立小型语义案例、固定 GNU/真实 M4、V1/V2、x86 compile database 隔离、只读/禁执行断言）。单元另测语法/值/控制流/调用/配置单元/越界/预算与投影。
- `bound-rejection-v2/scan-result.json`：唯一 Finding 位于 configure，`autoconf-explicit-rejection`，非阻塞；跨 configure → config.guess → uname → config.sub → 拒绝/退出，15 个源码 step，链 complete，没有 classification/assessment。辅助文件已绑定时不重复报告“假设参数未绑定”的 unknown。
- 原生组件断言包含源码前后各 20 行、高亮、schema/reference 校验、中文 suggestion / 英文 suggestion_en、三个 artifact 与 V1 无 evidenceChain 合同。
- `gnu-v2/`：固定旧/新 GNU 四个脚本都是 unknown。新版 riscv 分支存在并不证明外部命令与 libc/目标条件；旧版缺字面也不单独证明拒绝。原始全文、GPLv3/附加许可、来源提交、SHA-256 与人工解释在 `tests/fixtures/autoconf-target/`，扫描期间无网络/项目执行。
- libarchive 固定源码提交 `c4cfba676d2b86d6a2a7c508cd90a75c4dfaa1d9`；configure.ac:26 的 AUX_DIR 和 :92 的无括号 canonical 已识别，缺失辅助文件不能当作目标不支持。
- 首轮完整回归 229 项中，仅 build-selection / workspace-escape 两个共用样例的历史 staged signature 不一致。人工确认新增的唯一项是 configure.ac:1 缺少 helper pair 的 unknown；原 6 项保留，blocking/actionable 仍为 4。仅更新这两项 golden 与差异账本，不改 legacy golden 或其他样例。
- 证明路径预算先被其他构建输入耗尽时，Autoconf 仍在关系预算内保留未知源码边；不创建额外完整 ProofPath，不丢弃 unknown Finding。单元覆盖 max_paths=0 和显式拒绝降级。

最终完整回归：`regression-accepted.log`，**229 项全部通过，258.795 秒，退出码 0**。覆盖 AVX/RPM/枚举/候选、原生崩溃、源码链、双语、V1/V2 与本次真实 grammar 组件。

### libarchive 全项目前后对比

同一只读输入（810 个文件）、同一独立镜像与规则字节下的实测：

| 指标 | 基线 | 本次最终实现 |
| --- | ---: | ---: |
| 原始 facts 总数 | 154137 | 154139 |
| Findings | 58 | 59 |
| 各阶段累计耗时（秒） | 160.0655 | 162.1465 |
| 峰值 RSS（KiB） | 633588 | 626228 |
| 退出码 | 0 | 0 |

按稳定 Finding ID 对比：原有 **58 项完整 JSON 内容均未改变**，只新增 `configure.ac:92` 的 `AC_CANONICAL_HOST` 提示，reason 为 `autoconf-helper-pair-unavailable`，status 为 unknown、blocking/actionable 均为 false。这是未输入辅助文件的证据缺失，不是“不支持 RISC-V”。新增两条声明事实，既有 M4 原始事实继续保留。新增提示含上下各 20 行及双语建议。

最终图包含 137091 条关系、4098 条总证明路径；Autoconf 没有在其他分析已用完分配路径预算时额外创建完整证明。预算边界回归和全项目结果共同确认：保留 unknown，而不生成无依据的拒绝。

产物：`libarchive-before/`、`libarchive-accepted/` 中的 JSON/HTML/log；阶段事件和资源分别在 `libarchive-before.events.jsonl`、`libarchive-accepted.events.jsonl`。基线由初始 HEAD 的 `git archive` 导出至临时目录；为避免归档 LF 与现有知识清单 CRLF 的摘要差异，仅测试入口使用同一只读 `/rules` 挂载，未修改生产源码/规则。单次运行且与其他验证共享宿主资源，以上时长仅作验收记录，不据此宣称性能提升或回退。

## 冻结哈希

下列文件未修改（字节哈希，包括 V2 schema/词汇/引用规则）；V1 继续通过既有 output-contract-baseline 与 schemaVersion=1.0 组件合同验收，不伪造单独的 V1 JSON schema 文件。

| 文件 | SHA-256 |
| --- | --- |
| generated/clang-x86-entries.json | adf187416c006b120e43f2d2ce0677ee2104a4c27de4dd9cabd1df12add352f7 |
| generated/gcc-x86-entries.json | 89775341ee880b13ac4f10a30558ff5d52875b25a3233114a5765601f0a9dad9 |
| schemas/scan-result-v2.schema.json | 2583aaa78094eae3577ecdfcaf4d22c21030990563b77a57d9fece05aa643637 |
| schemas/scan-result-v2-vocabulary.json | 592215e9f885d5efbf16a32b0d9f6cc5d74ce360f8d9d6d1b338aa5b430d0eb8 |
| schemas/scan-result-v2-reference-rules.json | 8211bbf5f76efa254e39ee77e3ebefab008ace5aef74cffc6ff8c82fdc6b3614 |

## 格式与 OpenSpec

`openspec validate implement-kb-scanner-autoconf-target-support --strict` 在 scanner 根执行通过。`git diff --check -- tools/kb-scanner`、新增自有代码尾随空白检查、inventory 源码/测试路径与本次 README/文档本地链接检查通过。冻结 schema/知识哈希再次一致；GNU 第三方样例保持上游字节，不做格式重写。纯文档和固定第三方数据不虚构代码覆盖率。同步/归档、commit/push 和部署均留待用户下一阶段授权。
