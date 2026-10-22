## ADDED Requirements

### Requirement: Build an independent development image in this change

项目 SHALL 在本 change 提供独立 `Dockerfile.dev` 及项目内构建入口，实际构建并验证 Linux amd64 开发镜像；构建上下文 SHALL 限于本项目，不依赖兄弟项目镜像、源码或宿主机 LLVM SDK。开发与生产 Dockerfile 的合并 MUST 留给后续独立 change。

#### Scenario: Build from a clean project context

- **WHEN** 在仅有 Docker 和本项目源码的主机执行文档中的开发镜像构建命令
- **THEN** 镜像构建成功，镜像内可构建分析核心及 Python 入口，并记录构建命令、镜像 ID 和结果

#### Scenario: Preserve production container configuration

- **WHEN** 本 change 的开发镜像完成构建和验证
- **THEN** 生产 Dockerfile、仓库级容器集成和归档 checker 均未因此被修改

### Requirement: Pin and verify the analysis toolchain

项目 SHALL 提供精确工具链/依赖锁定清单，包含基础镜像 digest、依赖版本、来源/校验信息和许可证；doctor SHALL 核对 Clang、LLVM SDK、reader、opt、llvm-link 及覆盖率工具的锁定发行一致性。具体 LLVM 发行 MUST 在实施起始任务验证，不使用浮动 latest 或把历史 DevKit/Clang 实验视为本镜像验证。

#### Scenario: Tools do not match the lock

- **WHEN** doctor 发现实际 opt/LLVM SDK 与锁定工具链不匹配
- **THEN** 输出实际和预期版本及可操作诊断，以非零退出，不继续声称环境就绪

### Requirement: Run isolated development and quality checks

开发容器 SHALL 支持非 root、只读被分析源码、独立可写构建/缓存/报告目录；质量入口 SHALL 不依赖网络、SSH、DevKit、特权模式或 Docker socket。构建依赖获取与离线运行阶段 SHALL 分开说明。

#### Scenario: Validate inside the built image

- **WHEN** 在已构建镜像中使用全新输出目录运行项目质量入口和 collect/index 冒烟测试
- **THEN** 编译、单元测试、覆盖率门槛和集成验证实际执行，报告写入指定输出目录，被分析源码保持不变且不运行竞争程序
