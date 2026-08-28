"""litearm-hermes: Hermes Agent Plugin for LiteArm robot arm control.

通过 litearm-python SDK 操作 LiteArm 机械臂，以 Hermes Plugin 形式注册工具。
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Arm 连接单例
# ---------------------------------------------------------------------------

_arm: Any = None  # litearm.Arm instance
_arm_endpoint: Optional[str] = None


def _get_endpoint(endpoint: Optional[str] = None) -> str:
    return endpoint or os.environ.get("LITEARM_ENDPOINT", "tcp/127.0.0.1:7447")


def _get_arm(endpoint: Optional[str] = None) -> Any:
    """获取或创建 Arm 单例连接。"""
    global _arm, _arm_endpoint
    ep = _get_endpoint(endpoint)
    if _arm is None:
        import litearm

        logger.info("Connecting to LiteArm at %s", ep)
        _arm = litearm.Arm(endpoint=ep)
        _arm_endpoint = ep
    elif endpoint and ep != _arm_endpoint:
        # 新 endpoint 替旧
        _arm.close()
        import litearm

        _arm = litearm.Arm(endpoint=ep)
        _arm_endpoint = ep
    return _arm


def _close_arm() -> None:
    """断开连接。"""
    global _arm, _arm_endpoint
    if _arm:
        try:
            _arm.close()
        except Exception:
            pass
        _arm = None
        _arm_endpoint = None


# ---------------------------------------------------------------------------
# 工具 helper
# ---------------------------------------------------------------------------


def _ok(data: Any = None) -> str:
    return json.dumps({"success": True, **(data or {})}, ensure_ascii=False)


def _err(msg: str) -> str:
    return json.dumps({"success": False, "error": msg}, ensure_ascii=False)


def _safe_call(fn, *args, **kwargs) -> str:
    """安全调用，异常转 JSON error。"""
    try:
        result = fn(*args, **kwargs)
        if isinstance(result, dict):
            return json.dumps({"success": True, **result}, ensure_ascii=False, default=str)
        elif isinstance(result, bool):
            return json.dumps({"success": result}, ensure_ascii=False)
        elif isinstance(result, (list, tuple)):
            return json.dumps({"success": True, "data": result}, ensure_ascii=False, default=str)
        elif result is None:
            return json.dumps({"success": True}, ensure_ascii=False)
        else:
            return json.dumps({"success": True, "data": result}, ensure_ascii=False, default=str)
    except Exception as e:
        logger.exception("Tool call failed")
        return _err(str(e))


# ---------------------------------------------------------------------------
# 连接管理
# ---------------------------------------------------------------------------

CONNECT_SCHEMA = {
    "name": "arm_connect",
    "description": "连接 LiteArm 机械臂。默认从 LITEARM_ENDPOINT 环境变量读取地址。",
    "parameters": {
        "type": "object",
        "properties": {
            "endpoint": {
                "type": "string",
                "description": "LiteArm server 端点 (e.g. tcp/192.168.31.237:7447)。留空则用 LITEARM_ENDPOINT 环境变量。",
            },
        },
    },
}


def arm_connect(endpoint: Optional[str] = None) -> str:
    arm = _get_arm(endpoint)
    return _ok({"arm_id": arm._arm_id, "endpoint": _get_endpoint(endpoint)})


DISCONNECT_SCHEMA = {
    "name": "arm_disconnect",
    "description": "断开 LiteArm 机械臂连接。",
    "parameters": {"type": "object", "properties": {}},
}


def arm_disconnect() -> str:
    _close_arm()
    return _ok()


# ---------------------------------------------------------------------------
# 状态读取
# ---------------------------------------------------------------------------

GET_STATE_SCHEMA = {
    "name": "arm_get_state",
    "description": "获取机械臂当前状态：关节角(q)、速度(dq)、力矩(tau)、故障码、状态机状态、时间戳等。",
    "parameters": {"type": "object", "properties": {}},
}


def arm_get_state() -> str:
    arm = _get_arm()
    state = arm.get_state()
    if state is None:
        return _err("尚未收到状态数据，请稍后重试")
    return _ok({"state": state})


GET_TCP_POSE_SCHEMA = {
    "name": "arm_get_tcp_pose",
    "description": "获取当前末端 TCP 位姿：position [px,py,pz] + rotation 3x3 矩阵。",
    "parameters": {"type": "object", "properties": {}},
}


def arm_get_tcp_pose() -> str:
    return _safe_call(_get_arm().get_tcp_pose)


GET_SYSTEM_STATS_SCHEMA = {
    "name": "arm_get_system_stats",
    "description": "获取系统信息：CPU 使用率、内存、主板温度、运行时间等。",
    "parameters": {"type": "object", "properties": {}},
}


def arm_get_system_stats() -> str:
    return _safe_call(_get_arm().get_system_stats)


# ---------------------------------------------------------------------------
# 运动控制
# ---------------------------------------------------------------------------

MOVEJ_SCHEMA = {
    "name": "arm_movej",
    "description": "关节空间运动：移动到目标关节角。7 关节，角度单位：弧度。",
    "parameters": {
        "type": "object",
        "properties": {
            "q_target": {
                "type": "array",
                "items": {"type": "number"},
                "minItems": 7,
                "maxItems": 7,
                "description": "目标关节角 [j1, j2, j3, j4, j5, j6, j7]（弧度）",
            },
            "speed": {
                "type": "number",
                "description": "运动速度比例 (0.05~1.0，默认 0.3)",
                "default": 0.3,
            },
        },
        "required": ["q_target"],
    },
}


def arm_movej(q_target: list, speed: float = 0.3) -> str:
    return _safe_call(_get_arm().movej, q_target, speed=speed)


MOVEL_SCHEMA = {
    "name": "arm_movel",
    "description": "笛卡尔直线运动到目标位姿。pose 格式: [position, rotation]，position=[px,py,pz]，rotation=3x3 行主序矩阵。",
    "parameters": {
        "type": "object",
        "properties": {
            "pose_goal": {
                "type": "array",
                "description": "目标位姿 [position, rotation_matrix]",
            },
            "speed": {
                "type": "number",
                "description": "运动速度比例 (默认 0.3)",
                "default": 0.3,
            },
        },
        "required": ["pose_goal"],
    },
}


def arm_movel(pose_goal: list, speed: float = 0.3) -> str:
    return _safe_call(_get_arm().movel, pose_goal, speed=speed)


MOVEC_SCHEMA = {
    "name": "arm_movec",
    "description": "圆弧运动：经过中间点到达目标位姿。",
    "parameters": {
        "type": "object",
        "properties": {
            "pose_via": {"type": "array", "description": "中间位姿 [position, rotation]"},
            "pose_goal": {"type": "array", "description": "目标位姿 [position, rotation]"},
            "speed": {"type": "number", "description": "运动速度 (默认 0.3)", "default": 0.3},
        },
        "required": ["pose_via", "pose_goal"],
    },
}


def arm_movec(pose_via: list, pose_goal: list, speed: float = 0.3) -> str:
    return _safe_call(_get_arm().movec, pose_via, pose_goal, speed=speed)


MOVEP_SCHEMA = {
    "name": "arm_movep",
    "description": "多航点笛卡尔运动：依次经过多个位姿航点。",
    "parameters": {
        "type": "object",
        "properties": {
            "poses_goal": {"type": "array", "description": "位姿列表 [[position, rotation], ...]"},
            "speed": {"type": "number", "description": "运动速度 (默认 0.3)", "default": 0.3},
        },
        "required": ["poses_goal"],
    },
}


def arm_movep(poses_goal: list, speed: float = 0.3) -> str:
    return _safe_call(_get_arm().movep, poses_goal, speed=speed)


HOME_SCHEMA = {
    "name": "arm_home",
    "description": "回零：所有关节归零（绕开限位和自碰路径检查）。",
    "parameters": {
        "type": "object",
        "properties": {
            "speed": {"type": "number", "description": "运动速度 (默认 0.3)", "default": 0.3},
        },
    },
}


def arm_home(speed: float = 0.3) -> str:
    return _safe_call(_get_arm().home, speed=speed)


HOLD_SCHEMA = {
    "name": "arm_hold",
    "description": "原地保持当前姿态，增加刚度。",
    "parameters": {
        "type": "object",
        "properties": {
            "kp_scale": {"type": "number", "description": "刚度放大倍数 (默认 3.0)", "default": 3.0},
        },
    },
}


def arm_hold(kp_scale: float = 3.0) -> str:
    return _safe_call(_get_arm().hold, kp_scale=kp_scale)


ZERO_GRAVITY_SCHEMA = {
    "name": "arm_zero_gravity",
    "description": "零重力（自由拖动）模式。机械臂可被手动拖动，用于录制轨迹。",
    "parameters": {
        "type": "object",
        "properties": {
            "duration_s": {
                "type": "number",
                "description": "持续时间（秒），不指定则手动停止",
            },
        },
    },
}


def arm_zero_gravity(duration_s: Optional[float] = None) -> str:
    return _safe_call(_get_arm().zero_gravity, duration_s=duration_s)


# ---------------------------------------------------------------------------
# 轨迹回放
# ---------------------------------------------------------------------------

REPLAY_JOINT_PATH_SCHEMA = {
    "name": "arm_replay_joint_path",
    "description": "回放关节路径：依次执行关节配置序列。",
    "parameters": {
        "type": "object",
        "properties": {
            "q_path": {"type": "array", "description": "关节配置列表 [[j1..j7], ...]"},
            "speed": {"type": "number", "description": "回放速度 (默认 0.3)", "default": 0.3},
        },
        "required": ["q_path"],
    },
}


def arm_replay_joint_path(q_path: list, speed: float = 0.3) -> str:
    return _safe_call(_get_arm().replay_joint_path, q_path, speed=speed)


REPLAY_TRAJECTORY_SCHEMA = {
    "name": "arm_replay_trajectory",
    "description": "回放录制的轨迹（JointTrajectory 格式）。",
    "parameters": {
        "type": "object",
        "properties": {
            "traj_q": {"type": "array", "description": "轨迹关节数据 [[j1..j7], ...]"},
            "speed": {"type": "number", "description": "回放速度 (默认 0.3)", "default": 0.3},
        },
        "required": ["traj_q"],
    },
}


def arm_replay_trajectory(traj_q: list, speed: float = 0.3) -> str:
    return _safe_call(_get_arm().replay_trajectory, traj_q, speed=speed)


RECORD_TRAJECTORY_SCHEMA = {
    "name": "arm_record_trajectory",
    "description": "拖动录制轨迹：先进入零重力模式，手动拖动机械臂，录制关节轨迹。",
    "parameters": {
        "type": "object",
        "properties": {
            "duration_s": {
                "type": "number",
                "description": "录制时长（秒）",
            },
            "name": {
                "type": "string",
                "description": "轨迹名称（可选）",
            },
        },
        "required": ["duration_s"],
    },
}


def arm_record_trajectory(duration_s: float, name: Optional[str] = None) -> str:
    return _safe_call(_get_arm().record_trajectory, duration_s=duration_s, name=name)


LIST_TRAJECTORIES_SCHEMA = {
    "name": "arm_list_trajectories",
    "description": "列出所有已保存的轨迹。",
    "parameters": {"type": "object", "properties": {}},
}


def arm_list_trajectories() -> str:
    return _safe_call(_get_arm().list_trajectories)


PLAY_TRAJECTORY_SCHEMA = {
    "name": "arm_play_trajectory",
    "description": "加载并回放已保存的轨迹（通过轨迹 ID 或路径）。",
    "parameters": {
        "type": "object",
        "properties": {
            "trajectory": {
                "type": "string",
                "description": "轨迹 ID（如 'mytraj'）或 server 端文件路径",
            },
            "speed": {"type": "number", "description": "回放速度 (默认 0.5)", "default": 0.5},
        },
        "required": ["trajectory"],
    },
}


def arm_play_trajectory(trajectory: str, speed: float = 0.5) -> str:
    return _safe_call(_get_arm().play_trajectory, trajectory, speed=speed)


# ---------------------------------------------------------------------------
# 安全
# ---------------------------------------------------------------------------

EMERGENCY_STOP_SCHEMA = {
    "name": "arm_emergency_stop",
    "description": "⚠️ 高优先级急停 — 独立通道，可随时安全停机。机械臂立即停止运动。",
    "parameters": {"type": "object", "properties": {}},
}


def arm_emergency_stop() -> str:
    try:
        _get_arm().request_stop()
    except Exception as e:
        return _err(f"急停发送失败: {e}")
    return _ok({"message": "急停已发送"})


CLEAR_STOP_SCHEMA = {
    "name": "arm_clear_stop",
    "description": "清除急停状态，恢复就绪。",
    "parameters": {"type": "object", "properties": {}},
}


def arm_clear_stop() -> str:
    return _safe_call(_get_arm().clear_stop)


ENABLE_SCHEMA = {
    "name": "arm_enable",
    "description": "使能所有电机并保持当前姿态。",
    "parameters": {"type": "object", "properties": {}},
}


def arm_enable() -> str:
    return _safe_call(_get_arm().enable)


DISABLE_SCHEMA = {
    "name": "arm_disable",
    "description": "⚠️ 失能所有电机 — 机械臂会在重力作用下坠落！请确保已做好防护。",
    "parameters": {"type": "object", "properties": {}},
}


def arm_disable() -> str:
    return _safe_call(_get_arm().disable)


CLEAR_FAULTS_SCHEMA = {
    "name": "arm_clear_faults",
    "description": "清除电机故障。",
    "parameters": {"type": "object", "properties": {}},
}


def arm_clear_faults() -> str:
    return _safe_call(_get_arm().clear_faults)


# ---------------------------------------------------------------------------
# 外设设备
# ---------------------------------------------------------------------------

DEVICE_ACTION_SCHEMA = {
    "name": "arm_device_action",
    "description": (
        "操作末端外设设备。支持的 action: "
        "open(打开), close(关闭), "
        "set_gesture(设置手势,需value), "
        "set_width(设置夹爪宽度,需value), "
        "set_force(设置抓取力,需value), "
        "finger_move(逐指运动,需value[float[]]), "
        "list_gestures(列出手势), "
        "get_width(获取夹爪宽度), "
        "get_joints(读取示教板关节角), "
        "get_buttons(读取示教板按钮)"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "device_id": {
                "type": "string",
                "description": "设备 ID (hand_0 / gripper_0 / teach_0)",
            },
            "action": {
                "type": "string",
                "description": "操作类型 (open/close/set_gesture/set_width/set_force/finger_move/list_gestures/get_width/get_joints/get_buttons)",
            },
            "value": {
                "description": "操作值（部分 action 需要）",
            },
        },
        "required": ["device_id", "action"],
    },
}


def arm_device_action(device_id: str, action: str, value: Any = None) -> str:
    arm = _get_arm()
    dev = arm.device(device_id)

    # 无值操作
    no_value_actions = {
        "open": dev.open,
        "close": dev.close,
        "list_gestures": dev.list_gestures,
        "get_width": dev.get_width,
        "get_joints": dev.get_joints,
        "get_buttons": dev.get_buttons,
    }

    if action in no_value_actions:
        return _safe_call(no_value_actions[action])

    # 有值操作
    if action == "set_gesture":
        return _safe_call(dev.set_gesture, value)
    elif action == "set_width":
        return _safe_call(dev.set_width, value)
    elif action == "set_force":
        return _safe_call(dev.set_force, value)
    elif action == "finger_move":
        return _safe_call(dev.finger_move, value)
    else:
        return _err(f"未知 action: {action}。支持的 action: open/close/set_gesture/set_width/set_force/finger_move/list_gestures/get_width/get_joints/get_buttons")


DEVICE_GET_STATE_SCHEMA = {
    "name": "arm_device_get_state",
    "description": "获取末端外设设备的状态信息。",
    "parameters": {
        "type": "object",
        "properties": {
            "device_id": {
                "type": "string",
                "description": "设备 ID (hand_0 / gripper_0 / teach_0)",
            },
        },
        "required": ["device_id"],
    },
}


def arm_device_get_state(device_id: str) -> str:
    return _safe_call(_get_arm().device(device_id).get_state)


# ---------------------------------------------------------------------------
# 遥操
# ---------------------------------------------------------------------------

ENTER_TELEOP_SCHEMA = {
    "name": "arm_enter_teleop",
    "description": (
        "进入遥操模式。master: 本臂采样并发布关节流；slave: 跟随主臂。"
        "进入后 server 拒绝手动控制 RPC，只放行只读/急停/exit_teleop。"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "mode": {
                "type": "string",
                "enum": ["master", "slave"],
                "description": "master(主臂) 或 slave(从臂)",
            },
            "peer": {
                "type": "string",
                "description": "slave 模式下必填：主臂网络端点 (e.g. tcp/10.0.0.2:7447)",
            },
        },
        "required": ["mode"],
    },
}


def arm_enter_teleop(mode: str, peer: Optional[str] = None) -> str:
    params = {}
    if peer:
        params["peer"] = peer
    return _safe_call(_get_arm().enter_teleop, mode, **params)


EXIT_TELEOP_SCHEMA = {
    "name": "arm_exit_teleop",
    "description": "退出遥操模式：停跟随 + 解锁 + 机械臂就地持位。幂等操作。",
    "parameters": {"type": "object", "properties": {}},
}


def arm_exit_teleop() -> str:
    return _safe_call(_get_arm().exit_teleop)


GET_TELEOP_STATUS_SCHEMA = {
    "name": "arm_get_teleop_status",
    "description": "查询当前遥操状态（active / mode / stats）。",
    "parameters": {"type": "object", "properties": {}},
}


def arm_get_teleop_status() -> str:
    return _safe_call(_get_arm().get_teleop_status)


# ---------------------------------------------------------------------------
# 计算（纯计算，不控制硬件）
# ---------------------------------------------------------------------------

FK_SCHEMA = {
    "name": "arm_fk",
    "description": "正运动学：关节角 → 末端位姿。纯计算，不控制硬件。",
    "parameters": {
        "type": "object",
        "properties": {
            "q": {
                "type": "array",
                "items": {"type": "number"},
                "minItems": 7,
                "maxItems": 7,
                "description": "关节角 [j1..j7]（弧度）",
            },
        },
        "required": ["q"],
    },
}


def arm_fk(q: list) -> str:
    return _safe_call(_get_arm().fk, q)


IK_SCHEMA = {
    "name": "arm_ik",
    "description": "逆运动学：末端位姿 → 关节角。纯计算，不控制硬件。",
    "parameters": {
        "type": "object",
        "properties": {
            "pos_d": {
                "type": "array",
                "items": {"type": "number"},
                "minItems": 3,
                "maxItems": 3,
                "description": "目标位置 [px, py, pz]",
            },
            "R_d": {
                "type": "array",
                "description": "目标旋转矩阵 3x3 行主序",
            },
            "q_seed": {
                "type": "array",
                "items": {"type": "number"},
                "description": "初始猜测关节角（可选）",
            },
        },
        "required": ["pos_d", "R_d"],
    },
}


def arm_ik(pos_d: list, R_d: list, q_seed: Optional[list] = None) -> str:
    return _safe_call(_get_arm().ik, pos_d, R_d, q_seed=q_seed)


# ---------------------------------------------------------------------------
# 参数设置
# ---------------------------------------------------------------------------

SET_GAINS_SCHEMA = {
    "name": "arm_set_gains",
    "description": "设置 PD 控制器增益。",
    "parameters": {
        "type": "object",
        "properties": {
            "kp": {
                "type": "array",
                "items": {"type": "number"},
                "description": "比例增益（7 元素）",
            },
            "kd": {
                "type": "array",
                "items": {"type": "number"},
                "description": "微分增益（7 元素）",
            },
        },
    },
}


def arm_set_gains(kp: Optional[list] = None, kd: Optional[list] = None) -> str:
    return _safe_call(_get_arm().set_gains, kp=kp, kd=kd)


SET_PAYLOAD_SCHEMA = {
    "name": "arm_set_payload",
    "description": "设置末端负载（质量 + 质心）。",
    "parameters": {
        "type": "object",
        "properties": {
            "mass": {"type": "number", "description": "负载质量（kg）"},
            "com": {
                "type": "array",
                "items": {"type": "number"},
                "minItems": 3,
                "maxItems": 3,
                "description": "质心位置 [cx, cy, cz]（默认 [0,0,0]）",
            },
        },
        "required": ["mass"],
    },
}


def arm_set_payload(mass: float, com: list = None) -> str:
    if com is None:
        com = [0.0, 0.0, 0.0]
    return _safe_call(_get_arm().set_payload, mass, com=tuple(com))


GET_JOINT_LIMITS_SCHEMA = {
    "name": "arm_get_joint_limits",
    "description": "获取当前关节限位配置。",
    "parameters": {"type": "object", "properties": {}},
}


def arm_get_joint_limits() -> str:
    return _safe_call(_get_arm().get_joint_limits)


SET_JOINT_LIMITS_SCHEMA = {
    "name": "arm_set_joint_limits",
    "description": "设置关节限位。",
    "parameters": {
        "type": "object",
        "properties": {
            "limits": {
                "type": "object",
                "description": "限位配置字典",
            },
        },
        "required": ["limits"],
    },
}


def arm_set_joint_limits(limits: dict) -> str:
    return _safe_call(_get_arm().set_joint_limits, limits)


SET_END_EFFECTOR_SCHEMA = {
    "name": "arm_set_end_effector",
    "description": "设置末端执行器配置。",
    "parameters": {
        "type": "object",
        "properties": {
            "config": {
                "type": "object",
                "description": "末端执行器配置字典",
            },
        },
        "required": ["config"],
    },
}


def arm_set_end_effector(config: dict) -> str:
    return _safe_call(_get_arm().set_end_effector, config)


# ---------------------------------------------------------------------------
# 工具注册表
# ---------------------------------------------------------------------------

TOOLS = {
    "arm_connect": (CONNECT_SCHEMA, arm_connect),
    "arm_disconnect": (DISCONNECT_SCHEMA, arm_disconnect),
    "arm_get_state": (GET_STATE_SCHEMA, arm_get_state),
    "arm_get_tcp_pose": (GET_TCP_POSE_SCHEMA, arm_get_tcp_pose),
    "arm_get_system_stats": (GET_SYSTEM_STATS_SCHEMA, arm_get_system_stats),
    "arm_movej": (MOVEJ_SCHEMA, arm_movej),
    "arm_movel": (MOVEL_SCHEMA, arm_movel),
    "arm_movec": (MOVEC_SCHEMA, arm_movec),
    "arm_movep": (MOVEP_SCHEMA, arm_movep),
    "arm_home": (HOME_SCHEMA, arm_home),
    "arm_hold": (HOLD_SCHEMA, arm_hold),
    "arm_zero_gravity": (ZERO_GRAVITY_SCHEMA, arm_zero_gravity),
    "arm_replay_joint_path": (REPLAY_JOINT_PATH_SCHEMA, arm_replay_joint_path),
    "arm_replay_trajectory": (REPLAY_TRAJECTORY_SCHEMA, arm_replay_trajectory),
    "arm_record_trajectory": (RECORD_TRAJECTORY_SCHEMA, arm_record_trajectory),
    "arm_list_trajectories": (LIST_TRAJECTORIES_SCHEMA, arm_list_trajectories),
    "arm_play_trajectory": (PLAY_TRAJECTORY_SCHEMA, arm_play_trajectory),
    "arm_emergency_stop": (EMERGENCY_STOP_SCHEMA, arm_emergency_stop),
    "arm_clear_stop": (CLEAR_STOP_SCHEMA, arm_clear_stop),
    "arm_enable": (ENABLE_SCHEMA, arm_enable),
    "arm_disable": (DISABLE_SCHEMA, arm_disable),
    "arm_clear_faults": (CLEAR_FAULTS_SCHEMA, arm_clear_faults),
    "arm_device_action": (DEVICE_ACTION_SCHEMA, arm_device_action),
    "arm_device_get_state": (DEVICE_GET_STATE_SCHEMA, arm_device_get_state),
    "arm_enter_teleop": (ENTER_TELEOP_SCHEMA, arm_enter_teleop),
    "arm_exit_teleop": (EXIT_TELEOP_SCHEMA, arm_exit_teleop),
    "arm_get_teleop_status": (GET_TELEOP_STATUS_SCHEMA, arm_get_teleop_status),
    "arm_fk": (FK_SCHEMA, arm_fk),
    "arm_ik": (IK_SCHEMA, arm_ik),
    "arm_set_gains": (SET_GAINS_SCHEMA, arm_set_gains),
    "arm_set_payload": (SET_PAYLOAD_SCHEMA, arm_set_payload),
    "arm_get_joint_limits": (GET_JOINT_LIMITS_SCHEMA, arm_get_joint_limits),
    "arm_set_joint_limits": (SET_JOINT_LIMITS_SCHEMA, arm_set_joint_limits),
    "arm_set_end_effector": (SET_END_EFFECTOR_SCHEMA, arm_set_end_effector),
}


# ---------------------------------------------------------------------------
# Hermes 插件入口
# ---------------------------------------------------------------------------


def register(ctx):
    """Hermes Plugin 入口：注册所有工具。"""
    plugin_id = "litearm-hermes"

    for name, (schema, handler) in TOOLS.items():
        ctx.register_tool(
            name=name,
            schema=schema,
            handler=lambda args, h=handler, **kw: _invoke(h, args),
            plugin_id=plugin_id,
        )

    logger.info("litearm-hermes: registered %d tools", len(TOOLS))


def _invoke(handler, args: dict) -> str:
    """调用 handler，自动匹配参数。"""
    import inspect

    sig = inspect.signature(handler)
    valid_params = set(sig.parameters.keys())
    filtered = {k: v for k, v in args.items() if k in valid_params}
    return handler(**filtered)