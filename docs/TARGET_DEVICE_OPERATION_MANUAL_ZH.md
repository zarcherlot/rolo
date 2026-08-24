# Rolo 目标机部署与 Adapt 操作手册

版本：`v0.1.0-rc.1`

适用范围：Linux/ROS 机器人目标机

本手册用于在真实机器人目标机上部署 Rolo 并运行 Adapt。Adapt 负责采集签名证据、发现
机器人接口、生成 Wiki 和 Adapter、执行独立门禁，并发布 State Graph、Tool Catalog、handoff
与不可变 release。Adapt 不执行机器人写操作，也不证明行为正确性、可靠性、性能或安全性。
未经后续安全验收，不要执行 `robotctl tool invoke`。

## 1. 选择证据采集模式

Rolo 支持两种显式模式，两者生成相同格式的签名目标证据。

### 模式 A：Rolo 运行在目标机上（推荐）

适合能够在机器人主机上运行 Rolo 和 Codex Agent 的部署。`adapt start` 默认使用本地模式，
不需要指定 `--evidence-mode`。这是最短的首次真机路径。

### 模式 B：控制器加目标机 Collector

适合目标机资源有限、不允许保存 Codex 凭据，或 Agent 必须运行在独立控制器上的部署。
目标机只运行受限的只读 Collector；控制器显式使用 `--evidence-mode remote`。远程采集失败
不会回退到控制器本机的 Linux、ROS 或硬件证据。

## 2. 模式 A：目标机一体化部署

### 2.1 部署前检查

目标机应准备：

- Linux，推荐 Ubuntu/Debian；
- Git 和 `uv`；
- 已安装的 ROS 发行版；
- 机器人工程源码；
- 完整 Agent 链使用的 Codex CLI；
- 完整 Gate 使用的 `bubblewrap` 和可用的 Linux namespace。

检查基础工具：

```bash
git --version
uv --version
codex --version
```

Rolo 不需要安装 wheel，也不要求预先创建配置、制品、输出或临时目录。

### 2.2 获取固定版本

```bash
git clone --branch v0.1.0-rc.1 --depth 1 \
  https://github.com/zarcherlot/rolo.git
cd rolo
```

该命令固定获取已经通过远端 CI 的 `v0.1.0-rc.1`，不会随 `main` 后续变化。

### 2.3 安装锁定依赖和生产沙箱

```bash
uv sync --frozen
```

Ubuntu/Debian 示例：

```bash
sudo apt-get update
sudo apt-get install --yes bubblewrap
```

完整 `adapt start` 会执行生产沙箱自检。如果目标内核禁止创建 user、mount 或 network
namespace，流程会在 Discovery 前安全停止。

### 2.4 完成 Codex 登录

完整 Agent 链首次运行前，以运行 Rolo 的同一操作系统账号执行：

```bash
codex login --device-auth
```

确定性证据采集不需要 Codex 凭据；启发式 Agent、Adapter Agent 和完整发布链需要完成登录。

### 2.5 默认目录与可选配置

Rolo 无须配置文件即可运行。Linux 默认路径为：

```text
~/.config/rolo/config.yaml           可选的用户配置
~/.local/state/rolo/config/          机器人身份和 Collector 状态
~/.local/share/rolo/artifacts/       Discovery、Wiki、Gate 和审计证据
~/.local/share/rolo/output/          不可变 Adapter release
系统安全临时目录                     Agent 临时工作区，结束后删除
```

运行时会自动创建所需目录，不需要设置 `ROLO_ARTIFACT_DIR` 或 `ROLO_OUTPUT_DIR`。

查看当前有效配置：

```bash
uv run robotctl config show
```

需要修改默认值时生成配置文件：

```bash
uv run robotctl config init
uv run robotctl config validate
```

`config init` 不会覆盖已经存在的文件。配置优先级为：命令行、环境变量、用户 YAML、`.env`、
内置默认值。

### 2.6 ROS 环境自动加载

通常不需要手工执行任何 `source`。Rolo 按以下顺序解析 setup 文件：

1. `~/.config/rolo/config.yaml` 中明确配置的 `ros.setup_files`；
2. 继承的 `ROS_DISTRO` 对应的 ROS base，或唯一的 `/opt/ros/<distro>/setup.bash`；
3. `<project-root>/install/local_setup.bash`；
4. 不存在 `local_setup.bash` 时使用 `<project-root>/install/setup.bash`。

Rolo 不加载 `.bashrc`、`.profile` 或 Agent 自主选择的脚本。存在多个 ROS 发行版或 overlay
候选时会失败关闭，部署者必须明确配置顺序：

```yaml
schema_version: rolo-config/v1

storage:
  config_dir: ~/.local/state/rolo/config
  artifact_dir: ~/.local/share/rolo/artifacts
  output_dir: ~/.local/share/rolo/output
  scratch_dir: null

agent:
  provider: codex
  executable: codex
  timeout_s: 1800

ros:
  auto_source: true
  setup_files:
    - /opt/ros/humble/setup.bash
    - /home/robot/wheeltec_ws/install/local_setup.bash
  domain_id: "0"
  rmw_implementation: rmw_fastrtps_cpp
```

修改后执行：

```bash
uv run robotctl config validate
```

setup 文件路径和 SHA-256 会写入签名目标证据。已固定的 setup 文件发生变化后，Collector
会拒绝继续采集，需要按[目标证据部署规范](TARGET_EVIDENCE_DEPLOYMENT.md)执行轮换和重新注册。

### 2.7 启动完整 Adapt

没有 URDF 时：

```bash
uv run robotctl adapt start \
  --robot-id wheeltec \
  --project-root /home/robot/wheeltec_ws \
  --timeout 1800
```

有 URDF 时：

```bash
uv run robotctl adapt start \
  --robot-id wheeltec \
  --project-root /home/robot/wheeltec_ws \
  --urdf /home/robot/wheeltec_ws/src/robot_description/urdf/robot.urdf \
  --timeout 1800
```

`--urdf` 可以省略。缺失的硬件规格会标记为未知，不会被启发式输出冒充为确定事实。

这一条产品命令会自动：

1. 准备用户级运行目录；
2. 注册或复用机器人身份和本地 Collector；
3. 解析、固定并加载 ROS 环境；
4. 采集并验证 Hardware、Linux 和 ROS 签名证据；
5. 有界扫描机器人工程源码；
6. 运行启发式自主发现、Operation 映射和 Wiki 编写技能；
7. 启动真实 Adapter Agent 并冻结结构化代码输出；
8. 执行独立 Gate；
9. 生成 State Graph、Tool Catalog 和 handoff；
10. 发布不可变 Adapter release。

只运行 Discovery 与 Wiki 时增加：

```bash
uv run robotctl adapt start \
  --robot-id wheeltec \
  --project-root /home/robot/wheeltec_ws \
  --discover-only
```

## 3. 检查和验收

以下命令均为只读检查，不会调用目标 Operation：

```bash
uv run robotctl adapt status --robot wheeltec
uv run robotctl adapt operations summary --robot wheeltec
uv run robotctl adapt operations list --robot wheeltec --registration REGISTERED
uv run robotctl tool catalog --robot wheeltec
uv run robotctl state graph snapshot --robot wheeltec
```

检查单个 Operation 时，将 `OPERATION` 替换为实际名称：

```bash
uv run robotctl adapt candidates inspect OPERATION --robot wheeltec
uv run robotctl adapt operations inspect OPERATION --robot wheeltec
uv run robotctl tool schema OPERATION --robot wheeltec
```

### 3.1 生成回传验收包

```bash
uv run robotctl adapt acceptance-pack \
  --robot wheeltec \
  --output ./rolo-adapt-acceptance.json
```

向评审方回传：

- `rolo-adapt-acceptance.json`；
- 命令报告的 SHA-256；
- 流程失败时的终端错误信息。

验收包包含源码版本、Registry 身份与数量、目标证据 digest、Discovery 状态、eligible/deferred
Operation、Gate 与 release 身份，不包含凭据、调用载荷、私有源码归档或完整原始 Probe 数据。

### 3.2 完整 Adapt 判定标准

- Adapt 状态为 `COMPLETE`，独立 Gate 为 `PASSED`；
- Journey v2 中存在 Collector ID、目标指纹和 bundle digest；
- Registry 保持完整产品 Operation 集，而不是只剩本机候选；
- 纳入 bundle 的 Operation 为 `VERIFIED`，且唯一绑定到对应 release 入口；
- deferred Operation 为 `UNAVAILABLE`，不能以未验证状态进入门禁目录；
- State Graph 为 `robot-state-graph/v2`，并包含 Operation 到现场路由的边；
- release manifest 记录所有 Adapter 文件、受控 Runtime Context 和 Operation 级目标指纹；
- 再次运行等价发现后，Adapt 仍保持 `COMPLETE`。

Discovery 为 `PARTIAL` 不一定失败。缺失证据与本次目标 Operation 无关时可以继续；关键路由、
目标机身份、签名或 Gate 证据缺失时必须停止。

## 4. 模式 B：控制器与目标机分离

### 4.1 在目标机初始化 Collector

目标机只需要 Git checkout、锁定环境和 Collector，不需要 Codex、Agent 工作区或 Tool Gateway
访问权限。

```bash
git clone --branch v0.1.0-rc.1 --depth 1 \
  https://github.com/zarcherlot/rolo.git
cd rolo
uv sync --frozen
```

初始化：

```bash
uv run robotctl target-evidence collector-init \
  --robot-id wheeltec \
  --project-root /home/robot/wheeltec_ws \
  --config /etc/rolo/target-evidence-collector.json \
  --secret-file /etc/rolo/target-evidence-collector.key \
  --descriptor-out ./wheeltec-collector.json
```

自动 ROS 选择存在歧义时，按真实加载顺序重复传入：

```bash
--ros-setup /opt/ros/humble/setup.bash \
--ros-setup /home/robot/wheeltec_ws/install/local_setup.bash
```

需要采集某个已审核程序的受限 `--help` 时，可增加：

```bash
--allow-executable /opt/robot/bin/wheeltec_driver
```

第三方程序可能为 `--help` 实现副作用，只能 allowlist 经人工审核的可执行文件，也可以完全
省略此类证据。

部署时必须使用相互独立的通道传递：

- descriptor：普通配置通道；
- Collector secret：独立秘密通道；
- SSH host key：独立核验的 `known_hosts`。

### 4.2 在控制器启动远程 Adapt

控制器同样克隆固定标签并完成 `uv sync --frozen` 与 Codex 登录。首次远程启动：

```bash
uv run robotctl adapt start \
  --robot-id wheeltec \
  --project-root /path/to/controller/source-copy \
  --evidence-mode remote \
  --collector-descriptor ./wheeltec-collector.json \
  --verification-secret /etc/rolo/secrets/wheeltec-collector.key \
  --ssh-target rolo-evidence@wheeltec-host \
  --known-hosts /etc/rolo/ssh/known_hosts \
  --collector-config /etc/rolo/target-evidence-collector.json
```

只运行远程 Discovery 时增加 `--discover-only`。远程模式要求 SSH `BatchMode=yes`、
`StrictHostKeyChecking=yes` 和显式 `known_hosts`；目标身份、Collector ID、签名或 SSH host key
不匹配时必须停止。

控制器上的 build/install 目录必须是未经修改的目标机制品副本，不能把控制器本机编译结果
当作目标证据。

## 5. 常见故障处理

### 5.1 ROS 候选存在歧义

执行 `uv run robotctl config init`，编辑 `~/.config/rolo/config.yaml` 中的
`ros.setup_files`，再运行 `uv run robotctl config validate`。不要通过修改 `.bashrc` 绕过。

### 5.2 手工 `ros2 node list` 正常，但 Probe 不可用

保留本次运行的 `ros.json`，检查 `command_diagnostics`。它会区分继承环境的尝试和干净
base setup 重试，并保留有界退出码与 stderr。Probe 不可用不能解释成“ROS 图为空”。

### 5.3 Adapt 返回 `BLOCKED`

```bash
uv run robotctl adapt discover review --robot wheeltec
uv run robotctl adapt operations summary --robot wheeltec
uv run robotctl adapt operations list --robot wheeltec --applicability OBSERVED
uv run robotctl adapt run --robot wheeltec --dry-run
```

重点核查真实 ROS Topic/Service/Action、设备或 CLI 路由、工程根路径、ROS setup、证据时效、
目标指纹和签名。

### 5.4 生产沙箱自检失败

```bash
bubblewrap --version
```

确认目标内核允许 user、mount 和 network namespace。真实目标机禁止设置
`ROLO_ADAPTER_UNSANDBOXED_DEV=1`；该选项仅用于单元测试和离线 Demo。

### 5.5 身份、签名或 SSH pin 变化

以下情况不能绕过：

- Collector 或目标指纹不匹配；
- payload hash 或 HMAC 签名不匹配；
- setup 文件路径或 digest 变化；
- SSH host key 校验失败；
- 签名证据已经过期。

停止采集，核验物理目标机，初始化新 Collector 或执行显式轮换与 re-enroll，再采集新 bundle。
旧 bundle 只能作为审计证据，不能重复用于新的 Discovery。

## 6. 真机安全边界

Adapt 阶段禁止：

- 绕过 Collector、目标指纹、签名或 SSH host-key 校验；
- 用控制器本机 ROS 图替代目标机证据；
- 手工把未验证 Operation 标记为 `VERIFIED`；
- 允许 Agent 自主加载任意 shell 脚本；
- 在没有后续安全流程时执行写 Operation；
- 关闭真实目标机的生产沙箱；
- 将 Collector secret 或其他凭据写入源码仓库。

完成 Adapt 后，先回传验收包和 SHA-256 并通过评审，再进入 Diagnose/Verify、写 Operation 和
真实行为闭环。
