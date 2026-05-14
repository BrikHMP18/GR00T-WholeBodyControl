# PICO VR Teleop on Real Robot

This guide is a practical step-by-step checklist for teleoperating the real
Unitree G1 with PICO VR after cloning this repo from scratch.

It is based on the project docs:

- `docs/source/getting_started/installation_deploy.md`
- `docs/source/getting_started/download_models.md`
- `docs/source/getting_started/vr_teleop_setup.md`
- `docs/source/tutorials/vr_wholebody_teleop.md`
- `docs/source/tutorials/data_collection.md`
- `docs/source/user_guide/teleoperation.md`

Official rendered docs:

- https://nvlabs.github.io/GR00T-WholeBodyControl/getting_started/installation_deploy.html
- https://nvlabs.github.io/GR00T-WholeBodyControl/getting_started/download_models.html
- https://nvlabs.github.io/GR00T-WholeBodyControl/getting_started/vr_teleop_setup.html
- https://nvlabs.github.io/GR00T-WholeBodyControl/tutorials/vr_wholebody_teleop.html
- https://nvlabs.github.io/GR00T-WholeBodyControl/tutorials/data_collection.html
- https://nvlabs.github.io/GR00T-WholeBodyControl/user_guide/teleoperation.html

## 0. Machine Roles and Network Topology

Recommended real-robot setup from the docs:

| Component | What runs there | How it connects |
|---|---|---|
| Laptop / host workstation | C++ deployment process, PICO teleop streamer, data exporter, optional camera viewer | Ethernet to robot network, WiFi to PICO |
| Robot onboard computer / G1 | Unitree robot services, low-level robot stack, and camera server for VLA data collection | Internal robot network, actuators, and physically connected cameras |
| PICO headset | XRoboToolkit PICO app | WiFi to laptop / host workstation |
| PICO controllers | Hand/controller tracking and button commands | Paired to PICO headset |
| PICO motion trackers | Feet/body tracking | Paired to PICO headset, strapped to ankles |
| Robot cameras | Ego-view OAK camera and optional wrist OAK cameras | Physically connected to robot onboard computer |

Important connection details:

- PICO to host: WiFi. The PICO and the host must be on the same low-latency
  local network. In the PICO XRoboToolkit app, set `PC Service` to the host
  WiFi IP.
- Host to robot: Unitree robot network, normally via Ethernet. The host should
  have an interface on the robot network, typically `192.168.123.x`.
- Robot onboard computer to robot hardware: handled by the robot's own Unitree
  stack.
- Robot camera server to host: same robot network. The camera server runs on
  the robot computer and publishes camera frames over ZMQ, default port `5555`.
  The docs use `192.168.123.164` as the default G1 camera host IP.
- For data collection, the host data exporter reads three sources:
  - C++ deployment robot state on host port `5557`.
  - PICO SMPL teleop stream on host port `5556`.
  - Robot camera server on robot IP, port `5555`.
- In the standard offboard workflow, you do not run the C++ deployment, PICO
  streamer, or data exporter on the robot computer. The only extra process on
  the robot computer for VLA data collection is the camera server.
- The host can use two network interfaces at the same time: Ethernet for the
  robot and WiFi for the PICO.

The basic real-robot teleop runtime has two main terminals on the host:

1. C++ deployment in `gear_sonic_deploy/`
2. PICO teleop streamer in the repo root

For VLA data collection, add:

1. Camera server on the robot computer.
2. Data exporter on the host.
3. Optional camera viewer on the host.

There is no MuJoCo simulator terminal for real robot teleop.

## 1. Safety Requirements

Do not skip this section.

- Practice in simulation first until mode switching and emergency stop are
  comfortable.
- Keep a clear 3 meter safety zone around the robot.
- Keep a safety operator at the host keyboard.
- Emergency stop from the C++ deployment terminal: press `O`.
- Emergency stop from PICO controllers: press `A+B+X+Y`.
- Use a gantry or equivalent safe support for early real-robot tests.
- Wear tight-fitting pants or leggings. Loose clothing can occlude PICO foot
  trackers and cause bad motion.
- Before entering `POSE` or `VR_3PT`, align your body with the robot's current
  pose. Large pose mismatch can cause sudden aggressive motion.

## 2. Prepare the Host Laptop / Workstation

Run these steps on the laptop / host workstation.

### 2.1 Clone and Pull Large Files

If you have just cloned the repo:

```bash
cd GR00T-WholeBodyControl

sudo apt install git-lfs
git lfs install
git lfs pull
```

If meshes or binary assets are tiny text pointer files, `git lfs pull` did not
complete correctly.

### 2.2 Install TensorRT

Install the exact TensorRT version required by the docs:

| Platform | Required TensorRT |
|---|---|
| x86_64 desktop / laptop | `10.13` |
| Jetson / G1 onboard Orin | `10.7` with JetPack 6 |

Use the TAR package from NVIDIA Developer, not the DEB package. Example:

```bash
sudo apt-get install -y pv
pv TensorRT-*.tar.gz | tar -xz -f -
```

Move the extracted TensorRT directory to `~/TensorRT` or another fixed path,
then set:

```bash
echo 'export TensorRT_ROOT=$HOME/TensorRT' >> ~/.bashrc
source ~/.bashrc
```

Using the wrong TensorRT version can produce silently wrong inference outputs
and dangerous robot behavior.

### 2.3 Install and Build the C++ Deployment

Run on the host:

```bash
cd gear_sonic_deploy
chmod +x scripts/install_deps.sh
./scripts/install_deps.sh
source scripts/setup_env.sh
just build
cd ..
```

The deployment script will later build again before launching, but doing this
once up front catches missing dependencies early.

### 2.4 Download ONNX Models and Planner

Run from the repo root:

```bash
pip install huggingface_hub
python download_from_hf.py
```

Expected files:

```text
gear_sonic_deploy/
+-- policy/release/
|   +-- model_encoder.onnx
|   +-- model_decoder.onnx
|   +-- observation_config.yaml
+-- planner/target_vel/V2/
    +-- planner_sonic.onnx
```

The deployment script expects these default paths.

### 2.5 Install the Data Collection Environment on the Host

This is required only if you want to record VLA demonstrations in LeRobot format
for Isaac-GR00T post-training.

Run from the repo root on the host:

```bash
bash install_scripts/install_data_collection.sh
```

This creates `.venv_data_collection` with LeRobot, PyAV, OpenCV, and the data
exporter dependencies.

## 3. Prepare PICO and XRoboToolkit

These steps involve both the host and the PICO headset.

### 3.1 Install XRoboToolkit PC Service on the Host

The PC service runs on the same machine that the PICO connects to.

Ubuntu 22.04 x86_64 host:

```bash
wget https://github.com/XR-Robotics/XRoboToolkit-PC-Service/releases/download/v1.0.0/XRoboToolkit_PC_Service_1.0.0_ubuntu_22.04_amd64.deb
sudo dpkg -i XRoboToolkit_PC_Service_1.0.0_ubuntu_22.04_amd64.deb
```

Ubuntu 24.04 x86_64 host:

```bash
wget https://github.com/XR-Robotics/XRoboToolkit-PC-Service/releases/download/v1.0.0/XRoboToolkit_PC_Service_1.0.0_ubuntu_24.04_amd64.deb
sudo dpkg -i XRoboToolkit_PC_Service_1.0.0_ubuntu_24.04_amd64.deb
```

If running the whole stack onboard on a Jetson, install the ARM service there:

```bash
sudo dpkg -i gear_sonic_deploy/thirdparty/roboticsservice_1.0.0.0_arm64.deb
```

For the recommended offboard workflow, install this on the host laptop.

### 3.2 Install XRoboToolkit App on PICO

Inside the PICO headset:

1. Complete the PICO initial setup.
2. Connect PICO to the same WiFi network as the host.
3. Enable Developer Mode.
4. Open the PICO browser.
5. Download and install `XRoboToolkit-PICO-1.1.1.apk`:
   https://github.com/XR-Robotics/XRoboToolkit-Unity-Client/releases/download/v1.1.1/XRoboToolkit-PICO-1.1.1.apk
6. The app appears in the `Unknown` section of the PICO library.

### 3.3 Pair and Calibrate Motion Trackers

Inside PICO:

1. Strap one motion tracker to each ankle.
2. Keep the tracker light indicator facing up.
3. Use tight pants or scrunch loose fabric so the trackers are visible.
4. In PICO settings, turn off `Safeguard` under `Developer`.
5. Open the motion tracker setup screen.
6. Unpair old trackers if needed.
7. Pair both trackers by holding their buttons for about 6 seconds.
8. Run the PICO calibration:
   - Sequence 1: stand stiff with controllers down by your sides.
   - Sequence 2: look down at the foot trackers until the headset cameras see
     them.
9. After calibration, wear the PICO around your forehead, facing forward, so it
   can keep seeing the trackers.

### 3.4 Connect PICO to the Host

Find the host WiFi IP:

```bash
ip -4 addr show
```

Inside the PICO XRoboToolkit app:

1. Set `PC Service` to the host WiFi IP.
2. Press reconnect if an old IP was already configured.
3. Confirm status shows `WORKING`.
4. Enable:
   - `Head`
   - `Controller`
   - `Send`
   - `Full body` for PICO Motion Tracker

If `WORKING` does not appear, verify that the PICO and host are on the same
WiFi network and that the XRoboToolkit PC service is running on the host.

## 4. Install the PICO Teleop Python Environment on the Host

Run from the repo root on the host:

```bash
bash install_scripts/install_pico.sh
source .venv_teleop/bin/activate
```

This creates `.venv_teleop` with:

- `gear_sonic[teleop]`
- `gear_sonic[sim]` on desktop hosts
- XRoboToolkit SDK
- Unitree SDK2 Python bindings on desktop hosts

If you also plan to collect VLA data, make sure `.venv_data_collection` from
step 2.5 exists on the host.

## 5. Validate in Simulation Before Real Robot

Run this on the host. This is required practice before real robot deployment.

### Terminal 1: MuJoCo Simulator

From repo root:

```bash
source .venv_teleop/bin/activate
python gear_sonic/scripts/run_sim_loop.py
```

### Terminal 2: C++ Deployment in Sim

From `gear_sonic_deploy/`:

```bash
cd gear_sonic_deploy
source scripts/setup_env.sh
./deploy.sh --input-type zmq_manager sim
```

Wait until you see `Init done`.

### Terminal 3: PICO Teleop Streamer

From repo root:

```bash
source .venv_teleop/bin/activate
python gear_sonic/scripts/pico_manager_thread_server.py --manager --vis_vr3pt --vis_smpl
```

For the first run, keep visualization on. You should see the Unitree G1 mesh at
the default pose. If no visualization appears or tracking is stale, re-check the
PICO XRoboToolkit IP and `WORKING` status.

### First Sim Teleop Sequence

1. Stand in calibration pose:
   - Upright.
   - Feet together.
   - Upper arms down close to torso.
   - Forearms bent 90 degrees forward.
   - Palms inward.
2. Press `A+B+X+Y` on PICO controllers. This engages the policy and runs
   `CALIB_FULL`.
3. Align your body and arms with the robot's current pose.
4. Press `A+X` to enter `POSE` mode.
5. Move naturally. The robot should track your full-body motion.
6. Press `A+X` again to return to `PLANNER` idle.
7. Press `A+B+X+Y` to stop.

Do not continue to real robot until this is smooth and you are comfortable with
emergency stop.

## 6. Prepare the Real Robot

On the robot side:

1. Power on the G1.
2. Put the robot on a gantry or equivalent safety setup for initial tests.
3. Ensure the robot is standing loose but supported as recommended in the docs.
4. Confirm the robot network is available to the host, typically on
   `192.168.123.x`.
5. If collecting VLA data, connect the robot cameras to the robot onboard
   computer. The supported and tested camera setup is Luxonis OAK cameras:
   one ego/head camera and optional left/right wrist cameras.

On the host:

1. Connect Ethernet from host to the robot network.
2. Keep host WiFi connected to the same WiFi network as the PICO.
3. Check the robot-side interface:

```bash
ip -4 addr show
```

You should see one host interface with a `192.168.123.x` address for the robot
network. The deployment command `real` auto-detects this interface. If it does
not, pass the interface name or the G1 IP explicitly.

Make sure the sim process is not running:

```bash
pgrep -af run_sim_loop.py
```

If any `run_sim_loop.py` process is still running, stop it before real robot
teleop. Sim and real instances conflict.

### 6.1 Camera Server on the Robot Computer for VLA Data Collection

Skip this subsection if you only want teleop without dataset recording.

For VLA data collection, this is the missing onboard piece: the robot computer
runs the camera server. It captures frames from the OAK cameras physically
connected to the robot and publishes them over ZMQ to the host on port `5555`.

SSH into the robot computer:

```bash
ssh <robot-user>@<robot-ip>
```

On the robot computer, clone the repo and install the camera environment:

```bash
git clone https://github.com/NVlabs/GR00T-WholeBodyControl.git
cd GR00T-WholeBodyControl
bash install_scripts/install_camera_server.sh
```

The script creates `.venv_camera`, installs `gear_sonic[camera]`, detects OAK
cameras, asks which physical camera maps to ego/left-wrist/right-wrist, and can
install the camera server as a systemd service.

Recommended: answer `y` when it asks to install the systemd service. Then check:

```bash
sudo systemctl status composed_camera_server.service
journalctl -u composed_camera_server.service -f
```

If you do not install the service, run the camera server manually on the robot:

```bash
source .venv_camera/bin/activate

# Single ego-view OAK camera
python -m gear_sonic.camera.composed_camera \
    --ego-view-camera oak \
    --ego-view-device-id <EGO_MXID> \
    --port 5555
```

For ego + wrist cameras:

```bash
source .venv_camera/bin/activate
python -m gear_sonic.camera.composed_camera \
    --ego-view-camera oak --ego-view-device-id <EGO_MXID> \
    --left-wrist-camera oak --left-wrist-device-id <LEFT_WRIST_MXID> \
    --right-wrist-camera oak --right-wrist-device-id <RIGHT_WRIST_MXID> \
    --port 5555
```

From the host, test the camera feed:

```bash
source .venv_data_collection/bin/activate
python gear_sonic/scripts/run_camera_viewer.py \
    --camera-host 192.168.123.164 \
    --camera-port 5555
```

Replace `192.168.123.164` with the robot computer IP if yours is different.

## 7. Run Real Robot Teleop Without Data Collection

Use this path when you only want to teleoperate the robot and do not need to
record a VLA dataset. Run these two terminals on the host laptop / workstation.

### Terminal 1: C++ Deployment for Real Robot

From `gear_sonic_deploy/`:

```bash
cd gear_sonic_deploy
source scripts/setup_env.sh
./deploy.sh --input-type zmq_manager real
```

When prompted, review the deployment configuration and confirm. Wait until you
see `Init done`.

If auto-detection fails, pass the robot network interface or IP:

```bash
./deploy.sh --input-type zmq_manager <G1-IP-or-interface>
```

If the PICO teleop streamer runs on a different machine from the C++ deployment,
tell the deployment where the ZMQ publisher is:

```bash
./deploy.sh --input-type zmq_manager --zmq-host <teleop-machine-ip> real
```

In the standard setup, both deployment and streamer run on the same host, so
`--zmq-host` can remain the default `localhost`.

### Terminal 2: PICO Teleop Streamer

From repo root:

```bash
source .venv_teleop/bin/activate
python gear_sonic/scripts/pico_manager_thread_server.py --manager
```

If the host has a display and this is an early test, use visualization:

```bash
python gear_sonic/scripts/pico_manager_thread_server.py --manager --vis_vr3pt --vis_smpl
```

Before starting, confirm that the IP configured inside PICO XRoboToolkit is the
host WiFi IP and that status is `WORKING`.

## 8. Run Real Robot Teleop with VLA Data Collection

Use this path when you want to record demonstrations as LeRobot datasets for
Isaac-GR00T / VLA post-training.

Before running this:

1. The robot camera server must be running on the robot computer.
2. `.venv_data_collection` must exist on the host.
3. `.venv_teleop` must exist on the host.
4. `gear_sonic_deploy` must be built and the ONNX models must be downloaded.
5. PICO XRoboToolkit must show `WORKING`.

### Option A: All-in-One Tmux Launcher on the Host

This is the recommended data collection path. It starts the C++ deployment,
PICO teleop streamer, data exporter, and camera viewer in a tmux session on the
host.

Install tmux if needed:

```bash
sudo apt install tmux
```

Run from the repo root on the host:

```bash
python gear_sonic/scripts/launch_data_collection.py \
    --camera-host 192.168.123.164 \
    --task-prompt "pick up the cup"
```

For ego + **both** wrist cameras:

```bash
python gear_sonic/scripts/launch_data_collection.py \
    --camera-host 192.168.123.164 \
    --task-prompt "pick up the cup" \
    --wrist-cameras both
```

For ego + **right** wrist only (no left camera on the robot):

```bash
python gear_sonic/scripts/launch_data_collection.py \
    --camera-host 192.168.123.164 \
    --task-prompt "pick up the cup" \
    --wrist-cameras right
```

Replace `192.168.123.164` with the robot computer IP if different.

The launcher creates a `sonic_data_collection` tmux session with panes for:

- C++ deployment.
- PICO teleop streamer.
- Data exporter.
- Camera viewer.

The deploy pane waits for confirmation before starting robot control. Click that
pane and press Enter only after reviewing the config and confirming the robot is
safe.

Useful tmux controls:

| Action | Command |
|---|---|
| Switch panes | `Ctrl+b`, then arrow keys |
| Detach while keeping processes running | `Ctrl+b`, then `d` |
| Reattach | `tmux attach -t sonic_data_collection` |
| Kill session | `tmux kill-session -t sonic_data_collection` |

### Option B: Manual Multi-Terminal Setup on the Host

Use this if you want direct control over each process.

Terminal 1: C++ deployment:

```bash
cd gear_sonic_deploy
source scripts/setup_env.sh
./deploy.sh --input-type zmq_manager real
```

Terminal 2: PICO teleop streamer:

```bash
source .venv_teleop/bin/activate
python gear_sonic/scripts/pico_manager_thread_server.py --manager
```

Terminal 3: data exporter:

```bash
source .venv_data_collection/bin/activate
python gear_sonic/scripts/run_data_exporter.py \
    --task-prompt "pick up the cup" \
    --camera-host 192.168.123.164 \
    --camera-port 5555
```

Terminal 4: optional camera viewer:

```bash
source .venv_data_collection/bin/activate
python gear_sonic/scripts/run_camera_viewer.py \
    --camera-host 192.168.123.164 \
    --camera-port 5555
```

For wrist cameras, add `--wrist-cameras right`, `--wrist-cameras left`, or `--wrist-cameras both` to the data exporter / launcher (``--record-wrist-cameras`` remains as a legacy alias for ``both``).

### Recording Controls

These controls are independent of teleop mode switching:

| Input | Action |
|---|---|
| Left Grip + A | Toggle recording: start a new episode, or stop and save the current one |
| Left Grip + B | Discard the current episode without saving |

Keyboard equivalents for the data exporter:

| Key | Action |
|---|---|
| `c` | Toggle recording |
| `x` | Discard current episode |

Datasets are saved under `outputs/<dataset-name>/` unless you override the
exporter output directory. If `--dataset-name` is omitted, a timestamped dataset
name is generated automatically.

The recorded LeRobot dataset includes robot state, teleop target/action data,
task prompt annotations, ego-view camera video, and optionally wrist camera
videos.

## 9. Operator Sequence on the PICO

1. Put on the PICO headset and controllers.
2. Confirm both foot trackers are secure and visible.
3. Stand in calibration pose.
4. Confirm the robot is supported and the safety operator is ready.
5. Press `A+B+X+Y`.
   - First press starts the policy and runs `CALIB_FULL`.
   - The system enters `PLANNER`.
6. Hold the calibration pose steady for 1 to 2 seconds.
7. Align your body and arms with the robot's current pose.
8. Press `A+X` to enter `POSE` full-body teleop.
9. Move naturally. Avoid hesitant, overly slow motion.
10. Use each controller trigger to close the corresponding robot hand.
11. Press `A+X` again to return to `PLANNER` idle.
12. Press `A+B+X+Y` to stop the policy.

Emergency stop options:

- PICO controllers: `A+B+X+Y`.
- C++ deployment terminal: `O`.

## 10. Useful PICO Controls

| Action | Button | Notes |
|---|---|---|
| Start / stop policy | `A+B+X+Y` | First press engages and calibrates. Next press stops. |
| Toggle POSE | `A+X` | Switches between `PLANNER` and `POSE`. |
| Toggle PLANNER_FROZEN_UPPER | `B+Y` | Planner locomotion with upper body frozen. |
| Toggle VR_3PT | Left stick click | From planner modes, enters 3-point upper-body control and calibrates wrists. |
| Hand grasp | Trigger | Per hand. |
| Move in planner modes | Left stick | Forward, backward, strafe. |
| Yaw in planner modes | Right stick horizontal | Continuous heading control. |
| Next locomotion mode | `A+B` | Planner modes only. |
| Previous locomotion mode | `X+Y` | Planner modes only. |

## 11. Troubleshooting Checklist

### PICO does not connect

- Confirm PICO and host are on the same WiFi.
- Confirm PICO XRoboToolkit `PC Service` IP is the host WiFi IP, not the robot
  Ethernet IP.
- Confirm XRoboToolkit status is `WORKING`.
- Restart XRoboToolkit on PICO.
- Restart the host PC service if needed.

### Robot does not move with PICO

- Confirm Terminal 1 C++ deployment is running with `--input-type zmq_manager`.
- Confirm Terminal 2 streamer is running with `--manager`.
- Confirm `Init done` appeared before pressing PICO buttons.
- Confirm PICO tracking is valid in the PICO avatar or visualization.
- Recalibrate with `A+B+X+Y`.

### Robot makes sudden aggressive motions

- Stop with `A+B+X+Y` or `O`.
- Check if you switched into `POSE` while your body did not match the robot pose.
- Recalibrate carefully.
- Confirm foot trackers are visible and not occluded by clothing.
- Check for high WiFi latency or packet drops.

### Tracking is jittery or delayed

- Use a private low-latency router.
- Avoid public or congested WiFi.
- Keep PICO and host on the same local network.
- Watch deployment terminal warnings for high ZMQ latency.
- Expected latency guidance from docs:
  - Good: less than 10 ms.
  - Acceptable: 10 to 30 ms.
  - Poor: greater than 30 ms.

### Data exporter receives no camera frames

- Confirm the camera server is running on the robot computer:

```bash
sudo systemctl status composed_camera_server.service
journalctl -u composed_camera_server.service -f
```

- Confirm the host can reach the robot computer IP on the robot network.
- Confirm `--camera-host` is the robot computer IP, not the host WiFi IP.
- Test with the camera viewer from the host:

```bash
source .venv_data_collection/bin/activate
python gear_sonic/scripts/run_camera_viewer.py \
    --camera-host 192.168.123.164 \
    --camera-port 5555
```

### Data exporter records no robot state or teleop action

- Confirm C++ deployment is running and publishing robot state on port `5557`.
- Confirm PICO teleop streamer is running and publishing `pose` /
  `manager_state` on port `5556`.
- If using the manual setup, start C++ deployment and PICO streamer before the
  data exporter.
- For standard single-host setup, keep `--state-zmq-host localhost` and
  `--sonic-zmq-host localhost`, which are the exporter defaults.

## 12. Optional: Onboard Deployment Variant

The recommended workflow above runs deployment and PICO streamer on the host
laptop/workstation. If you intentionally run deployment onboard on the G1 Orin:

- The onboard computer must have JetPack 6.
- It must use TensorRT `10.7`.
- Install the ARM XRoboToolkit service on the onboard computer if PICO connects
  directly to it.
- The PICO XRoboToolkit app must use the onboard computer's reachable WiFi IP.
- Headless mode is preferred:

```bash
python gear_sonic/scripts/pico_manager_thread_server.py --manager
```

Only use this variant if the robot computer, WiFi routing, and TensorRT setup
are intentionally configured for onboard operation.
