import pandas as pd
import numpy as np
from datetime import date, datetime, timedelta
from typing import Optional, Dict
import streamlit as st
from src.filters import add_zone, build_zone_map_from_master

PHYSICAL_DAMAGE = {"AIR LEAK/DAMAGE PIEC", "CARTON DAMAGE", "DAMAGED IN TRANSIT"}
QUALITY_ISSUE   = {"QAS RELATED ISSUE", "AGING STOCK"}
COMMERCIAL      = {"PRICING ISSUE", "PACK SIZE/ GRAMMAGE", "ALL ISSUESRELATED PO", "THROUGH CUSTOMER"}
OTHER_REASONS   = {"INTER CHANGE", "OTHER REASON"}

# Pre-compute upper-case sets for vectorized damage classification
_PHYSICAL_UPPER  = {x.upper() for x in PHYSICAL_DAMAGE}
_QUALITY_UPPER   = {x.upper() for x in QUALITY_ISSUE}
_COMMERCIAL_UPPER = {x.upper() for x in COMMERCIAL}
_OTHER_UPPER     = {x.upper() for x in OTHER_REASONS}

# ── Column name candidate lists (first match wins, case-insensitive) ──────────
_INV_COLS    = ["Invoice no", "Invoice No", "Invoice Number", "Invoice_No",
                "Billing Doc", "Doc. Number", "Document Number"]
_DATE_COLS   = ["Date", "Invoice Date", "Billing Date", "Invoice_Date", "Order Date"]
_QTY_COLS    = ["Billing Qty(Cas)", "Billing Qty (Cas)", "Cases", "Qty(Cas)",
                "Cases_Ordered", "Qty in CS", "Billing Qty"]
_CUST_COLS   = ["Customer Name(SOLD)", "Customer Name", "Customer", "Sold-to Party"]
_SKU_COLS    = ["Material", "SKU", "Material No", "Mat.", "SKU_Code"]
_DESC_COLS   = ["Material Name", "SKU_Description", "Material Description", "Description"]
_BATCH_COLS  = ["Batch", "Batch No", "Lot No", "Lot_No", "Batch Number"]
_REASON_COLS = ["Line Item Usage Reason Desc.", "Line Item Usage Reason",
                "Usage Reason", "Return Reason", "Return_Reason_Code"]
_EXPIRY_COLS = ["Expiry Date", "Expiry_Date", "EXP Date", "Expiry", "Best Before"]
_PLANT_COLS  = ["Plant", "Source Plant - Key", "Source Plant", "Plant Code",
                "Warehouse Code"]
_CHANNEL_COLS = ["Dist.Channel Desc.", "Dist Channel Desc.", "Distribution Channel",
                 "Customer_Type", "Channel"]
_TRUCK_COLS  = ["Truck No", "Truck No.", "Vehicle Number", "Carrier"]
_PRICE_COLS  = ["Basic", "MRP", "Gross Revenue New", "Invoice Value",
                "Unit_Price_INR", "Rate"]
_ITEM_COLS   = ["Item no", "Item No", "Item no.", "Line Item", "Order Line"]
_REF_COLS    = ["Reference Invoice Number", "Ref Invoice", "Reference Doc",
                "Ref. Invoice No", "Reference Document Number"]

_EXCEL_EPOCH = pd.Timestamp(datetime(1899, 12, 30))


def _safe_col(df: pd.DataFrame, *candidates) -> Optional[str]:
    """Return first matching column name; falls back to case-insensitive match."""
    cols = df.columns
    for c in candidates:
        if c in cols:
            return c
    lower = {col.lower(): col for col in cols}
    for c in candidates:
        found = lower.get(c.lower())
        if found:
            return found
    return None


def _sc(df, lst):
    """Shorthand: _safe_col from a candidate list."""
    return _safe_col(df, *lst)


def _to_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").fillna(0)


def _to_date(series: pd.Series) -> pd.Series:
    """Parse a column of dates that may be datetimes, ISO strings, or Excel serials.

    CRITICAL: Excel serials are numbers like 45000 (days since 1899-12-30). They must
    NOT be passed to pd.to_datetime first, which would interpret a bare integer as
    nanoseconds since 1970 (turning 45000 into 1970-01-01). So the numeric-serial
    branch is handled explicitly before falling back to general datetime parsing.
    """
    # Fast path: already a proper datetime dtype.
    if pd.api.types.is_datetime64_any_dtype(series):
        return series

    result = pd.Series(pd.NaT, index=series.index, dtype="datetime64[ns]")

    # Branch 1 — numeric Excel serials (ints, floats, and numeric strings like "45000.0").
    numeric = pd.to_numeric(
        series.astype(str).str.replace(",", "", regex=False).str.strip(),
        errors="coerce",
    )
    serial_mask = numeric.notna() & (numeric > 1) & (numeric < 200000)
    if serial_mask.any():
        result[serial_mask] = _EXCEL_EPOCH + pd.to_timedelta(numeric[serial_mask], unit="D")

    # Branch 2 — real date strings / datetime objects via general parser.
    remaining = result.isna() & series.notna()
    if remaining.any():
        result[remaining] = pd.to_datetime(series[remaining], errors="coerce")

    return result


def _norm_plant_series(series: pd.Series) -> pd.Series:
    """Vectorized plant normalisation: '5135.0' → '5135', blank/NaN → 'Unknown'."""
    s = series.fillna("").astype(str).str.strip()
    numeric = pd.to_numeric(s, errors="coerce")
    is_int_float = numeric.notna() & (numeric % 1 == 0)
    result = s.copy()
    result[is_int_float] = numeric[is_int_float].astype(int).astype(str)
    result[result.isin(["", "nan", "None"])] = "Unknown"
    return result


def _norm_plant(val) -> str:
    """Normalise a single plant code to clean string (5135.0 → '5135')."""
    if pd.isna(val) or str(val).strip() in ("", "nan", "None"):
        return "Unknown"
    s = str(val).strip()
    try:
        if float(s) == int(float(s)):
            return str(int(float(s)))
    except (ValueError, OverflowError):
        pass
    return s


@st.cache_data(show_spinner=False)
def build_all_dataframes(
    zsd_bytes: bytes,
    nysd_bytes: bytes,
    transport_bytes: Optional[bytes],
    invoice_types: tuple,
    credit_types: tuple,
    challan_types: tuple,
    master_wh_bytes: Optional[bytes] = None,
) -> Dict[str, Optional[pd.DataFrame]]:
    from src.data_loader import load_zsd, load_nysd, load_transport, load_master_wh

    result = {k: None for k in [
        "customer_orders", "order_despatch", "returns",
        "receiving", "inventory", "inventory_accuracy", "transport"
    ]}

    zone_map = {}
    if master_wh_bytes:
        mwh_df, _ = load_master_wh(master_wh_bytes)
        zone_map, _ = build_zone_map_from_master(mwh_df)

    raw_zsd, err = load_zsd(zsd_bytes)
    if raw_zsd is None:
        return result

    raw_nysd, _ = load_nysd(nysd_bytes)

    raw_transport = None
    if transport_bytes:
        raw_transport, _ = load_transport(transport_bytes)

    ttd_col = _safe_col(raw_zsd, "Transaction Typ Desc", "Transaction Type Desc",
                         "Transaction Typ", "Billing Type")
    if not ttd_col:
        return result

    invoices = raw_zsd[raw_zsd[ttd_col].astype(str).isin(invoice_types)].copy()
    credits  = raw_zsd[raw_zsd[ttd_col].astype(str).isin(credit_types)].copy()
    challans = raw_zsd[raw_zsd[ttd_col].astype(str).isin(challan_types)].copy()

    result["customer_orders"] = _build_customer_orders(invoices)
    result["order_despatch"]  = _build_order_despatch(invoices)
    result["returns"]         = _build_returns(credits)
    result["receiving"]       = _build_receiving(challans)

    if raw_nysd is not None:
        result["inventory"] = _build_inventory(raw_nysd)

    result["inventory_accuracy"] = _build_inventory_accuracy(
        result["receiving"], result["order_despatch"],
        result["returns"], result["inventory"]
    )

    if raw_transport is not None:
        result["transport"] = _build_transport(raw_transport)

    for key, df in result.items():
        if df is not None and not df.empty and "Plant" in df.columns:
            result[key] = add_zone(df, zone_map or None)

    return result


def _extract(df, src_col, candidates=None) -> pd.Series:
    """Extract a column by explicit name or candidate list; return NaN Series if missing."""
    col = src_col if src_col in df.columns else (_sc(df, candidates) if candidates else None)
    return df[col] if col else pd.Series([np.nan] * len(df), index=df.index)


def _build_customer_orders(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()

    inv_col   = _sc(df, _INV_COLS)
    date_col  = _sc(df, _DATE_COLS)
    item_col  = _sc(df, _ITEM_COLS)
    cust_col  = _sc(df, _CUST_COLS)
    chan_col  = _sc(df, _CHANNEL_COLS)
    sku_col   = _sc(df, _SKU_COLS)
    desc_col  = _sc(df, _DESC_COLS)
    qty_col   = _sc(df, _QTY_COLS)
    price_col = _sc(df, _PRICE_COLS)
    plant_col = _sc(df, _PLANT_COLS)

    out = pd.DataFrame()
    out["Order_No"]        = df[inv_col].values   if inv_col   else np.nan
    out["Order_Line_No"]   = df[item_col].values  if item_col  else np.nan
    out["Order_Date"]      = _to_date(df[date_col]) if date_col else pd.NaT
    out["Customer"]        = df[cust_col].values  if cust_col  else np.nan
    out["Customer_Type"]   = df[chan_col].values  if chan_col  else np.nan
    out["SKU"]             = df[sku_col].values   if sku_col   else np.nan
    out["SKU_Description"] = df[desc_col].values  if desc_col  else np.nan
    out["Cases_Ordered"]   = _to_numeric(df[qty_col]) if qty_col else 0.0
    out["Unit_Price_INR"]  = _to_numeric(df[price_col]) if price_col else 0.0
    out["Plant"]           = _norm_plant_series(df[plant_col]) if plant_col else "Unknown"
    out["On_Time_Delivery"]   = "Pending"
    out["In_Full_Delivery"]   = "Pending"
    return out.reset_index(drop=True)


def _build_order_despatch(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()

    inv_col   = _sc(df, _INV_COLS)
    date_col  = _sc(df, _DATE_COLS)
    cust_col  = _sc(df, _CUST_COLS)
    sku_col   = _sc(df, _SKU_COLS)
    batch_col = _sc(df, _BATCH_COLS)
    qty_col   = _sc(df, _QTY_COLS)
    truck_col = _sc(df, _TRUCK_COLS)
    plant_col = _sc(df, _PLANT_COLS)

    out = pd.DataFrame()
    out["Order_No"]          = df[inv_col].values    if inv_col    else np.nan
    out["Customer"]          = df[cust_col].values   if cust_col   else np.nan
    out["SKU"]               = df[sku_col].values    if sku_col    else np.nan
    out["Lot_No"]            = df[batch_col].astype(str).values if batch_col else np.nan
    out["Despatch_Date"]     = _to_date(df[date_col]) if date_col  else pd.NaT
    out["Cases_Despatched"]  = _to_numeric(df[qty_col]) if qty_col else 0.0
    out["Carrier"]           = df[truck_col].values  if truck_col  else np.nan
    out["Plant"]             = _norm_plant_series(df[plant_col]) if plant_col else "Unknown"

    lot_str = out["Lot_No"].fillna("").astype(str).str.strip()
    out["Lot_No_Status"] = np.where(
        lot_str.isin(["", "nan", "None"]), "MISSING BATCH", "OK"
    )
    return out.reset_index(drop=True)


def _build_returns(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()

    inv_col    = _sc(df, _INV_COLS)
    ref_col    = _sc(df, _REF_COLS)
    date_col   = _sc(df, _DATE_COLS)
    cust_col   = _sc(df, _CUST_COLS)
    sku_col    = _sc(df, _SKU_COLS)
    batch_col  = _sc(df, _BATCH_COLS)
    qty_col    = _sc(df, _QTY_COLS)
    reason_col = _sc(df, _REASON_COLS)
    plant_col  = _sc(df, _PLANT_COLS)

    out = pd.DataFrame()
    out["Return_No"]          = df[inv_col].values   if inv_col   else np.nan
    out["Order_No"]           = df[ref_col].values   if ref_col   else np.nan
    out["Customer"]           = df[cust_col].values  if cust_col  else np.nan
    out["SKU"]                = df[sku_col].values   if sku_col   else np.nan
    out["Lot_No"]             = df[batch_col].astype(str).values if batch_col else np.nan
    out["Return_Date"]        = _to_date(df[date_col]) if date_col else pd.NaT
    out["Returned_Cases"]     = _to_numeric(df[qty_col]).abs() if qty_col else 0.0
    out["Return_Reason_Code"] = df[reason_col].values if reason_col else np.nan
    out["Plant"]              = _norm_plant_series(df[plant_col]) if plant_col else "Unknown"

    reason_upper = out["Return_Reason_Code"].fillna("").astype(str).str.strip().str.upper()
    out["Damage_Category"] = np.select(
        [
            reason_upper.isin(_PHYSICAL_UPPER),
            reason_upper.isin(_QUALITY_UPPER),
            reason_upper.isin(_COMMERCIAL_UPPER),
            reason_upper.isin(_OTHER_UPPER),
            reason_upper == "",
        ],
        ["Physical Damage", "Quality Issue", "Commercial Issue", "Other", "Unclassified"],
        default="Unclassified",
    )
    return out.reset_index(drop=True)


def _build_receiving(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()

    inv_col    = _sc(df, _INV_COLS)
    date_col   = _sc(df, _DATE_COLS)
    sku_col    = _sc(df, _SKU_COLS)
    desc_col   = _sc(df, _DESC_COLS)
    batch_col  = _sc(df, _BATCH_COLS)
    exp_col    = _sc(df, _EXPIRY_COLS)
    qty_col    = _sc(df, _QTY_COLS)
    reason_col = _sc(df, _REASON_COLS)
    plant_col  = _sc(df, _PLANT_COLS)

    out = pd.DataFrame()
    out["Receipt_No"]            = df[inv_col].values   if inv_col   else np.nan
    out["Receipt_Date"]          = _to_date(df[date_col]) if date_col else pd.NaT
    out["SKU"]                   = df[sku_col].values   if sku_col   else np.nan
    out["SKU_Description"]       = df[desc_col].values  if desc_col  else np.nan
    out["Lot_No"]                = df[batch_col].astype(str).values if batch_col else np.nan
    out["Expiry_Date"]           = _to_date(df[exp_col]) if exp_col  else pd.NaT
    out["Total_Cases_Received"]  = _to_numeric(df[qty_col]) if qty_col else 0.0
    out["Plant"]                 = _norm_plant_series(df[plant_col]) if plant_col else "Unknown"

    reason_series = df[reason_col] if reason_col else pd.Series([""] * len(df), index=df.index)
    reason_str = reason_series.fillna("").astype(str).str.strip()
    is_clean = reason_str.isin(["", "nan", "None"])
    out["Good_Cases"]    = np.where(is_clean.values, out["Total_Cases_Received"].values, 0.0)
    out["Damaged_Cases"] = out["Total_Cases_Received"] - out["Good_Cases"]
    return out.reset_index(drop=True)


def _build_inventory(nysd_df: pd.DataFrame) -> pd.DataFrame:
    """Build inventory from nysd_css — columns are already Power Query-renamed."""
    if nysd_df.empty:
        return pd.DataFrame()

    sku_col   = _safe_col(nysd_df, "SKU", "Material No", "Material", "SKU_Code")
    desc_col  = _safe_col(nysd_df, "SKU_Description", "Material Description", "Material Name", "Description")
    lot_col   = _safe_col(nysd_df, "Lot_No", "Batch No", "Batch", "Lot No")
    exp_col   = _safe_col(nysd_df, "Expiry_Date", "EXP Date", "Expiry Date", "Expiry")
    qty_col   = _safe_col(nysd_df, "Cases_On_Hand", "Qty in CS", "Cases", "Qty")
    cost_col  = _safe_col(nysd_df, "Unit_Cost_INR", "MRP Rate", "MRP", "Unit Cost")
    val_col   = _safe_col(nysd_df, "Inventory_Value_INR", "Value OF Stock", "Inventory Value", "Value")
    stat_col  = _safe_col(nysd_df, "Status", "Storage Description", "Lot Status")
    plant_col = _safe_col(nysd_df, "Plant", "Plant Code", "Warehouse Code")

    out = pd.DataFrame()
    out["SKU"]                 = nysd_df[sku_col].values   if sku_col   else np.nan
    out["SKU_Description"]     = nysd_df[desc_col].values  if desc_col  else np.nan
    out["Lot_No"]              = nysd_df[lot_col].astype(str).values if lot_col else np.nan
    out["Expiry_Date"]         = _to_date(nysd_df[exp_col]) if exp_col  else pd.NaT
    out["Cases_On_Hand"]       = _to_numeric(nysd_df[qty_col]).astype(int) if qty_col else 0
    out["Unit_Cost_INR"]       = _to_numeric(nysd_df[cost_col]) if cost_col else 0.0
    out["Inventory_Value_INR"] = _to_numeric(nysd_df[val_col]) if val_col  else 0.0
    out["Status"]              = nysd_df[stat_col].values  if stat_col  else np.nan
    out["Plant"]               = _norm_plant_series(nysd_df[plant_col]) if plant_col else "Unknown"
    out["Month_End_Date"]      = pd.Timestamp(date.today())

    today_ts = pd.Timestamp(date.today())
    exp_dates = out["Expiry_Date"]
    days = (exp_dates - today_ts).dt.days
    out["Expiry_Risk"] = np.select(
        [
            exp_dates.isna(),
            days < 0,
            days <= 30,
            days <= 45,
            days <= 60,
        ],
        ["Unknown", "Expired", "0-30 Days", "31-45 Days", "46-60 Days"],
        default="OK",
    )
    return out.reset_index(drop=True)


def _build_inventory_accuracy(receiving, despatch, returns, inventory) -> pd.DataFrame:
    def _group_sum(df, col) -> pd.Series:
        if df is None or df.empty or "Plant" not in df.columns or col not in df.columns:
            return pd.Series(dtype=float)
        return (
            pd.to_numeric(df[col], errors="coerce")
            .fillna(0)
            .groupby(df["Plant"])
            .sum()
        )

    mov_in  = _group_sum(receiving,  "Total_Cases_Received")
    mov_out = _group_sum(despatch,   "Cases_Despatched")
    ret_qty = _group_sum(returns,    "Returned_Cases")
    actual  = _group_sum(inventory,  "Cases_On_Hand")

    all_plants = sorted(
        set(mov_in.index) | set(mov_out.index) | set(ret_qty.index) | set(actual.index)
    )
    if not all_plants:
        return pd.DataFrame(columns=[
            "Plant", "Movement_In", "Movement_Out", "Returns_Qty",
            "Expected_Stock", "Actual_Stock", "Cases_Deviation", "Accuracy_%",
        ])

    acc = pd.DataFrame(index=all_plants)
    acc["Movement_In"]    = mov_in.reindex(all_plants, fill_value=0)
    acc["Movement_Out"]   = mov_out.reindex(all_plants, fill_value=0)
    acc["Returns_Qty"]    = ret_qty.reindex(all_plants, fill_value=0)
    acc["Actual_Stock"]   = actual.reindex(all_plants, fill_value=0)
    acc["Expected_Stock"] = acc["Movement_In"] - acc["Movement_Out"] + acc["Returns_Qty"]
    acc["Cases_Deviation"] = acc["Actual_Stock"] - acc["Expected_Stock"]
    denom = acc["Expected_Stock"].abs().clip(lower=1)
    acc["Accuracy_%"] = (1.0 - acc["Cases_Deviation"].abs() / denom).mul(100).round(2)
    acc.index.name = "Plant"
    return acc.reset_index()


def _build_transport(df: pd.DataFrame) -> pd.DataFrame:
    """Build transport DataFrame — tries named columns first, falls back to position index."""
    NAMED = {
        "Source_Plant": ["Source_Plant", "Source Plant", "Plant"],
        "Truck_No":     ["Truck_No", "Truck No", "Truck No."],
        "Shipment_Doc": ["Shipment_Doc", "Shipment Doc"],
        "Delivery_Doc": ["Delivery_Doc", "Delivery Doc"],
        "Shipment_Type":["Shipment_Type", "Shipment Type"],
        "Bill_Type":    ["Bill_Type", "Bill Type"],
        "Invoice_No":   ["Invoice_No", "Invoice No", "Invoice no"],
        "Invoice_Date": ["Invoice_Date", "Invoice Date", "Date"],
        "Billing_Source_Plant": ["Billing_Source_Plant", "Billing Source Plant"],
        "Dest_Plant_Key":   ["Dest_Plant_Key", "Dest Plant Key"],
        "Dest_Plant_Name":  ["Dest_Plant_Name", "Dest Plant Name"],
        "Dest_City":    ["Dest_City", "Dest City"],
        "SKU":          ["SKU", "Material", "Material No"],
        "Billing_Qty":  ["Billing_Qty", "Billing Qty(Cas)", "Billing Qty"],
        "Billing_Qty_KG": ["Billing_Qty_KG", "Billing Qty KG"],
        "Dest_State_Key": ["Dest_State_Key", "Dest State Key"],
        "Dest_State":   ["Dest_State", "Dest State"],
        "Dest_Unit":    ["Dest_Unit", "Dest Unit"],
        "Material_Type":["Material_Type", "Material Type"],
        "Vendor_No":    ["Vendor_No", "Vendor No"],
        "Vendor_Name":  ["Vendor_Name", "Vendor Name"],
        "Product_Category": ["Product_Category", "Product Category"],
        "SKU_Description": ["SKU_Description", "Material Name"],
    }

    has_named = any(_safe_col(df, *v) for v in NAMED.values())

    out = pd.DataFrame()
    if has_named:
        for dst, candidates in NAMED.items():
            c = _safe_col(df, *candidates)
            out[dst] = df[c].values if c else np.nan
    else:
        idx_map = {
            5: "Source_Plant", 11: "Truck_No", 12: "Shipment_Doc", 13: "Delivery_Doc",
            18: "Shipment_Type", 19: "Bill_Type", 20: "Invoice_No", 21: "Invoice_Date",
            22: "Billing_Source_Plant", 23: "Dest_Plant_Key", 24: "Dest_Plant_Name",
            25: "Dest_City", 26: "SKU", 28: "Billing_Qty", 29: "Billing_Qty_KG",
            41: "Dest_State_Key", 42: "Dest_State", 45: "Dest_Unit", 46: "Material_Type",
        }
        for idx, name in idx_map.items():
            out[name] = df.iloc[:, idx].values if idx < len(df.columns) else np.nan

    out["Invoice_Date"]    = _to_date(out.get("Invoice_Date", pd.Series(dtype=object)))
    out["Billing_Qty"]     = _to_numeric(out.get("Billing_Qty",    pd.Series(dtype=object)))
    out["Billing_Qty_KG"]  = _to_numeric(out.get("Billing_Qty_KG", pd.Series(dtype=object)))
    src = out.get("Source_Plant", pd.Series(["Unknown"] * len(out)))
    out["Plant"] = _norm_plant_series(src)
    return out.reset_index(drop=True)
