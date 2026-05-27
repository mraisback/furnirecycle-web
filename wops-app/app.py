import streamlit as st
import pandas as pd

st.set_page_config(layout="wide", page_title="WOPS Intelligence Dashboard", page_icon="📦")

from src.styles import (
    GLOBAL_CSS, kpi_card, selector_bar, fmt_currency, fmt_indian, rate_color, accuracy_color,
)
from src.data_loader import load_zsd, get_transaction_types
from src.transformer import build_all_dataframes
from src.filters import apply_filter
from src.kpis import (
    compute_primary_kpis, compute_receiving_kpi, compute_inventory_kpis,
    compute_expiry_kpis, compute_returns_by_category, compute_channel_split,
    compute_inventory_health_table,
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
    master_file    = st.file_uploader("FILE 4 — Master_WH.xlsx (optional)\nEnables Zone mapping", type=["xlsx"], key="mwh")

    st.markdown("---")

    if not (zsd_file and nysd_file):
        st.info("Upload files 1 & 2 to begin.")
        st.stop()

    # Read ALL file bytes exactly once here — UploadedFile pointer is exhausted after first .read()
    zsd_bytes      = zsd_file.read()
    nysd_bytes     = nysd_file.read()
    tp_bytes       = transport_file.read() if transport_file else None
    mwh_bytes      = master_file.read()    if master_file    else None

    # Transaction type mapping
    raw_zsd, load_err = load_zsd(zsd_bytes)
    if load_err:
        st.error(f"Could not read FILE 1: {load_err}")
        st.stop()

    all_types = get_transaction_types(raw_zsd)

    # Seed session-state defaults only when the file changes — never pass default= alongside
    # key= in st.multiselect, as Streamlit re-applies default= on every rerun, resetting the
    # user's selections.
    _file_hash = hash(zsd_bytes)
    if st.session_state.get("_zsd_hash") != _file_hash:
        st.session_state["_zsd_hash"]   = _file_hash
        st.session_state["inv_types"]   = [t for t in all_types if any(
            k in t.upper() for k in ["INVOICE", "BILLING", "F2", "ZF2", "F8"])]
        st.session_state["cred_types"]  = [t for t in all_types if
            "CREDIT" in t.upper() or t.upper() in ("RE", "REN", "RE2")]
        st.session_state["ch_types"]    = [t for t in all_types if
            "CHALLAN" in t.upper() or "DELIVERY" in t.upper()]

    # Always expanded so interactions inside don't collapse the widget on rerun
    with st.expander("⚙ Column Mapping", expanded=True):
        if not all_types:
            st.warning("⚠ No transaction types detected. Check sheet/column names.")
        else:
            st.caption(f"{len(all_types)} transaction type(s) found in FILE 1")

        # NO default= parameter here — session state (set above) drives the value
        invoice_types = st.multiselect(
            "Invoice / Billing types", all_types, key="inv_types",
        )
        credit_types = st.multiselect(
            "Credit Note types", all_types, key="cred_types",
        )
        challan_types = st.multiselect(
            "Delivery Challan types", all_types, key="ch_types",
        )

    st.markdown("---")
    zone_sel  = st.selectbox("Zone", ["All Zones", "North", "South", "East", "West"])

    st.markdown("---")
    st.markdown("**Parameters**")
    fixed_manpower = st.number_input("Fixed Manpower", min_value=1, value=50, step=1)


# ── LOAD & TRANSFORM DATA ─────────────────────────────────────────────────────
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

# Populate Plant dropdown with real plant codes (or names if Master_WH was provided)
# Build name_map for display
from src.filters import build_zone_map_from_master
from src.data_loader import load_master_wh

plant_name_map: dict = {}
if mwh_bytes:
    mwh_df, _ = load_master_wh(mwh_bytes)
    _, plant_name_map = build_zone_map_from_master(mwh_df)

def plant_display(code: str) -> str:
    return plant_name_map.get(str(code), str(code)) if plant_name_map else str(code)

all_plant_codes = []
if orders is not None and "Plant" in orders.columns:
    all_plant_codes = sorted(orders["Plant"].dropna().unique().tolist(), key=str)

plant_display_options = ["All Plants"] + [plant_display(p) for p in all_plant_codes]
plant_code_options    = ["All Plants"] + list(map(str, all_plant_codes))

plant_sel_disp = st.sidebar.selectbox("Plant", plant_display_options, key="plant_sel_real")
# Map display name back to code for filtering
if plant_sel_disp == "All Plants":
    plant_sel = "All Plants"
else:
    idx = plant_display_options.index(plant_sel_disp)
    plant_sel = plant_code_options[idx]


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
tab1, tab2, tab3, tab4 = st.tabs(["📊 Dashboard", "⚠ Error Log", "🚚 Transport", "📋 Raw Data"])


# ════════════════════════════════════════════════════════
# TAB 1 — DASHBOARD
# ════════════════════════════════════════════════════════
with tab1:
    st.markdown(selector_bar(plant_sel_disp, zone_sel), unsafe_allow_html=True)

    # ── PRIMARY KPIs ─────────────────────────────────────
    primary        = compute_primary_kpis(f_orders, f_despatch, f_returns)
    cases_received = compute_receiving_kpi(f_receiving)
    rr             = primary["return_rate"]
    rr_color       = rate_color(rr)

    kpi_cols = st.columns(7)
    cards = [
        ("TOTAL CASES ORDERED",   fmt_indian(primary["total_ordered"]),    "from customer orders",    "#1565C0", "#FFFFFF"),
        ("TOTAL RETURNS (CASES)", fmt_indian(primary["total_returns"]),    "returned from customers", "#C0392B", "#FFFFFF"),
        ("RETURN RATE %",         f"{rr:.1f}%",                            "green <2%, red >5%",      "#C0392B", rr_color),
        ("COUNT OF ORDERS",       fmt_indian(primary["count_orders"]),     "unique invoices",         "#1565C0", "#FFFFFF"),
        ("UNIQUE CUSTOMERS",      fmt_indian(primary["unique_customers"]), "distinct buyers",         "#1565C0", "#FFFFFF"),
        ("CASES DISPATCHED",      fmt_indian(primary["cases_dispatched"]), "shipped to customers",    "#27AE60", "#FFFFFF"),
        ("CASES RECEIVED",        fmt_indian(cases_received),              "inbound to warehouse",    "#2980B9", "#FFFFFF"),
    ]
    for col, (title, val, sub, border, vc) in zip(kpi_cols, cards):
        with col:
            st.markdown(kpi_card(title, val, sub, border, vc), unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── INVENTORY & RECEIVING KPIs ───────────────────────
    inv_kpis = compute_inventory_kpis(f_inventory, f_despatch, fixed_manpower, f_orders)
    inv_cols = st.columns(4)
    inv_cards = [
        ("TOTAL INVENTORY VALUE",  fmt_currency(inv_kpis["total_value"]),
         "month-end stock",                    "#E67E22", "#FFFFFF"),
        ("STOCK COVER (DAYS)",     f"{inv_kpis['stock_cover']:.1f}",
         "days of forward cover",             "#E67E22", "#FFFFFF"),
        ("CASES LOADED / MANHOUR", f"{inv_kpis['cases_per_manhour']:.1f}",
         f"based on {fixed_manpower} manpower","#E67E22", "#FFFFFF"),
        ("MANPOWER PER ORDER",     f"{inv_kpis['manpower_per_order']:.2f}",
         "fixed manpower / orders",           "#E67E22", "#FFFFFF"),
    ]
    for col, (title, val, sub, border, vc) in zip(inv_cols, inv_cards):
        with col:
            st.markdown(kpi_card(title, val, sub, border, vc), unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── INVENTORY HEALTH ────────────────────────────────
    exp_kpis = compute_expiry_kpis(f_inventory)
    health_cols = st.columns(4)
    health_cards = [
        ("EXPIRED STOCK VALUE",  fmt_currency(exp_kpis["expired_value"]),
         "immediate write-off risk",        "#C0392B", "#C0392B"),
        ("NEAR EXPIRY 0-30 DAYS",fmt_indian(exp_kpis["near_30_cases"]),
         "cases expiring within 30 days",   "#E67E22", "#E67E22"),
        ("30-45 DAYS TO EXPIRY", fmt_indian(exp_kpis["near_45_cases"]),
         "cases expiring in 31-45 days",    "#F39C12", "#F39C12"),
        ("45-60 DAYS TO EXPIRY", fmt_indian(exp_kpis["near_60_cases"]),
         "cases expiring in 46-60 days",    "#F1C40F", "#F1C40F"),
    ]
    for col, (title, val, sub, border, vc) in zip(health_cols, health_cards):
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
# TAB 2 — ERROR LOG
# ════════════════════════════════════════════════════════
with tab2:
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
        use_container_width=True,
        hide_index=True,
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
# TAB 3 — TRANSPORT
# ════════════════════════════════════════════════════════
with tab3:
    if transport is None or transport.empty:
        st.info("Upload FILE 3 (Transport.xlsx) to view transport analytics.")
    else:
        st.subheader("🚚 Transport Analysis")
        tp = f_transport if (f_transport is not None and not f_transport.empty) else transport

        tp_shipments = len(tp)
        tp_cases     = int(tp["Billing_Qty"].sum())   if "Billing_Qty"   in tp.columns else 0
        tp_vendors   = tp["Source_Plant"].nunique()    if "Source_Plant"  in tp.columns else 0
        tp_dests     = tp["Dest_City"].nunique()       if "Dest_City"     in tp.columns else 0

        kc1, kc2, kc3, kc4 = st.columns(4)
        for col, (title, val, sub) in zip([kc1, kc2, kc3, kc4], [
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
# TAB 4 — RAW DATA
# ════════════════════════════════════════════════════════
with tab4:
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
