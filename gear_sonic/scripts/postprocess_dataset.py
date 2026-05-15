"""
Run the full LeRobot dataset post-processing pipeline in one command.

This wraps:
  1. process_dataset.py
  2. remove_discarded_episodes.py

Usage:

    python gear_sonic/scripts/postprocess_dataset.py \\
        --dataset-path outputs/my_dataset \\
        --output-path outputs/my_dataset_postprocessed

    python gear_sonic/scripts/postprocess_dataset.py \\
        --dataset-path outputs/session1 outputs/session2 \\
        --output-path outputs/merged_postprocessed
"""

from dataclasses import dataclass, field
import csv
from pathlib import Path
import shutil
import tempfile
from typing import Optional

import tyro

from process_dataset import ProcessDatasetConfig
from process_dataset import get_video_keys
from process_dataset import get_video_paths
from process_dataset import load_episodes_meta
from process_dataset import load_info
from process_dataset import load_tasks_meta
from process_dataset import main as process_dataset_main
from remove_discarded_episodes import remove_discarded_episodes as prune_discarded_episodes


@dataclass
class PostprocessDatasetConfig:
    """Clean stale SMPL frames, optionally merge, then remove discarded episodes."""

    dataset_path: list[str] = field(default_factory=list)
    """One or more dataset directories to process."""

    dataset_list: Optional[str] = None
    """Path to a text file listing dataset directories, one per line."""

    output_path: str = ""
    """Final output directory. Must not already exist."""

    remove_stale_smpl: bool = True
    """Remove stale/dropped teleop.smpl_pose frames."""

    remove_discarded: bool = True
    """Remove episodes listed in meta/info.json discarded_episode_indices."""

    keep_intermediate: bool = False
    """Keep the intermediate dataset produced by process_dataset.py."""

    intermediate_path: Optional[str] = None
    """Optional path for the intermediate dataset."""

    generate_hf_preview: bool = True
    """Generate README.md and preview/metadata.csv for the Hugging Face viewer."""

    preview_episodes: int = 5
    """Number of final episodes to include in the lightweight HF preview."""

    hf_repo_id: Optional[str] = None
    """Optional Hub repo id to write in README.md, e.g. org/dataset_name."""


def _safe_camera_name(video_key: str) -> str:
    prefix = "observation.images."
    if video_key.startswith(prefix):
        return video_key[len(prefix):]
    return video_key.replace(".", "_").replace("/", "_")


def _format_task(tasks: list[str], tasks_meta: list[dict]) -> str:
    if tasks:
        return " | ".join(str(task) for task in tasks)
    if tasks_meta:
        return str(tasks_meta[0].get("task", ""))
    return ""


def _hf_size_category(total_frames) -> str:
    if not isinstance(total_frames, int):
        return "n<1K"
    if total_frames < 1_000:
        return "n<1K"
    if total_frames < 10_000:
        return "1K<n<10K"
    if total_frames < 100_000:
        return "10K<n<100K"
    if total_frames < 1_000_000:
        return "100K<n<1M"
    return "1M<n<10M"


def _readme_text(
    dataset_path: Path,
    info: dict,
    tasks_meta: list[dict],
    video_keys: list[str],
    preview_rows: int,
    hf_repo_id: str | None,
) -> str:
    task_text = _format_task([], tasks_meta) or "unspecified task"
    repo_or_name = hf_repo_id or dataset_path.name
    total_episodes = info.get("total_episodes", "unknown")
    total_frames = info.get("total_frames", "unknown")
    size_category = _hf_size_category(total_frames)
    fps = info.get("fps", "unknown")
    codebase_version = info.get("codebase_version", "unknown")
    splits = info.get("splits", {})
    train_split = splits.get("train", "unknown") if isinstance(splits, dict) else "unknown"

    camera_lines = "\n".join(f"  - `{key}`" for key in video_keys) or "  - none"
    preview_note = (
        "A lightweight `preview/` subset is configured as the default Hugging Face "
        "Dataset Viewer view so the dataset page shows representative videos directly."
        if preview_rows
        else "No video preview subset was generated because no matching video files were found."
    )
    config_block = (
        "configs:\n"
        "- config_name: preview\n"
        "  data_dir: preview\n"
        "  default: true\n"
        "  drop_labels: true\n"
        if preview_rows
        else ""
    )

    return f"""---
{config_block}tags:
- lerobot
- robotics
- teleoperation
- robot-learning
- imitation-learning
size_categories:
- {size_category}
---

# {dataset_path.name}

Post-processed LeRobot dataset for the task: **{task_text}**.

The repository contains the full LeRobot dataset under the standard `meta/`, `data/`, and `videos/` directories. {preview_note}

## Dataset Summary

- Task: {task_text}
- Format: LeRobot {codebase_version}
- Episodes: {total_episodes}
- Frames: {total_frames}
- FPS: {fps}
- Video streams: {len(video_keys)}
- Cameras:
{camera_lines}
- Train split: `{train_split}`

## Repository Layout

```text
meta/
  info.json
  episodes.jsonl
  tasks.jsonl
data/
  chunk-000/
    episode_000000.parquet
    ...
videos/
  chunk-000/
    ...
preview/
  metadata.csv
  videos/
```

## Preview Subset

The `preview` config contains representative MP4 files from the first post-processed episodes and available camera views. This subset exists only to make the Hugging Face web viewer easier to inspect. The training data remains in the LeRobot directory structure.

## Loading With LeRobot

```python
from lerobot.datasets.lerobot_dataset import LeRobotDataset

dataset = LeRobotDataset("{repo_or_name}")
print(dataset.meta.info)
print(len(dataset))
```

## Post-processing

This dataset was post-processed to remove stale SMPL frames and discarded episodes, then episodes were renumbered sequentially.
"""


def generate_hf_dataset_preview(
    dataset_path: Path,
    preview_episodes: int,
    hf_repo_id: str | None,
) -> None:
    """Create README.md plus a small video preview dataset for the HF viewer."""
    info = load_info(dataset_path)
    episodes_meta = load_episodes_meta(dataset_path)
    tasks_meta = load_tasks_meta(dataset_path)
    video_keys = get_video_keys(info)

    preview_root = dataset_path / "preview"
    if preview_root.exists():
        shutil.rmtree(preview_root)
    videos_dir = preview_root / "videos"
    videos_dir.mkdir(parents=True, exist_ok=True)

    fps = info.get("fps", 50)
    rows = []

    for ep_meta in episodes_meta[:max(0, preview_episodes)]:
        ep_idx = ep_meta["episode_index"]
        task_text = _format_task(ep_meta.get("tasks", []), tasks_meta)
        length_frames = int(ep_meta.get("length", 0))
        duration_seconds = round(length_frames / fps, 2) if fps else 0
        video_paths = get_video_paths(dataset_path, info, ep_idx)

        for video_key in video_keys:
            src_video = video_paths.get(video_key)
            if src_video is None or not src_video.exists():
                continue

            camera_name = _safe_camera_name(video_key)
            dst_name = f"episode_{ep_idx:06d}_{camera_name}.mp4"
            dst_video = videos_dir / dst_name
            shutil.copy2(src_video, dst_video)

            rows.append({
                "file_name": f"videos/{dst_name}",
                "episode_index": ep_idx,
                "camera": video_key,
                "task": task_text,
                "length_frames": length_frames,
                "duration_seconds": f"{duration_seconds:.2f}",
                "fps": fps,
                "text": (
                    f"Episode {ep_idx} {camera_name} recording"
                    + (f" for {task_text}." if task_text else ".")
                ),
            })

    if rows:
        metadata_path = preview_root / "metadata.csv"
        with open(metadata_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)

    readme_path = dataset_path / "README.md"
    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(_readme_text(dataset_path, info, tasks_meta, video_keys, len(rows), hf_repo_id))

    print("\nGenerated Hugging Face dataset card and preview:")
    print(f"  README: {readme_path}")
    if rows:
        print(f"  Preview rows: {len(rows)}")
        print(f"  Preview videos: {videos_dir}")
    else:
        print("  Preview rows: 0 (no matching videos found)")


def main(cfg: PostprocessDatasetConfig):
    if not cfg.output_path:
        print("ERROR: --output-path is required.")
        raise SystemExit(1)

    output_path = Path(cfg.output_path)
    if output_path.exists():
        print(f"ERROR: Output path already exists: {output_path}")
        print("Choose a new --output-path to avoid mixing old and new files.")
        raise SystemExit(1)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not cfg.remove_discarded:
        process_dataset_main(
            ProcessDatasetConfig(
                dataset_path=cfg.dataset_path,
                dataset_list=cfg.dataset_list,
                output_path=str(output_path),
                remove_stale_smpl=cfg.remove_stale_smpl,
            )
        )
        if cfg.generate_hf_preview:
            generate_hf_dataset_preview(output_path, cfg.preview_episodes, cfg.hf_repo_id)
        return

    if cfg.intermediate_path:
        intermediate_path = Path(cfg.intermediate_path)
        if intermediate_path.exists():
            print(f"ERROR: Intermediate path already exists: {intermediate_path}")
            raise SystemExit(1)
        intermediate_path.parent.mkdir(parents=True, exist_ok=True)
    else:
        intermediate_path = Path(
            tempfile.mkdtemp(
                prefix=f".{output_path.name}.process_dataset.",
                dir=output_path.parent,
            )
        )

    try:
        print("\nStep 1/2: process_dataset.py")
        process_dataset_main(
            ProcessDatasetConfig(
                dataset_path=cfg.dataset_path,
                dataset_list=cfg.dataset_list,
                output_path=str(intermediate_path),
                remove_stale_smpl=cfg.remove_stale_smpl,
            )
        )

        info = load_info(intermediate_path)
        discarded = info.get("discarded_episode_indices", [])

        if discarded:
            print("\nStep 2/2: remove_discarded_episodes.py")
            prune_discarded_episodes(intermediate_path, output_path)
        else:
            print("\nStep 2/2: no discarded episodes found; moving processed dataset")
            shutil.move(str(intermediate_path), output_path)

        if cfg.keep_intermediate:
            if intermediate_path.exists():
                print(f"Intermediate dataset kept at: {intermediate_path}")
            else:
                print("Intermediate dataset was moved to the final output path.")

    finally:
        if not cfg.keep_intermediate and intermediate_path.exists():
            shutil.rmtree(intermediate_path)

    if cfg.generate_hf_preview:
        generate_hf_dataset_preview(output_path, cfg.preview_episodes, cfg.hf_repo_id)


if __name__ == "__main__":
    main(tyro.cli(PostprocessDatasetConfig))
