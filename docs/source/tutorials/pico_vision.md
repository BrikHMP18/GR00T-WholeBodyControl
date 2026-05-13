# PICO Remote Vision

Stream robot camera feeds to the PICO headset during teleoperation and data collection. Pose tracking uses a separate path:

```text
PICO pose tracking:      PICO -> PC

Remote Vision (video):    robot (ZMQ) -> PC -> PICO
```

Requirements: **`teleop_real`** (or newer) branch with PICO vision support, **`bash install_scripts/install_pico.sh`**, **`bash install_scripts/install_data_collection.sh`**, and **`composed_camera`** running on the robot (or localhost).

---

## 1. System packages on the workstation (once)

Install GStreamer bits and **`x264enc`**:

```bash
bash install_scripts/install_pico_vision_deps.sh
gst-inspect-1.0 x264enc   # encoder must be visible
```

This does **not** create a Python virtual environment.

---

## 2. Camera server on the robot

From the repo on the robot, with `.venv_camera` activated:

**OAK (typical)**

```bash
source .venv_camera/bin/activate

python -m gear_sonic.camera.composed_camera \
  --ego-view-camera oak \
  --port 5555
```

**USB (example)** — map indices with `v4l2-ctl --list-devices` before choosing IDs:

```bash
python -m gear_sonic.camera.composed_camera \
  --ego-view-camera usb \
  --ego-view-device-id 6 \
  --right-wrist-camera usb \
  --right-wrist-device-id 8 \
  --port 5555
```

Anything that talks to the camera stack later uses **`--camera-host`** = this machine IP (often `192.168.123.164`).

---

## 3. Configure the headset (XRoboToolkit)

1. **Tracking session**: Head, Controller, Hand; enter the **workstation WiFi IP** (the PC that runs Python), then **Send**.
2. **Remote Vision session**: **ZEDMINI** → **Listen**.

Typical XRoboToolkit ports (as shown in VR): **command** `13579`, **streaming** `12345`.
This repo’s `stream_camera_to_pico` connects to the headset on the **streaming** port (default **`12345`**; use **`--pico-port`** if yours differs).

If the app asks for **camera source IP**, use the **workstation WiFi IP** (the machine that encodes and pushes H.264 over TCP to the headset) — **not** the robot’s `192.168.123.x` address. The robot only supplies ZMQ to the PC.

Use the headset WiFi IP for **`--pico-ip`** (see §6 example).

---

## 4. Test stream only (no tmux launcher)

From the repo root on the workstation (same machine that reaches both robot camera and headset):

```bash
python -m gear_sonic.scripts.stream_camera_to_pico \
  --camera-host 192.168.123.164 \
  --camera-port 5555 \
  --camera-key ego_view \
  --pico-ip 192.168.250.19
```

- Default TCP port toward the headset is **`12345`**; override if needed with **`--pico-port`**.
- **Aspect ratio:** 4:3 cameras (e.g. 640×480) are **letterboxed** into 1280×720 by default so the headset matches OpenCV proportions (black bars left/right). Old stretch-to-16:9 behaviour: **`--stretch`** on `stream_camera_to_pico`, or **`--pico-vision-stretch`** on `launch_data_collection.py`.
- Send another multiplexed camera (e.g. wrist): **`--camera-key right_wrist`**.
- Debug preview on the PC: add **`--show-preview`**.

---

## 5. Full data collection + Remote Vision

```bash
python gear_sonic/scripts/launch_data_collection.py \
  --pico-vision \
  --pico-ip 192.168.250.19 \
  --camera-host 192.168.123.164 \
  --camera-port 5555 \
  --task-prompt "Describe your task here." \
  --record-wrist-cameras
```

Local OpenCV preview of the stream being encoded:

```bash
python gear_sonic/scripts/launch_data_collection.py \
  --pico-vision \
  --pico-vision-preview \
  --pico-ip 192.168.250.19 \
  --camera-host 192.168.123.164 \
  --camera-port 5555
```

Stream a wrist camera instead of **`ego_view`** by appending:

```bash
  --pico-vision-camera-key right_wrist
```

The launcher adds a **`pico_vision`** tmux pane that wraps `gear_sonic.scripts.stream_camera_to_pico`.

---

## 6. IP cheat sheet

| Setting | Meaning |
|--------|---------|
| **`--camera-host`** | Host running **`python -m gear_sonic.camera.composed_camera`** (robot IP or `localhost`) |
| **`--pico-ip`** | WiFi IP of **the headset** as reached from the workstation (`ping` must be stable) |
| **Tracking Send target in app** | **Workstation WiFi** IP (not the robot) |
| **Remote Vision “camera source IP”** (if asked) | Same as **workstation WiFi** IP (the PC that runs `stream_camera_to_pico`) |

**Example LAN** (replace octets if your network differs):

```text
Robot / camera ZMQ:           192.168.123.164:5555
Workstation WiFi (PC):        192.168.250.82   →  Tracking Send target, camera source IP
PICO headset WiFi:            192.168.250.19   →  --pico-ip; stream TCP :12345
```

Same machine as viewer and camera server:

```bash
--camera-host localhost
```

---

## 7. Troubleshooting

No video in the headset:

1. Confirm **ZEDMINI** + **Listen** on the PICO app.
2. Verify **`ping 192.168.250.19`** (headset) from the workstation.
3. Verify camera path: **`python gear_sonic/scripts/run_camera_viewer.py --camera-host 192.168.123.164 --camera-port 5555`**
4. Confirm **`gst-inspect-1.0 x264enc`**; if missing rerun **`bash install_scripts/install_pico_vision_deps.sh`**.

