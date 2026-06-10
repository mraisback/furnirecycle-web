import gc
import io
from typing import Optional, Set, Tuple

import openpyxl
import pandas as pd
import streamlit as st

# ── Column sets for selective loading (lower-cased for case-insensitive match) ─
# Only the columns each file type actually uses are loaded; the rest are skipped,
# cutting pandas memory and parse time by ~40-60 % for wide SAP exports.

_SALEFL_NEEDED: Set[str] = {c.lower() for c in [
    "Transaction Typ Desc", "Transaction Type Desc", "Transaction Type Description",
    "Trans.Typ Desc", "Billing Type",
    "Invoice no", "Invoice No", "Invoice Number", "Invoice_No",
    "Billing Doc", "Doc. Number", "Document Number",
    "Date", "Invoice Date", "Billing Date", "Invoice_Date", "Order Date",
    "Billing Qty(Cas)", "Billing Qty (Cas)", "Cases", "Qty(Cas)",
    "Cases_Ordered", "Qty in CS", "Billing Qty",
    "Customer Name(SOLD)", "Customer Name", "Customer", "Sold-to Party",
    "Material", "SKU", "Material No", "Mat.", "SKU_Code",
    "Material Name", "SKU_Description", "Material Description", "Description",
    "Batch", "Batch No", "Lot No", "Lot_No", "Batch Number",
    "Line Item Usage Reason Desc.", "Line Item Usage Reason",
    "Usage Reason", "Return Reason", "Return_Reason_Code",
    "Expiry Date", "Expiry_Date", "EXP Date", "Expiry", "Best Before",
    "Plant", "Source Plant - Key", "Source Plant", "Plant Code", "Warehouse Code",
    "Dist.Channel Desc.", "Dist Channel Desc.", "Distribution Channel",
    "Customer_Type", "Channel",
    "Truck No", "Truck No.", "Vehicle Number", "Carrier",
    "Basic", "MRP", "Gross Revenue New", "Invoice Value", "Unit_Price_INR", "Rate",
    "Item no", "Item No", "Item no.", "Line Item", "Order Line",
    "Reference Invoice Number", "Ref Invoice", "Reference Doc",
    "Ref. Invoice No", "Reference Document Number",
]}

_TRANSPORT_NEEDED: Set[str] = {c.lower() for c in [
    "Source Plant - Key", "Source Plant", "Source_Plant", "Plant",
    "Truck No", "Truck No.", "Truck no", "Truck_No",
    "Shipment Doc - Key", "Shipment Doc",
    "Delivery Doc No", "Delivery Doc",
    "Shipment type - Text", "Shipment Type - Text", "Shipment Type", "Shipment type",
    "Bill Type - Key", "Bill Type",
    "Invoice No", "Invoice no", "Invoice_No",
    "Invoice Date", "Invoice_Date", "Date",
    "Billing Source Plant",
    "Customer No/Destination Plant - Key", "Dest Plant Key", "Dest_Plant_Key",
    "Customer No/Destination Plant - Text", "Dest Plant Name", "Dest_Plant_Name",
    "Destination Plant City", "Dest City", "Dest_City",
    "Destination State - Key", "Dest State Key", "Dest_State_Key",
    "Destination State - Text", "Dest State", "Dest_State",
    "Destination Unit - Text", "Dest Unit", "Dest_Unit",
    "Material - Key", "Material", "Material No", "SKU",
    "Material - Text", "Material Name", "Material Description", "SKU_Description",
    "Material Type - Text", "Material Type - Key", "Material Type", "Material_Type",
    "Product Category - Text", "Product Category",
    "Billed Qty(CAS)", "Billing Qty(Cas)", "Billing Qty (Cas)", "Billing Qty", "Billing_Qty",
    "Billing Qty KG", "Billing Qty(KG)", "Billing_Qty_KG",
    "Vendor - Key", "Vendor No", "Vendor_No",
    "Vendor - Text", "Vendor Name", "Vendor_Name",
]}

_NYSD_NEEDED: Set[str] = {c.lower() for c in [
    "SKU", "Material No", "Material", "SKU_Code",
    "SKU_Description", "Material Description", "Material Name", "Description",
    "Lot_No", "Batch No", "Batch", "Lot No",
    "Expiry_Date", "EXP Date", "Expiry Date", "Expiry",
    "Cases_On_Hand", "Qty in CS", "Cases", "Qty",
    "Unit_Cost_INR", "MRP Rate", "MRP", "Unit Cost",
    "Inventory_Value_INR", "Value OF Stock", "Inventory Value", "Value",
    "Status", "Storage Description", "Lot Status",
    "Plant", "Plant Code", "Warehouse Code",
]}


def _strip_strings(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = df.columns.str.strip()
    for col in df.select_dtypes(include="object").columns:
        df[col] = df[col].where(pd.isna(df[col]), df[col].astype(str).str.strip())
    return df


def _to_buffer(file_bytes: bytes) -> io.BytesIO:
    return io.BytesIO(file_bytes)


def _find_sheet_and_header(
    file_bytes: bytes, preferred_names: list
) -> Tuple[Optional[str], Optional[list]]:
    """One fast openpyxl read_only pass: find the right sheet and return its headers."""
    try:
        wb = openpyxl.load_workbook(_to_buffer(file_bytes), read_only=True, data_only=True)
        try:
            names = wb.sheetnames
            sheet_name = None
            for s in preferred_names:
                if s in names:
                    sheet_name = s
                    break
            if sheet_name is None and names:
                sheet_name = names[0]
            if sheet_name is None:
                return None, None
            ws = wb[sheet_name]
            first_row = next(ws.iter_rows(values_only=True), [])
            cols = [str(h).strip() if h is not None else "" for h in first_row]
            return sheet_name, cols
        finally:
            wb.close()
    except Exception:
        return None, None


def _read_sheet_filtered(
    file_bytes: bytes,
    preferred_names: list,
    needed_lower: Set[str],
) -> Tuple[Optional[pd.DataFrame], Optional[str]]:
    """Two-phase read: fast header scan → full read with usecols filter."""
    sheet_name, headers = _find_sheet_and_header(file_bytes, preferred_names)

    if sheet_name is None:
        # openpyxl failed — fall back to pandas plain read
        try:
            df = pd.read_excel(_to_buffer(file_bytes), sheet_name=0, engine="openpyxl")
            return _strip_strings(df), None
        except Exception as e:
            return None, str(e)

    usecols = None
    if needed_lower and headers:
        matched = [h for h in headers if h.lower() in needed_lower]
        if matched:
            usecols = matched

    try:
        df = pd.read_excel(
            _to_buffer(file_bytes),
            sheet_name=sheet_name,
            usecols=usecols,
            engine="openpyxl",
        )
        return _strip_strings(df), None
    except Exception as e:
        return None, str(e)


def _read_first_sheet(
    file_bytes: bytes, preferred_names: list
) -> Tuple[Optional[pd.DataFrame], Optional[str]]:
    """Try each sheet name in order; then keyword-search; then first sheet."""
    for sheet in preferred_names:
        try:
            df = pd.read_excel(_to_buffer(file_bytes), sheet_name=sheet, engine="openpyxl")
            return _strip_strings(df), None
        except Exception:
            pass
    try:
        df = pd.read_excel(_to_buffer(file_bytes), sheet_name=0, engine="openpyxl")
        return _strip_strings(df), None
    except Exception as e:
        return None, str(e)


def _read_with_keyword_search(
    file_bytes: bytes, preferred_names: list, keywords: list
) -> Tuple[Optional[pd.DataFrame], Optional[str]]:
    """Try preferred names, then keyword-match any sheet, then first sheet."""
    for sheet in preferred_names:
        try:
            df = pd.read_excel(_to_buffer(file_bytes), sheet_name=sheet, engine="openpyxl")
            return _strip_strings(df), None
        except Exception:
            pass
    try:
        xl = pd.ExcelFile(_to_buffer(file_bytes), engine="openpyxl")
        for sh in xl.sheet_names:
            sh_lower = sh.lower()
            if all(kw.lower() in sh_lower for kw in keywords):
                df = pd.read_excel(_to_buffer(file_bytes), sheet_name=sh, engine="openpyxl")
                return _strip_strings(df), None
        for kw in keywords:
            for sh in xl.sheet_names:
                if kw.lower() in sh.lower():
                    df = pd.read_excel(_to_buffer(file_bytes), sheet_name=sh, engine="openpyxl")
                    return _strip_strings(df), None
    except Exception:
        pass
    try:
        df = pd.read_excel(_to_buffer(file_bytes), sheet_name=0, engine="openpyxl")
        return _strip_strings(df), None
    except Exception as e:
        return None, str(e)


@st.cache_data(show_spinner=False, max_entries=4)
def load_zsd(file_bytes: bytes) -> Tuple[Optional[pd.DataFrame], Optional[str]]:
    preferred = ["Sheet1", "zsd_salefl_Data", "Data", "Sheet 1"]
    result = _read_sheet_filtered(file_bytes, preferred, _SALEFL_NEEDED)
    gc.collect()
    return result


@st.cache_data(show_spinner=False, max_entries=4)
def load_nysd(file_bytes: bytes) -> Tuple[Optional[pd.DataFrame], Optional[str]]:
    preferred = ["Sheet1", "nysd_css_Data", "Data", "Sheet 1"]
    result = _read_sheet_filtered(file_bytes, preferred, _NYSD_NEEDED)
    gc.collect()
    return result


@st.cache_data(show_spinner=False, max_entries=4)
def load_transport(file_bytes: bytes) -> Tuple[Optional[pd.DataFrame], Optional[str]]:
    # "Report 1" is the sheet name used in YTFPN freight exports
    preferred = ["Report 1", "Sheet1", "YTFPN", "Transport", "Sheet 1", "Data"]
    result = _read_sheet_filtered(file_bytes, preferred, _TRANSPORT_NEEDED)
    gc.collect()
    return result


@st.cache_data(show_spinner=False, max_entries=4)
def load_master_wh(file_bytes: bytes) -> Tuple[Optional[pd.DataFrame], Optional[str]]:
    return _read_first_sheet(
        file_bytes, ["Master_WH", "Master WH", "MasterWH", "Sheet1", "Sheet 1"]
    )


@st.cache_data(show_spinner=False, max_entries=4)
def load_ost(file_bytes: bytes) -> Tuple[Optional[pd.DataFrame], Optional[str]]:
    # Handles "Order to Service Time May-26" and similar sheet names via keyword search
    return _read_with_keyword_search(
        file_bytes,
        preferred_names=["Sheet1", "OST_Report", "OST", "Sheet 1"],
        keywords=["order", "service"],
    )


def get_transaction_types(df: Optional[pd.DataFrame]) -> list:
    if df is None:
        return []
    for col in ["Transaction Typ Desc", "Transaction Type Desc",
                "Transaction Type Description", "Trans.Typ Desc", "Billing Type"]:
        if col in df.columns:
            return sorted(df[col].dropna().astype(str).str.strip().unique().tolist())
    return []
