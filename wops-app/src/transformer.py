import pandas as pd
import numpy as np
from datetime import date
from typing import Optional, Dict
import streamlit as st
from src.filters import add_zone, ZONE_MAP

PHYSICAL_DAMAGE = {"AIR LEAK/DAMAGE PIEC", "CARTON DAMAGE", "DAMAGED IN TRANSIT"}
QUALITY_ISSUE   = {"QAS RELATED ISSUE", "AGING STOCK"}
COMMERCIAL      = {"PRICING ISSUE", "PACK SIZE/ GRAMMAGE", "ALL ISSUESRELATED PO", "THROUGH CUSTOMER"}
OTHER_REASONS   = {"INTER CHANGE", "OTHER REASON"}


def _safe_col(df: pd.DataFrame, *candidates) -> Optional[str]:
    for c in candidates:
        if c in df.columns:
            return c
    return None


def _pick_col_by_index(df: pd.DataFrame, idx: int) -> Optional[str]:
    if idx < len(df.columns):
        return df.columns[idx]
    return None


def _to_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").fillna(0)


def _to_date(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce")


def _classify_damage(reason: str) -> str:
    if not isinstance(reason, str):
        return "Unclassified"
    r = reason.upper().strip()
    if r in {x.upper() for x in PHYSICAL_DAMAGE}:
        return "Physical Damage"
    if r in {x.upper() for x in QUALITY_ISSUE}:
        return "Quality Issue"
    if r in {x.upper() for x in COMMERCIAL}:
        return "Commercial Issue"
    if r in {x.upper() for x in OTHER_REASONS}:
        return "Other"
    return "Unclassified"


@st.cache_data(show_spinner=False)
def build_all_dataframes(
    zsd_bytes: bytes,
    nysd_bytes: bytes,
    transport_bytes: Optional[bytes],
    invoice_types: list,
    credit_types: list,
    challan_types: list,
) -> Dict[str, Optional[pd.DataFrame]]:
    from src.data_loader import load_zsd, load_nysd, load_transport

    result = {k: None for k in [
        "customer_orders", "order_despatch", "returns",
        "receiving", "inventory", "inventory_accuracy", "transport"
    ]}

    raw_zsd, err = load_zsd(zsd_bytes)
    if raw_zsd is None:
        return result

    raw_nysd, err = load_nysd(nysd_bytes)

    raw_transport = None
    if transport_bytes:
        raw_transport, _ = load_transport(transport_bytes)

    ttd_col = "Transaction Typ Desc"
    if ttd_col not in raw_zsd.columns:
        return result

    invoices = raw_zsd[raw_zsd[ttd_col].isin(invoice_types)].copy()
    credits  = raw_zsd[raw_zsd[ttd_col].isin(credit_types)].copy()
    challans = raw_zsd[raw_zsd[ttd_col].isin(challan_types)].copy()

    # Plant column: prefer col index 5 (0-based) from original
    plant_col_name = _pick_col_by_index(raw_zsd, 5) or _safe_col(raw_zsd, "Source Plant - Key", "Source Plant")

    result["customer_orders"] = _build_customer_orders(invoices, plant_col_name)
    result["order_despatch"]  = _build_order_despatch(invoices, plant_col_name)
    result["returns"]         = _build_returns(credits, plant_col_name)
    result["receiving"]       = _build_receiving(challans, plant_col_name)

    if raw_nysd is not None:
        result["inventory"] = _build_inventory(raw_nysd, result["receiving"])

    result["inventory_accuracy"] = _build_inventory_accuracy(
        result["receiving"], result["order_despatch"],
        result["returns"], result["inventory"]
    )

    if raw_transport is not None:
        result["transport"] = _build_transport(raw_transport)

    return result


def _build_customer_orders(df: pd.DataFrame, plant_col: Optional[str]) -> pd.DataFrame:
    col_map = {
        "Invoice No":             "Order_No",
        "Customer Name(SOLD)":    "Customer",
        "Dist.Channel Desc.":     "Customer_Type",
        "Material":               "SKU",
        "Material Name":          "SKU_Description",
        "Billing Qty(Cas)":       "Cases_Ordered",
        "MRP":                    "Unit_Price_INR",
    }
    item_col = _safe_col(df, "Item no", "Item No", "Line Item")
    date_col = _safe_col(df, "Invoice Date", "Billing Date")

    out = pd.DataFrame()
    for src, dst in col_map.items():
        c = _safe_col(df, src)
        if c:
            out[dst] = df[c].values
        else:
            out[dst] = np.nan

    if item_col:
        out["Order_Line_No"] = df[item_col].values
    else:
        out["Order_Line_No"] = np.nan

    if date_col:
        out["Order_Date"] = _to_date(df[date_col])
    else:
        out["Order_Date"] = pd.NaT

    if plant_col and plant_col in df.columns:
        out["Plant"] = df[plant_col].values
    else:
        out["Plant"] = "Unknown"

    out["Cases_Ordered"] = _to_numeric(out["Cases_Ordered"])
    out["Unit_Price_INR"] = _to_numeric(out["Unit_Price_INR"])
    out = add_zone(out)
    return out.reset_index(drop=True)


def _build_order_despatch(df: pd.DataFrame, plant_col: Optional[str]) -> pd.DataFrame:
    col_map = {
        "Invoice No":          "Order_No",
        "Customer Name(SOLD)": "Customer",
        "Material":            "SKU",
        "Batch":               "Lot_No",
        "Billing Qty(Cas)":    "Cases_Despatched",
        "Truck No":            "Carrier",
    }
    date_col = _safe_col(df, "Invoice Date", "Billing Date")

    out = pd.DataFrame()
    for src, dst in col_map.items():
        c = _safe_col(df, src)
        if c:
            out[dst] = df[c].values
        else:
            out[dst] = np.nan

    if date_col:
        out["Despatch_Date"] = _to_date(df[date_col])
    else:
        out["Despatch_Date"] = pd.NaT

    if plant_col and plant_col in df.columns:
        out["Plant"] = df[plant_col].values
    else:
        out["Plant"] = "Unknown"

    out["Cases_Despatched"] = _to_numeric(out["Cases_Despatched"])
    out["Lot_No_Status"] = out["Lot_No"].apply(
        lambda x: "MISSING BATCH" if (pd.isna(x) or str(x).strip() == "") else "OK"
    )
    out = add_zone(out)
    return out.reset_index(drop=True)


def _build_returns(df: pd.DataFrame, plant_col: Optional[str]) -> pd.DataFrame:
    col_map = {
        "Invoice No":                    "Return_No",
        "Reference Invoice Number":      "Order_No",
        "Customer Name(SOLD)":           "Customer",
        "Material":                      "SKU",
        "Batch":                         "Lot_No",
        "Line Item Usage Reason Desc.":  "Return_Reason_Code",
    }
    date_col = _safe_col(df, "Invoice Date", "Billing Date")
    qty_col  = _safe_col(df, "Billing Qty(Cas)")

    out = pd.DataFrame()
    for src, dst in col_map.items():
        c = _safe_col(df, src)
        if c:
            out[dst] = df[c].values
        else:
            out[dst] = np.nan

    if date_col:
        out["Return_Date"] = _to_date(df[date_col])
    else:
        out["Return_Date"] = pd.NaT

    if qty_col:
        out["Returned_Cases"] = _to_numeric(df[qty_col]).abs()
    else:
        out["Returned_Cases"] = 0.0

    if plant_col and plant_col in df.columns:
        out["Plant"] = df[plant_col].values
    else:
        out["Plant"] = "Unknown"

    out["Damage_Category"] = out["Return_Reason_Code"].apply(_classify_damage)
    out = add_zone(out)
    return out.reset_index(drop=True)


def _build_receiving(df: pd.DataFrame, plant_col: Optional[str]) -> pd.DataFrame:
    col_map = {
        "Invoice No":                   "Receipt_No",
        "Material":                     "SKU",
        "Material Name":                "SKU_Description",
        "Batch":                        "Lot_No",
        "Expiry Date":                  "Expiry_Date_raw",
        "Billing Qty(Cas)":             "Total_Cases_Received",
        "Line Item Usage Reason Desc.": "Usage_Reason",
    }
    date_col = _safe_col(df, "Invoice Date", "Billing Date")

    out = pd.DataFrame()
    for src, dst in col_map.items():
        c = _safe_col(df, src)
        if c:
            out[dst] = df[c].values
        else:
            out[dst] = np.nan

    if date_col:
        out["Receipt_Date"] = _to_date(df[date_col])
    else:
        out["Receipt_Date"] = pd.NaT

    if plant_col and plant_col in df.columns:
        out["Plant"] = df[plant_col].values
    else:
        out["Plant"] = "Unknown"

    out["Expiry_Date"] = _to_date(out["Expiry_Date_raw"])
    out.drop(columns=["Expiry_Date_raw"], inplace=True, errors="ignore")
    out["Total_Cases_Received"] = _to_numeric(out["Total_Cases_Received"])
    out["Good_Cases"] = out.apply(
        lambda r: r["Total_Cases_Received"]
        if (pd.isna(r.get("Usage_Reason")) or str(r.get("Usage_Reason", "")).strip() == "")
        else 0,
        axis=1,
    )
    out["Damaged_Cases"] = out["Total_Cases_Received"] - out["Good_Cases"]
    out = add_zone(out)
    return out.reset_index(drop=True)


def _expiry_risk(expiry_date, today: date) -> str:
    if pd.isna(expiry_date):
        return "Unknown"
    days = (expiry_date.date() - today).days
    if days < 0:
        return "Expired"
    if days <= 30:
        return "0-30 Days"
    if days <= 45:
        return "30-45 Days"
    if days <= 60:
        return "45-60 Days"
    return "OK"


def _build_inventory(nysd_df: pd.DataFrame, receiving_df: Optional[pd.DataFrame]) -> pd.DataFrame:
    col_map = {
        "Material No":          "SKU",
        "Material Description": "SKU_Description",
        "Batch No":             "Lot_No",
        "EXP Date":             "Expiry_Date",
        "Qty in CS":            "Cases_On_Hand",
        "MRP Rate":             "Unit_Cost_INR",
        "Value OF Stock":       "Inventory_Value_INR",
        "Storage Description":  "Status",
    }
    out = pd.DataFrame()
    for src, dst in col_map.items():
        c = _safe_col(nysd_df, src)
        if c:
            out[dst] = nysd_df[c].values
        else:
            out[dst] = np.nan

    out["Expiry_Date"] = _to_date(out["Expiry_Date"])
    out["Cases_On_Hand"] = _to_numeric(out["Cases_On_Hand"]).astype(int)
    out["Unit_Cost_INR"] = _to_numeric(out["Unit_Cost_INR"])
    out["Inventory_Value_INR"] = _to_numeric(out["Inventory_Value_INR"])
    out["Month_End_Date"] = pd.Timestamp(date.today())

    today = date.today()
    out["Expiry_Risk"] = out["Expiry_Date"].apply(lambda x: _expiry_risk(x, today))

    # Try to get Plant from receiving via SKU + Lot_No join
    out["Plant"] = "Unknown"
    if receiving_df is not None and not receiving_df.empty:
        ref = receiving_df[["SKU", "Lot_No", "Plant"]].drop_duplicates(subset=["SKU", "Lot_No"])
        out = out.merge(ref, on=["SKU", "Lot_No"], how="left", suffixes=("", "_recv"))
        if "Plant_recv" in out.columns:
            out["Plant"] = out["Plant_recv"].fillna(out["Plant"])
            out.drop(columns=["Plant_recv"], inplace=True)

    out = add_zone(out)
    return out.reset_index(drop=True)


def _build_inventory_accuracy(receiving, despatch, returns, inventory) -> pd.DataFrame:
    rows = []
    plants = set()
    for df in [receiving, despatch, returns, inventory]:
        if df is not None and "Plant" in df.columns:
            plants.update(df["Plant"].dropna().unique())

    for plant in sorted(plants):
        def psum(df, col):
            if df is None or col not in df.columns:
                return 0.0
            sub = df[df["Plant"] == plant] if "Plant" in df.columns else df
            return _to_numeric(sub[col]).sum()

        mov_in  = psum(receiving, "Total_Cases_Received")
        mov_out = psum(despatch, "Cases_Despatched")
        ret_qty = psum(returns, "Returned_Cases")
        actual  = psum(inventory, "Cases_On_Hand")
        expected = mov_in - mov_out + ret_qty
        deviation = actual - expected
        accuracy  = 1.0 - abs(deviation) / max(abs(expected), 1)

        rows.append({
            "Plant": plant,
            "Movement_In": mov_in,
            "Movement_Out": mov_out,
            "Returns_Qty": ret_qty,
            "Expected_Stock": expected,
            "Actual_Stock": actual,
            "Cases_Deviation": deviation,
            "Accuracy_%": round(accuracy * 100, 2),
        })

    df_out = pd.DataFrame(rows)
    return add_zone(df_out) if not df_out.empty else df_out


def _build_transport(df: pd.DataFrame) -> pd.DataFrame:
    col_indices = {
        5:  "Source_Plant",
        11: "Truck_No",
        12: "Shipment_Doc",
        13: "Delivery_Doc",
        18: "Shipment_Type",
        19: "Bill_Type",
        20: "Invoice_No",
        21: "Invoice_Date",
        22: "Billing_Source_Plant",
        23: "Dest_Plant_Key",
        24: "Dest_Plant_Name",
        25: "Dest_City",
        26: "SKU",
        28: "Billing_Qty",
        29: "Billing_Qty_KG",
        41: "Dest_State_Key",
        42: "Dest_State",
        45: "Dest_Unit",
        46: "Material_Type",
    }
    out = pd.DataFrame()
    for idx, name in col_indices.items():
        if idx < len(df.columns):
            out[name] = df.iloc[:, idx].values
        else:
            out[name] = np.nan

    out["Invoice_Date"] = _to_date(out["Invoice_Date"])
    out["Billing_Qty"]    = _to_numeric(out["Billing_Qty"])
    out["Billing_Qty_KG"] = _to_numeric(out["Billing_Qty_KG"])
    out["Plant"] = out["Source_Plant"].astype(str).str.strip()
    out = add_zone(out)
    return out.reset_index(drop=True)
