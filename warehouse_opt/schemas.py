from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional, Tuple

from pydantic import BaseModel, Field


class Location(BaseModel):
    location_id: str
    x: int
    y: int
    zone: str
    volume_capacity: float
    weight_capacity: float


class SKU(BaseModel):
    sku_id: str
    volume: float
    weight: float
    fragile: bool = False
    hazardous: bool = False
    temp_sensitive: bool = False
    required_zone: str


class OrderLine(BaseModel):
    order_id: str
    order_date: datetime
    sku_id: str
    quantity: int = Field(gt=0)


class OptimizationRequest(BaseModel):
    warehouse_id: str
    dispatch_xy: Tuple[int, int]
    exit_xy: Tuple[int, int]
    locations: List[Location]
    skus: List[SKU]
    order_lines: List[OrderLine]
    batch_size_orders: int = 16


class JobAcceptedResponse(BaseModel):
    job_id: str
    status: str


class AssignmentRow(BaseModel):
    sku_id: str
    location_id: str


class MetricRow(BaseModel):
    metric: str
    before: float
    after: float
    pct_change: float


class OptimizationResult(BaseModel):
    job_id: str
    status: str
    created_at: datetime
    completed_at: Optional[datetime] = None
    optimized_mapping: List[AssignmentRow]
    metrics: List[MetricRow]
    diagnostics: Dict[str, float] = Field(default_factory=dict)
