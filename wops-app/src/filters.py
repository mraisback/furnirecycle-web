import pandas as pd
from typing import Optional, Dict, Tuple, Any

# ── Numeric plant-code → Zone (hardcoded from Master_WH) ─────────────────────
ZONE_MAP: Dict[str, str] = {
    # EAST
    "5313": "East",   # Guwahati WH - AS
    "5325": "East",   # JORHAT WH - AS
    "5334": "East",   # KOLKATA-1- WH - WB
    "5085": "East",   # KOLKATA 3P
    "5328": "East",   # Kolkata WH - WB
    "5327": "East",   # Patna WH - BH
    "5419": "East",   # Raipur WH - CT
    "5303": "East",   # Ranchi WH - JH
    "5320": "East",   # Silchar WH - AS
    "5329": "East",   # Siliguri WH - WB
    # NORTH
    "5129": "North",  # Barota WH - HR
    "5054": "North",  # Channo 3P - PB
    "5216": "North",  # Dehradun WH - UT
    "5211": "North",  # Kanpur WH - UP
    "5224": "North",  # Kanpur WH - UP
    "5227": "North",  # KANPUR WH - WEST
    "5083": "North",  # KOSI WH
    "5082": "North",  # KOSI WH
    "5228": "North",  # KOSI WH
    "5229": "North",  # KOSI WH
    "5139": "North",  # PATAUDI (New) WH - HR
    "5225": "North",  # RAMPUR WH - UP
    "5226": "North",  # RAMPUR WH - UP
    "5135": "North",  # Sujanpur WH - PB
    "5222": "North",  # Varanasi WH - UP
    "5140": "North",  # HODAL WH - HR
    # SOUTH
    "5713": "South",  # Bangalore WH - KN
    "5524": "South",  # Chennai WH - TN
    "5523": "South",  # Cochin WH - KL
    "5526": "South",  # COIMBATORE WH - AT
    "5710": "South",  # Hyderabad HMDA WH - AP
    "5709": "South",  # MANGALORE WH - KN
    "5514": "South",  # Trichy WH - TN
    "5703": "South",  # Vijayawada WH - AT
    "5702": "South",  # Hubli WH - KN
    "5712": "South",  # VIZAG WH - AT
    # WEST
    "5813": "West",   # Ahmedabad WH - GJ
    "5403": "West",   # Goa WH - GO
    "5220": "West",   # Indore WH - MP
    "5217": "West",   # Jaipur WH - RJ
    "5407": "West",   # Nagpur WH - MH
    "5418": "West",   # Pune WH - MH & Pune 3P
    "5024": "West",   # Pune WH - MH & Pune 3P
}

# ── Numeric plant-code → Warehouse display name ───────────────────────────────
PLANT_NAME_MAP: Dict[str, str] = {
    "5313": "Guwahati WH - AS",
    "5325": "JORHAT WH - AS",
    "5334": "KOLKATA-1- WH - WB",
    "5085": "KOLKATA 3P",
    "5328": "Kolkata WH - WB",
    "5327": "Patna WH - BH",
    "5419": "Raipur WH - CT",
    "5303": "Ranchi WH - JH",
    "5320": "Silchar WH - AS",
    "5329": "Siliguri WH - WB",
    "5129": "Barota WH - HR",
    "5054": "Channo 3P - PB",
    "5216": "Dehradun WH - UT",
    "5211": "Kanpur WH - UP (5211)",
    "5224": "Kanpur WH - UP (5224)",
    "5227": "KANPUR WH - WEST",
    "5083": "KOSI WH (5083)",
    "5082": "KOSI WH (5082)",
    "5228": "KOSI WH (5228)",
    "5229": "KOSI WH (5229)",
    "5139": "PATAUDI (New) WH - HR",
    "5225": "RAMPUR WH - UP (5225)",
    "5226": "RAMPUR WH - UP (5226)",
    "5135": "Sujanpur WH - PB",
    "5222": "Varanasi WH - UP",
    "5140": "HODAL WH - HR",
    "5713": "Bangalore WH - KN",
    "5524": "Chennai WH - TN",
    "5523": "Cochin WH - KL",
    "5526": "COIMBATORE WH - AT",
    "5710": "Hyderabad HMDA WH - AP",
    "5709": "MANGALORE WH - KN",
    "5514": "Trichy WH - TN",
    "5703": "Vijayawada WH - AT",
    "5702": "Hubli WH - KN",
    "5712": "VIZAG WH - AT",
    "5813": "Ahmedabad WH - GJ",
    "5403": "Goa WH - GO",
    "5220": "Indore WH - MP",
    "5217": "Jaipur WH - RJ",
    "5407": "Nagpur WH - MH",
    "5418": "Pune WH - MH (5418)",
    "5024": "Pune WH - MH (5024)",
}


def _norm_plant_key(val) -> str:
    """Normalise a plant value to a string key: 5135.0 → '5135'."""
    if pd.isna(val) or str(val).strip() in ("", "nan", "None"):
        return ""
    s = str(val).strip()
    try:
        if float(s) == int(float(s)):
            return str(int(float(s)))
    except (ValueError, OverflowError):
        pass
    return s


def build_zone_map_from_master(
    master_df: Optional[pd.DataFrame],
) -> Tuple[Dict[str, str], Dict[str, str]]:
    """Return ({plant_key: zone}, {plant_key: name}) from an uploaded Master_WH sheet.
    Used to OVERRIDE the built-in ZONE_MAP / PLANT_NAME_MAP if FILE 4 is provided."""
    if master_df is None or master_df.empty:
        return {}, {}

    def _find(df, *candidates):
        for c in candidates:
            if c in df.columns:
                return c
        lower = {col.lower(): col for col in df.columns}
        for c in candidates:
            found = lower.get(c.lower())
            if found:
                return found
        return None

    code_col = _find(master_df, "Warehouse Code *", "Warehouse Code", "Plant", "Plant Code")
    zone_col = _find(master_df, "Zone *", "Zone")
    name_col = _find(master_df, "Warehouse Name *", "Warehouse Name")

    if not code_col or not zone_col:
        return {}, {}

    zone_map: Dict[str, str] = {}
    name_map: Dict[str, str] = {}
    for _, row in master_df.iterrows():
        key = _norm_plant_key(row[code_col])
        if not key or key == "All Plants":
            continue
        zone = row.get(zone_col)
        if pd.notna(zone) and str(zone).strip() not in ("", "All Plants"):
            zone_map[key] = str(zone).strip()
        if name_col:
            name = row.get(name_col)
            if pd.notna(name) and str(name).strip() not in ("", "All Plants"):
                name_map[key] = str(name).strip()

    return zone_map, name_map


def add_zone(df: pd.DataFrame, zone_map: Optional[Dict] = None) -> pd.DataFrame:
    """Add Zone column. Uses provided zone_map (from FILE 4) or built-in ZONE_MAP."""
    if df is None or "Plant" not in df.columns:
        return df
    effective = zone_map if zone_map else ZONE_MAP
    df["Zone"] = df["Plant"].apply(_norm_plant_key).map(effective).fillna("Unknown")
    return df


def apply_filter(
    df: pd.DataFrame,
    zone_sel: str,
    plant_sel: str,
) -> pd.DataFrame:
    if df is None or df.empty:
        return df
    if plant_sel != "All Plants" and "Plant" in df.columns:
        plant_keys = df["Plant"].apply(_norm_plant_key)
        return df[plant_keys == _norm_plant_key(plant_sel)]
    elif zone_sel != "All Zones" and "Zone" in df.columns:
        return df[df["Zone"] == zone_sel]
    return df


def build_master_wh_numeric_maps(
    master_df: Optional[pd.DataFrame],
) -> Dict[str, Dict[str, float]]:
    """Extract per-plant numeric columns from Master_WH.

    Returns a dict with keys: 'rent', 'capacity', 'area', 'labour'
    Each value is {plant_code_str: float}.
    """
    empty: Dict[str, Dict[str, float]] = {
        "rent": {}, "capacity": {}, "area": {}, "labour": {}, "unload_labour": {}
    }
    if master_df is None or master_df.empty:
        return empty

    def _find(df: pd.DataFrame, *candidates: str) -> Optional[str]:
        for c in candidates:
            if c in df.columns:
                return c
        lower = {col.lower(): col for col in df.columns}
        for c in candidates:
            found = lower.get(c.lower())
            if found:
                return found
        return None

    code_col = _find(master_df,
        "Warehouse Code *", "Warehouse Code", "Plant", "Plant Code")
    rent_col = _find(master_df,
        "Rent", "Monthly Rent", "Rent (₹)", "Monthly Rent (₹)",
        "Rent_INR", "Rent (INR)")
    cap_col  = _find(master_df,
        "Capacity", "Capacity (Cases)", "WH Capacity",
        "Storage Capacity", "Storage Capacity (Cases)")
    area_col = _find(master_df,
        "Usable Area", "Usable Area (Sqft)", "Area (Sqft)",
        "Floor Area", "Floor Area (Sqft)", "Area")
    lab_col  = _find(master_df,
        "Labour", "Manpower", "Fixed Manpower", "No. of Manpower",
        "Headcount", "Labour Count", "Labour (Nos)")
    unload_lab_col = _find(master_df,
        "Unloading Labour", "Unloading Manpower", "Unload Labour",
        "Labour (Unloading)", "Unloading Labour (Nos)", "Unloading_Labour",
        "Unload_Labour", "Unloading labor")

    if not code_col:
        return empty

    maps: Dict[str, Dict[str, float]] = {
        "rent": {}, "capacity": {}, "area": {}, "labour": {}, "unload_labour": {}
    }
    col_mapping = [
        ("rent",          rent_col),
        ("capacity",      cap_col),
        ("area",          area_col),
        ("labour",        lab_col),
        ("unload_labour", unload_lab_col),
    ]

    for _, row in master_df.iterrows():
        key = _norm_plant_key(row[code_col])
        if not key or key in ("", "All Plants"):
            continue
        for map_key, col_name in col_mapping:
            if not col_name:
                continue
            val = pd.to_numeric(row.get(col_name), errors="coerce")
            if pd.notna(val) and val > 0:
                maps[map_key][key] = float(val)

    return maps
