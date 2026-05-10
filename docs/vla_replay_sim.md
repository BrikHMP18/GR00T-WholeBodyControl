# VLA Replay Video Inference In Simulation

This document describes the local setup for testing the push-peluche VLA policy
in MuJoCo simulation while feeding the policy a recorded ego-view dataset video.

## Goal

We want to see how the fine-tuned VLA policy controls the simulated G1 through
SONIC WBC. Since the real robot and real scene are unavailable, the VLA camera
input is replayed from the dataset:

- Dataset: `NONHUMAN-RESEARCH/push_peluche_processed_and_cleaned`
- Model: `NONHUMAN-RESEARCH/push_peluche_48demos_best_10k`
- Prompt:
  `Push the panda off the chair, turn 180 degrees to the right, then return to the starting position.`

Important limitation: this is not closed-loop visual evaluation. The simulated
robot moves in MuJoCo, but the policy continues seeing the recorded video, not
the simulated camera. This validates model loading, observation formatting,
PolicyServer calls, latent action publishing, and WBC execution.

## Current Status

The local simulation/deploy side is working:

- MuJoCo simulation starts.
- Replay-video camera publishes the dataset MP4 on ZMQ port `5555`.
- C++ deploy builds with ROS2 disabled, starts with `zmq_manager`, publishes
  robot state on `5557`, and reaches `Init Done`.
- The keyboard publisher sends `k`, `i`, and `p` correctly.

The remaining blocker is GPU memory for the GR00T PolicyServer on this laptop.
After Hugging Face access to `nvidia/Cosmos-Reason2-2B` was resolved, the policy
loaded the model files but failed while moving the model to CUDA:

```text
torch.OutOfMemoryError: CUDA out of memory
GPU 0 total capacity: 7.60 GiB
Tried to allocate: 288.00 MiB
```

This is not a deploy/ROS2/simulation failure. It means the RTX 4060 Laptop GPU
with 8 GB VRAM is too tight for this GR00T checkpoint, especially when desktop
apps and the TensorRT deploy process also use VRAM. The recommended path is to
run PolicyServer on a GPU with 16 GB+ VRAM and keep MuJoCo/deploy/replay-camera
on this laptop.

## What Is Already Downloaded Locally

Checkpoint:

```text
/home/raul/NONHUMAN/GR00T-WholeBodyControl/checkpoints/push_peluche_48demos_best_10k
```

Expected checkpoint files:

```text
config.json
embodiment_id.json
model-00001-of-00003.safetensors
model-00002-of-00003.safetensors
model-00003-of-00003.safetensors
model.safetensors.index.json
processor_config.json
statistics.json
trainer_state.json
training_args.bin
wandb_config.json
experiment_cfg/
```

Replay video:

```text
/home/raul/NONHUMAN/GR00T-WholeBodyControl/data/push_peluche_processed_and_cleaned/videos/chunk-000/observation.images.ego_view/episode_000000.mp4
```

This episode has 863 frames at 50 FPS and is about 2.2 MB.

Isaac-GR00T source checkout:

```text
/home/raul/NONHUMAN/Isaac-GR00T
```

The checkout is at commit `3df8b38` and contains:

```text
/home/raul/NONHUMAN/Isaac-GR00T/gr00t/eval/run_gr00t_server.py
```

I did not run the full Isaac-GR00T server environment install here. The local
machine has an RTX 4060 Laptop GPU with 8 GB VRAM, while the Isaac-GR00T README
recommends 16 GB+ VRAM for inference. You can still try it locally, but a remote
GPU machine is safer for the PolicyServer.

## Changes Made

### `.gitignore`

Added:

```gitignore
checkpoints/
```

Reason: Hugging Face model downloads include JSON/config files that are not
covered by the existing `*.safetensors` ignore rule. This prevents accidental
commits of large downloaded checkpoints.

### `gear_sonic/pyproject.toml`

Updated the `inference` extra:

- Removed the full Isaac-GR00T Git dependency from the local inference venv.
- Added `huggingface-hub[cli]` so helper downloads can use `hf`.

Reason: the local inference client only needs ZMQ/msgpack transport to talk to
an already-running Isaac-GR00T PolicyServer. Installing the full Isaac-GR00T repo
inside `.venv_inference` failed in this environment because of upstream package
metadata and a transitive `torchcodec` local-wheel source. The PolicyServer still
must be run from an Isaac-GR00T environment.

### `install_scripts/install_inference.sh`

Updated the script comments to match the new local-client setup.

Reason: `.venv_inference` now installs the deployment-side dependencies and the
local compatible PolicyClient, not the full Isaac-GR00T package.

### `gear_sonic/utils/inference/policy_client.py`

Added a lightweight `PolicyClient` compatible with the Isaac-GR00T PolicyServer
ZMQ API. It supports:

- `ping`
- `get_action`
- `reset`
- generic endpoint calls

Reason: lets `run_vla_inference.py` run from the local `.venv_inference` without
requiring the full `gr00t` Python package locally.

### `gear_sonic/scripts/run_vla_inference.py`

Changed the PolicyClient import:

- Prefer `gr00t.policy.server_client.PolicyClient` if installed.
- Fall back to `gear_sonic.utils.inference.policy_client.PolicyClient`.

Reason: keeps compatibility with official Isaac-GR00T installs while making the
deployment-only local environment work.

### `gear_sonic/scripts/run_video_replay_camera.py`

Added a ZMQ camera server that streams an MP4 as `ImageMessageSchema` with the
image key expected by VLA inference:

```python
images["ego_view"]
timestamps["ego_view"]
```

Reason: `run_vla_inference.py` expects a live `ComposedCameraClientSensor`, so
the replay video must look exactly like the normal camera server.

### `gear_sonic/scripts/download_push_peluche_replay.py`

Added a helper to download one random or specified push-peluche MP4 episode from
Hugging Face.

Reason: avoids cloning the full dataset just to test a replay-camera input.

### `gear_sonic/scripts/run_inference_keyboard.py`

Added a reusable ZMQ keyboard publisher for inference controls:

- `k`: start/stop C++ control loop
- `i`: send initial pose
- `p`: pause/resume VLA inference
- `t <text>`: change prompt

Reason: manual multi-terminal testing should not depend on the tmux launcher.

### `gear_sonic/scripts/launch_vla_replay_sim.py`

Added a dedicated tmux launcher for this replay-video simulation experiment.
It starts six terminals:

1. Isaac-GR00T PolicyServer
2. MuJoCo simulator
3. Replay-video camera server
4. C++ deploy
5. VLA inference client
6. Keyboard publisher

The deploy terminal is auto-confirmed with `y`, uses `--input-type zmq_manager`,
uses `--output-type zmq`, and exports `HAS_ROS2=0`.

For local GPU runs, the launcher waits for the PolicyServer port before starting
the GPU-consuming C++ deploy. This avoids a load-time VRAM spike where the VLA
model and TensorRT WBC are initialized at the same time.

Reason: the generic launcher is designed for normal camera/sim inference. This
experiment needs the policy camera input to come from an MP4 dataset replay, so
the simulator must not publish images on the same camera port.

### `gear_sonic_deploy/deploy.sh`

Added default ROS2 opt-out behavior for non-ROS2 input/output modes.

For the VLA replay simulation command:

```bash
./deploy.sh --input-type zmq_manager --output-type zmq sim
```

the script now exports `HAS_ROS2=0` before sourcing `scripts/setup_env.sh`.

Reason: the official VLA flow uses ZMQ between PolicyServer, inference client,
camera server, and C++ deploy. ROS2 is not needed here.

### `gear_sonic_deploy/scripts/setup_env.sh`

Changed ROS2 setup from auto-detect to opt-in:

- Default: `HAS_ROS2=0`, do not source `/opt/ros/.../setup.bash`.
- Explicit ROS2: run with `HAS_ROS2=1` if a ROS2 input/output path is really
  needed.

Reason: this machine has ROS2 Humble installed. The old auto-detection sourced
ROS2 and mixed system CycloneDDS headers with the vendored Unitree/CycloneDDS
stack, causing the large compile failure in `ddscxx`.

### `docs/vla_replay_sim.md`

This guide. It documents setup, changes, commands, verification, and limitations.

### `gear_sonic_deploy/thirdparty/unitree_sdk2/.../Reference.hpp`

Patched the vendored CycloneDDS C++ header:

```cpp
#include <cstddef>
void* operator new(std::size_t);
```

Reason: GCC 11/12 with C++20 rejects the old `void* operator new(size_t);`
declaration inside this namespace with:

```text
error: 'operator new' takes type 'size_t' ('long unsigned int') as first parameter [-fpermissive]
```

After this patch, `just build` from `gear_sonic_deploy/` completed and produced:

```text
target/release/g1_deploy_onnx_ref
```

The later `cdr_stream.hpp` errors (`position`, `incr_position`, and missing
`memcpy`) were not patched directly. They were caused by the ROS2/system DDS
interference above. With ROS2 disabled for this ZMQ flow, the deploy build is
clean.

## One-Time Setup

The inference venv has already been installed successfully after the local client
fallback change:

```bash
cd /home/raul/NONHUMAN/GR00T-WholeBodyControl
source .venv_inference/bin/activate
python gear_sonic/scripts/run_vla_inference.py --help
```

If you ever need to recreate it:

```bash
cd /home/raul/NONHUMAN/GR00T-WholeBodyControl
bash install_scripts/install_inference.sh
```

MuJoCo simulation venv already exists as `.venv_sim`. If it needs recreation:

```bash
cd /home/raul/NONHUMAN/GR00T-WholeBodyControl
bash install_scripts/install_mujoco_sim.sh
```

Isaac-GR00T has been cloned but not fully synced. To prepare the PolicyServer
environment on a GPU machine:

```bash
cd /home/raul/NONHUMAN/Isaac-GR00T
uv sync --all-extras
```

If you run the PolicyServer on a different GPU machine, clone Isaac-GR00T there
and copy/download the checkpoint there, or mount this checkpoint path.

## Re-Download Commands

Only needed if you delete local files.

Download the fine-tuned model:

```bash
cd /home/raul/NONHUMAN/GR00T-WholeBodyControl
source .venv_inference/bin/activate
mkdir -p checkpoints
hf download NONHUMAN-RESEARCH/push_peluche_48demos_best_10k \
  --local-dir checkpoints/push_peluche_48demos_best_10k
```

Download one replay video:

```bash
cd /home/raul/NONHUMAN/GR00T-WholeBodyControl
source .venv_inference/bin/activate
python gear_sonic/scripts/download_push_peluche_replay.py --episode-index 0
```

## Official Guide Alignment

The setup follows the official VLA inference architecture:

- Isaac-GR00T PolicyServer serves VLA actions over ZMQ.
- `run_vla_inference.py` reads camera images plus robot state, queries the
  PolicyServer, and publishes actions to C++ deploy.
- `gear_sonic_deploy` runs the whole-body controller.

The official docs also recommend MuJoCo sim and C++ deploy as separate processes
for sim2sim. This replay setup adds one adaptation: the camera server is our
MP4 replay server instead of a live robot camera or MuJoCo image publisher.

References:

- https://nvlabs.github.io/GR00T-WholeBodyControl/tutorials/vla_inference.html
- https://nvlabs.github.io/GR00T-WholeBodyControl/getting_started/quickstart.html

## Run The Test

### One Command - Six Terminals

Recommended command from the repo root:

```bash
cd /home/raul/NONHUMAN/GR00T-WholeBodyControl
source .venv_inference/bin/activate
python gear_sonic/scripts/launch_vla_replay_sim.py
```

This creates a tmux session named:

```text
sonic_vla_replay_sim
```

It starts:

```text
window policy: Isaac-GR00T PolicyServer
window sim:    MuJoCo simulator
core pane 0:   C++ deploy, auto-confirmed with y
core pane 1:   VLA inference client
core pane 2:   replay-video camera
core pane 3:   keyboard publisher
```

When deploy shows:

```text
Init Done
```

and the inference client is paused, type in the keyboard pane:

```text
k
i
p
```

Meaning:

- `k`: starts the C++ control loop in planner/ZMQ-manager mode.
- `i`: sends the latent initial pose and switches to pose mode.
- `p`: unpauses VLA inference.

To preview the exact commands without launching tmux:

```bash
cd /home/raul/NONHUMAN/GR00T-WholeBodyControl
source .venv_inference/bin/activate
python gear_sonic/scripts/launch_vla_replay_sim.py --dry-run --no-attach
```

If the local 8 GB GPU cannot run PolicyServer, start PolicyServer on a larger
GPU machine and launch the local sim stack with:

```bash
cd /home/raul/NONHUMAN/GR00T-WholeBodyControl
source .venv_inference/bin/activate
python gear_sonic/scripts/launch_vla_replay_sim.py \
  --no-start-policy-server \
  --policy-host <gpu_machine_ip>
```

PolicyServer access note: the fine-tuned checkpoint config references the gated
backbone `nvidia/Cosmos-Reason2-2B`. The Hugging Face account/token used on the
PolicyServer machine must have access to that repo. If PolicyServer fails with
`403 Client Error` or `Cannot access gated repo`, open:

```text
https://huggingface.co/nvidia/Cosmos-Reason2-2B
```

request/accept access, then authenticate on the machine:

```bash
source /home/raul/NONHUMAN/GR00T-WholeBodyControl/.venv_inference/bin/activate
hf auth login
hf download nvidia/Cosmos-Reason2-2B config.json
```

After that, restart the tmux session:

```bash
tmux kill-session -t sonic_vla_replay_sim
python gear_sonic/scripts/launch_vla_replay_sim.py
```

Local VRAM note: on the RTX 4060 Laptop GPU with about 8 GB VRAM, the policy can
fail with:

```text
torch.OutOfMemoryError: CUDA out of memory
```

This is why the launcher now waits for PolicyServer to finish loading before it
starts the deploy process. If it still OOMs, close extra GPU apps such as Chrome,
Cursor, Steam, and other viewers, then restart the tmux session. The robust path
is still to run PolicyServer on a 16 GB+ GPU machine and use `--policy-host`.

### Recommended: PolicyServer On A Bigger GPU

On the bigger GPU machine, prepare Isaac-GR00T and the model checkpoint:

```bash
cd /home/raul/NONHUMAN/Isaac-GR00T
uv sync --all-extras

hf auth login
hf download NONHUMAN-RESEARCH/push_peluche_48demos_best_10k \
  --local-dir /home/raul/NONHUMAN/GR00T-WholeBodyControl/checkpoints/push_peluche_48demos_best_10k
hf download nvidia/Cosmos-Reason2-2B config.json
```

Then start PolicyServer there:

```bash
cd /home/raul/NONHUMAN/Isaac-GR00T
unset VIRTUAL_ENV
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
export NO_ALBUMENTATIONS_UPDATE=1
uv run python gr00t/eval/run_gr00t_server.py \
  --model-path /home/raul/NONHUMAN/GR00T-WholeBodyControl/checkpoints/push_peluche_48demos_best_10k \
  --embodiment-tag UNITREE_G1_SONIC \
  --device cuda:0 \
  --host 0.0.0.0 \
  --port 5550
```

Expected success log:

```text
✓ Server ready — listening on 0.0.0.0:5550
```

On this laptop, launch the rest of the sim stack and point it to that GPU
machine:

```bash
cd /home/raul/NONHUMAN/GR00T-WholeBodyControl
source .venv_inference/bin/activate
python gear_sonic/scripts/launch_vla_replay_sim.py \
  --no-start-policy-server \
  --policy-host <gpu_machine_ip>
```

After deploy shows `Init Done` and inference connects to PolicyServer, type in
the keyboard pane:

```text
k
i
p
```

Network check from this laptop:

```bash
nc -vz <gpu_machine_ip> 5550
```

If that fails, open/firewall-forward TCP port `5550` on the GPU machine or put
both machines on the same reachable LAN.

Navigation:

```text
Ctrl+b, arrow keys  switch panes
Ctrl+b, n / p       switch windows
Ctrl+b, d           detach
Ctrl+\              kill the whole tmux session
```

To reattach:

```bash
tmux attach -t sonic_vla_replay_sim
```

To stop everything:

```bash
tmux kill-session -t sonic_vla_replay_sim
```

### Manual Setup

Use separate terminals. Start them in this order.

All relative commands in this guide assume this repo root:

```bash
cd /home/raul/NONHUMAN/GR00T-WholeBodyControl
```

If your prompt is at `~` or anywhere else, run that `cd` first. Otherwise the
virtualenv path `.venv_inference/bin/activate` and scripts like
`gear_sonic/scripts/run_video_replay_camera.py` will not be found.

### Terminal 1 - PolicyServer

Run from the Isaac-GR00T repo/environment on the GPU machine:

```bash
cd /home/raul/NONHUMAN/Isaac-GR00T
uv run python gr00t/eval/run_gr00t_server.py \
  --model-path /home/raul/NONHUMAN/GR00T-WholeBodyControl/checkpoints/push_peluche_48demos_best_10k \
  --embodiment-tag UNITREE_G1_SONIC \
  --device cuda:0 \
  --port 5550
```

If the PolicyServer is on another machine, replace `localhost` with that machine
IP in Terminal 5.

Local note: this laptop reports an RTX 4060 Laptop GPU with 8 GB VRAM. If the
server fails with CUDA OOM, run Terminal 1 on a larger GPU box and set
`--host <gpu_machine_ip>` in Terminal 5.

### Terminal 2 - MuJoCo Sim

```bash
cd /home/raul/NONHUMAN/GR00T-WholeBodyControl
source .venv_sim/bin/activate
python gear_sonic/scripts/run_sim_loop.py
```

Do not pass `--enable-image-publish` for this replay-video test, because port
`5555` is reserved for the replay camera server.

### Terminal 3 - Replay Camera

```bash
cd /home/raul/NONHUMAN/GR00T-WholeBodyControl
source .venv_inference/bin/activate
python gear_sonic/scripts/run_video_replay_camera.py \
  --video-path data/push_peluche_processed_and_cleaned/videos/chunk-000/observation.images.ego_view/episode_000000.mp4 \
  --port 5555 \
  --fps 50 \
  --image-key ego_view
```

Expected log:

```text
Video replay camera: ...
Source: 863 frames @ 50.00 FPS
Sensor server running at tcp://*:5555
Published 100 frames ...
```

Optional camera visual check:

```bash
cd /home/raul/NONHUMAN/GR00T-WholeBodyControl
source .venv_inference/bin/activate
python gear_sonic/scripts/run_camera_viewer.py \
  --camera-host localhost \
  --camera-port 5555 \
  --fps 30
```

### Terminal 4 - C++ Deploy

```bash
cd /home/raul/NONHUMAN/GR00T-WholeBodyControl/gear_sonic_deploy
export HAS_ROS2=0
./deploy.sh --input-type zmq_manager --output-type zmq sim
```

When prompted:

```text
Proceed with deployment? [Y/n]:
```

Press Enter.

For a non-interactive run:

```bash
cd /home/raul/NONHUMAN/GR00T-WholeBodyControl/gear_sonic_deploy
export HAS_ROS2=0
printf 'y\n' | ./deploy.sh --input-type zmq_manager --output-type zmq sim
```

### Terminal 5 - VLA Inference Client

```bash
cd /home/raul/NONHUMAN/GR00T-WholeBodyControl
source .venv_inference/bin/activate
python gear_sonic/scripts/run_vla_inference.py \
  --host localhost \
  --port 5550 \
  --embodiment-tag unitree_g1_sonic \
  --prompt "Push the panda off the chair, turn 180 degrees to the right, then return to the starting position." \
  --camera-host localhost \
  --camera-port 5555 \
  --action-publish-rate 50 \
  --action-horizon 40 \
  --rate 2.5 \
  --verbose-timing
```

Expected logs:

```text
Connecting to PolicyServer at localhost:5550...
PolicyServer is reachable.
Starting the policy loop with language prompt: ...
Pausing...
```

After unpausing with Terminal 6, expect:

```text
New action chunk (...)
ZMQ: Sent latent action - frame: ...
```

### Terminal 6 - Keyboard Publisher

```bash
cd /home/raul/NONHUMAN/GR00T-WholeBodyControl
source .venv_inference/bin/activate
python gear_sonic/scripts/run_inference_keyboard.py
```

Type these commands in order:

```text
k
i
p
```

Meaning:

- `k`: starts the C++ control loop in PLANNER mode.
- `i`: sends the latent initial pose and switches to POSE mode.
- `p`: unpauses VLA inference.

The simulated robot should then move using VLA-predicted latent actions.

## Stop Sequence

In Terminal 6:

```text
p
k
```

Then stop each running process with `Ctrl+C`.

## Verification Already Done

These checks were run locally:

```bash
python -m py_compile \
  gear_sonic/scripts/run_video_replay_camera.py \
  gear_sonic/scripts/download_push_peluche_replay.py \
  gear_sonic/scripts/run_inference_keyboard.py \
  gear_sonic/utils/inference/policy_client.py
```

```bash
source .venv_inference/bin/activate
python gear_sonic/scripts/run_vla_inference.py --help
python gear_sonic/scripts/download_push_peluche_replay.py --help
python gear_sonic/scripts/run_video_replay_camera.py \
  --video-path data/push_peluche_processed_and_cleaned/videos/chunk-000/observation.images.ego_view/episode_000000.mp4 \
  --port 5599 \
  --fps 50 \
  --max-frames 3 \
  --warmup-seconds 0 \
  --print-every 1
```

The replay-camera test published frames successfully.

The local fallback `PolicyClient` was also tested against a small fake ZMQ REP
server for `ping` and `get_action`; numpy arrays survived msgpack serialization
with the expected shapes.

The deploy was run against MuJoCo with:

```bash
printf 'y\n' | ./deploy.sh --input-type zmq_manager --output-type zmq sim
```

Observed verification:

```text
ROS2 disabled (HAS_ROS2 unset or 0)
ROS2 not found - building without ROS2InputHandler support
Initialized ZMQ output interface
Binding to port: 5557 and topic: g1_debug
Total output interfaces initialized: 1
Init Done
```

This confirms the previous build failure was from ROS2/system DDS interference,
not from the ZMQ deploy path itself.

Checkpoint download was verified by file presence and size:

```text
checkpoints/push_peluche_48demos_best_10k: about 12 GB
data/push_peluche_processed_and_cleaned: about 2.2 MB
```

Environment checks:

```text
.venv_inference exists and imports tyro, cv2, zmq, msgpack_numpy, pinocchio, huggingface_hub.
gr00t is intentionally not installed in .venv_inference; run_vla_inference.py uses the local fallback PolicyClient.
Isaac-GR00T is cloned at /home/raul/NONHUMAN/Isaac-GR00T.
```

## Troubleshooting

If `run_vla_inference.py` says `PolicyServer not reachable`, check Terminal 1
and make sure port `5550` is reachable.

If Terminal 1 fails with `Cannot access gated repo` for
`nvidia/Cosmos-Reason2-2B`, the current Hugging Face account is logged in but
does not yet have access to the gated NVIDIA backbone. Request access on the
model page, then run `hf auth login` again if needed.

If Terminal 1 fails with `torch.OutOfMemoryError: CUDA out of memory`, the model
started loading but the GPU did not have enough free VRAM. Stop the session,
close GPU-heavy desktop apps, and relaunch. If it still fails, run PolicyServer
on a larger GPU and pass `--policy-host <gpu_machine_ip>`.

If it waits for camera messages, check Terminal 3 and make sure no other process
is using port `5555`.

If it waits for state messages, check Terminal 4. The C++ deploy process must be
running and publishing `g1_debug` state on port `5557`.

If MuJoCo binds camera port `5555`, restart Terminal 2 without
`--enable-image-publish`.

If `gear_sonic_deploy` prints many ROS2/CycloneDDS errors during build, make
sure this ZMQ flow is not enabling ROS2:

```bash
cd /home/raul/NONHUMAN/GR00T-WholeBodyControl/gear_sonic_deploy
export HAS_ROS2=0
just build
```

Expected CMake lines:

```text
ROS2 disabled (HAS_ROS2 unset or 0)
ROS2 not found - building without ROS2InputHandler support
```

If `gear_sonic_deploy` fails during build with the CycloneDDS `operator new`
error, confirm that this file has the local patch:

```bash
grep -n "operator new" \
  /home/raul/NONHUMAN/GR00T-WholeBodyControl/gear_sonic_deploy/thirdparty/unitree_sdk2/thirdparty/include/ddscxx/dds/core/Reference.hpp
```

Expected:

```text
void* operator new(std::size_t);
```
