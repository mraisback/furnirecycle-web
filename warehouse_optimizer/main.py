"""
main.py – End-to-end warehouse optimization pipeline.

Run:
    python -m warehouse_optimizer.main

Outputs (saved to warehouse_optimizer/outputs/):
    warehouse_heatmap.png   – velocity heatmap (post-optimization)
    abc_xyz_matrix.png      – ABC×XYZ bubble chart
    comparison_bar.png      – before vs after KPI bars
    route_sample.png        – sample picker route
    velocity_dist.png       – velocity score distribution
    slot_assignments.csv    – full SKU→location mapping
    simulation_comparison.csv
"""

import os
import sys

# Allow running from repo root as  python -m warehouse_optimizer.main
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pandas as pd

from warehouse_optimizer.data.synthetic_generator import generate_skus, generate_orders
from warehouse_optimizer.modules.data_processor import DataProcessor, WarehouseLayout
from warehouse_optimizer.modules.slotting_optimizer import SlottingOptimizer
from warehouse_optimizer.modules.routing_engine import RoutingEngine
from warehouse_optimizer.modules.simulator import Simulator
from warehouse_optimizer.modules.dynamic_reslotting import DynamicReslotting
from warehouse_optimizer.modules.visualizer import (
    plot_warehouse_heatmap,
    plot_abc_xyz_matrix,
    plot_comparison,
    plot_sample_route,
    plot_velocity_distribution,
)

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "outputs")
os.makedirs(OUTPUT_DIR, exist_ok=True)


def main():
    print("=" * 65)
    print("  Warehouse Slotting & Routing Optimization System")
    print("=" * 65)

    # ----------------------------------------------------------------
    # 1. Define warehouse layout
    # ----------------------------------------------------------------
    print("\n[1] Building warehouse layout (20 rows × 24 cols, aisle every 4 cols)...")
    layout = WarehouseLayout(rows=20, cols=24, aisle_gap=4, entry_exit=(0, 0), cell_size_m=1.5)
    print(f"    Storage locations: {layout.n_locations}")

    # ----------------------------------------------------------------
    # 2. Generate synthetic data
    # ----------------------------------------------------------------
    print("[2] Generating synthetic dataset (200 SKUs, ~3000 orders)...")
    sku_records = generate_skus(n=200)
    order_records = generate_orders(
        sku_ids=[s["sku_id"] for s in sku_records],
        n_orders=3000,
    )
    print(f"    Order lines generated: {len(order_records)}")

    # ----------------------------------------------------------------
    # 3. Data processing & classification
    # ----------------------------------------------------------------
    print("[3] Running DataProcessor (ABC/XYZ classification + velocity)...")
    processor = DataProcessor(layout)
    processor.load_skus(sku_records)
    processor.load_orders(order_records)
    sku_df = processor.get_classified_skus()

    a_count = (sku_df["abc_class"] == "A").sum()
    b_count = (sku_df["abc_class"] == "B").sum()
    c_count = (sku_df["abc_class"] == "C").sum()
    print(f"    ABC classes → A:{a_count}  B:{b_count}  C:{c_count}")
    print(f"    XYZ classes → ", end="")
    for cls in ["X", "Y", "Z"]:
        print(f"{cls}:{(sku_df['xyz_class'] == cls).sum()}  ", end="")
    print()

    # ----------------------------------------------------------------
    # 4. Baseline slotting (random assignment) for comparison
    # ----------------------------------------------------------------
    print("[4] Creating BASELINE slotting (random)...")
    import random, copy
    random.seed(0)
    baseline_skus = copy.deepcopy(processor.skus)
    baseline_optimizer = SlottingOptimizer(layout, baseline_skus)
    # Random: shuffle SKUs so velocity ordering is broken
    shuffled_locs = list(layout.locations)
    random.shuffle(shuffled_locs)
    baseline_assignment: dict = {}
    for i, sku in enumerate(baseline_skus.values()):
        if i < len(shuffled_locs):
            baseline_assignment[sku.sku_id] = shuffled_locs[i]

    baseline_engine = RoutingEngine(layout, baseline_assignment)

    # ----------------------------------------------------------------
    # 5. Optimized slotting
    # ----------------------------------------------------------------
    print("[5] Running SlottingOptimizer (greedy + LP refinement)...")
    opt_optimizer = SlottingOptimizer(layout, processor.skus)
    optimized_assignment = opt_optimizer.optimize(use_lp=True, lp_top_n=40)
    print(f"    SKUs assigned: {len(optimized_assignment)}")

    slot_df = opt_optimizer.get_slot_dataframe()
    slot_df.to_csv(os.path.join(OUTPUT_DIR, "slot_assignments.csv"), index=False)
    print(f"    Slot assignments saved → outputs/slot_assignments.csv")

    # ----------------------------------------------------------------
    # 6. Build routing engines
    # ----------------------------------------------------------------
    print("[6] Building RoutingEngine (Dijkstra on grid graph)...")
    optimized_engine = RoutingEngine(layout, optimized_assignment)

    # ----------------------------------------------------------------
    # 7. Simulation (digital twin)
    # ----------------------------------------------------------------
    print("[7] Running Digital Twin Simulation...")
    orders_df = pd.DataFrame(order_records)

    # Use a subset (last 500 orders) for simulation speed
    recent_order_ids = (
        orders_df.sort_values("order_date").tail(2000)["order_id"].unique()[:500]
    )
    sim_orders = orders_df[orders_df["order_id"].isin(recent_order_ids)]

    simulator = Simulator(layout, sim_orders)

    print("    Simulating baseline (individual picking)...")
    result_baseline = simulator.run(baseline_engine, label="Baseline", batch_size=1)

    print("    Simulating optimized (batch picking, batch_size=5)...")
    result_optimized = simulator.run(optimized_engine, label="Optimised", batch_size=5)

    comparison_df = Simulator.compare(result_baseline, result_optimized)
    comparison_df.to_csv(
        os.path.join(OUTPUT_DIR, "simulation_comparison.csv"), index=False
    )

    print("\n    --- Simulation Results ---")
    print(comparison_df.to_string(index=False))

    # ----------------------------------------------------------------
    # 8. Dynamic re-slotting
    # ----------------------------------------------------------------
    print("\n[8] Running DynamicReslotting (weekly update simulation)...")
    # Simulate a "new week" of orders as recent data
    recent_week_orders = orders_df.sample(n=200, random_state=99)
    reslotter = DynamicReslotting(
        layout,
        processor.skus,
        opt_optimizer.locations,
        optimized_assignment,
    )
    reslot_result = reslotter.weekly_update(recent_week_orders, window_weeks=4, top_k_swaps=15)
    print(f"    Swaps proposed: {reslot_result['swaps_proposed']}")
    print(f"    Swaps applied:  {reslot_result['swaps_applied']}")
    n_clusters = len(reslot_result["co_affinity_clusters"])
    print(f"    Co-affinity clusters found: {n_clusters}")
    if n_clusters:
        biggest = max(reslot_result["co_affinity_clusters"], key=len)
        print(f"    Largest cluster ({len(biggest)} SKUs): {list(biggest)[:5]}...")

    # ----------------------------------------------------------------
    # 9. Visualizations
    # ----------------------------------------------------------------
    print("\n[9] Generating visualizations...")

    plot_warehouse_heatmap(layout, slot_df, title="Optimised SKU Velocity Heatmap")
    print("    warehouse_heatmap.png")

    plot_abc_xyz_matrix(sku_df)
    print("    abc_xyz_matrix.png")

    plot_comparison(result_baseline, result_optimized)
    print("    comparison_bar.png")

    # Sample route: pick the highest-frequency order
    top_order_id = (
        orders_df.groupby("order_id")["sku_id"]
        .count()
        .idxmax()
    )
    top_order_skus = orders_df[orders_df["order_id"] == top_order_id]["sku_id"].tolist()
    sample_route, sample_dist = optimized_engine.route_order(top_order_skus)
    plot_sample_route(
        layout,
        sample_route,
        optimized_assignment,
        title=f"Optimised Route — {top_order_id} ({len(top_order_skus)} SKUs, {sample_dist:.1f} m)",
    )
    print("    route_sample.png")

    plot_velocity_distribution(sku_df)
    print("    velocity_dist.png")

    # ----------------------------------------------------------------
    # 10. Summary
    # ----------------------------------------------------------------
    print("\n" + "=" * 65)
    print("  OPTIMISATION SUMMARY")
    print("=" * 65)
    for _, row in comparison_df.iterrows():
        direction = "↓" if row["improvement_pct"] < 0 else "↑"
        print(
            f"  {row['metric']:<30} "
            f"Baseline: {row['baseline']:>10.1f}  "
            f"Optimised: {row['optimised']:>10.1f}  "
            f"{direction} {abs(row['improvement_pct']):.1f}%"
        )
    print("=" * 65)
    print(f"\nAll outputs saved to:  {OUTPUT_DIR}/")
    print("Done.")


if __name__ == "__main__":
    main()
