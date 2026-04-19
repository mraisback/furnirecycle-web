"""
DataProcessor: Cleans demand data, classifies SKUs via ABC/XYZ analysis,
and computes pick velocity metrics used by downstream modules.
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class SKU:
    sku_id: str
    volume: float          # cubic metres
    weight: float          # kg
    fragile: bool = False
    hazardous: bool = False
    temperature_sensitive: bool = False
    # Populated by DataProcessor
    pick_frequency: int = 0
    revenue_contribution: float = 0.0
    abc_class: str = ""    # A / B / C
    xyz_class: str = ""    # X / Y / Z
    velocity_score: float = 0.0


@dataclass
class WarehouseLayout:
    """Rectangular grid warehouse with aisle gaps every `aisle_gap` columns."""
    rows: int
    cols: int
    aisle_gap: int = 4          # every N cols is an aisle (open column)
    entry_exit: Tuple[int, int] = (0, 0)   # (row, col) of dispatch point
    cell_size_m: float = 1.0    # metres per grid cell

    def __post_init__(self):
        self.locations: List[Tuple[int, int]] = [
            (r, c)
            for r in range(self.rows)
            for c in range(self.cols)
            if c % self.aisle_gap != 0   # aisles are not storage locations
        ]
        self.aisles: List[Tuple[int, int]] = [
            (r, c)
            for r in range(self.rows)
            for c in range(self.cols)
            if c % self.aisle_gap == 0
        ]

    @property
    def n_locations(self) -> int:
        return len(self.locations)

    def manhattan_distance(self, a: Tuple[int, int], b: Tuple[int, int]) -> float:
        return (abs(a[0] - b[0]) + abs(a[1] - b[1])) * self.cell_size_m


class DataProcessor:
    """
    Responsibilities:
    1. Ingest and clean order-level demand data.
    2. Compute per-SKU pick frequency and revenue contribution.
    3. Classify SKUs: ABC (revenue) × XYZ (demand variability).
    4. Produce a velocity score used by SlottingOptimizer.
    """

    # ABC thresholds: top 20 % of SKUs → A, next 30 % → B, rest → C
    ABC_THRESHOLDS = (0.20, 0.50)
    # XYZ thresholds by coefficient of variation (CV)
    XYZ_CV = (0.50, 1.00)   # CV < 0.5 → X (stable), < 1.0 → Y, else Z

    def __init__(self, layout: WarehouseLayout):
        self.layout = layout
        self.skus: Dict[str, SKU] = {}
        self.order_df: Optional[pd.DataFrame] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_skus(self, sku_records: List[dict]) -> None:
        """Load SKU master data (dimensions, constraints)."""
        for rec in sku_records:
            s = SKU(**rec)
            self.skus[s.sku_id] = s

    def load_orders(self, order_records: List[dict]) -> None:
        """
        order_records columns: order_id, sku_id, qty, unit_price, order_date.
        Dates should be ISO strings or datetime objects.
        """
        df = pd.DataFrame(order_records)
        df["order_date"] = pd.to_datetime(df["order_date"])
        df = df.dropna(subset=["order_id", "sku_id", "qty"])
        df = df[df["qty"] > 0]
        self.order_df = df
        self._compute_metrics()
        self._abc_classify()
        self._xyz_classify()
        self._compute_velocity()

    def get_classified_skus(self) -> pd.DataFrame:
        rows = [
            {
                "sku_id": s.sku_id,
                "pick_frequency": s.pick_frequency,
                "revenue_contribution": s.revenue_contribution,
                "abc_class": s.abc_class,
                "xyz_class": s.xyz_class,
                "velocity_score": s.velocity_score,
                "weight": s.weight,
                "volume": s.volume,
                "fragile": s.fragile,
                "hazardous": s.hazardous,
                "temperature_sensitive": s.temperature_sensitive,
            }
            for s in self.skus.values()
        ]
        return pd.DataFrame(rows).sort_values("velocity_score", ascending=False)

    # ------------------------------------------------------------------
    # Internal computation
    # ------------------------------------------------------------------

    def _compute_metrics(self) -> None:
        df = self.order_df
        freq = df.groupby("sku_id")["order_id"].nunique().rename("pick_frequency")
        revenue = (df["qty"] * df["unit_price"]).groupby(df["sku_id"]).sum().rename("revenue")
        summary = pd.concat([freq, revenue], axis=1).fillna(0)
        for sku_id, row in summary.iterrows():
            if sku_id in self.skus:
                self.skus[sku_id].pick_frequency = int(row["pick_frequency"])
                self.skus[sku_id].revenue_contribution = float(row["revenue"])

    def _abc_classify(self) -> None:
        """Pareto-based ABC classification on cumulative revenue."""
        items = sorted(self.skus.values(), key=lambda s: s.revenue_contribution, reverse=True)
        total_rev = sum(s.revenue_contribution for s in items) or 1.0
        cumulative = 0.0
        n = len(items)
        a_cut = self.ABC_THRESHOLDS[0] * n
        b_cut = self.ABC_THRESHOLDS[1] * n
        for i, s in enumerate(items):
            cumulative += s.revenue_contribution / total_rev
            if i < a_cut:
                s.abc_class = "A"
            elif i < b_cut:
                s.abc_class = "B"
            else:
                s.abc_class = "C"

    def _xyz_classify(self) -> None:
        """XYZ classification based on weekly demand coefficient of variation."""
        df = self.order_df.copy()
        df["week"] = df["order_date"].dt.isocalendar().week.astype(int)
        df["year"] = df["order_date"].dt.isocalendar().year.astype(int)
        weekly = df.groupby(["sku_id", "year", "week"])["qty"].sum().reset_index()
        stats = weekly.groupby("sku_id")["qty"].agg(["mean", "std"]).fillna(0)
        stats["cv"] = stats["std"] / (stats["mean"] + 1e-9)
        for sku_id, row in stats.iterrows():
            if sku_id not in self.skus:
                continue
            cv = row["cv"]
            if cv < self.XYZ_CV[0]:
                self.skus[sku_id].xyz_class = "X"
            elif cv < self.XYZ_CV[1]:
                self.skus[sku_id].xyz_class = "Y"
            else:
                self.skus[sku_id].xyz_class = "Z"
        # SKUs with no demand history → Z
        for s in self.skus.values():
            if not s.xyz_class:
                s.xyz_class = "Z"

    def _compute_velocity(self) -> None:
        """
        velocity_score ∈ [0, 1] — composite of normalised pick frequency
        and normalised revenue contribution.  Higher = place closer to dispatch.
        """
        freqs = np.array([s.pick_frequency for s in self.skus.values()], dtype=float)
        revs = np.array([s.revenue_contribution for s in self.skus.values()], dtype=float)
        norm_freq = freqs / (freqs.max() + 1e-9)
        norm_rev = revs / (revs.max() + 1e-9)
        scores = 0.6 * norm_freq + 0.4 * norm_rev
        for s, score in zip(self.skus.values(), scores):
            s.velocity_score = float(score)
