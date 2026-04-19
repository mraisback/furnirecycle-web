"""
Visualizer: Produces all output charts saved to the outputs/ directory.

Charts generated:
  1. warehouse_heatmap.png   – SKU velocity heatmap on the grid
  2. abc_xyz_matrix.png      – 3×3 ABC/XYZ distribution bubble chart
  3. comparison_bar.png      – Before vs after KPI bar chart
  4. route_sample.png        – Sample picker route plotted on the grid
"""

from __future__ import annotations

import os
from typing import Dict, List, Optional, Tuple

import matplotlib
matplotlib.use("Agg")   # headless rendering
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from .data_processor import WarehouseLayout
from .simulator import SimResult

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "outputs")


def _ensure_output_dir():
    os.makedirs(OUTPUT_DIR, exist_ok=True)


# ------------------------------------------------------------------
# 1. Warehouse velocity heatmap
# ------------------------------------------------------------------

def plot_warehouse_heatmap(
    layout: WarehouseLayout,
    slot_df: pd.DataFrame,
    title: str = "SKU Velocity Heatmap",
    filename: str = "warehouse_heatmap.png",
) -> None:
    _ensure_output_dir()
    grid = np.full((layout.rows, layout.cols), np.nan)
    for _, row in slot_df.iterrows():
        grid[int(row["row"]), int(row["col"])] = row["velocity_score"]

    fig, ax = plt.subplots(figsize=(max(10, layout.cols * 0.6), max(6, layout.rows * 0.5)))
    sns.heatmap(
        grid,
        ax=ax,
        cmap="YlOrRd",
        linewidths=0.3,
        linecolor="grey",
        cbar_kws={"label": "Velocity Score"},
        mask=np.isnan(grid),
        vmin=0,
        vmax=1,
    )
    # Mark dispatch point
    ey, ex = layout.entry_exit
    ax.add_patch(mpatches.Rectangle((ex, ey), 1, 1, color="blue", alpha=0.7, zorder=5))
    ax.set_title(title, fontsize=14, fontweight="bold")
    ax.set_xlabel("Column")
    ax.set_ylabel("Row")
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, filename), dpi=150)
    plt.close()


# ------------------------------------------------------------------
# 2. ABC × XYZ bubble matrix
# ------------------------------------------------------------------

def plot_abc_xyz_matrix(
    sku_df: pd.DataFrame,
    filename: str = "abc_xyz_matrix.png",
) -> None:
    _ensure_output_dir()
    abc_order = ["A", "B", "C"]
    xyz_order = ["X", "Y", "Z"]
    counts = (
        sku_df.groupby(["abc_class", "xyz_class"])
        .size()
        .reset_index(name="count")
    )

    fig, ax = plt.subplots(figsize=(7, 5))
    for _, row in counts.iterrows():
        xi = xyz_order.index(row["xyz_class"])
        yi = abc_order.index(row["abc_class"])
        size = row["count"] * 200
        ax.scatter(xi, yi, s=size, alpha=0.7, color="steelblue")
        ax.text(xi, yi, str(row["count"]), ha="center", va="center", fontsize=10, color="white", fontweight="bold")

    ax.set_xticks(range(3))
    ax.set_xticklabels(xyz_order, fontsize=12)
    ax.set_yticks(range(3))
    ax.set_yticklabels(abc_order, fontsize=12)
    ax.set_xlabel("XYZ Class (demand variability)", fontsize=11)
    ax.set_ylabel("ABC Class (revenue contribution)", fontsize=11)
    ax.set_title("ABC × XYZ SKU Classification Matrix", fontsize=13, fontweight="bold")
    ax.grid(True, linestyle="--", alpha=0.4)
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, filename), dpi=150)
    plt.close()


# ------------------------------------------------------------------
# 3. Before vs after KPI comparison
# ------------------------------------------------------------------

def plot_comparison(
    baseline: SimResult,
    optimised: SimResult,
    filename: str = "comparison_bar.png",
) -> None:
    _ensure_output_dir()
    metrics = {
        "Total Distance (m)": ("total_distance_m", True),     # lower is better
        "Mean Distance/Order (m)": ("mean_distance_m", True),
        "Total Time (s)": ("total_time_s", True),
        "Throughput Orders/h": ("throughput_orders_h", False), # higher is better
        "Throughput Picks/h": ("throughput_picks_h", False),
    }

    labels = list(metrics.keys())
    base_vals = [getattr(baseline, v) for v, _ in metrics.values()]
    opt_vals = [getattr(optimised, v) for v, _ in metrics.values()]

    x = np.arange(len(labels))
    width = 0.35

    fig, ax = plt.subplots(figsize=(12, 6))
    bars1 = ax.bar(x - width / 2, base_vals, width, label="Baseline", color="#E07B54", alpha=0.85)
    bars2 = ax.bar(x + width / 2, opt_vals, width, label="Optimised", color="#4C9BE8", alpha=0.85)

    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=20, ha="right", fontsize=9)
    ax.set_ylabel("Value")
    ax.set_title("Warehouse Optimisation: Before vs After", fontsize=13, fontweight="bold")
    ax.legend()
    ax.grid(axis="y", linestyle="--", alpha=0.4)

    # Annotate % change
    for i, (b, o) in enumerate(zip(base_vals, opt_vals)):
        if b != 0:
            pct = (o - b) / abs(b) * 100
            color = "green" if pct < 0 else "red"
            ax.text(
                x[i],
                max(b, o) * 1.02,
                f"{pct:+.1f}%",
                ha="center",
                fontsize=8,
                color=color,
                fontweight="bold",
            )

    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, filename), dpi=150)
    plt.close()


# ------------------------------------------------------------------
# 4. Sample picker route overlay
# ------------------------------------------------------------------

def plot_sample_route(
    layout: WarehouseLayout,
    route: List[Tuple[int, int]],
    assignment: Dict[str, Tuple[int, int]],
    title: str = "Sample Picker Route",
    filename: str = "route_sample.png",
) -> None:
    _ensure_output_dir()
    fig, ax = plt.subplots(figsize=(max(10, layout.cols * 0.6), max(6, layout.rows * 0.5)))

    # Draw grid cells
    for r in range(layout.rows):
        for c in range(layout.cols):
            is_aisle = (c % layout.aisle_gap == 0)
            color = "#DDEEFF" if is_aisle else "#F5F5F5"
            rect = mpatches.FancyBboxPatch(
                (c, r), 1, 1,
                boxstyle="square,pad=0.02",
                facecolor=color,
                edgecolor="#CCCCCC",
                linewidth=0.4,
            )
            ax.add_patch(rect)

    # Draw storage locations
    inv_assign = {v: k for k, v in assignment.items()}
    for pos, sku_id in inv_assign.items():
        r, c = pos
        ax.add_patch(mpatches.Rectangle((c + 0.1, r + 0.1), 0.8, 0.8, color="#A8D8EA", alpha=0.7))

    # Draw route
    if route:
        route_cols = [c + 0.5 for r, c in route]
        route_rows = [r + 0.5 for r, c in route]
        ax.plot(route_cols, route_rows, "r-o", linewidth=1.5, markersize=5, zorder=5)
        # Mark start/end
        ax.plot(route_cols[0], route_rows[0], "gs", markersize=12, label="Start/End", zorder=6)

    # Mark pick points (stops that are not start/end)
    for i, (r, c) in enumerate(route[1:-1], 1):
        ax.text(c + 0.5, r + 0.5, str(i), ha="center", va="center", fontsize=7, color="darkred")

    ax.set_xlim(0, layout.cols)
    ax.set_ylim(0, layout.rows)
    ax.set_aspect("equal")
    ax.set_title(title, fontsize=13, fontweight="bold")
    ax.set_xlabel("Column")
    ax.set_ylabel("Row")
    ax.legend(loc="upper right")
    ax.invert_yaxis()
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, filename), dpi=150)
    plt.close()


# ------------------------------------------------------------------
# 5. Velocity distribution bar chart
# ------------------------------------------------------------------

def plot_velocity_distribution(
    sku_df: pd.DataFrame,
    filename: str = "velocity_dist.png",
) -> None:
    _ensure_output_dir()
    fig, axes = plt.subplots(1, 2, figsize=(12, 4))

    # ABC distribution
    abc_counts = sku_df["abc_class"].value_counts().reindex(["A", "B", "C"])
    axes[0].bar(abc_counts.index, abc_counts.values, color=["#E63946", "#F4A261", "#2A9D8F"])
    axes[0].set_title("ABC Class Distribution")
    axes[0].set_ylabel("SKU Count")
    for i, v in enumerate(abc_counts.values):
        axes[0].text(i, v + 0.3, str(v), ha="center", fontsize=10)

    # Velocity score histogram
    axes[1].hist(sku_df["velocity_score"], bins=20, color="steelblue", edgecolor="white")
    axes[1].set_title("Velocity Score Distribution")
    axes[1].set_xlabel("Velocity Score")
    axes[1].set_ylabel("SKU Count")

    plt.suptitle("SKU Classification & Velocity Analysis", fontsize=13, fontweight="bold")
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, filename), dpi=150)
    plt.close()
