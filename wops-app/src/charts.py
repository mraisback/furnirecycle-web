import plotly.express as px
import plotly.graph_objects as go
import pandas as pd

CHART_LAYOUT = dict(
    paper_bgcolor="#0D1B2A",
    plot_bgcolor="#111D2E",
    font=dict(color="#8AAAC8", family="Calibri"),
    margin=dict(l=10, r=10, t=30, b=10),
    showlegend=True,
)

PALETTE = {
    "TEAL":   "#1ABC9C",
    "BLUE":   "#1565C0",
    "ORANGE": "#E67E22",
    "GREEN":  "#27AE60",
    "PURPLE": "#8E44AD",
    "RED":    "#C0392B",
    "GOLD":   "#F39C12",
    "LBLUE":  "#2980B9",
}

CHANNEL_COLORS = {
    "Modern Trade":      "#1565C0",
    "Traditional Trade": "#27AE60",
    "E-Commerce SNX":    "#E67E22",
    "On premise":        "#8E44AD",
    "Stock xfr":         "#7F8C8D",
}


def _apply_base(fig):
    fig.update_layout(**CHART_LAYOUT)
    fig.update_xaxes(gridcolor="#1E3A5F", showgrid=True)
    fig.update_yaxes(gridcolor="#1E3A5F", showgrid=False)
    return fig


def returns_bar_chart(df: pd.DataFrame) -> go.Figure:
    if df.empty or df["Cases"].sum() == 0:
        fig = go.Figure()
        fig.add_annotation(text="No returns data", showarrow=False,
                           font=dict(color="#8AAAC8", size=14))
        return _apply_base(fig)

    fig = px.bar(
        df,
        x="Cases",
        y="Damage_Category",
        orientation="h",
        text="Cases",
        title="Returns by Damage Category",
        color_discrete_sequence=[PALETTE["TEAL"]],
    )
    fig.update_traces(textposition="outside", textfont_color="#FFFFFF")
    fig.update_xaxes(title="Cases Returned", showgrid=True, gridcolor="#1E3A5F")
    fig.update_yaxes(title="", showgrid=False, categoryorder="total ascending")
    fig.update_layout(showlegend=False)
    return _apply_base(fig)


def channel_pie_chart(df: pd.DataFrame) -> go.Figure:
    if df.empty or df["Cases_Ordered"].sum() == 0:
        fig = go.Figure()
        fig.add_annotation(text="No channel data", showarrow=False,
                           font=dict(color="#8AAAC8", size=14))
        return _apply_base(fig)

    colors = [CHANNEL_COLORS.get(c, "#95A5A6") for c in df["Customer_Type"]]
    fig = go.Figure(data=[go.Pie(
        labels=df["Customer_Type"],
        values=df["Cases_Ordered"],
        hole=0.35,
        marker_colors=colors,
        textinfo="percent+label",
        textfont=dict(size=11, color="#FFFFFF"),
    )])
    fig.update_layout(
        title="Channel Split — Cases Ordered",
        legend=dict(orientation="h", yanchor="bottom", y=-0.3, xanchor="center", x=0.5),
    )
    return _apply_base(fig)


def transport_state_bar(df: pd.DataFrame) -> go.Figure:
    if df.empty or "Dest_State" not in df.columns or "Billing_Qty" not in df.columns:
        fig = go.Figure()
        fig.add_annotation(text="No transport data", showarrow=False,
                           font=dict(color="#8AAAC8", size=14))
        return _apply_base(fig)

    grp = (
        df.groupby("Dest_State")["Billing_Qty"]
        .sum()
        .nlargest(10)
        .reset_index()
        .sort_values("Billing_Qty")
    )
    fig = px.bar(
        grp,
        x="Billing_Qty",
        y="Dest_State",
        orientation="h",
        text="Billing_Qty",
        title="Cases by Destination State (Top 10)",
        color_discrete_sequence=[PALETTE["BLUE"]],
    )
    fig.update_traces(textposition="outside", textfont_color="#FFFFFF")
    fig.update_layout(showlegend=False)
    return _apply_base(fig)


def transport_material_bar(df: pd.DataFrame) -> go.Figure:
    if df.empty or "Material_Type" not in df.columns or "Billing_Qty" not in df.columns:
        fig = go.Figure()
        fig.add_annotation(text="No transport data", showarrow=False,
                           font=dict(color="#8AAAC8", size=14))
        return _apply_base(fig)

    grp = (
        df.groupby("Material_Type")["Billing_Qty"]
        .sum()
        .reset_index()
        .sort_values("Billing_Qty", ascending=False)
    )
    fig = px.bar(
        grp,
        x="Material_Type",
        y="Billing_Qty",
        text="Billing_Qty",
        title="Cases by Material Type",
        color_discrete_sequence=[PALETTE["ORANGE"]],
    )
    fig.update_traces(textposition="outside", textfont_color="#FFFFFF")
    fig.update_xaxes(title="Material Type")
    fig.update_yaxes(title="Cases")
    fig.update_layout(showlegend=False)
    return _apply_base(fig)


_TREND_COLORS = {
    "Cases Ordered":    PALETTE["BLUE"],
    "Cases Dispatched": PALETTE["GREEN"],
    "Returned Cases":   PALETTE["RED"],
}


def _empty(msg: str) -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(text=msg, showarrow=False,
                       font=dict(color="#8AAAC8", size=14))
    return _apply_base(fig)


def trend_line(df: pd.DataFrame, title: str = "Trend over time") -> go.Figure:
    """Multi-series line chart. ``df`` must have a 'Period' column plus one
    column per numeric series."""
    if df is None or df.empty or "Period" not in df.columns or df.shape[1] < 2:
        return _empty("No trend data")
    fig = go.Figure()
    for col in [c for c in df.columns if c != "Period"]:
        fig.add_trace(go.Scatter(
            x=df["Period"], y=df[col], mode="lines+markers", name=col,
            line=dict(width=2.5, color=_TREND_COLORS.get(col)),
            marker=dict(size=5),
        ))
    fig.update_layout(
        title=title,
        legend=dict(orientation="h", yanchor="bottom", y=-0.25, xanchor="center", x=0.5),
        hovermode="x unified",
    )
    fig.update_yaxes(title="Cases", showgrid=True, gridcolor="#1E3A5F")
    fig.update_xaxes(title="")
    return _apply_base(fig)


def pareto_chart(df: pd.DataFrame, cat_col: str, val_col: str,
                 title: str = "Pareto") -> go.Figure:
    """Bar (volume) + cumulative-% line on a secondary axis."""
    if df is None or df.empty or cat_col not in df.columns or val_col not in df.columns:
        return _empty("No data")
    cats = df[cat_col].astype(str).tolist()
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=cats, y=df[val_col], name=val_col,
        marker_color=PALETTE["BLUE"], yaxis="y1",
    ))
    if "Cum_%" in df.columns:
        fig.add_trace(go.Scatter(
            x=cats, y=df["Cum_%"], name="Cumulative %", mode="lines+markers",
            line=dict(color=PALETTE["GOLD"], width=2.5), yaxis="y2",
        ))
        fig.add_hline(y=80, line_dash="dot", line_color="#C0392B", yref="y2")
    fig.update_layout(
        title=title,
        yaxis=dict(title="Cases", gridcolor="#1E3A5F"),
        yaxis2=dict(title="Cumulative %", overlaying="y", side="right",
                    range=[0, 105], showgrid=False),
        legend=dict(orientation="h", yanchor="bottom", y=-0.35, xanchor="center", x=0.5),
        xaxis=dict(tickangle=-35),
    )
    return _apply_base(fig)


def hbar(df: pd.DataFrame, cat_col: str, val_col: str, title: str,
         color: str = None) -> go.Figure:
    """Generic horizontal bar (top-N already applied upstream)."""
    if df is None or df.empty or cat_col not in df.columns or val_col not in df.columns:
        return _empty("No data")
    plot = df.sort_values(val_col, ascending=True)
    fig = px.bar(
        plot, x=val_col, y=cat_col, orientation="h", text=val_col, title=title,
        color_discrete_sequence=[color or PALETTE["TEAL"]],
    )
    fig.update_traces(textposition="outside", textfont_color="#FFFFFF")
    fig.update_yaxes(title="", showgrid=False)
    fig.update_xaxes(title="", showgrid=True, gridcolor="#1E3A5F")
    fig.update_layout(showlegend=False, height=max(300, len(plot) * 28))
    return _apply_base(fig)
