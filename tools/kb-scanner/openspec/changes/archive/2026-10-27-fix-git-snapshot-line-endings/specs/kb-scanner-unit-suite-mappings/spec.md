## MODIFIED Requirements

### Requirement: 本地和 CI 必须使用一致的完整验收入口
KB Scanner 测试镜像的默认命令 SHALL 执行完整源码门槛、全部独立子门槛及既有回归；开发文档 MUST 区分快速局部验证与完整验收。失败的子命令 SHALL 传播非零状态，报告包含具体命令、范围、测试结果、行/分支覆盖率与报告位置。正式验收 MUST 从经核对的拟提交 Git 快照构建，记录 tree 与输入摘要，不能只凭工作区镜像或变更文件摘要推断与 CI 输入一致。

#### Scenario: 本地执行默认测试容器
- **WHEN** 开发者不指定局部模式而运行当前源码构建的测试镜像
- **THEN** SHALL 使用与 CI 相同的默认入口，不能仅运行全量 discover 后宣称完整验收通过

#### Scenario: 干净构建保留验收输入
- **WHEN** 测试镜像从仓库根构建上下文生成
- **THEN** Docker 排除规则 SHALL 保留已跟踪的 KB Scanner 测试清单和构建选择夹具，完整入口无需额外复制源码即可通过

#### Scenario: 导出过程自动转换换行
- **WHEN** archive、checkout 或其他导出过程可能受 core.autocrlf 或 attributes 影响
- **THEN** SHALL 将导出输入与候选 tree 的原始 Git blob 核对，发现差异时不能将导出包认作未经转换的 Git 快照
