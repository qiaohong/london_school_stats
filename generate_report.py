"""
generate_report.py — Build a self-contained report.html from schools.db metrics tables.

Reads metrics_ks4, metrics_ks2, metrics_ks5, metrics_la, metrics_type.
Outputs report.html with all data embedded as JSON (no server required).
"""

import json
import math
import os
import sqlite3

import pandas as pd

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH  = os.path.join(BASE_DIR, "schools.db")
OUT_PATH = os.path.join(BASE_DIR, "report.html")


# ── Load & serialise ──────────────────────────────────────────────────────────

def load(conn, table, cols=None):
    q = f"SELECT {', '.join(cols) if cols else '*'} FROM {table}"
    df = pd.read_sql(q, conn)
    # Replace NaN/inf with None for JSON
    df = df.where(pd.notnull(df), None)
    df = df.replace([float("inf"), float("-inf")], None)
    return df


def df_to_json(df):
    """Return compact JSON list-of-dicts, rounding floats to 2 dp."""
    rows = []
    for row in df.to_dict(orient="records"):
        clean = {}
        for k, v in row.items():
            if v is None:
                clean[k] = None
            elif isinstance(v, float):
                clean[k] = None if math.isnan(v) or math.isinf(v) else round(v, 2)
            elif hasattr(v, "item"):          # numpy scalar
                val = v.item()
                if isinstance(val, float):
                    clean[k] = None if math.isnan(val) or math.isinf(val) else round(val, 2)
                else:
                    clean[k] = val
            else:
                clean[k] = v
        rows.append(clean)
    return json.dumps(rows, separators=(",", ":"))


# ── HTML template ──────────────────────────────────────────────────────────────

HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>London School Performance Report</title>
<style>
/* ── Reset & base ── */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: system-ui, -apple-system, sans-serif; font-size: 14px;
       color: #1a1a1a; background: #f5f5f5; min-height: 100vh; }
a { color: #0066cc; text-decoration: none; }

/* ── Layout ── */
.page { max-width: 1400px; margin: 0 auto; padding: 0 16px 48px; }
header { background: #1a3a5c; color: white; padding: 16px 24px; margin-bottom: 24px; }
header h1 { font-size: 22px; font-weight: 700; }
header p  { font-size: 13px; opacity: 0.8; margin-top: 4px; }

/* ── Tabs ── */
.tabs { display: flex; gap: 4px; margin-bottom: 16px; flex-wrap: wrap; }
.tab  { padding: 8px 20px; border-radius: 6px 6px 0 0; cursor: pointer;
        background: #dde4ec; color: #334; font-weight: 500; border: none;
        font-size: 14px; transition: background 0.15s; }
.tab:hover   { background: #c4d0e0; }
.tab.active  { background: white; color: #1a3a5c; border-bottom: 3px solid #1a3a5c; }

/* ── Panel ── */
.panel { display: none; background: white; border-radius: 0 8px 8px 8px;
         box-shadow: 0 1px 4px rgba(0,0,0,0.08); }
.panel.active { display: block; }
.panel-inner  { padding: 20px; }

/* ── Filter bar ── */
.filters { display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 16px;
           align-items: center; }
.filters input, .filters select {
    padding: 7px 11px; border: 1px solid #c8d0da; border-radius: 6px;
    font-size: 13px; background: #fff; color: #1a1a1a; }
.filters input { width: 240px; }
.filters select { min-width: 160px; }
.filter-count { margin-left: auto; font-size: 12px; color: #777; }

/* ── Table ── */
.tbl-wrap { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
thead th { background: #f0f3f7; font-weight: 600; color: #1a3a5c;
           padding: 8px 10px; white-space: nowrap; position: sticky; top: 0;
           cursor: pointer; user-select: none; border-bottom: 2px solid #c8d0da; }
thead th:hover { background: #dde4ec; }
thead th.sort-asc  { background: #d0dff5; }
thead th.sort-desc { background: #d0dff5; }
thead th .sort-icon { margin-left: 4px; opacity: 0.5; font-size: 11px; }
tbody tr { border-bottom: 1px solid #edf0f5; }
tbody tr:hover { background: #f7f9fc; }
td { padding: 7px 10px; vertical-align: top; }
.school-name { font-weight: 500; }
.borough-cell { color: #555; font-size: 12px; }
.type-cell    { color: #666; font-size: 12px; }

/* ── Score chips ── */
.chip { display: inline-block; padding: 2px 8px; border-radius: 10px;
        font-weight: 600; font-size: 12px; }
.chip-green  { background: #d4edda; color: #1a5c2a; }
.chip-amber  { background: #fff3cd; color: #7a5800; }
.chip-red    { background: #f8d7da; color: #7c1d20; }
.chip-grey   { background: #e9ecef; color: #555; }

/* ── Trend ── */
.trend-up   { color: #228b22; font-weight: 600; }
.trend-down { color: #c0392b; font-weight: 600; }
.trend-flat { color: #888; }
.trend-none { color: #ccc; }

/* ── Metric numbers ── */
.num { text-align: right; }
.na  { color: #bbb; font-style: italic; }

/* ── Borough view ── */
.la-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
           gap: 14px; }
.la-card { background: #f8fafc; border: 1px solid #dde4ec; border-radius: 8px;
           padding: 14px; }
.la-card h3 { font-size: 14px; color: #1a3a5c; margin-bottom: 8px; }
.la-stat { display: flex; justify-content: space-between; padding: 3px 0;
           font-size: 12px; border-bottom: 1px solid #edf0f5; }
.la-stat:last-child { border-bottom: none; }
.la-stat-label { color: #555; }
.la-stat-val   { font-weight: 600; }

/* ── Punching above weight ── */
.paw { font-size: 11px; background: #e8d5f5; color: #5b2d8e;
       padding: 1px 6px; border-radius: 8px; white-space: nowrap; }

/* ── Methodology ── */
.method { margin-top: 32px; border-top: 1px solid #dde4ec; padding-top: 20px; }
.method summary { cursor: pointer; font-weight: 600; color: #1a3a5c; }
.method-body { margin-top: 12px; font-size: 13px; line-height: 1.6; color: #444; }
.method-body h4 { margin: 12px 0 4px; color: #1a3a5c; }
.method-body ul { padding-left: 20px; }

/* ── Data note ── */
.data-note { font-size: 11px; color: #888; margin-top: 8px; }
</style>
</head>
<body>
<header>
  <h1>London School Performance Report</h1>
  <p>Primary (KS2) &bull; Secondary (KS4 GCSE) &bull; Sixth Form (KS5 A-level) &bull; Academic years 2022&ndash;2025</p>
</header>

<div class="page">
  <div class="tabs">
    <button class="tab active" onclick="showTab('ks2')">Primary (KS2)</button>
    <button class="tab" onclick="showTab('ks4')">Secondary (KS4)</button>
    <button class="tab" onclick="showTab('ks5')">Sixth Form (KS5)</button>
    <button class="tab" onclick="showTab('boroughs')">Boroughs</button>
  </div>

  <!-- ── KS2 panel ── -->
  <div id="tab-ks2" class="panel active">
    <div class="panel-inner">
      <div class="filters">
        <input type="text" id="ks2-search" placeholder="Search school name…" oninput="renderKS2()">
        <select id="ks2-borough" onchange="renderKS2()"><option value="">All boroughs</option></select>
        <select id="ks2-type"    onchange="renderKS2()"><option value="">All types</option></select>
        <span class="filter-count" id="ks2-count"></span>
      </div>
      <div class="tbl-wrap">
        <table id="ks2-table">
          <thead>
            <tr>
              <th onclick="sortKS2('SCHNAME')" title="School name">School <span class="sort-icon">⇅</span></th>
              <th onclick="sortKS2('LANAME')" title="Borough">Borough <span class="sort-icon">⇅</span></th>
              <th onclick="sortKS2('MINORGROUP')" title="School type">Type <span class="sort-icon">⇅</span></th>
              <th onclick="sortKS2('total_pupils')" class="num" title="Total pupils assessed">Pupils <span class="sort-icon">⇅</span></th>
              <th onclick="sortKS2('pct_rwm_expected')" class="num" title="% pupils meeting expected standard in reading, writing &amp; maths">RWM% <span class="sort-icon">⇅</span></th>
              <th onclick="sortKS2('pct_rwm_high')" class="num" title="% pupils achieving higher standard in RWM">High% <span class="sort-icon">⇅</span></th>
              <th onclick="sortKS2('avg_progress')" class="num" title="Average progress score across reading, writing &amp; maths (KS1 to KS2)">Progress <span class="sort-icon">⇅</span></th>
              <th onclick="sortKS2('absence_pct')" class="num" title="Overall absence rate (%)">Absence <span class="sort-icon">⇅</span></th>
              <th onclick="sortKS2('pct_fsm')" class="num" title="% pupils eligible for free school meals (disadvantaged proxy)">FSM% <span class="sort-icon">⇅</span></th>
              <th onclick="sortKS2('rwm_trend')" class="num" title="Change in RWM% from earliest to latest available year">Trend <span class="sort-icon">⇅</span></th>
              <th onclick="sortKS2('composite_score')" class="num" title="Composite performance score (0–100 within London)">Score <span class="sort-icon">⇅</span></th>
              <th title="Year of data shown">Year</th>
            </tr>
          </thead>
          <tbody id="ks2-tbody"></tbody>
        </table>
      </div>
      <p class="data-note">Data source: DfE KS2 results 2022–25. Progress scores from 2023-24 and 2024-25 only (DfE suspended KS1 prior attainment comparisons in earlier years).</p>
    </div>
  </div>

  <!-- ── KS4 panel ── -->
  <div id="tab-ks4" class="panel">
    <div class="panel-inner">
      <div class="filters">
        <input type="text" id="ks4-search" placeholder="Search school name…" oninput="renderKS4()">
        <select id="ks4-borough" onchange="renderKS4()"><option value="">All boroughs</option></select>
        <select id="ks4-type"    onchange="renderKS4()"><option value="">All types</option></select>
        <span class="filter-count" id="ks4-count"></span>
      </div>
      <div class="tbl-wrap">
        <table id="ks4-table">
          <thead>
            <tr>
              <th onclick="sortKS4('SCHNAME')" title="School name">School <span class="sort-icon">⇅</span></th>
              <th onclick="sortKS4('LANAME')" title="Borough">Borough <span class="sort-icon">⇅</span></th>
              <th onclick="sortKS4('MINORGROUP')" title="School type">Type <span class="sort-icon">⇅</span></th>
              <th onclick="sortKS4('ks4_cohort')" class="num" title="Number of pupils in KS4 cohort">Cohort <span class="sort-icon">⇅</span></th>
              <th onclick="sortKS4('progress8')" class="num" title="Progress 8 score (school vs expected based on KS2 prior attainment)">P8 <span class="sort-icon">⇅</span></th>
              <th onclick="sortKS4('attainment8')" class="num" title="Attainment 8 average score">Att8 <span class="sort-icon">⇅</span></th>
              <th onclick="sortKS4('pct_grade5_eng_maths')" class="num" title="% pupils achieving grade 5+ in English &amp; Maths">5+EM <span class="sort-icon">⇅</span></th>
              <th onclick="sortKS4('pct_ebacc_4plus')" class="num" title="% pupils entering and achieving EBacc (grade 4+)">EBacc <span class="sort-icon">⇅</span></th>
              <th onclick="sortKS4('dest_pct_education')" class="num" title="% pupils in sustained education 16–18 months after KS4">Dest% <span class="sort-icon">⇅</span></th>
              <th onclick="sortKS4('absence_pct')" class="num" title="Overall absence rate (%)">Absence <span class="sort-icon">⇅</span></th>
              <th onclick="sortKS4('p8_trend')" class="num" title="Change in Progress 8 from earliest to latest year with P8 data">P8 trend <span class="sort-icon">⇅</span></th>
              <th onclick="sortKS4('composite_score')" class="num" title="Composite score: P8 (35%), Grade 5+ E&amp;M (25%), EBacc (10%), absence (15%), destinations (15%)">Score <span class="sort-icon">⇅</span></th>
              <th title="Year of data shown">Year</th>
            </tr>
          </thead>
          <tbody id="ks4-tbody"></tbody>
        </table>
      </div>
      <p class="data-note">Progress 8 may be from an earlier year if 2024–25 provisional data did not include P8. ★ = punching above weight (above-median P8, below-median Att8 — typically serves a higher-need intake).</p>
    </div>
  </div>

  <!-- ── KS5 panel ── -->
  <div id="tab-ks5" class="panel">
    <div class="panel-inner">
      <div class="filters">
        <input type="text" id="ks5-search" placeholder="Search school name…" oninput="renderKS5()">
        <select id="ks5-borough" onchange="renderKS5()"><option value="">All boroughs</option></select>
        <select id="ks5-type"    onchange="renderKS5()"><option value="">All types</option></select>
        <span class="filter-count" id="ks5-count"></span>
      </div>
      <div class="tbl-wrap">
        <table id="ks5-table">
          <thead>
            <tr>
              <th onclick="sortKS5('SCHNAME')" title="School name">School <span class="sort-icon">⇅</span></th>
              <th onclick="sortKS5('LANAME')" title="Borough">Borough <span class="sort-icon">⇅</span></th>
              <th onclick="sortKS5('MINORGROUP')" title="School type">Type <span class="sort-icon">⇅</span></th>
              <th onclick="sortKS5('alevel_cohort')" class="num" title="Number of A-level students">A-lvl N <span class="sort-icon">⇅</span></th>
              <th onclick="sortKS5('alevel_value_added')" class="num" title="A-level value added score (national average = 0)">VA <span class="sort-icon">⇅</span></th>
              <th onclick="sortKS5('pct_aab_facilitating')" class="num" title="% students achieving AAB+ in 2 facilitating A-levels">AAB% <span class="sort-icon">⇅</span></th>
              <th onclick="sortKS5('dest_pct_he')" class="num" title="% students progressing to higher education">HE% <span class="sort-icon">⇅</span></th>
              <th onclick="sortKS5('absence_pct')" class="num" title="Overall absence rate (%)">Absence <span class="sort-icon">⇅</span></th>
              <th onclick="sortKS5('va_trend')" class="num" title="Change in value added score from earliest to latest year">VA trend <span class="sort-icon">⇅</span></th>
              <th onclick="sortKS5('composite_score')" class="num" title="Composite score: VA (40%), AAB% (25%), HE destinations (25%), absence (10%)">Score <span class="sort-icon">⇅</span></th>
              <th title="Year of data shown">Year</th>
            </tr>
          </thead>
          <tbody id="ks5-tbody"></tbody>
        </table>
      </div>
      <p class="data-note">Only school-based sixth forms are shown (FE colleges excluded). Value added score: 0 = national average; positive = better than expected.</p>
    </div>
  </div>

  <!-- ── Boroughs panel ── -->
  <div id="tab-boroughs" class="panel">
    <div class="panel-inner">
      <div class="filters">
        <select id="la-phase" onchange="renderLA()">
          <option value="KS4">Secondary (KS4)</option>
          <option value="KS2">Primary (KS2)</option>
          <option value="KS5">Sixth Form (KS5)</option>
        </select>
        <select id="la-sort" onchange="renderLA()">
          <option value="avg_composite">Sort by composite score</option>
          <option value="borough">Sort by borough name</option>
          <option value="n_schools">Sort by no. of schools</option>
        </select>
      </div>
      <div class="la-grid" id="la-grid"></div>
    </div>
  </div>

  <!-- ── Methodology ── -->
  <details class="method">
    <summary>Methodology &amp; data sources</summary>
    <div class="method-body">
      <h4>Data sources</h4>
      <ul>
        <li>DfE KS2 results (2022–23, 2023–24, 2024–25 revised)</li>
        <li>DfE KS4 results (2022–23, 2023–24 final; 2024–25 revised)</li>
        <li>DfE KS5 results (2022–23, 2023–24 final; 2024–25 revised)</li>
        <li>DfE school census (2022–25), absence statistics (2022–24), pupil destinations (2022–25)</li>
      </ul>
      <h4>Composite score (0–100)</h4>
      <p>Each metric is percentile-ranked within London schools (0 = lowest, 100 = highest).
         Missing values are treated as 50 (London median) — neutral, not penalising.</p>
      <ul>
        <li><b>KS2:</b> RWM expected standard 30%, average progress 40%, absence 15%, RWM higher standard 15%</li>
        <li><b>KS4:</b> Progress 8 35%, grade 5+ Eng&amp;Maths 25%, EBacc 10%, absence 15%, destinations education 15%</li>
        <li><b>KS5:</b> A-level value added 40%, AAB facilitating 25%, HE destinations 25%, absence 10%</li>
      </ul>
      <h4>Caveats</h4>
      <ul>
        <li>Suppressed values (small cohorts) are treated as missing.</li>
        <li>Independent schools are included and ranked alongside state schools.</li>
        <li>Progress 8 for 2024–25 was not yet published at time of data collection; some schools show 2023–24 P8.</li>
        <li>KS2 progress scores use KS1 prior attainment as baseline; DfE paused publication in 2022–23, so progress is shown for 2023–24 and 2024–25 only.</li>
        <li>Destinations data reflects outcomes ~16 months after leaving school; 2024–25 destinations not yet available for all schools.</li>
      </ul>
    </div>
  </details>
</div>

<script>
// ── Embedded data ──────────────────────────────────────────────────────────────
const DATA_KS2 = __DATA_KS2__;
const DATA_KS4 = __DATA_KS4__;
const DATA_KS5 = __DATA_KS5__;
const DATA_LA  = __DATA_LA__;

// ── Helpers ────────────────────────────────────────────────────────────────────
function fmtN(v, dp=1)  { return v == null ? '<span class="na">—</span>' : Number(v).toFixed(dp); }
function fmtPct(v)       { return v == null ? '<span class="na">—</span>' : Number(v).toFixed(1) + '%'; }
function fmtYr(v)        { return v ? String(v).slice(0, 9) : ''; }

function scoreChip(v) {
  if (v == null) return '<span class="na">—</span>';
  const cls = v >= 67 ? 'chip-green' : v >= 34 ? 'chip-amber' : 'chip-red';
  return `<span class="chip ${cls}">${Number(v).toFixed(1)}</span>`;
}

function trendArrow(v, threshold=0.5) {
  if (v == null) return '<span class="trend-none">—</span>';
  if (v > threshold)  return `<span class="trend-up">↑ +${Number(v).toFixed(2)}</span>`;
  if (v < -threshold) return `<span class="trend-down">↓ ${Number(v).toFixed(2)}</span>`;
  return `<span class="trend-flat">→ ${Number(v).toFixed(2)}</span>`;
}

function p8Arrow(v) {
  if (v == null) return '<span class="trend-none">—</span>';
  if (v > 0.05)  return `<span class="trend-up">↑ +${Number(v).toFixed(2)}</span>`;
  if (v < -0.05) return `<span class="trend-down">↓ ${Number(v).toFixed(2)}</span>`;
  return `<span class="trend-flat">→ ${Number(v).toFixed(2)}</span>`;
}

function vaArrow(v) {
  if (v == null) return '<span class="trend-none">—</span>';
  if (v > 0.05)  return `<span class="trend-up">↑ +${Number(v).toFixed(3)}</span>`;
  if (v < -0.05) return `<span class="trend-down">↓ ${Number(v).toFixed(3)}</span>`;
  return `<span class="trend-flat">→ ${Number(v).toFixed(3)}</span>`;
}

function vaScore(v) {
  if (v == null) return '<span class="na">—</span>';
  const n = Number(v);
  const s = (n >= 0 ? '+' : '') + n.toFixed(3);
  const cls = n > 0.1 ? 'trend-up' : n < -0.1 ? 'trend-down' : '';
  return cls ? `<span class="${cls}">${s}</span>` : s;
}

// ── Tab switching ──────────────────────────────────────────────────────────────
function showTab(id) {
  document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.getElementById('tab-' + id).classList.add('active');
  event.target.classList.add('active');
  if (id === 'boroughs') renderLA();
}

// ── Sort state ─────────────────────────────────────────────────────────────────
const sortState = {
  ks2: { col: 'composite_score', asc: false },
  ks4: { col: 'composite_score', asc: false },
  ks5: { col: 'composite_score', asc: false },
};

function makeSort(phase) {
  return function(col) {
    const st = sortState[phase];
    if (st.col === col) st.asc = !st.asc;
    else { st.col = col; st.asc = true; }
    if (phase === 'ks2') renderKS2();
    if (phase === 'ks4') renderKS4();
    if (phase === 'ks5') renderKS5();
  };
}
const sortKS2 = makeSort('ks2');
const sortKS4 = makeSort('ks4');
const sortKS5 = makeSort('ks5');

function sortData(data, col, asc) {
  return [...data].sort((a, b) => {
    let av = a[col], bv = b[col];
    if (av == null && bv == null) return 0;
    if (av == null) return 1;
    if (bv == null) return -1;
    if (typeof av === 'string') av = av.toLowerCase();
    if (typeof bv === 'string') bv = bv.toLowerCase();
    return asc ? (av < bv ? -1 : av > bv ? 1 : 0)
               : (av > bv ? -1 : av < bv ? 1 : 0);
  });
}

// ── Populate filter dropdowns ──────────────────────────────────────────────────
function populateSelects(data, boroughSel, typeSel) {
  const boroughs = [...new Set(data.map(d => d.LANAME).filter(Boolean))].sort();
  const types    = [...new Set(data.map(d => d.MINORGROUP).filter(Boolean))].sort();
  boroughs.forEach(b => { const o = document.createElement('option'); o.value = o.textContent = b; boroughSel.appendChild(o); });
  types.forEach(t => { const o = document.createElement('option'); o.value = o.textContent = t; typeSel.appendChild(o); });
}

// ── KS2 render ─────────────────────────────────────────────────────────────────
function filterKS2() {
  const q  = document.getElementById('ks2-search').value.toLowerCase();
  const la = document.getElementById('ks2-borough').value;
  const ty = document.getElementById('ks2-type').value;
  return DATA_KS2.filter(d =>
    (!q  || (d.SCHNAME || '').toLowerCase().includes(q)) &&
    (!la || d.LANAME === la) &&
    (!ty || d.MINORGROUP === ty)
  );
}

function renderKS2() {
  const st   = sortState.ks2;
  const rows = sortData(filterKS2(), st.col, st.asc);
  document.getElementById('ks2-count').textContent = `${rows.length} schools`;
  document.getElementById('ks2-tbody').innerHTML = rows.map(d => `
<tr>
  <td><span class="school-name">${d.SCHNAME || '—'}</span></td>
  <td class="borough-cell">${d.LANAME || ''}</td>
  <td class="type-cell">${d.MINORGROUP || ''}</td>
  <td class="num">${d.total_pupils != null ? d.total_pupils : '<span class="na">—</span>'}</td>
  <td class="num">${fmtPct(d.pct_rwm_expected)}</td>
  <td class="num">${fmtPct(d.pct_rwm_high)}</td>
  <td class="num">${fmtN(d.avg_progress, 2)}</td>
  <td class="num">${fmtPct(d.absence_pct)}</td>
  <td class="num">${fmtPct(d.pct_fsm)}</td>
  <td class="num">${trendArrow(d.rwm_trend, 1)}</td>
  <td class="num">${scoreChip(d.composite_score)}</td>
  <td>${fmtYr(d.data_year)}</td>
</tr>`).join('');
}

// ── KS4 render ─────────────────────────────────────────────────────────────────
function filterKS4() {
  const q  = document.getElementById('ks4-search').value.toLowerCase();
  const la = document.getElementById('ks4-borough').value;
  const ty = document.getElementById('ks4-type').value;
  return DATA_KS4.filter(d =>
    (!q  || (d.SCHNAME || '').toLowerCase().includes(q)) &&
    (!la || d.LANAME === la) &&
    (!ty || d.MINORGROUP === ty)
  );
}

function renderKS4() {
  const st   = sortState.ks4;
  const rows = sortData(filterKS4(), st.col, st.asc);
  document.getElementById('ks4-count').textContent = `${rows.length} schools`;
  document.getElementById('ks4-tbody').innerHTML = rows.map(d => `
<tr>
  <td><span class="school-name">${d.SCHNAME || '—'}</span>${d.punching_above_weight === 1 ? ' <span class="paw" title="Above-median Progress 8, below-median Attainment 8">★</span>' : ''}</td>
  <td class="borough-cell">${d.LANAME || ''}</td>
  <td class="type-cell">${d.MINORGROUP || ''}</td>
  <td class="num">${d.ks4_cohort != null ? d.ks4_cohort : '<span class="na">—</span>'}</td>
  <td class="num">${fmtN(d.progress8, 2)}</td>
  <td class="num">${fmtN(d.attainment8, 1)}</td>
  <td class="num">${fmtPct(d.pct_grade5_eng_maths)}</td>
  <td class="num">${fmtPct(d.pct_ebacc_4plus)}</td>
  <td class="num">${fmtPct(d.dest_pct_education)}</td>
  <td class="num">${fmtPct(d.absence_pct)}</td>
  <td class="num">${p8Arrow(d.p8_trend)}</td>
  <td class="num">${scoreChip(d.composite_score)}</td>
  <td>${fmtYr(d.data_year)}</td>
</tr>`).join('');
}

// ── KS5 render ─────────────────────────────────────────────────────────────────
function filterKS5() {
  const q  = document.getElementById('ks5-search').value.toLowerCase();
  const la = document.getElementById('ks5-borough').value;
  const ty = document.getElementById('ks5-type').value;
  return DATA_KS5.filter(d =>
    (!q  || (d.SCHNAME || '').toLowerCase().includes(q)) &&
    (!la || d.LANAME === la) &&
    (!ty || d.MINORGROUP === ty)
  );
}

function renderKS5() {
  const st   = sortState.ks5;
  const rows = sortData(filterKS5(), st.col, st.asc);
  document.getElementById('ks5-count').textContent = `${rows.length} schools`;
  document.getElementById('ks5-tbody').innerHTML = rows.map(d => `
<tr>
  <td><span class="school-name">${d.SCHNAME || '—'}</span></td>
  <td class="borough-cell">${d.LANAME || ''}</td>
  <td class="type-cell">${d.MINORGROUP || ''}</td>
  <td class="num">${d.alevel_cohort != null ? d.alevel_cohort : '<span class="na">—</span>'}</td>
  <td class="num">${vaScore(d.alevel_value_added)}</td>
  <td class="num">${fmtPct(d.pct_aab_facilitating)}</td>
  <td class="num">${fmtPct(d.dest_pct_he)}</td>
  <td class="num">${fmtPct(d.absence_pct)}</td>
  <td class="num">${vaArrow(d.va_trend)}</td>
  <td class="num">${scoreChip(d.composite_score)}</td>
  <td>${fmtYr(d.data_year)}</td>
</tr>`).join('');
}

// ── Borough render ─────────────────────────────────────────────────────────────
function renderLA() {
  const phase   = document.getElementById('la-phase').value;
  const sortCol = document.getElementById('la-sort').value;
  const rows = DATA_LA.filter(d => d.phase === phase);
  rows.sort((a, b) => {
    if (sortCol === 'borough') return (a.borough || '').localeCompare(b.borough || '');
    if (sortCol === 'n_schools') return (b.n_schools || 0) - (a.n_schools || 0);
    return (b.avg_composite || 0) - (a.avg_composite || 0);
  });

  const grid = document.getElementById('la-grid');
  grid.innerHTML = rows.map(d => {
    let stats = '';
    if (phase === 'KS4') {
      stats = `
        <div class="la-stat"><span class="la-stat-label">Avg Progress 8</span><span class="la-stat-val">${fmtN(d.avg_progress8, 2)}</span></div>
        <div class="la-stat"><span class="la-stat-label">Avg Attainment 8</span><span class="la-stat-val">${fmtN(d.avg_attainment8, 1)}</span></div>
        <div class="la-stat"><span class="la-stat-label">Avg Grade 5+ E&amp;M</span><span class="la-stat-val">${fmtPct(d.avg_pct_grade5_eng_maths)}</span></div>
        <div class="la-stat"><span class="la-stat-label">Avg EBacc 4+</span><span class="la-stat-val">${fmtPct(d.avg_pct_ebacc)}</span></div>
        <div class="la-stat"><span class="la-stat-label">Avg FSM P8 gap</span><span class="la-stat-val">${fmtN(d.avg_fsm_gap_p8, 2)}</span></div>
        <div class="la-stat"><span class="la-stat-label">Avg Absence</span><span class="la-stat-val">${fmtPct(d.avg_absence_pct)}</span></div>`;
    } else if (phase === 'KS2') {
      stats = `
        <div class="la-stat"><span class="la-stat-label">Avg RWM expected</span><span class="la-stat-val">${fmtPct(d.avg_pct_rwm_expected)}</span></div>
        <div class="la-stat"><span class="la-stat-label">Avg RWM higher</span><span class="la-stat-val">${fmtPct(d.avg_pct_rwm_high)}</span></div>
        <div class="la-stat"><span class="la-stat-label">Avg Progress</span><span class="la-stat-val">${fmtN(d.avg_progress, 3)}</span></div>
        <div class="la-stat"><span class="la-stat-label">Avg FSM RWM gap</span><span class="la-stat-val">${fmtPct(d.avg_fsm_gap_rwm)}</span></div>
        <div class="la-stat"><span class="la-stat-label">Avg Absence</span><span class="la-stat-val">${fmtPct(d.avg_absence_pct)}</span></div>`;
    } else {
      stats = `
        <div class="la-stat"><span class="la-stat-label">Avg Value Added</span><span class="la-stat-val">${fmtN(d.avg_va_alevel, 3)}</span></div>
        <div class="la-stat"><span class="la-stat-label">Avg AAB facilitating</span><span class="la-stat-val">${fmtPct(d.avg_pct_aab)}</span></div>
        <div class="la-stat"><span class="la-stat-label">Avg HE destinations</span><span class="la-stat-val">${fmtPct(d.avg_pct_he)}</span></div>
        <div class="la-stat"><span class="la-stat-label">Avg Absence</span><span class="la-stat-val">${fmtPct(d.avg_absence_pct)}</span></div>`;
    }
    return `
<div class="la-card">
  <h3>${d.borough || '?'} <span style="font-weight:400;color:#888;font-size:12px;">(${d.n_schools} schools)</span></h3>
  ${stats}
  <div class="la-stat" style="margin-top:6px;border-top:1px solid #c8d0da;padding-top:6px;">
    <span class="la-stat-label"><b>Avg composite</b></span>
    <span class="la-stat-val">${scoreChip(d.avg_composite)}</span>
  </div>
</div>`;
  }).join('');
}

// ── Init ───────────────────────────────────────────────────────────────────────
(function init() {
  populateSelects(DATA_KS2,
    document.getElementById('ks2-borough'),
    document.getElementById('ks2-type'));
  populateSelects(DATA_KS4,
    document.getElementById('ks4-borough'),
    document.getElementById('ks4-type'));
  populateSelects(DATA_KS5,
    document.getElementById('ks5-borough'),
    document.getElementById('ks5-type'));
  renderKS2();
  renderKS4();
  renderKS5();
  renderLA();
})();
</script>
</body>
</html>
"""


# ── Main ───────────────────────────────────────────────────────────────────────

KS2_COLS = ["SCHNAME", "LANAME", "MINORGROUP", "data_year",
            "total_pupils", "pct_rwm_expected", "pct_rwm_high",
            "avg_progress", "absence_pct", "pct_fsm", "rwm_trend", "composite_score"]

KS4_COLS = ["SCHNAME", "LANAME", "MINORGROUP", "data_year",
            "ks4_cohort", "progress8", "attainment8",
            "pct_grade5_eng_maths", "pct_ebacc_4plus",
            "dest_pct_education", "absence_pct",
            "p8_trend", "punching_above_weight", "composite_score"]

KS5_COLS = ["SCHNAME", "LANAME", "MINORGROUP", "data_year",
            "alevel_cohort", "alevel_value_added",
            "pct_aab_facilitating", "dest_pct_he",
            "absence_pct", "va_trend", "composite_score"]


def main():
    print(f"Reading from: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)

    ks2 = load(conn, "metrics_ks2", KS2_COLS)
    ks4 = load(conn, "metrics_ks4", KS4_COLS)
    ks5 = load(conn, "metrics_ks5", KS5_COLS)
    la  = load(conn, "metrics_la")
    conn.close()

    print(f"  KS2: {len(ks2):,} rows, KS4: {len(ks4):,} rows, KS5: {len(ks5):,} rows, LA: {len(la):,} rows")

    html = HTML_TEMPLATE
    html = html.replace("__DATA_KS2__", df_to_json(ks2))
    html = html.replace("__DATA_KS4__", df_to_json(ks4))
    html = html.replace("__DATA_KS5__", df_to_json(ks5))
    html = html.replace("__DATA_LA__",  df_to_json(la))

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(html)

    size_kb = os.path.getsize(OUT_PATH) / 1024
    print(f"Written: {OUT_PATH} ({size_kb:.0f} KB)")


if __name__ == "__main__":
    main()
