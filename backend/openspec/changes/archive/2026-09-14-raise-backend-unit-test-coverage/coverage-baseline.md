# 后端单元测试覆盖率基线

## 执行基线

- 命令：`mvn -B clean verify`
- 测试：639
- 失败：0
- 错误：0
- 跳过：2
- 行覆盖率：55.22%（12,139 / 21,982）
- 分支覆盖率：45.11%（3,752 / 8,317）
- 报告：`target/site/jacoco/index.html`
- 默认排除：`cn/rvport/backend/jooq/**`（自动生成代码）

## 达标差距

- 在统计范围不变时，整体行覆盖率达到 90% 至少还需覆盖 7,645 行。
- 在统计范围不变时，整体分支覆盖率达到 90% 至少还需覆盖 3,734 个分支。

## 分层基线

| 层级 | 可执行行 | 行覆盖率 | 未覆盖行 | 分支覆盖率 | 未覆盖分支 |
|---|---:|---:|---:|---:|---:|
| Repository | 5,194 | 5.4% | 4,911 | 0.0% | 1,286 |
| Service | 7,609 | 75.6% | 1,860 | 54.1% | 1,518 |
| Handler | 1,100 | 67.3% | 360 | 41.3% | 203 |
| Controller | 517 | 40.8% | 306 | 57.4% | 23 |
| Adapter | 333 | 27.0% | 243 | 5.1% | 148 |
| Configuration | 129 | 93.8% | 8 | 64.3% | 5 |
| Other | 7,100 | 69.6% | 2,155 | 56.1% | 1,382 |

## 主要类缺口

| 类 | 未覆盖行 |
|---|---:|
| `SbomRepository` | 568 |
| `KbScanRepository` | 262 |
| `DependencyAutoFixRepository` | 222 |
| `DependencyAnalysisRepository` | 215 |
| `ModelProfileRepository` | 213 |
| `EnvironmentRepository` | 212 |
| `ReportRepository` | 210 |
| `OptimizationCycleRepository` | 206 |
| `BuildValidationRepository` | 201 |
| `ReportComparisonRepository` | 185 |
| `TaskRepository` | 178 |
| `AutomatedTestHandler` | 172 |
| `WorkerInstanceRepository` | 168 |
| `TestComparisonRepository` | 166 |
| `ProjectRepository` | 148 |

## 外部环境测试

- `LiquibaseMigrationTests` 仅在 `RVPORT_MIGRATION_TEST_ENABLED=true` 时执行，需要显式 PostgreSQL 参数。
- `RealAdapterEnvironmentInfoSmokeTest` 为真实 SSH smoke test，默认禁用。
- 两者不作为普通单元测试覆盖率来源。
