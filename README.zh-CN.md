# litearm-hermes

通过 [Hermes Agent](https://hermes-agent.nousresearch.com/) 操作 [LiteArm](https://github.com/nexform-tech) 机械臂的 Hermes Plugin + Skill。
基于 [litearm-python](https://github.com/nexform-tech/litearm-python) SDK。

## 目录

- [架构说明](#架构说明)
- [前提条件](#前提条件)
- [安装](#安装)
- [快速开始](#快速开始)
- [工具参考](#工具参考)
- [使用场景](#使用场景)
- [安全说明](#安全说明)
- [故障排查](#故障排查)
- [目录结构](#目录结构)
- [开发](#开发)

## 架构说明

```
┌─────────────────────────────────────────────────────────┐
│  Hermes Agent (CLI / Telegram / Discord / Slack / ...)   │
│                                                           │
│  ┌──────────────────┐   ┌──────────────────────────────┐ │
│  │  Skill            │   │  Plugin (litearm_hermes)     │ │
│  │  (SKILL.md)       │   │                              │ │
│  │                   │   │  34 个工具:                  │ │
│  │  领域知识          │──▶│  arm_connect / arm_movej    │ │
│  │  安全规则          │   │  arm_home / arm_get_state   │ │
│  │  操作流程          │   │  arm_device_* / arm_teleop_* │ │
│  │  故障排查          │   │  arm_emergency_stop / ...    │ │
│  └──────────────────┘   └──────────┬───────────────────┘ │
│                                     │ Zenoh RPC            │
└─────────────────────────────────────┼─────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────┐
│  litearm-server（运行在机械臂控制器上，如 192.168.31.237:7447） │
│  ┌─────────────────────────────────────────────────────┐│
│  │  CAN 总线 → 电机驱动 → 7-DOF 机械臂 + 末端执行器     ││
│  └─────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────┘
```

**工作原理：**

1. **Plugin**（Python）— 提供 34 个结构化工具，调用 litearm-python SDK 方法。每个工具都有 JSON Schema 定义、参数校验和错误处理。Plugin 以单例模式管理 Arm 连接，无需每次调用都重新连接。

2. **Skill**（SKILL.md）— Hermes 按需加载的 Markdown 文档。教 AI 理解机械臂：关节范围、安全规则、典型操作流程、故障排查方法。这是"知识"层。

3. **Hermes Agent** 统筹一切 — 读取 Skill 理解领域知识，再调用 Plugin 工具执行命令。你可以通过 CLI、Telegram、Discord、Slack 或任何支持的平台与之交互。

## 前提条件

### 软件

| 要求 | 版本 | 说明 |
|------|------|------|
| Python | ≥ 3.8 | |
| [Hermes Agent](https://hermes-agent.nousresearch.com/) | 最新版 | 通过 `curl -fsSL https://hermes-agent.nousresearch.com/install.sh \| bash` 安装 |
| [litearm-python](https://github.com/nexform-tech/litearm-python) | 最新版 | `pip install litearm-python` |
| litearm-server | 运行中 | 部署在机械臂控制器上（如 192.168.31.237） |

### 硬件

- LiteArm 7-DOF 机械臂（CAN 总线连接）
- 控制器（如 NVIDIA Jetson 地瓜），运行 litearm-server
- Hermes 主机与控制器之间网络互通

### 网络

Hermes Agent 主机必须能访问 litearm-server。默认端口 **7447**（Zenoh）。验证连通性：

```bash
# 从 Hermes 主机执行
ping 192.168.31.237

# 或测试 Zenoh 端口
nc -zv 192.168.31.237 7447
```

## 安装

### 第一步：安装 litearm-python SDK

```bash
pip install litearm-python
```

如果从源码安装：

```bash
cd /path/to/litearm-python
pip install -e .
```

### 第二步：安装 litearm-hermes Plugin

**方式 A：复制到 Hermes 插件目录（推荐）**

```bash
# 复制 Plugin
cp -r /path/to/litearm-hermes ~/.hermes/plugins/litearm-hermes

# 复制 Skill
mkdir -p ~/.hermes/skills
cp -r /path/to/litearm-hermes/skills/litearm ~/.hermes/skills/
```

**方式 B：pip 安装**

```bash
cd /path/to/litearm-hermes
pip install -e .
```

pip 安装后，通过 `hermes_agent.plugins` entry point 自动注册，Hermes 会自动发现。

### 第三步：配置环境变量

```bash
# 设置 LiteArm 服务器端点（建议添加到 ~/.bashrc 或 ~/.zshrc 持久化）
export LITEARM_ENDPOINT=tcp/192.168.31.237:7447
```

`LITEARM_ENDPOINT` 环境变量是默认服务器地址。也可以在 `arm_connect` 调用时显式传入：

```
arm_connect(endpoint="tcp/192.168.31.237:7447")
```

### 第四步：验证安装

```bash
# 检查 Plugin 已加载
hermes plugins list | grep litearm

# 检查 Skill 可用
hermes skills list | grep litearm

# 快速测试（只读，不运动）
hermes chat -q "连接机械臂并告诉我当前状态"
```

如果一切正常，Hermes 会：
1. 加载 litearm skill
2. 调用 `arm_connect` 连接
3. 调用 `arm_get_state` 读取状态
4. 报告当前关节角、状态等信息

## 快速开始

### 1. 基本连接和状态读取

```
你: 连接机械臂，显示当前状态。
```

Hermes 会依次调用 `arm_connect` → `arm_get_state`，报告关节角、速度、力矩、故障等信息。

### 2. 回零

```
你: 把机械臂回到零位，速度 0.3。
```

Hermes 调用 `arm_home(speed=0.3)` — 所有关节归零，绕开限位和自碰检查。

### 3. 关节空间运动

```
你: 把关节 1 移到 0.5 弧度，关节 2 移到 0.3 弧度，其余为 0，速度 0.2。
```

Hermes 调用 `arm_movej(q_target=[0.5, 0.3, 0, 0, 0, 0, 0], speed=0.2)`。

### 4. 操作夹爪

```
你: 打开夹爪，然后关到 50% 宽度。
```

Hermes 调用：
1. `arm_device_action(device_id="gripper_0", action="open")`
2. `arm_device_action(device_id="gripper_0", action="set_width", value=0.5)`

### 5. 急停

```
你: 立即停止机械臂！
```

Hermes 调用 `arm_emergency_stop()` — 高优先级急停，独立通道。

### 6. 录制并回放轨迹

```
你: 录制一个 10 秒的轨迹，命名为 "demo"，然后用半速回放。
```

Hermes 调用：
1. `arm_enable()`
2. `arm_record_trajectory(duration_s=10, name="demo")`
3. `arm_play_trajectory(trajectory="demo", speed=0.5)`

### 7. 遥操设置

```
你: 把这个机械臂设为主臂，进入遥操模式。
```

Hermes 调用 `arm_enter_teleop(mode="master")`。

### 8. 正/逆运动学计算

```
你: 所有关节都在 0.1 弧度时，末端位姿是什么？
```

Hermes 调用 `arm_fk(q=[0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1])`。

### 9. 定时自动化（通过 Hermes Cron）

```
你: 每天早上 9 点让机械臂回零。
```

Hermes 设置 cron 任务：每天 9:00 自动执行 `arm_connect → arm_home(speed=0.3) → arm_disconnect`。

## 工具参考

所有 34 个工具按类别分组。每个工具返回 JSON 字符串，格式为 `{"success": true/false, ...}`。

### 连接管理

| 工具 | 参数 | 说明 |
|------|------|------|
| `arm_connect` | `endpoint`（string，可选） | 连接机械臂。默认从 `LITEARM_ENDPOINT` 环境变量读取 |
| `arm_disconnect` | 无 | 断开连接 |

### 状态读取

| 工具 | 参数 | 返回值 |
|------|------|--------|
| `arm_get_state` | 无 | `q`（关节角）、`dq`（速度）、`tau`（力矩）、`fault`（故障码）、`state`（状态机）、`ts`（时间戳）、`temperature`（温度） |
| `arm_get_tcp_pose` | 无 | `position` [px,py,pz]、`rotation` 3x3 行主序矩阵 |
| `arm_get_system_stats` | 无 | CPU 使用率、内存、主板温度、运行时间 |

### 运动控制

| 工具 | 参数 | 说明 |
|------|------|------|
| `arm_movej` | `q_target`（float[7]）、`speed`（float，默认 0.3） | 关节空间运动。角度单位：**弧度** |
| `arm_movel` | `pose_goal`（array）、`speed`（float，默认 0.3） | 笛卡尔直线运动 |
| `arm_movec` | `pose_via`、`pose_goal`、`speed`（float，默认 0.3） | 圆弧运动（经过中间点） |
| `arm_movep` | `poses_goal`（array[]）、`speed`（float，默认 0.3） | 多航点笛卡尔运动 |
| `arm_home` | `speed`（float，默认 0.3） | 回零：所有关节归零，绕开限位和自碰检查 |
| `arm_hold` | `kp_scale`（float，默认 3.0） | 原地保持，增加刚度 |
| `arm_zero_gravity` | `duration_s`（float，可选） | 零重力（自由拖动）模式 |

### 轨迹回放

| 工具 | 参数 | 说明 |
|------|------|------|
| `arm_replay_joint_path` | `q_path`（float[][7]）、`speed`（float，默认 0.3） | 回放关节配置序列 |
| `arm_replay_trajectory` | `traj_q`（float[][7]）、`speed`（float，默认 0.3） | 回放录制的轨迹 |
| `arm_record_trajectory` | `duration_s`（float）、`name`（string，可选） | 拖动录制轨迹，自动进入零重力模式 |
| `arm_list_trajectories` | 无 | 列出所有已保存轨迹 |
| `arm_play_trajectory` | `trajectory`（string）、`speed`（float，默认 0.5） | 加载并回放已保存轨迹（通过 ID 或路径） |

### 安全

| 工具 | 参数 | 说明 |
|------|------|------|
| `arm_emergency_stop` | 无 | ⚠️ 高优先级急停，独立通道，随时可用 |
| `arm_clear_stop` | 无 | 清除急停状态，恢复就绪 |
| `arm_enable` | 无 | 使能所有电机并保持当前姿态 |
| `arm_disable` | 无 | ⚠️ 失能所有电机 — 机械臂会在重力作用下坠落！ |
| `arm_clear_faults` | 无 | 清除电机故障 |

### 末端设备

| 工具 | 参数 | 说明 |
|------|------|------|
| `arm_device_action` | `device_id`（string）、`action`（string）、`value`（any，可选） | 通用设备操作。详见下表 |
| `arm_device_get_state` | `device_id`（string） | 获取设备状态/信息 |

**各设备支持的 action：**

| 设备 | device_id | 支持的 action |
|------|-----------|--------------|
| **灵巧手** | `hand_0` | `open`、`close`、`set_gesture`（value: "pinch"/"fist"/"point"/...）、`list_gestures`、`finger_move`（value: float[]）、`set_force`（value: 0.0~1.0）、`set_speed`（value: float[]）、`set_torque`（value: float[]） |
| **夹爪** | `gripper_0` | `open`、`close`、`set_width`（value: 0.0~1.0）、`get_width`、`set_force`（value: 0.0~1.0） |
| **示教板** | `teach_0` | `get_joints`、`get_buttons` |

### 遥操

| 工具 | 参数 | 说明 |
|------|------|------|
| `arm_enter_teleop` | `mode`（"master"\|"slave"）、`peer`（string，slave 时必填） | 进入遥操模式。master 发布关节流；slave 跟随 |
| `arm_exit_teleop` | 无 | 退出遥操。幂等操作 |
| `arm_get_teleop_status` | 无 | 查询遥操状态（active/mode/stats） |

### 计算（纯计算，不控制硬件）

| 工具 | 参数 | 说明 |
|------|------|------|
| `arm_fk` | `q`（float[7]） | 正运动学：关节角 → 末端位姿 |
| `arm_ik` | `pos_d`（float[3]）、`R_d`（float[3][3]）、`q_seed`（float[7]，可选） | 逆运动学：位姿 → 关节角 |

### 参数设置

| 工具 | 参数 | 说明 |
|------|------|------|
| `arm_set_gains` | `kp`（float[7]，可选）、`kd`（float[7]，可选） | 设置 PD 控制器增益 |
| `arm_set_payload` | `mass`（float）、`com`（float[3]，可选，默认 [0,0,0]） | 设置末端负载（质量 + 质心） |
| `arm_get_joint_limits` | 无 | 获取当前关节限位配置 |
| `arm_set_joint_limits` | `limits`（object） | 设置关节限位 |
| `arm_set_end_effector` | `config`（object） | 设置末端执行器配置 |

### 位姿格式

所有位姿使用 `[position, rotation]` 格式：

```python
position = [px, py, pz]           # 3 元素，单位：米
rotation = [[r00, r01, r02],      # 3×3 行主序旋转矩阵
            [r10, r11, r12],
            [r20, r21, r22]]
```

关节角单位为**弧度**，不是度。

## 使用场景

### 场景 1：每日回零

> *"每天早上 9 点让机械臂回零，并报告状态。"*

可设置为 Hermes cron 任务，附加 litearm skill。Agent 会：
1. 连接机械臂
2. 读取当前状态
3. 回零
4. 通过消息平台报告完成

### 场景 2：轨迹录制

> *"我想录制一个倒水动作。让我拖动机械臂。"*

1. `arm_enable` — 使能电机
2. `arm_record_trajectory(duration_s=15, name="pour")` — 自动进入零重力，手动拖动 15 秒
3. `arm_list_trajectories` — 确认已保存
4. `arm_play_trajectory(trajectory="pour", speed=0.3)` — 低速测试回放
5. `arm_play_trajectory(trajectory="pour", speed=1.0)` — 全速回放

### 场景 3：夹爪取放

> *"用夹爪夹起物体，移到箱子，松开。"*

1. `arm_get_state` — 确认就绪
2. `arm_movej(q_target=[...], speed=0.2)` — 移到取料位置
3. `arm_device_action(device_id="gripper_0", action="close")` — 夹紧
4. `arm_movej(q_target=[...], speed=0.2)` — 移到放料位置
5. `arm_device_action(device_id="gripper_0", action="open")` — 松开

### 场景 4：遥操

> *"把这个机械臂设为从臂，跟随 10.0.0.2 的主臂。"*

1. `arm_connect(endpoint="tcp/SLAVE_IP:7447")`
2. `arm_enter_teleop(mode="slave", peer="tcp/10.0.0.2:7447")`
3. `arm_get_teleop_status` — 监控
4. `arm_exit_teleop` — 完成后退出

### 场景 5：FK/IK 调试

> *"我想让末端到达位置 [0.5, 0, 0.3]，方向朝前。需要哪些关节角？"*

1. `arm_ik(pos_d=[0.5, 0, 0.3], R_d=[[1,0,0],[0,1,0],[0,0,1]])` — 计算关节角
2. `arm_fk(q=[...])` — 验证结果
3. `arm_movej(q_target=[...], speed=0.2)` — 执行

## 安全说明

> ⚠️ **重要：本插件运行在"自由模式"下 — 无确认提示。机械臂会在收到指令后立即运动。使用本插件时，务必有人在急停旁值守。**

### 安全规则

1. **默认速度 0.3** — 所有运动工具默认 `speed=0.3`（安全低速）。只在确认安全后才调高速度。
2. **先查状态** — 每次运动前必须先调用 `arm_get_state` 确认机械臂状态。
3. **急停随时可用** — `arm_emergency_stop` 使用独立通道，遇到任何异常立即调用。
4. **禁用电机极其危险** — `arm_disable` 切断所有电机电源，机械臂会在重力作用下坠落。
5. **遥操锁定手动控制** — 遥操态下所有手动 RPC 被拒绝，用 `arm_exit_teleop` 退出。
6. **保持工作空间清空** — 运动前确保机械臂周围无人无障碍。

### 关节限位

| 关节 | 范围（度） | 范围（弧度） |
|------|-----------|-------------|
| J1 | [-180, 180] | [-π, π] |
| J2 | [-120, 120] | [-2π/3, 2π/3] |
| J3 | [-180, 180] | [-π, π] |
| J4 | [-120, 120] | [-2π/3, 2π/3] |
| J5 | [-180, 180] | [-π, π] |
| J6 | [-120, 120] | [-2π/3, 2π/3] |
| J7 | [-180, 180] | [-π, π] |

## 故障排查

### 连接失败

```
错误: "No valid reply received"
```

**原因和解决方案：**
1. **litearm-server 未运行** — SSH 到控制器启动：
   ```bash
   ssh sunrise@192.168.31.237
   cd ~/luo && ./start_server.sh
   ```
2. **网络不通** — 验证连通性：`ping 192.168.31.237`
3. **端点错误** — 检查格式是否为 `tcp/IP:PORT`
4. **防火墙阻挡 7447 端口** — 检查 iptables 规则
5. **LITEARM_ENDPOINT 未设置** — 验证：`echo $LITEARM_ENDPOINT`

### 电机故障

1. 调用 `arm_get_state` 检查 `fault` 字段
2. 尝试 `arm_clear_faults` 清除软故障
3. 如无法清除，重启控制器上的 litearm-server
4. 检查控制器上的 CAN 总线连接

### 急停状态

1. 调用 `arm_clear_stop` 清除急停
2. 调用 `arm_enable` 重新使能
3. 用 `arm_get_state` 确认状态为 "ready"

### 运动不执行

1. 检查 `arm_get_state` — 状态必须是 "ready"
2. 检查 `arm_get_teleop_status` — 遥操态拒绝手动命令
3. 如果在遥操态，调用 `arm_exit_teleop` 退出
4. 通过 `arm_get_state` → `fault` 字段检查故障

### 夹爪/灵巧手不响应

1. 调用 `arm_device_get_state(device_id="gripper_0")` 确认在线状态
2. 确认控制器上设备 daemon 已启动
3. 检查末端执行器的 CAN 总线连接

### Hermes 相关问题

**Plugin 未加载：**
```bash
hermes plugins list | grep litearm
# 如果未找到，检查 plugin 目录：
ls ~/.hermes/plugins/litearm-hermes/plugin.yaml
```

**Skill 未找到：**
```bash
hermes skills list | grep litearm
# 如果未找到，检查 skill 目录：
ls ~/.hermes/skills/litearm/SKILL.md
```

**环境变量未设置：**
```bash
# 当前 shell 检查
echo $LITEARM_ENDPOINT

# 持久化设置，添加到 ~/.bashrc：
echo 'export LITEARM_ENDPOINT=tcp/192.168.31.237:7447' >> ~/.bashrc
source ~/.bashrc
```

## 目录结构

```
litearm-hermes/
├── plugin.yaml                      # Hermes Plugin 清单（名称、版本、工具列表、环境变量）
├── litearm_hermes/
│   └── __init__.py                  # 插件入口。所有 34 个工具定义在此。
│                                     #   - Schema 定义（每个工具的 JSON Schema）
│                                     #   - Handler 函数（调用 litearm SDK 的 Python 代码）
│                                     #   - 连接单例（_get_arm / _close_arm）
│                                     #   - 错误处理（_safe_call / _ok / _err）
│                                     #   - register(ctx) — Hermes 插件入口点
├── skills/
│   └── litearm/
│       ├── SKILL.md                 # Hermes 加载的 Skill 文档：
│       │                             #   - 领域知识（关节范围、速度限制）
│       │                             #   - 安全规则（6 条）
│       │                             #   - 8 个操作场景
│       │                             #   - 设备操作参考
│       │                             #   - 故障排查指南
│       └── references/
│           └── api-reference.md     # 完整 API 参考（34 个工具的参数说明）
├── docs/
│   └── superpowers/
│       └── specs/
│           └── 2026-08-28-litearm-hermes-design.md  # 设计文档
├── README.md                        # 英文使用说明
├── README.zh-CN.md                  # 本文件（中文使用说明）
└── pyproject.toml                   # Python 包配置 + Hermes entry point
```

## 开发

### 运行测试

```bash
# 安装开发依赖
pip install -e ".[dev]"

# 运行单元测试（不需要 server）
python -m pytest tests/ -v
```

### 真机测试

```bash
# 确保控制器上 arm server 已运行
# 设置端点
export LITEARM_ENDPOINT=tcp/192.168.31.237:7447

# 启动 Hermes 测试
hermes chat -q "连接机械臂并读取状态"
```

### Plugin 验证

```bash
# 验证 Plugin 结构
hermes plugins doctor ~/.hermes/plugins/litearm-hermes
```

### 添加新工具

1. 在 `litearm_hermes/__init__.py` 中添加 `SCHEMA` 字典和 handler 函数
2. 将工具添加到 `TOOLS` 字典
3. 将工具名添加到 `plugin.yaml` → `provides_tools`
4. 更新 `skills/litearm/references/api-reference.md`
5. 必要时更新 `skills/litearm/SKILL.md`

### 代码规范

- 所有 handler 返回 JSON 字符串（不返回原始 dict）
- 错误返回 `{"success": false, "error": "描述"}`
- 成功返回 `{"success": true, ...}`
- 对可能抛出异常的函数调用使用 `_safe_call()`
- 所有运动工具 speed 默认 0.3

## License

Proprietary