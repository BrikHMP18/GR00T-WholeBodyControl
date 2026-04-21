# README Teleop

Quick PICO teleop setup for `GR00T-WholeBodyControl` on Ubuntu 22.04.

## 1) Install XRoboToolkit PC Service

```bash
cd ~/Downloads
sudo dpkg -i XRoboToolkit_PC_Service_1.0.0_ubuntu_22.04_amd64.deb
sudo apt --fix-broken install -y
```

## 2) Start service (keep running)

```bash
/opt/apps/roboticsservice/runService.sh
```

## 3) Repo + LFS

```bash
cd ~/NONHUMAN/GR00T-WholeBodyControl
git lfs pull
```

## 4) Install teleop env

From repo root:

```bash
bash install_scripts/install_pico.sh
source .venv_teleop/bin/activate
```

If already in `install_scripts/`:

```bash
./install_pico.sh
```

## 5) Connect PICO

- Same Wi-Fi on laptop + PICO.
- In laptop, get IP:

```bash
hostname -I
```

- Use Wi-Fi IPv4 (example `192.168.1.36`) in PICO `PC Service`.
- Press `Enter/Reconnect`, confirm status `WORKING`.
- In PICO app:
  - Tracking: `Head` + `Controller`
  - Data/Control: `Send`
  - Pico Motion Tracker: `Full body`

## 6) Run teleop streamer

From repo root:

```bash
source .venv_teleop/bin/activate
python gear_sonic/scripts/pico_manager_thread_server.py --manager --vis_vr3pt --vis_smpl
```

Headless:

```bash
python gear_sonic/scripts/pico_manager_thread_server.py --manager
```

## Notes

- `arm64` package is for Jetson/onboard.
- `amd64` package is for Intel/AMD laptops.
- Full `gear_sonic_deploy` control requires NVIDIA CUDA/TensorRT.
