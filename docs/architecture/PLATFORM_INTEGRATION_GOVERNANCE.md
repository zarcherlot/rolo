# Platform Integration Governance

本文件定义平台集成（LeRobot、Nav2、LanderPi 等）的边界。目标是让核心
`src/rolo` 只实现稳定的机器人语义，把厂商、发行版和目标机差异放在可审计的
integration manifest、target profile 和 adapter 中。

## 分层规则

| 层 | 允许内容 | 禁止内容 |
| --- | --- | --- |
| `src/rolo` 运行时 | 通用 Operation、ROS 语义推断、adapter 接口 | 厂商 CLI、Nav2 节点名、平台专用 action 实现 |
| Operation Contract | 稳定的应用语义与兼容解析 | 以厂商名创建 `lerobot.*` 或 `landerpi.*` Operation |
| `tests/integrations` | 真实平台命令、topic、action 和依赖 | 将真实平台依赖混入默认测试矩阵 |
| `.ci/integrations` | 外部仓库 commit、依赖、入口和环境变量 | 在主 CI job 中散落平台参数 |
| target profile/adapter | 节点、action、topic 和生命周期角色绑定 | 将目标绑定写回核心 Registry |

所有平台专用字符串必须能在 integration manifest 或经过审查的 allowlist 中找到
理由。新增平台时先新增 profile 和隔离测试，再决定是否存在可复用的通用语义；
禁止仅因一个工程出现就新增厂商专用 Operation。

## LeRobot

LeRobot 通过普通 Python console script 接入。当前只允许将相机发现映射到
`app.camera.list`；环境诊断不等价于机器人 health，record、rollout、train 和
teleoperate 仍需独立的 contract、风险和 provider 设计。真实 LeRobot checkout、
commit 和重量级依赖只能出现在 LeRobot integration manifest 和 opt-in CI 中。

## Nav2

核心只暴露 `app.navigation.*` 的可移植语义。Nav2 的 lifecycle 节点、action type、
topic 和具体 endpoint 必须通过 target profile 提供。旧的 `format: nav2` 输入可以
继续兼容读取，但新数据应规范化为通用 `ros_yaml`，并在 profile 中声明导航消费方。

## LanderPi

当前没有 LanderPi 实现。未来如需支持，应新增独立 profile/adapter 和真实目标验收，
不得把品牌名或硬件拓扑写入核心 Registry、ROS 规则或通用 CLI 推断器。

## 远程目标机边界

Codex 和编排逻辑运行在开发机。目标机不安装 Codex 或 coding-agent runtime，只运行
collector、目标 adapter、ROS/机器人原生进程以及受 allowlist、超时和输出限制约束的
SSH 命令。目标命令中不得出现 `codex`、模型调用或 agent 启动逻辑。

## 变更验收

平台集成变更必须同时满足：

1. 默认测试不要求外部平台安装；
2. integration 测试可单独运行且有明确 marker；
3. 静态检查不会发现未解释的平台专用字符串；
4. 核心 Operation 的语义和风险不因单个平台而改变；
5. 目标绑定可由 profile/evidence 替换，而无需修改核心执行器。
