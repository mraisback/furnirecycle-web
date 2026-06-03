/* Supplier Risk AI — single-file React app (no build step).
   Renders Overview / Suppliers / Detail / Alerts / Analytics / About. */

const { useState, useMemo, useEffect } = React;

function zoneOf(score) {
  if (score >= 60) return "red";
  if (score >= 35) return "amber";
  return "green";
}

function zoneLabel(z) {
  return { green: "Green", amber: "Amber", red: "Red" }[z];
}

function fmtCr(n) {
  return "₹" + n.toLocaleString("en-IN") + " Cr";
}

function Sparkline({ data, color = "#6c8cff" }) {
  if (!data || !data.length) return null;
  const w = 120, h = 36, pad = 2;
  const min = Math.min(...data), max = Math.max(...data);
  const range = max - min || 1;
  const step = (w - pad * 2) / (data.length - 1);
  const pts = data.map((v, i) => {
    const x = pad + i * step;
    const y = h - pad - ((v - min) / range) * (h - pad * 2);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(" ");
  return (
    <svg className="sparkline" viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none">
      <polyline fill="none" stroke={color} strokeWidth="1.8" points={pts} />
      <circle cx={w - pad} cy={h - pad - ((data[data.length - 1] - min) / range) * (h - pad * 2)} r="2.2" fill={color} />
    </svg>
  );
}

function Donut({ green, amber, red }) {
  const total = green + amber + red || 1;
  const r = 42, c = 2 * Math.PI * r;
  const segs = [
    { v: green, color: "#22c55e" },
    { v: amber, color: "#f59e0b" },
    { v: red,   color: "#ef4444" }
  ];
  let offset = 0;
  return (
    <svg className="donut" viewBox="0 0 110 110">
      <circle cx="55" cy="55" r={r} fill="none" stroke="#1b2347" strokeWidth="14" />
      {segs.map((s, i) => {
        const len = (s.v / total) * c;
        const dasharray = `${len} ${c - len}`;
        const el = <circle key={i} cx="55" cy="55" r={r} fill="none"
          stroke={s.color} strokeWidth="14"
          strokeDasharray={dasharray} strokeDashoffset={-offset}
          transform="rotate(-90 55 55)" strokeLinecap="butt" />;
        offset += len;
        return el;
      })}
      <text x="55" y="51" textAnchor="middle" fill="#e6ebff" fontSize="18" fontWeight="700">{total}</text>
      <text x="55" y="68" textAnchor="middle" fill="#9aa3c7" fontSize="10">suppliers</text>
    </svg>
  );
}

function ScoreBar({ score }) {
  const z = zoneOf(score);
  const color = z === "red" ? "#ef4444" : z === "amber" ? "#f59e0b" : "#22c55e";
  return (
    <div className="score-bar" title={`Risk score ${score}`}>
      <span style={{ width: `${score}%`, background: color }} />
    </div>
  );
}

function Pill({ score }) {
  const z = zoneOf(score);
  return <span className={`pill ${z}`}><span className="dot" style={{
    width: 6, height: 6, borderRadius: "50%",
    background: z === "red" ? "#ef4444" : z === "amber" ? "#f59e0b" : "#22c55e"
  }} />{zoneLabel(z)} · {score}</span>;
}

function DeltaTag({ delta }) {
  if (delta === 0) return <span className="kpi-delta neutral">no change</span>;
  const up = delta > 0;
  return <span className={`kpi-delta ${up ? "up" : "down"}`}>{up ? "▲" : "▼"} {Math.abs(delta)}</span>;
}

/* ---------- Pages ---------- */

function Overview({ go }) {
  const stats = window.computeStats();
  const alerts = window.computeAlerts().slice(0, 5);
  const topRisk = [...window.SUPPLIERS].sort((a, b) => b.score - a.score).slice(0, 5);

  return (
    <div className="fade-in">
      <div className="grid grid-4" style={{ marginBottom: 18 }}>
        <div className="card">
          <h3>Suppliers monitored</h3>
          <div className="kpi-row"><div className="big">{stats.total}</div><span className="kpi-delta neutral">live</span></div>
          <div className="sub">Target: 250+ across packaging, flavors, ingredients</div>
        </div>
        <div className="card">
          <h3>Annual spend covered</h3>
          <div className="kpi-row"><div className="big">{fmtCr(stats.totalSpend)}</div></div>
          <div className="sub">{fmtCr(stats.atRiskSpend)} in Amber/Red zones</div>
        </div>
        <div className="card">
          <h3>Critical alerts (30d)</h3>
          <div className="kpi-row"><div className="big" style={{ color: "#ffb4b4" }}>{stats.red}</div><span className="kpi-delta up">+2</span></div>
          <div className="sub">Includes 1 IBC filing, 1 rating downgrade</div>
        </div>
        <div className="card">
          <h3>Estimated savings YTD</h3>
          <div className="kpi-row"><div className="big" style={{ color: "#b6f5c8" }}>₹6.2 Cr</div><span className="kpi-delta down">on track</span></div>
          <div className="sub">Avoided expediting + line-stop costs</div>
        </div>
      </div>

      <div className="grid grid-3" style={{ marginBottom: 18 }}>
        <div className="card">
          <h3>Risk zone distribution</h3>
          <div className="donut-wrap">
            <Donut green={stats.green} amber={stats.amber} red={stats.red} />
            <div className="legend">
              <div className="legend-item"><span className="swatch" style={{ background: "#22c55e" }} /> Green · {stats.green}</div>
              <div className="legend-item"><span className="swatch" style={{ background: "#f59e0b" }} /> Amber · {stats.amber}</div>
              <div className="legend-item"><span className="swatch" style={{ background: "#ef4444" }} /> Red · {stats.red}</div>
            </div>
          </div>
        </div>

        <div className="card" style={{ gridColumn: "span 2" }}>
          <h3>Top 5 highest-risk suppliers</h3>
          <table className="suppliers">
            <thead><tr><th>Supplier</th><th>Category</th><th>Score</th><th>Trend (90d)</th><th>Δ</th></tr></thead>
            <tbody>
              {topRisk.map(s => (
                <tr key={s.id} onClick={() => go("supplier", s.id)}>
                  <td><strong>{s.name}</strong><div className="sub" style={{ fontSize: 11.5, color: "var(--muted)" }}>{s.sub}</div></td>
                  <td>{s.category}</td>
                  <td><Pill score={s.score} /></td>
                  <td style={{ width: 140 }}><Sparkline data={s.trend} color={zoneOf(s.score) === "red" ? "#ef4444" : zoneOf(s.score) === "amber" ? "#f59e0b" : "#22c55e"} /></td>
                  <td><DeltaTag delta={s.delta} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="card">
        <h3>Recent intelligence feed</h3>
        {alerts.map((a, i) => (
          <div className="signal" key={i}>
            <div className={`signal-icon sev-${a.severity}`}>{a.severity[0]}</div>
            <div style={{ flex: 1 }}>
              <div><strong onClick={() => go("supplier", a.supplierId)} style={{ cursor: "pointer" }}>{a.supplierName}</strong> — {a.text}</div>
              <div className="signal-meta">{a.type} · {a.severity} · {a.source} · {a.date}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function SupplierList({ go, query, setQuery }) {
  const [zone, setZone] = useState("all");
  const [cat, setCat] = useState("all");

  const filtered = useMemo(() => {
    return window.SUPPLIERS.filter(s => {
      if (zone !== "all" && zoneOf(s.score) !== zone) return false;
      if (cat !== "all" && s.category !== cat) return false;
      if (query && !(`${s.name} ${s.sub} ${s.skus.join(" ")}`.toLowerCase().includes(query.toLowerCase()))) return false;
      return true;
    }).sort((a, b) => b.score - a.score);
  }, [zone, cat, query]);

  return (
    <div className="fade-in">
      <div className="filters">
        {["all", "red", "amber", "green"].map(z => (
          <span key={z} className={`chip ${zone === z ? "active" : ""}`} onClick={() => setZone(z)}>
            {z === "all" ? "All zones" : zoneLabel(z)}
          </span>
        ))}
        <span style={{ width: 12 }} />
        {["all", "Packaging", "Flavor"].map(c => (
          <span key={c} className={`chip ${cat === c ? "active" : ""}`} onClick={() => setCat(c)}>
            {c === "all" ? "All categories" : c}
          </span>
        ))}
      </div>

      <div className="card" style={{ padding: 6 }}>
        <table className="suppliers">
          <thead>
            <tr>
              <th>Supplier</th><th>Category</th><th>Spend</th><th>SKUs</th>
              <th>Risk score</th><th>Trend</th><th>Δ</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map(s => (
              <tr key={s.id} onClick={() => go("supplier", s.id)}>
                <td>
                  <strong>{s.name}</strong>
                  <div style={{ fontSize: 11.5, color: "var(--muted)" }}>{s.sub}</div>
                </td>
                <td>{s.category}</td>
                <td>{fmtCr(s.spendCr)}</td>
                <td style={{ color: "var(--muted)", fontSize: 12.5 }}>{s.skus.slice(0, 3).join(", ")}</td>
                <td style={{ minWidth: 200 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                    <Pill score={s.score} />
                    <ScoreBar score={s.score} />
                  </div>
                </td>
                <td style={{ width: 140 }}>
                  <Sparkline data={s.trend} color={zoneOf(s.score) === "red" ? "#ef4444" : zoneOf(s.score) === "amber" ? "#f59e0b" : "#22c55e"} />
                </td>
                <td><DeltaTag delta={s.delta} /></td>
              </tr>
            ))}
            {filtered.length === 0 && (
              <tr><td colSpan="7"><div className="empty">No suppliers match the current filters.</div></td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function SupplierDetail({ id, go }) {
  const s = window.SUPPLIERS.find(x => x.id === id);
  if (!s) return <div className="empty">Supplier not found.</div>;
  const zColor = zoneOf(s.score) === "red" ? "#ef4444" : zoneOf(s.score) === "amber" ? "#f59e0b" : "#22c55e";

  return (
    <div className="fade-in">
      <div className="back-link" onClick={() => go("suppliers")}>← Back to suppliers</div>

      <div className="card" style={{ marginBottom: 16 }}>
        <div style={{ display: "flex", flexWrap: "wrap", justifyContent: "space-between", gap: 12, alignItems: "center" }}>
          <div>
            <div style={{ fontSize: 22, fontWeight: 700 }}>{s.name}</div>
            <div style={{ color: "var(--muted)", fontSize: 13 }}>{s.category} · {s.sub} · Buyer: {s.contact}</div>
          </div>
          <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
            <Pill score={s.score} />
            <DeltaTag delta={s.delta} />
          </div>
        </div>

        <div className="grid grid-4" style={{ marginTop: 14 }}>
          <div><div style={{ color: "var(--muted)", fontSize: 12 }}>ANNUAL SPEND</div><div style={{ fontSize: 18, fontWeight: 700 }}>{fmtCr(s.spendCr)}</div></div>
          <div><div style={{ color: "var(--muted)", fontSize: 12 }}>HERO SKUs</div><div style={{ fontSize: 14 }}>{s.skus.join(", ")}</div></div>
          <div><div style={{ color: "var(--muted)", fontSize: 12 }}>LAST INCIDENT</div><div style={{ fontSize: 14 }}>{s.lastIncident || "—"}</div></div>
          <div><div style={{ color: "var(--muted)", fontSize: 12 }}>90-DAY TREND</div><Sparkline data={s.trend} color={zColor} /></div>
        </div>
      </div>

      <div className="detail-grid">
        <div className="card">
          <h3>Signals detected</h3>
          {(s.signals && s.signals.length) ? s.signals.map((sig, i) => (
            <div className="signal" key={i}>
              <div className={`signal-icon sev-${sig.severity}`}>{sig.severity[0]}</div>
              <div style={{ flex: 1 }}>
                <div>{sig.text}</div>
                <div className="signal-meta">{sig.type} · <strong>{sig.severity}</strong> · {sig.source} · {sig.date}</div>
              </div>
            </div>
          )) : <div className="empty">No signals in the last 90 days.</div>}
        </div>

        <div>
          <div className="card" style={{ marginBottom: 16 }}>
            <h3>Score breakdown</h3>
            {["Financial", "Operational", "Regulatory", "Promoter", "Cyber", "ESG"].map((cat, i) => {
              const subScore = Math.max(0, Math.min(100, Math.round((s.score + (i * 7 - 14)) * (0.5 + (i % 3) * 0.25))));
              const z = zoneOf(subScore);
              const col = z === "red" ? "#ef4444" : z === "amber" ? "#f59e0b" : "#22c55e";
              return (
                <div key={cat} style={{ display: "flex", alignItems: "center", gap: 10, margin: "8px 0" }}>
                  <div style={{ width: 90, fontSize: 12.5, color: "var(--muted)" }}>{cat}</div>
                  <div style={{ flex: 1 }}><div className="score-bar"><span style={{ width: `${subScore}%`, background: col }} /></div></div>
                  <div style={{ width: 28, textAlign: "right", fontSize: 12.5 }}>{subScore}</div>
                </div>
              );
            })}
          </div>

          <div className="card">
            <div className="recommend">
              <div className="recommend-label">Recommended action</div>
              <div>{s.recommendation}</div>
            </div>
            <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
              <button className="btn btn-primary">Create task in Ariba</button>
              <button className="btn">Notify buyer</button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function Alerts({ go }) {
  const [sev, setSev] = useState("all");
  const all = window.computeAlerts();
  const list = sev === "all" ? all : all.filter(a => a.severity === sev);
  return (
    <div className="fade-in">
      <div className="filters">
        {["all", "CRITICAL", "HIGH", "MEDIUM", "LOW"].map(s => (
          <span key={s} className={`chip ${sev === s ? "active" : ""}`} onClick={() => setSev(s)}>{s === "all" ? "All severities" : s}</span>
        ))}
      </div>
      <div className="card">
        {list.length === 0 && <div className="empty">No alerts at this severity.</div>}
        {list.map((a, i) => (
          <div className="signal" key={i}>
            <div className={`signal-icon sev-${a.severity}`}>{a.severity[0]}</div>
            <div style={{ flex: 1 }}>
              <div><strong onClick={() => go("supplier", a.supplierId)} style={{ cursor: "pointer" }}>{a.supplierName}</strong> — {a.text}</div>
              <div className="signal-meta">{a.type} · {a.severity} · {a.source} · {a.date}</div>
            </div>
            <Pill score={a.score} />
          </div>
        ))}
      </div>
    </div>
  );
}

function Analytics() {
  const all = window.SUPPLIERS;
  const cats = ["Financial", "Operational", "Regulatory", "Promoter", "Cyber", "ESG", "Insolvency", "Market"];
  const counts = cats.map(c => ({
    cat: c,
    n: all.reduce((acc, s) => acc + (s.signals || []).filter(x => x.type === c).length, 0)
  }));
  const max = Math.max(...counts.map(c => c.n), 1);

  return (
    <div className="fade-in">
      <div className="grid grid-2">
        <div className="card">
          <h3>Signals by category (last 90d)</h3>
          <div className="bar-chart">
            {counts.map(c => (
              <div className="bar" key={c.cat} style={{ height: `${(c.n / max) * 100}%`, minHeight: c.n ? 12 : 2 }}>
                <span className="value">{c.n}</span>
                <span className="label">{c.cat}</span>
              </div>
            ))}
          </div>
          <div className="legend-row" />
        </div>

        <div className="card">
          <h3>Spend at risk by category</h3>
          {["Packaging", "Flavor"].map(c => {
            const cat = all.filter(s => s.category === c);
            const total = cat.reduce((a, s) => a + s.spendCr, 0);
            const atRisk = cat.filter(s => s.score >= 35).reduce((a, s) => a + s.spendCr, 0);
            const pct = total ? Math.round((atRisk / total) * 100) : 0;
            return (
              <div key={c} style={{ margin: "12px 0" }}>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13 }}>
                  <span>{c}</span><span style={{ color: "var(--muted)" }}>{fmtCr(atRisk)} / {fmtCr(total)} ({pct}%)</span>
                </div>
                <div className="score-bar" style={{ height: 10, marginTop: 6 }}>
                  <span style={{ width: `${pct}%`, background: pct >= 60 ? "#ef4444" : pct >= 35 ? "#f59e0b" : "#22c55e" }} />
                </div>
              </div>
            );
          })}
          <div style={{ color: "var(--muted)", fontSize: 12, marginTop: 14 }}>
            "At risk" = suppliers in Amber or Red zone. Source: live risk scores.
          </div>
        </div>
      </div>

      <div className="card" style={{ marginTop: 16 }}>
        <h3>Business case (from CEO briefing)</h3>
        <div className="grid grid-3">
          <div><div style={{ color: "var(--muted)", fontSize: 12 }}>YEAR-1 BUILD</div><div style={{ fontSize: 22, fontWeight: 700 }}>₹50 lakh</div></div>
          <div><div style={{ color: "var(--muted)", fontSize: 12 }}>ANNUAL SAVINGS (REALISTIC)</div><div style={{ fontSize: 22, fontWeight: 700, color: "#b6f5c8" }}>₹8 Cr</div></div>
          <div><div style={{ color: "var(--muted)", fontSize: 12 }}>PAYBACK</div><div style={{ fontSize: 22, fontWeight: 700 }}>&lt; 4 months</div></div>
        </div>
      </div>
    </div>
  );
}

function About() {
  return (
    <div className="fade-in">
      <div className="card">
        <h3>About this system</h3>
        <p>This dashboard is a working demonstration of the <strong>AI-Powered Supplier Risk Early Warning System</strong> proposed
          for PepsiCo India's packaging and flavor supply base. It continuously reads news, regulatory filings, court records and
          financial data about top suppliers and flags signs of distress 3–9 months before they hurt production.</p>
        <h3 style={{ marginTop: 16 }}>How it works</h3>
        <ol style={{ paddingLeft: 18, lineHeight: 1.7 }}>
          <li><strong>Read everything.</strong> Daily scan of newspapers, BSE/NSE filings, credit rating reports, court orders, GST and FSSAI notices, satellite imagery.</li>
          <li><strong>Understand it.</strong> Specialized language models classify which signals concern each supplier and what risk they imply.</li>
          <li><strong>Score the risk.</strong> Each supplier gets a daily 0–100 score broken into financial, operational, regulatory, promoter, cyber and ESG dimensions.</li>
          <li><strong>Alert the right people.</strong> Buyers get a daily digest; Red signals trigger immediate escalations with recommended actions.</li>
        </ol>
        <h3 style={{ marginTop: 16 }}>Coverage targets</h3>
        <ul style={{ paddingLeft: 18, lineHeight: 1.7 }}>
          <li>250+ suppliers across packaging, flavors and ingredients</li>
          <li>3–9 month lead time on supplier distress events</li>
          <li>70–80% of disruptions caught early (vs ~20% today)</li>
        </ul>
        <div className="footer-note">Built as a demonstration of the CEO briefing proposal. Mock data only.</div>
      </div>
    </div>
  );
}

/* ---------- Shell ---------- */

const PAGES = [
  { id: "overview",  label: "Overview" },
  { id: "suppliers", label: "Suppliers" },
  { id: "alerts",    label: "Alerts" },
  { id: "analytics", label: "Analytics" },
  { id: "about",     label: "About" }
];

function App() {
  const [page, setPage] = useState("overview");
  const [detailId, setDetailId] = useState(null);
  const [query, setQuery] = useState("");

  function go(p, id) {
    if (p === "supplier") { setDetailId(id); setPage("supplier"); }
    else { setPage(p); setDetailId(null); }
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  const titleMap = {
    overview:  { t: "Operations Overview", s: "Live view of the supplier risk landscape — refreshed daily." },
    suppliers: { t: "Supplier Directory",  s: "Filter and drill into any monitored supplier." },
    supplier:  { t: "Supplier Detail",     s: "Signals, score breakdown and recommended actions." },
    alerts:    { t: "Alerts & Signals",    s: "Every signal detected across the supplier base." },
    analytics: { t: "Analytics",           s: "Trends, spend at risk and business-case metrics." },
    about:     { t: "About",               s: "How the early-warning system works." }
  };
  const cur = titleMap[page] || titleMap.overview;

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-logo">SR</div>
          <div>
            <div className="brand-title">Supplier Risk AI</div>
            <div className="brand-sub">PepsiCo India · Procurement</div>
          </div>
        </div>
        <div className="nav-section-label">Workspace</div>
        <nav>
          {PAGES.map(p => (
            <div key={p.id}
              className={`nav-item ${page === p.id || (p.id === "suppliers" && page === "supplier") ? "active" : ""}`}
              onClick={() => go(p.id)}>
              <span className="dot" />
              <span>{p.label}</span>
            </div>
          ))}
        </nav>
      </aside>

      <main className="main">
        <div className="topbar">
          <div>
            <h1 className="page-title">{cur.t}</h1>
            <div className="page-sub">{cur.s}</div>
          </div>
          <div className="topbar-actions">
            {page === "suppliers" && (
              <input className="search" placeholder="Search supplier, SKU…"
                value={query} onChange={e => setQuery(e.target.value)} />
            )}
            <button className="btn">Export</button>
            <button className="btn btn-primary">+ Add supplier</button>
          </div>
        </div>

        {page === "overview"  && <Overview go={go} />}
        {page === "suppliers" && <SupplierList go={go} query={query} setQuery={setQuery} />}
        {page === "supplier"  && <SupplierDetail id={detailId} go={go} />}
        {page === "alerts"    && <Alerts go={go} />}
        {page === "analytics" && <Analytics />}
        {page === "about"     && <About />}

        <div className="footer-note">Demonstration build · mock data · last refresh {new Date().toISOString().slice(0,10)}</div>
      </main>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<App />);
