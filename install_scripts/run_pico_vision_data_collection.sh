#!/usr/bin/env bash
# First-run helper for SONIC data collection with PICO Remote Vision.
#
# This script:
#   1. switches to the PICO_VISION_UNITREE branch,
#   2. optionally installs system GStreamer/H.264 dependencies,
#   3. launches launch_data_collection.py with PICO vision enabled.
#
# Example:
#   bash install_scripts/run_pico_vision_data_collection.sh \
#     --pico-ip 192.168.0.128 \
#     --camera-host 192.168.123.164

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

BRANCH="PICO_VISION_UNITREE"
PICO_IP="192.168.0.128"
CAMERA_HOST="192.168.123.164"
CAMERA_PORT="5555"
CAMERA_KEY="ego_view"
INSTALL_DEPS=1

usage() {
    cat <<USAGE
Usage:
  bash install_scripts/run_pico_vision_data_collection.sh [options]

Options:
  --pico-ip IP          PICO headset IP for Remote Vision (default: ${PICO_IP})
  --camera-host IP      Host/IP running composed_camera server (default: ${CAMERA_HOST})
  --camera-port PORT    Camera server ZMQ port (default: ${CAMERA_PORT})
  --camera-key KEY      Camera stream key to send to PICO (default: ${CAMERA_KEY})
  --skip-install-deps   Do not run install_pico_vision_deps.sh
  -h, --help            Show this help

Before running:
  - On the Unitree/robot PC, start the camera server on --camera-port.
  - In PICO XRoboToolkit, Remote Vision -> ZEDMINI -> Listen.
USAGE
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --pico-ip)
            PICO_IP="$2"
            shift 2
            ;;
        --camera-host)
            CAMERA_HOST="$2"
            shift 2
            ;;
        --camera-port)
            CAMERA_PORT="$2"
            shift 2
            ;;
        --camera-key)
            CAMERA_KEY="$2"
            shift 2
            ;;
        --skip-install-deps)
            INSTALL_DEPS=0
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "[ERROR] Unknown argument: $1"
            usage
            exit 1
            ;;
    esac
done

cd "$REPO_ROOT"

echo "============================================================"
echo "  PICO Vision Data Collection Launcher"
echo "============================================================"
echo "  Repo:        $REPO_ROOT"
echo "  Branch:      $BRANCH"
echo "  PICO IP:     $PICO_IP"
echo "  Camera:      ${CAMERA_HOST}:${CAMERA_PORT}"
echo "  Camera key:  $CAMERA_KEY"
echo "============================================================"

if ! git diff --quiet || ! git diff --cached --quiet; then
    echo "[ERROR] Working tree has uncommitted changes."
    echo "        Commit, stash, or discard them before switching branches."
    git status --short
    exit 1
fi

git switch "$BRANCH"

if [[ "$INSTALL_DEPS" -eq 1 ]]; then
    bash install_scripts/install_pico_vision_deps.sh
else
    echo "[SKIP] Not installing PICO vision system dependencies."
fi

python gear_sonic/scripts/launch_data_collection.py \
    --pico-vision \
    --pico-ip "$PICO_IP" \
    --camera-host "$CAMERA_HOST" \
    --camera-port "$CAMERA_PORT" \
    --pico-vision-camera-key "$CAMERA_KEY"
