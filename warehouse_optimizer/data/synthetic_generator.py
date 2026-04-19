"""
Generates a realistic synthetic dataset:
  - 200 SKUs with varying dimensions, weight, constraints
  - 9 months of order history (≈ 3 000 orders)
  - Pareto demand distribution (20 % of SKUs drive 80 % of picks)
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta
from typing import Dict, List, Tuple

import numpy as np


RNG = np.random.default_rng(42)
random.seed(42)


def generate_skus(n: int = 200) -> List[dict]:
    skus = []
    for i in range(n):
        sku_id = f"SKU-{i:04d}"
        # Most SKUs are small, a few are large
        volume = float(RNG.lognormal(mean=-1.5, sigma=0.8))
        weight = float(RNG.lognormal(mean=1.0, sigma=0.7))
        fragile = random.random() < 0.08
        hazardous = (not fragile) and random.random() < 0.05
        temp_sensitive = (not fragile) and (not hazardous) and random.random() < 0.04
        skus.append(
            dict(
                sku_id=sku_id,
                volume=round(min(volume, 4.0), 3),
                weight=round(min(weight, 400.0), 2),
                fragile=fragile,
                hazardous=hazardous,
                temperature_sensitive=temp_sensitive,
            )
        )
    return skus


def generate_orders(
    sku_ids: List[str],
    n_orders: int = 3000,
    start_date: str = "2024-07-01",
    end_date: str = "2025-03-31",
) -> List[dict]:
    """
    Pareto demand: top 20 % of SKUs have 4× higher pick probability.
    Each order picks 1–8 SKUs.
    """
    n_skus = len(sku_ids)
    n_hot = max(1, n_skus // 5)
    hot_skus = sku_ids[:n_hot]
    cold_skus = sku_ids[n_hot:]

    # Probability weights: hot SKUs 4× more likely
    weights = np.array([4.0] * len(hot_skus) + [1.0] * len(cold_skus))
    weights /= weights.sum()

    start = datetime.fromisoformat(start_date)
    end = datetime.fromisoformat(end_date)
    span_days = (end - start).days

    records = []
    for order_idx in range(n_orders):
        order_id = f"ORD-{order_idx:06d}"
        n_lines = RNG.integers(1, 9)
        chosen = RNG.choice(sku_ids, size=n_lines, replace=False, p=weights)
        order_date = (start + timedelta(days=int(RNG.integers(0, span_days)))).date().isoformat()
        for sku_id in chosen:
            qty = int(RNG.integers(1, 11))
            unit_price = round(float(RNG.lognormal(mean=3.5, sigma=0.9)), 2)
            records.append(
                dict(
                    order_id=order_id,
                    sku_id=sku_id,
                    qty=qty,
                    unit_price=unit_price,
                    order_date=order_date,
                )
            )
    return records
