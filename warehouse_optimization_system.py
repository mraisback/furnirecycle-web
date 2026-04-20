"""
Backward-compatible CLI demo for the production-grade warehouse optimization stack.

This module now serves as:
1) Synthetic dataset generator
2) Local execution harness that uses warehouse_opt.optimizer classes
3) Artifact writer for mapping/metrics/heatmaps
"""

from __future__ import annotations

import random
from typing import Optional, Sequence, Tuple

import numpy as np
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt

from warehouse_opt.optimizer import (
    DataProcessor,
    RoutingEngine,
    SimulationConfig,
    Simulator,
    SlottingOptimizer,
)


def generate_warehouse_layout(
    width: int = 40,
    height: int = 24,
    rack_columns: Optional[Sequence[int]] = None,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if rack_columns is None:
        rack_columns = [x for x in range(2, width, 3)]

    dispatch = (0, 0)
    exit_point = (0, height - 1)

    nodes_df = pd.DataFrame([(x, y) for x in range(width) for y in range(height)], columns=["x", "y"])

    rows = []
    lid = 0
    for x in rack_columns:
        for y in range(1, height - 1):
            rows.append(
                {
                    "location_id": f"L{lid:06d}",
                    "x": x,
                    "y": y,
                    "zone": random.choices(["ambient", "cold", "hazmat"], [0.75, 0.2, 0.05])[0],
                    "volume_capacity": random.choice([90, 100, 110, 120]),
                    "weight_capacity": random.choice([60, 70, 80, 100]),
                }
            )
            lid += 1

    locations_df = pd.DataFrame(rows)
    meta_df = pd.DataFrame(
        [
            {"name": "dispatch", "x": dispatch[0], "y": dispatch[1]},
            {"name": "exit", "x": exit_point[0], "y": exit_point[1]},
        ]
    )
    return nodes_df, locations_df, meta_df


def generate_sku_master(n_skus: int = 1200) -> pd.DataFrame:
    rows = []
    for i in range(n_skus):
        hazardous = np.random.rand() < 0.04
        cold = np.random.rand() < 0.17
        required_zone = "hazmat" if hazardous else ("cold" if cold else "ambient")
        rows.append(
            {
                "sku_id": f"SKU{i:07d}",
                "volume": float(max(5, np.random.gamma(2.1, 10))),
                "weight": float(max(1, np.random.gamma(1.9, 6))),
                "fragile": bool(np.random.rand() < 0.18),
                "hazardous": bool(hazardous),
                "temp_sensitive": bool(cold),
                "required_zone": required_zone,
            }
        )
    return pd.DataFrame(rows)


def generate_order_demand(sku_df: pd.DataFrame, months: int = 9, avg_orders_per_day: int = 280) -> pd.DataFrame:
    sku_ids = sku_df["sku_id"].tolist()
    pop = np.array([1 / (i + 1) ** 0.85 for i in range(len(sku_ids))])
    pop = pop / pop.sum()

    rows = []
    order_seq = 0
    base_date = pd.Timestamp("2025-07-01")
    for day in range(months * 30):
        d = base_date + pd.Timedelta(days=day)
        n_orders = max(30, int(np.random.poisson(avg_orders_per_day)))
        for _ in range(n_orders):
            oid = f"O{order_seq:09d}"
            order_seq += 1
            n_lines = np.random.randint(1, 7)
            picks = np.random.choice(sku_ids, p=pop, replace=False, size=n_lines)
            for s in picks:
                rows.append({"order_id": oid, "order_date": d, "sku_id": s, "quantity": int(np.random.choice([1, 1, 2, 2, 3]))})
    return pd.DataFrame(rows)


def build_heatmap(assignment_df: pd.DataFrame, locations_df: pd.DataFrame, sku_features: pd.DataFrame, title: str, path: str) -> None:
    m = assignment_df.merge(locations_df, on="location_id").merge(sku_features[["sku_id", "velocity_score"]], on="sku_id", how="left")
    pivot = m.pivot_table(index="y", columns="x", values="velocity_score", aggfunc="mean")
    plt.figure(figsize=(12, 6))
    sns.heatmap(pivot.sort_index(ascending=False), cmap="YlOrRd")
    plt.title(title)
    plt.tight_layout()
    plt.savefig(path, dpi=120)
    plt.close()


def run_demo() -> None:
    nodes_df, locations_df, meta_df = generate_warehouse_layout()
    sku_df = generate_sku_master(n_skus=min(4000, len(locations_df) - 10))
    demand_df = generate_order_demand(sku_df)

    dispatch_xy = tuple(meta_df.loc[meta_df["name"] == "dispatch", ["x", "y"]].iloc[0])
    exit_xy = tuple(meta_df.loc[meta_df["name"] == "exit", ["x", "y"]].iloc[0])

    processor = DataProcessor(demand_df, sku_df)
    demand = processor.clean_demand_data()
    velocity = processor.compute_velocity()
    classes = processor.abc_xyz_classification(velocity)
    affinity = processor.compute_co_pick_affinity(min_pair_support=2)

    sku_features = sku_df.merge(classes, on="sku_id", how="left")
    sku_features["velocity_score"] = sku_features["velocity_score"].fillna(0.01)

    optimizer = SlottingOptimizer(locations_df, dispatch_xy)
    baseline = optimizer._solve_large_scale_greedy(sku_features.sample(frac=1.0, random_state=8))
    optimized = optimizer.optimize_assignments(sku_features)
    optimized = optimizer.greedy_copick_refinement(optimized, affinity)

    routing = RoutingEngine(nodes_df)
    sim = Simulator(routing, SimulationConfig(dispatch_xy=dispatch_xy, exit_xy=exit_xy, batch_size_orders=20))

    before = sim.evaluate(demand, baseline, locations_df)
    after = sim.evaluate(demand, optimized, locations_df)
    compare_df = sim.compare(before, after)

    build_heatmap(baseline, locations_df, sku_features, "Baseline Heatmap", "baseline_heatmap.png")
    build_heatmap(optimized, locations_df, sku_features, "Optimized Heatmap", "optimized_heatmap.png")

    optimized.to_csv("optimized_sku_location_mapping.csv", index=False)
    compare_df.to_csv("performance_comparison.csv", index=False)

    print(compare_df)


if __name__ == "__main__":
    run_demo()
