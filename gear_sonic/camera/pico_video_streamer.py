"""Low-latency H.264 video streaming to PICO Remote Vision.

The PICO XRoboToolkit Unity client's Remote Vision mode listens for a TCP
connection and accepts length-prefixed H.264 byte-stream access units.  This
module mirrors the proven Psi0 flow while keeping video transport independent
from PICO pose/control tracking.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
import socket
import struct
import sys
import threading
import time

import cv2
import numpy as np


def letterbox_bgr(
    img_bgr: np.ndarray,
    out_w: int,
    out_h: int,
    fill: tuple[int, int, int] = (0, 0, 0),
    y_offset: int = 0,
) -> np.ndarray:
    """Scale image to fit inside (out_w, out_h) preserving aspect ratio; pad with ``fill``.

    ``y_offset`` shifts the scaled image downward by N pixels (letterbox only).
    """
    h, w = img_bgr.shape[:2]
    if w == out_w and h == out_h and y_offset == 0:
        return img_bgr
    scale = min(out_w / w, out_h / h)
    nw = max(1, int(round(w * scale)))
    nh = max(1, int(round(h * scale)))
    resized = cv2.resize(img_bgr, (nw, nh), interpolation=cv2.INTER_LINEAR)
    canvas = np.full((out_h, out_w, 3), fill, dtype=np.uint8)
    x0 = (out_w - nw) // 2
    y0 = (out_h - nh) // 2 + y_offset
    y0 = max(0, min(y0, out_h - nh))
    canvas[y0 : y0 + nh, x0 : x0 + nw] = resized
    return np.ascontiguousarray(canvas)


def _panel_bgr(
    img_bgr: np.ndarray | None,
    panel_w: int,
    panel_h: int,
    letterbox: bool,
    y_offset: int,
) -> np.ndarray:
    """Render one camera into a fixed-size BGR panel."""
    if img_bgr is None:
        return np.zeros((panel_h, panel_w, 3), dtype=np.uint8)
    if letterbox:
        return letterbox_bgr(img_bgr, panel_w, panel_h, y_offset=y_offset)
    return cv2.resize(img_bgr, (panel_w, panel_h), interpolation=cv2.INTER_LINEAR)


def _teleop_stack_geometry(out_w: int, out_h: int) -> dict[str, int]:
    """Panel sizes shared by teleop_grid and teleop_center_stack."""
    cell_w = max(1, out_w // 3)
    cell_h = max(1, out_h // 3)
    center_w = max(1, out_w - 2 * cell_w)
    return {
        "cell_w": cell_w,
        "cell_h": cell_h,
        "center_w": center_w,
        "ego_h": out_h - cell_h,
        "wrist_h": cell_h,
        "wrist_row_w": 2 * cell_w,
    }


def compose_teleop_center_stack_bgr(
    ego_bgr: np.ndarray | None,
    left_wrist_bgr: np.ndarray | None,
    right_wrist_bgr: np.ndarray | None,
    out_w: int,
    out_h: int,
    letterbox: bool = True,
    y_offset: int = 0,
) -> np.ndarray:
    """Compose ego above left/right wrist cameras, centered as one block.

    Layout (ego column width matches ``teleop_grid``; wrists use full ``cell_w`` each):

        [dark] [      ego (center_w × ego_h)      ] [dark]
           [dark] [ L (cell_w) ] [ R (cell_w) ] [dark]

    Wrist panels are the same size as in ``teleop_grid`` and sit on a wider row
    centered under the ego (they may extend slightly past the ego column).
    """
    canvas = np.zeros((out_h, out_w, 3), dtype=np.uint8)
    geom = _teleop_stack_geometry(out_w, out_h)
    cell_w = geom["cell_w"]
    center_w = geom["center_w"]
    ego_h = geom["ego_h"]
    wrist_h = geom["wrist_h"]
    wrist_row_w = geom["wrist_row_w"]

    block_h = ego_h + wrist_h
    ego_start_x = (out_w - center_w) // 2
    wrist_start_x = (out_w - wrist_row_w) // 2
    start_y = max(0, (out_h - block_h) // 2)
    wrist_y = start_y + ego_h

    ego_panel = _panel_bgr(ego_bgr, center_w, ego_h, letterbox, y_offset)
    canvas[start_y : start_y + ego_h, ego_start_x : ego_start_x + center_w] = ego_panel

    left_panel = _panel_bgr(left_wrist_bgr, cell_w, wrist_h, letterbox, y_offset)
    canvas[wrist_y : wrist_y + wrist_h, wrist_start_x : wrist_start_x + cell_w] = (
        left_panel
    )

    right_panel = _panel_bgr(right_wrist_bgr, cell_w, wrist_h, letterbox, y_offset)
    canvas[
        wrist_y : wrist_y + wrist_h,
        wrist_start_x + cell_w : wrist_start_x + wrist_row_w,
    ] = right_panel

    return np.ascontiguousarray(canvas)


def compose_teleop_grid_bgr(
    ego_bgr: np.ndarray | None,
    left_wrist_bgr: np.ndarray | None,
    right_wrist_bgr: np.ndarray | None,
    out_w: int,
    out_h: int,
    letterbox: bool = True,
    y_offset: int = 0,
) -> np.ndarray:
    """Compose ego + wrist cameras into a 3x3 teleop grid.

    Layout (1-indexed):

        [dark] [ego ] [dark]
        [left] [ego ] [right]
        [dark] [ego ] [dark]

    The center column shows a single ego-view panel spanning the full height.
    Corner cells stay black. Only the middle-row side cells show wrist cameras.
    """
    canvas = np.zeros((out_h, out_w, 3), dtype=np.uint8)
    geom = _teleop_stack_geometry(out_w, out_h)
    cell_w = geom["cell_w"]
    cell_h = geom["cell_h"]
    center_w = geom["center_w"]
    center_x = cell_w

    if ego_bgr is not None:
        ego_panel = _panel_bgr(ego_bgr, center_w, out_h, letterbox, y_offset)
        canvas[:, center_x : center_x + center_w] = ego_panel

    row_y = cell_h
    if left_wrist_bgr is not None:
        left_panel = _panel_bgr(left_wrist_bgr, cell_w, cell_h, letterbox, y_offset)
        canvas[row_y : row_y + cell_h, 0:cell_w] = left_panel

    if right_wrist_bgr is not None:
        right_panel = _panel_bgr(right_wrist_bgr, cell_w, cell_h, letterbox, y_offset)
        canvas[row_y : row_y + cell_h, out_w - cell_w : out_w] = right_panel

    return np.ascontiguousarray(canvas)


def stereo_pair_bgr(
    img_bgr: np.ndarray,
    out_w: int,
    out_h: int,
    letterbox: bool = True,
    y_offset: int = 0,
) -> np.ndarray:
    """Duplicate a mono BGR frame into side-by-side left/right eye views."""
    left_w = max(1, out_w // 2)
    right_w = max(1, out_w - left_w)

    if letterbox:
        left = letterbox_bgr(img_bgr, left_w, out_h, y_offset=y_offset)
        right = letterbox_bgr(img_bgr, right_w, out_h, y_offset=y_offset)
    else:
        left = cv2.resize(img_bgr, (left_w, out_h), interpolation=cv2.INTER_LINEAR)
        right = cv2.resize(img_bgr, (right_w, out_h), interpolation=cv2.INTER_LINEAR)

    return np.ascontiguousarray(np.concatenate([left, right], axis=1))


@dataclass
class PicoVideoStreamerConfig:
    """Configuration for the PICO H.264 stream."""

    pico_ip: str
    pico_port: int = 12345
    width: int = 1280
    height: int = 720
    fps: int = 30
    bitrate_kbps: int = 4000
    reconnect_interval_s: float = 1.0
    connect_timeout_s: float = 2.0
    letterbox: bool = True
    """If True, preserve source aspect ratio inside width×height (black bars). If False, stretch."""
    letterbox_y_offset: int = 0
    """Shift letterboxed content downward by N pixels (PICO stream only)."""
    mono_to_stereo: bool = False
    """If True, duplicate each mono source frame into side-by-side left/right eye views."""


class PicoVideoStreamer:
    """Encode BGR frames as H.264 and send them to PICO over TCP."""

    def __init__(self, config: PicoVideoStreamerConfig):
        self.config = config
        self._running = False
        self._connected = False
        self._sock: socket.socket | None = None
        self._Gst = None
        self._pipeline = None
        self._appsrc = None
        self._frame_id = 0
        self._latest_frame_bgr: np.ndarray | None = None
        self._lock = threading.Lock()
        self._connection_thread: threading.Thread | None = None
        self._push_thread: threading.Thread | None = None

    def start(self):
        """Start the encoder and background TCP connection loops."""
        if self._running:
            return

        self._Gst = self._import_gstreamer()
        self._Gst.init(None)

        self._running = True
        self._start_pipeline()
        self._connection_thread = threading.Thread(target=self._connection_loop, daemon=True)
        self._push_thread = threading.Thread(target=self._push_loop, daemon=True)
        self._connection_thread.start()
        self._push_thread.start()

        print(
            "[PicoVideoStreamer] started "
            f"target={self.config.pico_ip}:{self.config.pico_port} "
            f"{self.config.width}x{self.config.height}@{self.config.fps} "
            f"bitrate={self.config.bitrate_kbps}kbps "
            f"mono_to_stereo={self.config.mono_to_stereo}"
        )

    def submit_frame_bgr(self, frame_bgr: np.ndarray):
        """Submit the latest BGR frame for encoding.

        The streamer keeps only the newest frame to avoid latency buildup.
        """
        if frame_bgr is None:
            return
        with self._lock:
            self._latest_frame_bgr = np.ascontiguousarray(frame_bgr.copy())

    def submit_frame_rgb(self, frame_rgb: np.ndarray):
        """Submit an RGB frame, converting to BGR for the GStreamer pipeline."""
        if frame_rgb is None:
            return
        self.submit_frame_bgr(cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR))

    def stop(self):
        """Stop background loops, close the socket, and tear down GStreamer."""
        self._running = False
        self._connected = False

        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None

        if self._connection_thread is not None:
            self._connection_thread.join(timeout=2.0)
            self._connection_thread = None
        if self._push_thread is not None:
            self._push_thread.join(timeout=2.0)
            self._push_thread = None

        if self._pipeline is not None:
            try:
                self._pipeline.set_state(self._Gst.State.NULL)
            finally:
                self._pipeline = None
                self._appsrc = None
                self._Gst = None

    def _connection_loop(self):
        while self._running:
            if not self._connected:
                self._close_socket()
                try:
                    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    s.settimeout(self.config.connect_timeout_s)
                    s.connect((self.config.pico_ip, self.config.pico_port))
                    s.settimeout(None)
                    self._sock = s
                    self._connected = True
                    print(
                        "[PicoVideoStreamer] connected to "
                        f"{self.config.pico_ip}:{self.config.pico_port}"
                    )
                except OSError:
                    self._close_socket()

            time.sleep(self.config.reconnect_interval_s)

    def _start_pipeline(self):
        pipe_str = (
            "appsrc name=src is-live=True format=time ! "
            f"video/x-raw,format=BGR,width={self.config.width},height={self.config.height},"
            f"framerate={self.config.fps}/1 ! "
            "videoconvert ! "
            "x264enc tune=zerolatency speed-preset=ultrafast "
            f"key-int-max=15 bitrate={self.config.bitrate_kbps} ! "
            "video/x-h264,profile=baseline ! "
            "h264parse config-interval=-1 ! "
            "video/x-h264,stream-format=byte-stream,alignment=au ! "
            "appsink name=sink emit-signals=True sync=False"
        )
        self._pipeline = self._Gst.parse_launch(pipe_str)
        self._appsrc = self._pipeline.get_by_name("src")
        appsink = self._pipeline.get_by_name("sink")
        appsink.connect("new-sample", self._on_encoded_frame)
        self._pipeline.set_state(self._Gst.State.PLAYING)

    def _on_encoded_frame(self, sink):
        sample = sink.emit("pull-sample")
        if sample is None:
            return self._Gst.FlowReturn.OK

        buf = sample.get_buffer()
        ok, info = buf.map(self._Gst.MapFlags.READ)
        if not ok:
            return self._Gst.FlowReturn.OK

        try:
            if self._connected and self._sock is not None:
                payload = bytes(info.data)
                header = struct.pack(">I", len(payload))
                self._sock.sendall(header + payload)
        except OSError:
            self._connected = False
            self._close_socket()
            print("[PicoVideoStreamer] connection lost, retrying...")
        finally:
            buf.unmap(info)

        return self._Gst.FlowReturn.OK

    def _push_loop(self):
        frame_period = 1.0 / self.config.fps
        while self._running:
            t0 = time.monotonic()

            frame = None
            with self._lock:
                if self._latest_frame_bgr is not None:
                    frame = self._latest_frame_bgr
                    self._latest_frame_bgr = None

            if frame is not None and self._appsrc is not None:
                if self.config.mono_to_stereo:
                    frame = stereo_pair_bgr(
                        frame,
                        self.config.width,
                        self.config.height,
                        letterbox=self.config.letterbox,
                        y_offset=self.config.letterbox_y_offset,
                    )
                elif frame.shape[1] != self.config.width or frame.shape[0] != self.config.height:
                    if self.config.letterbox:
                        frame = letterbox_bgr(
                            frame,
                            self.config.width,
                            self.config.height,
                            y_offset=self.config.letterbox_y_offset,
                        )
                    else:
                        frame = cv2.resize(
                            frame,
                            (self.config.width, self.config.height),
                            interpolation=cv2.INTER_LINEAR,
                        )

                frame = np.ascontiguousarray(frame)
                gst_buf = self._Gst.Buffer.new_wrapped(frame.tobytes())
                gst_buf.pts = self._frame_id * (self._Gst.SECOND // self.config.fps)
                gst_buf.duration = self._Gst.SECOND // self.config.fps
                self._appsrc.emit("push-buffer", gst_buf)
                self._frame_id += 1

            elapsed = time.monotonic() - t0
            if elapsed < frame_period:
                time.sleep(frame_period - elapsed)

    def _close_socket(self):
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None
        self._connected = False

    @staticmethod
    def _ensure_system_gi_path() -> None:
        """Let venv Python load system PyGObject/GStreamer bindings."""
        candidates = [
            "/usr/lib/python3/dist-packages",
            f"/usr/lib/python3.{sys.version_info.minor}/site-packages",
        ]
        for path in candidates:
            if os.path.isdir(path) and path not in sys.path:
                sys.path.insert(0, path)

    @staticmethod
    def _import_gstreamer():
        PicoVideoStreamer._ensure_system_gi_path()
        try:
            import gi

            gi.require_version("Gst", "1.0")
            from gi.repository import Gst
        except (ImportError, ValueError) as exc:
            raise ImportError(
                "GStreamer Python bindings are required for PICO video streaming. "
                "Run: bash install_scripts/install_pico_vision_deps.sh "
                "Or export PYTHONPATH=/usr/lib/python3/dist-packages:$PYTHONPATH "
                "before running stream_camera_to_pico."
            ) from exc
        return Gst
