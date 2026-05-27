GLOBAL_CSS = """
<style>
/* Hide default streamlit header padding */
.block-container { padding-top: 1rem; }

/* KPI card base */
.kpi-card {
    background: #111D2E;
    padding: 12px;
    border-radius: 4px;
    text-align: center;
    height: 100%;
}
.kpi-title {
    color: #8AAAC8;
    font-size: 11px;
    margin: 0;
    font-weight: 600;
    letter-spacing: 0.5px;
    text-transform: uppercase;
}
.kpi-value {
    font-size: 28px;
    font-weight: 700;
    margin: 4px 0;
}
.kpi-subtitle {
    color: #4A6070;
    font-size: 10px;
    margin: 0;
}

/* Selector bar */
.selector-bar {
    background: #1565C0;
    padding: 10px 20px;
    border-radius: 4px;
    color: white;
    font-size: 14px;
    font-weight: 600;
    margin-bottom: 12px;
}

/* Error table styling */
.error-high   { color: #E74C3C; font-weight: 700; }
.error-medium { color: #E67E22; font-weight: 700; }
.error-low    { color: #F1C40F; font-weight: 700; }

/* Tab spacing */
.stTabs [data-baseweb="tab"] { font-size: 14px; padding: 8px 20px; }
</style>
"""


def kpi_card(title: str, value: str, subtitle: str = "",
             border_color: str = "#1565C0", value_color: str = "#FFFFFF") -> str:
    return f"""
<div style="background:#111D2E; border-top:3px solid {border_color};
            padding:12px; border-radius:4px; text-align:center; height:100%">
  <p style="color:#8AAAC8; font-size:11px; margin:0; font-weight:600;
            letter-spacing:0.5px; text-transform:uppercase">{title}</p>
  <p style="color:{value_color}; font-size:28px; font-weight:700;
            margin:4px 0">{value}</p>
  <p style="color:#4A6070; font-size:10px; margin:0">{subtitle}</p>
</div>"""


def selector_bar(plant: str, zone: str) -> str:
    return f"""
<div style="background:#1565C0; padding:10px 20px; border-radius:4px;
            color:white; font-size:14px; font-weight:600; margin-bottom:12px">
  Plant: <span style="font-weight:400">{plant}</span>
  &nbsp;&nbsp;|&nbsp;&nbsp;
  Zone: <span style="font-weight:400">{zone}</span>
</div>"""


def fmt_indian(n: float) -> str:
    """Format number in Indian comma notation."""
    try:
        n = int(round(n))
        if n < 0:
            return f"-{fmt_indian(-n)}"
        s = str(n)
        if len(s) <= 3:
            return s
        last3 = s[-3:]
        rest = s[:-3]
        parts = []
        while len(rest) > 2:
            parts.append(rest[-2:])
            rest = rest[:-2]
        if rest:
            parts.append(rest)
        parts.reverse()
        return ",".join(parts) + "," + last3
    except Exception:
        return str(n)


def fmt_currency(n: float) -> str:
    return f"₹{fmt_indian(n)}"


def rate_color(rate: float, thresholds=(2.0, 5.0),
               colors=("#27AE60", "#E67E22", "#C0392B")) -> str:
    if rate < thresholds[0]:
        return colors[0]
    if rate < thresholds[1]:
        return colors[1]
    return colors[2]


def accuracy_color(acc: float) -> str:
    if acc >= 97:
        return "#27AE60"
    if acc >= 90:
        return "#E67E22"
    return "#C0392B"
