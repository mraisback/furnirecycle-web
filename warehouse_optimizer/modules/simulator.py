"""
Simulator (Digital Twin): Replays historical orders against a slotting
assignment + routing engine and reports throughput KPIs.

Metrics computed per simulation run:
  - total_distance_m    : sum of all picker route distances
  - mean_distance_m     : average distance per order
  - total_picks         : total number of SKU-line picks processed
  - throughput_orders_h : estimated orders per hour
  - throughput_picks_h  : estimated picks per hour

`compare` runs two simulations (baseline vs optimised) and returns the
delta / percentage improvement for each metric.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from .data_processor import WarehouseLayout
from .routing_engine import RoutingEngine, PickPoint


# Picker speed assumptions
WALK_SPEED_M_S = 1.2        # metres per second walking
PICK_TIME_S = 8.0           # seconds to physically pick one line item


@dataclass
class SimResult:
    label: str
    total_distance_m: float = 0.0
    mean_distance_m: float = 0.0
    total_picks: int = 0
    n_orders: int = 0
    total_time_s: float = 0.0
    throughput_orders_h: float = 0.0
    throughput_picks_h: float = 0.0
    per_order: List[Dict[str, Any]] = field(default_factory=list)

    def summary(self) -> pd.Series:
        return pd.Series({
            "label": self.label,
            "total_distance_m": round(self.total_distance_m, 1),
            "mean_distance_m": round(self.mean_distance_m, 1),
            "total_picks": self.total_picks,
            "n_orders": self.n_orders,
            "total_time_s": round(self.total_time_s, 1),
            "throughput_orders_h": round(self.throughput_orders_h, 2),
            "throughput_picks_h": round(self.throughput_picks_h, 2),
        })


class Simulator:
    """
    Replays order history through a given slotting + routing configuration.

    Usage:
        sim = Simulator(layout, orders_df)
        result_base  = sim.run(engine_baseline,  label="Baseline")
        result_optim = sim.run(engine_optimised, label="Optimised")
        comparison   = sim.compare(result_base, result_optim)
    """

    def __init__(self, layout: WarehouseLayout, orders_df: pd.DataFrame):
        self.layout = layout
        # Group orders: {order_id: [sku_id, ...]}
        self.orders: Dict[str, List[str]] = (
            orders_df.groupby("order_id")["sku_id"]
            .apply(list)
            .to_dict()
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(
        self,
        engine: RoutingEngine,
        label: str = "run",
        batch_size: int = 1,
    ) -> SimResult:
        """
        Simulate all orders.  batch_size=1 → individual picking;
        batch_size>1 → batch picking.
        """
        result = SimResult(label=label)
        t0 = time.perf_counter()

        if batch_size <= 1:
            self._run_individual(engine, result)
        else:
            self._run_batch(engine, result, batch_size)

        elapsed_wall = time.perf_counter() - t0
        result.total_time_s = result.total_distance_m / WALK_SPEED_M_S + result.total_picks * PICK_TIME_S
        result.n_orders = len(self.orders)
        if result.n_orders:
            result.mean_distance_m = result.total_distance_m / result.n_orders
        result.throughput_orders_h = (
            result.n_orders / result.total_time_s * 3600
            if result.total_time_s > 0 else 0
        )
        result.throughput_picks_h = (
            result.total_picks / result.total_time_s * 3600
            if result.total_time_s > 0 else 0
        )
        return result

    @staticmethod
    def compare(baseline: SimResult, optimised: SimResult) -> pd.DataFrame:
        """Return side-by-side comparison with % improvement."""
        metrics = [
            "total_distance_m",
            "mean_distance_m",
            "total_picks",
            "total_time_s",
            "throughput_orders_h",
            "throughput_picks_h",
        ]
        rows = []
        for m in metrics:
            b_val = getattr(baseline, m)
            o_val = getattr(optimised, m)
            if b_val != 0:
                pct = (o_val - b_val) / abs(b_val) * 100
            else:
                pct = 0.0
            rows.append({
                "metric": m,
                "baseline": round(b_val, 2),
                "optimised": round(o_val, 2),
                "delta": round(o_val - b_val, 2),
                "improvement_pct": round(pct, 1),
            })
        return pd.DataFrame(rows)

    # ------------------------------------------------------------------
    # Internal simulation loops
    # ------------------------------------------------------------------

    def _run_individual(self, engine: RoutingEngine, result: SimResult) -> None:
        for order_id, skus in self.orders.items():
            route, dist = engine.route_order(skus)
            picks = len(skus)
            result.total_distance_m += dist
            result.total_picks += picks
            result.per_order.append({
                "order_id": order_id,
                "distance_m": dist,
                "n_picks": picks,
                "n_stops": len(route),
            })

    def _run_batch(
        self, engine: RoutingEngine, result: SimResult, batch_size: int
    ) -> None:
        batch_results = engine.route_batch(self.orders, batch_size=batch_size)
        for batch_id, (route, dist) in batch_results.items():
            result.total_distance_m += dist
            # Count picks across all orders in the batch
            # (engine deduplicates positions but we want raw pick count)
        # Re-count picks from raw orders
        result.total_picks = sum(len(v) for v in self.orders.values())
        result.per_order = [
            {"batch_id": k, "distance_m": v[1], "n_stops": len(v[0])}
            for k, v in batch_results.items()
        ]
