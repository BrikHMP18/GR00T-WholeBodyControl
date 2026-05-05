#!/usr/bin/env python3
"""
calculate_vel_from_pos.py

Estimate joint velocities from joint positions via finite differences,
then optionally optimize dt to minimize error against a ground-truth vel CSV.

Key design choices (informed by data analysis):
  - Ground truth was produced with forward differencing:
      vel[t] = (pos[t+1] - pos[t]) / dt
  - Two-stage dt search: coarse log-spaced grid + scipy Brent refinement.
  - Optional Gaussian smoothing of positions before differentiating.
  - Generates a 5-panel diagnostic figure.
"""

from __future__ import annotations

import argparse
import csv
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

import numpy as np

try:
    from scipy.optimize import minimize_scalar
    from scipy.ndimage import gaussian_filter1d
    _SCIPY = True
except ImportError:
    _SCIPY = False

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as _plt_module
    import matplotlib.gridspec as gridspec
    _MPL = True
except ImportError:
    _MPL = False


# ── I/O ──────────────────────────────────────────────────────────────────────

def _read_header(path: Path) -> List[str]:
    with path.open("r", newline="") as f:
        return next(csv.reader(f))


def _read_numeric(path: Path) -> np.ndarray:
    return np.loadtxt(str(path), delimiter=",", skiprows=1, dtype=np.float64)


def _write_csv(path: Path, header: Sequence[str], data: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(list(header))
        w.writerows(data.tolist())


def _vel_header(pos_header: Sequence[str]) -> List[str]:
    out = []
    for h in pos_header:
        out.append("joint_vel_" + h[len("joint_"):] if h.startswith("joint_") else h + "_vel")
    return out


# ── Smoothing ─────────────────────────────────────────────────────────────────

def smooth_positions(pos: np.ndarray, sigma: float) -> np.ndarray:
    """Gaussian smoothing along time axis (per joint)."""
    if sigma <= 0.0:
        return pos
    if _SCIPY:
        return gaussian_filter1d(pos.astype(np.float64), sigma=sigma, axis=0)
    # fallback: simple box filter
    k = max(3, int(round(sigma * 3)) | 1)
    kernel = np.ones(k) / k
    out = np.empty_like(pos, dtype=np.float64)
    for j in range(pos.shape[1]):
        out[:, j] = np.convolve(pos[:, j], kernel, mode="same")
    return out


# ── Finite-difference estimators ─────────────────────────────────────────────

def estimate_vel(pos: np.ndarray, dt: float, method: str) -> np.ndarray:
    """
    Estimate joint velocity from positions.

    Methods:
      forward  : vel[t] = (pos[t+1] - pos[t]) / dt  (last row copies prev)
      backward : vel[t] = (pos[t] - pos[t-1]) / dt  (first row copies next)
      central  : vel[t] = (pos[t+1] - pos[t-1]) / (2*dt)  (boundaries: one-sided)
    """
    if dt <= 0.0 or not np.isfinite(dt):
        raise ValueError(f"dt must be finite and positive, got {dt!r}")
    if pos.ndim != 2 or pos.shape[0] < 2:
        raise ValueError("pos must be 2-D array [T≥2, D]")

    vel = np.empty_like(pos, dtype=np.float64)
    m = method.lower().strip()

    if m == "forward":
        vel[:-1] = (pos[1:] - pos[:-1]) / dt
        vel[-1] = vel[-2]
    elif m == "backward":
        vel[1:] = (pos[1:] - pos[:-1]) / dt
        vel[0] = vel[1]
    elif m == "central":
        vel[0] = (pos[1] - pos[0]) / dt
        vel[-1] = (pos[-1] - pos[-2]) / dt
        vel[1:-1] = (pos[2:] - pos[:-2]) / (2.0 * dt)
    else:
        raise ValueError(f"Unknown method {method!r}. Choose: forward | backward | central")

    return vel


# ── Metrics ───────────────────────────────────────────────────────────────────

@dataclass
class Metrics:
    mse:           float
    rmse:          float
    mae:           float
    r2:            float
    per_joint_mse: np.ndarray
    per_joint_mae: np.ndarray
    per_joint_r2:  np.ndarray


def compute_metrics(est: np.ndarray, gt: np.ndarray) -> Metrics:
    diff = est - gt
    mse  = float(np.mean(diff ** 2))
    mae  = float(np.mean(np.abs(diff)))
    rmse = math.sqrt(mse)

    ss_res = float(np.sum(diff ** 2))
    ss_tot = float(np.sum((gt - gt.mean()) ** 2))
    r2 = (1.0 - ss_res / ss_tot) if ss_tot > 1e-30 else float("nan")

    pj_mse = np.mean(diff ** 2, axis=0)
    pj_mae = np.mean(np.abs(diff), axis=0)
    pj_r2  = np.full(gt.shape[1], float("nan"))
    for j in range(gt.shape[1]):
        ss_r = float(np.sum(diff[:, j] ** 2))
        ss_t = float(np.sum((gt[:, j] - gt[:, j].mean()) ** 2))
        if ss_t > 1e-30:
            pj_r2[j] = 1.0 - ss_r / ss_t

    return Metrics(mse, rmse, mae, r2, pj_mse, pj_mae, pj_r2)


# ── Optimization ─────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class DtResult:
    dt:     float
    loss:   float   # value of the optimized metric (MSE or MAE)
    method: str
    metric: str     # "mse" or "mae"


def _golden(f, lo: float, hi: float, tol: float = 1e-14, max_iter: int = 200) -> Tuple[float, float]:
    phi = (1 + math.sqrt(5)) / 2
    c, d = hi - (hi - lo) / phi, lo + (hi - lo) / phi
    fc, fd = f(c), f(d)
    for _ in range(max_iter):
        if abs(hi - lo) < tol:
            break
        if fc < fd:
            hi, d, fd = d, c, fc
            c = hi - (hi - lo) / phi
            fc = f(c)
        else:
            lo, c, fc = c, d, fd
            d = lo + (hi - lo) / phi
            fd = f(d)
    return (c, fc) if fc < fd else (d, fd)


def optimize_dt(
    pos: np.ndarray,
    vel_gt: np.ndarray,
    *,
    method: str,
    dt_min: float,
    dt_max: float,
    n_grid: int = 300,
    metric: str = "mse",
) -> DtResult:
    """
    Two-stage optimization:
      1. Log-spaced coarse grid of n_grid points → find best interval.
      2. Refine with scipy Brent (or golden-section if scipy absent).

    metric: "mse" minimizes mean squared error; "mae" minimizes mean absolute error.
    """
    metric = metric.lower().strip()
    if metric not in ("mse", "mae"):
        raise ValueError(f"metric must be 'mse' or 'mae', got {metric!r}")

    def obj(dt: float) -> float:
        diff = estimate_vel(pos, dt, method) - vel_gt
        return float(np.mean(np.abs(diff)) if metric == "mae" else np.mean(diff ** 2))

    # Stage 1: coarse grid
    grid = np.logspace(math.log10(dt_min), math.log10(dt_max), n_grid)
    losses = np.fromiter((obj(dt) for dt in grid), dtype=np.float64, count=n_grid)
    best_i = int(np.argmin(losses))
    lo = grid[max(0, best_i - 1)]
    hi = grid[min(n_grid - 1, best_i + 1)]

    # Stage 2: refinement
    if _SCIPY:
        res = minimize_scalar(obj, bounds=(lo, hi), method="bounded",
                              options={"xatol": 1e-14, "maxiter": 500})
        dt_best, loss_best = float(res.x), float(res.fun)
    else:
        dt_best, loss_best = _golden(obj, lo, hi)

    return DtResult(dt=dt_best, loss=loss_best, method=method, metric=metric)


def compare_all_methods(
    pos: np.ndarray,
    vel_gt: np.ndarray,
    *,
    dt_min: float,
    dt_max: float,
    n_grid: int,
    metric: str = "mse",
) -> List[DtResult]:
    results = [
        optimize_dt(pos, vel_gt, method=m,
                    dt_min=dt_min, dt_max=dt_max, n_grid=n_grid, metric=metric)
        for m in ("forward", "backward", "central")
    ]
    results.sort(key=lambda r: r.loss)
    return results


# ── Plots ─────────────────────────────────────────────────────────────────────

def _top_variance_joints(vel_gt: np.ndarray, n: int = 6) -> List[int]:
    return list(np.argsort(np.var(vel_gt, axis=0))[::-1][:n])


def plot_comparison(
    vel_est: np.ndarray,
    vel_gt: np.ndarray,
    metrics: Metrics,
    *,
    dt: float,
    method: str,
    joints_to_plot: Optional[List[int]] = None,
    out_path: Optional[Path] = None,
    show: bool = False,
    pos_header: Optional[List[str]] = None,
    method_results: Optional[List[DtResult]] = None,
) -> None:
    if not _MPL:
        print("[WARN] matplotlib not available; skipping plots.", file=sys.stderr)
        return

    if show:
        try:
            matplotlib.use("TkAgg")
        except Exception:
            pass

    import matplotlib.pyplot as plt

    T, D = vel_gt.shape
    if joints_to_plot is None:
        joints_to_plot = _top_variance_joints(vel_gt, n=6)

    joint_names = [
        (pos_header[j] if pos_header and j < len(pos_header) else f"joint_{j}")
        for j in range(D)
    ]

    fig = plt.figure(figsize=(20, 14))
    fig.suptitle(
        f"Velocity estimation  │  method={method}  dt={dt:.8f} s  "
        f"MSE={metrics.mse:.6f}  RMSE={metrics.rmse:.6f}  MAE={metrics.mae:.6f}  R²={metrics.r2:.4f}",
        fontsize=12, fontweight="bold",
    )
    gs = gridspec.GridSpec(2, 3, figure=fig, hspace=0.45, wspace=0.35)

    cmap = plt.cm.tab10
    t = np.arange(T)

    # ── A: time series overlay ────────────────────────────────────────────────
    ax_ts = fig.add_subplot(gs[0, :2])
    for k, j in enumerate(joints_to_plot):
        c = cmap(k % 10)
        ax_ts.plot(t, vel_gt[:, j],  color=c, lw=1.2, label=f"GT  {joint_names[j]}")
        ax_ts.plot(t, vel_est[:, j], color=c, lw=1.0, ls="--", alpha=0.75,
                   label=f"Est {joint_names[j]}")
    ax_ts.set_title("Time-series: GT (solid) vs Estimated (dashed) – top-variance joints")
    ax_ts.set_xlabel("Frame")
    ax_ts.set_ylabel("Velocity (rad/s)")
    ax_ts.legend(fontsize=6.5, ncol=2, loc="upper right")
    ax_ts.grid(True, alpha=0.25)

    # ── B: per-joint MSE bar ──────────────────────────────────────────────────
    ax_bar = fig.add_subplot(gs[0, 2])
    xb = np.arange(D)
    ax_bar.bar(xb, metrics.per_joint_mse, color="steelblue", alpha=0.85)
    ax_bar.axhline(metrics.mse, color="crimson", lw=1.5, ls="--",
                   label=f"global MSE={metrics.mse:.5f}")
    for j in joints_to_plot:
        ax_bar.axvline(j, color="orange", lw=0.8, alpha=0.7)
    ax_bar.set_title("Per-joint MSE  (orange = plotted joints)")
    ax_bar.set_xlabel("Joint index")
    ax_bar.set_ylabel("MSE")
    ax_bar.legend(fontsize=8)
    ax_bar.set_xticks(xb[::5])
    ax_bar.grid(True, alpha=0.25)

    # ── C: scatter vel_est vs vel_gt ─────────────────────────────────────────
    ax_sc = fig.add_subplot(gs[1, 0])
    flat_gt  = vel_gt.ravel()
    flat_est = vel_est.ravel()
    step = max(1, len(flat_gt) // 8000)
    ax_sc.scatter(flat_gt[::step], flat_est[::step], s=1.5, alpha=0.25, color="royalblue", rasterized=True)
    vmin = min(flat_gt.min(), flat_est.min())
    vmax = max(flat_gt.max(), flat_est.max())
    ax_sc.plot([vmin, vmax], [vmin, vmax], "r--", lw=1.5, label="ideal y=x")
    ax_sc.set_title("Scatter: GT vs Estimated")
    ax_sc.set_xlabel("GT velocity (rad/s)")
    ax_sc.set_ylabel("Estimated velocity (rad/s)")
    ax_sc.legend(fontsize=8)
    ax_sc.grid(True, alpha=0.25)

    # ── D: error histogram ───────────────────────────────────────────────────
    ax_hist = fig.add_subplot(gs[1, 1])
    errors = (vel_est - vel_gt).ravel()
    ax_hist.hist(errors, bins=100, color="darkorange", alpha=0.8, density=True)
    ax_hist.axvline(0,             color="black", lw=1.2, ls="--", label="zero")
    ax_hist.axvline(errors.mean(), color="crimson", lw=1.5, label=f"mean={errors.mean():.5f}")
    # ±1 std
    std = errors.std()
    ax_hist.axvline( std, color="steelblue", lw=1.0, ls=":", label=f"±σ={std:.4f}")
    ax_hist.axvline(-std, color="steelblue", lw=1.0, ls=":")
    ax_hist.set_title("Error distribution  (est − GT)")
    ax_hist.set_xlabel("Error (rad/s)")
    ax_hist.set_ylabel("Density")
    ax_hist.legend(fontsize=8)
    ax_hist.grid(True, alpha=0.25)

    # ── E: per-joint R² ──────────────────────────────────────────────────────
    ax_r2 = fig.add_subplot(gs[1, 2])
    r2c = np.clip(np.nan_to_num(metrics.per_joint_r2, nan=0.0), -1.0, 1.0)
    colors_r2 = ["steelblue" if v >= 0.0 else "tomato" for v in r2c]
    ax_r2.bar(xb, r2c, color=colors_r2, alpha=0.85)
    ax_r2.axhline(1.0, color="green",  lw=1.0, ls="--", label="perfect R²=1")
    ax_r2.axhline(0.0, color="black",  lw=0.8)
    global_r2_clean = np.nan_to_num(metrics.r2, nan=0.0)
    ax_r2.axhline(global_r2_clean, color="crimson", lw=1.5, ls="--",
                  label=f"global R²={metrics.r2:.4f}")
    ax_r2.set_title("Per-joint R²  (blue≥0, red<0)")
    ax_r2.set_xlabel("Joint index")
    ax_r2.set_ylabel("R²")
    ax_r2.legend(fontsize=8)
    ax_r2.set_xticks(xb[::5])
    ax_r2.grid(True, alpha=0.25)

    if out_path is not None:
        fig.savefig(str(out_path), dpi=150, bbox_inches="tight")
        print(f"[plot] Saved → {out_path}")
    if show:
        plt.show()
    plt.close(fig)


# ── CLI ───────────────────────────────────────────────────────────────────────

def main(argv: Optional[Sequence[str]] = None) -> int:
    p = argparse.ArgumentParser(
        description="Estimate joint velocities from joint_pos.csv; optimize dt against GT.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    io = p.add_argument_group("I/O")
    io.add_argument("--pos",      type=Path, required=True, help="Path to joint_pos.csv")
    io.add_argument("--vel-gt",   type=Path, default=None,  help="Path to joint_vel.csv (ground truth)")
    io.add_argument("--out",      type=Path, default=None,  help="Output CSV for estimated velocities")

    opt = p.add_argument_group("Optimization")
    opt.add_argument("--dt",          type=float, default=None,
                     help="Fixed dt (s). Omit to optimize automatically.")
    opt.add_argument("--method",      type=str,   default="forward",
                     choices=["forward", "backward", "central"],
                     help="Finite-difference method.")
    opt.add_argument("--all-methods", action="store_true",
                     help="Try all 3 methods and select the best (requires --vel-gt).")
    opt.add_argument("--metric",  type=str,   default="mse", choices=["mse", "mae"],
                     help="Metric to minimize during dt optimization.")
    opt.add_argument("--dt-min",  type=float, default=1e-4, help="Lower bound for dt search.")
    opt.add_argument("--dt-max",  type=float, default=0.20, help="Upper bound for dt search.")
    opt.add_argument("--n-grid",  type=int,   default=300,  help="Coarse grid points for dt search.")

    pre = p.add_argument_group("Pre-processing")
    pre.add_argument("--smooth-sigma", type=float, default=0.0,
                     help="Gaussian σ (frames) to smooth positions before differentiating. 0=off.")

    viz = p.add_argument_group("Visualization")
    viz.add_argument("--plot",     action="store_true", help="Generate diagnostic figure.")
    viz.add_argument("--plot-out", type=Path, default=None, help="Path to save figure (PNG/PDF).")
    viz.add_argument("--show",     action="store_true",    help="Display figure interactively.")
    viz.add_argument("--joints",   type=int, nargs="+", default=None,
                     help="Joint indices to highlight in time-series panel.")

    args = p.parse_args(argv)

    # ── Load ─────────────────────────────────────────────────────────────────
    pos_header = _read_header(args.pos)
    pos = _read_numeric(args.pos).astype(np.float64)

    if args.smooth_sigma > 0.0:
        pos_smooth = smooth_positions(pos, sigma=args.smooth_sigma)
        print(f"[pre] Gaussian smoothing applied: σ={args.smooth_sigma} frames")
    else:
        pos_smooth = pos

    vel_gt, vel_gt_header = None, None
    if args.vel_gt is not None:
        vel_gt_header = _read_header(args.vel_gt)
        vel_gt = _read_numeric(args.vel_gt).astype(np.float64)
        if vel_gt.shape != pos.shape:
            raise ValueError(f"Shape mismatch: pos{pos.shape} vs vel_gt{vel_gt.shape}")

    # ── Optimize / set dt & method ────────────────────────────────────────────
    dt, method = args.dt, args.method
    method_results: List[DtResult] = []

    if dt is None:
        if vel_gt is None:
            raise ValueError("Provide --dt, or --vel-gt so dt can be optimized.")
        print(f"[opt] Searching dt in [{args.dt_min}, {args.dt_max}] with {args.n_grid}-point grid "
              f"(metric={args.metric.upper()}) …")
        if args.all_methods:
            method_results = compare_all_methods(
                pos_smooth, vel_gt,
                dt_min=args.dt_min, dt_max=args.dt_max, n_grid=args.n_grid, metric=args.metric,
            )
            best = method_results[0]
            dt, method = best.dt, best.method
        else:
            res = optimize_dt(
                pos_smooth, vel_gt, method=method,
                dt_min=args.dt_min, dt_max=args.dt_max, n_grid=args.n_grid, metric=args.metric,
            )
            dt, method = res.dt, res.method
            method_results = [res]
    elif args.all_methods and vel_gt is not None:
        for m in ("forward", "backward", "central"):
            ve = estimate_vel(pos_smooth, dt, m)
            diff = ve - vel_gt
            loss = float(np.mean(np.abs(diff)) if args.metric == "mae" else np.mean(diff ** 2))
            method_results.append(DtResult(dt=dt, loss=loss, method=m, metric=args.metric))
        method_results.sort(key=lambda r: r.loss)

    # ── Estimate ─────────────────────────────────────────────────────────────
    vel_est = estimate_vel(pos_smooth, float(dt), method)

    # ── Metrics ──────────────────────────────────────────────────────────────
    metrics = compute_metrics(vel_est, vel_gt) if vel_gt is not None else None

    # ── Print summary ────────────────────────────────────────────────────────
    opt_metric = args.metric.upper()
    sep = "=" * 62
    print(sep)
    print(f"  dt       : {dt:.10f} s  ({1.0/dt:.4f} Hz)")
    print(f"  method   : {method}")
    print(f"  metric   : {opt_metric} (optimization target)")
    if _SCIPY:
        print(f"  backend  : scipy Brent (stage-2 refinement)")
    else:
        print(f"  backend  : golden-section search")
    if metrics is not None:
        print(f"  MSE      : {metrics.mse:.8f}")
        print(f"  RMSE     : {metrics.rmse:.8f}")
        print(f"  MAE      : {metrics.mae:.8f}")
        print(f"  R²       : {metrics.r2:.6f}")
    if len(method_results) > 1:
        print()
        print(f"  {'Method':<12}  {'dt (s)':>14}  {opt_metric:>14}")
        print(f"  {'-'*12}  {'-'*14}  {'-'*14}")
        for r in method_results:
            tag = " ← best" if r.method == method else ""
            print(f"  {r.method:<12}  {r.dt:>14.8f}  {r.loss:>14.8f}{tag}")
    if metrics is not None:
        print()
        worst = np.argsort(metrics.per_joint_mse)[::-1][:8]
        print(f"  {'Joint':<22}  {'MSE':>10}  {'MAE':>10}  {'R²':>8}")
        print(f"  {'-'*22}  {'-'*10}  {'-'*10}  {'-'*8}")
        for j in worst:
            name = pos_header[j] if j < len(pos_header) else f"joint_{j}"
            r2v  = metrics.per_joint_r2[j]
            print(f"  {name:<22}  {metrics.per_joint_mse[j]:>10.6f}  "
                  f"{metrics.per_joint_mae[j]:>10.6f}  "
                  f"{r2v:>8.4f}")
    print(sep)
    print(f"\n>>> Best dt: {dt:.10f} s  ({1.0/dt:.6f} Hz)  [method={method}, metric={opt_metric}]\n")

    # ── Save CSV ─────────────────────────────────────────────────────────────
    if args.out is not None:
        out_hdr = (
            vel_gt_header
            if (vel_gt_header and len(vel_gt_header) == vel_est.shape[1])
            else _vel_header(pos_header)
        )
        _write_csv(args.out, out_hdr, vel_est)
        print(f"[out] Saved → {args.out}")

    # ── Plot ─────────────────────────────────────────────────────────────────
    if (args.plot or args.plot_out or args.show):
        if vel_gt is not None and metrics is not None:
            plot_comparison(
                vel_est, vel_gt, metrics,
                dt=dt, method=method,
                joints_to_plot=args.joints,
                out_path=args.plot_out,
                show=args.show,
                pos_header=pos_header,
                method_results=method_results,
            )
        else:
            print("[WARN] --plot requires --vel-gt for comparison. Skipping.", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
