"""Bridge a GR00T composed-camera stream into PICO Remote Vision.

Run the normal camera server on the robot, set the PICO XRoboToolkit Remote
Vision source to PICO4U by default, then run this script on the host that can
reach both the camera server and the PICO headset.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import socket
import struct
import threading
import time
from typing import Any


VISION_SOURCE_PROFILES = {
    "pico4u": {
        "label": "PICO4U",
        "camera_type": "VR",
        "width": 2160,
        "height": 810,
        "fps": 30,
        "bitrate_bps": 20 * 1024 * 1024,
        "mono_to_stereo": True,
    },
    "zedmini": {
        "label": "ZEDMINI",
        "camera_type": "ZED",
        "width": 2560,
        "height": 720,
        "fps": 30,
        "bitrate_bps": 4_000_000,
        "mono_to_stereo": True,
    },
    "raw": {
        "label": "RAW",
        "camera_type": "RAW",
        "width": 1280,
        "height": 720,
        "fps": 30,
        "bitrate_bps": 4_000_000,
        "mono_to_stereo": False,
    },
}
ROTATION_CHOICES = ("none", "cw90", "ccw90", "180")
LAYOUT_CHOICES = ("single", "teleop_grid", "teleop_center_stack")
TELEOP_GRID_CAMERA_KEYS = ("ego_view", "left_wrist", "right_wrist")
TELEOP_MULTI_CAMERA_LAYOUTS = ("teleop_grid", "teleop_center_stack")


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

    vision_source: str = "pico4u"
    """XRoboToolkit source profile: pico4u for the large PICO4U view, zedmini for the ZEDMINI rectangle."""

    pico_command_host: str = "0.0.0.0"
    """Host/IP where the XRoboToolkit Remote Vision command server listens."""

    pico_command_port: int = 13579
    """XRoboToolkit Remote Vision command port."""

    command_server: bool = True
    """Run a small command server so the PICO can send OPEN_CAMERA/CLOSE_CAMERA."""

    width: int | None = None
    """Output stream width. Defaults come from --vision-source."""

    height: int | None = None
    """Output stream height. Defaults come from --vision-source."""

    bitrate_bps: int | None = None
    """H.264 bitrate in bits per second. Defaults come from --vision-source."""

    stretch: bool = False
    """If True, stretch source to width×height (distorts non-16:9). If False, letterbox."""

    fps: int | None = None
    """Output stream frame rate. Defaults come from --vision-source."""

    mono_to_stereo: bool | None = None
    """If True, duplicate the selected mono camera into left/right eye views."""

    rotate: str = "none"
    """Rotate ego_view before streaming: none, cw90, ccw90, or 180."""

    vision_y_offset: int = 0
    """Shift letterboxed PICO stream content downward by N pixels (default: 0)."""

    layout: str = "single"
    """Stream layout: single, teleop_grid, or teleop_center_stack (ego + both wrists)."""

    show_preview: bool = False
    """Show a local OpenCV preview window for debugging."""

    list_keys_only: bool = False
    """Print available camera keys from the first frame and exit."""

    startup_timeout_s: float = 10.0
    """How long to wait for the first camera message."""


@dataclass
class RemoteVisionRequest:
    """Camera request sent by the XRoboToolkit headset app."""

    width: int = 2160
    height: int = 810
    fps: int = 30
    bitrate_bps: int = 20 * 1024 * 1024
    enable_mv_hevc: int = 0
    render_mode: int = 2
    port: int = 12345
    camera: str = "VR"
    ip: str = "127.0.0.1"


def _resolve_stream_settings(config: StreamCameraToPicoConfig) -> dict[str, Any]:
    profile = VISION_SOURCE_PROFILES[config.vision_source]
    return {
        "label": profile["label"],
        "camera_type": profile["camera_type"],
        "width": config.width or profile["width"],
        "height": config.height or profile["height"],
        "fps": config.fps or profile["fps"],
        "bitrate_bps": config.bitrate_bps or profile["bitrate_bps"],
        "mono_to_stereo": (
            profile["mono_to_stereo"]
            if config.mono_to_stereo is None
            else config.mono_to_stereo
        ),
    }


def _parse_compact_string(data: bytes, offset: int) -> tuple[str, int]:
    if offset >= len(data):
        return "", offset
    length = data[offset]
    offset += 1
    value = data[offset : offset + length].decode("utf-8", errors="replace")
    return value, offset + length


def _parse_camera_request(data: bytes) -> RemoteVisionRequest:
    if len(data) < 31 or data[:2] != b"\xca\xfe" or data[2] != 1:
        raise ValueError("invalid camera request payload")

    values = struct.unpack_from("<7i", data, 3)
    camera, offset = _parse_compact_string(data, 31)
    ip, _ = _parse_compact_string(data, offset)

    return RemoteVisionRequest(
        width=values[0],
        height=values[1],
        fps=values[2],
        bitrate_bps=values[3],
        enable_mv_hevc=values[4],
        render_mode=values[5],
        port=values[6],
        camera=camera,
        ip=ip,
    )


def _parse_network_protocol(data: bytes) -> tuple[str, bytes]:
    if len(data) < 8:
        raise ValueError("protocol message too small")

    command_len = struct.unpack_from("<i", data, 0)[0]
    command_start = 4
    command_end = command_start + command_len
    data_len = struct.unpack_from("<i", data, command_end)[0]
    payload_start = command_end + 4
    payload_end = payload_start + data_len

    if command_len < 0 or data_len < 0 or payload_end > len(data):
        raise ValueError("invalid protocol lengths")

    command = data[command_start:command_end].decode("utf-8", errors="replace")
    return command, data[payload_start:payload_end]


def _unwrap_command_packet(packet: bytes) -> bytes:
    if len(packet) >= 4:
        body_len = struct.unpack(">I", packet[:4])[0]
        if body_len and 4 + body_len <= len(packet):
            return packet[4 : 4 + body_len]
    return packet


def _mono_stream_size(width: int, height: int, mono_to_stereo: bool) -> tuple[int, int]:
    if mono_to_stereo:
        return max(1, width // 2), height
    return width, height


def _build_preview_frame(
    frame_bgr: Any,
    width: int,
    height: int,
    mono_to_stereo: bool,
    stretch: bool,
    vision_y_offset: int = 0,
):
    import cv2

    from gear_sonic.camera.pico_video_streamer import letterbox_bgr, stereo_pair_bgr

    if mono_to_stereo:
        return stereo_pair_bgr(
            frame_bgr,
            width,
            height,
            letterbox=not stretch,
            y_offset=vision_y_offset,
        )
    if stretch:
        return cv2.resize(frame_bgr, (width, height))
    return letterbox_bgr(frame_bgr, width, height, y_offset=vision_y_offset)


def _build_stream_frame_rgb(
    message: dict,
    config: StreamCameraToPicoConfig,
    mono_w: int,
    mono_h: int,
):
    import cv2

    from gear_sonic.camera.pico_video_streamer import (
        compose_teleop_center_stack_bgr,
        compose_teleop_grid_bgr,
    )

    images = message["images"]
    if config.layout in TELEOP_MULTI_CAMERA_LAYOUTS:
        ego_rgb = images.get("ego_view")
        if ego_rgb is None:
            return None
        ego_rgb = _rotate_frame_rgb(ego_rgb, config.rotate)
        left_rgb = images.get("left_wrist")
        right_rgb = images.get("right_wrist")
        left_bgr = (
            cv2.cvtColor(left_rgb, cv2.COLOR_RGB2BGR) if left_rgb is not None else None
        )
        right_bgr = (
            cv2.cvtColor(right_rgb, cv2.COLOR_RGB2BGR) if right_rgb is not None else None
        )
        ego_bgr = cv2.cvtColor(ego_rgb, cv2.COLOR_RGB2BGR)
        compose_fn = (
            compose_teleop_center_stack_bgr
            if config.layout == "teleop_center_stack"
            else compose_teleop_grid_bgr
        )
        return compose_fn(
            ego_bgr,
            left_bgr,
            right_bgr,
            mono_w,
            mono_h,
            letterbox=not config.stretch,
            y_offset=config.vision_y_offset,
        )

    img_rgb = images.get(config.camera_key)
    if img_rgb is None:
        return None
    img_rgb = _rotate_frame_rgb(img_rgb, config.rotate)
    return cv2.cvtColor(img_rgb, cv2.COLOR_RGB2BGR)


def _rotate_frame_rgb(frame_rgb: Any, rotate: str) -> Any:
    if rotate == "none":
        return frame_rgb

    import cv2

    rotation_codes = {
        "cw90": cv2.ROTATE_90_CLOCKWISE,
        "ccw90": cv2.ROTATE_90_COUNTERCLOCKWISE,
        "180": cv2.ROTATE_180,
    }
    try:
        return cv2.rotate(frame_rgb, rotation_codes[rotate])
    except KeyError as exc:
        raise ValueError(f"Unsupported rotation: {rotate}") from exc


class RemoteVisionCommandServer:
    """Minimal XRoboToolkit command server for OPEN_CAMERA/CLOSE_CAMERA logging."""

    def __init__(
        self,
        host: str,
        port: int,
        stream_host: str,
        stream_port: int,
        source_label: str,
    ):
        self.host = host
        self.port = port
        self.stream_host = stream_host
        self.stream_port = stream_port
        self.source_label = source_label
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self):
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)
            self._thread = None

    def _run(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind((self.host, self.port))
            server.listen(1)
            server.settimeout(0.5)
            print(
                "[RemoteVisionCommandServer] listening on "
                f"{self.host}:{self.port} for {self.source_label}"
            )

            while not self._stop.is_set():
                try:
                    conn, addr = server.accept()
                except socket.timeout:
                    continue
                except OSError:
                    break

                print(f"[RemoteVisionCommandServer] PICO connected from {addr}")
                with conn:
                    conn.settimeout(0.5)
                    buffer = b""
                    while not self._stop.is_set():
                        try:
                            chunk = conn.recv(65536)
                        except socket.timeout:
                            continue
                        except OSError:
                            break
                        if not chunk:
                            break
                        buffer += chunk

                        while buffer:
                            if len(buffer) < 4:
                                break
                            body_len = struct.unpack(">I", buffer[:4])[0]
                            if not (0 < body_len <= 16 * 1024 * 1024):
                                buffer = b""
                                break
                            if len(buffer) < 4 + body_len:
                                break
                            packet = buffer[: 4 + body_len]
                            buffer = buffer[4 + body_len :]

                            try:
                                command, payload = _parse_network_protocol(
                                    _unwrap_command_packet(packet)
                                )
                            except Exception as exc:
                                print(
                                    "[RemoteVisionCommandServer] could not parse "
                                    f"packet: {exc}"
                                )
                                continue

                            if command == "OPEN_CAMERA":
                                try:
                                    request = _parse_camera_request(payload)
                                    print(
                                        "[RemoteVisionCommandServer] OPEN_CAMERA "
                                        f"{request.camera} "
                                        f"{request.width}x{request.height}@{request.fps} "
                                        f"requested {request.ip}:{request.port}; "
                                        f"streaming via {self.stream_host}:{self.stream_port}"
                                    )
                                except Exception as exc:
                                    print(
                                        "[RemoteVisionCommandServer] invalid "
                                        f"OPEN_CAMERA payload: {exc}"
                                    )
                            elif command == "CLOSE_CAMERA":
                                print("[RemoteVisionCommandServer] CLOSE_CAMERA")
                            else:
                                print(
                                    "[RemoteVisionCommandServer] ignoring "
                                    f"{command!r}"
                                )

                print("[RemoteVisionCommandServer] PICO disconnected")


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
    )

    stream_settings = _resolve_stream_settings(config)
    width = stream_settings["width"]
    height = stream_settings["height"]
    fps = stream_settings["fps"]
    bitrate_kbps = max(1, int(round(stream_settings["bitrate_bps"] / 1000)))
    mono_to_stereo = stream_settings["mono_to_stereo"]

    client = ComposedCameraClientSensor(server_ip=config.camera_host, port=config.camera_port)
    streamer = PicoVideoStreamer(
        PicoVideoStreamerConfig(
            pico_ip=config.pico_ip,
            pico_port=config.pico_port,
            width=width,
            height=height,
            fps=fps,
            bitrate_kbps=bitrate_kbps,
            letterbox=not config.stretch,
            letterbox_y_offset=config.vision_y_offset,
            mono_to_stereo=mono_to_stereo,
        )
    )
    command_server = None
    if config.command_server:
        command_server = RemoteVisionCommandServer(
            config.pico_command_host,
            config.pico_command_port,
            config.pico_ip,
            config.pico_port,
            stream_settings["label"],
        )

    try:
        if command_server is not None:
            command_server.start()

        first_message = _wait_for_first_frame(client, config.startup_timeout_s)
        available_keys = sorted(first_message["images"].keys())
        print(f"Available camera keys: {available_keys}")

        if config.list_keys_only:
            return

        if config.layout in TELEOP_MULTI_CAMERA_LAYOUTS:
            missing_keys = [
                key
                for key in TELEOP_GRID_CAMERA_KEYS
                if key not in first_message["images"]
            ]
            if missing_keys:
                raise KeyError(
                    f"{config.layout} layout requires ego_view, left_wrist, and "
                    f"right_wrist. Missing: {missing_keys}. "
                    f"Available keys: {available_keys}"
                )
        elif config.camera_key not in first_message["images"]:
            raise KeyError(
                f"Camera key '{config.camera_key}' was not found. "
                f"Available keys: {available_keys}"
            )

        mono_w, mono_h = _mono_stream_size(width, height, mono_to_stereo)

        print(
            "Open PICO XRoboToolkit Remote Vision, select "
            f"{stream_settings['label']}, press Listen, use camera/source IP "
            "127.0.0.1 for USB, then keep this process running."
        )
        layout_desc = {
            "teleop_grid": "teleop_grid(ego_view+left_wrist+right_wrist)",
            "teleop_center_stack": "teleop_center_stack(ego above wrists)",
        }.get(config.layout, config.camera_key)
        print(
            "[stream_camera_to_pico] output "
            f"{width}x{height}@{fps} bitrate={bitrate_kbps}kbps "
            f"mono_to_stereo={mono_to_stereo} layout={layout_desc} "
            f"rotate={config.rotate} y_offset={config.vision_y_offset}"
        )
        streamer.start()

        frame_period = 1.0 / fps
        frame_count = 0
        last_report = time.monotonic()

        while True:
            t0 = time.monotonic()
            message = client.read(blocking=False)
            if message and message.get("images"):
                frame_bgr = _build_stream_frame_rgb(message, config, mono_w, mono_h)
                if frame_bgr is not None:
                    streamer.submit_frame_bgr(frame_bgr)
                    frame_count += 1

                    if config.show_preview:
                        preview = _build_preview_frame(
                            frame_bgr,
                            width,
                            height,
                            mono_to_stereo,
                            config.stretch,
                            config.vision_y_offset,
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
        if command_server is not None:
            command_server.stop()
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
    parser.add_argument(
        "--vision-source",
        choices=sorted(VISION_SOURCE_PROFILES),
        default="pico4u",
        help="XRoboToolkit Remote Vision profile. Default pico4u uses the large PICO4U view.",
    )
    parser.add_argument("--pico-command-host", default="0.0.0.0")
    parser.add_argument("--pico-command-port", type=int, default=13579)
    parser.add_argument(
        "--no-command-server",
        dest="command_server",
        action="store_false",
        help="Do not listen for XRoboToolkit OPEN_CAMERA/CLOSE_CAMERA commands.",
    )
    parser.add_argument("--width", type=int, default=None)
    parser.add_argument("--height", type=int, default=None)
    parser.add_argument("--fps", type=int, default=None)
    parser.add_argument("--bitrate-bps", type=int, default=None)
    parser.add_argument(
        "--mono-to-stereo",
        dest="mono_to_stereo",
        action="store_true",
        default=None,
        help="Duplicate one mono camera into side-by-side left/right eye views.",
    )
    parser.add_argument(
        "--no-mono-to-stereo",
        dest="mono_to_stereo",
        action="store_false",
        help="Send the selected camera as a single mono frame.",
    )
    parser.add_argument(
        "--layout",
        choices=LAYOUT_CHOICES,
        default="single",
        help=(
            "Stream layout. single uses --camera-key only; teleop_grid uses a 3x3 "
            "grid; teleop_center_stack places ego above left/right wrist cameras "
            "as a centered block."
        ),
    )
    parser.add_argument(
        "--rotate",
        choices=ROTATION_CHOICES,
        default="none",
        help="Rotate ego_view before streaming to PICO (ignored for wrist cameras).",
    )
    parser.add_argument(
        "--vision-y-offset",
        type=int,
        default=0,
        help=(
            "Shift letterboxed PICO stream content downward by N pixels. "
            "Ignored when --stretch is set. Does not affect recorded dataset images."
        ),
    )
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
