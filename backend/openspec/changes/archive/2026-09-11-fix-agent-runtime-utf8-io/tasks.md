## 1. 统一 Agent 进程输入契约

- [x] 1.1 扩展 Agent 进程执行请求与 `CodexProcessRunner`，支持可选 UTF-8 stdin 文本且不把 prompt 写入错误摘要
- [x] 1.2 在 `DefaultCodexProcessRunner` 中实现 stdin UTF-8 写入、无输入时关闭、提前退出和超时情况下的受控清理
- [x] 1.3 将 Agent workspace 中的输入 JSON、结果 JSON 和文本配置读写显式固定为 UTF-8

## 2. Agent Adapter 提示词传输

- [x] 2.1 调整 Codex Adapter 使用 Codex 非交互 stdin 协议，确保完整 prompt 不再作为命令行参数
- [x] 2.2 在固定 DeepSeek Harness 版本上验证 stdin 协议并实现 UTF-8 stdin，若不支持则在 UTF-8 locale 下保留受控参数回退并记录验证结论
- [x] 2.3 在固定 OpenCode 版本上验证 stdin 协议并实现 UTF-8 stdin，若不支持则在 UTF-8 locale 下保留受控参数回退并记录验证结论
- [x] 2.4 验证模型兼容性 probe、自动化测试比较和 KB AI 扩展均通过统一 Adapter 使用新的输入契约

## 3. Agent 输出 UTF-8 解码

- [x] 3.1 将 stdout 与 stderr 收集改为有状态 UTF-8 字符解码，保留分流结果和 `mergedOutput` 来源标签及顺序
- [x] 3.2 在总输出大小限制处按完整 UTF-8 字符边界截断，并保留超时、读取异常和非零退出码下的已有输出

## 4. 容器 UTF-8 运行环境

- [x] 4.1 在后端运行镜像中设置 `LANG=C.UTF-8` 与 `LC_ALL=C.UTF-8`
- [x] 4.2 检查 Compose 中 API 与 Worker 的环境继承，确保两类进程及其 Agent 子进程使用一致 UTF-8 locale
- [x] 4.3 重新构建后端镜像并在 API、Worker 容器中验证 `native.encoding`、`sun.jnu.encoding` 和中文子进程参数闭环均为 UTF-8

## 5. 测试与验收

- [x] 5.1 补充正常流程单元测试，覆盖中文与 ASCII prompt 的 UTF-8 传输、中文 stdout/stderr 解码以及三类 Adapter 的输入协议
- [x] 5.2 补充异常流程单元测试，覆盖 stdin 写入失败、Agent 提前退出、非零退出码、读取失败与超时，且断言错误信息不泄漏 prompt 或密钥
- [x] 5.3 补充边界条件单元测试，覆盖空 stdin、超长 prompt、多字节字符跨缓冲区边界和输出上限处字符完整性
- [ ] 5.4 运行项目完整单元测试与覆盖率统计，确认项目整体及受影响模块行覆盖率至少 90%，工具支持时分支覆盖率至少 90%，并记录命令、统计范围和报告位置
- [x] 5.5 在独立 API/Worker 容器部署中运行中文模型 probe 或自动化测试比较 E2E，确认 Agent 日志不再出现传输导致的连续 `?`，且对应的 `probe-output.json` 或 `comparison-result.json` 可按 UTF-8 正常解析
