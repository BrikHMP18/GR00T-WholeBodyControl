#!/usr/bin/env python3
"""Inspect LeRobot-style episode Parquet files: schema, dtypes, and value shapes.

Requires ``pyarrow``. ``numpy`` / ``torch`` are optional (clearer shape lines when present).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any


def _collect_parquet_files(root: Path) -> list[Path]:
    """Prefer data/chunk-*/episode_*.parquet; otherwise any *.parquet under root."""
    data_glob = sorted(root.glob("data/chunk-*/episode_*.parquet"))
    if data_glob:
        return data_glob
    return sorted(root.rglob("*.parquet"))


def _shape_str(value: Any, depth: int = 0) -> str:
    """Human-readable shape / layout for scalars, numpy, lists, and nested structures."""
    if depth > 6:
        return "... (max depth)"

    try:
        import numpy as np
    except ImportError:
        np = None  # type: ignore[assignment]

    if value is None:
        return "None"

    if np is not None and isinstance(value, np.ndarray):
        return f"ndarray shape={tuple(value.shape)} dtype={value.dtype}"

    if np is not None and isinstance(value, np.generic):
        return f"numpy scalar {type(value).__name__} = {value!r}"

    try:
        import torch

        if isinstance(value, torch.Tensor):
            return f"Tensor shape={tuple(value.shape)} dtype={value.dtype}"
    except ImportError:
        pass

    if isinstance(value, (bytes, bytearray, memoryview)):
        return f"{type(value).__name__} len={len(value)}"

    if isinstance(value, str):
        s = value if len(value) <= 80 else value[:77] + "..."
        return f"str len={len(value)} sample={s!r}"

    if isinstance(value, (list, tuple)):
        n = len(value)
        if n == 0:
            return f"{type(value).__name__} len=0"
        if np is not None:
            try:
                arr = np.asarray(value)
                if arr.dtype != object or arr.size == 0:
                    return f"{type(value).__name__}[{n}] -> asarray shape={tuple(arr.shape)} dtype={arr.dtype}"
            except (ValueError, TypeError):
                pass
        inner = _shape_str(value[0], depth + 1)
        return f"{type(value).__name__} len={n} first_elem: {inner}"

    if isinstance(value, dict):
        keys = list(value.keys())[:5]
        more = "" if len(value) <= 5 else f", ... (+{len(value) - 5} keys)"
        return f"dict keys={keys}{more}"

    return f"{type(value).__name__} value={value!r}"


def _first_row_as_dict(pf: Any) -> dict[str, Any] | None:
    """Read a single row via pyarrow (cheap: one batch)."""
    try:
        batch = next(pf.iter_batches(batch_size=1))
    except StopIteration:
        return None
    d = batch.to_pydict()
    return {k: v[0] if v else None for k, v in d.items()}


def analyze_parquet(path: Path) -> None:
    try:
        import pyarrow.parquet as pq
    except ImportError as e:
        print("Install pyarrow to inspect Parquet: pip install pyarrow", file=sys.stderr)
        raise SystemExit(1) from e

    pf = pq.ParquetFile(path)
    meta = pf.metadata
    rows = meta.num_rows
    print(f"\n{'=' * 72}")
    print(f"File: {path}")
    print(f"Rows: {rows}  row_groups: {meta.num_row_groups}  size: {path.stat().st_size / 1e6:.3f} MB")
    print(f"\n--- Arrow schema ---\n{pf.schema_arrow}")

    first = _first_row_as_dict(pf)
    if first is None:
        print("\n(no rows)")
        return

    print("\n--- Columns (dtype from first row + shape / layout) ---")
    for name in pf.schema_arrow.names:
        val = first.get(name)
        arrow_type = pf.schema_arrow.field(name).type
        line = f"  {name!r}: arrow={arrow_type}"
        try:
            line += f"  |  sample: {_shape_str(val)}"
        except Exception as ex:  # noqa: BLE001 — inspection script
            line += f"  |  sample: <error describing: {ex}>"
        print(line)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="List columns and value shapes for dataset episode Parquet files.",
    )
    parser.add_argument(
        "dataset_root",
        nargs="?",
        type=Path,
        default=None,
        help="Dataset root (contains data/, meta/, videos/). Default: scan next to this script.",
    )
    parser.add_argument(
        "--file",
        type=Path,
        default=None,
        help="Analyze a single Parquet file instead of scanning dataset_root.",
    )
    parser.add_argument(
        "--max-files",
        type=int,
        default=3,
        help="Maximum number of Parquet files to print in full (default: 3).",
    )
    args = parser.parse_args()

    if args.file is not None:
        files = [args.file.resolve()]
        for p in files:
            if not p.is_file():
                print(f"Not a file: {p}", file=sys.stderr)
                raise SystemExit(1)
    else:
        root = (args.dataset_root or Path(__file__).resolve().parent).resolve()
        if not root.is_dir():
            print(f"Not a directory: {root}", file=sys.stderr)
            raise SystemExit(1)
        files = _collect_parquet_files(root)
        if not files:
            print(f"No .parquet under {root}", file=sys.stderr)
            raise SystemExit(1)
        print(f"Found {len(files)} Parquet file(s) under {root}")

    shown = 0
    for p in files:
        if shown >= args.max_files:
            remaining = len(files) - shown
            if remaining > 0:
                print(f"\n... omitting {remaining} more file(s) (--max-files={args.max_files})")
            break
        analyze_parquet(p)
        shown += 1


if __name__ == "__main__":
    main()
