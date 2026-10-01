---
name: minds-write
description: 用户明确请求16 Minds的保持事实的写作与改写时使用。Use for explicitly requested 16 Minds write workflow. Requires host generation and Python helper; local candidate, host validation varies.
---

本入口 workflow 为 `write`。只在解析层兼容旧名，不声称已注册旧 slash 命令。
先读 [公共调用协议](references/references/protocol.md) 和 [工作流](references/workflows/write.md)，调用旁边 [helper](scripts/minds_cli.py)。
normalize 的 explicit_options.workflow 设为 `write`；保留原始材料、明示参数和权限来源。
最终人数恰好 1。遵循完整控制流：规范化、真实能力预检、选人、准备、先登记intent再实际宿主派发、实际回执、真实输出校验、业务处理及最终稿。
未实际运行的角色不得出现在已执行披露中；prepared 不等于完成。缺能力时如实拒绝相关分支，不伪造输出或回执。
默认无持久化、无联网、无额外模型调用。只在明确授权下使用对应功能。阅读当前登记profile所需资料，不扩成新顶层入口。

English: Follow the local protocol and this workflow. The host performs generation; the helper enforces deterministic contracts. Disclose actual execution and validation limits.
