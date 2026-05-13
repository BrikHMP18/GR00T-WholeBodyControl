"""Bridge a GR00T composed-camera stream into PICO Remote Vision.

Run the normal camera server on the robot, set the PICO XRoboToolkit Remote
Vision session to listen as ZEDMINI, then run this script on the host that can
reach both the camera server and the PICO headset.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import time
from typing import Any


@dataclass
class StreamCameraToPicoConfig:
    """CLI options for streaming a composed camera feed to PICO."""

    camera_host: str = "localhost"
    """Host/IP running gear_sonic.camera.composed_camera."""

    camera_port: int = 5555
    """ZMQ PUB port for the composed camera server."""

    camera_key: str = "ego_view"
    """Image key to stream to PICO, usually ego_view."""

    pico_ip: str = "192.168.0.128"
    """PICO headset IP address."""

    pico_port: int = 12345
    """PICO Remote Vision TCP port used by XRoboToolkit."""

    width: int = 1280
    """Output stream width expected by the PICO Remote Vision app."""

    height: int = 720
    """Output stream height expected by the PICO Remote Vision app."""

    stretch: bool = False
    """If True, stretch source to width×height (distorts non-16:9). If False, letterbox."""

    fps: int = 30
    """Output stream frame rate."""

    show_preview: bool = False
    """Show a local OpenCV preview window for debugging."""

    list_keys_only: bool = False
    """Print available camera keys from the first frame and exit."""

    startup_timeout_s: float = 10.0
    """How long to wait for the first camera message."""


def _wait_for_first_frame(
    client: Any,
    timeout_s: float,
) -> dict:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        message = client.read(blocking=False)
        if message and message.get("images"):
            return message
        time.sleep(0.05)
    raise TimeoutError(
        "No camera frames received. Check --camera-host, --camera-port, "
        "and that gear_sonic.camera.composed_camera is running."
    )


def main(config: StreamCameraToPicoConfig):
    import cv2

    from gear_sonic.camera.composed_camera import ComposedCameraClientSensor
    from gear_sonic.camera.pico_video_streamer import (
        PicoVideoStreamer,
        PicoVideoStreamerConfig,
        letterbox_bgr,
    )

    client = ComposedCameraClientSensor(server_ip=config.camera_host, port=config.camera_port)
    streamer = PicoVideoStreamer(
        PicoVideoStreamerConfig(
            pico_ip=config.pico_ip,
            pico_port=config.pico_port,
            width=config.width,
            height=config.height,
            fps=config.fps,
            letterbox=not config.stretch,
        )
    )

    try:
        first_message = _wait_for_first_frame(client, config.startup_timeout_s)
        available_keys = sorted(first_message["images"].keys())
        print(f"Available camera keys: {available_keys}")

        if config.list_keys_only:
            return

        if config.camera_key not in first_message["images"]:
            raise KeyError(
                f"Camera key '{config.camera_key}' was not found. "
                f"Available keys: {available_keys}"
            )

        print(
            "Open PICO XRoboToolkit Remote Vision, select ZEDMINI, "
            "press Listen, then keep this process running."
        )
        streamer.start()

        frame_period = 1.0 / config.fps
        frame_count = 0
        last_report = time.monotonic()

        while True:
            t0 = time.monotonic()
            message = client.read(blocking=False)
            if message and message.get("images"):
                img_rgb = message["images"].get(config.camera_key)
                if img_rgb is not None:
                    streamer.submit_frame_rgb(img_rgb)
                    frame_count += 1

                    if config.show_preview:
                        img_bgr = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2BGR)
                        if config.stretch:
                            preview = cv2.resize(
                                img_bgr, (config.width, config.height)
                            )
                        else:
                            preview = letterbox_bgr(
                                img_bgr, config.width, config.height
                            )
                        cv2.imshow("PICO camera stream preview", preview)
                        if cv2.waitKey(1) & 0xFF == ord("q"):
                            break

            now = time.monotonic()
            if now - last_report >= 5.0:
                print(f"[stream_camera_to_pico] submitted {frame_count} frames")
                last_report = now

            elapsed = time.monotonic() - t0
            if elapsed < frame_period:
                time.sleep(frame_period - elapsed)

    except KeyboardInterrupt:
        print("Stopping PICO camera stream...")
    finally:
        streamer.stop()
        client.close()
        if config.show_preview:
            cv2.destroyAllWindows()


def parse_args() -> StreamCameraToPicoConfig:
    parser = argparse.ArgumentParser(
        description="Stream a GR00T composed-camera feed into PICO Remote Vision."
    )
    parser.add_argument("--camera-host", default="localhost")
    parser.add_argument("--camera-port", type=int, default=5555)
    parser.add_argument("--camera-key", default="ego_view")
    parser.add_argument("--pico-ip", default="192.168.0.128")
    parser.add_argument("--pico-port", type=int, default=12345)
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument(
        "--stretch",
        action="store_true",
        help="Stretch to output size (distorts). Default: letterbox to preserve aspect.",
    )
    parser.add_argument("--show-preview", action="store_true")
    parser.add_argument("--list-keys-only", action="store_true")
    parser.add_argument("--startup-timeout-s", type=float, default=10.0)
    return StreamCameraToPicoConfig(**vars(parser.parse_args()))


if __name__ == "__main__":
    main(parse_args())
