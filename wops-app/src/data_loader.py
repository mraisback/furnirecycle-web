import io
import pandas as pd
import streamlit as st
from typing import Optional, Tuple


def _strip_strings(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = df.columns.str.strip()
    for col in df.select_dtypes(include="object").columns:
        df[col] = df[col].where(pd.isna(df[col]), df[col].astype(str).str.strip())
    return df


def _to_buffer(file_bytes: bytes) -> io.BytesIO:
    """Wrap raw bytes in a BytesIO buffer so pd.read_excel accepts it."""
    return io.BytesIO(file_bytes)


def _read_first_sheet(
    file_bytes: bytes, preferred_names: list
) -> Tuple[Optional[pd.DataFrame], Optional[str]]:
    """Try each sheet name in order; then keyword-search sheet names; then first sheet."""
    for sheet in preferred_names:
        try:
            df = pd.read_excel(_to_buffer(file_bytes), sheet_name=sheet, engine="openpyxl")
            return _strip_strings(df), None
        except Exception:
            pass
    # Last resort: load whichever sheet is first (index 0)
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
        # Try any single keyword match as secondary fallback
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


@st.cache_data(show_spinner=False)
def load_zsd(file_bytes: bytes) -> Tuple[Optional[pd.DataFrame], Optional[str]]:
    return _read_first_sheet(file_bytes, ["Sheet1", "zsd_salefl_Data", "Data", "Sheet 1"])


@st.cache_data(show_spinner=False)
def load_nysd(file_bytes: bytes) -> Tuple[Optional[pd.DataFrame], Optional[str]]:
    return _read_first_sheet(file_bytes, ["Sheet1", "nysd_css_Data", "Data", "Sheet 1"])


@st.cache_data(show_spinner=False)
def load_transport(file_bytes: bytes) -> Tuple[Optional[pd.DataFrame], Optional[str]]:
    # "Report 1" is the sheet name used in YTFPN freight exports
    return _read_first_sheet(
        file_bytes, ["Report 1", "Sheet1", "YTFPN", "Transport", "Sheet 1", "Data"]
    )


@st.cache_data(show_spinner=False)
def load_master_wh(file_bytes: bytes) -> Tuple[Optional[pd.DataFrame], Optional[str]]:
    for sheet in ["Master_WH", "Master WH", "MasterWH", "Sheet1", "Sheet 1"]:
        try:
            df = pd.read_excel(_to_buffer(file_bytes), sheet_name=sheet, engine="openpyxl")
            return _strip_strings(df), None
        except Exception:
            continue
    try:
        df = pd.read_excel(_to_buffer(file_bytes), sheet_name=0, engine="openpyxl")
        return _strip_strings(df), None
    except Exception as e:
        return None, str(e)


@st.cache_data(show_spinner=False)
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
