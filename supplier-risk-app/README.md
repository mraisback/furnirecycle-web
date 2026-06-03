# Supplier Risk AI — PepsiCo India

A working, single-page demonstration of the **AI-powered Supplier Risk Early
Warning System** proposed in the CEO briefing. It visualizes daily risk scores,
intelligence signals, alerts, and the business case for protecting PepsiCo
India's packaging and flavor supply base.

## Run locally

No build step — pure HTML/CSS/JS (React + Babel via CDN).

```bash
cd supplier-risk-app
python3 -m http.server 8080
# then open http://localhost:8080
```

Or just double-click `index.html` (some browsers block CDN scripts on
`file://` — prefer the local server).

## Deploy

This is a static site. Any static host works:

- **Vercel / Netlify**: drag-and-drop the `supplier-risk-app/` folder, or point
  the project at this directory.
- **GitHub Pages**: push to a branch and enable Pages with the `supplier-risk-app/`
  folder as the source.
- **Cloudflare Pages / S3 + CloudFront**: upload as-is.

There are no environment variables, no API keys, no backend.

## Project structure

```
supplier-risk-app/
├─ index.html              # entry point
├─ assets/
│  ├─ styles.css           # design system + layout
│  └─ app.js               # React app (Overview / Suppliers / Detail / Alerts / Analytics / About)
└─ data/
   └─ suppliers.js         # mock supplier data + score / alert helpers
```

## What's included

- **Overview** — KPIs, risk-zone donut, spend-weighted **portfolio risk line
  chart**, top 5 riskiest suppliers, live intelligence feed.
- **Suppliers** — filterable directory (zone, category, free-text search),
  **sortable columns**, gradient sparklines, traffic-light pills, **star to
  watchlist**, and **working CSV export**.
- **Supplier detail** — risk-history line chart, signals, sub-category score
  breakdown, **qualified backup suppliers**, recommended action, and
  toast-confirmed "Create task in Ariba" / "Notify buyer" actions.
- **Alerts** — full intelligence feed, filterable by severity.
- **Watchlist** — suppliers you've starred, persisted in `localStorage`.
- **Analytics** — portfolio trend, signals-by-category bar chart, spend-at-risk,
  business-case numbers from the briefing.
- **Settings** — tune Amber/Red thresholds, toggle Live mode, clear data.
- **About** — plain-English explanation of how the system works.

### Robustness & polish

- **Hash routing** (`#/overview`, `#/supplier/uflex`, …) — deep-linkable,
  refresh-safe, browser back/forward works.
- **Error boundary** — a view error shows a recovery card, never a white screen.
- **Command palette** — press <kbd>⌘/Ctrl</kbd>+<kbd>K</kbd> to jump to any page
  or supplier.
- **Light / dark theme** toggle, **Live mode** (simulated score drift), toast
  notifications, keyboard-navigable nav, ARIA roles, reduced-motion support.
- State (theme, watchlist, thresholds) persists across reloads.

## Wiring real data in

Replace `data/suppliers.js` with output from the ingestion + scoring pipeline.
The shape expected by the UI is documented at the top of that file.
