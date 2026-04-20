# furnirecycle-web

## Production-Grade Warehouse Slotting & Routing Optimization

This repository now contains a production-ready Python architecture for AI-driven warehouse slotting and routing with:

- FastAPI API layer
- PostgreSQL persistence
- Real-time job progress streaming (WebSocket)
- Scalable optimization strategy for large warehouses (10,000+ SKUs)

## Project Structure

- `warehouse_opt/api.py` — FastAPI endpoints (`/v1/optimize`, `/v1/optimize/{job_id}`, WebSocket stream).
- `warehouse_opt/db.py` — PostgreSQL async SQLAlchemy models, engine, and sessions.
- `warehouse_opt/service.py` — orchestration service for job lifecycle and background execution.
- `warehouse_opt/realtime.py` — in-process real-time pub/sub hub for streaming updates.
- `warehouse_opt/optimizer.py` — core optimization engine (`DataProcessor`, `SlottingOptimizer`, `RoutingEngine`, `Simulator`).
- `warehouse_optimization_system.py` — CLI synthetic-data demo harness for offline benchmarking.
- `main.py` — ASGI entrypoint for deployment.

## Runtime Scalability Strategy

To handle 10,000+ SKUs efficiently:

1. **Hybrid slotting algorithm**
   - Uses exact MIP for smaller problems.
   - Automatically falls back to a large-scale greedy allocator with bounded candidate pools for very large SKU sets.

2. **Candidate pool pruning**
   - Limits feasible location candidates per SKU to nearest locations that satisfy constraints.

3. **Vectorized analytics**
   - Demand processing, velocity scoring, and ABC/XYZ calculations are done via pandas groupby operations.

4. **Route runtime optimization**
   - Uses single-source shortest path caching during nearest-neighbor route construction.

## Install Dependencies

```bash
pip install fastapi uvicorn sqlalchemy psycopg[binary] asyncpg pydantic-settings pandas numpy networkx pulp matplotlib seaborn
```

## Database Setup

Set your PostgreSQL connection string:

```bash
export WAREHOUSE_POSTGRES_DSN='postgresql+psycopg://warehouse:warehouse@localhost:5432/warehouse'
```

## Start API

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

## API Overview

### Create optimization job
`POST /v1/optimize`

Body contains:
- warehouse layout locations
- SKU master
- historical order lines
- dispatch/exit coordinates
- batch size

Returns:
- `job_id`
- initial status (`queued`)

### Get job result
`GET /v1/optimize/{job_id}`

Returns:
- status
- optimized mapping
- before/after KPI metrics
- diagnostics

### Real-time progress stream
`WS /v1/optimize/{job_id}/stream`

Receives JSON events (`queued`, `running`, `completed`) with progress percentages.

## CLI Demo (Synthetic Data)

```bash
python warehouse_optimization_system.py
```

Outputs:
- `optimized_sku_location_mapping.csv`
- `performance_comparison.csv`
- `baseline_heatmap.png`
- `optimized_heatmap.png`
