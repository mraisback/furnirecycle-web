import pandas as pd
import numpy as np
from typing import Optional


def _safe_sum(df: Optional[pd.DataFrame], col: str) -> float:
    if df is None or df.empty or col not in df.columns:
        return 0.0
    return pd.to_numeric(df[col], errors="coerce").fillna(0).sum()


def _safe_nunique(df: Optional[pd.DataFrame], col: str) -> int:
    if df is None or df.empty or col not in df.columns:
        return 0
    return df[col].nunique()


def compute_primary_kpis(orders, despatch, returns) -> dict:
    total_ordered    = _safe_sum(orders, "Cases_Ordered")
    total_dispatched = _safe_sum(despatch, "Cases_Despatched")
    total_returns    = _safe_sum(returns, "Returned_Cases")
    count_orders     = _safe_nunique(orders, "Order_No")
    unique_customers = _safe_nunique(orders, "Customer")

    denom = total_dispatched if total_dispatched > 0 else 1
    return_rate = (total_returns / denom) * 100

    return {
        "total_ordered":    total_ordered,
        "total_returns":    total_returns,
        "return_rate":      return_rate,
        "count_orders":     count_orders,
        "unique_customers": unique_customers,
        "cases_dispatched": total_dispatched,
    }


def compute_receiving_kpi(receiving) -> float:
    return _safe_sum(receiving, "Total_Cases_Received")


def compute_inventory_kpis(inventory, despatch, fixed_manpower: int, orders) -> dict:
    total_value = _safe_sum(inventory, "Inventory_Value_INR")
    cases_on_hand = _safe_sum(inventory, "Cases_On_Hand")
    cases_dispatched = _safe_sum(despatch, "Cases_Despatched")

    monthly_out = cases_dispatched / 30 if cases_dispatched > 0 else 1
    stock_cover = cases_on_hand / monthly_out

    cases_per_manhour = cases_dispatched / max(fixed_manpower, 1)
    count_orders = _safe_nunique(orders, "Order_No") if orders is not None else 1
    manpower_per_order = fixed_manpower / max(count_orders, 1)

    return {
        "total_value":        total_value,
        "stock_cover":        stock_cover,
        "cases_per_manhour":  cases_per_manhour,
        "manpower_per_order": manpower_per_order,
    }


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
        ("30-45 Days", "near_45_cases"),
        ("45-60 Days", "near_60_cases"),
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
    risks = ["Expired", "0-30 Days", "30-45 Days", "45-60 Days"]
    if inventory is None or inventory.empty or "Expiry_Risk" not in inventory.columns:
        return pd.DataFrame({
            "Expiry_Risk": risks,
            "Cases": [0]*4,
            "Value_INR": [0.0]*4,
            "Pct_Total": [0.0]*4,
        })

    total_val = inventory["Inventory_Value_INR"].sum()
    rows = []
    for risk in risks:
        sub = inventory[inventory["Expiry_Risk"] == risk]
        cases = int(sub["Cases_On_Hand"].sum()) if "Cases_On_Hand" in sub.columns else 0
        val   = sub["Inventory_Value_INR"].sum() if "Inventory_Value_INR" in sub.columns else 0
        pct   = round(val / max(total_val, 1) * 100, 1)
        rows.append({"Expiry_Risk": risk, "Cases": cases, "Value_INR": val, "Pct_Total": pct})
    return pd.DataFrame(rows)
