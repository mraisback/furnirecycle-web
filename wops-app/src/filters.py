import pandas as pd
from typing import Optional, Dict, Tuple

ZONE_MAP = {
    # EAST
    "Guwahati WH - AS":       "East",
    "JORHAT WH - AS":         "East",
    "KOLKATA-1- WH - WB":     "East",
    "KOLKATA 3P":             "East",
    "Kolkata WH - WB":        "East",
    "Patna WH - BH":          "East",
    "Raipur WH - CT":         "East",
    "Ranchi WH - JH":         "East",
    "Silchar WH - AS":        "East",
    "Siliguri WH - WB":       "East",
    # NORTH
    "Barota WH - HR":         "North",
    "Channo 3P - PB":         "North",
    "Dehradun WH - UT":       "North",
    "Kanpur WH - UP":         "North",
    "KANPUR WH - WEST":       "North",
    "KOSI WH":                "North",
    "PATAUDI (New) WH - HR":  "North",
    "RAMPUR WH - UP":         "North",
    "Sujanpur WH - PB":       "North",
    "Varanasi WH - UP":       "North",
    "HODAL WH - HR":          "North",
    # SOUTH
    "Bangalore WH - KN":      "South",
    "Chennai WH - TN":        "South",
    "Cochin WH - KL":         "South",
    "COIMBATORE WH - AT":     "South",
    "Hyderabad HMDA WH - AP": "South",
    "MANGALORE WH - KN":      "South",
    "Trichy WH - TN":         "South",
    "Vijayawada WH - AT":     "South",
    "Hubli WH - KN":          "South",
    "VIZAG WH - AT":          "South",
    # WEST
    "Ahmedabad WH - GJ":           "West",
    "Goa WH - GO":                 "West",
    "Indore WH - MP":              "West",
    "Jaipur WH - RJ":              "West",
    "Nagpur WH - MH":              "West",
    "Pune WH - MH & Pune 3P":      "West",
}


def _norm_plant_key(val) -> str:
    """Normalise a plant value to a string key for mapping/comparison."""
    if pd.isna(val) or str(val).strip() in ("", "nan", "None"):
        return ""
    s = str(val).strip()
    # Convert numeric float/int to clean int string: "5135.0" → "5135"
    try:
        if float(s) == int(float(s)):
            return str(int(float(s)))
    except (ValueError, OverflowError):
        pass
    return s


def build_zone_map_from_master(
    master_df: Optional[pd.DataFrame],
) -> Tuple[Dict[str, str], Dict[str, str]]:
    """Return ({plant_key: zone}, {plant_key: warehouse_name}) from Master_WH sheet."""
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
        if not key:
            continue
        zone = row.get(zone_col)
        if pd.notna(zone):
            zone_map[key] = str(zone).strip()
        if name_col:
            name = row.get(name_col)
            if pd.notna(name):
                name_map[key] = str(name).strip()

    return zone_map, name_map


def add_zone(df: pd.DataFrame, zone_map: Optional[Dict] = None) -> pd.DataFrame:
    """Add Zone column using zone_map (numeric codes) or ZONE_MAP fallback (text names)."""
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
