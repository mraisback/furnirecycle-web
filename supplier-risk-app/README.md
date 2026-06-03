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

- **Overview** — KPIs, risk-zone donut, top 5 riskiest suppliers, live feed.
- **Suppliers** — filterable directory (zone, category, free-text search) with
  sparkline trends and traffic-light pills.
- **Supplier detail** — signals, sub-category score breakdown, recommended
  action, and one-click "Create task in Ariba" / "Notify buyer" stubs.
- **Alerts** — full intelligence feed, filterable by severity.
- **Analytics** — signals-by-category bar chart, spend-at-risk by category,
  business-case numbers from the briefing.
- **About** — plain-English explanation of how the system works.

## Wiring real data in

Replace `data/suppliers.js` with output from the ingestion + scoring pipeline.
The shape expected by the UI is documented at the top of that file.
