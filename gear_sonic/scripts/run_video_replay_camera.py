"""Replay an MP4 as a SONIC camera server.

This publishes frames over the same ZMQ/ImageMessageSchema transport used by
``ComposedCameraClientSensor``.  It is intended for offline VLA inference tests
where the policy should receive a recorded dataset video instead of a live robot
camera.

Example:
    python gear_sonic/scripts/run_video_replay_camera.py \
        --video-path data/push_peluche_processed_and_cleaned/videos/chunk-000/observation.images.ego_view/episode_000000.mp4 \
        --port 5555 \
        --fps 50
"""

from dataclasses import dataclass
from pathlib import Path
import time

import cv2
import tyro

from gear_sonic.camera.sensor_server import ImageMessageSchema, SensorServer


@dataclass
class VideoReplayCameraConfig:
    """CLI config for MP4 camera replay."""

    video_path: str
    """Path to an MP4 video to stream as camera input."""

    port: int = 5555
    """ZMQ camera server port."""

    image_key: str = "ego_view"
    """Image key expected by the VLA policy."""

    fps: float = 50.0
    """Replay FPS. Use 50 for SONIC VLA datasets."""

    loop: bool = True
    """Loop back to the start when the video ends."""

    start_frame: int = 0
    """Frame index to start from."""

    max_frames: int = 0
    """Maximum frames to publish, or 0 for unlimited."""

    width: int = 640
    """Published image width."""

    height: int = 480
    """Published image height."""

    warmup_seconds: float = 1.0
    """Delay after binding the PUB socket so subscribers can connect."""

    print_every: int = 100
    """Print status every N frames."""


class VideoReplayCameraServer(SensorServer):
    """Small SensorServer wrapper for video replay."""


def _open_video(video_path: Path, start_frame: int) -> cv2.VideoCapture:
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Could not open video: {video_path}")
    if start_frame > 0:
        cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
    return cap


def main(config: VideoReplayCameraConfig):
    video_path = Path(config.video_path).expanduser().resolve()
    if not video_path.exists():
        raise FileNotFoundError(video_path)
    if config.fps <= 0:
        raise ValueError("--fps must be > 0")

    server = VideoReplayCameraServer()
    cap = _open_video(video_path, config.start_frame)

    source_fps = cap.get(cv2.CAP_PROP_FPS)
    source_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    print(f"Video replay camera: {video_path}")
    print(f"Source: {source_frames} frames @ {source_fps:.2f} FPS")
    print(f"Publishing: key={config.image_key!r}, size={config.width}x{config.height}")

    server.start_server(config.port)
    print(f"Waiting {config.warmup_seconds:.1f}s for subscribers...")
    time.sleep(config.warmup_seconds)

    frame_period = 1.0 / config.fps
    published = 0
    loops = 0
    next_frame_time = time.monotonic()

    try:
        while True:
            if config.max_frames > 0 and published >= config.max_frames:
                print(f"Reached max frames ({config.max_frames}); stopping.")
                break

            loop_start = time.monotonic()
            ret, frame_bgr = cap.read()
            if not ret or frame_bgr is None:
                if not config.loop:
                    print("Video ended; stopping.")
                    break
                loops += 1
                cap.release()
                cap = _open_video(video_path, config.start_frame)
                print(f"Looping video from frame {config.start_frame} (loop {loops})")
                continue

            if frame_bgr.shape[1] != config.width or frame_bgr.shape[0] != config.height:
                frame_bgr = cv2.resize(frame_bgr, (config.width, config.height))

            # Match the existing camera stack: OAK/USB drivers provide RGB arrays
            # before ImageMessageSchema JPEG-encodes the frame.
            frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
            now = time.time()
            message = ImageMessageSchema(
                timestamps={config.image_key: now},
                images={config.image_key: frame_rgb},
            )
            server.send_message(message.serialize())
            published += 1

            if config.print_every > 0 and published % config.print_every == 0:
                elapsed = max(time.monotonic() - loop_start, 1e-6)
                print(
                    f"Published {published} frames "
                    f"(last loop body {elapsed * 1000:.1f} ms, loops={loops})"
                )

            next_frame_time += frame_period
            sleep_time = next_frame_time - time.monotonic()
            if sleep_time > 0:
                time.sleep(sleep_time)
            else:
                next_frame_time = time.monotonic()

    except KeyboardInterrupt:
        print("\nVideo replay camera interrupted.")
    finally:
        cap.release()
        server.stop_server()
        print("Video replay camera stopped.")


if __name__ == "__main__":
    main(tyro.cli(VideoReplayCameraConfig))
