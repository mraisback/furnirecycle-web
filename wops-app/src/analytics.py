"""Analytics helpers — date filtering, time-series trends, customer / product /
vendor breakdowns.

All functions are defensive: they accept None / empty frames and missing columns
and always return an empty (but correctly-shaped) DataFrame or a neutral value
instead of raising. They operate on the *transformed* frames produced by
``transformer.build_all_dataframes`` (column names like Order_Date,
Cases_Ordered, Customer, SKU, Despatch_Date, Cases_Despatched, Return_Date,
Returned_Cases, Damage_Category, …).
"""
from typing import List, Optional, Tuple

import numpy as np
import pandas as pd


# ── Date helpers ──────────────────────────────────────────────────────────────
def date_bounds(specs: List[Tuple[Optional[pd.DataFrame], str]]):
    """Return (min_date, max_date) as python ``date`` objects across every
    (df, column) pair supplied, or (None, None) when no dates are present."""
    mins, maxs = [], []
    for df, col in specs:
        if df is None or getattr(df, "empty", True) or col not in df.columns:
            continue
        s = pd.to_datetime(df[col], errors="coerce").dropna()
        if not s.empty:
            mins.append(s.min())
            maxs.append(s.max())
    if not mins:
        return None, None
    return min(mins).date(), max(maxs).date()


def filter_by_date(df: Optional[pd.DataFrame], col: str, start, end):
    """Keep rows whose ``col`` falls within [start, end] (inclusive).

    * Returns ``df`` unchanged when the frame/column is unusable or when the
      column holds no parseable dates (so a frame that simply lacks a date does
      not silently vanish from the dashboard).
    """
    if df is None or df.empty or col not in df.columns or start is None or end is None:
        return df
    s = pd.to_datetime(df[col], errors="coerce")
    if s.notna().sum() == 0:
        return df
    start_ts = pd.Timestamp(start)
    end_ts = pd.Timestamp(end) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
    mask = s.notna() & (s >= start_ts) & (s <= end_ts)
    return df[mask]


# ── Time-series trends ────────────────────────────────────────────────────────
def monthly_trend(df: Optional[pd.DataFrame], date_col: str, value_col: str,
                  freq: str = "MS", label: Optional[str] = None) -> pd.DataFrame:
    """Aggregate ``value_col`` by calendar period.

    freq: ``"MS"`` (month start, default), ``"W"`` (weekly), ``"D"`` (daily).
    Returns columns ``["Period", <label or value_col>]``.
    """
    out_name = label or value_col
    if df is None or df.empty or date_col not in df.columns:
        return pd.DataFrame(columns=["Period", out_name])
    d = pd.DataFrame()
    d["__d"] = pd.to_datetime(df[date_col], errors="coerce")
    if value_col in df.columns:
        d["__v"] = pd.to_numeric(df[value_col], errors="coerce").fillna(0)
    else:
        d["__v"] = 1.0
    d = d.dropna(subset=["__d"])
    if d.empty:
        return pd.DataFrame(columns=["Period", out_name])
    res = d.set_index("__d").resample(freq)["__v"].sum().reset_index()
    res.columns = ["Period", out_name]
    return res


def combined_trend(orders, despatch, returns, freq: str = "MS") -> pd.DataFrame:
    """Merge cases-ordered, cases-dispatched and returned-cases onto one period
    axis for a single multi-series line chart."""
    o = monthly_trend(orders,   "Order_Date",    "Cases_Ordered",   freq, "Cases Ordered")
    d = monthly_trend(despatch, "Despatch_Date", "Cases_Despatched", freq, "Cases Dispatched")
    r = monthly_trend(returns,  "Return_Date",   "Returned_Cases",  freq, "Returned Cases")

    merged = None
    for frame in (o, d, r):
        if frame.empty:
            continue
        merged = frame if merged is None else merged.merge(frame, on="Period", how="outer")
    if merged is None:
        return pd.DataFrame(columns=["Period"])
    merged = merged.sort_values("Period").reset_index(drop=True)
    for c in merged.columns:
        if c != "Period":
            merged[c] = merged[c].fillna(0)
    return merged


# ── Customer / product / geography breakdowns ─────────────────────────────────
def top_breakdown(df: Optional[pd.DataFrame], group_col: str, value_col: str,
                  top_n: int = 15, with_cumulative: bool = False) -> pd.DataFrame:
    """Generic 'top-N by sum' helper. Optionally appends Share_% and Cum_%
    (Pareto) columns computed against the *full* total, not just the top-N."""
    cols = [group_col, value_col] + (["Share_%", "Cum_%"] if with_cumulative else [])
    if (df is None or df.empty or group_col not in df.columns
            or value_col not in df.columns):
        return pd.DataFrame(columns=cols)
    g = (
        df.assign(**{value_col: pd.to_numeric(df[value_col], errors="coerce").fillna(0)})
        .groupby(group_col)[value_col].sum()
        .sort_values(ascending=False)
    )
    g = g[g > 0]
    if g.empty:
        return pd.DataFrame(columns=cols)
    res = g.reset_index()
    if with_cumulative:
        total = res[value_col].sum()
        res["Share_%"] = (res[value_col] / total * 100).round(1)
        res["Cum_%"] = (res[value_col].cumsum() / total * 100).round(1)
    if top_n and len(res) > top_n:
        res = res.head(top_n)
    return res.reset_index(drop=True)


def customer_pareto(orders, value_col: str = "Cases_Ordered", top_n: int = 15) -> pd.DataFrame:
    return top_breakdown(orders, "Customer", value_col, top_n, with_cumulative=True)


def sku_breakdown(df, value_col: str, top_n: int = 20) -> pd.DataFrame:
    name_col = "SKU_Description" if (df is not None and "SKU_Description" in df.columns) else "SKU"
    return top_breakdown(df, name_col, value_col, top_n)


def category_breakdown(orders, top_n: int = 15) -> pd.DataFrame:
    """Product-category mix if a category-like column survived transformation,
    else falls back to Customer_Type (channel)."""
    for col in ("Category_Desc", "Category", "Customer_Type"):
        if orders is not None and not orders.empty and col in orders.columns:
            return top_breakdown(orders, col, "Cases_Ordered", top_n)
    return pd.DataFrame(columns=["Customer_Type", "Cases_Ordered"])


# ── Vendor / transport performance ────────────────────────────────────────────
def vendor_performance(transport, top_n: int = 15) -> pd.DataFrame:
    cols = ["Vendor_Name", "Shipments", "Cases", "Avg_Cases"]
    if transport is None or transport.empty or "Vendor_Name" not in transport.columns:
        return pd.DataFrame(columns=cols)
    df = transport.copy()
    df["Vendor_Name"] = (
        df["Vendor_Name"].astype(str).str.strip()
        .replace({"": "Unknown", "nan": "Unknown", "None": "Unknown"})
    )
    qty_col = "Billing_Qty" if "Billing_Qty" in df.columns else None
    cases = (
        df.groupby("Vendor_Name")[qty_col].sum() if qty_col
        else df.groupby("Vendor_Name").size()
    )
    if "Invoice_No" in df.columns:
        ship = df.groupby("Vendor_Name")["Invoice_No"].nunique()
    else:
        ship = df.groupby("Vendor_Name").size()
    res = pd.DataFrame({"Shipments": ship, "Cases": cases}).reset_index()
    res["Avg_Cases"] = np.where(res["Shipments"] > 0, res["Cases"] / res["Shipments"], 0).round(1)
    res = res.sort_values("Cases", ascending=False)
    if top_n and len(res) > top_n:
        res = res.head(top_n)
    return res.reset_index(drop=True)


# ── Alert engine ──────────────────────────────────────────────────────────────
def plant_return_rates(despatch, returns) -> pd.DataFrame:
    """Per-plant return rate = returned ÷ dispatched × 100 (NaN-safe)."""
    if despatch is None or despatch.empty or "Plant" not in despatch.columns:
        return pd.DataFrame(columns=["Plant", "Dispatched", "Returned", "Return_Rate_%"])
    disp = (
        despatch.assign(_q=pd.to_numeric(despatch.get("Cases_Despatched", 0), errors="coerce").fillna(0))
        .groupby("Plant")["_q"].sum()
    )
    if returns is not None and not returns.empty and "Plant" in returns.columns:
        ret = (
            returns.assign(_q=pd.to_numeric(returns.get("Returned_Cases", 0), errors="coerce").fillna(0))
            .groupby("Plant")["_q"].sum()
        )
    else:
        ret = pd.Series(dtype=float)
    res = pd.DataFrame({"Dispatched": disp}).reset_index()
    res["Returned"] = res["Plant"].map(ret).fillna(0)
    res["Return_Rate_%"] = np.where(
        res["Dispatched"] > 0, res["Returned"] / res["Dispatched"] * 100, np.nan
    ).round(2)
    return res


def near_expiry_summary(inventory, near_days: int):
    """Return (near_expiry_cases, expired_cases, expired_value) for stock whose
    Expiry_Date is within ``near_days`` (and already-expired)."""
    if inventory is None or inventory.empty or "Expiry_Date" not in inventory.columns:
        return 0, 0, 0.0
    exp = pd.to_datetime(inventory["Expiry_Date"], errors="coerce")
    today = pd.Timestamp.today().normalize()
    days = (exp - today).dt.days
    cases = pd.to_numeric(inventory.get("Cases_On_Hand", 0), errors="coerce").fillna(0)
    value = pd.to_numeric(inventory.get("Inventory_Value_INR", 0), errors="coerce").fillna(0)
    near_mask = days.notna() & (days >= 0) & (days <= near_days)
    exp_mask = days.notna() & (days < 0)
    return int(cases[near_mask].sum()), int(cases[exp_mask].sum()), float(value[exp_mask].sum())
