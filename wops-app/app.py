import streamlit as st
import pandas as pd

st.set_page_config(layout="wide", page_title="WOPS Intelligence Dashboard", page_icon="📦")

from src.styles import (
    GLOBAL_CSS, LIGHT_MODE_CSS, app_header, kpi_card, selector_bar,
    fmt_currency, fmt_indian, rate_color, accuracy_color, fill_rate_color,
)
from src.data_loader import load_zsd, get_transaction_types
from src.transformer import build_all_dataframes
from src.filters import apply_filter, build_master_wh_numeric_maps
from src.kpis import (
    compute_primary_kpis, compute_receiving_kpi, compute_inventory_kpis,
    compute_rs_per_case, compute_cases_per_manhour_unload, compute_otif_kpis,
    compute_expiry_kpis, compute_returns_by_category,
    compute_channel_split, compute_inventory_health_table,
    compute_data_freshness, compute_rlm_table,
)
from src.charts import returns_bar_chart, channel_pie_chart, transport_state_bar, transport_material_bar
from src.error_detection import compute_error_log, get_missing_batch_detail, get_duplicate_invoices
from src import analytics, panels

if "dark_mode" not in st.session_state:
    st.session_state["dark_mode"] = True

st.markdown(GLOBAL_CSS, unsafe_allow_html=True)
if not st.session_state["dark_mode"]:
    st.markdown(LIGHT_MODE_CSS, unsafe_allow_html=True)
st.markdown(app_header(), unsafe_allow_html=True)


# ── SIDEBAR ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 📦 WOPS Intelligence")
    _theme_icon = "☀️ Light Mode" if st.session_state["dark_mode"] else "🌙 Dark Mode"
    if st.button(_theme_icon, key="theme_toggle", use_container_width=True):
        st.session_state["dark_mode"] = not st.session_state["dark_mode"]
        st.rerun()
    st.markdown("---")

    st.markdown("##### 📂 Required data")
    zsd_file       = st.file_uploader("FILE 1 — zsd_salefl.xlsx",  type=["xlsx"], key="zsd")
    nysd_file      = st.file_uploader("FILE 2 — nysd_css.xlsx",    type=["xlsx"], key="nysd")

    with st.expander("➕ Optional data sources (3–5)", expanded=False):
        st.caption("Unlock extra KPIs — transport analytics, zone/labour mapping, and service-level metrics.")
        transport_file = st.file_uploader("FILE 3 — Transport.xlsx\nTransport & vendor analytics", type=["xlsx"], key="tp")
        master_file    = st.file_uploader("FILE 4 — Master_WH.xlsx\nZone mapping + Rent/Labour KPIs", type=["xlsx"], key="mwh")
        ost_file       = st.file_uploader("FILE 5 — OST_Report.xlsx\nOTIF % and Order Service Time %", type=["xlsx"], key="ost")

    # Live status summary of what's loaded
    _loaded = [n for n, f in [
        ("Sales", zsd_file), ("Stock", nysd_file), ("Transport", transport_file),
        ("Master_WH", master_file), ("OST", ost_file),
    ] if f]
    if _loaded:
        st.success("✅ Loaded: " + ", ".join(_loaded))

    st.markdown("---")

    if not (zsd_file and nysd_file):
        st.info("⬆️ Upload **FILE 1** and **FILE 2** to begin.")
        st.stop()

    # Read ALL file bytes exactly once — UploadedFile pointer exhausts after first .read()
    zsd_bytes  = zsd_file.read()
    nysd_bytes = nysd_file.read()
    tp_bytes   = transport_file.read() if transport_file else None
    mwh_bytes  = master_file.read()    if master_file    else None
    ost_bytes  = ost_file.read()       if ost_file       else None

    raw_zsd, load_err = load_zsd(zsd_bytes)
    if load_err:
        st.error(f"Could not read FILE 1: {load_err}")
        st.stop()

    all_types = get_transaction_types(raw_zsd)

    # Seed session-state defaults only when file changes — never pass default= with key=
    _file_hash = hash(zsd_bytes)
    if st.session_state.get("_zsd_hash") != _file_hash:
        st.session_state["_zsd_hash"]  = _file_hash
        st.session_state["inv_types"]  = [t for t in all_types if any(
            k in t.upper() for k in ["INVOICE", "BILLING", "F2", "ZF2", "F8"])]
        st.session_state["cred_types"] = [t for t in all_types if
            "CREDIT" in t.upper() or t.upper() in ("RE", "REN", "RE2")]
        st.session_state["ch_types"]   = [t for t in all_types if
            "CHALLAN" in t.upper() or "DELIVERY" in t.upper()]

    with st.expander("⚙ Column Mapping", expanded=True):
        if not all_types:
            st.warning("⚠ No transaction types detected. Check sheet/column names.")
        else:
            st.caption(f"{len(all_types)} transaction type(s) found in FILE 1")

        invoice_types = st.multiselect("Invoice / Billing types", all_types, key="inv_types")
        credit_types  = st.multiselect("Credit Note types",       all_types, key="cred_types")
        challan_types = st.multiselect("Delivery Challan types",  all_types, key="ch_types")

    st.markdown("---")
    # Seed Zone from the URL (?zone=North) so a view can be bookmarked / shared.
    _zone_opts = ["All Zones", "North", "South", "East", "West"]
    _qp_zone = st.query_params.get("zone")
    if _qp_zone in _zone_opts and "zone_box" not in st.session_state:
        st.session_state["zone_box"] = _qp_zone
    zone_sel = st.selectbox("Zone", _zone_opts, key="zone_box")

    st.markdown("---")
    st.markdown("**Parameters**")
    fixed_manpower = st.number_input(
        "Fixed Manpower (fallback)",
        min_value=1, value=50, step=1,
        help="Used when Master_WH does not contain a Labour/Manpower column",
    )


# ── LOAD & TRANSFORM ─────────────────────────────────────────────────────────
if not invoice_types:
    st.warning("No Invoice types selected. Open **⚙ Column Mapping** in the sidebar.")
    st.stop()

with st.spinner("Processing data..."):
    dfs = build_all_dataframes(
        zsd_bytes, nysd_bytes, tp_bytes,
        tuple(invoice_types), tuple(credit_types), tuple(challan_types),
        mwh_bytes, ost_bytes,
    )

orders       = dfs["customer_orders"]
despatch     = dfs["order_despatch"]
returns      = dfs["returns"]
receiving    = dfs["receiving"]
inventory    = dfs["inventory"]
inv_accuracy = dfs["inventory_accuracy"]
transport    = dfs["transport"]
ost          = dfs["ost"]

# Build plant display map and master numeric maps
from src.filters import build_zone_map_from_master, PLANT_NAME_MAP, _norm_plant_key
from src.data_loader import load_master_wh

plant_name_map: dict = dict(PLANT_NAME_MAP)
master_maps: dict = {}

if mwh_bytes:
    mwh_df, _ = load_master_wh(mwh_bytes)
    _, override = build_zone_map_from_master(mwh_df)
    plant_name_map.update(override)
    master_maps = build_master_wh_numeric_maps(mwh_df)


def plant_display(code: str) -> str:
    key  = str(code).strip().replace(".0", "")
    name = plant_name_map.get(key, "")
    return f"{name} ({key})" if name else key


all_plant_codes = []
if orders is not None and "Plant" in orders.columns:
    all_plant_codes = sorted(
        {_norm_plant_key(p) for p in orders["Plant"].dropna() if _norm_plant_key(p)},
        key=lambda x: int(x) if x.isdigit() else x,
    )

plant_display_options = ["All Plants"] + [plant_display(p) for p in all_plant_codes]
plant_code_options    = ["All Plants"] + all_plant_codes

# Seed Plant from the URL (?plant=5524) before the widget is instantiated.
_qp_plant = st.query_params.get("plant")
if (_qp_plant and _qp_plant in plant_code_options
        and "plant_sel_real" not in st.session_state):
    st.session_state["plant_sel_real"] = plant_display_options[
        plant_code_options.index(_qp_plant)
    ]

plant_sel_disp = st.sidebar.selectbox("Plant", plant_display_options, key="plant_sel_real")
plant_sel = (
    "All Plants"
    if plant_sel_disp == "All Plants"
    else plant_code_options[plant_display_options.index(plant_sel_disp)]
)

# Persist the current Zone/Plant selection to the URL for bookmarking/sharing.
st.query_params["zone"] = zone_sel
st.query_params["plant"] = plant_sel

# ── DATE RANGE + ALERT THRESHOLDS ────────────────────────────────────────────
_dmin, _dmax = analytics.date_bounds([
    (orders, "Order_Date"), (despatch, "Despatch_Date"), (returns, "Return_Date"),
])
date_range = None
if _dmin is not None and _dmax is not None and _dmin < _dmax:
    _picked = st.sidebar.date_input(
        "📅 Date range", value=(_dmin, _dmax),
        min_value=_dmin, max_value=_dmax, key="date_range",
    )
    if isinstance(_picked, (tuple, list)) and len(_picked) == 2 and all(_picked):
        date_range = (_picked[0], _picked[1])

st.sidebar.markdown("---")
st.sidebar.markdown("**🔔 Alert thresholds**")
rr_warn = st.sidebar.number_input(
    "Return-rate warning %", min_value=0.0, max_value=100.0, value=2.0, step=0.5,
    key="rr_warn",
)
rr_crit = st.sidebar.number_input(
    "Return-rate critical %", min_value=0.0, max_value=100.0, value=5.0, step=0.5,
    key="rr_crit",
)
near_exp_days = int(st.sidebar.number_input(
    "Near-expiry window (days)", min_value=1, max_value=365, value=30, step=1,
    key="near_exp_days",
))


# ── FILTERING ─────────────────────────────────────────────────────────────────
def flt(df):
    return apply_filter(df, zone_sel, plant_sel) if df is not None else None

f_orders    = flt(orders)
f_despatch  = flt(despatch)
f_returns   = flt(returns)
f_receiving = flt(receiving)
f_inventory = flt(inventory)
f_inv_acc   = flt(inv_accuracy)
f_transport = flt(transport)
f_ost       = flt(ost)

# Date-range filter on the transactional frames (inventory is a point-in-time
# snapshot, so it is intentionally excluded).
if date_range is not None:
    _ds, _de = date_range
    f_orders    = analytics.filter_by_date(f_orders,    "Order_Date",    _ds, _de)
    f_despatch  = analytics.filter_by_date(f_despatch,  "Despatch_Date", _ds, _de)
    f_returns   = analytics.filter_by_date(f_returns,   "Return_Date",   _ds, _de)
    f_receiving = analytics.filter_by_date(f_receiving, "Receipt_Date",  _ds, _de)


# ── ZONE CHIP HELPER ─────────────────────────────────────────────────────────
def _zone_chips(prefix: str, state_key: str = "zone_box",
                zones=("All Zones", "North", "South", "East", "West")):
    """Row of chip buttons for quick zone selection."""
    current = st.session_state.get(state_key, zones[0])
    cols = st.columns(len(zones))
    for col, z in zip(cols, zones):
        with col:
            if st.button(
                z, key=f"zchip_{prefix}_{z}",
                type="primary" if current == z else "secondary",
                use_container_width=True,
            ):
                st.session_state[state_key] = z
                st.rerun()


# ── TABS ──────────────────────────────────────────────────────────────────────
tab1, tab2, tab_tr, tab_cu, tab3, tab4, tab5 = st.tabs([
    "📊 Dashboard", "🏭 RLM Zone View", "📈 Trends", "👥 Customers & Products",
    "⚠ Error Log", "🚚 Transport", "📋 Raw Data",
])


# ════════════════════════════════════════════════════════
# TAB 1 — DASHBOARD
# ════════════════════════════════════════════════════════
with tab1:
    st.markdown(selector_bar(plant_sel_disp, zone_sel), unsafe_allow_html=True)
    _zone_chips("d")

    # Data freshness indicator (pd.notna guards against NaT, which is truthy)
    freshness = compute_data_freshness(f_orders, f_despatch)
    parts = []
    if pd.notna(freshness["max_order_date"]):
        parts.append(f"Latest order: **{freshness['max_order_date'].strftime('%d %b %Y')}**")
    if pd.notna(freshness["max_despatch_date"]):
        parts.append(f"Latest despatch: **{freshness['max_despatch_date'].strftime('%d %b %Y')}**")
    if parts:
        st.caption("📅 " + "  |  ".join(parts))

    # ── ALERTS — threshold-driven exceptions ─────────────
    panels.render_alerts(
        f_despatch, f_returns, f_inventory,
        rr_warn, rr_crit, near_exp_days, plant_display,
    )

    # ── PRIMARY KPIs — row 1: volume ─────────────────────
    primary        = compute_primary_kpis(f_orders, f_despatch, f_returns)
    cases_received = compute_receiving_kpi(f_receiving)
    rr             = primary["return_rate"]
    fr             = primary["fill_rate"]

    st.markdown("##### 📦 Volume & Flow")
    r1 = st.columns(4)
    for col, (title, val, sub, border, vc, icon) in zip(r1, [
        ("CASES ORDERED",    fmt_indian(primary["total_ordered"]),    "from customer orders",   "#1565C0", "#FFFFFF", "🛒"),
        ("CASES DISPATCHED", fmt_indian(primary["cases_dispatched"]), "shipped to customers",   "#27AE60", "#FFFFFF", "🚚"),
        ("FILL RATE %",      f"{fr:.1f}%",                           "dispatched ÷ ordered",   "#27AE60", fill_rate_color(fr), "🎯"),
        ("CASES RECEIVED",   fmt_indian(cases_received),             "inbound to warehouse",   "#2980B9", "#FFFFFF", "📥"),
    ]):
        with col:
            st.markdown(kpi_card(title, val, sub, border, vc, icon), unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── PRIMARY KPIs — row 2: quality / service ───────────
    avg_sz = primary["avg_order_size"]
    st.markdown("##### ↩️ Quality & Orders")
    r2 = st.columns(4)
    for col, (title, val, sub, border, vc, icon) in zip(r2, [
        ("RETURN RATE %",      f"{rr:.1f}%",                           "returns ÷ dispatched",   "#C0392B", rate_color(rr), "📉"),
        ("TOTAL RETURNS",      fmt_indian(primary["total_returns"]),   "returned from customers","#C0392B", "#FFFFFF", "↩️"),
        ("COUNT OF ORDERS",    fmt_indian(primary["count_orders"]),    "unique invoices",         "#1565C0", "#FFFFFF", "🧾"),
        ("AVG ORDER SIZE",     f"{avg_sz:.1f}",                        "cases per order",         "#1565C0", "#FFFFFF", "📐"),
    ]):
        with col:
            st.markdown(kpi_card(title, val, sub, border, vc, icon), unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── INVENTORY KPIs ───────────────────────────────────
    inv_kpis = compute_inventory_kpis(f_inventory, f_despatch, fixed_manpower, f_orders)
    sc_disp  = "No dispatch" if inv_kpis["stock_cover_na"] else f"{inv_kpis['stock_cover']:.1f}"
    sc_sub   = "no despatch data" if inv_kpis["stock_cover_na"] else "days of forward cover"

    unload_mph = compute_cases_per_manhour_unload(
        f_receiving, master_maps.get("unload_labour", {}), zone_sel, plant_sel, fixed_manpower
    )
    otif_kpis  = compute_otif_kpis(f_ost)

    rs_case   = compute_rs_per_case(f_despatch, master_maps.get("rent", {}), zone_sel, plant_sel)
    rs_disp   = fmt_currency(rs_case) if rs_case is not None else "—"
    rs_sub    = "rent ÷ cases dispatched" if rs_case is not None else "upload Master_WH with Rent column"

    # Row: warehouse ops metrics (5 cols)
    st.markdown("##### 💰 Inventory & Cost")
    inv_cols = st.columns(5)
    for col, (title, val, sub, border, vc, icon) in zip(inv_cols, [
        ("TOTAL INVENTORY VALUE",    fmt_currency(inv_kpis["total_value"]),   "month-end stock",               "#E67E22", "#FFFFFF", "💰"),
        ("STOCK COVER (DAYS)",       sc_disp,                                 sc_sub,                          "#E67E22", "#FFFFFF", "📆"),
        ("CASES LOADED / MANHOUR",   f"{inv_kpis['cases_per_manhour']:.1f}", f"based on {fixed_manpower} mp", "#E67E22", "#FFFFFF", "📤"),
        ("CASES UNLOADED / MANHOUR", f"{unload_mph:.1f}",                    "inbound ÷ unloading labour",    "#2980B9", "#FFFFFF", "📥"),
        ("Rs/CASE",                  rs_disp,                                 rs_sub,                          "#8E44AD", "#FFFFFF", "🏷️"),
    ]):
        with col:
            st.markdown(kpi_card(title, val, sub, border, vc, icon), unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Row: service level (OTIF + OST + manpower per order)
    st.markdown("##### ⏱️ Service Level")
    _otif_disp = f"{otif_kpis['otif_pct']:.1f}%" if otif_kpis["available"] else "—"
    _otif_sub  = f"{otif_kpis['otif_orders']:,} of {otif_kpis['total_orders']:,} orders" if otif_kpis["available"] else "upload OST_Report (FILE 5)"
    _ost_disp  = f"{otif_kpis['ost_pct']:.1f}%"  if otif_kpis["available"] else "—"
    _ost_sub   = "order→dispatch < 24h" if otif_kpis["available"] else "upload OST_Report (FILE 5)"
    svc_cols = st.columns(3)
    for col, (title, val, sub, border, vc, icon) in zip(svc_cols, [
        ("OTIF %",              _otif_disp,                               _otif_sub,                   "#27AE60", "#27AE60" if otif_kpis["available"] else "#FFFFFF", "✅"),
        ("ORDER SERVICE TIME %",_ost_disp,                                _ost_sub,                    "#1565C0", "#1565C0" if otif_kpis["available"] else "#FFFFFF", "⏱️"),
        ("MANPOWER PER ORDER",  f"{inv_kpis['manpower_per_order']:.2f}", "fixed manpower ÷ orders",   "#E67E22", "#FFFFFF", "👷"),
    ]):
        with col:
            st.markdown(kpi_card(title, val, sub, border, vc, icon), unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── INVENTORY HEALTH ────────────────────────────────
    st.markdown("##### ⏳ Expiry Risk")
    exp_kpis = compute_expiry_kpis(f_inventory)
    health_cols = st.columns(4)
    for col, (title, val, sub, border, vc, icon) in zip(health_cols, [
        ("EXPIRED STOCK VALUE",   fmt_currency(exp_kpis["expired_value"]), "immediate write-off risk",      "#C0392B", "#C0392B", "🔴"),
        ("NEAR EXPIRY 0-30 DAYS", fmt_indian(exp_kpis["near_30_cases"]),  "cases expiring within 30 days", "#E67E22", "#E67E22", "🟠"),
        ("31-45 DAYS TO EXPIRY",  fmt_indian(exp_kpis["near_45_cases"]),  "cases expiring in 31-45 days",  "#F39C12", "#F39C12", "🟡"),
        ("46-60 DAYS TO EXPIRY",  fmt_indian(exp_kpis["near_60_cases"]),  "cases expiring in 46-60 days",  "#F1C40F", "#F1C40F", "🟢"),
    ]):
        with col:
            st.markdown(kpi_card(title, val, sub, border, vc, icon), unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── BOTTOM ANALYSIS ─────────────────────────────────
    col_left, col_mid, col_right = st.columns([2.5, 4, 3.5])

    returns_cat = compute_returns_by_category(f_returns)
    channel_df  = compute_channel_split(f_orders)
    inv_health  = compute_inventory_health_table(f_inventory)

    with col_left:
        st.markdown("##### Returns Analysis")
        if not returns_cat.empty and returns_cat["Cases"].sum() > 0:
            def style_returns(row):
                pct = row.get("Pct_Returns", 0)
                if pct > 30:
                    return ["color: #E74C3C"] * len(row)
                if pct > 15:
                    return ["color: #E67E22"] * len(row)
                return [""] * len(row)
            st.dataframe(
                returns_cat.style.apply(style_returns, axis=1),
                use_container_width=True, height=220, hide_index=True,
            )
        else:
            st.info("No returns data for selection")

    with col_mid:
        st.plotly_chart(returns_bar_chart(returns_cat), use_container_width=True)
        st.markdown("##### Inventory Health")
        if not inv_health.empty and inv_health["Cases"].sum() > 0:
            inv_health_disp = inv_health.copy()
            inv_health_disp["Value_INR"] = inv_health_disp["Value_INR"].apply(fmt_currency)
            st.dataframe(inv_health_disp, use_container_width=True, height=185, hide_index=True)
        else:
            st.info("No inventory data for selection")

    with col_right:
        st.markdown("##### Channel Split")
        if not channel_df.empty and channel_df["Cases_Ordered"].sum() > 0:
            st.dataframe(channel_df, use_container_width=True, height=185, hide_index=True)
        else:
            st.info("No channel data for selection")
        st.plotly_chart(channel_pie_chart(channel_df), use_container_width=True)

    st.markdown("<br>", unsafe_allow_html=True)
    panels.render_sku_drilldown(f_orders, f_returns)


# ════════════════════════════════════════════════════════
# TAB 2 — RLM ZONE VIEW
# ════════════════════════════════════════════════════════
with tab2:
    st.subheader("🏭 RLM Zone Comparison")
    st.caption("Side-by-side warehouse KPIs within a zone — mirrors the Excel RLM Dashboard. '—' = no data / zero denominator.")

    _zone_chips("rlm", state_key="rlm_zone_sel",
                zones=("North", "South", "East", "West", "All Zones"))
    rlm_zone = st.session_state.get("rlm_zone_sel", "North")
    if rlm_zone not in ("North", "South", "East", "West", "All Zones"):
        rlm_zone = "North"

    rlm_df = compute_rlm_table(
        orders, despatch, returns, receiving, inventory,
        zone_sel=rlm_zone,
        fixed_manpower=fixed_manpower,
        master_maps=master_maps,
        ost=ost,
    )

    if rlm_df.empty:
        st.info("No data available for the selected zone.")
    else:
        rlm_df.insert(1, "Warehouse", rlm_df["Plant"].apply(plant_display))

        # ── Summary callouts ─────────────────────────────
        # Safe extremum helpers: return None when the column is empty / all-NaN
        # (idxmin/idxmax raise ValueError "Encountered all NA values" otherwise).
        def _safe_idx(col, how="max"):
            s = rlm_df[col].dropna()
            if s.empty:
                return None
            return s.idxmax() if how == "max" else s.idxmin()

        best_idx = _safe_idx("Cases_Dispatched", "max")
        worst_fr = _safe_idx("Fill_Rate_%", "min")
        worst_rr = _safe_idx("Return_Rate_%", "max")

        c1, c2, c3 = st.columns(3)
        with c1:
            if best_idx is not None and rlm_df.loc[best_idx, "Cases_Dispatched"] > 0:
                st.markdown(kpi_card(
                    "TOP DISPATCHER",
                    fmt_indian(rlm_df.loc[best_idx, "Cases_Dispatched"]),
                    rlm_df.loc[best_idx, "Warehouse"],
                    "#27AE60", "#27AE60", "🏆"
                ), unsafe_allow_html=True)
            else:
                st.markdown(kpi_card("TOP DISPATCHER", "—", "no despatch data",
                                     "#27AE60", "#FFFFFF", "🏆"), unsafe_allow_html=True)
        with c2:
            if worst_fr is not None:
                low_fr = rlm_df.loc[worst_fr, "Fill_Rate_%"]
                st.markdown(kpi_card(
                    "LOWEST FILL RATE", f"{low_fr:.1f}%",
                    rlm_df.loc[worst_fr, "Warehouse"],
                    "#E67E22", fill_rate_color(low_fr), "📉"
                ), unsafe_allow_html=True)
            else:
                st.markdown(kpi_card("LOWEST FILL RATE", "—", "no order data",
                                     "#E67E22", "#FFFFFF", "📉"), unsafe_allow_html=True)
        with c3:
            if worst_rr is not None:
                high_rr = rlm_df.loc[worst_rr, "Return_Rate_%"]
                st.markdown(kpi_card(
                    "HIGHEST RETURN RATE", f"{high_rr:.1f}%",
                    rlm_df.loc[worst_rr, "Warehouse"],
                    "#C0392B", rate_color(high_rr), "↩️"
                ), unsafe_allow_html=True)
            else:
                st.markdown(kpi_card("HIGHEST RETURN RATE", "—", "no despatch data",
                                     "#C0392B", "#FFFFFF", "↩️"), unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("#### Warehouse KPI Summary")

        display_cols = [
            "Plant", "Warehouse", "Cases_Ordered", "Cases_Dispatched",
            "Fill_Rate_%", "Cases_Received", "Returned_Cases", "Return_Rate_%",
            "Inv_Value_INR", "Stock_Cover_Days", "Rs_Per_Case",
            "Dock_Util_%", "Rent_Per_Sqft", "Cases_Per_MH", "Cases_Per_MH_Unload",
            "OTIF_%", "OST_%", "Avg_Order_Size", "Dispatch_Rank",
        ]
        display_cols = [c for c in display_cols if c in rlm_df.columns]
        disp_num = rlm_df[display_cols].copy()

        # Formatters operate on display only; Styler.apply still sees raw numerics,
        # so colour logic never parses strings (robust against NaN → "—").
        def _pct(v):
            return "—" if not pd.notna(v) else f"{v:.1f}%"
        def _rs(v):
            return "—" if not pd.notna(v) else f"₹{v:,.2f}"
        def _f1(v):
            return "—" if not pd.notna(v) else f"{v:.1f}"
        def _rank(v):
            return "—" if not pd.notna(v) else f"{int(v)}"
        fmt_map = {
            "Cases_Ordered":      fmt_indian,
            "Cases_Dispatched":   fmt_indian,
            "Cases_Received":     fmt_indian,
            "Returned_Cases":     fmt_indian,
            "Inv_Value_INR":      fmt_currency,
            "Fill_Rate_%":        _pct,
            "Return_Rate_%":      _pct,
            "Dock_Util_%":        _pct,
            "OTIF_%":             _pct,
            "OST_%":              _pct,
            "Rs_Per_Case":        _rs,
            "Rent_Per_Sqft":      _rs,
            "Stock_Cover_Days":   _f1,
            "Cases_Per_MH":       _f1,
            "Cases_Per_MH_Unload": _f1,
            "Avg_Order_Size":     _f1,
            "Dispatch_Rank":      _rank,
        }
        fmt_map = {k: v for k, v in fmt_map.items() if k in disp_num.columns}

        _disp_max = float(disp_num["Cases_Dispatched"].max()) if "Cases_Dispatched" in disp_num.columns else 0.0

        def _color_col(col):
            name = col.name
            if name == "Fill_Rate_%":
                return [f"color: {fill_rate_color(v)}" if pd.notna(v) else "" for v in col]
            if name == "Return_Rate_%":
                return [f"color: {rate_color(v)}" if pd.notna(v) else "" for v in col]
            if name in ("OTIF_%", "OST_%"):
                return [f"color: {fill_rate_color(v)}" if pd.notna(v) else "" for v in col]
            if name == "Dispatch_Rank":
                return ["color: #27AE60; font-weight: 700"
                        if (pd.notna(v) and v == 1) else "" for v in col]
            if name == "Cases_Dispatched" and _disp_max > 0:
                # Manual green heatmap (no matplotlib dependency)
                out = []
                for v in col:
                    if pd.notna(v) and v > 0:
                        alpha = 0.12 + 0.45 * (float(v) / _disp_max)
                        out.append(f"background-color: rgba(39, 174, 96, {alpha:.2f})")
                    else:
                        out.append("")
                return out
            return [""] * len(col)

        styler = disp_num.style.format(fmt_map, na_rep="—").apply(_color_col, axis=0)
        st.dataframe(styler, use_container_width=True, hide_index=True)

        # ── Dispatch bar chart ────────────────────────────
        try:
            import plotly.express as px
            chart_df = rlm_df[rlm_df["Cases_Dispatched"] > 0].copy()
            if not chart_df.empty:
                fig = px.bar(
                    chart_df.sort_values("Cases_Dispatched", ascending=True),
                    x="Cases_Dispatched", y="Warehouse", orientation="h",
                    title=f"Cases Dispatched — {rlm_zone}",
                    color="Cases_Dispatched",
                    color_continuous_scale=["#1a3a5c", "#1565C0", "#27AE60"],
                    labels={"Cases_Dispatched": "Cases", "Warehouse": ""},
                )
                fig.update_layout(
                    paper_bgcolor="#0D1117", plot_bgcolor="#0D1117",
                    font_color="#FFFFFF", showlegend=False,
                    coloraxis_showscale=False,
                    height=max(300, len(chart_df) * 35),
                )
                st.plotly_chart(fig, use_container_width=True)
        except Exception:
            pass

        st.download_button(
            label="⬇ Download RLM Table CSV",
            data=rlm_df.to_csv(index=False).encode("utf-8"),
            file_name=f"rlm_{rlm_zone.lower().replace(' ', '_')}.csv",
            mime="text/csv",
            key="dl_rlm",
        )


# ════════════════════════════════════════════════════════
# TAB 3 — ERROR LOG
# ════════════════════════════════════════════════════════
with tab3:
    st.subheader("⚠ Automated Quality Checks")
    error_df = compute_error_log(
        f_orders, f_despatch, f_returns, f_receiving, f_inventory, f_inv_acc
    )

    # Severity filter chips
    if "err_sev" not in st.session_state:
        st.session_state["err_sev"] = "All"
    _sev_opts = ["All", "HIGH", "MEDIUM", "LOW"]
    _sev_cols = st.columns(len(_sev_opts))
    for _sc, _sv in zip(_sev_cols, _sev_opts):
        with _sc:
            if st.button(
                _sv, key=f"sev_{_sv}",
                type="primary" if st.session_state["err_sev"] == _sv else "secondary",
                use_container_width=True,
            ):
                st.session_state["err_sev"] = _sv
                st.rerun()

    _sev_filter = st.session_state["err_sev"]
    _err_display = (
        error_df if _sev_filter == "All"
        else error_df[error_df["Severity"] == _sev_filter]
        if "Severity" in error_df.columns else error_df
    )

    def _sev_style(val):
        if val == "HIGH":
            return "color: #E74C3C; font-weight: 700"
        if val == "MEDIUM":
            return "color: #E67E22; font-weight: 700"
        return "color: #F1C40F; font-weight: 700"

    st.dataframe(
        _err_display.style.map(_sev_style, subset=["Severity"])
        if "Severity" in _err_display.columns else _err_display,
        use_container_width=True, hide_index=True,
    )

    st.markdown("---")
    st.markdown("#### Detailed Error Records")

    with st.expander("Missing Batch — Dispatch Records"):
        detail = get_missing_batch_detail(f_despatch)
        if detail is not None and not detail.empty:
            st.dataframe(detail, use_container_width=True, height=300, hide_index=True)
        else:
            st.success("No missing batch records")

    with st.expander("Duplicate Invoice Numbers"):
        detail = get_duplicate_invoices(f_orders)
        if detail is not None and not detail.empty:
            st.dataframe(detail, use_container_width=True, height=300, hide_index=True)
        else:
            st.success("No duplicate invoices found")

    with st.expander("Inventory Accuracy by Plant"):
        if f_inv_acc is not None and not f_inv_acc.empty:
            def _acc_style(val):
                if isinstance(val, (int, float)):
                    return f"color: {accuracy_color(val)}"
                return ""
            st.dataframe(
                f_inv_acc.style.map(_acc_style, subset=["Accuracy_%"]),
                use_container_width=True, height=300, hide_index=True,
            )
        else:
            st.info("No inventory accuracy data")


# ════════════════════════════════════════════════════════
# TAB 4 — TRANSPORT
# ════════════════════════════════════════════════════════
with tab4:
    if transport is None or transport.empty:
        st.info("Upload FILE 3 (Transport.xlsx) to view transport analytics.")
    else:
        st.subheader("🚚 Transport Analysis")
        tp = f_transport if (f_transport is not None and not f_transport.empty) else transport

        tp_shipments = len(tp)
        tp_cases     = int(tp["Billing_Qty"].sum())  if "Billing_Qty"  in tp.columns else 0
        tp_vendors   = tp["Source_Plant"].nunique()   if "Source_Plant" in tp.columns else 0
        tp_dests     = tp["Dest_City"].nunique()      if "Dest_City"    in tp.columns else 0

        for col, (title, val, sub, border, vc, icon) in zip(st.columns(4), [
            ("TOTAL SHIPMENTS",     fmt_indian(tp_shipments), "rows in transport file", "#1565C0", "#FFFFFF", "📦"),
            ("TOTAL CASES",         fmt_indian(tp_cases),     "Billing_Qty sum",        "#27AE60", "#FFFFFF", "📬"),
            ("UNIQUE SOURCES",      fmt_indian(tp_vendors),   "source plants",          "#E67E22", "#FFFFFF", "🏭"),
            ("UNIQUE DESTINATIONS", fmt_indian(tp_dests),     "destination cities",     "#8E44AD", "#FFFFFF", "📍"),
        ]):
            with col:
                st.markdown(kpi_card(title, val, sub, border, vc, icon), unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        c1, c2 = st.columns(2)
        with c1:
            st.plotly_chart(transport_state_bar(tp), use_container_width=True)
        with c2:
            st.plotly_chart(transport_material_bar(tp), use_container_width=True)

        if "Dest_State" in tp.columns and "Billing_Qty" in tp.columns:
            st.markdown("#### Cases by Destination State")
            state_grp = (
                tp.groupby("Dest_State")
                .agg(Cases=("Billing_Qty", "sum"), Shipments=("Billing_Qty", "count"))
                .reset_index()
                .sort_values("Cases", ascending=False)
            )
            st.dataframe(state_grp, use_container_width=True, height=300, hide_index=True)

        st.markdown("<br>", unsafe_allow_html=True)
        panels.render_vendors(tp)


# ════════════════════════════════════════════════════════
# TAB 5 — RAW DATA
# ════════════════════════════════════════════════════════
with tab5:
    st.subheader("📋 Raw Data Export")

    export_tables = [
        ("Customer Orders",     f_orders),
        ("Order Despatch",      f_despatch),
        ("Returns",             f_returns),
        ("Receiving",           f_receiving),
        ("Month-End Inventory", f_inventory),
        ("Inventory Accuracy",  f_inv_acc),
    ]

    # Combined multi-sheet Excel workbook for the current filter selection
    _have_data = any(d is not None and not d.empty for _, d in export_tables)
    if _have_data:
        import io as _io
        _buf = _io.BytesIO()
        try:
            with pd.ExcelWriter(_buf, engine="openpyxl") as _writer:
                for _name, _df in export_tables:
                    if _df is not None and not _df.empty:
                        # Excel sheet names cap at 31 chars and forbid some symbols
                        _sheet = _name[:31].replace("/", "-")
                        _df.to_excel(_writer, sheet_name=_sheet, index=False)
            st.download_button(
                label="⬇ Download ALL tables as one Excel workbook",
                data=_buf.getvalue(),
                file_name="wops_export.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="dl_workbook",
            )
        except Exception as _e:
            st.caption(f"Excel export unavailable ({_e}). Use per-table CSV below.")

    st.markdown("---")

    for _i, (name, df) in enumerate(export_tables):
        panels.searchable_table(name, df, key=f"raw{_i}")


# ════════════════════════════════════════════════════════
# TAB — TRENDS
# ════════════════════════════════════════════════════════
with tab_tr:
    st.markdown(selector_bar(plant_sel_disp, zone_sel), unsafe_allow_html=True)
    _zone_chips("tr")
    panels.render_trends(f_orders, f_despatch, f_returns)


# ════════════════════════════════════════════════════════
# TAB — CUSTOMERS & PRODUCTS
# ════════════════════════════════════════════════════════
with tab_cu:
    st.markdown(selector_bar(plant_sel_disp, zone_sel), unsafe_allow_html=True)
    _zone_chips("cu")
    panels.render_customers(f_orders, f_returns)
