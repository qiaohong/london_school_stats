"""
Generates a self-contained HTML report (report.html) with charts
summarising the school database — no web server required.
"""

import sqlite3
import json
from pathlib import Path

DB_PATH     = Path(__file__).parent / "ofsted_schools.db"
OUTPUT_PATH = Path(__file__).parent / "report.html"

GRADE_LABELS = {
    1: "Outstanding",
    2: "Good",
    3: "Requires Improvement",
    4: "Inadequate",
}
GRADE_COLOURS = {
    "Outstanding":            "#2e7d32",
    "Good":                   "#66bb6a",
    "Requires Improvement":   "#fb8c00",
    "Inadequate":             "#c62828",
    "Not yet inspected":      "#bdbdbd",
}


def query(conn, sql, params=()):
    return conn.execute(sql, params).fetchall()


def build_data(conn):
    # ── 1. Schools per LA (stacked primary / secondary) ──────────────────────
    rows = query(conn, """
        SELECT local_authority, phase, COUNT(*) AS n
        FROM schools
        GROUP BY local_authority, phase
        ORDER BY local_authority
    """)
    la_totals = {}
    la_primary = {}
    la_secondary = {}
    for la, phase, n in rows:
        la_totals[la] = la_totals.get(la, 0) + n
        if phase == "Primary":
            la_primary[la] = n
        else:
            la_secondary[la] = n

    # Sort by total descending
    sorted_las = sorted(la_totals, key=lambda x: -la_totals[x])
    schools_per_la = {
        "labels":    sorted_las,
        "primary":   [la_primary.get(la, 0)   for la in sorted_las],
        "secondary": [la_secondary.get(la, 0) for la in sorted_las],
        "totals":    [la_totals[la]            for la in sorted_las],
    }

    # ── 2. Overall judgement distribution ─────────────────────────────────────
    rows = query(conn, """
        SELECT j.overall_effectiveness, COUNT(*) AS n
        FROM schools s
        LEFT JOIN inspections i ON s.urn = i.urn
        LEFT JOIN judgements  j ON i.id  = j.inspection_id
        GROUP BY j.overall_effectiveness
    """)
    grade_counts = {}
    for grade, n in rows:
        label = GRADE_LABELS.get(grade, "Not yet inspected")
        grade_counts[label] = grade_counts.get(label, 0) + n

    grade_order = ["Outstanding", "Good", "Requires Improvement", "Inadequate", "Not yet inspected"]
    judgement_dist = {
        "labels":  grade_order,
        "counts":  [grade_counts.get(g, 0) for g in grade_order],
        "colours": [GRADE_COLOURS[g]       for g in grade_order],
    }

    # ── 3. Judgements by LA (% Good or better, sorted) ────────────────────────
    rows = query(conn, """
        SELECT s.local_authority,
               j.overall_effectiveness,
               COUNT(*) AS n
        FROM schools s
        LEFT JOIN inspections i ON s.urn = i.urn
        LEFT JOIN judgements  j ON i.id  = j.inspection_id
        GROUP BY s.local_authority, j.overall_effectiveness
    """)
    la_grades = {}  # la -> {grade_label: count}
    for la, grade, n in rows:
        label = GRADE_LABELS.get(grade, "Not yet inspected")
        la_grades.setdefault(la, {})
        la_grades[la][label] = la_grades[la].get(label, 0) + n

    # Sort LAs by % Good-or-better (Outstanding + Good), inspected schools only
    def pct_good_or_better(la):
        d = la_grades.get(la, {})
        inspected = sum(v for k, v in d.items() if k != "Not yet inspected")
        if inspected == 0:
            return 0
        return (d.get("Outstanding", 0) + d.get("Good", 0)) / inspected * 100

    sorted_by_grade = sorted(la_grades.keys(), key=pct_good_or_better, reverse=True)
    judgements_by_la = {
        "labels": sorted_by_grade,
        "series": {
            grade: [la_grades.get(la, {}).get(grade, 0) for la in sorted_by_grade]
            for grade in grade_order
        },
        "colours": GRADE_COLOURS,
    }

    # ── 4. Summary stats ──────────────────────────────────────────────────────
    total_schools  = query(conn, "SELECT COUNT(*) FROM schools")[0][0]
    total_primary  = query(conn, "SELECT COUNT(*) FROM schools WHERE phase='Primary'")[0][0]
    total_secondary= query(conn, "SELECT COUNT(*) FROM schools WHERE phase='Secondary'")[0][0]
    pct_good_plus  = query(conn, """
        SELECT ROUND(100.0 * SUM(CASE WHEN j.overall_effectiveness IN (1,2) THEN 1 ELSE 0 END)
                     / SUM(CASE WHEN j.overall_effectiveness IS NOT NULL THEN 1 ELSE 0 END), 1)
        FROM schools s
        LEFT JOIN inspections i ON s.urn = i.urn
        LEFT JOIN judgements  j ON i.id  = j.inspection_id
    """)[0][0]

    summary = {
        "total_schools":   total_schools,
        "total_primary":   total_primary,
        "total_secondary": total_secondary,
        "pct_good_plus":   pct_good_plus,
    }

    return schools_per_la, judgement_dist, judgements_by_la, summary


def render_html(schools_per_la, judgement_dist, judgements_by_la, summary):
    d_la   = json.dumps(schools_per_la)
    d_dist = json.dumps(judgement_dist)
    d_byla = json.dumps(judgements_by_la)
    d_summ = json.dumps(summary)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>London & Surrey School Report</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}

  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: #f5f6fa;
    color: #222;
    padding: 0 0 60px;
  }}

  header {{
    background: #1a237e;
    color: white;
    padding: 28px 40px 24px;
  }}
  header h1 {{ font-size: 1.7rem; font-weight: 700; letter-spacing: -0.02em; }}
  header p  {{ margin-top: 6px; opacity: 0.75; font-size: 0.9rem; }}

  .stats {{
    display: flex;
    gap: 16px;
    padding: 24px 40px;
    flex-wrap: wrap;
  }}
  .stat-card {{
    background: white;
    border-radius: 10px;
    padding: 20px 28px;
    flex: 1;
    min-width: 160px;
    box-shadow: 0 1px 4px rgba(0,0,0,.08);
    border-top: 4px solid #1a237e;
  }}
  .stat-card .value {{ font-size: 2rem; font-weight: 700; color: #1a237e; }}
  .stat-card .label {{ font-size: 0.82rem; color: #666; margin-top: 4px; }}

  .charts {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 20px;
    padding: 0 40px;
  }}
  .chart-card {{
    background: white;
    border-radius: 10px;
    padding: 24px;
    box-shadow: 0 1px 4px rgba(0,0,0,.08);
  }}
  .chart-card.full {{ grid-column: 1 / -1; }}
  .chart-card h2 {{
    font-size: 0.95rem;
    font-weight: 600;
    color: #444;
    margin-bottom: 18px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }}

  @media (max-width: 900px) {{
    .charts {{ grid-template-columns: 1fr; }}
    .chart-card.full {{ grid-column: 1; }}
    header, .stats, .charts {{ padding-left: 16px; padding-right: 16px; }}
  }}
</style>
</head>
<body>

<header>
  <h1>London & Surrey School Report</h1>
  <p>Ofsted inspection outcomes · KS2/KS4 attainment · Absence & exclusions · Admissions</p>
</header>

<div class="stats" id="stats"></div>

<div class="charts">
  <div class="chart-card">
    <h2>Judgement distribution — all schools</h2>
    <canvas id="chartDist" height="260"></canvas>
  </div>

  <div class="chart-card">
    <h2>Phase split per local authority</h2>
    <canvas id="chartPhase" height="260"></canvas>
  </div>

  <div class="chart-card full">
    <h2>Ofsted grades by local authority (sorted by % Good or better)</h2>
    <canvas id="chartByLA" height="420"></canvas>
  </div>

  <div class="chart-card full">
    <h2>Total schools per local authority</h2>
    <canvas id="chartTotal" height="420"></canvas>
  </div>
</div>

<script>
const laData      = {d_la};
const distData    = {d_dist};
const byLAData    = {d_byla};
const summary     = {d_summ};

// ── Summary cards ─────────────────────────────────────────────────────────────
const stats = [
  {{ value: summary.total_schools.toLocaleString(),  label: "Total schools" }},
  {{ value: summary.total_primary.toLocaleString(),  label: "Primary schools" }},
  {{ value: summary.total_secondary.toLocaleString(),label: "Secondary schools" }},
  {{ value: summary.pct_good_plus + "%",             label: "Good or Outstanding" }},
];
const statsEl = document.getElementById("stats");
stats.forEach(s => {{
  statsEl.innerHTML += `
    <div class="stat-card">
      <div class="value">${{s.value}}</div>
      <div class="label">${{s.label}}</div>
    </div>`;
}});

// ── Chart defaults ─────────────────────────────────────────────────────────────
Chart.defaults.font.family = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif";
Chart.defaults.font.size   = 12;
Chart.defaults.color       = "#555";

// ── 1. Judgement distribution (doughnut) ──────────────────────────────────────
new Chart(document.getElementById("chartDist"), {{
  type: "doughnut",
  data: {{
    labels:   distData.labels,
    datasets: [{{ data: distData.counts, backgroundColor: distData.colours, borderWidth: 2, borderColor: "#fff" }}]
  }},
  options: {{
    cutout: "60%",
    plugins: {{
      legend: {{ position: "right", labels: {{ padding: 14, boxWidth: 14 }} }},
      tooltip: {{
        callbacks: {{
          label: ctx => {{
            const total = ctx.dataset.data.reduce((a,b) => a+b, 0);
            const pct   = (ctx.parsed / total * 100).toFixed(1);
            return ` ${{ctx.label}}: ${{ctx.parsed.toLocaleString()}} (${{pct}}%)`;
          }}
        }}
      }}
    }}
  }}
}});

// ── 2. Primary / Secondary stacked horizontal bar (by LA total) ───────────────
new Chart(document.getElementById("chartPhase"), {{
  type: "bar",
  data: {{
    labels: laData.labels,
    datasets: [
      {{ label: "Primary",   data: laData.primary,   backgroundColor: "#1565c0", borderRadius: 2 }},
      {{ label: "Secondary", data: laData.secondary, backgroundColor: "#42a5f5", borderRadius: 2 }},
    ]
  }},
  options: {{
    indexAxis: "y",
    plugins: {{ legend: {{ position: "top" }} }},
    scales: {{
      x: {{ stacked: true, grid: {{ color: "#f0f0f0" }} }},
      y: {{ stacked: true, ticks: {{ font: {{ size: 11 }} }} }}
    }}
  }}
}});

// ── 3. Judgements stacked bar by LA ───────────────────────────────────────────
const gradeOrder = ["Outstanding", "Good", "Requires Improvement", "Inadequate", "Not yet inspected"];
new Chart(document.getElementById("chartByLA"), {{
  type: "bar",
  data: {{
    labels: byLAData.labels,
    datasets: gradeOrder.map(g => ({{
      label:           g,
      data:            byLAData.series[g],
      backgroundColor: byLAData.colours[g],
      borderRadius:    2,
    }}))
  }},
  options: {{
    indexAxis: "y",
    plugins: {{ legend: {{ position: "top" }} }},
    scales: {{
      x: {{ stacked: true, grid: {{ color: "#f0f0f0" }} }},
      y: {{ stacked: true, ticks: {{ font: {{ size: 11 }} }} }}
    }}
  }}
}});

// ── 4. Total schools bar ───────────────────────────────────────────────────────
new Chart(document.getElementById("chartTotal"), {{
  type: "bar",
  data: {{
    labels: laData.labels,
    datasets: [{{
      label:           "Total schools",
      data:            laData.totals,
      backgroundColor: "#1a237e",
      borderRadius:    4,
    }}]
  }},
  options: {{
    indexAxis: "y",
    plugins: {{ legend: {{ display: false }} }},
    scales: {{
      x: {{ grid: {{ color: "#f0f0f0" }} }},
      y: {{ ticks: {{ font: {{ size: 11 }} }} }}
    }}
  }}
}});
</script>
</body>
</html>
"""


if __name__ == "__main__":
    with sqlite3.connect(DB_PATH) as conn:
        schools_per_la, judgement_dist, judgements_by_la, summary = build_data(conn)

    html = render_html(schools_per_la, judgement_dist, judgements_by_la, summary)
    OUTPUT_PATH.write_text(html, encoding="utf-8")
    print(f"Report written to: {OUTPUT_PATH}")
    print(f"Open with: xdg-open '{OUTPUT_PATH}'  or copy to your browser")
