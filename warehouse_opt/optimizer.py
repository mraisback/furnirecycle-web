from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Tuple
import math
import random

import networkx as nx
import numpy as np
import pandas as pd
from pulp import LpBinary, LpMinimize, LpProblem, LpVariable, PULP_CBC_CMD, lpSum, value

from .config import settings


class DataProcessor:
    def __init__(self, demand_df: pd.DataFrame, sku_df: pd.DataFrame):
        self.demand_df = demand_df.copy()
        self.sku_df = sku_df.copy()

    def clean_demand_data(self) -> pd.DataFrame:
        df = self.demand_df.copy()
        df["order_date"] = pd.to_datetime(df["order_date"], errors="coerce")
        df = df.dropna(subset=["order_id", "order_date", "sku_id", "quantity"])
        df = df[df["quantity"] > 0]
        df = df[df["sku_id"].isin(set(self.sku_df["sku_id"]))]
        self.demand_df = df.sort_values(["order_date", "order_id"]).reset_index(drop=True)
        return self.demand_df

    def compute_velocity(self) -> pd.DataFrame:
        df = self.demand_df
        span_days = max(1, (df["order_date"].max() - df["order_date"].min()).days + 1)
        out = (
            df.groupby("sku_id")
            .agg(order_lines=("order_id", "count"), unique_orders=("order_id", "nunique"), total_qty=("quantity", "sum"))
            .reset_index()
        )
        out["pick_frequency_per_day"] = out["order_lines"] / span_days
        out["order_frequency_per_day"] = out["unique_orders"] / span_days
        out["velocity_score"] = 0.55 * out["pick_frequency_per_day"] + 0.45 * out["order_frequency_per_day"]
        return out

    def abc_xyz_classification(self, velocity_df: pd.DataFrame) -> pd.DataFrame:
        df = velocity_df.sort_values("total_qty", ascending=False).copy()
        df["demand_share"] = df["total_qty"] / max(1, df["total_qty"].sum())
        df["cum_share"] = df["demand_share"].cumsum()
        df["abc_class"] = np.where(df["cum_share"] <= 0.8, "A", np.where(df["cum_share"] <= 0.95, "B", "C"))

        weekly = self.demand_df.assign(year_week=self.demand_df["order_date"].dt.strftime("%Y-%W"))
        weekly = weekly.groupby(["sku_id", "year_week"]) ["quantity"].sum().reset_index(name="weekly_qty")
        var = weekly.groupby("sku_id")["weekly_qty"].agg(["mean", "std"]).reset_index()
        var["cv"] = var["std"].fillna(0) / var["mean"].replace(0, np.nan)
        var["cv"] = var["cv"].replace([np.inf, -np.inf], np.nan).fillna(0)
        var["xyz_class"] = np.where(var["cv"] <= 0.5, "X", np.where(var["cv"] <= 1.0, "Y", "Z"))

        return df.merge(var[["sku_id", "cv", "xyz_class"]], on="sku_id", how="left")

    def compute_co_pick_affinity(self, min_pair_support: int = 3) -> pd.DataFrame:
        order_groups = self.demand_df.groupby("order_id")["sku_id"].apply(lambda x: sorted(set(x))).tolist()
        pair_counts: Dict[Tuple[str, str], int] = {}
        sku_counts: Dict[str, int] = {}

        for sku_list in order_groups:
            for sku in sku_list:
                sku_counts[sku] = sku_counts.get(sku, 0) + 1
            for i in range(len(sku_list)):
                for j in range(i + 1, len(sku_list)):
                    pair = (sku_list[i], sku_list[j])
                    pair_counts[pair] = pair_counts.get(pair, 0) + 1

        rows = []
        total_orders = max(1, len(order_groups))
        for (a, b), c in pair_counts.items():
            if c < min_pair_support:
                continue
            rows.append(
                {
                    "sku_a": a,
                    "sku_b": b,
                    "pair_orders": c,
                    "support": c / total_orders,
                    "affinity": 0.5 * (c / max(1, sku_counts[a]) + c / max(1, sku_counts[b])),
                }
            )

        return pd.DataFrame(rows).sort_values(["affinity", "pair_orders"], ascending=False) if rows else pd.DataFrame()


class SlottingOptimizer:
    """
    Production-oriented slotting strategy:
    - For <= max_skus_for_exact_mip: solve constrained MIP assignment.
    - For larger cases: scalable greedy heuristic with candidate pools and vectorized scoring.
    """

    def __init__(self, locations_df: pd.DataFrame, dispatch_xy: Tuple[int, int]):
        self.locations_df = locations_df.copy()
        self.dispatch_xy = dispatch_xy
        self.locations_df["distance_to_dispatch"] = (
            (self.locations_df["x"] - dispatch_xy[0]).abs() + (self.locations_df["y"] - dispatch_xy[1]).abs()
        )

    def _candidate_locations(self, sku_row: pd.Series) -> pd.DataFrame:
        loc = self.locations_df
        out = loc[(loc["volume_capacity"] >= sku_row["volume"]) & (loc["weight_capacity"] >= sku_row["weight"])]
        req = sku_row["required_zone"]
        out = out[out["zone"] == req]
        return out.nsmallest(settings.candidate_pool_per_sku, "distance_to_dispatch")

    def optimize_assignments(self, sku_features_df: pd.DataFrame) -> pd.DataFrame:
        if len(sku_features_df) <= settings.max_skus_for_exact_mip:
            return self._solve_mip(sku_features_df)
        return self._solve_large_scale_greedy(sku_features_df)

    def _solve_mip(self, sku_features_df: pd.DataFrame) -> pd.DataFrame:
        sku_df = sku_features_df.copy()
        candidate_map = {}
        for _, row in sku_df.iterrows():
            cands = self._candidate_locations(row)
            candidate_map[row["sku_id"]] = cands["location_id"].tolist()
        if any(len(v) == 0 for v in candidate_map.values()):
            return self._solve_large_scale_greedy(sku_df)

        loc_dist = self.locations_df.set_index("location_id")["distance_to_dispatch"].to_dict()
        velocity = sku_df.set_index("sku_id")["velocity_score"].fillna(0.01).to_dict()

        prob = LpProblem("slotting", LpMinimize)
        x: Dict[Tuple[str, str], LpVariable] = {}
        for sku, locs in candidate_map.items():
            for loc in locs:
                x[(sku, loc)] = LpVariable(f"x_{sku}_{loc}", cat=LpBinary)

        prob += lpSum((velocity[sku] + 1e-6) * loc_dist[loc] * var for (sku, loc), var in x.items())

        for sku, locs in candidate_map.items():
            prob += lpSum(x[(sku, loc)] for loc in locs) == 1
        for loc in self.locations_df["location_id"]:
            vars_for_loc = [x[(sku, loc)] for sku, locs in candidate_map.items() if loc in locs]
            if vars_for_loc:
                prob += lpSum(vars_for_loc) <= 1

        prob.solve(PULP_CBC_CMD(msg=False, timeLimit=settings.max_solver_seconds))

        rows = [{"sku_id": sku, "location_id": loc} for (sku, loc), var in x.items() if value(var) and value(var) > 0.5]
        out = pd.DataFrame(rows)
        if len(out) != len(sku_df):
            return self._solve_large_scale_greedy(sku_df)
        return out

    def _solve_large_scale_greedy(self, sku_features_df: pd.DataFrame) -> pd.DataFrame:
        """Scalable assignment: O(S log S + L log L) using sorted feasible pools."""
        sku_df = sku_features_df.copy().sort_values("velocity_score", ascending=False)

        available = {
            zone: self.locations_df[self.locations_df["zone"] == zone]
            .sort_values("distance_to_dispatch")
            .copy()
            for zone in self.locations_df["zone"].unique()
        }
        used = set()
        rows = []

        for _, sku in sku_df.iterrows():
            zone_locs = available.get(sku["required_zone"], pd.DataFrame())
            if zone_locs.empty:
                continue

            feasible = zone_locs[
                (zone_locs["volume_capacity"] >= sku["volume"])
                & (zone_locs["weight_capacity"] >= sku["weight"])
                & (~zone_locs["location_id"].isin(used))
            ]
            if feasible.empty:
                continue
            loc_id = feasible.iloc[0]["location_id"]
            used.add(loc_id)
            rows.append({"sku_id": sku["sku_id"], "location_id": loc_id})

        out = pd.DataFrame(rows)
        if len(out) < len(sku_df):
            # fill leftovers from any not-used location to guarantee total assignment where possible
            remaining_skus = [s for s in sku_df["sku_id"] if s not in set(out["sku_id"])]
            all_unused = [l for l in self.locations_df["location_id"] if l not in used]
            for sku, loc in zip(remaining_skus, all_unused):
                out = pd.concat([out, pd.DataFrame([{"sku_id": sku, "location_id": loc}])], ignore_index=True)
        return out

    def greedy_copick_refinement(self, assignment_df: pd.DataFrame, affinity_df: pd.DataFrame, max_swaps: int = 1500) -> pd.DataFrame:
        if affinity_df.empty:
            return assignment_df

        loc_map = assignment_df.set_index("sku_id")["location_id"].to_dict()
        loc_xy = self.locations_df.set_index("location_id")[["x", "y"]].to_dict("index")
        skus = list(loc_map.keys())
        swaps = 0

        def pair_dist(a: str, b: str) -> int:
            p1 = loc_xy[loc_map[a]]
            p2 = loc_xy[loc_map[b]]
            return abs(p1["x"] - p2["x"]) + abs(p1["y"] - p2["y"])

        for _, row in affinity_df.head(5000).iterrows():
            if swaps >= max_swaps:
                break
            a, b = row["sku_a"], row["sku_b"]
            if a not in loc_map or b not in loc_map:
                continue
            if pair_dist(a, b) <= 2:
                continue
            candidates = random.sample(skus, min(30, len(skus)))
            best = (None, 0.0)
            for c in candidates:
                if c in (a, b):
                    continue
                before = pair_dist(a, b)
                loc_map[a], loc_map[c] = loc_map[c], loc_map[a]
                after = pair_dist(a, b)
                gain = before - after
                loc_map[a], loc_map[c] = loc_map[c], loc_map[a]
                if gain > best[1]:
                    best = (c, gain)
            if best[0] is not None and best[1] > 0:
                c = best[0]
                loc_map[a], loc_map[c] = loc_map[c], loc_map[a]
                swaps += 1

        return pd.DataFrame([{"sku_id": k, "location_id": v} for k, v in loc_map.items()])


class RoutingEngine:
    def __init__(self, nodes_df: pd.DataFrame, blocked_cells: Iterable[Tuple[int, int]] | None = None):
        blocked = set(blocked_cells or [])
        coords = [tuple(v) for v in nodes_df[["x", "y"]].to_numpy().tolist()]
        allowed = [c for c in coords if c not in blocked]
        allowed_set = set(allowed)

        g = nx.Graph()
        g.add_nodes_from(allowed)
        for x, y in allowed:
            for n in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if n in allowed_set:
                    g.add_edge((x, y), n, weight=1)
        self.graph = g

    def _shortest_path_length_cached(self, start: Tuple[int, int], targets: List[Tuple[int, int]]) -> Dict[Tuple[int, int], float]:
        lengths = nx.single_source_dijkstra_path_length(self.graph, start, weight="weight")
        return {t: lengths[t] for t in targets if t in lengths}

    def route_multi_pick(self, start: Tuple[int, int], end: Tuple[int, int], picks: List[Tuple[int, int]]) -> float:
        remaining = list(dict.fromkeys(picks))
        current = start
        dist = 0.0
        while remaining:
            all_d = self._shortest_path_length_cached(current, remaining)
            nxt = min(all_d.items(), key=lambda x: x[1])[0]
            dist += all_d[nxt]
            current = nxt
            remaining.remove(nxt)
        if current != end:
            dist += nx.shortest_path_length(self.graph, current, end, weight="weight")
        return dist

    def optimize_batch_routes(
        self,
        demand_df: pd.DataFrame,
        sku_to_xy: Dict[str, Tuple[int, int]],
        start_xy: Tuple[int, int],
        end_xy: Tuple[int, int],
        batch_size_orders: int,
    ) -> pd.DataFrame:
        order_skus = demand_df.groupby("order_id")["sku_id"].apply(list).tolist()
        rows = []
        for i in range(0, len(order_skus), batch_size_orders):
            chunk = order_skus[i : i + batch_size_orders]
            picks = [sku_to_xy[s] for order in chunk for s in order if s in sku_to_xy]
            dist = self.route_multi_pick(start_xy, end_xy, picks)
            rows.append({"batch_id": i // batch_size_orders, "travel_distance": dist, "picks": len(picks), "orders": len(chunk)})
        return pd.DataFrame(rows)


@dataclass
class SimulationConfig:
    dispatch_xy: Tuple[int, int]
    exit_xy: Tuple[int, int]
    walking_speed_mps: float = 1.3
    pick_time_sec: float = 5.2
    batch_size_orders: int = 16


class Simulator:
    def __init__(self, routing_engine: RoutingEngine, config: SimulationConfig):
        self.routing_engine = routing_engine
        self.config = config

    def evaluate(self, demand_df: pd.DataFrame, assignment_df: pd.DataFrame, locations_df: pd.DataFrame) -> Dict[str, float]:
        loc_xy = locations_df.set_index("location_id")[["x", "y"]].to_dict("index")
        sku_to_xy = {
            sku: (loc_xy[loc]["x"], loc_xy[loc]["y"])
            for sku, loc in assignment_df.set_index("sku_id")["location_id"].to_dict().items()
            if loc in loc_xy
        }
        batch = self.routing_engine.optimize_batch_routes(
            demand_df,
            sku_to_xy,
            self.config.dispatch_xy,
            self.config.exit_xy,
            self.config.batch_size_orders,
        )
        total_dist = float(batch["travel_distance"].sum())
        total_picks = int(batch["picks"].sum())
        total_time = total_dist / max(self.config.walking_speed_mps, 0.1) + total_picks * self.config.pick_time_sec
        throughput = demand_df["order_id"].nunique() / (total_time / 3600) if total_time > 0 else 0
        return {
            "total_travel_distance": total_dist,
            "total_picks": float(total_picks),
            "total_time_sec": total_time,
            "throughput_orders_per_hour": float(throughput),
        }

    @staticmethod
    def compare(before: Dict[str, float], after: Dict[str, float]) -> pd.DataFrame:
        rows = []
        for metric in before:
            b, a = before[metric], after[metric]
            pct = ((a - b) / b * 100) if b else np.nan
            rows.append({"metric": metric, "before": b, "after": a, "pct_change": pct})
        return pd.DataFrame(rows)
