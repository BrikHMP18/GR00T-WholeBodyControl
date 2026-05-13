# Real Robot Data Recording Checklist

Short checklist for recording VLA demos on the real G1.

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
  --ego-view-device-id 6 \
  --right-wrist-camera usb \
  --right-wrist-device-id 8 \
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

Optional **subtasks** (multi-phase language labels in one episode): pass
`--subtasks "label one|label two"` to `launch_data_collection.py` or
`run_data_exporter.py`. While recording, send ZMQ keyboard messages on port
`5580`: digits `1`–`9` select a subtask, `[` / `]` for previous/next. PICO
buttons do **not** change subtasks.

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
