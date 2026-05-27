import pandas as pd
import streamlit as st
from typing import Optional, Tuple


@st.cache_data(show_spinner=False)
def load_zsd(file_bytes: bytes) -> Tuple[Optional[pd.DataFrame], Optional[str]]:
    try:
        df = pd.read_excel(file_bytes, sheet_name="Sheet1", engine="openpyxl", dtype=str)
        df.columns = df.columns.str.strip()
        for col in df.select_dtypes(include="object").columns:
            df[col] = df[col].str.strip()
        return df, None
    except Exception as e:
        return None, str(e)


@st.cache_data(show_spinner=False)
def load_nysd(file_bytes: bytes) -> Tuple[Optional[pd.DataFrame], Optional[str]]:
    try:
        df = pd.read_excel(file_bytes, sheet_name="Sheet1", engine="openpyxl", dtype=str)
        df.columns = df.columns.str.strip()
        for col in df.select_dtypes(include="object").columns:
            df[col] = df[col].str.strip()
        return df, None
    except Exception as e:
        return None, str(e)


@st.cache_data(show_spinner=False)
def load_transport(file_bytes: bytes) -> Tuple[Optional[pd.DataFrame], Optional[str]]:
    try:
        df = pd.read_excel(file_bytes, sheet_name="Sheet1", engine="openpyxl", header=0)
        return df, None
    except Exception as e:
        return None, str(e)


def get_transaction_types(df: pd.DataFrame) -> list:
    if df is None or "Transaction Typ Desc" not in df.columns:
        return []
    return sorted(df["Transaction Typ Desc"].dropna().unique().tolist())
