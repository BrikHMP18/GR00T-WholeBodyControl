# PICO Remote Vision Quickstart

This guide starts SONIC data collection while also streaming the robot ego camera
to PICO Remote Vision.

The video path is separate from PICO pose tracking:

```text
PICO tracking:
  PICO -> local PC

PICO Remote Vision:
  local PC -> PICO

Camera frames:
  Unitree / robot PC -> local PC -> PICO
```

## 1. Select The Branch

On the local PC:

```bash
cd /home/mbrq/NONHUMAN/HUMANOID_FULLSTACK/GR00T-WholeBodyControl
git switch PICO_VISION_UNITREE
```

## 2. Install PICO Vision System Dependencies

Run this once on the local PC that will execute `launch_data_collection.py`:

```bash
bash install_scripts/install_pico_vision_deps.sh
```

This does not create a virtual environment. It installs Ubuntu system packages
for GStreamer and H.264 encoding, especially `x264enc`.

You can verify the encoder with:

```bash
gst-inspect-1.0 x264enc
```

## 3. Start The Camera Server On Unitree

On the Unitree / robot PC, start the normal GR00T camera server.

For an OAK ego camera:

```bash
cd /path/to/GR00T-WholeBodyControl
source .venv_camera/bin/activate

python -m gear_sonic.camera.composed_camera \
  --ego-view-camera oak \
  --port 5555
```

For USB camera testing:

```bash
python -m gear_sonic.camera.composed_camera \
  --ego-view-camera usb \
  --ego-view-device-id 0 \
  --port 5555
```

The `--camera-host` used later must be the IP of this machine.

Typical real Unitree value:

```text
192.168.123.164
```

## 4. Configure The PICO

In the XRoboToolkit app on the PICO:

1. In Tracking Session, select `Head`, `Controller`, and `Hand`.
2. Enter the local PC IP, then enable `Send`.
3. In Remote Vision Session, select `ZEDMINI`.
4. Press `Listen`.

The PICO IP is the headset's WiFi IP. Typical example:

```text
192.168.0.128
```

## 5. Launch Data Collection With PICO Vision

On the local PC:

```bash
cd /home/mbrq/NONHUMAN/HUMANOID_FULLSTACK/GR00T-WholeBodyControl

python gear_sonic/scripts/launch_data_collection.py \
  --pico-vision \
  --pico-ip 192.168.0.128 \
  --camera-host 192.168.123.164 \
  --camera-port 5555
```

Replace:

- `--pico-ip` with the PICO headset IP.
- `--camera-host` with the Unitree / robot PC IP running `composed_camera`.
- `--camera-port` with the camera server port, usually `5555`.

The launcher will create an extra tmux window:

```text
pico_vision
```

That window runs:

```bash
python -m gear_sonic.scripts.stream_camera_to_pico \
  --camera-host <camera-host> \
  --camera-port <camera-port> \
  --camera-key ego_view \
  --pico-ip <pico-ip>
```

## 6. Optional Local Preview

To show a local OpenCV preview of the stream:

```bash
python gear_sonic/scripts/launch_data_collection.py \
  --pico-vision \
  --pico-vision-preview \
  --pico-ip 192.168.0.128 \
  --camera-host 192.168.123.164
```

## 7. Which IP Goes Where

Use this mapping:

```text
camera-host = machine running gear_sonic.camera.composed_camera
pico-ip     = PICO headset WiFi IP
```

Common setup:

```text
Unitree camera server: 192.168.123.164:5555
PICO headset:          192.168.0.128:12345
Local PC:              runs launch_data_collection.py
```

If the camera server runs on the same local PC:

```bash
--camera-host localhost
```

## 8. Troubleshooting

If the PICO does not show video:

1. Check that Remote Vision is set to `ZEDMINI` and `Listen`.
2. Check the PICO IP.
3. Check that the local PC can reach the PICO:

```bash
ping 192.168.0.128
```

4. Check that the local PC can reach the camera server:

```bash
python gear_sonic/scripts/run_camera_viewer.py \
  --camera-host 192.168.123.164 \
  --camera-port 5555
```

5. Check that `x264enc` exists:

```bash
gst-inspect-1.0 x264enc
```

If `x264enc` is missing, run:

```bash
bash install_scripts/install_pico_vision_deps.sh
```
