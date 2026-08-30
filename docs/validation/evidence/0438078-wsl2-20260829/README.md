<!-- status: frozen; authority: reference; owner: ROLO maintainers; last_reviewed: 2026-08-29 -->

# 0438078 WSL2 验证证据

本目录是 `0438078-wsl2-20260829` 的脱敏、可提交证据集。它记录固定 revision、失败
case、真实 Diagnose/Verify handoff 摘要、SSH 故障矩阵和逐文件 SHA256，不包含私钥、
collector secret、完整环境变量、二进制归档或物理机器人 E4 声明。

完整结论见 [validation-report.md](validation-report.md)。所有文件在提交前通过
`sha256sum -c SHA256SUMS`；修复后复验必须新建 validation ID，不得覆盖本目录。

