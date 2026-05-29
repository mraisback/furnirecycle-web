import pandas as pd
import numpy as np
from typing import Optional, Dict


def _safe_sum(df: Optional[pd.DataFrame], col: str) -> float:
    if df is None or df.empty or col not in df.columns:
        return 0.0
    return pd.to_numeric(df[col], errors="coerce").fillna(0).sum()


def _safe_nunique(df: Optional[pd.DataFrame], col: str) -> int:
    if df is None or df.empty or col not in df.columns:
        return 0
    return df[col].nunique()


def compute_primary_kpis(orders, despatch, returns) -> dict:
    total_ordered    = _safe_sum(orders,  "Cases_Ordered")
    total_dispatched = _safe_sum(despatch, "Cases_Despatched")
    total_returns    = _safe_sum(returns,  "Returned_Cases")
    count_orders     = _safe_nunique(orders, "Order_No")
    unique_customers = _safe_nunique(orders, "Customer")

    return_rate    = (total_returns    / max(total_dispatched, 1)) * 100
    fill_rate      = (total_dispatched / max(total_ordered,    1)) * 100
    avg_order_size = total_dispatched  / max(count_orders,     1)

    return {
        "total_ordered":    total_ordered,
        "total_returns":    total_returns,
        "return_rate":      return_rate,
        "fill_rate":        fill_rate,
        "avg_order_size":   avg_order_size,
        "count_orders":     count_orders,
        "unique_customers": unique_customers,
        "cases_dispatched": total_dispatched,
    }


def compute_receiving_kpi(receiving) -> float:
    return _safe_sum(receiving, "Total_Cases_Received")


def compute_inventory_kpis(inventory, despatch, fixed_manpower: int, orders) -> dict:
    total_value      = _safe_sum(inventory, "Inventory_Value_INR")
    cases_on_hand    = _safe_sum(inventory, "Cases_On_Hand")
    cases_dispatched = _safe_sum(despatch,  "Cases_Despatched")

    monthly_out = cases_dispatched / 30 if cases_dispatched > 0 else 0
    stock_cover = min(cases_on_hand / monthly_out, 9999.9) if monthly_out > 0 else 0.0
    no_dispatch = monthly_out == 0

    cases_per_manhour  = cases_dispatched / max(fixed_manpower, 1)
    count_orders       = _safe_nunique(orders, "Order_No") if orders is not None else 1
    manpower_per_order = fixed_manpower / max(count_orders, 1)

    return {
        "total_value":        total_value,
        "stock_cover":        stock_cover,
        "stock_cover_na":     no_dispatch,
        "cases_per_manhour":  cases_per_manhour,
        "manpower_per_order": manpower_per_order,
    }


def compute_rs_per_case(
    despatch,
    rent_map: Dict[str, float],
    zone_sel: str,
    plant_sel: str,
) -> Optional[float]:
    """Rent ÷ Cases Dispatched for the current filter context.

    Returns None when rent data is unavailable or despatch is zero
    (caller should display '—' rather than 0 or an error).
    """
    if not rent_map or despatch is None or despatch.empty:
        return None

    cases_dispatched = _safe_sum(despatch, "Cases_Despatched")
    if cases_dispatched == 0:
        return None

    if plant_sel != "All Plants" and "Plant" in despatch.columns:
        total_rent = rent_map.get(str(plant_sel), None)
        if total_rent is None:
            return None
    else:
        plants = (
            despatch["Plant"].dropna().astype(str).unique()
            if "Plant" in despatch.columns else []
        )
        total_rent = sum(rent_map.get(p, 0.0) for p in plants)
        if total_rent == 0:
            return None

    return total_rent / cases_dispatched


def compute_expiry_kpis(inventory) -> dict:
    result = {
        "expired_value": 0.0,
        "near_30_cases": 0,
        "near_45_cases": 0,
        "near_60_cases": 0,
    }
    if inventory is None or inventory.empty or "Expiry_Risk" not in inventory.columns:
        return result

    for risk, key in [
        ("Expired",    "expired_value"),
        ("0-30 Days",  "near_30_cases"),
        ("31-45 Days", "near_45_cases"),
        ("46-60 Days", "near_60_cases"),
    ]:
        sub = inventory[inventory["Expiry_Risk"] == risk]
        if risk == "Expired":
            result[key] = _safe_sum(sub, "Inventory_Value_INR")
        else:
            result[key] = int(_safe_sum(sub, "Cases_On_Hand"))

    return result


def compute_returns_by_category(returns) -> pd.DataFrame:
    cats = ["Physical Damage", "Quality Issue", "Commercial Issue", "Other", "Unclassified"]
    if returns is None or returns.empty or "Damage_Category" not in returns.columns:
        return pd.DataFrame({"Damage_Category": cats, "Cases": [0]*5, "Pct_Returns": [0.0]*5})

    total = returns["Returned_Cases"].sum()
    grp = (
        returns.groupby("Damage_Category")["Returned_Cases"]
        .sum()
        .reindex(cats, fill_value=0)
        .reset_index()
    )
    grp.columns = ["Damage_Category", "Cases"]
    grp["Pct_Returns"] = (grp["Cases"] / max(total, 1) * 100).round(1)
    return grp


def compute_channel_split(orders) -> pd.DataFrame:
    channels = ["Modern Trade", "Traditional Trade", "E-Commerce SNX",
                "On premise", "Stock xfr"]
    if orders is None or orders.empty or "Customer_Type" not in orders.columns:
        return pd.DataFrame({
            "Customer_Type": channels,
            "Orders": [0]*len(channels),
            "Cases_Ordered": [0]*len(channels),
        })

    grp = orders.groupby("Customer_Type").agg(
        Orders=("Order_No", "nunique"),
        Cases_Ordered=("Cases_Ordered", "sum"),
    ).reset_index()
    return grp


def compute_inventory_health_table(inventory) -> pd.DataFrame:
    risks = ["Expired", "0-30 Days", "31-45 Days", "46-60 Days"]
    if inventory is None or inventory.empty or "Expiry_Risk" not in inventory.columns:
        return pd.DataFrame({
            "Expiry_Risk": risks,
            "Cases": [0]*4,
            "Value_INR": [0.0]*4,
            "Pct_Total": [0.0]*4,
        })

    total_val = (
        pd.to_numeric(inventory["Inventory_Value_INR"], errors="coerce").fillna(0).sum()
        if "Inventory_Value_INR" in inventory.columns else 0.0
    )
    rows = []
    for risk in risks:
        sub   = inventory[inventory["Expiry_Risk"] == risk]
        cases = int(_safe_sum(sub, "Cases_On_Hand"))
        val   = _safe_sum(sub, "Inventory_Value_INR")
        pct   = round(val / max(total_val, 1) * 100, 1)
        rows.append({"Expiry_Risk": risk, "Cases": cases, "Value_INR": val, "Pct_Total": pct})
    return pd.DataFrame(rows)


def compute_data_freshness(orders, despatch) -> dict:
    """Return MAX order date and MAX despatch date for the current filter."""
    result = {"max_order_date": None, "max_despatch_date": None}
    if orders is not None and "Order_Date" in orders.columns:
        d = orders["Order_Date"].dropna()
        if not d.empty:
            result["max_order_date"] = d.max()
    if despatch is not None and "Despatch_Date" in despatch.columns:
        d = despatch["Despatch_Date"].dropna()
        if not d.empty:
            result["max_despatch_date"] = d.max()
    return result


def compute_rlm_table(
    orders, despatch, returns, receiving, inventory,
    zone_sel: str,
    fixed_manpower: int = 50,
    master_maps: Optional[Dict[str, Dict[str, float]]] = None,
) -> pd.DataFrame:
    """Per-plant KPI breakdown for the RLM Zone Comparison view.

    Undefined ratios (zero denominator, missing master data) are stored as
    NaN so callers can display '-' rather than a misleading 0.
    """

    def _zone_filter(df):
        if df is None or df.empty or "Plant" not in df.columns:
            return None
        if zone_sel != "All Zones" and "Zone" in df.columns:
            return df[df["Zone"] == zone_sel]
        return df

    o   = _zone_filter(orders)
    d   = _zone_filter(despatch)
    r   = _zone_filter(returns)
    rc  = _zone_filter(receiving)
    inv = _zone_filter(inventory)

    def _group(df, col) -> pd.Series:
        if df is None or df.empty or col not in df.columns:
            return pd.Series(dtype=float)
        return pd.to_numeric(df[col], errors="coerce").fillna(0).groupby(df["Plant"]).sum()

    cases_ordered    = _group(o,   "Cases_Ordered")
    cases_dispatched = _group(d,   "Cases_Despatched")
    cases_received   = _group(rc,  "Total_Cases_Received")
    returned_cases   = _group(r,   "Returned_Cases")
    inv_value        = _group(inv, "Inventory_Value_INR")
    cases_on_hand    = _group(inv, "Cases_On_Hand")

    all_plants = sorted(
        set(cases_ordered.index) | set(cases_dispatched.index)
        | set(cases_received.index) | set(returned_cases.index)
        | set(inv_value.index)
    )
    if not all_plants:
        return pd.DataFrame()

    # Pull master data maps
    maps         = master_maps or {}
    rent_map     = maps.get("rent",     {})
    cap_map      = maps.get("capacity", {})
    area_map     = maps.get("area",     {})
    labour_map   = maps.get("labour",   {})

    idx = all_plants
    acc = pd.DataFrame(index=idx)
    acc["Cases_Ordered"]    = cases_ordered.reindex(idx, fill_value=0).astype(int)
    acc["Cases_Dispatched"] = cases_dispatched.reindex(idx, fill_value=0).astype(int)
    acc["Cases_Received"]   = cases_received.reindex(idx, fill_value=0).astype(int)
    acc["Returned_Cases"]   = returned_cases.reindex(idx, fill_value=0).astype(int)
    acc["Inv_Value_INR"]    = inv_value.reindex(idx, fill_value=0).round(0)
    _on_hand                = cases_on_hand.reindex(idx, fill_value=0)

    # ── Derived metrics — NaN when denominator is zero ────────────────────────
    _ordered_pos    = acc["Cases_Ordered"].replace(0, np.nan)
    _dispatched_pos = acc["Cases_Dispatched"].replace(0, np.nan)

    acc["Fill_Rate_%"]   = (acc["Cases_Dispatched"] / _ordered_pos * 100).round(1)
    acc["Return_Rate_%"] = (acc["Returned_Cases"]   / _dispatched_pos * 100).round(1)
    monthly_out = (_dispatched_pos / 30)
    acc["Stock_Cover_Days"] = (_on_hand / monthly_out).clip(upper=9999).round(1)

    # ── Average Order Size ────────────────────────────────────────────────────
    if o is not None and not o.empty and "Order_No" in o.columns and "Plant" in o.columns:
        order_count = o.groupby("Plant")["Order_No"].nunique()
    else:
        order_count = pd.Series(dtype=float)
    order_count_r = order_count.reindex(idx, fill_value=0).replace(0, np.nan)
    acc["Avg_Order_Size"] = (acc["Cases_Dispatched"] / order_count_r).round(1)

    # ── Cases per Manhour (use Master_WH labour if available) ─────────────────
    manpower_series = pd.Series(
        {p: labour_map.get(str(p), fixed_manpower) for p in idx}
    )
    acc["Cases_Per_MH"] = (acc["Cases_Dispatched"] / manpower_series.clip(lower=1)).round(1)

    # ── Master_WH derived KPIs — NaN when data absent ─────────────────────────
    def _series_from_map(m: dict) -> pd.Series:
        return pd.Series({p: m.get(str(p), np.nan) for p in idx})

    rent_s  = _series_from_map(rent_map)
    cap_s   = _series_from_map(cap_map)
    area_s  = _series_from_map(area_map)

    acc["Rs_Per_Case"]    = (rent_s / _dispatched_pos).round(2)
    acc["Dock_Util_%"]    = (acc["Cases_Dispatched"] / cap_s.replace(0, np.nan) * 100).round(1)
    acc["Rent_Per_Sqft"]  = (rent_s / area_s.replace(0, np.nan)).round(2)

    # ── Dispatch rank (only among plants with non-zero dispatches) ─────────────
    acc["Dispatch_Rank"] = (
        acc["Cases_Dispatched"].replace(0, np.nan)
        .rank(method="min", ascending=False, na_option="bottom")
        .astype("Int64")
    )

    acc.index.name = "Plant"
    return acc.reset_index()
