import streamlit as st
import pandas as pd

st.set_page_config(layout="wide", page_title="WOPS Intelligence Dashboard", page_icon="📦")

from src.styles import (
    GLOBAL_CSS, kpi_card, selector_bar,
    fmt_currency, fmt_indian, rate_color, accuracy_color, fill_rate_color,
)
from src.data_loader import load_zsd, get_transaction_types
from src.transformer import build_all_dataframes
from src.filters import apply_filter, build_master_wh_numeric_maps
from src.kpis import (
    compute_primary_kpis, compute_receiving_kpi, compute_inventory_kpis,
    compute_rs_per_case, compute_expiry_kpis, compute_returns_by_category,
    compute_channel_split, compute_inventory_health_table,
    compute_data_freshness, compute_rlm_table,
)
from src.charts import returns_bar_chart, channel_pie_chart, transport_state_bar, transport_material_bar
from src.error_detection import compute_error_log, get_missing_batch_detail, get_duplicate_invoices

st.markdown(GLOBAL_CSS, unsafe_allow_html=True)


# ── SIDEBAR ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 📦 WOPS Intelligence")
    st.markdown("---")

    zsd_file       = st.file_uploader("FILE 1 — zsd_salefl.xlsx",           type=["xlsx"], key="zsd")
    nysd_file      = st.file_uploader("FILE 2 — nysd_css.xlsx",              type=["xlsx"], key="nysd")
    transport_file = st.file_uploader("FILE 3 — Transport.xlsx (optional)",  type=["xlsx"], key="tp")
    master_file    = st.file_uploader("FILE 4 — Master_WH.xlsx (optional)\nEnables Zone mapping + Rent/Labour KPIs", type=["xlsx"], key="mwh")

    st.markdown("---")

    if not (zsd_file and nysd_file):
        st.info("Upload files 1 & 2 to begin.")
        st.stop()

    # Read ALL file bytes exactly once — UploadedFile pointer exhausts after first .read()
    zsd_bytes  = zsd_file.read()
    nysd_bytes = nysd_file.read()
    tp_bytes   = transport_file.read() if transport_file else None
    mwh_bytes  = master_file.read()    if master_file    else None

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
    zone_sel = st.selectbox("Zone", ["All Zones", "North", "South", "East", "West"])

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
        mwh_bytes,
    )

orders       = dfs["customer_orders"]
despatch     = dfs["order_despatch"]
returns      = dfs["returns"]
receiving    = dfs["receiving"]
inventory    = dfs["inventory"]
inv_accuracy = dfs["inventory_accuracy"]
transport    = dfs["transport"]

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

plant_sel_disp = st.sidebar.selectbox("Plant", plant_display_options, key="plant_sel_real")
plant_sel = (
    "All Plants"
    if plant_sel_disp == "All Plants"
    else plant_code_options[plant_display_options.index(plant_sel_disp)]
)


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


# ── TABS ──────────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📊 Dashboard", "🏭 RLM Zone View", "⚠ Error Log", "🚚 Transport", "📋 Raw Data"
])


# ════════════════════════════════════════════════════════
# TAB 1 — DASHBOARD
# ════════════════════════════════════════════════════════
with tab1:
    st.markdown(selector_bar(plant_sel_disp, zone_sel), unsafe_allow_html=True)

    # Data freshness indicator
    freshness = compute_data_freshness(f_orders, f_despatch)
    parts = []
    if freshness["max_order_date"]:
        parts.append(f"Latest order: **{freshness['max_order_date'].strftime('%d %b %Y')}**")
    if freshness["max_despatch_date"]:
        parts.append(f"Latest despatch: **{freshness['max_despatch_date'].strftime('%d %b %Y')}**")
    if parts:
        st.caption("📅 " + "  |  ".join(parts))

    # ── PRIMARY KPIs — row 1: volume ─────────────────────
    primary        = compute_primary_kpis(f_orders, f_despatch, f_returns)
    cases_received = compute_receiving_kpi(f_receiving)
    rr             = primary["return_rate"]
    fr             = primary["fill_rate"]

    r1 = st.columns(4)
    for col, (title, val, sub, border, vc) in zip(r1, [
        ("CASES ORDERED",    fmt_indian(primary["total_ordered"]),    "from customer orders",   "#1565C0", "#FFFFFF"),
        ("CASES DISPATCHED", fmt_indian(primary["cases_dispatched"]), "shipped to customers",   "#27AE60", "#FFFFFF"),
        ("FILL RATE %",      f"{fr:.1f}%",                           "dispatched ÷ ordered",   "#27AE60", fill_rate_color(fr)),
        ("CASES RECEIVED",   fmt_indian(cases_received),             "inbound to warehouse",   "#2980B9", "#FFFFFF"),
    ]):
        with col:
            st.markdown(kpi_card(title, val, sub, border, vc), unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── PRIMARY KPIs — row 2: quality / service ───────────
    avg_sz = primary["avg_order_size"]
    r2 = st.columns(4)
    for col, (title, val, sub, border, vc) in zip(r2, [
        ("RETURN RATE %",      f"{rr:.1f}%",                           "returns ÷ dispatched",   "#C0392B", rate_color(rr)),
        ("TOTAL RETURNS",      fmt_indian(primary["total_returns"]),   "returned from customers","#C0392B", "#FFFFFF"),
        ("COUNT OF ORDERS",    fmt_indian(primary["count_orders"]),    "unique invoices",         "#1565C0", "#FFFFFF"),
        ("AVG ORDER SIZE",     f"{avg_sz:.1f}",                        "cases per order",         "#1565C0", "#FFFFFF"),
    ]):
        with col:
            st.markdown(kpi_card(title, val, sub, border, vc), unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── INVENTORY KPIs ───────────────────────────────────
    inv_kpis = compute_inventory_kpis(f_inventory, f_despatch, fixed_manpower, f_orders)
    sc_disp  = "No dispatch" if inv_kpis["stock_cover_na"] else f"{inv_kpis['stock_cover']:.1f}"
    sc_sub   = "no despatch data" if inv_kpis["stock_cover_na"] else "days of forward cover"

    rs_case   = compute_rs_per_case(f_despatch, master_maps.get("rent", {}), zone_sel, plant_sel)
    rs_disp   = fmt_currency(rs_case) if rs_case is not None else "—"
    rs_sub    = "rent ÷ cases dispatched" if rs_case is not None else "upload Master_WH with Rent column"

    inv_cols = st.columns(5)
    for col, (title, val, sub, border, vc) in zip(inv_cols, [
        ("TOTAL INVENTORY VALUE",  fmt_currency(inv_kpis["total_value"]),   "month-end stock",               "#E67E22", "#FFFFFF"),
        ("STOCK COVER (DAYS)",     sc_disp,                                 sc_sub,                          "#E67E22", "#FFFFFF"),
        ("CASES LOADED / MANHOUR", f"{inv_kpis['cases_per_manhour']:.1f}", f"based on {fixed_manpower} mp", "#E67E22", "#FFFFFF"),
        ("MANPOWER PER ORDER",     f"{inv_kpis['manpower_per_order']:.2f}","fixed manpower ÷ orders",        "#E67E22", "#FFFFFF"),
        ("Rs/CASE",                rs_disp,                                 rs_sub,                          "#8E44AD", "#FFFFFF"),
    ]):
        with col:
            st.markdown(kpi_card(title, val, sub, border, vc), unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── INVENTORY HEALTH ────────────────────────────────
    exp_kpis = compute_expiry_kpis(f_inventory)
    health_cols = st.columns(4)
    for col, (title, val, sub, border, vc) in zip(health_cols, [
        ("EXPIRED STOCK VALUE",   fmt_currency(exp_kpis["expired_value"]), "immediate write-off risk",      "#C0392B", "#C0392B"),
        ("NEAR EXPIRY 0-30 DAYS", fmt_indian(exp_kpis["near_30_cases"]),  "cases expiring within 30 days", "#E67E22", "#E67E22"),
        ("31-45 DAYS TO EXPIRY",  fmt_indian(exp_kpis["near_45_cases"]),  "cases expiring in 31-45 days",  "#F39C12", "#F39C12"),
        ("46-60 DAYS TO EXPIRY",  fmt_indian(exp_kpis["near_60_cases"]),  "cases expiring in 46-60 days",  "#F1C40F", "#F1C40F"),
    ]):
        with col:
            st.markdown(kpi_card(title, val, sub, border, vc), unsafe_allow_html=True)

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


# ════════════════════════════════════════════════════════
# TAB 2 — RLM ZONE VIEW
# ════════════════════════════════════════════════════════
with tab2:
    st.subheader("🏭 RLM Zone Comparison")
    st.caption("Side-by-side warehouse KPIs within a zone — mirrors the Excel RLM Dashboard. '—' = no data / zero denominator.")

    rlm_zone = st.selectbox(
        "Select Zone", ["North", "South", "East", "West", "All Zones"],
        key="rlm_zone_sel",
    )

    rlm_df = compute_rlm_table(
        orders, despatch, returns, receiving, inventory,
        zone_sel=rlm_zone,
        fixed_manpower=fixed_manpower,
        master_maps=master_maps,
    )

    if rlm_df.empty:
        st.info("No data available for the selected zone.")
    else:
        rlm_df.insert(1, "Warehouse", rlm_df["Plant"].apply(plant_display))

        # ── Summary callouts ─────────────────────────────
        best_idx  = rlm_df["Cases_Dispatched"].idxmax()
        worst_fr  = rlm_df["Fill_Rate_%"].idxmin()
        worst_rr  = rlm_df["Return_Rate_%"].idxmax()

        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown(kpi_card(
                "TOP DISPATCHER",
                fmt_indian(rlm_df.loc[best_idx, "Cases_Dispatched"]),
                rlm_df.loc[best_idx, "Warehouse"],
                "#27AE60", "#27AE60"
            ), unsafe_allow_html=True)
        with c2:
            low_fr = rlm_df.loc[worst_fr, "Fill_Rate_%"]
            st.markdown(kpi_card(
                "LOWEST FILL RATE",
                f"{low_fr:.1f}%" if pd.notna(low_fr) else "—",
                rlm_df.loc[worst_fr, "Warehouse"],
                "#E67E22", fill_rate_color(low_fr) if pd.notna(low_fr) else "#FFFFFF"
            ), unsafe_allow_html=True)
        with c3:
            high_rr = rlm_df.loc[worst_rr, "Return_Rate_%"]
            st.markdown(kpi_card(
                "HIGHEST RETURN RATE",
                f"{high_rr:.1f}%" if pd.notna(high_rr) else "—",
                rlm_df.loc[worst_rr, "Warehouse"],
                "#C0392B", rate_color(high_rr) if pd.notna(high_rr) else "#FFFFFF"
            ), unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("#### Warehouse KPI Summary")

        # Build a display version: format NaN as "—" for string cols, keep currency
        def _fmt_rlm_cell(col_name, val):
            if pd.isna(val):
                return "—"
            if col_name == "Inv_Value_INR":
                return fmt_currency(val)
            if col_name in ("Rs_Per_Case", "Rent_Per_Sqft"):
                return f"₹{val:,.2f}"
            if col_name in ("Fill_Rate_%", "Return_Rate_%", "Dock_Util_%"):
                return f"{val:.1f}%"
            if col_name == "Stock_Cover_Days":
                return f"{val:.1f}"
            if isinstance(val, float):
                return f"{val:.1f}"
            return str(val)

        display_cols = [
            "Plant", "Warehouse", "Cases_Ordered", "Cases_Dispatched",
            "Fill_Rate_%", "Cases_Received", "Returned_Cases", "Return_Rate_%",
            "Inv_Value_INR", "Stock_Cover_Days", "Rs_Per_Case",
            "Dock_Util_%", "Rent_Per_Sqft", "Cases_Per_MH",
            "Avg_Order_Size", "Dispatch_Rank",
        ]
        display_cols = [c for c in display_cols if c in rlm_df.columns]

        disp = rlm_df[display_cols].copy()
        for c in disp.columns:
            disp[c] = disp[c].apply(lambda v, cn=c: _fmt_rlm_cell(cn, v))

        def _style_rlm(df_row):
            styles = [""] * len(df_row)
            cols_list = list(disp.columns)

            for col_name, color_fn, default in [
                ("Fill_Rate_%",   fill_rate_color, None),
                ("Return_Rate_%", rate_color,       None),
            ]:
                if col_name in cols_list:
                    i   = cols_list.index(col_name)
                    raw = df_row.iloc[i]
                    if raw != "—":
                        try:
                            styles[i] = f"color: {color_fn(float(raw.rstrip('%')))}"
                        except Exception:
                            pass

            if "Dispatch_Rank" in cols_list:
                i = cols_list.index("Dispatch_Rank")
                if df_row.iloc[i] == "1":
                    styles[i] = "color: #27AE60; font-weight: 700"

            return styles

        st.dataframe(
            disp.style.apply(_style_rlm, axis=1),
            use_container_width=True,
            hide_index=True,
        )

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

    def _sev_style(val):
        if val == "HIGH":
            return "color: #E74C3C; font-weight: 700"
        if val == "MEDIUM":
            return "color: #E67E22; font-weight: 700"
        return "color: #F1C40F; font-weight: 700"

    st.dataframe(
        error_df.style.map(_sev_style, subset=["Severity"]),
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

        for col, (title, val, sub) in zip(st.columns(4), [
            ("TOTAL SHIPMENTS",     fmt_indian(tp_shipments), "rows in transport file"),
            ("TOTAL CASES",         fmt_indian(tp_cases),     "Billing_Qty sum"),
            ("UNIQUE SOURCES",      fmt_indian(tp_vendors),   "source plants"),
            ("UNIQUE DESTINATIONS", fmt_indian(tp_dests),     "destination cities"),
        ]):
            with col:
                st.markdown(kpi_card(title, val, sub), unsafe_allow_html=True)

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


# ════════════════════════════════════════════════════════
# TAB 5 — RAW DATA
# ════════════════════════════════════════════════════════
with tab5:
    st.subheader("📋 Raw Data Export")

    for name, df in [
        ("Customer Orders",     f_orders),
        ("Order Despatch",      f_despatch),
        ("Returns",             f_returns),
        ("Receiving",           f_receiving),
        ("Month-End Inventory", f_inventory),
        ("Inventory Accuracy",  f_inv_acc),
    ]:
        rows = len(df) if df is not None else 0
        with st.expander(f"{name} — {rows:,} rows"):
            if df is not None and not df.empty:
                st.dataframe(df, use_container_width=True, height=300, hide_index=True)
                st.download_button(
                    label=f"⬇ Download {name} CSV",
                    data=df.to_csv(index=False).encode("utf-8"),
                    file_name=f"{name.lower().replace(' ', '_')}.csv",
                    mime="text/csv",
                    key=f"dl_{name}",
                )
            else:
                st.info(f"No data available for {name}")
