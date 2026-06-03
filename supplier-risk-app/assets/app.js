/* ============================================================
   Supplier Risk AI — single-file React app (no build step)
   Routing: hash-based (#/overview, #/supplier/<id>, ...)
   Robustness: ErrorBoundary, safe data guards, localStorage state
   ============================================================ */

const { useState, useMemo, useEffect, useRef, useCallback, createContext, useContext } = React;

/* ---------- utils ---------- */

const zoneOf = (score, t) => window.zoneOf(score, t);
const zoneLabel = z => ({ green: "Green", amber: "Amber", red: "Red" }[z]);
const zoneColor = z => ({ green: "var(--green)", amber: "var(--amber)", red: "var(--red)" }[z]);
const fmtCr = n => "₹" + Number(n || 0).toLocaleString("en-IN") + " Cr";

function ls(key, fallback) {
  try { const v = localStorage.getItem("srisk." + key); return v == null ? fallback : JSON.parse(v); }
  catch { return fallback; }
}
function setLs(key, val) {
  try { localStorage.setItem("srisk." + key, JSON.stringify(val)); } catch {}
}
function useLocalStorage(key, fallback) {
  const [v, setV] = useState(() => ls(key, fallback));
  useEffect(() => setLs(key, v), [key, v]);
  return [v, setV];
}

function downloadCSV(rows, filename) {
  const esc = v => `"${String(v ?? "").replace(/"/g, '""')}"`;
  const csv = rows.map(r => r.map(esc).join(",")).join("\n");
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = filename; a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/* ---------- app-wide context (toasts, watchlist, settings, live) ---------- */

const AppCtx = createContext(null);
const useApp = () => useContext(AppCtx);

/* ---------- error boundary ---------- */

class ErrorBoundary extends React.Component {
  constructor(p) { super(p); this.state = { err: null }; }
  static getDerivedStateFromError(err) { return { err }; }
  componentDidCatch(err, info) { console.error("App error:", err, info); }
  render() {
    if (this.state.err) {
      return (
        <div style={{ padding: 40, maxWidth: 560, margin: "60px auto" }}>
          <div className="card">
            <h3 style={{ color: "var(--red)" }}>Something went wrong</h3>
            <p style={{ color: "var(--muted)" }}>The view hit an unexpected error. Your data is safe.</p>
            <pre style={{ fontSize: 12, color: "var(--muted)", whiteSpace: "pre-wrap", overflow: "auto" }}>
              {String(this.state.err && this.state.err.message || this.state.err)}
            </pre>
            <button className="btn btn-primary" onClick={() => { this.setState({ err: null }); location.hash = "#/overview"; }}>
              Back to Overview
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

/* ---------- hash routing ---------- */

function parseHash() {
  const h = (location.hash || "#/overview").replace(/^#\/?/, "");
  const [page = "overview", arg] = h.split("/");
  return { page, arg };
}
function useRoute() {
  const [route, setRoute] = useState(parseHash);
  useEffect(() => {
    const on = () => setRoute(parseHash());
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);
  const go = useCallback((page, arg) => {
    location.hash = arg ? `#/${page}/${arg}` : `#/${page}`;
    window.scrollTo({ top: 0, behavior: "smooth" });
  }, []);
  return [route, go];
}

/* ---------- visual primitives ---------- */

function Sparkline({ data, color = "var(--accent)" }) {
  const vals = (data || []).map(d => (typeof d === "object" ? d.value : d));
  if (!vals.length) return null;
  const w = 120, h = 36, pad = 3;
  const min = Math.min(...vals), max = Math.max(...vals), range = max - min || 1;
  const step = (w - pad * 2) / (vals.length - 1 || 1);
  const xy = vals.map((v, i) => [pad + i * step, h - pad - ((v - min) / range) * (h - pad * 2)]);
  const line = xy.map(p => p.join(",")).join(" ");
  const area = `${pad},${h} ${line} ${w - pad},${h}`;
  const id = "g" + Math.random().toString(36).slice(2, 7);
  return (
    <svg className="sparkline" viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none" aria-hidden="true">
      <defs><linearGradient id={id} x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stopColor={color} stopOpacity="0.28" /><stop offset="100%" stopColor={color} stopOpacity="0" />
      </linearGradient></defs>
      <polygon points={area} fill={`url(#${id})`} />
      <polyline fill="none" stroke={color} strokeWidth="1.8" points={line} strokeLinejoin="round" strokeLinecap="round" />
      <circle cx={xy[xy.length - 1][0]} cy={xy[xy.length - 1][1]} r="2.4" fill={color} />
    </svg>
  );
}

function Donut({ green, amber, red }) {
  const total = green + amber + red || 1;
  const r = 44, c = 2 * Math.PI * r;
  const segs = [{ v: green, color: "var(--green)" }, { v: amber, color: "var(--amber)" }, { v: red, color: "var(--red)" }];
  let offset = 0;
  return (
    <svg className="donut" viewBox="0 0 120 120" role="img" aria-label={`${green} green, ${amber} amber, ${red} red`}>
      <circle cx="60" cy="60" r={r} fill="none" stroke="var(--panel-3)" strokeWidth="14" />
      {segs.map((s, i) => {
        const len = (s.v / total) * c;
        const el = <circle key={i} cx="60" cy="60" r={r} fill="none" stroke={s.color} strokeWidth="14"
          strokeDasharray={`${len} ${c - len}`} strokeDashoffset={-offset} transform="rotate(-90 60 60)"
          style={{ transition: "stroke-dasharray .6s ease, stroke-dashoffset .6s ease" }} />;
        offset += len; return el;
      })}
      <text x="60" y="56" textAnchor="middle" fill="var(--text-strong)" fontSize="20" fontWeight="800">{total}</text>
      <text x="60" y="73" textAnchor="middle" fill="var(--muted)" fontSize="10.5">suppliers</text>
    </svg>
  );
}

function LineChart({ data, color = "var(--accent)", thresholds }) {
  const pts = (data || []).map(d => d.value);
  if (pts.length < 2) return <div className="empty">Not enough data.</div>;
  const w = 600, h = 200, padL = 30, padB = 26, padT = 14, padR = 12;
  const min = 0, max = 100;
  const sx = i => padL + (i * (w - padL - padR)) / (pts.length - 1);
  const sy = v => padT + (1 - (v - min) / (max - min)) * (h - padT - padB);
  const line = pts.map((v, i) => `${sx(i)},${sy(v)}`).join(" ");
  const area = `${sx(0)},${h - padB} ${line} ${sx(pts.length - 1)},${h - padB}`;
  return (
    <svg className="line-chart" viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="xMidYMid meet" role="img" aria-label="Portfolio risk trend">
      <defs><linearGradient id="lcg" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stopColor={color} stopOpacity="0.30" /><stop offset="100%" stopColor={color} stopOpacity="0" />
      </linearGradient></defs>
      {thresholds && [thresholds.amber, thresholds.red].map((t, i) => (
        <line key={i} x1={padL} x2={w - padR} y1={sy(t)} y2={sy(t)} stroke={i ? "var(--red)" : "var(--amber)"} strokeOpacity="0.35" strokeDasharray="4 4" />
      ))}
      {[0, 25, 50, 75, 100].map(g => (
        <text key={g} x={padL - 6} y={sy(g) + 3} textAnchor="end" fill="var(--muted-2)" fontSize="9">{g}</text>
      ))}
      <polygon points={area} fill="url(#lcg)" />
      <polyline fill="none" stroke={color} strokeWidth="2.4" points={line} strokeLinejoin="round" strokeLinecap="round" />
      {pts.map((v, i) => <circle key={i} cx={sx(i)} cy={sy(v)} r="3" fill={color} />)}
      {data.map((d, i) => (
        <text key={i} x={sx(i)} y={h - 8} textAnchor="middle" fill="var(--muted)" fontSize="10">{d.label}</text>
      ))}
    </svg>
  );
}

function ScoreBar({ score }) {
  const z = zoneOf(score);
  return <div className="score-bar" title={`Risk score ${score}`} role="img" aria-label={`Risk score ${score}`}>
    <span style={{ width: `${score}%`, background: zoneColor(z) }} />
  </div>;
}

function Pill({ score }) {
  const z = zoneOf(score);
  return <span className={`pill ${z}`}><span className="dot" style={{ background: zoneColor(z) }} />{zoneLabel(z)} · {score}</span>;
}

function DeltaTag({ delta }) {
  if (!delta) return <span className="kpi-delta neutral">±0</span>;
  const up = delta > 0;
  return <span className={`kpi-delta ${up ? "up" : "down"}`}>{up ? "▲" : "▼"} {Math.abs(delta)}</span>;
}

function Star({ id }) {
  const { watchlist, toggleWatch } = useApp();
  const on = watchlist.includes(id);
  return <span className={`star ${on ? "on" : ""}`} title={on ? "Remove from watchlist" : "Add to watchlist"}
    role="button" aria-pressed={on}
    onClick={e => { e.stopPropagation(); toggleWatch(id); }}>{on ? "★" : "☆"}</span>;
}

/* ---------- pages ---------- */

function Overview({ go }) {
  const stats = window.computeStats();
  const alerts = window.computeAlerts().slice(0, 6);
  const topRisk = [...window.SUPPLIERS].sort((a, b) => b.score - a.score).slice(0, 5);
  const history = window.computePortfolioHistory();
  const portfolioNow = history.length ? history[history.length - 1].value : 0;
  const portfolioPrev = history.length > 1 ? history[history.length - 2].value : portfolioNow;

  return (
    <div className="fade-in">
      <div className="grid grid-4" style={{ marginBottom: 18 }}>
        <div className="card hoverable">
          <h3>Suppliers monitored</h3>
          <div className="kpi-row"><div className="big">{stats.total}</div><span className="kpi-delta neutral">live</span></div>
          <div className="sub">Target: 250+ across packaging, flavors, ingredients</div>
        </div>
        <div className="card hoverable">
          <h3>Annual spend covered</h3>
          <div className="kpi-row"><div className="big">{fmtCr(stats.totalSpend)}</div></div>
          <div className="sub">{fmtCr(stats.atRiskSpend)} in Amber/Red zones</div>
        </div>
        <div className="card hoverable">
          <h3>Portfolio risk index</h3>
          <div className="kpi-row"><div className="big" style={{ color: zoneColor(zoneOf(portfolioNow)) }}>{portfolioNow}</div>
            <DeltaTag delta={portfolioNow - portfolioPrev} /></div>
          <div className="sub">Spend-weighted across all suppliers</div>
        </div>
        <div className="card hoverable">
          <h3>Est. savings YTD</h3>
          <div className="kpi-row"><div className="big" style={{ color: "var(--green)" }}>₹6.2 Cr</div><span className="kpi-delta down">on track</span></div>
          <div className="sub">Avoided expediting + line-stop costs</div>
        </div>
      </div>

      <div className="grid grid-3" style={{ marginBottom: 18 }}>
        <div className="card">
          <h3>Risk zone distribution</h3>
          <div className="donut-wrap">
            <Donut green={stats.green} amber={stats.amber} red={stats.red} />
            <div className="legend" style={{ flex: 1 }}>
              <div className="legend-item"><span className="swatch" style={{ background: "var(--green)" }} /> Green <span className="n">{stats.green}</span></div>
              <div className="legend-item"><span className="swatch" style={{ background: "var(--amber)" }} /> Amber <span className="n">{stats.amber}</span></div>
              <div className="legend-item"><span className="swatch" style={{ background: "var(--red)" }} /> Red <span className="n">{stats.red}</span></div>
            </div>
          </div>
        </div>
        <div className="card" style={{ gridColumn: "span 2" }}>
          <h3>Portfolio risk index — last 7 months</h3>
          <LineChart data={history} thresholds={window.RISK_THRESHOLDS} />
        </div>
      </div>

      <div className="grid grid-2">
        <div className="card">
          <h3>Top 5 highest-risk suppliers</h3>
          <table className="suppliers">
            <thead><tr><th>Supplier</th><th>Score</th><th>Trend</th><th>Δ</th></tr></thead>
            <tbody>
              {topRisk.map(s => (
                <tr key={s.id} onClick={() => go("supplier", s.id)}>
                  <td><strong>{s.name}</strong><div className="sub" style={{ fontSize: 11.5 }}>{s.sub}</div></td>
                  <td><Pill score={s.score} /></td>
                  <td style={{ width: 120 }}><Sparkline data={s.history} color={zoneColor(zoneOf(s.score))} /></td>
                  <td><DeltaTag delta={s.delta} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="card">
          <h3>Recent intelligence feed</h3>
          {alerts.map((a, i) => (
            <div className="signal" key={i}>
              <div className={`signal-icon sev-${a.severity}`}>{a.severity[0]}</div>
              <div style={{ flex: 1 }}>
                <div><strong style={{ cursor: "pointer" }} onClick={() => go("supplier", a.supplierId)}>{a.supplierName}</strong> — {a.text}</div>
                <div className="signal-meta">{a.type} · {a.severity} · {a.date}</div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function SupplierList({ go, query }) {
  const { toast } = useApp();
  const [zone, setZone] = useState("all");
  const [cat, setCat] = useState("all");
  const [sort, setSort] = useState({ key: "score", dir: "desc" });

  const filtered = useMemo(() => {
    let r = window.SUPPLIERS.filter(s => {
      if (zone !== "all" && zoneOf(s.score) !== zone) return false;
      if (cat !== "all" && s.category !== cat) return false;
      if (query && !`${s.name} ${s.sub} ${(s.skus || []).join(" ")} ${s.region}`.toLowerCase().includes(query.toLowerCase())) return false;
      return true;
    });
    const { key, dir } = sort, m = dir === "asc" ? 1 : -1;
    r = [...r].sort((a, b) => {
      const av = a[key], bv = b[key];
      if (typeof av === "string") return av.localeCompare(bv) * m;
      return ((av || 0) - (bv || 0)) * m;
    });
    return r;
  }, [zone, cat, query, sort]);

  const sortBy = key => setSort(s => ({ key, dir: s.key === key && s.dir === "desc" ? "asc" : "desc" }));
  const arrow = key => sort.key === key ? <span className="arrow">{sort.dir === "desc" ? "▼" : "▲"}</span> : null;

  const exportCSV = () => {
    const rows = [["Supplier", "Category", "Sub", "Region", "Tier", "Spend (Cr)", "Score", "Zone", "Delta"]];
    filtered.forEach(s => rows.push([s.name, s.category, s.sub, s.region, s.tier, s.spendCr, s.score, zoneLabel(zoneOf(s.score)), s.delta]));
    downloadCSV(rows, "supplier-risk.csv");
    toast({ title: "Export complete", body: `${filtered.length} suppliers exported to CSV.`, kind: "success" });
  };

  return (
    <div className="fade-in">
      <div className="filters">
        {["all", "red", "amber", "green"].map(z => (
          <span key={z} className={`chip ${zone === z ? "active" : ""}`} onClick={() => setZone(z)} role="button">{z === "all" ? "All zones" : zoneLabel(z)}</span>
        ))}
        <span className="filter-sep" />
        {["all", "Packaging", "Flavor"].map(c => (
          <span key={c} className={`chip ${cat === c ? "active" : ""}`} onClick={() => setCat(c)} role="button">{c === "all" ? "All categories" : c}</span>
        ))}
        <span className="result-count">{filtered.length} of {window.SUPPLIERS.length} suppliers · <a onClick={exportCSV} style={{ cursor: "pointer" }}>Export CSV</a></span>
      </div>

      <div className="card" style={{ padding: 6, overflowX: "auto" }}>
        <table className="suppliers">
          <thead>
            <tr>
              <th style={{ width: 28 }}></th>
              <th className="sortable" onClick={() => sortBy("name")}>Supplier {arrow("name")}</th>
              <th className="sortable" onClick={() => sortBy("category")}>Category {arrow("category")}</th>
              <th className="sortable" onClick={() => sortBy("spendCr")}>Spend {arrow("spendCr")}</th>
              <th>SKUs</th>
              <th className="sortable" onClick={() => sortBy("score")}>Risk score {arrow("score")}</th>
              <th>Trend</th>
              <th className="sortable" onClick={() => sortBy("delta")}>Δ {arrow("delta")}</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map(s => (
              <tr key={s.id} onClick={() => go("supplier", s.id)}>
                <td onClick={e => e.stopPropagation()}><Star id={s.id} /></td>
                <td><strong>{s.name}</strong> <span className="tier-tag">T{s.tier}</span>
                  <div style={{ fontSize: 11.5, color: "var(--muted)" }}>{s.sub} · {s.region}</div></td>
                <td>{s.category}</td>
                <td>{fmtCr(s.spendCr)}</td>
                <td style={{ color: "var(--muted)", fontSize: 12.5 }}>{(s.skus || []).slice(0, 3).join(", ")}</td>
                <td style={{ minWidth: 190 }}><div style={{ display: "flex", alignItems: "center", gap: 10 }}><Pill score={s.score} /><ScoreBar score={s.score} /></div></td>
                <td style={{ width: 120 }}><Sparkline data={s.history} color={zoneColor(zoneOf(s.score))} /></td>
                <td><DeltaTag delta={s.delta} /></td>
              </tr>
            ))}
            {filtered.length === 0 && <tr><td colSpan="8"><div className="empty">No suppliers match the current filters.</div></td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function SupplierDetail({ id, go }) {
  const { toast } = useApp();
  const s = window.SUPPLIERS.find(x => x.id === id);
  if (!s) return <div className="empty">Supplier not found. <a onClick={() => go("suppliers")} style={{ cursor: "pointer" }}>Back to directory</a></div>;
  const z = zoneOf(s.score), col = zoneColor(z);
  const backups = (s.backups || []).map(b => window.SUPPLIERS.find(x => x.id === b)).filter(Boolean);

  return (
    <div className="fade-in">
      <div className="back-link" onClick={() => go("suppliers")}>← Back to suppliers</div>

      <div className="card" style={{ marginBottom: 16 }}>
        <div className="row-between" style={{ flexWrap: "wrap" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <Star id={s.id} />
            <div>
              <div style={{ fontSize: 22, fontWeight: 800, color: "var(--text-strong)" }}>{s.name}</div>
              <div style={{ color: "var(--muted)", fontSize: 13 }}>{s.category} · {s.sub} · {s.region} · Tier {s.tier} · Buyer: {s.contact}</div>
            </div>
          </div>
          <div style={{ display: "flex", gap: 12, alignItems: "center" }}><Pill score={s.score} /><DeltaTag delta={s.delta} /></div>
        </div>
        <div className="grid grid-4" style={{ marginTop: 16 }}>
          <div><div style={{ color: "var(--muted)", fontSize: 11.5 }}>ANNUAL SPEND</div><div style={{ fontSize: 18, fontWeight: 700 }}>{fmtCr(s.spendCr)}</div></div>
          <div><div style={{ color: "var(--muted)", fontSize: 11.5 }}>HERO SKUs</div><div className="tag-row" style={{ marginTop: 4 }}>{(s.skus || []).map(k => <span key={k} className="mini-tag">{k}</span>)}</div></div>
          <div><div style={{ color: "var(--muted)", fontSize: 11.5 }}>LAST INCIDENT</div><div style={{ fontSize: 14 }}>{s.lastIncident || "—"}</div></div>
          <div><div style={{ color: "var(--muted)", fontSize: 11.5 }}>90-DAY TREND</div><Sparkline data={s.history} color={col} /></div>
        </div>
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <h3>Risk score history</h3>
        <LineChart data={s.history} color={col} thresholds={window.RISK_THRESHOLDS} />
      </div>

      <div className="detail-grid">
        <div className="card">
          <h3>Signals detected</h3>
          {(s.signals || []).length ? s.signals.map((sig, i) => (
            <div className="signal" key={i}>
              <div className={`signal-icon sev-${sig.severity}`}>{sig.severity[0]}</div>
              <div style={{ flex: 1 }}>
                <div>{sig.text}</div>
                <div className="signal-meta">{sig.type} · <strong>{sig.severity}</strong> · {sig.source} · {sig.date}</div>
              </div>
            </div>
          )) : <div className="empty">No signals in the last 90 days.</div>}
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <div className="card">
            <h3>Score breakdown</h3>
            {["Financial", "Operational", "Regulatory", "Promoter", "Cyber", "ESG"].map((cat, i) => {
              const sub = Math.max(0, Math.min(100, Math.round((s.score + (i * 7 - 14)) * (0.55 + (i % 3) * 0.22))));
              return (
                <div key={cat} style={{ display: "flex", alignItems: "center", gap: 10, margin: "9px 0" }}>
                  <div style={{ width: 92, fontSize: 12.5, color: "var(--muted)" }}>{cat}</div>
                  <div style={{ flex: 1 }}><div className="score-bar"><span style={{ width: `${sub}%`, background: zoneColor(zoneOf(sub)) }} /></div></div>
                  <div style={{ width: 26, textAlign: "right", fontSize: 12.5 }}>{sub}</div>
                </div>
              );
            })}
          </div>

          {backups.length > 0 && (
            <div className="card">
              <h3>Qualified backups</h3>
              {backups.map(b => (
                <div key={b.id} className="row-between" style={{ padding: "7px 0", cursor: "pointer" }} onClick={() => go("supplier", b.id)}>
                  <div><strong>{b.name}</strong><div style={{ fontSize: 11.5, color: "var(--muted)" }}>{b.sub}</div></div>
                  <Pill score={b.score} />
                </div>
              ))}
            </div>
          )}

          <div className="card">
            <div className="recommend">
              <div className="recommend-label">Recommended action</div>
              <div>{s.recommendation}</div>
            </div>
            <div style={{ display: "flex", gap: 8, marginTop: 12, flexWrap: "wrap" }}>
              <button className="btn btn-primary" onClick={() => toast({ title: "Task created in Ariba", body: `Contingency task raised for ${s.name}.`, kind: "success" })}>Create task in Ariba</button>
              <button className="btn" onClick={() => toast({ title: "Buyer notified", body: `${s.contact} alerted about ${s.name}.` })}>Notify buyer</button>
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
          <span key={s} className={`chip ${sev === s ? "active" : ""}`} onClick={() => setSev(s)} role="button">{s === "all" ? "All severities" : s}</span>
        ))}
        <span className="result-count">{list.length} signals</span>
      </div>
      <div className="card">
        {list.length === 0 && <div className="empty">No alerts at this severity.</div>}
        {list.map((a, i) => (
          <div className="signal" key={i}>
            <div className={`signal-icon sev-${a.severity}`}>{a.severity[0]}</div>
            <div style={{ flex: 1 }}>
              <div><strong style={{ cursor: "pointer" }} onClick={() => go("supplier", a.supplierId)}>{a.supplierName}</strong> — {a.text}</div>
              <div className="signal-meta">{a.type} · {a.severity} · {a.source} · {a.date}</div>
            </div>
            <Pill score={a.score} />
          </div>
        ))}
      </div>
    </div>
  );
}

function Watchlist({ go }) {
  const { watchlist } = useApp();
  const list = window.SUPPLIERS.filter(s => watchlist.includes(s.id)).sort((a, b) => b.score - a.score);
  return (
    <div className="fade-in">
      {list.length === 0
        ? <div className="empty">Your watchlist is empty. Star suppliers ☆ in the directory to track them here.</div>
        : <div className="card" style={{ padding: 6 }}>
            <table className="suppliers">
              <thead><tr><th style={{ width: 28 }}></th><th>Supplier</th><th>Spend</th><th>Risk score</th><th>Trend</th><th>Δ</th></tr></thead>
              <tbody>
                {list.map(s => (
                  <tr key={s.id} onClick={() => go("supplier", s.id)}>
                    <td onClick={e => e.stopPropagation()}><Star id={s.id} /></td>
                    <td><strong>{s.name}</strong><div style={{ fontSize: 11.5, color: "var(--muted)" }}>{s.sub}</div></td>
                    <td>{fmtCr(s.spendCr)}</td>
                    <td style={{ minWidth: 180 }}><div style={{ display: "flex", gap: 10, alignItems: "center" }}><Pill score={s.score} /><ScoreBar score={s.score} /></div></td>
                    <td style={{ width: 120 }}><Sparkline data={s.history} color={zoneColor(zoneOf(s.score))} /></td>
                    <td><DeltaTag delta={s.delta} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>}
    </div>
  );
}

function Analytics() {
  const all = window.SUPPLIERS;
  const cats = ["Financial", "Operational", "Regulatory", "Promoter", "Cyber", "ESG", "Insolvency", "Market"];
  const counts = cats.map(c => ({ cat: c, n: all.reduce((acc, s) => acc + (s.signals || []).filter(x => x.type === c).length, 0) }));
  const max = Math.max(...counts.map(c => c.n), 1);
  const history = window.computePortfolioHistory();

  return (
    <div className="fade-in">
      <div className="card" style={{ marginBottom: 16 }}>
        <h3>Portfolio risk index — trend</h3>
        <LineChart data={history} thresholds={window.RISK_THRESHOLDS} />
      </div>
      <div className="grid grid-2">
        <div className="card">
          <h3>Signals by category (90d)</h3>
          <div className="bar-chart">
            {counts.map((c, i) => (
              <div className="bar" key={c.cat} style={{ height: `${(c.n / max) * 100}%`, minHeight: c.n ? 14 : 3, animationDelay: `${i * 40}ms` }}>
                <span className="value">{c.n}</span><span className="label">{c.cat}</span>
              </div>
            ))}
          </div>
        </div>
        <div className="card">
          <h3>Spend at risk by category</h3>
          {["Packaging", "Flavor"].map(c => {
            const cat = all.filter(s => s.category === c);
            const total = cat.reduce((a, s) => a + s.spendCr, 0);
            const atRisk = cat.filter(s => zoneOf(s.score) !== "green").reduce((a, s) => a + s.spendCr, 0);
            const pct = total ? Math.round((atRisk / total) * 100) : 0;
            return (
              <div key={c} style={{ margin: "14px 0" }}>
                <div className="row-between" style={{ fontSize: 13 }}><span>{c}</span><span style={{ color: "var(--muted)" }}>{fmtCr(atRisk)} / {fmtCr(total)} ({pct}%)</span></div>
                <div className="score-bar" style={{ height: 10, marginTop: 6 }}><span style={{ width: `${pct}%`, background: zoneColor(zoneOf(pct)) }} /></div>
              </div>
            );
          })}
          <div style={{ color: "var(--muted)", fontSize: 12, marginTop: 16 }}>"At risk" = suppliers in Amber or Red zone.</div>
        </div>
      </div>
      <div className="card" style={{ marginTop: 16 }}>
        <h3>Business case (from CEO briefing)</h3>
        <div className="grid grid-3">
          <div><div style={{ color: "var(--muted)", fontSize: 11.5 }}>YEAR-1 BUILD</div><div className="big">₹50 lakh</div></div>
          <div><div style={{ color: "var(--muted)", fontSize: 11.5 }}>ANNUAL SAVINGS (REALISTIC)</div><div className="big" style={{ color: "var(--green)" }}>₹8 Cr</div></div>
          <div><div style={{ color: "var(--muted)", fontSize: 11.5 }}>PAYBACK</div><div className="big">&lt; 4 mo</div></div>
        </div>
      </div>
    </div>
  );
}

function Settings() {
  const { settings, setSettings, toast, watchlist, setWatchlist } = useApp();
  const [amber, setAmber] = useState(window.RISK_THRESHOLDS.amber);
  const [red, setRed] = useState(window.RISK_THRESHOLDS.red);

  const save = () => {
    const a = Math.max(1, Math.min(99, Number(amber)));
    const r = Math.max(a + 1, Math.min(100, Number(red)));
    window.RISK_THRESHOLDS = { amber: a, red: r };
    setRed(r); setAmber(a);
    setSettings({ ...settings, thresholds: { amber: a, red: r } });
    toast({ title: "Thresholds updated", body: `Amber ≥ ${a}, Red ≥ ${r}.`, kind: "success" });
  };

  return (
    <div className="fade-in">
      <div className="card" style={{ marginBottom: 16 }}>
        <h3>Risk thresholds</h3>
        <p style={{ color: "var(--muted)", fontSize: 13 }}>Tune the Amber and Red bands used across the dashboard.</p>
        <div style={{ display: "flex", gap: 16, alignItems: "flex-end", flexWrap: "wrap" }}>
          <label>Amber ≥ <input className="search" type="number" min="1" max="99" value={amber} onChange={e => setAmber(e.target.value)} style={{ width: 90 }} /></label>
          <label>Red ≥ <input className="search" type="number" min="2" max="100" value={red} onChange={e => setRed(e.target.value)} style={{ width: 90 }} /></label>
          <button className="btn btn-primary" onClick={save}>Apply</button>
        </div>
      </div>
      <div className="card" style={{ marginBottom: 16 }}>
        <h3>Live mode</h3>
        <div className="row-between">
          <div style={{ color: "var(--muted)", fontSize: 13 }}>Simulate incoming intelligence — scores drift in real time.</div>
          <div className={`switch ${settings.live ? "on" : ""}`} role="switch" aria-checked={settings.live} onClick={() => setSettings({ ...settings, live: !settings.live })} />
        </div>
      </div>
      <div className="card">
        <h3>Data</h3>
        <div className="row-between">
          <div style={{ color: "var(--muted)", fontSize: 13 }}>Clear watchlist ({watchlist.length} suppliers) and reset preferences.</div>
          <button className="btn" onClick={() => { setWatchlist([]); toast({ title: "Watchlist cleared" }); }}>Clear watchlist</button>
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
        <p>A working demonstration of the <strong>AI-Powered Supplier Risk Early Warning System</strong> proposed for PepsiCo India's
          packaging and flavor supply base. It continuously reads news, regulatory filings, court records and financial data about top
          suppliers and flags signs of distress 3–9 months before they hurt production.</p>
        <h3 style={{ marginTop: 16 }}>How it works</h3>
        <ol style={{ paddingLeft: 18, lineHeight: 1.8 }}>
          <li><strong>Read everything.</strong> Daily scan of newspapers, BSE/NSE filings, credit ratings, court orders, GST/FSSAI notices, satellite imagery.</li>
          <li><strong>Understand it.</strong> Specialized language models classify which signals concern each supplier and what risk they imply.</li>
          <li><strong>Score the risk.</strong> Each supplier gets a daily 0–100 score across financial, operational, regulatory, promoter, cyber and ESG dimensions.</li>
          <li><strong>Alert the right people.</strong> Buyers get a daily digest; Red signals trigger immediate escalations with recommended actions.</li>
        </ol>
        <h3 style={{ marginTop: 16 }}>Tips</h3>
        <ul style={{ paddingLeft: 18, lineHeight: 1.8 }}>
          <li>Press <span className="kbd">⌘/Ctrl</span> + <span className="kbd">K</span> to open the command palette.</li>
          <li>Star ☆ suppliers to build a watchlist. Toggle light/dark theme top-right.</li>
          <li>Enable Live mode in Settings to watch scores drift in real time.</li>
        </ul>
        <div className="footer-note">Demonstration build · mock data only.</div>
      </div>
    </div>
  );
}

/* ---------- command palette ---------- */

function CommandPalette({ open, onClose, go }) {
  const [q, setQ] = useState("");
  const [idx, setIdx] = useState(0);
  const inputRef = useRef(null);

  const items = useMemo(() => {
    const nav = [
      { kind: "page", label: "Overview", action: () => go("overview") },
      { kind: "page", label: "Suppliers", action: () => go("suppliers") },
      { kind: "page", label: "Alerts", action: () => go("alerts") },
      { kind: "page", label: "Watchlist", action: () => go("watchlist") },
      { kind: "page", label: "Analytics", action: () => go("analytics") },
      { kind: "page", label: "Settings", action: () => go("settings") },
      { kind: "page", label: "About", action: () => go("about") }
    ];
    const sup = window.SUPPLIERS.map(s => ({ kind: "supplier", label: s.name, sub: s.sub, action: () => go("supplier", s.id) }));
    const all = [...nav, ...sup];
    if (!q) return all;
    const ql = q.toLowerCase();
    return all.filter(i => (i.label + " " + (i.sub || "")).toLowerCase().includes(ql));
  }, [q, go]);

  useEffect(() => { if (open) { setQ(""); setIdx(0); setTimeout(() => inputRef.current && inputRef.current.focus(), 30); } }, [open]);
  useEffect(() => { setIdx(0); }, [q]);

  if (!open) return null;
  const run = i => { const it = items[i]; if (it) { it.action(); onClose(); } };
  const onKey = e => {
    if (e.key === "ArrowDown") { e.preventDefault(); setIdx(i => Math.min(i + 1, items.length - 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setIdx(i => Math.max(i - 1, 0)); }
    else if (e.key === "Enter") { e.preventDefault(); run(idx); }
    else if (e.key === "Escape") { onClose(); }
  };

  return (
    <div className="cmdk-overlay" onClick={onClose}>
      <div className="cmdk" onClick={e => e.stopPropagation()} role="dialog" aria-label="Command palette">
        <input ref={inputRef} value={q} onChange={e => setQ(e.target.value)} onKeyDown={onKey} placeholder="Search suppliers or jump to a page…" aria-label="Search" />
        <div className="cmdk-list">
          {items.length === 0 && <div className="cmdk-empty">No results for "{q}"</div>}
          {items.slice(0, 30).map((it, i) => (
            <div key={i} className={`cmdk-item ${i === idx ? "active" : ""}`} onMouseEnter={() => setIdx(i)} onClick={() => run(i)}>
              <span style={{ opacity: .7 }}>{it.kind === "supplier" ? "◆" : "▸"}</span>
              <span>{it.label}{it.sub && <span style={{ color: "var(--muted)", marginLeft: 8, fontSize: 12 }}>{it.sub}</span>}</span>
              <span className="kind">{it.kind}</span>
            </div>
          ))}
        </div>
        <div className="cmdk-foot"><span>↑↓ navigate</span><span>↵ select</span><span>esc close</span></div>
      </div>
    </div>
  );
}

/* ---------- toasts ---------- */

function ToastHost({ toasts }) {
  return (
    <div className="toast-wrap" aria-live="polite">
      {toasts.map(t => (
        <div key={t.id} className={`toast ${t.kind || ""}`}>
          <div className="t-title">{t.title}</div>
          {t.body && <div className="t-body">{t.body}</div>}
        </div>
      ))}
    </div>
  );
}

/* ---------- shell ---------- */

const NAV = [
  { id: "overview", label: "Overview" },
  { id: "suppliers", label: "Suppliers" },
  { id: "alerts", label: "Alerts" },
  { id: "watchlist", label: "Watchlist" },
  { id: "analytics", label: "Analytics" },
  { id: "settings", label: "Settings" },
  { id: "about", label: "About" }
];

const TITLES = {
  overview: ["Operations Overview", "Live view of the supplier risk landscape — refreshed daily."],
  suppliers: ["Supplier Directory", "Filter, sort and drill into any monitored supplier."],
  supplier: ["Supplier Detail", "Signals, score history and recommended actions."],
  alerts: ["Alerts & Signals", "Every signal detected across the supplier base."],
  watchlist: ["Watchlist", "Suppliers you're actively tracking."],
  analytics: ["Analytics", "Trends, spend at risk and business-case metrics."],
  settings: ["Settings", "Tune thresholds, live mode and preferences."],
  about: ["About", "How the early-warning system works."]
};

function App() {
  const [route, go] = useRoute();
  const [query, setQuery] = useState("");
  const [theme, setTheme] = useLocalStorage("theme", "dark");
  const [watchlist, setWatchlist] = useLocalStorage("watchlist", []);
  const [settings, setSettings] = useLocalStorage("settings", { live: false, thresholds: { amber: 35, red: 60 } });
  const [toasts, setToasts] = useState([]);
  const [cmdkOpen, setCmdkOpen] = useState(false);
  const [, force] = useState(0);

  // apply theme + persisted thresholds
  useEffect(() => { document.documentElement.setAttribute("data-theme", theme); }, [theme]);
  useEffect(() => { if (settings.thresholds) window.RISK_THRESHOLDS = settings.thresholds; }, []); // eslint-disable-line

  const toast = useCallback(t => {
    const id = Date.now() + Math.random();
    setToasts(ts => [...ts, { id, ...t }]);
    setTimeout(() => setToasts(ts => ts.filter(x => x.id !== id)), 3200);
  }, []);
  const toggleWatch = useCallback(id => setWatchlist(w => w.includes(id) ? w.filter(x => x !== id) : [...w, id]), [setWatchlist]);

  // global keyboard: cmd/ctrl+k
  useEffect(() => {
    const on = e => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); setCmdkOpen(o => !o); }
    };
    window.addEventListener("keydown", on);
    return () => window.removeEventListener("keydown", on);
  }, []);

  // live mode: drift scores around their baseline, occasionally notify
  useEffect(() => {
    if (!settings.live) return;
    const t = setInterval(() => {
      window.SUPPLIERS.forEach(s => {
        const drift = Math.round((Math.random() - 0.45) * 4);
        const next = Math.max(0, Math.min(100, s.score + drift));
        s.delta = next - s._baseScore;
        s.score = next;
        if (s.history && s.history.length) s.history[s.history.length - 1].value = next;
      });
      force(n => n + 1);
    }, 2500);
    return () => clearInterval(t);
  }, [settings.live]);

  const stats = window.computeStats();
  const [t, sub] = TITLES[route.page] || TITLES.overview;
  const isSuppliersArea = route.page === "suppliers" || route.page === "supplier";

  return (
    <AppCtx.Provider value={{ toast, watchlist, toggleWatch, setWatchlist, settings, setSettings }}>
      <div className="app">
        <aside className="sidebar">
          <div className="brand">
            <div className="brand-logo">SR</div>
            <div><div className="brand-title">Supplier Risk AI</div><div className="brand-sub">PepsiCo India · Procurement</div></div>
          </div>
          <div className="nav-section-label">Workspace</div>
          <nav>
            {NAV.map(n => (
              <div key={n.id} role="button" tabIndex="0"
                className={`nav-item ${route.page === n.id || (n.id === "suppliers" && route.page === "supplier") ? "active" : ""}`}
                onClick={() => go(n.id)} onKeyDown={e => { if (e.key === "Enter") go(n.id); }}>
                <span>{n.label}</span>
                {n.id === "alerts" && stats.red > 0 && <span className="nav-badge">{stats.red}</span>}
                {n.id === "watchlist" && watchlist.length > 0 && <span className="nav-badge" style={{ background: "var(--panel-3)", color: "var(--muted)" }}>{watchlist.length}</span>}
              </div>
            ))}
          </nav>
          <div className="sidebar-foot">
            <div className="live-toggle" onClick={() => setSettings({ ...settings, live: !settings.live })} role="switch" aria-checked={settings.live}>
              <span className={`live-dot ${settings.live ? "on" : ""}`} /> {settings.live ? "Live" : "Paused"}
            </div>
            <button className="btn btn-icon btn-ghost" title="Toggle theme" aria-label="Toggle theme" onClick={() => setTheme(theme === "dark" ? "light" : "dark")}>
              {theme === "dark" ? "☀" : "☾"}
            </button>
          </div>
        </aside>

        <main className="main">
          <div className="topbar">
            <div><h1 className="page-title">{t}</h1><div className="page-sub">{sub}</div></div>
            <div className="topbar-actions">
              {route.page === "suppliers" && <input className="search" placeholder="Search supplier, SKU…" value={query} onChange={e => setQuery(e.target.value)} aria-label="Search suppliers" />}
              <button className="btn" onClick={() => setCmdkOpen(true)}>Search <span className="kbd">⌘K</span></button>
              <button className="btn btn-primary" onClick={() => toast({ title: "Daily digest sent", body: "Risk summary dispatched to all category buyers.", kind: "success" })}>Send digest</button>
            </div>
          </div>

          <ErrorBoundary>
            {route.page === "overview" && <Overview go={go} />}
            {route.page === "suppliers" && <SupplierList go={go} query={query} />}
            {route.page === "supplier" && <SupplierDetail id={route.arg} go={go} />}
            {route.page === "alerts" && <Alerts go={go} />}
            {route.page === "watchlist" && <Watchlist go={go} />}
            {route.page === "analytics" && <Analytics />}
            {route.page === "settings" && <Settings />}
            {route.page === "about" && <About />}
            {!TITLES[route.page] && <div className="empty">Page not found. <a onClick={() => go("overview")} style={{ cursor: "pointer" }}>Go to Overview</a></div>}
          </ErrorBoundary>

          <div className="footer-note">Demonstration build · mock data · last refresh {new Date().toISOString().slice(0, 10)}</div>
        </main>
      </div>

      <CommandPalette open={cmdkOpen} onClose={() => setCmdkOpen(false)} go={go} />
      <ToastHost toasts={toasts} />
    </AppCtx.Provider>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<ErrorBoundary><App /></ErrorBoundary>);
