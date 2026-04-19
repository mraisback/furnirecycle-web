from __future__ import annotations

from datetime import datetime
import uuid

import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .db import JobEvent, OptimizationJob
from .optimizer import DataProcessor, RoutingEngine, SimulationConfig, Simulator, SlottingOptimizer
from .realtime import RealtimeHub
from .schemas import OptimizationRequest, OptimizationResult


class OptimizationService:
    def __init__(self, hub: RealtimeHub):
        self.hub = hub

    async def create_job(self, session: AsyncSession, payload: OptimizationRequest) -> str:
        job_id = str(uuid.uuid4())
        job = OptimizationJob(
            id=job_id,
            warehouse_id=payload.warehouse_id,
            status="queued",
            request_payload=payload.model_dump(mode="json"),
        )
        session.add(job)
        await session.commit()
        await self._record_event(session, job_id, "queued", {"message": "Job accepted"})
        return job_id

    async def run_job(self, session: AsyncSession, job_id: str) -> None:
        job = await session.get(OptimizationJob, job_id)
        if not job:
            return

        payload = OptimizationRequest.model_validate(job.request_payload)

        job.status = "running"
        await session.commit()
        await self._emit(session, job_id, "running", {"progress": 5, "message": "Starting optimization"})

        # Frames
        locations_df = pd.DataFrame([r.model_dump() for r in payload.locations])
        sku_df = pd.DataFrame([r.model_dump() for r in payload.skus])
        demand_df = pd.DataFrame([r.model_dump() for r in payload.order_lines])

        processor = DataProcessor(demand_df, sku_df)
        demand = processor.clean_demand_data()
        velocity = processor.compute_velocity()
        class_df = processor.abc_xyz_classification(velocity)
        affinity = processor.compute_co_pick_affinity(min_pair_support=2)
        sku_features = sku_df.merge(class_df, on="sku_id", how="left")
        sku_features["velocity_score"] = sku_features["velocity_score"].fillna(0.01)

        await self._emit(session, job_id, "running", {"progress": 35, "message": "Demand analytics complete"})

        # Baseline random assignment
        baseline = self._build_baseline(sku_features, locations_df)

        optimizer = SlottingOptimizer(locations_df, payload.dispatch_xy)
        optimized = optimizer.optimize_assignments(sku_features)
        optimized = optimizer.greedy_copick_refinement(optimized, affinity)

        await self._emit(session, job_id, "running", {"progress": 70, "message": "Slotting optimization complete"})

        # Routing + simulation
        max_x = int(max(locations_df["x"].max(), payload.dispatch_xy[0], payload.exit_xy[0]) + 1)
        max_y = int(max(locations_df["y"].max(), payload.dispatch_xy[1], payload.exit_xy[1]) + 1)
        nodes_df = pd.DataFrame([(x, y) for x in range(max_x + 1) for y in range(max_y + 1)], columns=["x", "y"])

        routing = RoutingEngine(nodes_df)
        sim = Simulator(
            routing,
            SimulationConfig(
                dispatch_xy=payload.dispatch_xy,
                exit_xy=payload.exit_xy,
                batch_size_orders=payload.batch_size_orders,
            ),
        )

        before = sim.evaluate(demand, baseline, locations_df)
        after = sim.evaluate(demand, optimized, locations_df)
        metrics = sim.compare(before, after)

        await self._emit(session, job_id, "running", {"progress": 92, "message": "Simulation complete"})

        result = {
            "job_id": job_id,
            "status": "completed",
            "created_at": job.created_at.isoformat(),
            "completed_at": datetime.utcnow().isoformat(),
            "optimized_mapping": optimized.to_dict(orient="records"),
            "metrics": metrics.to_dict(orient="records"),
            "diagnostics": {
                "num_skus": float(len(sku_df)),
                "num_locations": float(len(locations_df)),
                "num_orders": float(demand["order_id"].nunique()),
            },
        }

        job.status = "completed"
        job.completed_at = datetime.utcnow()
        job.result_payload = result
        await session.commit()

        await self._emit(session, job_id, "completed", {"progress": 100, "message": "Optimization finished"})

    async def get_result(self, session: AsyncSession, job_id: str) -> OptimizationResult | None:
        job = await session.get(OptimizationJob, job_id)
        if not job:
            return None
        payload = job.result_payload or {
            "job_id": job.id,
            "status": job.status,
            "created_at": job.created_at,
            "optimized_mapping": [],
            "metrics": [],
            "diagnostics": {},
        }
        return OptimizationResult.model_validate(payload)

    async def _record_event(self, session: AsyncSession, job_id: str, event_type: str, payload: dict) -> None:
        session.add(JobEvent(job_id=job_id, event_type=event_type, payload=payload))
        await session.commit()

    async def _emit(self, session: AsyncSession, job_id: str, event_type: str, payload: dict) -> None:
        await self._record_event(session, job_id, event_type, payload)
        await self.hub.publish(job_id, {"event": event_type, **payload})

    def _build_baseline(self, sku_df: pd.DataFrame, locations_df: pd.DataFrame) -> pd.DataFrame:
        loc_lookup = locations_df.set_index("location_id").to_dict("index")
        remaining = set(locations_df["location_id"])
        rows = []
        for _, sku in sku_df.iterrows():
            feasible = [
                l
                for l in remaining
                if loc_lookup[l]["zone"] == sku["required_zone"]
                and loc_lookup[l]["volume_capacity"] >= sku["volume"]
                and loc_lookup[l]["weight_capacity"] >= sku["weight"]
            ]
            if not feasible:
                feasible = list(remaining)
            chosen = feasible[0]
            remaining.remove(chosen)
            rows.append({"sku_id": sku["sku_id"], "location_id": chosen})
        return pd.DataFrame(rows)
