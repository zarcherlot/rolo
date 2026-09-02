<!-- status: frozen; authority: reference; owner: rolo maintainers; target: raspberrypi/192.168.10.167 -->

# Rolo v2 首次真机 Smoke

日期：2026-09-02（Asia/Shanghai）

## 目标证据

- 主机：Raspberry Pi 5 Model B Rev 1.，aarch64
- 系统：Debian 12，Linux `6.6.20+rpt-rpi-2712`
- 网络：`wlan0=192.168.10.167/24`，SSH 22 可达
- 容器：`MentorPi`，镜像 `ros:humble`，运行中
- Middleware graph：容器内观测到 30 个节点、多个传感器/控制 channel 和 service

## Tool smoke

在 `MentorPi` 容器中运行 `scripts/rolo_v2_native_smoke.py`，使用 Rolo v2 的 22 项
reduced Agent-native catalog：

| Tool | 结果 | 证据 |
|---|---|---|
| `native.os.host.inspect` / `status` | `SUCCEEDED` | stdout SHA-256 `6002810c96518aaaa79bf89505c7ef2ff84702443201894f4504cf11072a67c` |
| `native.middleware.graph.inspect` / `nodes` | `SUCCEEDED` | stdout SHA-256 `c938b32b47dfb7522086bc55d65f0a0fd355981950596cb0594c47f61aa10370` |

Middleware Tool 首次运行暴露了一个真实环境差异：受控 runner 必须显式继承目标 Middleware
的 runtime path、依赖包和动态库路径；否则会返回结构化失败（不会伪造成功）。补齐目标
环境后，Middleware graph 读取成功。

本次只执行只读命令，没有启动、停止、发布 topic、写参数或修改机器人文件。

## 当前 Codex Agent 计划回归

当前 Codex 会话生成并校验了 `rolo-tool-plan/v1`：

- `target_id=mentorpi`
- `session_id=native-02b2b112075d459191550b7d9e98370b`
- `surface_digest=bf4b3402604bddd46a1f9bdb659e0a8e857d3849007f274d17d554432f296ced`
- `plan_sha256 (OS)=905abe32c4c2739ba32d6929bdb07286e92c2bf19137c13f2943720f285f2d83`
- `plan_sha256 (Middleware)=de8db9715c6a938b0f336a4d6ca5368d84ae59e9b3a8418ae433705bf24019e7`

计划只包含两个 allowlisted、`readonly` 步骤；Rolo 校验通过后在目标容器执行，两个步骤
均返回 `SUCCEEDED`。这证明当前 Codex 可以作为 Agent 消费 Rolo Tool Surface，而不需要
启动第二个 Agent 进程。
