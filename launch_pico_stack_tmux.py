#!/usr/bin/env python3
"""Launch the full GR00T PICO teleop stack in a tmux session (3 panes).

Usage:
    python launch_pico_stack_tmux.py          # default env, with VR visualizer
    python launch_pico_stack_tmux.py --no-vis # headless / onboard practice

Kill the session:
    tmux kill-session -t g1-pico
"""
from __future__ import annotations

import argparse
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DEFAULT_SESSION = os.environ.get("TMUX_PICO_SESSION", "g1-pico")


def run_tmux(*args: str) -> None:
    subprocess.run(["tmux", *args], check=True)


def send(target: str, cmd: str) -> None:
    run_tmux("send-keys", "-t", target, cmd, "C-m")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--session", default=DEFAULT_SESSION, help="tmux session name (default: g1-pico)")
    parser.add_argument("--env-name", default="wbcd_logistics_picking", help="MuJoCo env for run_sim_loop.py")
    parser.add_argument("--venv", default=".venv_teleop", help="Python virtualenv path")
    parser.add_argument("--deploy-delay", type=float, default=6.0, help="Seconds before starting deploy (default: 6)")
    parser.add_argument("--no-vis", action="store_true", help="Skip --vis_vr3pt / --vis_smpl visualizers")
    parser.add_argument("--no-attach", action="store_true", help="Create session but do not attach")
    args = parser.parse_args()

    if not shutil.which("tmux"):
        sys.exit("ERROR: tmux not found. Install it with: sudo apt install tmux")

    if subprocess.run(["tmux", "has-session", "-t", args.session], capture_output=True).returncode == 0:
        sys.exit(
            f"ERROR: tmux session '{args.session}' already exists.\n"
            f"  Kill it with:  tmux kill-session -t {args.session}"
        )

    venv = shlex.quote(str(ROOT / args.venv))
    root = shlex.quote(str(ROOT))
    deploy_dir = shlex.quote(str(ROOT / "gear_sonic_deploy"))

    activate = f"source {venv}/bin/activate"

    cmd_sim = f"cd {root} && {activate} && python gear_sonic/scripts/run_sim_loop.py --env-name {shlex.quote(args.env_name)}"

    # printf '\n' auto-answers the [Y/n] confirmation prompt in deploy.sh
    cmd_deploy = (
        f"sleep {args.deploy_delay:g} && "
        f"cd {deploy_dir} && "
        "source scripts/setup_env.sh && "
        "printf '\\n' | ./deploy.sh --input-type zmq_manager sim"
    )

    vis_flags = "" if args.no_vis else " --vis_vr3pt --vis_smpl"
    cmd_pico = (
        f"cd {root} && {activate} && "
        f"python gear_sonic/scripts/pico_manager_thread_server.py --manager{vis_flags}"
    )

    # Create session with 3 panes: left=sim, right-top=deploy, right-bottom=pico
    run_tmux("new-session", "-d", "-s", args.session, "-n", "stack")
    run_tmux("split-window", "-t", f"{args.session}:0.0", "-h")
    run_tmux("split-window", "-t", f"{args.session}:0.1", "-v")
    run_tmux("set-window-option", "-t", f"{args.session}:0", "pane-border-status", "top")
    run_tmux("select-pane", "-t", f"{args.session}:0.0", "-T", "1 · sim")
    run_tmux("select-pane", "-t", f"{args.session}:0.1", "-T", "2 · deploy")
    run_tmux("select-pane", "-t", f"{args.session}:0.2", "-T", "3 · pico")

    send(f"{args.session}:0.0", f"bash -lc {shlex.quote(cmd_sim)}")
    send(f"{args.session}:0.1", f"bash -lc {shlex.quote(cmd_deploy)}")
    send(f"{args.session}:0.2", f"bash -lc {shlex.quote(cmd_pico)}")

    run_tmux("select-pane", "-t", f"{args.session}:0.0")

    if not args.no_attach:
        os.execvp("tmux", ["tmux", "attach", "-t", args.session])


if __name__ == "__main__":
    main()
