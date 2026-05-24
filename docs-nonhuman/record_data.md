# Real Robot Data Recording Checklist

Ultima modificacion: 2026-05-24 15:36:59 -05 -0500

Short checklist for recording VLA demos on the real G1. For **PICO Remote Vision** (live camera in the headset while you record), see [below](#pico-remote-vision); the full walkthrough is [`docs/source/tutorials/pico_vision.md`](../docs/source/tutorials/pico_vision.md).

## 1. Connect

On the laptop, connect Ethernet to the robot network and verify:

```bash
ip -4 addr show enp3s0
ping -c 1 192.168.123.164
```

SSH into the robot:

```bash
ssh unitree@192.168.123.164
```

## 2. Start Camera Server on Robot

On the robot:

```bash
cd ~/NONHUMAN/GR00T-WholeBodyControl
source .venv_camera/bin/activate
```

Find the USB camera index:

```bash
v4l2-ctl --list-devices
```

Start the camera server. Replace `0` with the working index:

```bash
python -m gear_sonic.camera.composed_camera \
  --ego-view-camera usb \
  --ego-view-device-id 0 \
  --right-wrist-camera usb \
  --right-wrist-device-id 4 \
  --left-wrist-camera usb \
  --left-wrist-device-id 2 \
  --port 5555
```

If port `5555` is busy:

```bash
ss -ltnp | grep 5555
kill <PID>
```

## 3. Verify Camera on Laptop

On the laptop:

```bash
cd ~/NONHUMAN/GR00T-WholeBodyControl
source .venv_data_collection/bin/activate

python gear_sonic/scripts/run_camera_viewer.py \
  --camera-host 192.168.123.164 \
  --camera-port 5555
```

Viewer keys:

```text
Q = quit
R = record raw camera video
```

## 4. Record Data

On the laptop:

```bash
cd ~/NONHUMAN/GR00T-WholeBodyControl

python gear_sonic/scripts/launch_data_collection.py \
  --camera-host 192.168.123.164 \
  --task-prompt "Push the panda off the chair, turn 180 degrees to the right, then return to the starting position."
```

In tmux, confirm the deploy pane only when the robot is safe.

### PICO Remote Vision

Optional: stream the robot camera to the PICO app **during** the same tmux session as data collection. Video path: **robot (ZMQ)** → **workstation** → **headset (TCP)**; pose tracking still uses the app’s normal **Send** flow to the PC.

**One-time on the workstation** (GStreamer / `x264enc`):

```bash
bash install_scripts/install_pico_vision_deps.sh
gst-inspect-1.0 x264enc
```

**XRoboToolkit on the headset**: start a **Remote Vision** session (**ZEDMINI** → **Listen**). If the app asks for **camera source IP**, use the **workstation Wi‑Fi IP** (the machine running the encoder), **not** the robot’s `192.168.123.x`. For **tracking Send**, use that same PC Wi‑Fi IP. Default stream port in VR is often **12345** (override with `--pico-vision-port` on the launcher if yours differs).

**IPs (typical setup)**

| Flag / setting | Meaning |
|----------------|--------|
| `--camera-host` | Machine running `composed_camera` (often robot `192.168.123.164`) |
| `--pico-ip` | Headset Wi‑Fi IP as reachable from the workstation (`ping` it first) |

**Launch** (same idea as the public tutorial; adjust IPs and `--task-prompt`):

```bash
cd ~/NONHUMAN/GR00T-WholeBodyControl

python gear_sonic/scripts/launch_data_collection.py \
  --pico-vision \
  --pico-ip 192.168.250.19 \
  --camera-host 192.168.123.164 \
  --camera-port 5555 \
  --task-prompt "Describe your task here." \
  --wrist-cameras right
```

Use `--wrist-cameras right` when you only have a **right** wrist camera (ego + right in the dataset). Use `--wrist-cameras both` or the legacy `--record-wrist-cameras` only when `composed_camera` publishes **both** `left_wrist` and `right_wrist`.

Useful extras: `--pico-vision-preview` (OpenCV preview on the PC), `--pico-vision-camera-key right_wrist` (stream a wrist camera instead of `ego_view`), `--pico-vision-stretch` only if you want stretched 16:9 instead of default letterbox.

More detail (test stream without tmux, USB vs OAK camera, troubleshooting): [`docs/source/tutorials/pico_vision.md`](../docs/source/tutorials/pico_vision.md).

## 5. PICO Controls

```text
A+B+X+Y          start/stop policy
A+X              enter/exit POSE
Left Stick Click enter/exit VR_3PT
Left Stick       move in planner/VR_3PT
Right Stick X    yaw/turn
Trigger          close hand
A+B              next locomotion mode
X+Y              previous locomotion mode
```

Recording controls:

```text
Left Grip + A    start episode / stop and save episode
Left Grip + B    discard current episode
```

Recommended VLA mode: `POSE`. `VR_3PT` can be recorded, but do not clean it with the default SMPL stale-frame filter.

## 6. Finish

Stop/save the current episode:

```text
Left Grip + A
```

Stop policy:

```text
A+B+X+Y
```

Kill tmux session if needed:

```bash
tmux kill-session -t sonic_data_collection
```

Datasets are saved under:

```text
outputs/<timestamp>/
```

## 7. Clean Dataset

For normal `POSE` datasets:

```bash
source .venv_data_collection/bin/activate

python gear_sonic/scripts/process_dataset.py \
  --dataset-path outputs/<dataset> \
  --output-path outputs/<dataset>_cleaned
```

For mostly `VR_3PT` datasets:

```bash
python gear_sonic/scripts/process_dataset.py \
  --dataset-path outputs/<dataset> \
  --output-path outputs/<dataset>_cleaned \
  --no-remove-stale-smpl
```
