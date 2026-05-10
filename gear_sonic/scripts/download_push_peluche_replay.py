"""Download one push-peluche dataset video for replay-camera inference tests."""

from dataclasses import dataclass
from pathlib import Path
import random
import re

import tyro


DEFAULT_DATASET_ID = "NONHUMAN-RESEARCH/push_peluche_processed_and_cleaned"
VIDEO_PREFIX = "videos/chunk-000/observation.images.ego_view/"


@dataclass
class DownloadPushPelucheReplayConfig:
    """CLI config for downloading a replay video."""

    dataset_id: str = DEFAULT_DATASET_ID
    """Hugging Face dataset id."""

    output_dir: str = "data/push_peluche_processed_and_cleaned"
    """Local directory where the selected video will be stored."""

    episode_index: int | None = None
    """Episode index to download. If omitted, choose a random episode."""

    seed: int | None = None
    """Optional random seed for repeatable random selection."""

    download_parquet: bool = False
    """Also download the matching parquet episode file."""


def _episode_index_from_path(path: str) -> int | None:
    match = re.search(r"episode_(\d+)\.mp4$", path)
    if not match:
        return None
    return int(match.group(1))


def main(config: DownloadPushPelucheReplayConfig):
    try:
        from huggingface_hub import HfApi, hf_hub_download
    except ImportError as exc:
        raise RuntimeError(
            "huggingface_hub is required. Install it with: pip install huggingface_hub"
        ) from exc

    api = HfApi()
    files = api.list_repo_files(config.dataset_id, repo_type="dataset")
    videos = sorted(
        f
        for f in files
        if f.startswith(VIDEO_PREFIX) and f.endswith(".mp4")
    )
    if not videos:
        raise RuntimeError(f"No ego-view MP4 files found in {config.dataset_id}")

    if config.episode_index is None:
        rng = random.Random(config.seed)
        selected_video = rng.choice(videos)
    else:
        selected_video = (
            f"{VIDEO_PREFIX}episode_{config.episode_index:06d}.mp4"
        )
        if selected_video not in videos:
            available = [
                idx for idx in (_episode_index_from_path(path) for path in videos)
                if idx is not None
            ]
            raise ValueError(
                f"Episode {config.episode_index} not found. "
                f"Available range: {min(available)}..{max(available)}"
            )

    output_dir = Path(config.output_dir).expanduser()
    output_dir.mkdir(parents=True, exist_ok=True)

    local_video = hf_hub_download(
        repo_id=config.dataset_id,
        repo_type="dataset",
        filename=selected_video,
        local_dir=str(output_dir),
    )

    episode_index = _episode_index_from_path(selected_video)
    print(f"Selected episode: {episode_index}")
    print(f"Video path: {local_video}")

    if config.download_parquet and episode_index is not None:
        parquet_path = f"data/chunk-000/episode_{episode_index:06d}.parquet"
        local_parquet = hf_hub_download(
            repo_id=config.dataset_id,
            repo_type="dataset",
            filename=parquet_path,
            local_dir=str(output_dir),
        )
        print(f"Parquet path: {local_parquet}")

    print()
    print("Use this in the replay camera terminal:")
    print(f"python gear_sonic/scripts/run_video_replay_camera.py --video-path {local_video}")


if __name__ == "__main__":
    main(tyro.cli(DownloadPushPelucheReplayConfig))
