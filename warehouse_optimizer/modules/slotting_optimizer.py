"""
SlottingOptimizer: Assigns SKUs to warehouse locations to minimise total
expected travel distance, respecting capacity, weight, and zone constraints.

Strategy:
  Phase 1 – Greedy seed: rank locations by distance from dispatch (closest
             first) and SKUs by velocity_score (highest first), then pair them.
  Phase 2 – LP refinement: use PuLP to fine-tune assignments for a subset of
             high-impact SKUs when the solution space is tractable.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

import numpy as np
import pandas as pd

try:
    import pulp
    HAS_PULP = True
except ImportError:
    HAS_PULP = False

from .data_processor import SKU, WarehouseLayout


@dataclass
class LocationSpec:
    """Physical and operational properties of one storage bin."""
    position: Tuple[int, int]
    max_weight: float = 500.0   # kg
    max_volume: float = 2.0     # m³
    zone: str = "GENERAL"       # GENERAL | HAZMAT | COLD | FRAGILE
    sku_id: Optional[str] = None


class SlottingOptimizer:
    """
    Assigns SKUs to LocationSpecs in two phases:
      1. Greedy assignment ranked by velocity × distance priority.
      2. Optional LP swap-improvement for top-N SKUs.
    """

    # Class-level zone compatibility matrix
    ZONE_COMPAT: Dict[str, Set[str]] = {
        "GENERAL": {"GENERAL"},
        "HAZMAT": {"HAZMAT"},
        "COLD": {"COLD"},
        "FRAGILE": {"FRAGILE", "GENERAL"},
    }

    def __init__(self, layout: WarehouseLayout, skus: Dict[str, SKU]):
        self.layout = layout
        self.skus = skus
        self.locations: List[LocationSpec] = self._build_locations()
        self.assignment: Dict[str, Tuple[int, int]] = {}  # sku_id → position

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def optimize(self, use_lp: bool = True, lp_top_n: int = 50) -> Dict[str, Tuple[int, int]]:
        """Run greedy slotting followed by LP refinement."""
        self._greedy_assign()
        if use_lp and HAS_PULP:
            self._lp_refine(lp_top_n)
        return self.assignment

    def get_slot_dataframe(self) -> pd.DataFrame:
        rows = []
        for loc in self.locations:
            s = self.skus.get(loc.sku_id) if loc.sku_id else None
            rows.append({
                "row": loc.position[0],
                "col": loc.position[1],
                "zone": loc.zone,
                "sku_id": loc.sku_id or "",
                "abc_class": s.abc_class if s else "",
                "xyz_class": s.xyz_class if s else "",
                "velocity_score": s.velocity_score if s else 0.0,
                "dist_to_dispatch": self.layout.manhattan_distance(
                    loc.position, self.layout.entry_exit
                ),
            })
        return pd.DataFrame(rows)

    # ------------------------------------------------------------------
    # Location construction
    # ------------------------------------------------------------------

    def _build_locations(self) -> List[LocationSpec]:
        locs = []
        for pos in self.layout.locations:
            # Simple heuristic zoning: back rows → HAZMAT corner,
            # first two rows → FRAGILE, rest GENERAL.
            r, c = pos
            if r >= self.layout.rows - 2 and c < 4:
                zone = "HAZMAT"
            elif r <= 1:
                zone = "FRAGILE"
            else:
                zone = "GENERAL"
            locs.append(LocationSpec(position=pos, zone=zone))
        return locs

    # ------------------------------------------------------------------
    # Phase 1 – Greedy
    # ------------------------------------------------------------------

    def _greedy_assign(self) -> None:
        entry = self.layout.entry_exit
        # Sort locations: closest to dispatch first (ascending distance).
        locs_sorted = sorted(
            self.locations,
            key=lambda l: self.layout.manhattan_distance(l.position, entry),
        )
        # Sort SKUs: highest velocity first.
        skus_sorted = sorted(
            self.skus.values(),
            key=lambda s: s.velocity_score,
            reverse=True,
        )

        for sku in skus_sorted:
            required_zone = self._required_zone(sku)
            # Scan all locations for each SKU to avoid burning through the
            # location list when zone-incompatible slots are encountered.
            for loc in locs_sorted:
                if (
                    loc.sku_id is None
                    and loc.max_weight >= sku.weight
                    and loc.max_volume >= sku.volume
                    and required_zone in self.ZONE_COMPAT.get(loc.zone, set())
                ):
                    loc.sku_id = sku.sku_id
                    self.assignment[sku.sku_id] = loc.position
                    break

    # ------------------------------------------------------------------
    # Phase 2 – LP swap refinement
    # ------------------------------------------------------------------

    def _lp_refine(self, top_n: int) -> None:
        """
        For the top_n SKUs by velocity, solve a binary assignment LP that
        minimises sum(velocity_score[i] × distance[j] × x[i,j]).
        Only considers locations currently holding those top-N SKUs, so
        problem size stays manageable.
        """
        top_skus = sorted(
            [s for s in self.skus.values() if s.sku_id in self.assignment],
            key=lambda s: s.velocity_score,
            reverse=True,
        )[:top_n]

        if len(top_skus) < 2:
            return

        # Candidate locations = current slots of top-N SKUs.
        candidate_positions = [self.assignment[s.sku_id] for s in top_skus]
        loc_map: Dict[Tuple[int, int], LocationSpec] = {
            l.position: l for l in self.locations
        }
        entry = self.layout.entry_exit

        prob = pulp.LpProblem("slotting", pulp.LpMinimize)

        # x[i][j] = 1 if SKU i assigned to position j
        x = {
            (i, j): pulp.LpVariable(f"x_{i}_{j}", cat="Binary")
            for i in range(len(top_skus))
            for j in range(len(candidate_positions))
        }

        dist = [
            self.layout.manhattan_distance(candidate_positions[j], entry)
            for j in range(len(candidate_positions))
        ]

        # Objective: minimise weighted distance
        prob += pulp.lpSum(
            top_skus[i].velocity_score * dist[j] * x[(i, j)]
            for i in range(len(top_skus))
            for j in range(len(candidate_positions))
        )

        # Each SKU assigned exactly once
        for i in range(len(top_skus)):
            prob += pulp.lpSum(x[(i, j)] for j in range(len(candidate_positions))) == 1

        # Each location used at most once
        for j in range(len(candidate_positions)):
            prob += pulp.lpSum(x[(i, j)] for i in range(len(top_skus))) <= 1

        # Zone constraints
        for i, sku in enumerate(top_skus):
            req = self._required_zone(sku)
            for j, pos in enumerate(candidate_positions):
                loc_zone = loc_map[pos].zone
                if req not in self.ZONE_COMPAT.get(loc_zone, set()):
                    prob += x[(i, j)] == 0

        prob.solve(pulp.PULP_CBC_CMD(msg=0))

        if pulp.LpStatus[prob.status] == "Optimal":
            # Clear old assignments for top-N SKUs
            for sku in top_skus:
                old_pos = self.assignment[sku.sku_id]
                loc_map[old_pos].sku_id = None

            for i, sku in enumerate(top_skus):
                for j, pos in enumerate(candidate_positions):
                    if pulp.value(x[(i, j)]) and pulp.value(x[(i, j)]) > 0.5:
                        loc_map[pos].sku_id = sku.sku_id
                        self.assignment[sku.sku_id] = pos

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _required_zone(sku: SKU) -> str:
        if sku.hazardous:
            return "HAZMAT"
        if sku.temperature_sensitive:
            return "COLD"
        if sku.fragile:
            return "FRAGILE"
        return "GENERAL"
