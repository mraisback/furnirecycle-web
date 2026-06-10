GLOBAL_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

/* ── Base typography ─────────────────────────────────────────── */
html, body, [class*="css"], .stMarkdown, .stApp {
    font-family: 'Inter', -apple-system, 'Segoe UI', Roboto, sans-serif;
}
.block-container { padding-top: 1.2rem; padding-bottom: 2rem; max-width: 1500px; }

/* ── App hero header ─────────────────────────────────────────── */
.wops-header {
    background: linear-gradient(120deg, #0F2440 0%, #1565C0 55%, #1B7BD6 100%);
    border-radius: 14px;
    padding: 18px 26px;
    margin-bottom: 18px;
    box-shadow: 0 6px 22px rgba(0,0,0,0.35);
    display: flex; align-items: center; gap: 16px;
}
.wops-header-icon { font-size: 38px; line-height: 1; }
.wops-header-text h1 {
    color: #FFFFFF; font-size: 24px; font-weight: 800;
    margin: 0; letter-spacing: 0.3px;
}
.wops-header-text p {
    color: #CFE2F7; font-size: 13px; margin: 2px 0 0; font-weight: 500;
}

/* ── KPI cards ───────────────────────────────────────────────── */
.wops-kpi {
    background: linear-gradient(180deg, #14233A 0%, #0F1B2E 100%);
    border-radius: 12px;
    padding: 16px 14px 14px;
    text-align: center;
    height: 100%;
    box-shadow: 0 2px 10px rgba(0,0,0,0.30);
    transition: transform 0.15s ease, box-shadow 0.15s ease;
    position: relative;
    overflow: hidden;
}
.wops-kpi:hover {
    transform: translateY(-3px);
    box-shadow: 0 8px 22px rgba(0,0,0,0.45);
}
.wops-kpi-icon {
    font-size: 18px; opacity: 0.85; margin-bottom: 2px; line-height: 1;
}
.wops-kpi-title {
    color: #8AAAC8; font-size: 11px; margin: 0; font-weight: 600;
    letter-spacing: 0.6px; text-transform: uppercase;
}
.wops-kpi-value {
    font-size: 27px; font-weight: 800; margin: 5px 0 3px; line-height: 1.1;
}
.wops-kpi-sub { color: #5B7790; font-size: 10.5px; margin: 0; }

/* ── Selector bar ────────────────────────────────────────────── */
.selector-bar {
    background: linear-gradient(90deg, #1565C0 0%, #1B7BD6 100%);
    padding: 10px 20px; border-radius: 10px; color: white;
    font-size: 14px; font-weight: 600; margin-bottom: 6px;
    box-shadow: 0 3px 12px rgba(21,101,192,0.30);
}

/* ── Zone / quick-filter chips ───────────────────────────────── */
.wops-chips { display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 12px; }

/* ── Error severity ──────────────────────────────────────────── */
.error-high   { color: #E74C3C; font-weight: 700; }
.error-medium { color: #E67E22; font-weight: 700; }
.error-low    { color: #F1C40F; font-weight: 700; }

/* ── Tabs ────────────────────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] { gap: 4px; }
.stTabs [data-baseweb="tab"] {
    font-size: 14px; font-weight: 600; padding: 9px 18px;
    border-radius: 9px 9px 0 0; color: #8AAAC8;
}
.stTabs [aria-selected="true"] {
    background: #14233A; color: #FFFFFF;
}

/* ── Sidebar ─────────────────────────────────────────────────── */
section[data-testid="stSidebar"] {
    background: #0B1626; border-right: 1px solid #1E3A5F;
}
section[data-testid="stSidebar"] .stFileUploader label { font-weight: 600; }

/* ── Dataframes & buttons ────────────────────────────────────── */
[data-testid="stDataFrame"] { border-radius: 10px; overflow: hidden; }
.stDownloadButton button, .stButton button {
    border-radius: 8px; font-weight: 600; border: 1px solid #1E3A5F;
    transition: all 0.15s ease;
}
.stDownloadButton button:hover, .stButton button:hover {
    border-color: #1565C0; box-shadow: 0 0 0 2px rgba(21,101,192,0.25);
}

/* ── Custom scrollbar ────────────────────────────────────────── */
::-webkit-scrollbar { width: 9px; height: 9px; }
::-webkit-scrollbar-track { background: #0D1B2A; }
::-webkit-scrollbar-thumb { background: #1E3A5F; border-radius: 5px; }
::-webkit-scrollbar-thumb:hover { background: #2C5179; }
</style>
"""

LIGHT_MODE_CSS = """
<style>
/* ── LIGHT MODE OVERRIDE ─────────────────────────────────────── */
.stApp, [data-testid="stAppViewContainer"],
[data-testid="stMain"], .main { background-color: #EEF3F9 !important; }
.block-container { background-color: #EEF3F9 !important; }
[data-testid="stVerticalBlock"] { background-color: transparent; }

.wops-kpi {
    background: linear-gradient(180deg, #FFFFFF 0%, #F4F9FF 100%) !important;
    box-shadow: 0 2px 8px rgba(21,101,192,0.12) !important;
}
.wops-kpi:hover { box-shadow: 0 8px 20px rgba(21,101,192,0.22) !important; }
.wops-kpi-title { color: #5B7A9E !important; }
.wops-kpi-sub   { color: #7A9AB8 !important; }

section[data-testid="stSidebar"] {
    background: #E4EBF5 !important;
    border-right: 1px solid #B8CDE0 !important;
}
.stTabs [data-baseweb="tab"] { color: #5B7A9E !important; }
.stTabs [aria-selected="true"] {
    background: #D8E6F5 !important; color: #1244A2 !important;
}
::-webkit-scrollbar-track { background: #EEF3F9 !important; }
::-webkit-scrollbar-thumb { background: #9DBAD4 !important; }
.stDownloadButton button, .stButton button { border-color: #9DBAD4 !important; }
</style>
"""


def app_header(subtitle: str = "Warehouse Operations Performance System") -> str:
    """Hero banner shown at the top of the main content area."""
    return f"""
<div class="wops-header">
  <div class="wops-header-icon">📦</div>
  <div class="wops-header-text">
    <h1>WOPS Intelligence Dashboard</h1>
    <p>{subtitle}</p>
  </div>
</div>"""


def kpi_card(title: str, value: str, subtitle: str = "",
             border_color: str = "#1565C0", value_color: str = "#FFFFFF",
             icon: str = "") -> str:
    icon_html = f'<div class="wops-kpi-icon">{icon}</div>' if icon else ""
    return f"""
<div class="wops-kpi" style="border-top:3px solid {border_color}">
  {icon_html}
  <p class="wops-kpi-title">{title}</p>
  <p class="wops-kpi-value" style="color:{value_color}">{value}</p>
  <p class="wops-kpi-sub">{subtitle}</p>
</div>"""


def selector_bar(plant: str, zone: str) -> str:
    return f"""
<div class="selector-bar">
  📍 Plant: <span style="font-weight:400">{plant}</span>
  &nbsp;&nbsp;|&nbsp;&nbsp;
  🗺️ Zone: <span style="font-weight:400">{zone}</span>
</div>"""


def fmt_indian(n: float) -> str:
    """Format number in Indian comma notation."""
    try:
        if n is None or n != n:  # None / NaN (NaN is the only value != itself)
            return "0"
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
    try:
        if rate is None or rate != rate:  # NaN guard
            return colors[2]
        if rate < thresholds[0]:
            return colors[0]
        if rate < thresholds[1]:
            return colors[1]
    except TypeError:
        pass
    return colors[2]


def accuracy_color(acc: float) -> str:
    try:
        if acc is None or acc != acc:
            return "#C0392B"
        if acc >= 97:
            return "#27AE60"
        if acc >= 90:
            return "#E67E22"
    except TypeError:
        pass
    return "#C0392B"


def fill_rate_color(rate: float) -> str:
    """Green ≥95%, orange 85-95%, red <85%."""
    try:
        if rate is None or rate != rate:
            return "#C0392B"
        if rate >= 95:
            return "#27AE60"
        if rate >= 85:
            return "#E67E22"
    except TypeError:
        pass
    return "#C0392B"
