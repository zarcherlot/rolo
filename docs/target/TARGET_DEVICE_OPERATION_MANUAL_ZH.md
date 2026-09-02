<!-- status: archived; authority: guide; owner: docs maintainers; last_reviewed: 2026-09-02; source_of_truth: docs/getting-started/ADAPT_SHORT_JOURNEY.md -->

# Rolo 目标机部署与 Adapt 操作手册

版本：`v0.1.0-rc.2`

适用范围：Linux 机器人或机器人应用目标机；ROS 为可选 Middleware

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
- 机器人工程所需的运行时；使用 ROS 的目标应安装对应 ROS 发行版，非 ROS 目标无需安装 ROS；
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
git clone --branch v0.1.0-rc.2 --depth 1 \
  https://github.com/zarcherlot/rolo.git
cd rolo
```

该命令固定获取已经通过远端 CI 和真实 Agent 验收的 `v0.1.0-rc.2`，不会随 `main` 后续变化。

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

### 2.6 目标运行环境与可选 ROS 自动加载

非 ROS 工程无需配置或补造 ROS 环境。Rolo 直接采集目标操作系统、工程入口、依赖、CLI/API、
协议、进程和设备接口，并把 ROS Probe 的不可用记录为不适用边界，而不是工程缺陷。

目标或工程存在 ROS 证据时，通常不需要手工执行任何 `source`。Rolo 按以下顺序解析 setup
文件：

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

非 ROS Application/CLI 工程首次运行时，只固定已经人工审核的目标可执行文件。建议先只生成
Discovery 与 Wiki：

```bash
uv run robotctl adapt start \
  --robot-id lerobot-host \
  --project-root /home/robot/lerobot \
  --allow-executable "$(command -v lerobot-find-cameras)" \
  --allow-executable "$(command -v lerobot-info)" \
  --discover-only \
  --timeout 1800
```

`--allow-executable` 会在 Collector enrollment 时固定绝对路径和 SHA-256，只允许采集有界
`--help` 证据，不会执行实际业务子命令。确认 Wiki、Route 和缺口后，移除
`--discover-only` 重跑完整 Agent/Gate 链。已存在 Collector 若要改变 allowlist，必须执行
显式 rotation/re-enrollment，不能静默扩大采集面。

这一条产品命令会自动：

1. 准备用户级运行目录；
2. 注册或复用机器人身份和本地 Collector；
3. 解析并固定目标运行环境；仅在 ROS 相关时加载 ROS setup；
4. 采集并验证 Hardware、Linux、Application 及可选 ROS 签名证据；
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

该模式中的 SSH 只承载一次一请求的只读 Collector 协议，不提供交互式 Shell、任意命令执行、
断点调试或写 Operation。建议为 Collector 使用独立账号和独立密钥，并把该密钥强制绑定到固定
Collector 命令。运维人员需要登录目标机时，应使用另一套经过授权的管理账号和密钥。

### 4.1 准备目标机运行目录

目标机只需要 Git checkout、锁定环境和 Collector，不需要 Codex、Agent 工作区或 Tool Gateway
访问权限。以下示例将固定版本放在 `/opt/rolo`，并让非交互 SSH 会话可以通过
`/usr/local/bin/robotctl` 找到入口：

```bash
sudo useradd --create-home --shell /bin/bash rolo-evidence
sudo install -d -m 0755 -o rolo-evidence -g rolo-evidence /opt/rolo
sudo -u rolo-evidence git clone --branch v0.1.0-rc.2 --depth 1 \
  https://github.com/zarcherlot/rolo.git /opt/rolo
cd /opt/rolo
sudo -u rolo-evidence uv sync --frozen
sudo ln -s /opt/rolo/.venv/bin/robotctl /usr/local/bin/robotctl
/usr/local/bin/robotctl --help >/dev/null
```

已有 `rolo-evidence` 账号或 `/usr/local/bin/robotctl` 时不要重复创建或覆盖，应核对它们是否指向
固定的 `v0.1.0-rc.2` 环境。该账号不应具有 `sudo` 权限。它必须能够只读访问机器人工程、已批准
的 ROS setup 和需要枚举的设备；仅按实际需要授予 Unix group 或 ACL，不要直接授予管理员权限。

创建仅该账号可读的 Collector 目录并初始化：

```bash
sudo install -d -m 0700 -o rolo-evidence -g rolo-evidence /etc/rolo
sudo -u rolo-evidence /usr/local/bin/robotctl target-evidence collector-init \
  --robot-id wheeltec \
  --project-root /home/robot/wheeltec_ws \
  --config /etc/rolo/target-evidence-collector.json \
  --secret-file /etc/rolo/target-evidence-collector.key \
  --descriptor-out /home/rolo-evidence/wheeltec-collector.json
sudo chmod 0600 /etc/rolo/target-evidence-collector.json \
  /etc/rolo/target-evidence-collector.key
```

使用 ROS 且自动选择存在歧义时，按真实加载顺序重复传入：

```bash
--ros-setup /opt/ros/humble/setup.bash \
--ros-setup /home/robot/wheeltec_ws/install/local_setup.bash
```

ROS 或非 ROS 目标需要采集某个已审核程序的受限 `--help` 时，可增加：

```bash
--allow-executable /opt/robot/bin/wheeltec_driver
```

第三方程序可能为 `--help` 实现副作用，只能 allowlist 经人工审核的可执行文件，也可以完全
省略此类证据。

### 4.2 创建专用 SSH 密钥并限制账号

在控制器上为这一台目标机创建独立 Ed25519 密钥。推荐使用口令并在运行前加载到
`ssh-agent`；无人值守场景应把密钥放入受控的秘密存储，不能提交到源码仓库：

```bash
install -d -m 0700 ~/.ssh
ssh-keygen -t ed25519 -f ~/.ssh/rolo-wheeltec -C rolo-wheeltec-evidence
ssh-add ~/.ssh/rolo-wheeltec
```

通过物理控制台或已有的管理通道，把 `~/.ssh/rolo-wheeltec.pub` 的内容安装到目标机
`/home/rolo-evidence/.ssh/authorized_keys`。生产配置推荐使用以下单行格式；将
`AAAAC3...` 替换为控制器公钥的完整内容：

```text
restrict,command="/usr/local/bin/robotctl target-evidence collector-run --config /etc/rolo/target-evidence-collector.json" ssh-ed25519 AAAAC3... rolo-wheeltec-evidence
```

然后在目标机核对权限：

```bash
sudo chown -R rolo-evidence:rolo-evidence /home/rolo-evidence/.ssh
sudo chmod 0700 /home/rolo-evidence/.ssh
sudo chmod 0600 /home/rolo-evidence/.ssh/authorized_keys
```

`restrict` 会禁用 PTY、端口转发、Agent 转发和 X11 转发。旧版 OpenSSH 不支持 `restrict` 时，
使用 `no-agent-forwarding,no-port-forwarding,no-X11-forwarding,no-pty` 等价限制，并继续保留
固定 `command=`。不要用该专用密钥执行 `scp`、交互式 Shell 或 SSH tunnel。

### 4.3 独立固定 SSH 主机密钥

在目标机物理控制台或可信管理通道读取 Ed25519 主机公钥及其 SHA-256 指纹：

```bash
sudo cat /etc/ssh/ssh_host_ed25519_key.pub
sudo ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub -E sha256
```

在控制器上通过另一个可信通道核对指纹后，创建专用 `known_hosts`。不要直接信任首次连接提示，
也不要把未经独立核对的 `ssh-keyscan` 输出当作可信主机密钥：

```bash
install -d -m 0700 ~/.config/rolo/ssh
printf '%s\n' 'wheeltec-host ssh-ed25519 <目标机主机公钥的Base64部分>' \
  > ~/.config/rolo/ssh/wheeltec_known_hosts
chmod 0600 ~/.config/rolo/ssh/wheeltec_known_hosts
ssh-keygen -F wheeltec-host -f ~/.config/rolo/ssh/wheeltec_known_hosts
```

为了明确指定地址、账号和私钥，在控制器的 `~/.ssh/config` 增加：

```sshconfig
Host wheeltec-rolo
  HostName 192.0.2.10
  User rolo-evidence
  IdentityFile ~/.ssh/rolo-wheeltec
  IdentitiesOnly yes
  HostKeyAlias wheeltec-host
```

把 `192.0.2.10` 替换为目标机实际 IP 或 DNS 名称。自定义端口可增加 `Port`，需要跳板机时可
增加 `ProxyJump`。`--ssh-target` 只接受 `host` 或 `user@host`，不接受 `-p` 等 SSH 参数；复杂
连接应封装为上述仅含字母、数字、点、下划线或连字符的 Host 别名。

### 4.4 分通道置备 Collector 身份与验签秘密

部署时必须使用相互独立的通道传递：

- descriptor：普通配置通道；
- Collector secret：独立秘密通道；
- SSH host key：独立核验的 `known_hosts`。

将目标机上的 `/home/rolo-evidence/wheeltec-collector.json` 通过普通配置管理通道传到控制器，
将 `/etc/rolo/target-evidence-collector.key` 通过秘密管理系统、加密介质或其他独立秘密通道置备
到控制器。例如最终文件可放置为：

```text
~/.config/rolo/collectors/wheeltec-collector.json
~/.config/rolo/secrets/wheeltec-collector.key
```

控制器上的 secret 必须设为 `0600`，且不得使用受限的 `rolo-evidence` SSH 密钥从目标机
下载。descriptor、secret 和 SSH host key 三者来自同一未验证 SSH 会话时，不构成独立置备。

### 4.5 配置远程模式并执行 SSH 冒烟采集

控制器同样克隆 `v0.1.0-rc.2` 固定标签并执行 `uv sync --frozen`。先单独配置并采集一份新鲜
证据，以同时验证 SSH 认证、主机密钥固定、远端 `robotctl`、Collector 配置和 HMAC 验签：

```bash
cd /path/to/controller/rolo
chmod 0600 ~/.config/rolo/secrets/wheeltec-collector.key
uv run robotctl target-evidence configure \
  --robot-id wheeltec \
  --mode remote \
  --collector-descriptor ~/.config/rolo/collectors/wheeltec-collector.json \
  --verification-secret ~/.config/rolo/secrets/wheeltec-collector.key \
  --ssh-target wheeltec-rolo \
  --known-hosts ~/.config/rolo/ssh/wheeltec_known_hosts \
  --collector-config /etc/rolo/target-evidence-collector.json

uv run robotctl target-evidence collect \
  --robot-id wheeltec \
  --output ./wheeltec-target-evidence.json \
  --timeout 45
```

成功时第二条命令返回 `status: VERIFIED`，并报告与 descriptor 一致的 `collector_id` 和
`target_host_fingerprint`。任何密码提示、首次连接确认提示、主机密钥错误、签名错误或超时都
应视为失败；不要改用 `StrictHostKeyChecking=no` 绕过。

首次配置会固定 Collector 身份、secret 摘要、SSH target、`known_hosts` 路径和远端配置路径。
以后更换其中任一项都必须走显式 rotation/re-enrollment，不能直接覆盖部署文件。

### 4.6 在控制器启动远程 Adapt

冒烟采集通过后，完成 Codex 登录并复用已经固定的远程部署：

```bash
uv run robotctl adapt start \
  --robot-id wheeltec \
  --project-root /path/to/controller/source-copy \
  --evidence-mode remote \
  --discover-only \
  --timeout 1800
```

确认 Discovery、Wiki 和目标路由后，移除 `--discover-only` 运行完整 Agent/Gate/release 链。
如果跳过 4.5 的独立配置，也可以在首次 `adapt start` 中传入
`--collector-descriptor`、`--verification-secret`、`--ssh-target`、`--known-hosts` 和
`--collector-config` 全部参数；先冒烟采集更容易定位连接和验签问题。

远程模式固定使用 SSH `BatchMode=yes`、
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

非 ROS 目标没有 ROS setup 或 ROS 图属于正常状态，不应执行本节排障，也不应为了通过检查而
安装 ROS；应转而核对 Application/CLI、协议、进程和设备接口证据。

### 5.3 Adapt 返回 `BLOCKED`

```bash
uv run robotctl adapt discover review --robot wheeltec
uv run robotctl adapt operations summary --robot wheeltec
uv run robotctl adapt operations list --robot wheeltec --applicability OBSERVED
uv run robotctl adapt run --robot wheeltec --dry-run
```

重点核查目标软件栈实际使用的路由：ROS 目标检查 Topic/Service/Action 与 setup，非 ROS 目标
检查 CLI/API、协议、进程和设备接口；两者都要核对工程根路径、证据时效、目标指纹和签名。

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

### 5.6 SSH 远程采集失败

先在控制器上重跑最小采集，不要直接反复运行完整 Adapt：

```bash
uv run robotctl target-evidence collect --robot-id wheeltec --timeout 45
```

按错误类型检查：

- `Permission denied (publickey)`：确认 `ssh-agent` 已加载正确私钥、SSH Host 别名选中了
  `rolo-evidence` 账号，并核对目标机 `.ssh` 与 `authorized_keys` 的属主和权限；
- `Host key verification failed`：核对 `HostKeyAlias` 与专用 `known_hosts` 第一列是否一致，并通过
  独立通道复核目标机指纹；不要自动删除旧 pin；
- `remote target evidence collector failed`：在目标机管理控制台确认
  `/usr/local/bin/robotctl`、Collector state、secret、工程和 ROS setup 对 `rolo-evidence` 可读，且
  固定 `command=` 中的配置路径与控制器 `--collector-config` 一致；
- `collector state belongs to a different target host`：Collector state 被复制到了另一台机器，
  必须在实际目标机重新初始化并显式 re-enroll；
- `signature mismatch`、`collector identity mismatch` 或证据过期：停止连接，核对 descriptor、
  secret、系统时间和目标身份，不要重建或替换部署文件来绕过；
- 超时：检查网络、跳板机和目标负载；可以在 `1` 到 `300` 秒之间调整 `--timeout`，但超时后
  不会回退采集控制器本机证据。

需要查看 SSH 握手细节时，可临时用相同 Host 别名和固定 `known_hosts` 执行 OpenSSH 的 `-vvv`
诊断，但受限账号仍会强制运行 Collector，空请求预期会被拒绝。不要为了调试移除
`BatchMode`、`StrictHostKeyChecking`、`UserKnownHostsFile` 或 `authorized_keys` 的强制命令。

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
