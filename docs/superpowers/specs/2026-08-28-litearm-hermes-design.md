# litearm-hermes 设计文档

**日期**: 2026-08-28
**状态**: Draft
**作者**: luochun

## 1. 概述

### 1.1 目标

通过 [Hermes Agent](https://hermes-agent.nousresearch.com/)（Nous Research 开源的 AI Agent）来操作 LiteArm 机械臂。用户可以通过自然语言对话（CLI、Telegram、Discord 等）、定时自动化任务、AI 辅助编程等方式控制机械臂。

### 1.2 范围

- **全部场景**：对话控制 + 定时任务 + AI 辅助编程/调试
- **安全模式**：自由模式（开发调试阶段，人始终在旁边）
- **交付形态**：混合方案（Hermes Plugin + Skill）

### 1.3 技术栈

| 层 | 技术 |
|---|---|
| AI Agent | Hermes Agent（Nous Research） |
| 机械臂 SDK | litearm-python（Zenoh RPC 协议） |
| 控制服务 | litearm-server（部署在地瓜 192.168.31.237） |
| 语言 | Python 3.8+ |

---

## 2. 架构设计

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────────┐
│  Hermes Agent (CLI / Telegram / Discord / ...)           │
│                                                           │
│  ┌──────────────────┐   ┌──────────────────────────────┐ │
│  │  Skill            │   │  Plugin (litearm_hermes)     │ │
│  │  (SKILL.md)       │   │                              │ │
│  │                   │   │  Tools (28 个):              │ │
│  │  - 领域知识        │   │  arm_connect / arm_disconnect│ │
│  │  - 安全约束        │──▶│  arm_get_state / arm_movej   │ │
│  │  - 操作流程        │   │  arm_home / arm_movel / ...  │ │
│  │  - 故障排查        │   │  arm_device_* / arm_teleop_* │ │
│  │                   │   │  arm_emergency_stop          │ │
│  └──────────────────┘   └──────────┬───────────────────┘ │
│                                     │                     │
└─────────────────────────────────────┼─────────────────────┘
                                      │ Zenoh RPC (protobuf)
                                      ▼
┌─────────────────────────────────────────────────────────┐
│  litearm-server (地瓜/控制器 192.168.31.237:7447)        │
│  ┌─────────────────────────────────────────────────────┐│
│  │  CAN → 电机控制 → 机械臂 (7-DOF + 末端设备)          ││
│  └─────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────┘
```

### 2.2 设计原则

- **Plugin 负责"能力"**：可靠的工具执行、参数校验、连接管理
- **Skill 负责"知识"**：领域知识、安全约束、操作流程、故障排查
- **单一 Arm 连接**：模块级单例管理，避免重复连接
- **JSON 返回**：所有工具返回 JSON 字符串（Hermes 工具规范）
- **无外部依赖**：除 litearm-python 外不引入额外依赖

---

## 3. 目录结构

```
litearm-hermes/
├── plugin.yaml                 # Hermes Plugin 清单
├── litearm_hermes/
│   ├── __init__.py             # 插件入口 + register(ctx)
│   ├── arm_manager.py          # Arm 连接单例管理
│   └── tools.py                # 所有工具定义和 handler
├── skills/
│   └── litearm/
│       ├── SKILL.md            # 机械臂操作技能（主文档）
│       └── references/
│           └── api-reference.md # 完整 API 参考
├── README.md
├── README.zh-CN.md
└── pyproject.toml              # Python 包元数据（可选 pip 分发）
```

---

## 4. Plugin 设计

### 4.1 清单文件（plugin.yaml）

```yaml
name: litearm-hermes
version: 0.1.0
description: LiteArm 机械臂控制 — 通过 litearm-python SDK 操作机械臂运动、状态读取、末端设备、遥操等
author: luochun
provides_tools:
  # 连接管理
  - arm_connect
  - arm_disconnect
  # 状态读取
  - arm_get_state
  - arm_get_tcp_pose
  - arm_get_system_stats
  # 运动控制
  - arm_movej
  - arm_movel
  - arm_movec
  - arm_movep
  - arm_home
  - arm_hold
  - arm_zero_gravity
  # 轨迹回放
  - arm_replay_joint_path
  - arm_replay_trajectory
  - arm_record_trajectory
  - arm_list_trajectories
  - arm_play_trajectory
  # 安全
  - arm_emergency_stop
  - arm_clear_stop
  - arm_enable
  - arm_disable
  # 外设
  - arm_device_action
  - arm_device_get_state
  # 遥操
  - arm_enter_teleop
  - arm_exit_teleop
  - arm_get_teleop_status
  # 计算
  - arm_fk
  - arm_ik
  # 参数
  - arm_set_gains
  - arm_set_payload
  - arm_set_joint_limits
  - arm_set_end_effector
requires_env:
  - LITEARM_ENDPOINT
```

### 4.2 连接管理（arm_manager.py）

模块级单例，管理 Arm 连接生命周期：

```python
# 伪代码
_arm: Optional[Arm] = None

def get_arm(endpoint: str) -> Arm:
    """获取或创建 Arm 单例连接"""
    global _arm
    if _arm is None:
        _arm = Arm(endpoint=endpoint)
    return _arm

def close_arm():
    """关闭连接"""
    global _arm
    if _arm:
        _arm.close()
        _arm = None
```

### 4.3 工具列表详细设计

#### 连接管理

| 工具 | 参数 | 描述 |
|------|------|------|
| `arm_connect` | `endpoint` (string, optional) | 连接机械臂。默认从 `LITEARM_ENDPOINT` 环境变量读取 |
| `arm_disconnect` | 无 | 断开连接 |

#### 状态读取

| 工具 | 参数 | 描述 |
|------|------|------|
| `arm_get_state` | 无 | 获取当前关节角(q)、速度(dq)、力矩(tau)、故障码、状态机状态 |
| `arm_get_tcp_pose` | 无 | 获取当前末端位姿 (position + 3x3 rotation) |
| `arm_get_system_stats` | 无 | 获取系统信息（CPU/内存/板温/运行时间） |

#### 运动控制

| 工具 | 参数 | 描述 |
|------|------|------|
| `arm_movej` | `q_target` (float[7]), `speed` (float, default 0.3) | 关节空间运动到目标关节角 |
| `arm_movel` | `pose_goal` (position + rotation), `speed` (float, default 0.3) | 笛卡尔直线运动 |
| `arm_movec` | `pose_via`, `pose_goal`, `speed` (float, default 0.3) | 圆弧运动（经过中间点） |
| `arm_movep` | `poses_goal` (pose[]), `speed` (float, default 0.3) | 多航点笛卡尔运动 |
| `arm_home` | `speed` (float, default 0.3) | 回零（所有关节归零，绕开限位和自碰检查） |
| `arm_hold` | `kp_scale` (float, default 3.0) | 原地保持当前姿态（增加刚度） |
| `arm_zero_gravity` | `duration_s` (float, optional) | 零重力模式（自由拖动） |

**设计要点**：
- 运动工具的 `speed` 默认值为 0.3（安全低速），避免 Hermes 使用 SDK 默认的 1.0
- 所有运动工具返回 `{"success": bool, "state": "ready"}`

#### 轨迹回放

| 工具 | 参数 | 描述 |
|------|------|------|
| `arm_replay_joint_path` | `q_path` (float[][7]), `speed` (float) | 回放关节路径 |
| `arm_replay_trajectory` | `traj_q` (float[][7]), `speed` (float) | 回放录制的轨迹 |
| `arm_record_trajectory` | `duration_s` (float), `name` (string, optional) | 拖动录制轨迹 |
| `arm_list_trajectories` | 无 | 列出已保存的轨迹 |
| `arm_play_trajectory` | `trajectory` (string, 轨迹ID或路径), `speed` (float) | 加载并回放已保存轨迹 |

#### 安全

| 工具 | 参数 | 描述 |
|------|------|------|
| `arm_emergency_stop` | 无 | 高优先级急停（独立通道，可随时安全停机） |
| `arm_clear_stop` | 无 | 清除急停状态 |
| `arm_enable` | 无 | 使能电机并保持当前姿态 |
| `arm_disable` | 无 | ⚠️ 失能电机（机械臂会在重力作用下坠落！） |

#### 外设设备

| 工具 | 参数 | 描述 |
|------|------|------|
| `arm_device_action` | `device_id` (string), `action` (string), `value` (any, optional) | 通用设备操作：open/close/set_gesture/set_width/set_force/finger_move |
| `arm_device_get_state` | `device_id` (string) | 获取设备状态 |

**设计要点**：使用通用 `arm_device_action` 而非为每个设备/动作创建独立工具，减少工具数量同时保持灵活性。action 参数支持：
- `open`, `close` — 开/合
- `set_gesture` — 设置手势（需 value，如 "pinch"）
- `set_width` — 设置夹爪宽度（需 value，如 0.5）
- `set_force` — 设置抓取力（需 value，如 0.8）
- `finger_move` — 逐指运动（需 value，float[]）
- `list_gestures` — 列出支持的手势
- `get_width` — 获取夹爪宽度
- `get_joints` — 读取示教板关节角
- `get_buttons` — 读取示教板按钮

#### 遥操

| 工具 | 参数 | 描述 |
|------|------|------|
| `arm_enter_teleop` | `mode` ("master"\|"slave"), `peer` (string, slave 时必填) | 进入遥操模式 |
| `arm_exit_teleop` | 无 | 退出遥操 |
| `arm_get_teleop_status` | 无 | 查询遥操状态 |

#### 计算（纯计算，不控制硬件）

| 工具 | 参数 | 描述 |
|------|------|------|
| `arm_fk` | `q` (float[7]) | 正运动学：关节角 → 末端位姿 |
| `arm_ik` | `pos_d` (float[3]), `R_d` (float[3][3]), `q_seed` (float[7], optional) | 逆运动学：位姿 → 关节角 |

#### 参数设置

| 工具 | 参数 | 描述 |
|------|------|------|
| `arm_set_gains` | `kp` (float[7], optional), `kd` (float[7], optional) | 设置 PD 控制器增益 |
| `arm_set_payload` | `mass` (float), `com` (float[3], optional) | 设置末端负载 |
| `arm_set_joint_limits` | `limits` (dict) | 设置关节限位 |
| `arm_set_end_effector` | `config` (dict) | 设置末端执行器配置 |

---

## 5. Skill 设计

### 5.1 SKILL.md 结构

```markdown
---
name: litearm
description: LiteArm 7-DOF 机械臂控制 — 运动、状态、外设、遥操、轨迹录制
version: 0.1.0
metadata:
  hermes:
    tags: [robotics, robot-arm, litearm, manipulation]
---

# LiteArm 机械臂控制

## 概述
LiteArm 是 7-DOF 机械臂，通过 litearm-server（Zenoh RPC）控制...

## 安全约束
- 关节范围: J1[-180,180], J2[-120,120], J3[-180,180], J4[-120,120], J5[-180,180], J6[-120,120], J7[-180,180]（度）
- 运动速度: 最低 0.05，建议 0.1~0.3，最高 1.0
- 每次运动前先 arm_get_state 确认当前状态
- 运动前确保机械臂周围无人无障碍
- 遇到异常立即 arm_emergency_stop

## 典型操作流程
### 场景 1: 回零
1. arm_connect
2. arm_get_state（确认当前状态）
3. arm_home(speed=0.3)
4. arm_get_state（确认到达零位）

### 场景 2: 关节空间运动
1. arm_connect
2. arm_get_state
3. arm_movej(q_target=[0.1, 0.2, ...], speed=0.2)
4. arm_get_state（确认到达目标位置）

### 场景 3: 操作夹爪
1. arm_connect
2. arm_device_action(device_id="gripper_0", action="open")
3. arm_device_action(device_id="gripper_0", action="set_width", value=0.5)
4. arm_device_get_state(device_id="gripper_0")

### 场景 4: 录制并回放轨迹
1. arm_enable（确保使能）
2. arm_zero_gravity(duration_s=10)
3. arm_record_trajectory(duration_s=10, name="mytraj")
4. arm_list_trajectories
5. arm_play_trajectory(trajectory="mytraj", speed=0.5)

### 场景 5: 遥操主从
1. master: arm_enter_teleop(mode="master")
2. slave: arm_enter_teleop(mode="slave", peer="tcp/MASTER_IP:7447")
3. arm_get_teleop_status（监控状态）
4. arm_exit_teleop

## 位姿格式
- position: [px, py, pz]（3 元素）
- rotation: 3x3 行主序旋转矩阵，[[r00,r01,r02],[r10,r11,r12],[r20,r21,r22]]

## 故障排查
- **连接失败**: 检查 litearm-server 是否运行、网络是否通、endpoint 是否正确
- **电机故障**: arm_get_state 查看 fault 字段，arm_clear_faults 尝试清除
- **急停状态**: arm_clear_stop 清除，arm_enable 重新使能
- **运动不执行**: 检查是否在遥操态（get_teleop_status），遥操态拒绝手动控制
- **夹爪不响应**: 检查 arm_device_get_state 确认在线状态

## 注意事项
- 运动工具 speed 默认 0.3（安全低速），如需更快请显式指定
- arm_disable 会使机械臂在重力作用下坠落，慎用
- 遥操态下所有手动控制 RPC 被拒绝
- 轨迹回放前确保机械臂在安全起始位置
```

### 5.2 api-reference.md（参考文档）

列出所有 28 个工具的完整参数签名和返回值格式，供 Hermes 按需加载。

---

## 6. 数据流

### 6.1 典型对话流程

```
用户: "把机械臂回到零位"
  │
  ▼
Hermes: 加载 skill_view("litearm")
  │
  ▼
Hermes: 调用 arm_connect(endpoint="tcp/192.168.31.237:7447")
  │ Plugin: arm_manager.get_arm(endpoint) → Arm 实例
  │ 返回: {"success": true, "arm_id": "armA"}
  │
  ▼
Hermes: 调用 arm_get_state()
  │ Plugin: arm.get_state() → RobotState dict
  │ 返回: {"q": [...], "dq": [...], "state": "ready", ...}
  │
  ▼
Hermes: 调用 arm_home(speed=0.3)
  │ Plugin: arm.home(speed=0.3)
  │ SDK: RPC → Zenoh → litearm-server → CAN → 电机
  │ 返回: {"success": true, "state": "ready"}
  │
  ▼
Hermes 回复: "机械臂已回到零位 ✓ 当前关节角: [0, 0, 0, 0, 0, 0, 0]"
```

### 6.2 定时任务流程

```
Hermes Cron: "每天早上 9 点回零"
  │
  ├─ 09:00 → arm_connect → arm_home → arm_disconnect
  └─ 结果通过 Telegram 通知用户
```

---

## 7. 错误处理

### 7.1 Plugin 层

- 所有工具 handler 用 try/except 包裹
- 异常返回 `{"error": "可读的错误描述"}`
- 连接错误：提示检查 endpoint 和网络
- SDK 异常：映射到可读的中文错误信息

### 7.2 Skill 层

- 在 SKILL.md 中列举常见故障和排查步骤
- Hermes 遇到工具返回 error 时自动参考 Skill 中的故障排查指南

---

## 8. 测试策略

| 层 | 测试内容 | 方法 |
|----|---------|------|
| arm_manager | 单例创建/复用/关闭 | 单元测试（mock Arm） |
| tools | 每个工具的 handler 逻辑 | 单元测试（mock Arm） |
| 集成 | 端到端：Hermes 调用工具 → SDK → 真机 | 真机测试（.237 地瓜） |

---

## 9. 部署

### 9.1 安装

```bash
# 安装 litearm-python
pip install litearm-python

# 安装 litearm-hermes plugin
cd /path/to/litearm-hermes
pip install -e .

# 或直接复制到 Hermes plugins 目录
cp -r litearm-hermes ~/.hermes/plugins/litearm-hermes

# 设置环境变量
export LITEARM_ENDPOINT=tcp/192.168.31.237:7447
```

### 9.2 验证

```bash
# 在 Hermes 中测试
hermes chat -q "连接机械臂并读取当前状态"
```

---

## 10. 决策记录

1. **Hermes 安装位置**：安装在开发机，通过 Zenoh 远程控制地瓜（192.168.31.237:7447）
2. **多机械臂支持**：当前只需单 arm，arm_id 默认 "armA"
3. **遥操安全**：自由模式不做额外限制，用户自行负责