import pandas as pd

ZONE_MAP = {
    # EAST
    "Guwahati WH - AS": "East",
    "JORHAT WH - AS": "East",
    "KOLKATA-1- WH - WB": "East",
    "KOLKATA 3P": "East",
    "Kolkata WH - WB": "East",
    "Patna WH - BH": "East",
    "Raipur WH - CT": "East",
    "Ranchi WH - JH": "East",
    "Silchar WH - AS": "East",
    "Siliguri WH - WB": "East",
    # NORTH
    "Barota WH - HR": "North",
    "Channo 3P - PB": "North",
    "Dehradun WH - UT": "North",
    "Kanpur WH - UP": "North",
    "KANPUR WH - WEST": "North",
    "KOSI WH": "North",
    "PATAUDI (New) WH - HR": "North",
    "RAMPUR WH - UP": "North",
    "Sujanpur WH - PB": "North",
    "Varanasi WH - UP": "North",
    "HODAL WH - HR": "North",
    # SOUTH
    "Bangalore WH - KN": "South",
    "Chennai WH - TN": "South",
    "Cochin WH - KL": "South",
    "COIMBATORE WH - AT": "South",
    "Hyderabad HMDA WH - AP": "South",
    "MANGALORE WH - KN": "South",
    "Trichy WH - TN": "South",
    "Vijayawada WH - AT": "South",
    "Hubli WH - KN": "South",
    "VIZAG WH - AT": "South",
    # WEST
    "Ahmedabad WH - GJ": "West",
    "Goa WH - GO": "West",
    "Indore WH - MP": "West",
    "Jaipur WH - RJ": "West",
    "Nagpur WH - MH": "West",
    "Pune WH - MH & Pune 3P": "West",
}


def apply_filter(df: pd.DataFrame, zone_sel: str, plant_sel: str) -> pd.DataFrame:
    if df is None or df.empty:
        return df
    if plant_sel != "All Plants" and "Plant" in df.columns:
        return df[df["Plant"] == plant_sel]
    elif zone_sel != "All Zones" and "Zone" in df.columns:
        return df[df["Zone"] == zone_sel]
    return df


def add_zone(df: pd.DataFrame) -> pd.DataFrame:
    if df is not None and "Plant" in df.columns:
        df["Zone"] = df["Plant"].map(ZONE_MAP).fillna("Unknown")
    return df
