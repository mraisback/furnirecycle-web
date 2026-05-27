import pandas as pd
from typing import Optional


def compute_error_log(orders, despatch, returns, receiving, inventory, inventory_accuracy) -> pd.DataFrame:
    rows = []

    # 1. Missing Lot_No (Batch) in despatch
    missing_batch = 0
    if despatch is not None and "Lot_No_Status" in despatch.columns:
        missing_batch = int((despatch["Lot_No_Status"] == "MISSING BATCH").sum())
    rows.append({
        "Error Type":       "Missing Batch / Lot_No",
        "Count":            missing_batch,
        "Severity":         "HIGH",
        "Action Required":  "Verify batch before dispatch",
    })

    # 2. Duplicate Invoice No in orders
    dup_invoices = 0
    if orders is not None and "Order_No" in orders.columns:
        counts = orders["Order_No"].value_counts()
        dup_invoices = int((counts > 1).sum())
    rows.append({
        "Error Type":       "Duplicate Invoice No",
        "Count":            dup_invoices,
        "Severity":         "HIGH",
        "Action Required":  "Check SAP export for duplicates",
    })

    # 3. Near Expiry ≤30 days
    near_expiry = 0
    if inventory is not None and "Expiry_Risk" in inventory.columns:
        near_expiry = int((inventory["Expiry_Risk"] == "0-30 Days").sum())
    rows.append({
        "Error Type":       "Near Expiry (≤30 days)",
        "Count":            near_expiry,
        "Severity":         "MEDIUM",
        "Action Required":  "Prioritise FEFO picking",
    })

    # 4. Inventory accuracy < 95%
    low_accuracy = 0
    if inventory_accuracy is not None and "Accuracy_%" in inventory_accuracy.columns:
        low_accuracy = int((inventory_accuracy["Accuracy_%"] < 95.0).sum())
    rows.append({
        "Error Type":       "Inventory Accuracy < 95%",
        "Count":            low_accuracy,
        "Severity":         "MEDIUM",
        "Action Required":  "Schedule cycle count",
    })

    # 5. Return Rate > 5%
    return_rate_flag = 0
    if despatch is not None and returns is not None:
        total_disp = pd.to_numeric(despatch.get("Cases_Despatched", pd.Series([0])),
                                   errors="coerce").sum() if despatch is not None else 0
        total_ret  = pd.to_numeric(returns.get("Returned_Cases", pd.Series([0])),
                                   errors="coerce").sum() if returns is not None else 0
        if total_disp > 0 and (total_ret / total_disp * 100) > 5:
            return_rate_flag = 1
    rows.append({
        "Error Type":       "Return Rate > 5%",
        "Count":            return_rate_flag,
        "Severity":         "HIGH",
        "Action Required":  "Escalate to ops manager",
    })

    # 6. Missing Lot on Returns
    missing_return_lot = 0
    if returns is not None and "Lot_No" in returns.columns:
        missing_return_lot = int(
            returns["Lot_No"].apply(
                lambda x: pd.isna(x) or str(x).strip() == ""
            ).sum()
        )
    rows.append({
        "Error Type":       "Missing Lot on Returns",
        "Count":            missing_return_lot,
        "Severity":         "LOW",
        "Action Required":  "Capture batch on all credit notes",
    })

    return pd.DataFrame(rows)


def get_missing_batch_detail(despatch: Optional[pd.DataFrame]) -> Optional[pd.DataFrame]:
    if despatch is None or "Lot_No_Status" not in despatch.columns:
        return None
    detail = despatch[despatch["Lot_No_Status"] == "MISSING BATCH"].copy()
    cols = [c for c in ["Order_No", "Customer", "SKU", "Despatch_Date", "Plant", "Cases_Despatched"]
            if c in detail.columns]
    return detail[cols] if cols else detail


def get_duplicate_invoices(orders: Optional[pd.DataFrame]) -> Optional[pd.DataFrame]:
    if orders is None or "Order_No" not in orders.columns:
        return None
    counts = orders["Order_No"].value_counts()
    dup_nos = counts[counts > 1].index
    detail = orders[orders["Order_No"].isin(dup_nos)].copy()
    cols = [c for c in ["Order_No", "Customer", "SKU", "Order_Date", "Plant", "Cases_Ordered"]
            if c in detail.columns]
    return detail[cols].sort_values("Order_No") if cols else detail
