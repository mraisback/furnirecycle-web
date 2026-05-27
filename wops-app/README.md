# WOPS Intelligence Dashboard
**Warehouse Operations Performance System — PepsiCo India**

A Streamlit web application that replicates and extends an Excel Power Query dashboard for warehouse operations analytics.

---

## Local Development

```bash
cd wops-app
pip install -r requirements.txt
streamlit run app.py
```

---

## Streamlit Cloud (free — recommended)

1. Push this repository to GitHub (public or private)
2. Go to [share.streamlit.io](https://share.streamlit.io) → **New app**
3. Select your repo + branch + **`wops-app/app.py`** as the entry point
4. Click **Deploy** — no environment variables required

> Set the app root to `wops-app/` or point the entry file to `wops-app/app.py`.

---

## Render.com

| Setting | Value |
|---|---|
| **Build command** | `pip install -r wops-app/requirements.txt` |
| **Start command** | `streamlit run wops-app/app.py --server.port $PORT --server.headless true` |
| **Health check path** | `/healthz` |

---

## Railway.app

Use the same start command as Render. Set `PORT` in environment variables if not auto-injected.

---

## Input Files

| # | File | Description |
|---|------|-------------|
| 1 | `zsd_salefl.xlsx` | SAP Sales & Logistics export (Sheet1) |
| 2 | `nysd_css.xlsx` | SAP CSS Inventory snapshot (Sheet1) |
| 3 | `Transport.xlsx` | Freight/transport data — **optional** (Sheet1) |

---

## Architecture

```
wops-app/
├── app.py                    ← Streamlit entry point (< 200 lines logic)
├── requirements.txt
├── .streamlit/config.toml    ← Dark theme
├── src/
│   ├── data_loader.py        ← File reading (openpyxl)
│   ├── transformer.py        ← All DataFrame transformations
│   ├── filters.py            ← Zone map + apply_filter()
│   ├── kpis.py               ← KPI computation functions
│   ├── charts.py             ← Plotly chart builders
│   ├── styles.py             ← CSS + KPI card HTML renderer
│   └── error_detection.py    ← Quality check / error log
└── README.md
```
