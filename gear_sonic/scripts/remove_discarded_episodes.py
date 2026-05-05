"""
Remove discarded episodes from a LeRobot dataset and renumber remaining episodes.

Reads the 'discarded_episode_indices' field from meta/info.json, omits those
episodes from the output copy (no parquet/videos for discarded indices),
renumbers remaining episodes sequentially (0, 1, 2, ...), and updates
info.json (total_episodes, total_frames, splits, total_videos, total_chunks).

Usage:

    # Remove discarded episodes and write to a new directory
    python gear_sonic/scripts/remove_discarded_episodes.py \\
        --dataset-path outputs/my_dataset \\
        --output-path outputs/my_dataset_cleaned

    # Show what would be removed without doing it
    python gear_sonic/scripts/remove_discarded_episodes.py \\
        --dataset-path outputs/my_dataset \\
        --dry-run
"""

from dataclasses import dataclass
import json
from pathlib import Path
import shutil
from typing import Optional

import pandas as pd
import tyro


# ---------------------------------------------------------------------------
# Helper functions (reusing logic from process_dataset.py)
# ---------------------------------------------------------------------------

def load_info(dataset_path: Path) -> dict:
    info_path = dataset_path / "meta" / "info.json"
    with open(info_path, encoding="utf-8") as f:
        return json.load(f)


def load_episodes_meta(dataset_path: Path) -> list[dict]:
    episodes_path = dataset_path / "meta" / "episodes.jsonl"
    episodes = []
    with open(episodes_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                episodes.append(json.loads(line))
    return episodes


def load_tasks_meta(dataset_path: Path) -> list[dict]:
    tasks_path = dataset_path / "meta" / "tasks.jsonl"
    tasks = []
    if tasks_path.exists():
        with open(tasks_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    tasks.append(json.loads(line))
    return tasks


def get_parquet_path(dataset_path: Path, info: dict, episode_index: int) -> Path:
    data_path_pattern = info.get("data_path", "data/chunk-{episode_chunk:03d}/episode_{episode_index:06d}.parquet")
    chunks_size = info.get("chunks_size", 1000)
    episode_chunk = episode_index // chunks_size
    return dataset_path / data_path_pattern.format(
        episode_chunk=episode_chunk, episode_index=episode_index,
    )


def get_video_keys(info: dict) -> list[str]:
    """Extract video keys from info.json."""
    keys = info.get("video_keys", [])
    if not keys:
        keys = [
            k for k, v in info.get("features", {}).items()
            if v.get("dtype") in ("video", "image")
        ]
    return keys


def get_video_paths(dataset_path: Path, info: dict, episode_index: int) -> dict[str, Path]:
    video_path_pattern = info.get(
        "video_path",
        "videos/{video_key}/episode_{episode_index:06d}.mp4",
    )
    video_keys = get_video_keys(info)
    chunks_size = info.get("chunks_size", 1000)
    episode_chunk = episode_index // chunks_size
    paths = {}
    for key in video_keys:
        paths[key] = dataset_path / video_path_pattern.format(
            video_key=key, episode_index=episode_index,
            episode_chunk=episode_chunk,
        )
    return paths


def episode_chunk_count(n_episodes: int, chunks_size: int) -> int:
    """Number of chunk folders needed for episode indices 0 .. n_episodes-1."""
    if n_episodes <= 0:
        return 1
    return max(1, (n_episodes - 1) // chunks_size + 1)


def apply_info_derived_counts(info: dict, n_episodes: int, total_frames: int) -> None:
    """Set total_episodes, total_frames, splits, total_videos, total_chunks in info.json."""
    info["total_episodes"] = n_episodes
    info["total_frames"] = total_frames

    video_keys = get_video_keys(info)
    info["total_videos"] = n_episodes * len(video_keys)

    chunks_size = info.get("chunks_size", 1000)
    info["total_chunks"] = episode_chunk_count(n_episodes, chunks_size)

    # LeRobot: "0:N" => episode indices 0 .. N-1 (N is exclusive end)
    info["splits"] = {"train": f"0:{n_episodes}"}


# ---------------------------------------------------------------------------
# Main logic
# ---------------------------------------------------------------------------

def remove_discarded_episodes(
    dataset_path: Path,
    output_path: Path | None,
    dry_run: bool = False,
):
    """Remove discarded episodes and renumber the rest."""
    
    info = load_info(dataset_path)
    episodes_meta = load_episodes_meta(dataset_path)
    tasks_meta = load_tasks_meta(dataset_path)
    
    # Get list of discarded episode indices
    discarded_indices = set(info.get("discarded_episode_indices", []))
    
    if not discarded_indices:
        print("No discarded episodes found in meta/info.json")
        print("Nothing to do.")
        return
    
    print(f"Found {len(discarded_indices)} discarded episodes: {sorted(discarded_indices)}")
    print(f"Total episodes in dataset: {len(episodes_meta)}")
    
    # Filter out discarded episodes
    kept_episodes = []
    removed_episodes = []
    
    for ep_meta in episodes_meta:
        ep_idx = ep_meta["episode_index"]
        if ep_idx in discarded_indices:
            removed_episodes.append(ep_idx)
        else:
            kept_episodes.append(ep_meta)
    
    print(f"Keeping {len(kept_episodes)} episodes")
    print(f"Removing {len(removed_episodes)} episodes: {sorted(removed_episodes)}")

    if not kept_episodes:
        print("\nERROR: All episodes are marked discarded; nothing to export.")
        raise SystemExit(1)

    if dry_run:
        k = len(kept_episodes)
        print("\n[DRY RUN] Would perform the following actions:")
        print(f"  - Remove {len(removed_episodes)} episodes")
        print(f"  - Renumber {k} episodes (0 .. {k - 1})")
        print(f"  - Write to: {output_path or '(set --output-path to write)'}")
        return

    if output_path is None:
        print("ERROR: --output-path is required when not using --dry-run")
        raise SystemExit(1)

    # Create output directory
    output_path.mkdir(parents=True, exist_ok=True)
    meta_dir = output_path / "meta"
    meta_dir.mkdir(exist_ok=True)
    
    fps = info.get("fps", 50)
    chunks_size = info.get("chunks_size", 1000)
    
    # Process and renumber episodes
    total_frames = 0
    new_episodes_meta = []
    
    for new_idx, old_ep_meta in enumerate(kept_episodes):
        old_idx = old_ep_meta["episode_index"]
        
        print(f"Processing episode {old_idx} -> {new_idx}")
        
        # Load parquet
        old_parquet_path = get_parquet_path(dataset_path, info, old_idx)
        if not old_parquet_path.exists():
            print(f"ERROR: Parquet file not found: {old_parquet_path}")
            raise SystemExit(1)

        df = pd.read_parquet(old_parquet_path)
        ep_len = len(df)
        
        # Update dataframe indices
        df["episode_index"] = new_idx
        df["index"] = range(total_frames, total_frames + ep_len)
        df["frame_index"] = range(ep_len)
        if "timestamp" in df.columns:
            df["timestamp"] = [i / fps for i in range(ep_len)]
        
        # Write new parquet
        episode_chunk = new_idx // chunks_size
        data_path_pattern = info.get(
            "data_path",
            "data/chunk-{episode_chunk:03d}/episode_{episode_index:06d}.parquet",
        )
        new_parquet_rel = data_path_pattern.format(
            episode_chunk=episode_chunk, episode_index=new_idx
        )
        new_parquet_path = output_path / new_parquet_rel
        new_parquet_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(new_parquet_path)
        
        # Copy and rename videos
        old_video_paths = get_video_paths(dataset_path, info, old_idx)
        video_path_pattern = info.get(
            "video_path",
            "videos/{video_key}/episode_{episode_index:06d}.mp4",
        )
        
        for vkey, old_video_path in old_video_paths.items():
            if old_video_path.exists():
                new_video_rel = video_path_pattern.format(
                    video_key=vkey, episode_index=new_idx, episode_chunk=episode_chunk,
                )
                new_video_path = output_path / new_video_rel
                new_video_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(old_video_path, new_video_path)
        
        # Create new episode metadata
        new_ep_meta = {
            "episode_index": new_idx,
            "tasks": old_ep_meta.get("tasks", []),
            "length": ep_len,
        }
        new_episodes_meta.append(new_ep_meta)
        
        total_frames += ep_len

    n_kept = len(new_episodes_meta)
    if n_kept != len(kept_episodes):
        print(
            f"ERROR: Expected {len(kept_episodes)} episodes after processing, "
            f"got {n_kept} (parquet loading must not skip)."
        )
        raise SystemExit(1)

    # Update info.json (remove discarded_episode_indices field)
    new_info = info.copy()
    if "discarded_episode_indices" in new_info:
        del new_info["discarded_episode_indices"]

    apply_info_derived_counts(new_info, n_kept, total_frames)

    with open(meta_dir / "info.json", "w", encoding="utf-8") as f:
        json.dump(new_info, f, indent=4)
    
    # Write episodes.jsonl
    with open(meta_dir / "episodes.jsonl", "w", encoding="utf-8") as f:
        for ep in new_episodes_meta:
            f.write(json.dumps(ep) + "\n")
    
    # Copy tasks.jsonl if exists
    if tasks_meta:
        with open(meta_dir / "tasks.jsonl", "w", encoding="utf-8") as f:
            for task in tasks_meta:
                f.write(json.dumps(task) + "\n")
    
    # Copy modality.json if exists
    modality_path = dataset_path / "meta" / "modality.json"
    if modality_path.exists():
        shutil.copy2(modality_path, meta_dir / "modality.json")
    
    print("\n" + "=" * 70)
    print("  Cleanup complete!")
    print("=" * 70)
    print(f"  Removed:         {len(removed_episodes)} episodes")
    print(f"  Kept:            {len(new_episodes_meta)} episodes (renumbered)")
    print(f"  Total frames:    {total_frames}")
    print(f"  Output:          {output_path}")
    print("=" * 70)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

@dataclass
class RemoveDiscardedConfig:
    """Remove discarded episodes from a LeRobot dataset."""

    dataset_path: str
    """Path to the input dataset directory."""

    output_path: Optional[str] = None
    """Output directory for the cleaned dataset. Required unless --dry-run is used."""

    dry_run: bool = False
    """Show what would be removed without actually doing it."""


def main(cfg: RemoveDiscardedConfig):
    dataset_path = Path(cfg.dataset_path)
    
    if not dataset_path.exists():
        print(f"ERROR: Dataset path does not exist: {dataset_path}")
        raise SystemExit(1)
    
    if not (dataset_path / "meta" / "info.json").exists():
        print(f"ERROR: Not a valid LeRobot dataset (missing meta/info.json): {dataset_path}")
        raise SystemExit(1)
    
    if not cfg.dry_run and cfg.output_path is None:
        print("ERROR: --output-path is required (or use --dry-run to preview)")
        raise SystemExit(1)
    
    output_path = Path(cfg.output_path) if cfg.output_path else None
    
    print("=" * 70)
    print("  Remove Discarded Episodes")
    print("=" * 70)
    print(f"  Input dataset:    {dataset_path}")
    if output_path:
        print(f"  Output:           {output_path}")
    print(f"  Dry run:          {cfg.dry_run}")
    print("=" * 70)
    print()
    
    remove_discarded_episodes(dataset_path, output_path, dry_run=cfg.dry_run)


if __name__ == "__main__":
    main(tyro.cli(RemoveDiscardedConfig))
