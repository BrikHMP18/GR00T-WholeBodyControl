#!/usr/bin/env bash
# Install system packages needed to stream GR00T camera video to PICO Remote Vision.
#
# Run on the host that executes:
#   python -m gear_sonic.scripts.stream_camera_to_pico ...

set -euo pipefail

if ! command -v apt-get >/dev/null 2>&1; then
    echo "[ERROR] This helper currently supports apt-based Ubuntu/Debian systems."
    echo "        Install Python GObject bindings and GStreamer H.264 plugins manually."
    exit 1
fi

echo "[INFO] Installing GStreamer Python bindings and H.264 plugins..."
sudo apt-get update
sudo apt-get install -y \
    python3-gi \
    gir1.2-gstreamer-1.0 \
    gstreamer1.0-tools \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-bad \
    gstreamer1.0-plugins-ugly

echo "[OK] PICO vision system dependencies installed."
echo ""
echo "Next:"
echo "  1. Start the GR00T camera server."
echo "  2. In PICO XRoboToolkit Remote Vision, select ZEDMINI and press Listen."
echo "  3. Run python -m gear_sonic.scripts.stream_camera_to_pico --pico-ip <PICO_IP>"
