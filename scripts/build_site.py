#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""构建 GitHub Pages 静态站点（数据概览 + 可缩放交互走势图）到 site/。
图表基于 Plotly.js（CDN），支持：拖拽框选缩放、滚轮缩放、双击复位、底部 range slider。"""
import csv, datetime as dt, html, json, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "site")
os.makedirs(OUT, exist_ok=True)

PLOTLY_CDN = "https://cdn.plot.ly/plotly-2.35.2.min.js"


def read_csv_rows(path):
    rows = []
    with open(path, newline="", encoding="utf-8", errors="replace") as f:
        for r in csv.reader(f):
            if not r or not r[0].strip() or r[0].lstrip().startswith("#"):
                continue
            rows.append(r)
    return rows[1:] if rows else []


def stats(path):
    rows = read_csv_rows(path)
    dates = [r[0] for r in rows if r[0]]
    return len(rows), (min(dates) if dates else "-"), (max(dates) if dates else "-")


def fval(s):
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# 图表数据
# ---------------------------------------------------------------------------

def master_data():
    """Master: date, rate, target_low, target_high（target 仅 2008+ 区间制有值）"""
    rows = read_csv_rows(os.path.join(ROOT, "Master_Federal_Funds_Rate_Daily.csv"))
    dates, rate, low, high = [], [], [], []
    for r in rows:
        dates.append(r[0])
        rate.append(fval(r[1]) if len(r) > 1 else None)
        low.append(fval(r[4]) if len(r) > 4 and r[4] else None)
        high.append(fval(r[5]) if len(r) > 5 and r[5] else None)
    return {"dates": dates, "rate": rate, "low": low, "high": high}


def effr_data():
    """EFFR_simplified: date, rate, target_low, target_high"""
    rows = read_csv_rows(os.path.join(ROOT, "EFFR_simplified.csv"))
    dates, rate, low, high = [], [], [], []
    for r in rows:
        dates.append(r[0])
        rate.append(fval(r[1]))
        low.append(fval(r[2]) if len(r) > 2 and r[2] else None)
        high.append(fval(r[3]) if len(r) > 3 and r[3] else None)
    return {"dates": dates, "rate": rate, "low": low, "high": high}


def fomc_data():
    """Extended: date, change_bp, target_low（阶梯用）"""
    rows = read_csv_rows(os.path.join(ROOT, "FOMC_Rate_Decisions_Extended.csv"))
    dates, change, target = [], [], []
    for r in rows:
        dates.append(r[0])
        change.append(int(r[2]) if r[2].lstrip("-").isdigit() else 0)
        tr = r[3]
        if "-" in tr:
            low = tr.split("-")[0]
        else:
            low = tr
        target.append(fval(low))
    return {"dates": dates, "change": change, "target": target}


def supp_data():
    """补充经济数据：CPI、失业率、非农、核心 PCE"""
    out = {}
    for sid, title in [("FRED_CPIAUCSL.csv", "CPI (同比, %)"),
                       ("FRED_UNRATE.csv", "失业率 (%)"),
                       ("FRED_PAYEMS.csv", "非农就业 (千人)"),
                       ("FRED_PCEPILFE.csv", "核心 PCE (指数)")]:
        rows = read_csv_rows(os.path.join(ROOT, sid))
        out[sid] = {
            "title": title,
            "dates": [r[0] for r in rows],
            "values": [fval(r[1]) for r in rows],
        }
    return out


def js(obj):
    return json.dumps(obj, separators=(",", ":"))


# ---------------------------------------------------------------------------
# 页面
# ---------------------------------------------------------------------------

def chart_html(div_id, height):
    return (f'<div id="{div_id}" class="chart" style="width:100%;height:{height}px"></div>\n'
            f'<div class="hint">拖拽框选 / 滚轮缩放 / 双击复位 / 底部滑杆缩放</div>')


def build():
    master, effr, fomc, supp = master_data(), effr_data(), fomc_data(), supp_data()

    # Current status 卡片
    status = {}
    try:
        effr_rows = read_csv_rows(os.path.join(ROOT, "FRED_DFF.csv"))
        lows = read_csv_rows(os.path.join(ROOT, "FRED_DFEDTARL.csv"))
        highs = read_csv_rows(os.path.join(ROOT, "FRED_DFEDTARU.csv"))
        if lows and highs and effr_rows:
            status = {"low": lows[-1][1], "high": highs[-1][1],
                      "effr": effr_rows[-1][1], "effr_date": effr_rows[-1][0],
                      "date": dt.date.today().isoformat()}
    except Exception:
        pass

    rows_html = ""
    for fname, desc in [
        ("Master_Federal_Funds_Rate_Daily.csv", "Combined daily rate with target range"),
        ("DFF_federal_funds_effective_rate_daily.csv", "Effective Federal Funds Rate (DFF)"),
        ("EFFR_simplified.csv", "EFFR simplified (rate + target range)"),
        ("EFFR_nyfed_with_target_range.csv", "EFFR from NY Fed (all columns)"),
        ("DFEDTAR_target_range_from_nyfed.csv", "Target range extracted from EFFR data"),
        ("FOMC_Rate_Decisions.csv", "Official FOMC rate decisions (2003+)"),
        ("FOMC_Rate_Decisions_Extended.csv", "All FOMC meetings 1982-2026"),
        ("FOMC_Meeting_Calendars.csv", "FOMC meeting schedule (1960-2027)"),
        ("FOMC_communications_vtasca.csv", "FOMC statements & minutes (1994-2026)"),
    ]:
        n, first, last = stats(os.path.join(ROOT, fname))
        url = f"https://raw.githubusercontent.com/banana815/financial-info/main/{fname}"
        rows_html += (f"<tr><td><a href='{url}'>{html.escape(fname)}</a></td>"
                      f"<td>{html.escape(desc)}</td><td>{first} → {last}</td>"
                      f"<td style='text-align:right'>{n:,}</td></tr>\n")

    status_html = ""
    if status:
        status_html = f"""
    <div class="status">
      <div><span>Target Range</span><b>{html.escape(status['low'])}% – {html.escape(status['high'])}%</b></div>
      <div><span>EFFR (as of {html.escape(status['effr_date'])})</span><b>{html.escape(status['effr'])}%</b></div>
      <div><span>Updated</span><b>{html.escape(status['date'])}</b></div>
    </div>"""

    page = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Federal Funds Rate &amp; FOMC Data</title>
<script src="{PLOTLY_CDN}"></script>
<style>
  body {{ font-family: -apple-system, "Segoe UI", Roboto, "PingFang SC", sans-serif;
         margin: 0; background: #f6f8fa; color: #24292f; }}
  header {{ background: #0d1117; color: #fff; padding: 28px 24px; }}
  header h1 {{ margin: 0 0 6px; font-size: 24px; }}
  header p {{ margin: 0; color: #8b949e; }}
  main {{ max-width: 980px; margin: 24px auto; padding: 0 16px; }}
  .status {{ display: flex; gap: 16px; flex-wrap: wrap; margin-bottom: 24px; }}
  .status div {{ background: #fff; border: 1px solid #d0d7de; border-radius: 8px;
                 padding: 14px 18px; flex: 1; min-width: 180px; }}
  .status span {{ display: block; color: #57606a; font-size: 12px; margin-bottom: 4px; }}
  .status b {{ font-size: 20px; }}
  h2 {{ margin: 32px 0 12px; font-size: 19px; }}
  .chart {{ background: #fff; border: 1px solid #d0d7de; border-radius: 8px; }}
  .hint {{ color: #57606a; font-size: 12px; margin: 4px 0 20px; }}
  .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }}
  @media (max-width: 720px) {{ .grid {{ grid-template-columns: 1fr; }} }}
  table {{ width: 100%; border-collapse: collapse; background: #fff;
          border: 1px solid #d0d7de; border-radius: 8px; overflow: hidden; }}
  th, td {{ padding: 10px 12px; text-align: left; border-bottom: 1px solid #eaeef2; }}
  th {{ background: #f6f8fa; font-size: 13px; }}
  td {{ font-size: 14px; }}
  a {{ color: #0969da; text-decoration: none; }}
  footer {{ text-align: center; color: #57606a; font-size: 12px; padding: 24px 0; }}
</style>
</head>
<body>
<header>
  <h1>Federal Funds Rate &amp; FOMC Data Collection</h1>
  <p>Effective Federal Funds Rate · target range · FOMC decisions · 交互图表（可缩放）</p>
</header>
<main>
{status_html}
  <h2>📈 数据走势图</h2>
  {chart_html("chart-master", 460)}
  {chart_html("chart-effr", 460)}
  <div class="grid">
    {chart_html("chart-fomc", 400)}
    <div>
      {chart_html("chart-cpi", 190)}
      {chart_html("chart-unrate", 190)}
    </div>
  </div>
  <h2>数据文件</h2>
  <table>
    <tr><th>File</th><th>Description</th><th>Date Range</th><th>Records</th></tr>
{rows_html}
  </table>
  <footer>Auto-generated from the repository CSV files · 每日由 GitHub Actions 自动更新</footer>
</main>

<script type="application/json" id="data-master">{js(master)}</script>
<script type="application/json" id="data-effr">{js(effr)}</script>
<script type="application/json" id="data-fomc">{js(fomc)}</script>
<script type="application/json" id="data-supp">{js(supp)}</script>

<script>
(function () {{
  function get(id) {{ return JSON.parse(document.getElementById(id).textContent); }}

  const baseLayout = {{
    margin: {{ l: 52, r: 18, t: 36, b: 40 }},
    hovermode: "x unified",
    xaxis: {{ type: "date", rangeslider: {{ visible: true, thickness: 0.06 }},
              rangeselector: {{ buttons: [
                {{ count: 1, label: "1Y", step: "year", stepmode: "backward" }},
                {{ count: 5, label: "5Y", step: "year", stepmode: "backward" }},
                {{ count: 10, label: "10Y", step: "year", stepmode: "backward" }},
                {{ step: "all", label: "全部" }} ] }} }},
    dragmode: "zoom",
    uirevision: "fixed"
  }};

  // 图1：有效联邦基金利率 1976-2026 + 目标区间
  const m = get("data-master");
  Plotly.newPlot("chart-master", [
    {{ x: m.dates, y: m.low, mode: "lines", line: {{ width: 0 }}, showlegend: false,
       hoverinfo: "skip", fill: "none" }},
    {{ x: m.dates, y: m.high, mode: "lines", line: {{ width: 0 }}, showlegend: false,
       hoverinfo: "skip", fill: "tonexty", fillcolor: "rgba(30,136,229,0.15)" }},
    {{ x: m.dates, y: m.rate, name: "有效联邦基金利率 (DFF/EFFR)", mode: "lines",
       line: {{ color: "#1f77b4", width: 1.2 }} }}
  ], Object.assign({{}}, baseLayout, {{
    title: "联邦基金有效利率与目标区间 (1976-2026)",
    yaxis: {{ title: "%" }}
  }}));

  // 图2：EFFR + 目标区间（2000+）
  const e = get("data-effr");
  Plotly.newPlot("chart-effr", [
    {{ x: e.dates, y: e.low, mode: "lines", line: {{ color: "rgba(30,136,229,0.25)", width: 1 }},
       name: "目标区间下限", fill: "none" }},
    {{ x: e.dates, y: e.high, mode: "lines", line: {{ color: "rgba(30,136,229,0.25)", width: 1 }},
       name: "目标区间上限", fill: "tonexty", fillcolor: "rgba(30,136,229,0.12)" }},
    {{ x: e.dates, y: e.rate, name: "EFFR", mode: "lines",
       line: {{ color: "#d32f2f", width: 1.4 }} }}
  ], Object.assign({{}}, baseLayout, {{
    title: "EFFR 与目标区间 (2000-2026)",
    yaxis: {{ title: "%" }}
  }}));

  // 图3：FOMC 利率决议（升降息柱状 + 目标利率阶梯）
  const f = get("data-fomc");
  const colors = f.change.map(c => c > 0 ? "#d32f2f" : (c < 0 ? "#2e7d32" : "#9e9e9e"));
  Plotly.newPlot("chart-fomc", [
    {{ x: f.dates, y: f.change, type: "bar", name: "利率变动 (bp)",
       marker: {{ color: colors }}, yaxis: "y2" }},
    {{ x: f.dates, y: f.target, mode: "lines", name: "目标利率 (%)",
       line: {{ color: "#1565c0", width: 1.6, shape: "hv" }} }}
  ], Object.assign({{}}, baseLayout, {{
    title: "FOMC 利率决议 (1982-2026)",
    yaxis: {{ title: "目标利率 (%)" }},
    yaxis2: {{ title: "变动 (bp)", overlaying: "y", side: "right", showgrid: false }},
    barmode: "overlay"
  }}));

  // 图4-5：补充经济数据（CPI / 失业率 2x2 上半部分）
  const s = get("data-supp");
  function smallChart(id, key, color, title) {{
    const d = s[key];
    Plotly.newPlot(id, [
      {{ x: d.dates, y: d.values, mode: "lines", name: title,
         line: {{ color: color, width: 1.4 }} }}
    ], Object.assign({{}}, baseLayout, {{
      title: title, showlegend: false,
      xaxis: {{ type: "date", rangeslider: {{ visible: false }} }},
      margin: {{ l: 50, r: 14, t: 34, b: 30 }}
    }}));
  }}
  smallChart("chart-cpi", "FRED_CPIAUCSL.csv", "#8e24aa", "CPI (同比, %)");
  smallChart("chart-unrate", "FRED_UNRATE.csv", "#ef6c00", "失业率 (%)");

  window.addEventListener("resize", () => {{
    ["chart-master", "chart-effr", "chart-fomc", "chart-cpi", "chart-unrate"]
      .forEach(id => Plotly.Plots.resize(document.getElementById(id)));
  }});
}})();
</script>
</body>
</html>
"""
    out_path = os.path.join(OUT, "index.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(page)
    print(f"已生成 {out_path}（{len(page)/1024:.0f} KB）")


if __name__ == "__main__":
    build()
