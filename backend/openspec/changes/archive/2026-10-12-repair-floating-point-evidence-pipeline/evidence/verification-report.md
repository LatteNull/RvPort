# 浮点证据链修复验证报告

## 1. 验收结论

`repair-floating-point-evidence-pipeline` 的实现与验证已完成。合法 schema 2.0 共享 BC 已恢复消费，
`demo-test1` 的项目翻译单元分母由历史的 14 个原始命令修正为 3 个项目 C/C++ TU；系统声明、
非标量 conversion、赋值包装、解引用及一元负号不再制造 blocking unknown。AST-only 安全降级、
损坏制品拒绝和真实 `source_mapping_incomplete` 警告仍保留。

本 change 没有新增检测规则，没有修改 frontend 或其他分析工具，也没有修改历史审计结果。

## 2. 固定基线与真实 API 前后对照

固定 before 基线为 `backend/runtime/fp-step-description-validation` 根目录最新结果，明确排除
`first-run`。结构化基线见 `before-baseline.json`。

| 项目 | 修复前 | 修复后 |
|---|---|---|
| analysis | `aee4ef66-6d81-4e88-afd7-606cc7d6cc9a` | `73181be9-97cf-47b5-9fc3-b2de266a7dd8` |
| task | `a7653736-9b55-4b0c-89f1-12fb67c4b0c2` | `fb5ae5b3-43ae-47b5-a922-5452ec31f475` |
| source revision | `a019391f-89e6-4d8e-8eed-1b7871055541` | 相同 |
| build run | `be53c759-1e2e-459a-9f73-ef8289ecfaf2` | 相同 |
| 模式/状态 | `AST_ONLY/PARTIAL` | `AST_BC_COMPLETE/COMPLETE` |
| BC | `INVALID`，0 usable，笼统 worker validation 原因 | `READY`，3/3 usable，无降级原因 |
| TU 口径 | raw/planned 14 | raw 14、C/C++ candidate 5、项目 TU 3 |
| 层计数 | 无 IR/evidence | source、artifact、IR、evidence 均 3/3，unknown 0 |
| 诊断 | provenance budget、3 个 mixed conversion unknown、unsupported facts | 仅 1 个 `source_mapping_incomplete` |
| Finding | 1 个 reduction，`src/vectorcalc.cpp:62` | 相同 external ID、位置、排序与 heuristic origin |
| 退出码 | 4 | 0 |

修复后的 `source_mapping_incomplete` 是部分 LLVM fact 缺少调试源码映射的真实证据边界；它没有被
伪造成 AST↔IR evidence，也没有被隐藏。结果仍使用 AST 证据完成相关规则判断。

真实 API 审计位于 `api-after/`，包含 `task.json`、`run.json`、`result.json`、`findings.json`、
详情、历史 finding 前后快照及 `verification.json`。`historicalUnchanged=true`。

## 3. Backend Linux Docker 单元测试与覆盖率

执行环境：`rvport-backend-quality:local`，测试构建复制到容器 ext4 的 `/tmp/backend`；外部
SSH/SFTP、对象存储、数据库、Redis、RabbitMQ 和进程边界由独立单测 mock。执行命令：

```powershell
docker run --rm --name rvport-backend-evidence-repair-test `
  -v "D:/projects/RvPort:/workspace" `
  -v "rvport-maven-cache:/root/.m2" `
  --entrypoint sh rvport-backend-quality:local -lc `
  "ln -sf /usr/bin/python3 /usr/local/bin/python &&
   mkdir -p /tmp/backend /tmp/tools/kb-scanner /tmp/tools/sbom-analyzer &&
   tar -C /workspace/backend --exclude=target -cf - . | tar -C /tmp/backend -xf - &&
   tar -C /workspace/tools/kb-scanner -cf - . | tar -C /tmp/tools/kb-scanner -xf - &&
   tar -C /workspace/tools/sbom-analyzer -cf - . | tar -C /tmp/tools/sbom-analyzer -xf - &&
   cd /tmp/backend && mvn -B clean verify;
   result=$?;
   mkdir -p /workspace/backend/target/site /workspace/backend/target/surefire-reports;
   if [ -d target/site/jacoco ]; then cp -a target/site/jacoco /workspace/backend/target/site/; fi;
   if [ -d target/surefire-reports ]; then cp -a target/surefire-reports/. /workspace/backend/target/surefire-reports/; fi;
   exit $result"
```

结果：1733 项测试通过，0 failed、0 errors、2 skipped；JaCoCo 所有 bundle/package 门禁通过。

| 统计范围 | 行覆盖率 | 分支覆盖率 |
|---|---:|---:|
| backend 全部项目自有 Java | 96.75% | 90.99% |
| `cn.rvport.backend.analysis` | 96.37% | 90.42% |
| `cn.rvport.backend.buildvalidation.bitcode` | 96.59% | 90.59% |

报告：`backend/target/site/jacoco/jacoco.xml`、`backend/target/site/jacoco/index.html`、
`backend/target/surefire-reports/`。唯一覆盖率排除项是自动生成的 `cn/rvport/backend/jooq/**`；
项目自有业务逻辑未排除。

## 4. Scanner Linux Docker 测试与覆盖率

最终执行命令：

```powershell
docker run --rm --name rvport-fp-evidence-final-verify --network=none --cpus=4 --memory=4g `
  -v "D:/projects/RvPort/tools/floating-point-precision-scanner:/workspace" `
  -w /workspace rvport-fp-scanner:validate sh -lc "make verify-release integration"
```

结果：332 项 Python unit/contract、21 项 C++ unit、26 项 Linux Clang/LLVM integration 全部通过；
ruff 与 mypy 通过。integration 只作补充，没有替代独立单元测试。

| 统计范围 | 行覆盖率 | 分支覆盖率 |
|---|---:|---:|
| 全部项目自有 Python | 97.13% | 93.27% |
| 全部受影响 Python 模块 | 97.54% | 93.75% |
| `facts` | 95.63% | 90.45% |
| `canonical_types` | 100% | 100% |
| `source_locations` | 100% | 100% |
| 全部项目自有 C++ worker | 98.94% | 92.19% |

coverage.py 使用 `source=["src/floating_point_precision_scanner"]` 且 `omit=[]`，因此未被测试加载的
项目源码仍进入分母；只排除静态 `TYPE_CHECKING` 分支。C++ 报告显式统计
`src/cpp/ir_facts.cpp` 与 `src/cpp/ir_worker.cpp`，无项目源码排除。

报告：`tools/floating-point-precision-scanner/artifacts/coverage/coverage.json`、
`coverage.xml`、`htmlcov/index.html`、`cpp-coverage.json`。

## 5. Reviewed corpus 与 benchmark

reviewed validation corpus 共 183 个显式 oracle，183/183 exact；TP=60、FP=0、FN=0、
abstention=0，strict precision/recall 与 supported-only precision/recall 均为 1.0。十个 finding
code 的逐项指标见 `artifacts/validation/validation-result.json`。

固定 Linux amd64、4 vCPU、4 GiB、network disabled、Clang/LLVM 21.1.8 benchmark 全部通过：

| 档位 | 冷缓存 wall 中位数 | 热缓存 wall 中位数 | 峰值 RSS | 语义等价 | 门禁 |
|---|---:|---:|---:|---|---|
| S | 0.8000 s | 0.0587 s | 88.0 MB | 是 | 通过 |
| M | 4.2673 s | 0.2235 s | 88.0 MB | 是 | 通过 |
| L | 21.2516 s | 0.9795 s | 88.0 MB | 是 | 通过 |

完整 CPU、结果大小、workload digest 与回退预算见
`tools/floating-point-precision-scanner/artifacts/benchmark/benchmark-result.json`。

## 6. 真实 API 执行命令与隔离说明

专用镜像使用 `evidence/Backend.Dockerfile` 构建；临时 API/worker 连接测试环境的 PostgreSQL、
RabbitMQ、Redis、MinIO 和只读历史制品。执行期间旧 worker 暂停，避免旧镜像抢占任务；完成后临时
容器已删除，原 worker 已恢复。

```powershell
docker run --rm --name rvport-fp-evidence-audit --network rvport-infra `
  -v "D:/projects/RvPort:/workspace" -w /workspace --entrypoint node `
  -e AUDIT_API_BASE_URL=http://backend-evidence-repair:8080 `
  registry.example.invalid/oepkgs/rvport-backend:fp-evidence-repair `
  backend/openspec/changes/repair-floating-point-evidence-pipeline/evidence/api-after/audit.cjs
```

审计脚本完成全部断言：固定 source/build 身份、schema 2.0 artifact-set identity、3 个项目 TU、
BC/IR/evidence 完整消费、三类历史伪 unknown 消失、reduction finding 稳定、历史详情未变。

## 7. 验收边界

- 没有通过提高预算、隐藏诊断、伪造 IR evidence 或硬标 `COMPLETE` 解决问题；
- schema 2.1、未知版本、摘要篡改、损坏 bundle、路径越界与 AST-only 降级由单元测试覆盖；
- 本轮不新增规则，不做动态差分执行，不接入新的 frontend 流程；
- `source_mapping_incomplete` 是允许保留的真实证据边界，后续若要提高 IR 源码映射率，应由共享
  BC producer/build pipeline 的独立 change 处理。
