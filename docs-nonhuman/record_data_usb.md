# Real Robot Data Recording Checklist With PICO USB

Ultima modificacion: 2026-05-24 15:36:59 -05 -0500

Short checklist for recording VLA demos on the real G1 while the PICO is
connected to the laptop by USB/ADB. The robot camera server is expected at
`192.168.123.164:5555`; inside the PICO app, use `127.0.0.1` because the
launcher creates the USB tunnels.

## 1. Connect

On the laptop, connect Ethernet to the robot network and verify the robot:

```bash
ip -4 addr show enp3s0
ping -c 1 192.168.123.164
```

SSH into the robot:

```bash
ssh unitree@192.168.123.164
```

Connect the PICO by USB-C and verify ADB:

```bash
adb devices
```

Expected: one PICO device listed as `device`.

## 2. Start Camera Server on Robot

On the robot:

```bash
cd ~/NONHUMAN/GR00T-WholeBodyControl
source .venv_camera/bin/activate
```

Find the USB camera indices:

```bash
while true; do clear; echo "=== $(date) ==="; v4l2-ctl --list-devices; sleep 2; done
```

Start the camera server. Adjust device IDs if the indices changed:

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

## 4. Configure XRoboToolkit on PICO

For tracking / PC Service:

```text
PC Service: 127.0.0.1
```

For Remote Vision, use the large PICO4U view:

```text
Remote Vision: PICO4U
Camera/source IP: 127.0.0.1
command port: 13579
stream port: 12345
```

Use `PICO4U` for the large viewer. `ZEDMINI` is the rectangular stereo viewer
and is not the default for this USB flow.

## 5. Record Data With PICO USB

On the laptop:

```bash
cd ~/NONHUMAN/GR00T-WholeBodyControl
tmux kill-session -t sonic_data_collection 2>/dev/null || true

python gear_sonic/scripts/launch_data_collection.py \
  --pico-transport usb \
  --pico-vision \
  --pico-vision-camera-key ego_view \
  --camera-host 192.168.123.164 \
  --camera-port 5555 \
  --wrist-cameras both \
  --task-prompt "real shelf manipulation" \
  --dataset-name "real_usb_head_wrist_episode"
```

This records `ego_view`, `left_wrist`, and `right_wrist` in the dataset while
the PICO shows only `ego_view`.

If you only want the head camera in the dataset:

```bash
python gear_sonic/scripts/launch_data_collection.py \
  --pico-transport usb \
  --pico-vision \
  --pico-vision-camera-key ego_view \
  --camera-host 192.168.123.164 \
  --camera-port 5555 \
  --wrist-cameras none \
  --task-prompt "real shelf manipulation" \
  --dataset-name "real_usb_head_episode"
```

If only one wrist camera is published by the robot, use `--wrist-cameras left`
or `--wrist-cameras right`.

In tmux, confirm the deploy pane only when the robot is safe.

## 6. Check USB Tunnels

The launcher configures these automatically:

```text
adb reverse tcp:63901 tcp:63901
adb reverse tcp:13579 tcp:13579
adb forward tcp:12345 tcp:12345
```

Verify them from another terminal:

```bash
adb reverse --list
adb forward --list
```

Expected:

```text
tcp:63901 tcp:63901
tcp:13579 tcp:13579
tcp:12345 tcp:12345
```

## 7. Troubleshooting

If the PICO has tracking but no video, first verify the laptop can see the robot
camera:

```bash
python gear_sonic/scripts/run_camera_viewer.py \
  --camera-host 192.168.123.164 \
  --camera-port 5555
```

If the viewer fails, the issue is on the robot camera server, Ethernet, camera
indices, or port `5555`.

If the viewer works but the PICO does not show video, verify:

```text
Remote Vision: PICO4U
Camera/source IP: 127.0.0.1
command port: 13579
stream port: 12345
```

If the stream is still stale, restart only the PICO video pane or relaunch the
tmux session:

```bash
tmux kill-session -t sonic_data_collection
```

## 8. Finish

Stop/save the current episode:

```text
Left Grip + A
```

Discard the current episode:

```text
Left Grip + B
```

Kill tmux session if needed:

```bash
tmux kill-session -t sonic_data_collection
```

Datasets are saved under:

```text
outputs/<dataset-name>/
```
