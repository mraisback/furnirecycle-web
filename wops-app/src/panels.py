"""Streamlit render functions for the upgraded tabs / sections.

Keeping the heavier UI here keeps app.py readable and makes every panel
independently testable. Every function is defensive against None / empty inputs.
"""
import io

import pandas as pd
import streamlit as st

from src import analytics, charts
from src.styles import kpi_card, fmt_indian, fmt_currency, rate_color


# ── Alerts banner (Dashboard top) ─────────────────────────────────────────────
def render_alerts(despatch, returns, inventory, rr_warn, rr_crit, near_days,
                  plant_display=None):
    """Surface the plants/stock that breach the user-configured thresholds."""
    msgs_crit, msgs_warn = [], []

    rr = analytics.plant_return_rates(despatch, returns)
    if not rr.empty:
        flagged = rr[rr["Return_Rate_%"].notna() & (rr["Return_Rate_%"] >= rr_warn)]
        flagged = flagged.sort_values("Return_Rate_%", ascending=False)
        for _, row in flagged.iterrows():
            name = plant_display(row["Plant"]) if plant_display else str(row["Plant"])
            line = f"**{name}** return rate {row['Return_Rate_%']:.1f}% (≥ {rr_warn:.1f}%)"
            (msgs_crit if row["Return_Rate_%"] >= rr_crit else msgs_warn).append(line)

    near_cases, exp_cases, exp_value = analytics.near_expiry_summary(inventory, near_days)
    if exp_cases > 0:
        msgs_crit.append(
            f"**{fmt_indian(exp_cases)}** cases already expired "
            f"({fmt_currency(exp_value)} write-off risk)"
        )
    if near_cases > 0:
        msgs_warn.append(
            f"**{fmt_indian(near_cases)}** cases expiring within {near_days} days"
        )

    if not msgs_crit and not msgs_warn:
        st.success("✅ No alerts — all selected plants are within thresholds.")
        return
    if msgs_crit:
        st.error("🚨 **Critical**\n\n" + "\n\n".join(f"- {m}" for m in msgs_crit))
    if msgs_warn:
        st.warning("⚠️ **Warning**\n\n" + "\n\n".join(f"- {m}" for m in msgs_warn))


# ── SKU drill-down (Dashboard bottom) ─────────────────────────────────────────
def render_sku_drilldown(orders, returns):
    with st.expander("🔎 SKU Drill-down — top movers & most-returned"):
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Top SKUs by Cases Ordered**")
            top = analytics.sku_breakdown(orders, "Cases_Ordered", top_n=15)
            if top.empty:
                st.info("No order data for selection")
            else:
                st.plotly_chart(
                    charts.hbar(top, top.columns[0], "Cases_Ordered",
                                "Top SKUs — Cases Ordered", color="#1565C0"),
                    use_container_width=True,
                )
        with c2:
            st.markdown("**Most-Returned SKUs**")
            top_r = analytics.sku_breakdown(returns, "Returned_Cases", top_n=15)
            if top_r.empty:
                st.info("No returns data for selection")
            else:
                st.plotly_chart(
                    charts.hbar(top_r, top_r.columns[0], "Returned_Cases",
                                "Top SKUs — Returns", color="#C0392B"),
                    use_container_width=True,
                )


# ── Trends tab ────────────────────────────────────────────────────────────────
def render_trends(orders, despatch, returns):
    st.subheader("📈 Trends Over Time")
    st.caption("Volume movement across the selected period. Switch granularity below.")

    freq_label = st.radio(
        "Granularity", ["Monthly", "Weekly", "Daily"],
        horizontal=True, key="trend_freq",
    )
    freq = {"Monthly": "MS", "Weekly": "W", "Daily": "D"}[freq_label]

    trend = analytics.combined_trend(orders, despatch, returns, freq=freq)
    if trend.empty or trend.shape[1] < 2:
        st.info("No dated transactions available for the current selection.")
        return

    st.plotly_chart(
        charts.trend_line(trend, f"{freq_label} Volume — Ordered vs Dispatched vs Returned"),
        use_container_width=True,
    )

    # Period-over-period summary
    numeric_cols = [c for c in trend.columns if c != "Period"]
    cols = st.columns(len(numeric_cols))
    for col, name in zip(cols, numeric_cols):
        series = trend[name]
        latest = series.iloc[-1]
        prev = series.iloc[-2] if len(series) > 1 else 0
        delta = (latest - prev)
        delta_pct = (delta / prev * 100) if prev else 0
        with col:
            st.metric(
                f"{name} — latest period",
                fmt_indian(latest),
                f"{delta_pct:+.1f}% vs prev" if prev else "—",
            )

    with st.expander("⬇ Trend data table"):
        disp = trend.copy()
        disp["Period"] = pd.to_datetime(disp["Period"]).dt.strftime("%d %b %Y")
        st.dataframe(disp, use_container_width=True, hide_index=True)
        st.download_button(
            "Download trend CSV",
            trend.to_csv(index=False).encode("utf-8"),
            file_name="wops_trend.csv", mime="text/csv", key="dl_trend",
        )


# ── Customers & Products tab ──────────────────────────────────────────────────
def render_customers(orders, returns):
    st.subheader("👥 Customer Concentration & Product Mix")

    if orders is None or orders.empty:
        st.info("No order data available for the current selection.")
        return

    pareto = analytics.customer_pareto(orders, "Cases_Ordered", top_n=15)
    n_cust = orders["Customer"].nunique() if "Customer" in orders.columns else 0

    k = st.columns(3)
    with k[0]:
        st.markdown(kpi_card("UNIQUE CUSTOMERS", fmt_indian(n_cust),
                             "distinct sold-to parties", "#1565C0"), unsafe_allow_html=True)
    if not pareto.empty:
        top1_share = pareto["Share_%"].iloc[0]
        # how many customers make up 80% of volume
        within_80 = int((pareto["Cum_%"] <= 80).sum()) + 1
        with k[1]:
            st.markdown(kpi_card("TOP CUSTOMER SHARE", f"{top1_share:.1f}%",
                                 str(pareto["Customer"].iloc[0])[:22], "#27AE60"),
                        unsafe_allow_html=True)
        with k[2]:
            st.markdown(kpi_card("CUSTOMERS → 80% VOL", fmt_indian(within_80),
                                 "concentration depth", "#E67E22"), unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    if pareto.empty:
        st.info("No customer volume to chart.")
    else:
        st.plotly_chart(
            charts.pareto_chart(pareto, "Customer", "Cases_Ordered",
                                "Customer Pareto — Cases Ordered"),
            use_container_width=True,
        )

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("##### Top Customers")
        if pareto.empty:
            st.info("No data")
        else:
            disp = pareto.copy()
            disp["Cases_Ordered"] = disp["Cases_Ordered"].apply(fmt_indian)
            st.dataframe(disp, use_container_width=True, hide_index=True, height=360)
    with c2:
        st.markdown("##### Product Mix")
        cat = analytics.category_breakdown(orders, top_n=15)
        if cat.empty:
            st.info("No product/category data")
        else:
            st.plotly_chart(
                charts.hbar(cat, cat.columns[0], cat.columns[1],
                            "Cases by Product Group", color="#8E44AD"),
                use_container_width=True,
            )


# ── Vendor analytics (Transport tab) ──────────────────────────────────────────
def render_vendors(transport):
    vend = analytics.vendor_performance(transport, top_n=15)
    if vend.empty:
        return
    st.markdown("#### 🏷️ Vendor / Transporter Performance")
    c1, c2 = st.columns([3, 2])
    with c1:
        st.plotly_chart(
            charts.hbar(vend, "Vendor_Name", "Cases", "Cases by Vendor", color="#16A085"),
            use_container_width=True,
        )
    with c2:
        disp = vend.copy()
        disp["Cases"] = disp["Cases"].apply(fmt_indian)
        disp["Shipments"] = disp["Shipments"].apply(fmt_indian)
        st.dataframe(disp, use_container_width=True, hide_index=True, height=400)


# ── Searchable raw-data table ─────────────────────────────────────────────────
def searchable_table(name: str, df, key: str):
    """Render one raw-data table with a free-text filter + CSV download."""
    rows = len(df) if df is not None else 0
    with st.expander(f"{name} — {rows:,} rows"):
        if df is None or df.empty:
            st.info(f"No data available for {name}")
            return
        term = st.text_input(
            "🔎 Filter rows (matches any column)", key=f"search_{key}",
            placeholder="e.g. customer name, SKU, invoice no…",
        )
        view = df
        if term:
            t = term.strip().lower()
            mask = df.apply(
                lambda col: col.astype(str).str.lower().str.contains(t, na=False, regex=False)
            ).any(axis=1)
            view = df[mask]
            st.caption(f"{len(view):,} of {rows:,} rows match “{term}”.")
        st.dataframe(view, use_container_width=True, height=300, hide_index=True)
        st.download_button(
            label=f"⬇ Download {name} CSV (filtered)",
            data=view.to_csv(index=False).encode("utf-8"),
            file_name=f"{name.lower().replace(' ', '_')}.csv",
            mime="text/csv", key=f"dl_{key}",
        )
