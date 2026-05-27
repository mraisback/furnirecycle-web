import pandas as pd
import streamlit as st
from typing import Optional, Tuple


def _strip_strings(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = df.columns.str.strip()
    for col in df.select_dtypes(include="object").columns:
        df[col] = df[col].where(pd.isna(df[col]), df[col].astype(str).str.strip())
    return df


@st.cache_data(show_spinner=False)
def load_zsd(file_bytes: bytes) -> Tuple[Optional[pd.DataFrame], Optional[str]]:
    try:
        df = pd.read_excel(file_bytes, sheet_name="Sheet1", engine="openpyxl")
        return _strip_strings(df), None
    except Exception as e:
        return None, str(e)


@st.cache_data(show_spinner=False)
def load_nysd(file_bytes: bytes) -> Tuple[Optional[pd.DataFrame], Optional[str]]:
    try:
        df = pd.read_excel(file_bytes, sheet_name="Sheet1", engine="openpyxl")
        return _strip_strings(df), None
    except Exception as e:
        return None, str(e)


@st.cache_data(show_spinner=False)
def load_transport(file_bytes: bytes) -> Tuple[Optional[pd.DataFrame], Optional[str]]:
    try:
        df = pd.read_excel(file_bytes, sheet_name="Sheet1", engine="openpyxl", header=0)
        return _strip_strings(df), None
    except Exception as e:
        return None, str(e)


@st.cache_data(show_spinner=False)
def load_master_wh(file_bytes: bytes) -> Tuple[Optional[pd.DataFrame], Optional[str]]:
    """Load Master_WH sheet from WOPS dashboard xlsx or a standalone file."""
    for sheet in ["Master_WH", "Master WH", "MasterWH", "Sheet1"]:
        try:
            df = pd.read_excel(file_bytes, sheet_name=sheet, engine="openpyxl")
            return _strip_strings(df), None
        except Exception:
            continue
    return None, "Could not find Master_WH sheet"


def get_transaction_types(df: Optional[pd.DataFrame]) -> list:
    if df is None or "Transaction Typ Desc" not in df.columns:
        return []
    return sorted(df["Transaction Typ Desc"].dropna().astype(str).unique().tolist())
