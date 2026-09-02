<!-- status: observed; authority: validation record; target: raspberrypi/192.168.10.167 -->

# Rolo v2 首次真机 Smoke

日期：2026-09-02（Asia/Shanghai）

## 目标证据

- 主机：Raspberry Pi 5 Model B Rev 1.，aarch64
- 系统：Debian 12，Linux `6.6.20+rpt-rpi-2712`
- 网络：`wlan0=192.168.10.167/24`，SSH 22 可达
- 容器：`MentorPi`，镜像 `ros:humble`，运行中
- ROS graph：容器内观测到 30 个节点、多个传感器/控制 topic 和 service

## Tool smoke

在 `MentorPi` 容器中运行 `scripts/rolo_v2_native_smoke.py`，使用 Rolo v2 的 22 项
reduced Agent-native catalog：

| Tool | 结果 | 证据 |
|---|---|---|
| `native.linux.host.inspect` / `inventory` | `SUCCEEDED` | stdout SHA-256 `6002810c96518aaaa79bf89505c7ef2ff84702443201894f4504cf11072a67c` |
| `native.ros.graph.inspect` / `nodes` | `SUCCEEDED` | stdout SHA-256 `c938b32b47dfb7522086bc55d65f0a0fd355981950596cb0594c47f61aa10370` |

ROS Tool 首次运行暴露了一个真实环境差异：受控 runner 必须显式继承 ROS 的
`PATH`、Python site-packages 和 `LD_LIBRARY_PATH`；否则会返回结构化失败（不会伪造
成功）。补齐目标环境后，ROS graph 读取成功。

本次只执行只读命令，没有启动、停止、发布 topic、写参数或修改机器人文件。
