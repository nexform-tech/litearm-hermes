---
name: litearm
description: LiteArm 7-DOF 机械臂控制 — 运动、状态读取、末端设备、遥操、轨迹录制
version: 0.1.0
metadata:
  hermes:
    tags: [robotics, robot-arm, litearm, manipulation, hardware]
---

# LiteArm 机械臂控制

## 概述

LiteArm 是 7-DOF 机械臂，通过 litearm-server（Zenoh RPC 协议）控制。
本 Skill 配合 litearm-hermes Plugin 使用，Plugin 提供工具，Skill 提供领域知识和操作指南。

### 机械臂参数

- 自由度: 7
- 关节范围（度）: J1[-180,180], J2[-120,120], J3[-180,180], J4[-120,120], J5[-180,180], J6[-120,120], J7[-180,180]
- 运动速度: 最低 0.05，建议 0.1~0.3，最高 1.0
- 通信协议: Zenoh RPC (protobuf)，默认端口 7447

## 安全约束

**这是最重要的部分。任何操作前必须遵守：**

1. **速度默认 0.3**：所有运动工具的 speed 参数默认为 0.3（安全低速），非必要不调高
2. **先查状态**：每次运动前 先调用 `arm_get_state` 确认机械臂当前状态
3. **急停第一**：遇到任何异常，立即调用 `arm_emergency_stop`
4. **禁用慎用**：`arm_disable` 会使机械臂在重力作用下坠落，慎用
5. **遥操锁定**：遥操态下所有手动控制 RPC 被拒绝，用 `arm_exit_teleop` 退出
6. **轨迹回放**：回放前确保机械臂在安全起始位置

## 位姿格式

```
pose = [position, rotation]
position = [px, py, pz]  # 3 元素，单位：米
rotation = [[r00, r01, r02],  # 3x3 行主序旋转矩阵
            [r10, r11, r12],
            [r20, r21, r22]]
```

## 典型操作流程

### 场景 1: 回零

```
1. arm_connect (如果还没连接)
2. arm_get_state (确认当前状态)
3. arm_home(speed=0.3)
4. arm_get_state (确认到达零位)
```

### 场景 2: 关节空间运动

```
1. arm_connect
2. arm_get_state
3. arm_movej(q_target=[0.1, 0.2, 0.3, 0, 0, 0, 0], speed=0.2)
4. arm_get_state (确认到达目标)
```

### 场景 3: 笛卡尔直线运动

```
1. arm_connect
2. arm_get_state
3. arm_get_tcp_pose (获取当前位姿)
4. arm_movel(pose_goal=[[px, py, pz], [[r00, r01, r02], [r10, r11, r12], [r20, r21, r22]]], speed=0.2)
```

### 场景 4: 操作夹爪

```
1. arm_connect
2. arm_device_action(device_id="gripper_0", action="open")
3. arm_device_action(device_id="gripper_0", action="set_width", value=0.5)
4. arm_device_get_state(device_id="gripper_0")
```

### 场景 5: 操作灵巧手

```
1. arm_connect
2. arm_device_action(device_id="hand_0", action="list_gestures")  (查看支持的手势)
3. arm_device_action(device_id="hand_0", action="set_gesture", value="pinch")
4. arm_device_action(device_id="hand_0", action="open")
```

### 场景 6: 录制并回放轨迹

```
1. arm_connect
2. arm_enable (确保使能)
3. arm_record_trajectory(duration_s=10, name="mytraj")  (自动进入零重力模式，手动拖动机械臂 10 秒)
4. arm_list_trajectories (确认已保存)
5. arm_play_trajectory(trajectory="mytraj", speed=0.5)
```

注意：`arm_record_trajectory` 内部会自动进入零重力模式，不需要先调用 `arm_zero_gravity`。
如需手动控制零重力状态，可单独使用 `arm_zero_gravity(duration_s=N)` 自由拖动后，再用 `arm_record_trajectory` 录制。

### 场景 7: 遥操主从

```
Master 端:
1. arm_connect(endpoint="tcp/MASTER_IP:7447")
2. arm_enter_teleop(mode="master")

Slave 端:
1. arm_connect(endpoint="tcp/SLAVE_IP:7447")
2. arm_enter_teleop(mode="slave", peer="tcp/MASTER_IP:7447")

监控:
3. arm_get_teleop_status

退出:
4. arm_exit_teleop
```

### 场景 8: 正逆运动学计算

```
1. arm_connect
2. arm_get_state (获取当前关节角)
3. arm_fk(q=[0.1, 0.2, 0.3, 0, 0, 0, 0])  (正运动学)
4. arm_ik(pos_d=[0.5, 0, 0.3], R_d=[[1,0,0],[0,1,0],[0,0,1]])  (逆运动学)
```

## 设备操作参考

### 灵巧手 (hand_0)

| action | 描述 | value |
|--------|------|-------|
| open | 打开手掌 | 无 |
| close | 关闭手掌 | 无 |
| set_gesture | 设置手势 | "pinch", "fist", "point" 等 |
| list_gestures | 列出支持的手势 | 无 |
| finger_move | 逐指运动 | [角度列表] |
| set_force | 设置抓取力 | 0.0~1.0 |
| set_speed | 设置各指速度 | [速度列表] |
| set_torque | 设置各指力矩 | [力矩列表] |

### 夹爪 (gripper_0)

| action | 描述 | value |
|--------|------|-------|
| open | 打开 | 无 |
| close | 关闭 | 无 |
| set_width | 设置宽度 | 0.0~1.0 |
| get_width | 获取宽度 | 无 |
| set_force | 设置抓取力 | 0.0~1.0 |

### 示教板 (teach_0)

| action | 描述 | value |
|--------|------|-------|
| get_joints | 读取关节角 | 无 |
| get_buttons | 读取按钮状态 | 无 |

## 故障排查

### 连接失败
- 检查 litearm-server 是否在目标机器上运行
- 检查网络是否互通（ping 目标 IP）
- 检查 endpoint 格式是否正确（tcp/IP:PORT）
- 默认 endpoint: tcp/192.168.31.237:7447

### 电机故障
1. `arm_get_state` 查看 fault 字段
2. 尝试 `arm_clear_faults` 清除
3. 如无法清除，重启 litearm-server

### 急停状态
1. `arm_clear_stop` 清除急停
2. `arm_enable` 重新使能

### 运动不执行
- 检查 `arm_get_state` 确认状态是否为 "ready"
- 检查是否在遥操态：`arm_get_teleop_status`，遥操态拒绝手动控制
- 用 `arm_exit_teleop` 退出遥操

### 夹爪/灵巧手不响应
- `arm_device_get_state(device_id="gripper_0")` 确认在线状态
- 检查设备是否已连接：`arm_connect_device`（如需要）

## 注意事项

- 运动工具 speed 默认 0.3（安全低速），如需更快请显式指定
- `arm_disable` 会使机械臂在重力作用下坠落，**极其危险**，慎用
- 遥操态下所有手动控制 RPC 被拒绝
- 轨迹回放前确保机械臂在安全起始位置
- 位姿使用 3x3 行主序旋转矩阵，不是欧拉角/四元数
- 关节角单位是弧度，不是度