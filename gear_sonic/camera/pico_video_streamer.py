"""Low-latency H.264 video streaming to PICO Remote Vision.

The PICO XRoboToolkit Unity client's Remote Vision mode listens for a TCP
connection and accepts length-prefixed H.264 byte-stream access units.  This
module mirrors the proven Psi0 flow while keeping video transport independent
from PICO pose/control tracking.
"""

from __future__ import annotations

from dataclasses import dataclass
import socket
import struct
import threading
import time

import cv2
import numpy as np


def letterbox_bgr(
    img_bgr: np.ndarray,
    out_w: int,
    out_h: int,
    fill: tuple[int, int, int] = (0, 0, 0),
) -> np.ndarray:
    """Scale image to fit inside (out_w, out_h) preserving aspect ratio; pad with ``fill``."""
    h, w = img_bgr.shape[:2]
    if w == out_w and h == out_h:
        return img_bgr
    scale = min(out_w / w, out_h / h)
    nw = max(1, int(round(w * scale)))
    nh = max(1, int(round(h * scale)))
    resized = cv2.resize(img_bgr, (nw, nh), interpolation=cv2.INTER_LINEAR)
    canvas = np.full((out_h, out_w, 3), fill, dtype=np.uint8)
    x0 = (out_w - nw) // 2
    y0 = (out_h - nh) // 2
    canvas[y0 : y0 + nh, x0 : x0 + nw] = resized
    return canvas


def stereo_pair_bgr(
    img_bgr: np.ndarray,
    out_w: int,
    out_h: int,
    letterbox: bool = True,
) -> np.ndarray:
    """Duplicate a mono BGR frame into side-by-side left/right eye views."""
    left_w = max(1, out_w // 2)
    right_w = max(1, out_w - left_w)

    if letterbox:
        left = letterbox_bgr(img_bgr, left_w, out_h)
        right = letterbox_bgr(img_bgr, right_w, out_h)
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
                    )
                elif frame.shape[1] != self.config.width or frame.shape[0] != self.config.height:
                    if self.config.letterbox:
                        frame = letterbox_bgr(
                            frame, self.config.width, self.config.height
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
    def _import_gstreamer():
        try:
            import gi

            gi.require_version("Gst", "1.0")
            from gi.repository import Gst
        except (ImportError, ValueError) as exc:
            raise ImportError(
                "GStreamer Python bindings are required for PICO video streaming. "
                "Install system packages such as python3-gi, gir1.2-gstreamer-1.0, "
                "gstreamer1.0-plugins-good, gstreamer1.0-plugins-bad, and "
                "gstreamer1.0-plugins-ugly."
            ) from exc
        return Gst
