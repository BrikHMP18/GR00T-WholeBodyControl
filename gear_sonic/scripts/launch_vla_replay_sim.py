"""Launch the six-process VLA replay simulation stack in tmux.

This launcher is intentionally separate from the generic inference launcher
because this experiment feeds the VLA policy a recorded dataset video instead
of MuJoCo camera frames.
"""

from dataclasses import dataclass
from pathlib import Path
import os
import shlex
import shutil
import signal
import socket
import subprocess
import sys
import time


def _bootstrap_venv() -> None:
    try:
        import tyro  # noqa: F401
        return
    except ImportError:
        pass

    repo_root = Path(__file__).resolve().parent.parent.parent
    venv_python = repo_root / ".venv_inference" / "bin" / "python"
    if not venv_python.exists():
        print(
            "ERROR: tyro is not installed and .venv_inference was not found.\n"
            "Run: bash install_scripts/install_inference.sh"
        )
        sys.exit(1)

    os.execv(str(venv_python), [str(venv_python)] + sys.argv)


_bootstrap_venv()

import tyro


SESSION_NAME = "sonic_vla_replay_sim"
DEFAULT_PROMPT = (
    "Push the panda off the chair, turn 180 degrees to the right, "
    "then return to the starting position."
)


@dataclass
class ReplaySimLaunchConfig:
    """CLI config for the replay-video VLA sim launcher."""

    prompt: str = DEFAULT_PROMPT
    """Language prompt sent to the VLA policy."""

    replay_video_path: str = (
        "data/push_peluche_processed_and_cleaned/videos/chunk-000/"
        "observation.images.ego_view/episode_000000.mp4"
    )
    """Dataset MP4 to replay as the ego_view camera."""

    policy_repo: str = "/home/raul/NONHUMAN/Isaac-GR00T"
    """Path to the Isaac-GR00T checkout used for PolicyServer."""

    policy_model_path: str = "checkpoints/push_peluche_48demos_best_10k"
    """Fine-tuned VLA checkpoint path. Relative paths are resolved from repo root."""

    start_policy_server: bool = True
    """Start a local Isaac-GR00T PolicyServer in tmux."""

    policy_host: str = "localhost"
    """PolicyServer host used by run_vla_inference.py."""

    policy_port: int = 5550
    """PolicyServer port."""

    policy_device: str = "cuda:0"
    """Device passed to the Isaac-GR00T PolicyServer."""

    policy_backbone_repo: str = "nvidia/Cosmos-Reason2-2B"
    """Gated backbone repo referenced by the fine-tuned checkpoint config."""

    check_policy_backbone_access: bool = True
    """Check Hugging Face access to the gated backbone before launching locally."""

    wait_policy_server: bool = True
    """Wait for PolicyServer port before starting GPU-consuming deploy/sim processes."""

    policy_startup_timeout_s: int = 900
    """Maximum seconds to wait for the local PolicyServer to become reachable."""

    camera_port: int = 5555
    """ZMQ camera port for the replay-video camera server."""

    camera_fps: float = 50.0
    """Replay camera FPS."""

    deploy_zmq_host: str = "localhost"
    """ZMQ host passed to gear_sonic_deploy/deploy.sh."""

    inference_rate: float = 2.5
    """VLA forward-pass rate in Hz."""

    action_publish_rate: int = 50
    """Action publication rate from inference client to C++ deploy."""

    action_horizon: int = 40
    """Number of actions per VLA inference chunk."""

    attach: bool = True
    """Attach to tmux after launching."""

    kill_existing: bool = True
    """Kill an existing session with the same name before launching."""

    dry_run: bool = False
    """Print the six commands without creating tmux panes."""


def _quote(value: str | Path) -> str:
    return shlex.quote(str(value))


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def _resolve_from_repo(repo_root: Path, value: str) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = repo_root / path
    return path.resolve()


def _tmux(
    *args: str, check: bool = True, quiet: bool = False
) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["tmux", *args],
        check=check,
        text=True,
        capture_output=quiet,
    )


def _send(target: str, command: str) -> None:
    _tmux("send-keys", "-t", target, command, "C-m")


def _is_port_open(host: str, port: int, timeout_s: float = 0.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout_s):
            return True
    except OSError:
        return False


def _wait_for_port(host: str, port: int, timeout_s: int) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if _is_port_open(host, port):
            return True
        time.sleep(2.0)
    return False


def _check_prerequisites(config: ReplaySimLaunchConfig, repo_root: Path) -> None:
    errors: list[str] = []

    if not shutil.which("tmux") and not config.dry_run:
        errors.append("tmux is not installed. Install it with: sudo apt install tmux")

    if not (repo_root / ".venv_inference" / "bin" / "activate").exists():
        errors.append("Missing .venv_inference. Run: bash install_scripts/install_inference.sh")

    if not (repo_root / ".venv_sim" / "bin" / "activate").exists():
        errors.append("Missing .venv_sim. Run: bash install_scripts/install_mujoco_sim.sh")

    if not (repo_root / "gear_sonic_deploy" / "deploy.sh").exists():
        errors.append("Missing gear_sonic_deploy/deploy.sh")

    replay_video = _resolve_from_repo(repo_root, config.replay_video_path)
    if not replay_video.exists():
        errors.append(f"Replay video not found: {replay_video}")

    model_path = _resolve_from_repo(repo_root, config.policy_model_path)
    if not model_path.exists():
        errors.append(f"Policy model path not found: {model_path}")

    if config.start_policy_server and not Path(config.policy_repo).expanduser().exists():
        errors.append(f"Isaac-GR00T repo not found: {config.policy_repo}")

    if config.start_policy_server and config.check_policy_backbone_access:
        try:
            from huggingface_hub import hf_hub_download

            try:
                hf_hub_download(
                    repo_id=config.policy_backbone_repo,
                    filename="config.json",
                    local_files_only=True,
                )
            except Exception:
                hf_hub_download(
                    repo_id=config.policy_backbone_repo,
                    filename="config.json",
                )
        except Exception as exc:
            errors.append(
                "Cannot access the gated backbone repo "
                f"{config.policy_backbone_repo}. Visit "
                f"https://huggingface.co/{config.policy_backbone_repo}, request access, "
                "then run `hf auth login` with an authorized token. "
                f"Original error: {exc}"
            )

    if errors:
        print("ERROR: prerequisites failed:\n")
        for error in errors:
            print(f"  - {error}")
        sys.exit(1)


def _commands(config: ReplaySimLaunchConfig, repo_root: Path) -> dict[str, str]:
    replay_video = _resolve_from_repo(repo_root, config.replay_video_path)
    model_path = _resolve_from_repo(repo_root, config.policy_model_path)
    policy_repo = Path(config.policy_repo).expanduser().resolve()

    if config.start_policy_server:
        policy_cmd = (
            f"cd {_quote(policy_repo)} && "
            "unset VIRTUAL_ENV && "
            "export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True && "
            "export NO_ALBUMENTATIONS_UPDATE=1 && "
            "uv run python gr00t/eval/run_gr00t_server.py "
            f"--model-path {_quote(model_path)} "
            "--embodiment-tag UNITREE_G1_SONIC "
            f"--device {_quote(config.policy_device)} "
            f"--port {config.policy_port}"
        )
    else:
        policy_cmd = (
            "printf '%s\\n' "
            f"{_quote('PolicyServer is expected at ' + config.policy_host + ':' + str(config.policy_port))}; "
            "printf '%s\\n' "
            f"{_quote('Start it separately, or relaunch without --no-start-policy-server.')}; "
            "bash"
        )

    sim_cmd = (
        f"cd {_quote(repo_root)} && "
        "source .venv_sim/bin/activate && "
        "python gear_sonic/scripts/run_sim_loop.py"
    )

    camera_cmd = (
        f"cd {_quote(repo_root)} && "
        "source .venv_inference/bin/activate && "
        "python gear_sonic/scripts/run_video_replay_camera.py "
        f"--video-path {_quote(replay_video)} "
        f"--port {config.camera_port} "
        f"--fps {config.camera_fps} "
        "--image-key ego_view"
    )

    deploy_cmd = (
        f"cd {_quote(repo_root / 'gear_sonic_deploy')} && "
        "export HAS_ROS2=0 && "
        "printf 'y\\n' | "
        "./deploy.sh --input-type zmq_manager --output-type zmq "
        f"--zmq-host {_quote(config.deploy_zmq_host)} sim"
    )

    inference_cmd = (
        f"cd {_quote(repo_root)} && "
        "source .venv_inference/bin/activate && "
        "python gear_sonic/scripts/run_vla_inference.py "
        f"--host {_quote(config.policy_host)} "
        f"--port {config.policy_port} "
        "--embodiment-tag unitree_g1_sonic "
        f"--prompt {_quote(config.prompt)} "
        "--camera-host localhost "
        f"--camera-port {config.camera_port} "
        f"--action-publish-rate {config.action_publish_rate} "
        f"--action-horizon {config.action_horizon} "
        f"--rate {config.inference_rate} "
        "--verbose-timing"
    )

    keyboard_cmd = (
        f"cd {_quote(repo_root)} && "
        "source .venv_inference/bin/activate && "
        "python gear_sonic/scripts/run_inference_keyboard.py"
    )

    return {
        "1_policy_server": policy_cmd,
        "2_mujoco_sim": sim_cmd,
        "3_replay_camera": camera_cmd,
        "4_cpp_deploy": deploy_cmd,
        "5_vla_inference": inference_cmd,
        "6_keyboard": keyboard_cmd,
    }


def _print_commands(commands: dict[str, str]) -> None:
    for name, command in commands.items():
        print(f"\n[{name}]")
        print(command)


def _launch_tmux(commands: dict[str, str], config: ReplaySimLaunchConfig) -> None:
    if config.kill_existing:
        _tmux("kill-session", "-t", SESSION_NAME, check=False, quiet=True)

    _tmux("new-session", "-d", "-s", SESSION_NAME, "-n", "core")
    _tmux("set-option", "-t", SESSION_NAME, "-g", "mouse", "on")
    _tmux("bind-key", "-T", "root", "C-\\", "kill-session")

    _tmux("split-window", "-t", f"{SESSION_NAME}:core", "-h")
    _tmux("split-window", "-t", f"{SESSION_NAME}:core.0", "-v")
    _tmux("split-window", "-t", f"{SESSION_NAME}:core.2", "-v")
    _tmux("select-layout", "-t", f"{SESSION_NAME}:core", "tiled")

    _tmux("new-window", "-t", SESSION_NAME, "-n", "policy")
    _tmux("new-window", "-t", SESSION_NAME, "-n", "sim")
    _tmux("select-window", "-t", f"{SESSION_NAME}:core")

    _send(f"{SESSION_NAME}:policy.0", commands["1_policy_server"])

    if config.start_policy_server and config.wait_policy_server:
        print(
            f"Waiting for PolicyServer on {config.policy_host}:{config.policy_port} "
            f"before starting deploy/sim..."
        )
        if not _wait_for_port(
            config.policy_host,
            config.policy_port,
            config.policy_startup_timeout_s,
        ):
            print(
                "\nPolicyServer did not become reachable before timeout. "
                "Check the 'policy' tmux window for CUDA OOM or model-load errors."
            )
            return
        print("PolicyServer is reachable; launching the rest of the stack.")
    else:
        time.sleep(1.0)

    _send(f"{SESSION_NAME}:sim.0", commands["2_mujoco_sim"])
    time.sleep(1.0)
    _send(f"{SESSION_NAME}:core.2", commands["3_replay_camera"])
    time.sleep(2.0)
    _send(f"{SESSION_NAME}:core.0", commands["4_cpp_deploy"])
    time.sleep(4.0)
    _send(f"{SESSION_NAME}:core.1", commands["5_vla_inference"])
    time.sleep(1.0)
    _send(f"{SESSION_NAME}:core.3", commands["6_keyboard"])

    _tmux("select-pane", "-t", f"{SESSION_NAME}:core.3")


def main(config: ReplaySimLaunchConfig) -> None:
    repo_root = _repo_root()
    _check_prerequisites(config, repo_root)
    commands = _commands(config, repo_root)

    print("=" * 72)
    print("SONIC VLA replay-video simulation launcher")
    print("=" * 72)
    print(f"tmux session: {SESSION_NAME}")
    print(f"prompt: {config.prompt}")
    print(f"policy server: {config.policy_host}:{config.policy_port}")
    print(f"replay camera: localhost:{config.camera_port}")
    print("ROS2: disabled for deploy (HAS_ROS2=0)")

    if config.dry_run:
        _print_commands(commands)
        return

    _launch_tmux(commands, config)

    print("\nStarted six tmux terminals:")
    print("  window policy: Isaac-GR00T PolicyServer")
    print("  window sim:    MuJoCo simulator")
    print("  core pane 0:   C++ deploy, auto-confirmed with y")
    print("  core pane 1:   VLA inference client")
    print("  core pane 2:   replay-video camera")
    print("  core pane 3:   keyboard publisher")
    print("\nWhen deploy shows 'Init Done' and inference is paused, type in the keyboard pane:")
    print("  k")
    print("  i")
    print("  p")
    print("\nNavigation: Ctrl+b then arrow keys or n/p. Kill all with Ctrl+\\.")

    if config.attach:
        subprocess.run(["tmux", "attach", "-t", SESSION_NAME])


def _signal_handler(_sig, _frame) -> None:
    print("\nShutdown requested.")
    _tmux("kill-session", "-t", SESSION_NAME, check=False, quiet=True)
    sys.exit(0)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, _signal_handler)
    main(tyro.cli(ReplaySimLaunchConfig))
