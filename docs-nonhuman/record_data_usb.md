# Real Robot Data Recording Checklist With PICO USB

Ultima modificacion: 2026-05-24

Short checklist for recording VLA demos on the real G1 while the PICO is
connected to the laptop by USB/ADB. The robot camera server is expected at
`192.168.123.164:5555`; inside the PICO app, use `127.0.0.1` because the
launcher creates the USB tunnels.

USB cameras run at **320×240** by default (`gear_sonic/camera/drivers/usb_camera.py`).
The dataset schema and PICO stream both use that resolution.

On the laptop, install GStreamer bindings once (needed for PICO video):

```bash
bash install_scripts/install_pico_vision_deps.sh
```

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

Start the camera server. Adjust device IDs to match `v4l2-ctl --list-devices`
(example below uses ego=`0`, left wrist=`2`, right wrist=`4`):

```bash
python -m gear_sonic.camera.composed_camera \
  --ego-view-camera usb \
  --ego-view-device-id 0 \
  --left-wrist-camera usb \
  --left-wrist-device-id 2 \
  --right-wrist-camera usb \
  --right-wrist-device-id 4 \
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

### PICO vision layouts

The launcher streams robot cameras to the PICO through
`gear_sonic/scripts/stream_camera_to_pico.py`. Two layouts are available:

| Layout | Flag | What the teleoperator sees |
|---|---|---|
| `single` (default) | `--pico-vision-layout single` | One camera only (`--pico-vision-camera-key`, usually `ego_view`) |
| `teleop_grid` | `--pico-vision-layout teleop_grid` | Ego view in the center column plus both wrist cameras on the sides |

`teleop_grid` requires the robot camera server to publish all three keys:
`ego_view`, `left_wrist`, and `right_wrist`.

Grid layout (3×3, corners black):

```text
[dark] [ego ] [dark]
[left] [ego ] [right]
[dark] [ego ] [dark]
```

Rotation (`--pico-vision-rotate`) applies **only to `ego_view`**. Wrist cameras
are not rotated. This correction affects only the PICO Remote Vision stream; the
dataset keeps the original camera images.

## 5. Record Data With PICO USB

On the laptop (no need to activate a venv manually — the launcher re-execs into
`.venv_data_collection` and configures ADB tunnels + `--pico-ip 127.0.0.1` for
you):

```bash
cd ~/NONHUMAN/GR00T-WholeBodyControl
tmux kill-session -t sonic_data_collection 2>/dev/null || true

python gear_sonic/scripts/launch_data_collection.py \
  --pico-transport usb \
  --pico-vision \
  --pico-vision-layout teleop_grid \
  --pico-vision-rotate ccw90 \
  --camera-host 192.168.123.164 \
  --camera-port 5555 \
  --wrist-cameras both \
  --task-prompt "push the panda and the toilet paper" \
  --dataset-name "push_objects_session1_v2"
```

This is the recommended command for wrist teleop: it records `ego_view`,
`left_wrist`, and `right_wrist` in the dataset and shows the teleop grid on the
PICO (ego in the center column, wrists on the sides).

`--dataset-name` is optional; omit it to auto-generate a timestamped folder under
`outputs/`. If you change camera resolution or restart a broken session, delete
any partial dataset folder first (for example `outputs/push_objects_session1_v2/`).

The launcher opens tmux session `sonic_data_collection` with:

```text
Window pico_vision     -> stream_camera_to_pico (teleop_grid to PICO)
Window data_collection -> deploy | teleop | data exporter | camera viewer
```

In the `pico_vision` window, wait for:

```text
[PicoVideoStreamer] connected to 127.0.0.1:12345
```

Then open Remote Vision on the PICO (section 4). Negative `Image latency` lines
in that window are harmless clock skew between robot and laptop.

If the head camera is physically mounted sideways, adjust only ego rotation:
`--pico-vision-rotate cw90` or `--pico-vision-rotate ccw90`.

To show only ego view on the PICO (legacy behavior):

```bash
python gear_sonic/scripts/launch_data_collection.py \
  --pico-transport usb \
  --pico-vision \
  --pico-vision-layout single \
  --pico-vision-camera-key ego_view \
  --pico-vision-rotate ccw90 \
  --camera-host 192.168.123.164 \
  --camera-port 5555 \
  --wrist-cameras both \
  --task-prompt "push the panda and the toilet paper" \
  --dataset-name "push_objects_session1"
```

If you only want the head camera in the dataset:

```bash
python gear_sonic/scripts/launch_data_collection.py \
  --pico-transport usb \
  --pico-vision \
  --pico-vision-layout single \
  --pico-vision-camera-key ego_view \
  --pico-vision-rotate cw90 \
  --camera-host 192.168.123.164 \
  --camera-port 5555 \
  --wrist-cameras none \
  --task-prompt "real shelf manipulation" \
  --dataset-name "real_usb_head_episode"
```

If only one wrist camera is published by the robot, use `--wrist-cameras left`
or `--wrist-cameras right`. In that case use `--pico-vision-layout single`
because `teleop_grid` requires both wrists.

You can also run the stream standalone for debugging. With PICO over USB, set up
ADB tunnels first, then use `127.0.0.1` as the PICO IP:

```bash
adb reverse tcp:13579 tcp:13579
adb forward tcp:12345 tcp:12345

python -m gear_sonic.scripts.stream_camera_to_pico \
  --camera-host 192.168.123.164 \
  --camera-port 5555 \
  --layout teleop_grid \
  --rotate ccw90 \
  --pico-ip 127.0.0.1 \
  --show-preview
```

Wait for `[PicoVideoStreamer] connected to 127.0.0.1:12345` before opening
Remote Vision on the headset.

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

If `stream_camera_to_pico` fails with `No module named 'gi'`, install the system
GStreamer bindings on the laptop:

```bash
bash install_scripts/install_pico_vision_deps.sh
```

Then rerun the stream command. The script auto-loads system `python3-gi` from
`/usr/lib/python3/dist-packages` when running inside a venv.

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

When running `stream_camera_to_pico` manually over USB, pass
`--pico-ip 127.0.0.1` and configure `adb forward` / `adb reverse` (section 6).
The default `--pico-ip 192.168.0.128` is for WiFi only.

Negative `Image latency` values (for example `-69000 ms`) are harmless: they mean
the robot clock is ahead of the laptop clock. They do not affect streaming.

If the PICO video is rotated because the physical ego camera is mounted
sideways, use `--pico-vision-rotate cw90`. If that is the wrong direction, try
`--pico-vision-rotate ccw90`. Wrist cameras are never rotated in
`teleop_grid` mode.

If `teleop_grid` fails at startup with missing camera keys, verify the robot
camera server publishes `ego_view`, `left_wrist`, and `right_wrist` (see
section 2) and that `run_camera_viewer.py` shows all three streams.

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
