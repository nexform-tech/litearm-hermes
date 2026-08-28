# litearm-hermes

Hermes Agent Plugin + Skill for controlling [LiteArm](https://github.com/nexform-tech) robot arms via the [litearm-python](https://github.com/nexform-tech/litearm-python) SDK.

## Table of Contents

- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Tools Reference](#tools-reference)
- [Usage Scenarios](#usage-scenarios)
- [Safety Notes](#safety-notes)
- [Troubleshooting](#troubleshooting)
- [Directory Structure](#directory-structure)
- [Development](#development)

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Hermes Agent (CLI / Telegram / Discord / Slack / ...)   │
│                                                           │
│  ┌──────────────────┐   ┌──────────────────────────────┐ │
│  │  Skill            │   │  Plugin (litearm_hermes)     │ │
│  │  (SKILL.md)       │   │                              │ │
│  │                   │   │  34 tools registered:        │ │
│  │  Domain knowledge  │──▶│  arm_connect / arm_movej    │ │
│  │  Safety rules     │   │  arm_home / arm_get_state   │ │
│  │  Workflows        │   │  arm_device_* / arm_teleop_* │ │
│  │  Troubleshooting  │   │  arm_emergency_stop / ...    │ │
│  └──────────────────┘   └──────────┬───────────────────┘ │
│                                     │ Zenoh RPC            │
└─────────────────────────────────────┼─────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────┐
│  litearm-server (on robot controller, e.g. 192.168.31.237:7447) │
│  ┌─────────────────────────────────────────────────────┐│
│  │  CAN bus → Motor drivers → 7-DOF Arm + End-effector ││
│  └─────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────┘
```

**How it works:**

1. **Plugin** (Python) — Provides 34 structured tools that call litearm-python SDK methods. Each tool has a JSON Schema definition, parameter validation, and error handling. The Plugin manages the Arm connection as a singleton, so you don't need to reconnect for every tool call.

2. **Skill** (SKILL.md) — A markdown document loaded on-demand by Hermes. It teaches the agent about the robot arm: joint limits, safety rules, typical workflows, and how to troubleshoot problems. This is the "knowledge" layer.

3. **Hermes Agent** orchestrates everything — it reads the Skill to understand the domain, then calls the Plugin tools to execute commands. You can interact with it from CLI, Telegram, Discord, Slack, or any other supported platform.

## Prerequisites

### Software

| Requirement | Version | Notes |
|-------------|---------|-------|
| Python | ≥ 3.8 | |
| [Hermes Agent](https://hermes-agent.nousresearch.com/) | Latest | Install via `curl -fsSL https://hermes-agent.nousresearch.com/install.sh \| bash` |
| [litearm-python](https://github.com/nexform-tech/litearm-python) | Latest | `pip install litearm-python` |
| litearm-server | Running | Deployed on the robot controller (e.g., 192.168.31.237) |

### Hardware

- A LiteArm 7-DOF robot arm with CAN bus connection
- A controller (e.g., NVIDIA Jetson) running litearm-server
- Network connectivity between the Hermes host and the controller

### Network

The Hermes Agent host must be able to reach the litearm-server. Default port is **7447** (Zenoh). Verify connectivity:

```bash
# From the Hermes host
ping 192.168.31.237
# Or test the Zenoh port
nc -zv 192.168.31.237 7447
```

## Installation

### Step 1: Install litearm-python SDK

```bash
pip install litearm-python
```

If you're developing from source:

```bash
cd /path/to/litearm-python
pip install -e .
```

### Step 2: Install litearm-hermes Plugin

**Option A: Copy to Hermes plugins directory (recommended for quick start)**

```bash
# Copy the plugin
cp -r /path/to/litearm-hermes ~/.hermes/plugins/litearm-hermes

# Copy the skill
mkdir -p ~/.hermes/skills
cp -r /path/to/litearm-hermes/skills/litearm ~/.hermes/skills/
```

**Option B: Install as pip package**

```bash
cd /path/to/litearm-hermes
pip install -e .
```

The pip package registers itself via the `hermes_agent.plugins` entry point, so Hermes will discover it automatically.

### Step 3: Configure Environment

```bash
# Set the LiteArm server endpoint (add to ~/.bashrc or ~/.zshrc for persistence)
export LITEARM_ENDPOINT=tcp/192.168.31.237:7447
```

The `LITEARM_ENDPOINT` environment variable is the default server address. You can also pass it explicitly to `arm_connect`:

```
arm_connect(endpoint="tcp/192.168.31.237:7447")
```

### Step 4: Verify Installation

```bash
# Check the plugin is loaded
hermes plugins list | grep litearm

# Check the skill is available
hermes skills list | grep litearm

# Run a quick test (read-only, no motion)
hermes chat -q "connect to the robot arm and tell me its current state"
```

If everything is set up correctly, Hermes will:
1. Load the litearm skill
2. Call `arm_connect` to connect
3. Call `arm_get_state` to read the state
4. Report the current joint angles, state, etc.

## Quick Start

### 1. Basic connection and state reading

```
You: Connect to the robot arm and show me the current state.
```

Hermes will call `arm_connect` → `arm_get_state` and report joint angles, speed, torque, faults, etc.

### 2. Home the arm

```
You: Send the arm to home position at speed 0.3.
```

Hermes will call `arm_home(speed=0.3)` — all joints return to zero. This bypasses joint limit and self-collision checks.

### 3. Joint-space movement

```
You: Move joint 1 to 0.5 radians, joint 2 to 0.3 radians, others at 0, at speed 0.2.
```

Hermes calls `arm_movej(q_target=[0.5, 0.3, 0, 0, 0, 0, 0], speed=0.2)`.

### 4. Operate the gripper

```
You: Open the gripper, then close it to 50% width.
```

Hermes calls:
1. `arm_device_action(device_id="gripper_0", action="open")`
2. `arm_device_action(device_id="gripper_0", action="set_width", value=0.5)`

### 5. Emergency stop

```
You: Stop the arm immediately!
```

Hermes calls `arm_emergency_stop()` — high-priority stop, independent channel.

### 6. Record and replay a trajectory

```
You: Record a 10-second trajectory named "demo", then replay it at half speed.
```

Hermes calls:
1. `arm_enable()`
2. `arm_record_trajectory(duration_s=10, name="demo")`
3. `arm_play_trajectory(trajectory="demo", speed=0.5)`

### 7. Teleoperation setup

```
You: Set up this arm as the master for teleoperation.
```

Hermes calls `arm_enter_teleop(mode="master")`.

### 8. Forward/Inverse Kinematics

```
You: What's the end-effector pose if all joints are at 0.1 radians?
```

Hermes calls `arm_fk(q=[0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1])`.

### 9. Scheduled automation (via Hermes Cron)

```
You: Home the arm every morning at 9am.
```

Hermes sets up a cron job: `arm_connect → arm_home(speed=0.3) → arm_disconnect` at 9:00 daily.

## Tools Reference

All 34 tools are grouped by category. Each tool returns a JSON string with `{"success": true/false, ...}`.

### Connection Management

| Tool | Parameters | Description |
|------|-----------|-------------|
| `arm_connect` | `endpoint` (string, optional) | Connect to the arm. Uses `LITEARM_ENDPOINT` env var by default. |
| `arm_disconnect` | none | Disconnect from the arm. |

### State Reading

| Tool | Parameters | Returns |
|------|-----------|---------|
| `arm_get_state` | none | `q` (joint angles), `dq` (velocities), `tau` (torques), `fault`, `state`, `ts`, `temperature` |
| `arm_get_tcp_pose` | none | `position` [px,py,pz], `rotation` 3x3 row-major matrix |
| `arm_get_system_stats` | none | CPU usage, memory, board temperature, uptime |

### Motion Control

| Tool | Parameters | Notes |
|------|-----------|-------|
| `arm_movej` | `q_target` (float[7]), `speed` (float, default 0.3) | Joint-space motion. Angles in **radians**. |
| `arm_movel` | `pose_goal` (array), `speed` (float, default 0.3) | Cartesian straight-line motion. |
| `arm_movec` | `pose_via`, `pose_goal`, `speed` (float, default 0.3) | Circular arc motion through via-point. |
| `arm_movep` | `poses_goal` (array[]), `speed` (float, default 0.3) | Multi-waypoint Cartesian motion. |
| `arm_home` | `speed` (float, default 0.3) | Home all joints to zero. Bypasses limits. |
| `arm_hold` | `kp_scale` (float, default 3.0) | Hold position with increased stiffness. |
| `arm_zero_gravity` | `duration_s` (float, optional) | Zero-gravity (free-drag) mode. |

### Trajectory Playback

| Tool | Parameters | Notes |
|------|-----------|-------|
| `arm_replay_joint_path` | `q_path` (float[][7]), `speed` (float, default 0.3) | Replay a sequence of joint configurations. |
| `arm_replay_trajectory` | `traj_q` (float[][7]), `speed` (float, default 0.3) | Replay a recorded trajectory. |
| `arm_record_trajectory` | `duration_s` (float), `name` (string, optional) | Record by dragging the arm. Enters zero-gravity automatically. |
| `arm_list_trajectories` | none | List all saved trajectories. |
| `arm_play_trajectory` | `trajectory` (string), `speed` (float, default 0.5) | Load and replay a saved trajectory by ID or path. |

### Safety

| Tool | Parameters | Notes |
|------|-----------|-------|
| `arm_emergency_stop` | none | ⚠️ High-priority stop, independent channel. Works anytime. |
| `arm_clear_stop` | none | Clear stop condition, return to ready. |
| `arm_enable` | none | Enable all motors and hold current pose. |
| `arm_disable` | none | ⚠️ Disable all motors — arm will fall under gravity! |
| `arm_clear_faults` | none | Clear motor faults. |

### End-Effector Devices

| Tool | Parameters | Notes |
|------|-----------|-------|
| `arm_device_action` | `device_id` (string), `action` (string), `value` (any, optional) | Universal device operation. See table below. |
| `arm_device_get_state` | `device_id` (string) | Get device state/info. |

**Supported actions by device type:**

| Device | device_id | Actions |
|--------|-----------|---------|
| **Dexterous Hand** | `hand_0` | `open`, `close`, `set_gesture` (value: "pinch"/"fist"/"point"/...), `list_gestures`, `finger_move` (value: float[]), `set_force` (value: 0.0~1.0), `set_speed` (value: float[]), `set_torque` (value: float[]) |
| **Gripper** | `gripper_0` | `open`, `close`, `set_width` (value: 0.0~1.0), `get_width`, `set_force` (value: 0.0~1.0) |
| **Teach Pendant** | `teach_0` | `get_joints`, `get_buttons` |

### Teleoperation

| Tool | Parameters | Notes |
|------|-----------|-------|
| `arm_enter_teleop` | `mode` ("master"\|"slave"), `peer` (string, required for slave) | Enter teleop mode. Master publishes joint stream; slave follows. |
| `arm_exit_teleop` | none | Exit teleop. Idempotent. |
| `arm_get_teleop_status` | none | Get current teleop status (active/mode/stats). |

### Computation (No Hardware)

| Tool | Parameters | Notes |
|------|-----------|-------|
| `arm_fk` | `q` (float[7]) | Forward kinematics: joint angles → end-effector pose. |
| `arm_ik` | `pos_d` (float[3]), `R_d` (float[3][3]), `q_seed` (float[7], optional) | Inverse kinematics: pose → joint angles. |

### Parameter Settings

| Tool | Parameters | Notes |
|------|-----------|-------|
| `arm_set_gains` | `kp` (float[7], optional), `kd` (float[7], optional) | Set PD controller gains. |
| `arm_set_payload` | `mass` (float), `com` (float[3], optional, default [0,0,0]) | Set end-effector payload (mass + center of mass). |
| `arm_get_joint_limits` | none | Get current joint limit configuration. |
| `arm_set_joint_limits` | `limits` (object) | Set joint limits. |
| `arm_set_end_effector` | `config` (object) | Set end-effector configuration. |

### Pose Format

All poses use the format `[position, rotation]` where:

```python
position = [px, py, pz]           # 3 elements, unit: meters
rotation = [[r00, r01, r02],      # 3×3 row-major rotation matrix
            [r10, r11, r12],
            [r20, r21, r22]]
```

Joint angles are in **radians**, not degrees.

## Usage Scenarios

### Scenario 1: Daily Home Routine

> *"Every morning at 9am, home the arm and report status."*

This can be set up as a Hermes cron job with the litearm skill attached. The agent will:
1. Connect to the arm
2. Read current state
3. Home the arm
4. Report completion via your messaging platform

### Scenario 2: Trajectory Recording

> *"I want to record a pouring motion. Let me drag the arm."*

1. `arm_enable` — Enable motors
2. `arm_record_trajectory(duration_s=15, name="pour")` — Arm enters zero-gravity, you drag for 15 seconds
3. `arm_list_trajectories` — Verify it's saved
4. `arm_play_trajectory(trajectory="pour", speed=0.3)` — Test replay at low speed
5. `arm_play_trajectory(trajectory="pour", speed=1.0)` — Full-speed replay

### Scenario 3: Multi-Device Pick-and-Place

> *"Pick up the object with the gripper, move to the bin, and release."*

1. `arm_get_state` — Check arm is ready
2. `arm_movej(q_target=[...], speed=0.2)` — Move to pick position
3. `arm_device_action(device_id="gripper_0", action="close")` — Grip
4. `arm_movej(q_target=[...], speed=0.2)` — Move to place position
5. `arm_device_action(device_id="gripper_0", action="open")` — Release

### Scenario 4: Teleoperation

> *"Set up this arm as slave to follow the master at 10.0.0.2."*

1. `arm_connect(endpoint="tcp/SLAVE_IP:7447")`
2. `arm_enter_teleop(mode="slave", peer="tcp/10.0.0.2:7447")`
3. `arm_get_teleop_status` — Monitor
4. `arm_exit_teleop` — Stop when done

### Scenario 5: Debugging with FK/IK

> *"I want to reach position [0.5, 0, 0.3] with the end-effector pointing forward. What joint angles?"*

1. `arm_ik(pos_d=[0.5, 0, 0.3], R_d=[[1,0,0],[0,1,0],[0,0,1]])` — Compute joint angles
2. `arm_fk(q=[...])` — Verify the result
3. `arm_movej(q_target=[...], speed=0.2)` — Execute

## Safety Notes

> ⚠️ **CRITICAL: This plugin operates in "free mode" — no confirmation prompts. The arm will move immediately when commanded. Always have a person near the emergency stop when using this plugin.**

### Safety Rules

1. **Default speed is 0.3** — All motion tools default to `speed=0.3` (safe low speed). Only increase when you're confident.
2. **Check state first** — Always call `arm_get_state` before any motion command.
3. **Emergency stop is always available** — `arm_emergency_stop` uses an independent channel. Use it immediately if anything goes wrong.
4. **Never disable motors unless you mean it** — `arm_disable` cuts power to all motors. The arm will fall under gravity.
5. **Teleop locks manual control** — When in teleop mode, all manual RPC commands are rejected. Exit with `arm_exit_teleop`.
6. **Keep clear of the workspace** — Ensure no people or obstacles are in the arm's workspace before moving.

### Joint Limits

| Joint | Range (degrees) | Range (radians) |
|-------|-----------------|-----------------|
| J1 | [-180, 180] | [-π, π] |
| J2 | [-120, 120] | [-2π/3, 2π/3] |
| J3 | [-180, 180] | [-π, π] |
| J4 | [-120, 120] | [-2π/3, 2π/3] |
| J5 | [-180, 180] | [-π, π] |
| J6 | [-120, 120] | [-2π/3, 2π/3] |
| J7 | [-180, 180] | [-π, π] |

## Troubleshooting

### Connection Failed

```
Error: "No valid reply received"
```

**Causes & Solutions:**
1. **litearm-server not running** — SSH to the controller and start it:
   ```bash
   ssh sunrise@192.168.31.237
   cd ~/luo && ./start_server.sh
   ```
2. **Network unreachable** — Verify connectivity: `ping 192.168.31.237`
3. **Wrong endpoint** — Check the endpoint format is `tcp/IP:PORT`
4. **Firewall blocking port 7447** — Check iptables/firewall rules
5. **LITEARM_ENDPOINT not set** — Verify: `echo $LITEARM_ENDPOINT`

### Motor Faults

1. Call `arm_get_state` and check the `fault` field
2. Try `arm_clear_faults` to clear soft faults
3. If faults persist, restart litearm-server on the controller
4. Check CAN bus connection on the controller

### Emergency Stop State

1. Call `arm_clear_stop` to clear the stop condition
2. Call `arm_enable` to re-enable motors
3. Check `arm_get_state` to confirm the arm is "ready"

### Motion Not Executing

1. Check `arm_get_state` — the state must be "ready"
2. Check `arm_get_teleop_status` — teleop mode rejects manual commands
3. If in teleop, call `arm_exit_teleop` to exit
4. Check for faults with `arm_get_state` → `fault` field

### Gripper/Hand Not Responding

1. Call `arm_device_get_state(device_id="gripper_0")` to check online status
2. Verify the device daemon is running on the controller
3. Check CAN bus connection for the end-effector

### Hermes-Specific Issues

**Plugin not loaded:**
```bash
hermes plugins list | grep litearm
# If not found, check the plugin directory:
ls ~/.hermes/plugins/litearm-hermes/plugin.yaml
```

**Skill not found:**
```bash
hermes skills list | grep litearm
# If not found, check the skill directory:
ls ~/.hermes/skills/litearm/SKILL.md
```

**Environment variable not set:**
```bash
# Check in current shell
echo $LITEARM_ENDPOINT

# For persistent setting, add to ~/.bashrc:
echo 'export LITEARM_ENDPOINT=tcp/192.168.31.237:7447' >> ~/.bashrc
source ~/.bashrc
```

## Directory Structure

```
litearm-hermes/
├── plugin.yaml                      # Hermes Plugin manifest (name, version, tools list, env vars)
├── litearm_hermes/
│   └── __init__.py                  # Plugin entry point. All 34 tools defined here.
│                                     #   - Schema definitions (JSON Schema for each tool)
│                                     #   - Handler functions (Python code that calls litearm SDK)
│                                     #   - Connection singleton (_get_arm / _close_arm)
│                                     #   - Error handling (_safe_call / _ok / _err)
│                                     #   - register(ctx) — Hermes plugin entry point
├── skills/
│   └── litearm/
│       ├── SKILL.md                 # Skill document loaded by Hermes:
│       │                             #   - Domain knowledge (joint ranges, speed limits)
│       │                             #   - Safety rules (6 rules)
│       │                             #   - 8 workflow scenarios
│       │                             #   - Device operation reference
│       │                             #   - Troubleshooting guide
│       └── references/
│           └── api-reference.md     # Full API reference (all 34 tools with parameters)
├── docs/
│   └── superpowers/
│       └── specs/
│           └── 2026-08-28-litearm-hermes-design.md  # Design document
├── README.md                        # This file (English)
├── README.zh-CN.md                  # Chinese version
└── pyproject.toml                   # Python package config + Hermes entry point
```

## Development

### Running Tests

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run unit tests (requires mock server or no server)
python -m pytest tests/ -v
```

### Testing with a Real Arm

```bash
# Ensure the arm server is running on the controller
# Set the endpoint
export LITEARM_ENDPOINT=tcp/192.168.31.237:7447

# Start Hermes and test
hermes chat -q "connect to the arm and read the state"
```

### Plugin Validation

```bash
# Validate the plugin structure
hermes plugins doctor ~/.hermes/plugins/litearm-hermes
```

### Adding a New Tool

1. Add a `SCHEMA` dict and handler function in `litearm_hermes/__init__.py`
2. Add the tool to the `TOOLS` dict
3. Add the tool name to `plugin.yaml` → `provides_tools`
4. Update `skills/litearm/references/api-reference.md`
5. Update `skills/litearm/SKILL.md` if needed

### Code Style

- All handlers return JSON strings (never raw dicts)
- Errors return `{"success": false, "error": "message"}`
- Success returns `{"success": true, ...}`
- Use `_safe_call()` for any call that may throw
- Speed defaults to 0.3 for all motion tools

## License

Proprietary