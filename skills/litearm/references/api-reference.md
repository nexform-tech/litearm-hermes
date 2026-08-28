# LiteArm Hermes Plugin — API 参考

本文档列出 litearm-hermes Plugin 提供的全部工具，供 Hermes Agent 按需加载。

## 连接管理

### arm_connect

连接 LiteArm 机械臂。

| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| endpoint | string | 否 | 服务器端点 (tcp/IP:PORT)，默认从 LITEARM_ENDPOINT 环境变量读取 |

返回: `{"success": true, "arm_id": "armA", "endpoint": "..."}`

### arm_disconnect

断开连接。无参数。

---

## 状态读取

### arm_get_state

获取当前状态。无参数。

返回字段: `q` (关节角), `dq` (速度), `tau` (力矩), `fault` (故障码), `state` (状态机), `ts` (时间戳), `temperature` (温度)

### arm_get_tcp_pose

获取末端 TCP 位姿。无参数。

返回: `{"success": true, "data": [[px, py, pz], [[r00, r01, r02], ...]]}`

### arm_get_system_stats

获取系统信息。无参数。

返回: CPU 使用率、内存、主板温度、运行时间等。

---

## 运动控制

### arm_movej

关节空间运动。

| 参数 | 类型 | 必填 | 默认 | 描述 |
|------|------|------|------|------|
| q_target | float[7] | 是 | — | 目标关节角 (弧度) |
| speed | float | 否 | 0.3 | 运动速度 (0.05~1.0) |

### arm_movel

笛卡尔直线运动。

| 参数 | 类型 | 必填 | 默认 | 描述 |
|------|------|------|------|------|
| pose_goal | array | 是 | — | 目标位姿 [position, rotation] |
| speed | float | 否 | 0.3 | 运动速度 |

### arm_movec

圆弧运动。

| 参数 | 类型 | 必填 | 默认 | 描述 |
|------|------|------|------|------|
| pose_via | array | 是 | — | 中间位姿 |
| pose_goal | array | 是 | — | 目标位姿 |
| speed | float | 否 | 0.3 | 运动速度 |

### arm_movep

多航点运动。

| 参数 | 类型 | 必填 | 默认 | 描述 |
|------|------|------|------|------|
| poses_goal | array | 是 | — | 位姿列表 |
| speed | float | 否 | 0.3 | 运动速度 |

### arm_home

回零。所有关节归零，绕开限位和自碰路径检查。

| 参数 | 类型 | 必填 | 默认 | 描述 |
|------|------|------|------|------|
| speed | float | 否 | 0.3 | 运动速度 |

### arm_hold

原地保持，增加刚度。

| 参数 | 类型 | 必填 | 默认 | 描述 |
|------|------|------|------|------|
| kp_scale | float | 否 | 3.0 | 刚度放大倍数 |

### arm_zero_gravity

零重力（自由拖动）模式。

| 参数 | 类型 | 必填 | 默认 | 描述 |
|------|------|------|------|------|
| duration_s | float | 否 | 无 | 持续时间（秒），不填则手动停止 |

---

## 轨迹回放

### arm_replay_joint_path

回放关节路径。

| 参数 | 类型 | 必填 | 默认 | 描述 |
|------|------|------|------|------|
| q_path | float[][7] | 是 | — | 关节配置序列 |
| speed | float | 否 | 0.3 | 回放速度 |

### arm_replay_trajectory

回放录制的轨迹。

| 参数 | 类型 | 必填 | 默认 | 描述 |
|------|------|------|------|------|
| traj_q | float[][7] | 是 | — | 轨迹数据 |
| speed | float | 否 | 0.3 | 回放速度 |

### arm_record_trajectory

拖动录制轨迹。

| 参数 | 类型 | 必填 | 默认 | 描述 |
|------|------|------|------|------|
| duration_s | float | 是 | — | 录制时长（秒） |
| name | string | 否 | 无 | 轨迹名称 |

### arm_list_trajectories

列出已保存轨迹。无参数。

### arm_play_trajectory

加载并回放已保存轨迹。

| 参数 | 类型 | 必填 | 默认 | 描述 |
|------|------|------|------|------|
| trajectory | string | 是 | — | 轨迹 ID 或 server 端路径 |
| speed | float | 否 | 0.5 | 回放速度 |

---

## 安全

### arm_emergency_stop

⚠️ 高优先级急停。无参数。独立通道，可随时安全停机。

### arm_clear_stop

清除急停状态。无参数。

### arm_enable

使能电机并保持当前姿态。无参数。

### arm_disable

⚠️ 失能电机。无参数。机械臂会在重力作用下坠落！

### arm_clear_faults

清除电机故障。无参数。

---

## 外设设备

### arm_device_action

通用设备操作。

| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| device_id | string | 是 | 设备 ID (hand_0 / gripper_0 / teach_0) |
| action | string | 是 | 操作类型 |
| value | any | 否 | 操作值（部分 action 需要） |

支持的 action：

- **无值操作**: open, close, list_gestures, get_width, get_joints, get_buttons
- **有值操作**: set_gesture(value=手势名), set_width(value=0.0~1.0), set_force(value=0.0~1.0), finger_move(value=角度列表)

### arm_device_get_state

获取设备状态。

| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| device_id | string | 是 | 设备 ID |

---

## 遥操

### arm_enter_teleop

进入遥操模式。

| 参数 | 类型 | 必填 | 默认 | 描述 |
|------|------|------|------|------|
| mode | string | 是 | — | "master" 或 "slave" |
| peer | string | 否 | 无 | slave 时必填：主臂端点 |

### arm_exit_teleop

退出遥操。无参数。幂等。

### arm_get_teleop_status

查询遥操状态。无参数。

---

## 计算

### arm_fk

正运动学（纯计算）。关节角 → 末端位姿。

| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| q | float[7] | 是 | 关节角 (弧度) |

### arm_ik

逆运动学（纯计算）。位姿 → 关节角。

| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| pos_d | float[3] | 是 | 目标位置 [px, py, pz] |
| R_d | float[3][3] | 是 | 目标旋转矩阵 |
| q_seed | float[7] | 否 | 初始猜测关节角 |

---

## 参数设置

### arm_set_gains

设置 PD 增益。

| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| kp | float[7] | 否 | 比例增益 |
| kd | float[7] | 否 | 微分增益 |

### arm_set_payload

设置末端负载。

| 参数 | 类型 | 必填 | 默认 | 描述 |
|------|------|------|------|------|
| mass | float | 是 | — | 负载质量 (kg) |
| com | float[3] | 否 | [0,0,0] | 质心位置 |

### arm_get_joint_limits

获取关节限位。无参数。

### arm_set_joint_limits

设置关节限位。

| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| limits | object | 是 | 限位配置字典 |

### arm_set_end_effector

设置末端执行器。

| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| config | object | 是 | 末端执行器配置字典 |