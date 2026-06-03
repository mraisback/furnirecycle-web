// Mock supplier data for PepsiCo India Supplier Risk Early Warning System
// In production this would be replenished daily by the ingestion + scoring pipeline.

window.SUPPLIERS = [
  {
    id: "uflex",
    name: "Uflex Ltd",
    category: "Packaging",
    sub: "Metallized Films",
    spendCr: 410,
    skus: ["Lay's", "Kurkure", "Doritos"],
    score: 78,
    delta: +9,
    trend: [42, 48, 51, 55, 62, 69, 78],
    contact: "Rajiv Mehra (Category Buyer)",
    lastIncident: "2026-05-22",
    signals: [
      { type: "Financial", severity: "HIGH", text: "ICRA revised long-term outlook to Negative citing tightening interest cover.", source: "ICRA Rationale, 22 May 2026", date: "2026-05-22" },
      { type: "Promoter", severity: "HIGH", text: "Promoter pledged additional 12% of shares (cumulative 47%).", source: "BSE Disclosure, 14 May 2026", date: "2026-05-14" },
      { type: "Operational", severity: "MEDIUM", text: "Minor fire reported at Noida Unit-3 secondary line; production unaffected.", source: "Times of India regional ed., 02 May 2026", date: "2026-05-02" }
    ],
    recommendation: "Accelerate qualification of Backup Supplier (Cosmo First). Build 30-day buffer for Lay's metallized film SKUs."
  },
  {
    id: "huhtamaki",
    name: "Huhtamaki India Ltd",
    category: "Packaging",
    sub: "Flexible Laminates",
    spendCr: 280,
    skus: ["Pepsi Tetra", "Tropicana"],
    score: 34,
    delta: -2,
    trend: [38, 40, 39, 37, 36, 35, 34],
    contact: "Anita Rao",
    lastIncident: "2026-04-10",
    signals: [
      { type: "Market", severity: "LOW", text: "Q1 revenue down 3% YoY — within guided band.", source: "Q1 Results filing", date: "2026-04-30" },
      { type: "ESG", severity: "LOW", text: "Pollution control board issued advisory at Thane unit; remediation submitted.", source: "MPCB notice, 10 Apr 2026", date: "2026-04-10" }
    ],
    recommendation: "Maintain monitoring. No action required."
  },
  {
    id: "manjushree",
    name: "Manjushree Technopack",
    category: "Packaging",
    sub: "PET Bottles",
    spendCr: 215,
    skus: ["Pepsi", "Mountain Dew", "7UP"],
    score: 52,
    delta: +14,
    trend: [22, 25, 28, 33, 41, 47, 52],
    contact: "Vikram Suri",
    lastIncident: "2026-05-28",
    signals: [
      { type: "Operational", severity: "HIGH", text: "Labor unrest at Bidadi plant — 2-day token strike.", source: "Deccan Herald, 28 May 2026", date: "2026-05-28" },
      { type: "Financial", severity: "MEDIUM", text: "EBITDA margin contracted 180bps QoQ due to resin price spike.", source: "Investor Call Transcript", date: "2026-05-12" }
    ],
    recommendation: "Engage account manager; request contingency plan for Bidadi line. Pre-qualify alternate (Pearl Polymers) for South region."
  },
  {
    id: "givaudan",
    name: "Givaudan India",
    category: "Flavor",
    sub: "Hero SKU Flavors",
    spendCr: 195,
    skus: ["Lay's Magic Masala", "Kurkure Masala Munch"],
    score: 18,
    delta: -1,
    trend: [22, 21, 20, 19, 19, 18, 18],
    contact: "Priya Nair",
    lastIncident: "—",
    signals: [
      { type: "Regulatory", severity: "LOW", text: "FSSAI routine inspection cleared with no observations.", source: "FSSAI portal", date: "2026-04-18" }
    ],
    recommendation: "Healthy. Continue quarterly business reviews."
  },
  {
    id: "symrise",
    name: "Symrise India",
    category: "Flavor",
    sub: "Beverage Flavors",
    spendCr: 160,
    skus: ["Pepsi", "Mirinda"],
    score: 27,
    delta: +3,
    trend: [21, 22, 23, 24, 25, 26, 27],
    contact: "Suresh Kumar",
    lastIncident: "—",
    signals: [
      { type: "Market", severity: "LOW", text: "Lost mid-sized FMCG account in South India per industry chatter.", source: "FoodNavigator-Asia, 20 May 2026", date: "2026-05-20" }
    ],
    recommendation: "Monitor revenue concentration; no immediate action."
  },
  {
    id: "iff",
    name: "International Flavors & Fragrances (IFF)",
    category: "Flavor",
    sub: "Snack Flavors",
    spendCr: 140,
    skus: ["Doritos", "Cheetos"],
    score: 41,
    delta: +6,
    trend: [30, 32, 34, 35, 37, 39, 41],
    contact: "Megha Iyer",
    lastIncident: "2026-05-05",
    signals: [
      { type: "Cyber", severity: "MEDIUM", text: "Parent disclosed ransomware incident affecting EU ops; India unaffected.", source: "8-K filing, 05 May 2026", date: "2026-05-05" },
      { type: "Financial", severity: "LOW", text: "Goldman downgraded to Neutral on margin concerns.", source: "Equity research note", date: "2026-05-09" }
    ],
    recommendation: "Confirm with India team that ERP / order-management systems are segregated from EU incident scope."
  },
  {
    id: "cosmo",
    name: "Cosmo First Ltd",
    category: "Packaging",
    sub: "BOPP Films",
    spendCr: 95,
    skus: ["Lay's", "Doritos"],
    score: 22,
    delta: 0,
    trend: [23, 22, 22, 22, 22, 22, 22],
    contact: "Rajiv Mehra",
    lastIncident: "—",
    signals: [
      { type: "Financial", severity: "LOW", text: "Stable BBB+ rating reaffirmed by CRISIL.", source: "CRISIL Rationale", date: "2026-03-30" }
    ],
    recommendation: "Strong backup candidate for Uflex contingency."
  },
  {
    id: "ester",
    name: "Ester Industries",
    category: "Packaging",
    sub: "Polyester Films",
    spendCr: 70,
    skus: ["Kurkure"],
    score: 46,
    delta: +5,
    trend: [38, 39, 41, 42, 44, 45, 46],
    contact: "Anita Rao",
    lastIncident: "2026-05-01",
    signals: [
      { type: "Regulatory", severity: "MEDIUM", text: "Listed in GST defaulter watch-list for late return filing (one quarter).", source: "GSTN portal", date: "2026-05-01" }
    ],
    recommendation: "Buyer to seek written assurance of corrective filing; re-score in 30 days."
  },
  {
    id: "polyplex",
    name: "Polyplex Corporation",
    category: "Packaging",
    sub: "PET Films",
    spendCr: 85,
    skus: ["Lay's", "Cheetos"],
    score: 29,
    delta: +1,
    trend: [27, 28, 28, 28, 29, 29, 29],
    contact: "Vikram Suri",
    lastIncident: "—",
    signals: [
      { type: "Market", severity: "LOW", text: "Capacity expansion at Bazpur commissioned on schedule.", source: "Company press release", date: "2026-04-22" }
    ],
    recommendation: "Healthy and expanding. Consider for share-of-wallet increase."
  },
  {
    id: "jindal",
    name: "Jindal Poly Films",
    category: "Packaging",
    sub: "BOPET / BOPP",
    spendCr: 110,
    skus: ["Lay's", "Kurkure"],
    score: 38,
    delta: -3,
    trend: [44, 43, 42, 41, 40, 39, 38],
    contact: "Rajiv Mehra",
    lastIncident: "2026-02-14",
    signals: [
      { type: "Operational", severity: "LOW", text: "Power outage at Nashik plant — 6 hours, restored same day.", source: "Internal supplier note", date: "2026-02-14" }
    ],
    recommendation: "Improving trend; continue standard monitoring."
  },
  {
    id: "ttkpb",
    name: "TCPL Packaging",
    category: "Packaging",
    sub: "Folding Cartons",
    spendCr: 60,
    skus: ["Quaker Oats"],
    score: 25,
    delta: 0,
    trend: [25, 25, 25, 25, 25, 25, 25],
    contact: "Priya Nair",
    lastIncident: "—",
    signals: [],
    recommendation: "Stable."
  },
  {
    id: "essel",
    name: "Essel Propack",
    category: "Packaging",
    sub: "Laminated Tubes",
    spendCr: 45,
    skus: ["Tropicana Squeeze"],
    score: 31,
    delta: +2,
    trend: [27, 28, 29, 30, 30, 31, 31],
    contact: "Suresh Kumar",
    lastIncident: "—",
    signals: [{ type: "ESG", severity: "LOW", text: "Published 2026 sustainability report — on track for recycled content target.", source: "Company website", date: "2026-04-01" }],
    recommendation: "Healthy."
  },
  {
    id: "firmenich",
    name: "Firmenich India",
    category: "Flavor",
    sub: "Beverage Concentrates",
    spendCr: 90,
    skus: ["Mountain Dew", "Slice"],
    score: 23,
    delta: -1,
    trend: [25, 24, 24, 24, 23, 23, 23],
    contact: "Megha Iyer",
    lastIncident: "—",
    signals: [],
    recommendation: "Healthy."
  },
  {
    id: "sensient",
    name: "Sensient Technologies India",
    category: "Flavor",
    sub: "Colors & Flavors",
    spendCr: 55,
    skus: ["Cheetos", "Doritos"],
    score: 36,
    delta: +4,
    trend: [28, 30, 32, 33, 34, 35, 36],
    contact: "Priya Nair",
    lastIncident: "2026-05-18",
    signals: [{ type: "Regulatory", severity: "MEDIUM", text: "FSSAI sought clarification on a colorant additive used in export SKUs (not India portfolio).", source: "FSSAI notice", date: "2026-05-18" }],
    recommendation: "Confirm India portfolio scope is unaffected."
  },
  {
    id: "kraljic",
    name: "Mold-Tek Packaging",
    category: "Packaging",
    sub: "Rigid Plastic Containers",
    spendCr: 38,
    skus: ["Quaker"],
    score: 19,
    delta: 0,
    trend: [19, 19, 19, 19, 19, 19, 19],
    contact: "Anita Rao",
    lastIncident: "—",
    signals: [],
    recommendation: "Healthy."
  },
  {
    id: "swastik",
    name: "Swastik Polyfilms",
    category: "Packaging",
    sub: "PE Films",
    spendCr: 28,
    skus: ["Kurkure", "Lay's"],
    score: 67,
    delta: +18,
    trend: [30, 35, 41, 48, 55, 62, 67],
    contact: "Rajiv Mehra",
    lastIncident: "2026-05-30",
    signals: [
      { type: "Insolvency", severity: "CRITICAL", text: "Operational creditor filed Section 9 IBC petition at NCLT Mumbai.", source: "IBBI public records", date: "2026-05-30" },
      { type: "Financial", severity: "HIGH", text: "Auditor flagged going concern in FY26 annual report.", source: "MCA filing", date: "2026-05-15" }
    ],
    recommendation: "URGENT: Move active POs to alternate suppliers within 14 days. Escalate to CPO. Stop new orders pending IBC outcome."
  }
];

// Aggregate stats derived from the supplier list — used on Overview screen.
window.computeStats = function () {
  const all = window.SUPPLIERS;
  const z = s => (window.zoneOf ? window.zoneOf(s.score) : (s.score >= 60 ? "red" : s.score >= 35 ? "amber" : "green"));
  const red = all.filter(s => z(s) === "red").length;
  const amber = all.filter(s => z(s) === "amber").length;
  const green = all.length - red - amber;
  const totalSpend = all.reduce((a, s) => a + s.spendCr, 0);
  const atRiskSpend = all.filter(s => z(s) !== "green").reduce((a, s) => a + s.spendCr, 0);
  return { red, amber, green, total: all.length, totalSpend, atRiskSpend };
};

// ---------------------------------------------------------------------------
// Enrichment: add region / tier / backup-supplier metadata + a longer monthly
// risk history derived from the short trend. Done programmatically so the core
// records above stay readable.
// ---------------------------------------------------------------------------
(function enrich() {
  const REGIONS = ["North", "West", "South", "East"];
  const MONTHS = ["Dec", "Jan", "Feb", "Mar", "Apr", "May", "Jun"];
  const BACKUPS = {
    uflex: ["cosmo", "jindal"],
    huhtamaki: ["ester"],
    manjushree: ["polyplex"],
    swastik: ["jindal", "polyplex"],
    givaudan: ["symrise", "iff"],
    iff: ["givaudan", "sensient"],
    symrise: ["firmenich"]
  };
  window.SUPPLIERS.forEach((s, i) => {
    s.region = s.region || REGIONS[i % REGIONS.length];
    s.tier = s.spendCr >= 150 ? 1 : s.spendCr >= 70 ? 2 : 3;
    s.backups = BACKUPS[s.id] || [];
    // Map the 7-point trend onto labelled monthly history for charts.
    s.history = (s.trend || []).map((v, idx) => ({
      label: MONTHS[idx] || `M${idx + 1}`,
      value: v
    }));
    // Keep an immutable baseline so "live mode" can drift without losing truth.
    s._baseScore = s.score;
  });
})();

// Risk zone helpers shared by data + UI. Thresholds are overridable so the
// Settings page can re-tune Amber/Red bands at runtime.
window.RISK_THRESHOLDS = { amber: 35, red: 60 };
window.zoneOf = function (score, t) {
  t = t || window.RISK_THRESHOLDS;
  if (score >= t.red) return "red";
  if (score >= t.amber) return "amber";
  return "green";
};

// Portfolio risk over time = spend-weighted average of every supplier's monthly
// history. Drives the headline trend chart on the Overview/Analytics pages.
window.computePortfolioHistory = function () {
  const all = window.SUPPLIERS;
  const len = Math.max(...all.map(s => (s.history || []).length), 0);
  const totalSpend = all.reduce((a, s) => a + s.spendCr, 0) || 1;
  const out = [];
  for (let i = 0; i < len; i++) {
    let acc = 0, label = "";
    all.forEach(s => {
      const pt = (s.history || [])[i];
      if (pt) { acc += pt.value * s.spendCr; label = pt.label; }
    });
    out.push({ label, value: Math.round(acc / totalSpend) });
  }
  return out;
};

// Alert feed = signals across all suppliers, sorted by date desc + severity weight.
window.computeAlerts = function () {
  const sevWeight = { CRITICAL: 4, HIGH: 3, MEDIUM: 2, LOW: 1 };
  const out = [];
  window.SUPPLIERS.forEach(s => {
    (s.signals || []).forEach(sig => {
      out.push({ ...sig, supplierId: s.id, supplierName: s.name, score: s.score });
    });
  });
  out.sort((a, b) => {
    if (a.date !== b.date) return a.date < b.date ? 1 : -1;
    return sevWeight[b.severity] - sevWeight[a.severity];
  });
  return out;
};
