"""
DynamicReslotting: Weekly re-evaluation of slotting assignments.

Logic:
  1. Compute rolling 4-week velocity scores for each SKU.
  2. Compare current slot distance-to-dispatch vs ideal distance for
     its new velocity rank.
  3. Propose a swap list: pairs (sku_a, sku_b) where exchanging their
     locations reduces expected travel.
  4. Apply top-K swaps that pass constraint checks.

Also provides SKU co-affinity clustering: identifies SKUs frequently
ordered together and suggests grouping them in adjacent locations.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, List, Optional, Set, Tuple

import numpy as np
import pandas as pd
from itertools import combinations

from .data_processor import SKU, WarehouseLayout
from .slotting_optimizer import LocationSpec, SlottingOptimizer


class DynamicReslotting:
    """
    Analyses recent order data and proposes/applies incremental
    slotting improvements without a full re-optimization.
    """

    def __init__(
        self,
        layout: WarehouseLayout,
        skus: Dict[str, SKU],
        locations: List[LocationSpec],
        assignment: Dict[str, Tuple[int, int]],
    ):
        self.layout = layout
        self.skus = skus
        self.locations = locations
        self.assignment = assignment
        self._loc_map: Dict[Tuple[int, int], LocationSpec] = {
            l.position: l for l in locations
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def weekly_update(
        self,
        recent_orders: pd.DataFrame,
        window_weeks: int = 4,
        top_k_swaps: int = 20,
    ) -> Dict[str, object]:
        """
        Main entry: analyse recent_orders, compute updated velocities,
        propose and apply beneficial swaps.

        recent_orders must have columns: order_id, sku_id, qty, order_date.
        Returns a summary dict with swaps applied and new assignment.
        """
        updated_velocity = self._rolling_velocity(recent_orders, window_weeks)
        # Update SKU velocity scores in-place
        for sku_id, score in updated_velocity.items():
            if sku_id in self.skus:
                self.skus[sku_id].velocity_score = score

        swaps = self._propose_swaps()
        applied = self._apply_swaps(swaps[:top_k_swaps])

        co_clusters = self.cluster_co_ordered_skus(recent_orders)

        return {
            "updated_velocity_scores": updated_velocity,
            "swaps_proposed": len(swaps),
            "swaps_applied": len(applied),
            "applied_swaps": applied,
            "co_affinity_clusters": co_clusters,
            "new_assignment": self.assignment.copy(),
        }

    def cluster_co_ordered_skus(
        self,
        orders_df: pd.DataFrame,
        min_co_occurrence: int = 3,
    ) -> List[Set[str]]:
        """
        Identify groups of SKUs frequently ordered together using
        a simple co-occurrence graph + connected-components clustering.
        """
        co_count: Dict[Tuple[str, str], int] = defaultdict(int)
        for _, grp in orders_df.groupby("order_id")["sku_id"]:
            skus_in_order = list(grp.unique())
            for a, b in combinations(sorted(skus_in_order), 2):
                co_count[(a, b)] += 1

        # Build adjacency from strong co-occurrences
        adjacency: Dict[str, Set[str]] = defaultdict(set)
        for (a, b), cnt in co_count.items():
            if cnt >= min_co_occurrence:
                adjacency[a].add(b)
                adjacency[b].add(a)

        # Connected components = clusters
        visited: Set[str] = set()
        clusters: List[Set[str]] = []
        for sku in adjacency:
            if sku not in visited:
                cluster = self._bfs(adjacency, sku, visited)
                if len(cluster) > 1:
                    clusters.append(cluster)

        return clusters

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _rolling_velocity(
        self, orders_df: pd.DataFrame, weeks: int
    ) -> Dict[str, float]:
        """Return normalised velocity score per SKU over last N weeks."""
        orders_df = orders_df.copy()
        orders_df["order_date"] = pd.to_datetime(orders_df["order_date"])
        cutoff = orders_df["order_date"].max() - pd.Timedelta(weeks=weeks)
        recent = orders_df[orders_df["order_date"] >= cutoff]
        freq = recent.groupby("sku_id")["order_id"].nunique()
        max_f = freq.max() or 1
        return (freq / max_f).to_dict()

    def _propose_swaps(self) -> List[Tuple[str, str, float]]:
        """
        Score every pair of assigned SKUs: does swapping them reduce
        total weighted distance?  Return sorted list of (sku_a, sku_b, gain).
        """
        entry = self.layout.entry_exit
        assigned_skus = [
            self.skus[sid]
            for sid in self.assignment
            if sid in self.skus
        ]

        def weighted_dist(sku: SKU) -> float:
            pos = self.assignment.get(sku.sku_id)
            if pos is None:
                return 0.0
            return sku.velocity_score * self.layout.manhattan_distance(pos, entry)

        current_total = sum(weighted_dist(s) for s in assigned_skus)

        proposals: List[Tuple[str, str, float]] = []
        for i in range(len(assigned_skus)):
            for j in range(i + 1, len(assigned_skus)):
                a, b = assigned_skus[i], assigned_skus[j]
                pos_a = self.assignment[a.sku_id]
                pos_b = self.assignment[b.sku_id]
                # Gain from swapping a ↔ b
                old = (
                    a.velocity_score * self.layout.manhattan_distance(pos_a, entry)
                    + b.velocity_score * self.layout.manhattan_distance(pos_b, entry)
                )
                new = (
                    a.velocity_score * self.layout.manhattan_distance(pos_b, entry)
                    + b.velocity_score * self.layout.manhattan_distance(pos_a, entry)
                )
                gain = old - new
                if gain > 0.01:
                    proposals.append((a.sku_id, b.sku_id, gain))

        proposals.sort(key=lambda x: x[2], reverse=True)
        return proposals

    def _apply_swaps(
        self, swaps: List[Tuple[str, str, float]]
    ) -> List[Tuple[str, str, float]]:
        """Apply a list of (sku_a, sku_b, gain) swaps updating assignment and loc_map."""
        applied = []
        swapped: Set[str] = set()
        for sku_a_id, sku_b_id, gain in swaps:
            if sku_a_id in swapped or sku_b_id in swapped:
                continue
            if sku_a_id not in self.assignment or sku_b_id not in self.assignment:
                continue
            # Check zone compatibility after swap
            pos_a = self.assignment[sku_a_id]
            pos_b = self.assignment[sku_b_id]
            loc_a = self._loc_map[pos_a]
            loc_b = self._loc_map[pos_b]
            sku_a = self.skus[sku_a_id]
            sku_b = self.skus[sku_b_id]
            req_a = SlottingOptimizer._required_zone(sku_a)
            req_b = SlottingOptimizer._required_zone(sku_b)
            compat = SlottingOptimizer.ZONE_COMPAT
            if (
                req_a in compat.get(loc_b.zone, set())
                and req_b in compat.get(loc_a.zone, set())
            ):
                # Do the swap
                self.assignment[sku_a_id] = pos_b
                self.assignment[sku_b_id] = pos_a
                loc_a.sku_id = sku_b_id
                loc_b.sku_id = sku_a_id
                applied.append((sku_a_id, sku_b_id, gain))
                swapped.add(sku_a_id)
                swapped.add(sku_b_id)
        return applied

    @staticmethod
    def _bfs(adj: Dict[str, Set[str]], start: str, visited: Set[str]) -> Set[str]:
        cluster: Set[str] = set()
        queue = [start]
        while queue:
            node = queue.pop()
            if node in visited:
                continue
            visited.add(node)
            cluster.add(node)
            queue.extend(adj[node] - visited)
        return cluster
