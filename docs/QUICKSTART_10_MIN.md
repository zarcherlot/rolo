# 10 分钟安装与 Demo

本页是 ROLO 的最小可复现验收路径。它使用仓库内的 `demo_diff` 机器人夹具和 mock 后端，
不连接真实机器人，不发送运动命令，不需要 OpenAI/Codex 账号。它验证的是 ROLO 的离线
工程路径，不是物理安全或真机行为验收。

## 目标和计时预算

| 时间 | 步骤 | 成功标志 |
|---:|---|---|
| 0–1 分钟 | 检查 Python 和安装 `uv` | Python 3.10+、`uv --version` 有输出 |
| 1–3 分钟 | 同步锁定依赖 | `uv sync --locked --dev` 成功 |
| 3–4 分钟 | 检查本地运行时 | `runtime health` 返回 `HEALTHY` |
| 4–6 分钟 | 运行 demo discovery | 生成 discovery、Wiki 和 manifest |
| 6–8 分钟 | 查看 Wiki 和三阶段状态 | 能看到 `demo_diff` 和 `adapt/diagnose/verify` |
| 8–10 分钟 | 跑完整确定性验收 | `tests/test_stages.py` 全部通过 |

## 前置条件

- macOS、Linux 或 Windows；
- Python 3.10–3.13。仓库的 `.python-version` 固定本地默认版本为 3.10；
- Git；
- 网络只用于第一次下载依赖。Demo 运行阶段不需要网络、ROS、Docker、Codex 或 API Key。

安装 `uv` 的官方方式任选其一：

```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# macOS（Homebrew）
brew install uv
```

Windows PowerShell：

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

安装后重新打开终端，确认：

```bash
python3 --version    # 必须 >= 3.10
uv --version
```

## 1. 安装

```bash
git clone https://github.com/zarcherlot/rolo.git
cd rolo
uv sync --locked --dev
```

`uv sync` 会创建隔离环境并安装锁定版本。后续命令统一使用 `uv run`，不会污染系统 Python。

## 2. 设置离线 Demo 环境

仓库夹具包含两个注册机器人。为了让演示完全确定，选择 `demo_diff`，并把产物放到临时
目录；`ROLO_OUTPUT_DIR` 必须在源码目录之外。

macOS/Linux：

```bash
export ROLO_CONFIG_DIR="$PWD/tests/fixtures"
export ROLO_ARTIFACT_DIR="$PWD/.rolo/demo-artifacts"
export ROLO_OUTPUT_DIR="$(mktemp -d)/rolo-output"
export ROBOT_USE_BACKEND=mock
```

Windows PowerShell：

```powershell
$env:ROLO_CONFIG_DIR = "$PWD/tests/fixtures"
$env:ROLO_ARTIFACT_DIR = "$PWD/.rolo/demo-artifacts"
$env:ROLO_OUTPUT_DIR = Join-Path ([System.IO.Path]::GetTempPath()) "rolo-output"
$env:ROBOT_USE_BACKEND = "mock"
New-Item -ItemType Directory -Force $env:ROLO_OUTPUT_DIR | Out-Null
```

## 3. 检查运行时

```bash
uv run robotctl runtime version
uv run robotctl runtime health
```

预期：`runtime version` 输出 `0.1.0` 和当前协议版本；`runtime health` 输出
`"status": "HEALTHY"`，并显示两个注册机器人。`docker`、`ros2`、`ffmpeg` 和 `codex`
缺失在 mock Demo 中是允许的可选警告。

## 4. 运行 discovery

```bash
uv run robotctl adapt discover run \
  --robot demo_diff \
  --urdf tests/fixtures/profiles/differential_drive.urdf \
  --source-root src \
  --active-probe none
```

预期输出包含：

- `"robot_id": "demo_diff"`；
- `"status": "SUCCEEDED"` 或可解释的 `PARTIAL`；
- `discovery_id`、`artifact` 和 `wiki` 路径；
- 不会出现真实运动调用。

查看生成的工程 Wiki：

```bash
uv run robotctl adapt discover review --robot demo_diff
```

## 5. 查看三阶段状态

```bash
uv run robotctl adapt status --robot demo_diff
uv run robotctl pipeline-status --robot demo_diff
```

预期：Adapt 至少有 discovery 输入；Diagnose 在没有真实 Adapt release 时为 `BLOCKED`；
Verify 是可选并等待 Diagnose handoff。这是正确结果，不是 Demo 失败。它证明系统能明确
表达“已发现但尚未验证”，不会把静态夹具伪装成可调用能力。

## 6. 跑完整确定性验收

上一步是用户可见 CLI 演示；下面的测试使用相同的服务、夹具和 Schema，并用测试 Provider
替代外部 Coding Agent，验证完整的：

```text
discovery → isolated Agent output → freeze → independent gate
→ Tool Catalog → State Graph → immutable release → generic runtime path
```

```bash
uv run pytest tests/test_stages.py -q
```

预期：测试全部通过，且临时产物中会生成 `adapt/demo_diff/latest.json` 和外部
`robots/demo_diff/current.json`。该测试 Provider 仅用于离线验收，不能用于宣称真机能力。

## 10 分钟验收标准

一次合格的 Quickstart 必须满足：

- 从干净 checkout 完成 `uv sync --locked --dev`；
- 不设置 OpenAI/Codex 密钥也能完成 Demo；
- `runtime health` 返回 `HEALTHY`；
- discovery 生成可读 Wiki、机器 manifest 和可定位 artifact；
- pipeline 明确显示未完成的 Diagnose/Verify，而不是虚假成功；
- `tests/test_stages.py` 全部通过；
- 全过程不连接真机、不执行写操作、不把 mock 结果标成物理验证。

## 常见问题

### Python 版本过低

项目要求 Python `>=3.10,<3.14`。如果 `python3 --version` 是 3.9 或更低，先安装 3.10；
本地默认版本由 `.python-version` 固定。Python 3.11–3.13 由 CI 矩阵持续验证。

### `uv: command not found`

重新打开终端，或把 uv 安装器提示的目录加入 `PATH`。不要用系统 `pip` 绕过锁文件安装，
否则无法复现依赖版本。

### `ROLO_OUTPUT_DIR must be outside ...`

把 `ROLO_OUTPUT_DIR` 改到 `/tmp`、系统临时目录或其他 checkout 之外的目录。不要把发布
产物放进源码树。

### 想连接真实机器人

不要修改本页的离线验收命令。请阅读 [`ADAPT_DEVICE_HANDS_ON.md`](ADAPT_DEVICE_HANDS_ON.md)
和 [`P0_ADAPT_ACCEPTANCE.md`](P0_ADAPT_ACCEPTANCE.md)，完成环境、授权、只读探测和真实
目标证据准备后，再运行 `robotctl adapt start`。

### 运行 LeRobot 集成测试

LeRobot 当前要求 Python 3.12+，并包含 PyTorch 等重量级依赖，因此不进入 rolo 的默认
10 分钟环境或 Python 3.10–3.13 基础矩阵。准备一个独立的 LeRobot 环境和 checkout 后，
运行：

```bash
export ROLO_RUN_LEROBOT_E2E=1
export LEROBOT_ROOT=/path/to/lerobot
export LEROBOT_INFO=/path/to/lerobot/.venv/bin/lerobot-info  # 可选；默认从 PATH 查找
export LEROBOT_FIND_CAMERAS=/path/to/lerobot/.venv/bin/lerobot-find-cameras
uv run pytest tests/test_lerobot_e2e.py -q
```

该测试实际运行 `lerobot-info`，再让 rolo 对 LeRobot 源码执行有界 Discovery，并校验生成的
Wiki、manifest、应用工程证据和“源码发现不能升级为 VERIFIED 能力”的边界。在 Linux 且安装
`bubblewrap` 时，还会将真实 editable `lerobot-find-cameras --help` 放入生产沙箱，验证
Operation-scoped PATH、显式 PYTHONPATH 和虚拟环境 shebang。它不连接真机、不枚举摄像头、
不执行运动、不上传数据。
