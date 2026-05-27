import pandas as pd
import numpy as np
from datetime import date
from typing import Optional, Dict
import streamlit as st
from src.filters import add_zone, build_zone_map_from_master

PHYSICAL_DAMAGE = {"AIR LEAK/DAMAGE PIEC", "CARTON DAMAGE", "DAMAGED IN TRANSIT"}
QUALITY_ISSUE   = {"QAS RELATED ISSUE", "AGING STOCK"}
COMMERCIAL      = {"PRICING ISSUE", "PACK SIZE/ GRAMMAGE", "ALL ISSUESRELATED PO", "THROUGH CUSTOMER"}
OTHER_REASONS   = {"INTER CHANGE", "OTHER REASON"}

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
    """Parse dates — handles datetime objects, ISO strings, and Excel serials."""
    def _parse_one(v):
        if pd.isna(v):
            return pd.NaT
        if isinstance(v, (pd.Timestamp,)):
            return v
        try:
            return pd.to_datetime(v)
        except Exception:
            pass
        # Try Excel serial number
        try:
            from datetime import datetime, timedelta
            serial = float(str(v).replace(',', '').strip())
            if 1 < serial < 200000:  # sanity check: valid Excel date range
                return pd.Timestamp(datetime(1899, 12, 30) + timedelta(days=serial))
        except Exception:
            pass
        return pd.NaT

    return series.apply(_parse_one)


def _norm_plant(val) -> str:
    """Normalise plant code to clean string (5135.0 → '5135')."""
    if pd.isna(val) or str(val).strip() in ("", "nan", "None"):
        return "Unknown"
    s = str(val).strip()
    try:
        if float(s) == int(float(s)):
            return str(int(float(s)))
    except (ValueError, OverflowError):
        pass
    return s


def _classify_damage(reason) -> str:
    if not isinstance(reason, str) or not reason.strip():
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

    # Build zone map from Master_WH if provided
    zone_map = {}
    name_map = {}
    if master_wh_bytes:
        mwh_df, _ = load_master_wh(master_wh_bytes)
        zone_map, name_map = build_zone_map_from_master(mwh_df)

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

    # Apply zone mapping to every dataframe at the end
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
    out["Plant"]           = df[plant_col].apply(_norm_plant).values if plant_col else "Unknown"
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
    out["Plant"]             = df[plant_col].apply(_norm_plant).values if plant_col else "Unknown"

    out["Lot_No_Status"] = out["Lot_No"].apply(
        lambda x: "MISSING BATCH"
        if (pd.isna(x) or str(x).strip() in ("", "nan", "None"))
        else "OK"
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
    out["Plant"]              = df[plant_col].apply(_norm_plant).values if plant_col else "Unknown"
    out["Damage_Category"]    = out["Return_Reason_Code"].apply(_classify_damage)
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
    out["Plant"]                 = df[plant_col].apply(_norm_plant).values if plant_col else "Unknown"

    reason_series = df[reason_col] if reason_col else pd.Series([""] * len(df))
    out["Good_Cases"] = out.apply(
        lambda r: r["Total_Cases_Received"]
        if str(reason_series.iloc[r.name] if hasattr(reason_series, 'iloc') else "").strip() in ("", "nan", "None")
        else 0,
        axis=1,
    )
    out["Damaged_Cases"] = out["Total_Cases_Received"] - out["Good_Cases"]
    return out.reset_index(drop=True)


def _expiry_risk(expiry_date, today: date) -> str:
    if pd.isna(expiry_date):
        return "Unknown"
    try:
        exp = expiry_date.date() if hasattr(expiry_date, "date") else expiry_date
        days = (exp - today).days
    except Exception:
        return "Unknown"
    if days < 0:
        return "Expired"
    if days <= 30:
        return "0-30 Days"
    if days <= 45:
        return "30-45 Days"
    if days <= 60:
        return "45-60 Days"
    return "OK"


def _build_inventory(nysd_df: pd.DataFrame) -> pd.DataFrame:
    """Build inventory from nysd_css — columns are already Power Query-renamed."""
    if nysd_df.empty:
        return pd.DataFrame()

    # nysd_css already has clean column names per the schema.
    # Provide fallbacks in case the user uploads a raw variant.
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
    out["SKU"]                = nysd_df[sku_col].values   if sku_col   else np.nan
    out["SKU_Description"]    = nysd_df[desc_col].values  if desc_col  else np.nan
    out["Lot_No"]             = nysd_df[lot_col].astype(str).values if lot_col else np.nan
    out["Expiry_Date"]        = _to_date(nysd_df[exp_col]) if exp_col  else pd.NaT
    out["Cases_On_Hand"]      = _to_numeric(nysd_df[qty_col]).astype(int) if qty_col else 0
    out["Unit_Cost_INR"]      = _to_numeric(nysd_df[cost_col]) if cost_col else 0.0
    out["Inventory_Value_INR"]= _to_numeric(nysd_df[val_col]) if val_col  else 0.0
    out["Status"]             = nysd_df[stat_col].values  if stat_col  else np.nan
    out["Plant"]              = nysd_df[plant_col].apply(_norm_plant).values if plant_col else "Unknown"
    out["Month_End_Date"]     = pd.Timestamp(date.today())

    today = date.today()
    out["Expiry_Risk"] = out["Expiry_Date"].apply(lambda x: _expiry_risk(x, today))
    return out.reset_index(drop=True)


def _build_inventory_accuracy(receiving, despatch, returns, inventory) -> pd.DataFrame:
    plants: set = set()
    for df in [receiving, despatch, returns, inventory]:
        if df is not None and "Plant" in df.columns:
            plants.update(df["Plant"].dropna().unique())

    rows = []
    for plant in sorted(str(p) for p in plants):
        def psum(df, col):
            if df is None or col not in df.columns:
                return 0.0
            sub = df[df["Plant"] == plant]
            return _to_numeric(sub[col]).sum()

        mov_in    = psum(receiving, "Total_Cases_Received")
        mov_out   = psum(despatch, "Cases_Despatched")
        ret_qty   = psum(returns, "Returned_Cases")
        actual    = psum(inventory, "Cases_On_Hand")
        expected  = mov_in - mov_out + ret_qty
        deviation = actual - expected
        accuracy  = 1.0 - abs(deviation) / max(abs(expected), 1)

        rows.append({
            "Plant":          plant,
            "Movement_In":    mov_in,
            "Movement_Out":   mov_out,
            "Returns_Qty":    ret_qty,
            "Expected_Stock": expected,
            "Actual_Stock":   actual,
            "Cases_Deviation":deviation,
            "Accuracy_%":     round(accuracy * 100, 2),
        })

    return pd.DataFrame(rows)


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
        # Positional fallback for raw SAP export (47+ columns)
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
    out["Plant"] = src.apply(_norm_plant)
    return out.reset_index(drop=True)
