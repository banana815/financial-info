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


def pct_change(values, lag):
    """环比(lag=1)/同比(lag=12) 变化率 %。返回与 values 等长（前 lag 个为 None）。"""
    out = [None] * len(values)
    for i in range(lag, len(values)):
        if values[i] is not None and values[i - lag]:
            out[i] = round((values[i] / values[i - lag] - 1) * 100, 2)
    return out


# ---------------------------------------------------------------------------
# 图表数据
# ---------------------------------------------------------------------------

def master_data():
    rows = read_csv_rows(os.path.join(ROOT, "Master_Federal_Funds_Rate_Daily.csv"))
    dates, rate, low, high = [], [], [], []
    for r in rows:
        dates.append(r[0])
        rate.append(fval(r[1]) if len(r) > 1 else None)
        low.append(fval(r[4]) if len(r) > 4 and r[4] else None)
        high.append(fval(r[5]) if len(r) > 5 and r[5] else None)
    return {"dates": dates, "rate": rate, "low": low, "high": high}


def effr_data():
    rows = read_csv_rows(os.path.join(ROOT, "EFFR_simplified.csv"))
    dates, rate, low, high = [], [], [], []
    for r in rows:
        dates.append(r[0])
        rate.append(fval(r[1]))
        low.append(fval(r[2]) if len(r) > 2 and r[2] else None)
        high.append(fval(r[3]) if len(r) > 3 and r[3] else None)
    return {"dates": dates, "rate": rate, "low": low, "high": high}


def fomc_data():
    rows = read_csv_rows(os.path.join(ROOT, "FOMC_Rate_Decisions_Extended.csv"))
    dates, change, target = [], [], []
    for r in rows:
        dates.append(r[0])
        change.append(int(r[2]) if r[2].lstrip("-").isdigit() else 0)
        tr = r[3]
        low = tr.split("-")[0] if "-" in tr else tr
        target.append(fval(low))
    return {"dates": dates, "change": change, "target": target}


def econ_data():
    """全部补充经济指标：原值 + CPI 环比/同比。"""
    out = {}
    spec = {
        "FRED_CPIAUCSL.csv": "CPI",
        "FRED_UNRATE.csv": "UNRATE",
        "FRED_GDPC1.csv": "GDPC1",
        "FRED_GDPPOT.csv": "GDPPOT",
        "FRED_PAYEMS.csv": "PAYEMS",
        "FRED_PCEPILFE.csv": "PCEPILFE",
        "FRED_HSN1F.csv": "HSN1F",
        "FRED_RRSFS.csv": "RRSFS",
    }
    for fname in spec:
        rows = read_csv_rows(os.path.join(ROOT, fname))
        dates = [r[0] for r in rows]
        values = [fval(r[1]) for r in rows]
        d = {"title": spec[fname], "dates": dates, "value": values}
        if fname == "FRED_CPIAUCSL.csv":
            d["mom"] = pct_change(values, 1)
            d["yoy"] = pct_change(values, 12)
        if fname == "FRED_PCEPILFE.csv":
            d["yoy"] = pct_change(values, 12)
        out[fname] = d
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
    master, effr, fomc, econ = master_data(), effr_data(), fomc_data(), econ_data()

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

    # 经济指标小图（2 列网格）
    econ_grid = ""
    for div_id, height in [
        ("econ-cpi-mom", 220), ("econ-cpi-yoy", 220),
        ("econ-unrate", 220), ("econ-payems", 220),
        ("econ-gdp", 220), ("econ-pce", 220),
        ("econ-hsn1f", 220), ("econ-rrsfs", 220),
    ]:
        econ_grid += chart_html(div_id, height)

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
  <p>Effective Federal Funds Rate · target range · FOMC decisions · 宏观经济指标 · 交互图表（可缩放）</p>
</header>
<main>
{status_html}
  <h2>📈 利率与 FOMC</h2>
  {chart_html("chart-master", 460)}
  {chart_html("chart-effr", 440)}
  {chart_html("chart-fomc", 420)}

  <h2>📊 宏观经济指标</h2>
  <div class="grid">
{econ_grid}
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
<script type="application/json" id="data-econ">{js(econ)}</script>

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
  const smallLayout = Object.assign({{}}, baseLayout, {{
    showlegend: false,
    xaxis: {{ type: "date", rangeslider: {{ visible: false }} }},
    margin: {{ l: 50, r: 14, t: 34, b: 30 }}
  }});

  function line(x, y, name, color, width) {{
    return {{ x: x, y: y, name: name, mode: "lines",
              line: {{ color: color, width: width || 1.4 }} }};
  }}

  // 图1：有效联邦基金利率 1976-2026 + 目标区间
  const m = get("data-master");
  Plotly.newPlot("chart-master", [
    {{ x: m.dates, y: m.low, mode: "lines", line: {{ width: 0 }}, showlegend: false,
       hoverinfo: "skip", fill: "none" }},
    {{ x: m.dates, y: m.high, mode: "lines", line: {{ width: 0 }}, showlegend: false,
       hoverinfo: "skip", fill: "tonexty", fillcolor: "rgba(30,136,229,0.15)" }},
    line(m.dates, m.rate, "有效联邦基金利率 (DFF/EFFR)", "#1f77b4", 1.2)
  ], Object.assign({{}}, baseLayout, {{
    title: "联邦基金有效利率与目标区间 (1976-2026)", yaxis: {{ title: "%" }}
  }}));

  // 图2：EFFR + 目标区间（2000+）
  const e = get("data-effr");
  Plotly.newPlot("chart-effr", [
    line(e.dates, e.low, "目标区间下限", "rgba(30,136,229,0.25)", 1),
    {{ x: e.dates, y: e.high, mode: "lines", name: "目标区间上限",
       line: {{ color: "rgba(30,136,229,0.25)", width: 1 }},
       fill: "tonexty", fillcolor: "rgba(30,136,229,0.12)" }},
    line(e.dates, e.rate, "EFFR", "#d32f2f", 1.4)
  ], Object.assign({{}}, baseLayout, {{
    title: "EFFR 与目标区间 (2000-2026)", yaxis: {{ title: "%" }}
  }}));

  // 图3：FOMC 利率决议
  const f = get("data-fomc");
  const colors = f.change.map(c => c > 0 ? "#d32f2f" : (c < 0 ? "#2e7d32" : "#9e9e9e"));
  Plotly.newPlot("chart-fomc", [
    {{ x: f.dates, y: f.change, type: "bar", name: "利率变动 (bp)",
       marker: {{ color: colors }}, yaxis: "y2" }},
    line(f.dates, f.target, "目标利率 (%)", "#1565c0", 1.6)
  ], Object.assign({{}}, baseLayout, {{
    title: "FOMC 利率决议 (1982-2026)",
    yaxis: {{ title: "目标利率 (%)" }},
    yaxis2: {{ title: "变动 (bp)", overlaying: "y", side: "right", showgrid: false }}
  }}));

  // 经济指标小图
  const s = get("data-econ");
  function smallChart(id, traces, title, ylabel) {{
    Plotly.newPlot(id, traces, Object.assign({{}}, smallLayout, {{
      title: title, yaxis: {{ title: ylabel || "" }}
    }}));
  }}

  smallChart("econ-cpi-mom",
    [line(s["FRED_CPIAUCSL.csv"].dates, s["FRED_CPIAUCSL.csv"].mom, "CPI 环比", "#8e24aa", 1.3)],
    "CPI 环比增长 (MoM, %)", "%");
  smallChart("econ-cpi-yoy",
    [line(s["FRED_CPIAUCSL.csv"].dates, s["FRED_CPIAUCSL.csv"].yoy, "CPI 同比", "#c2185b", 1.3)],
    "CPI 同比增长 (YoY, %)", "%");
  smallChart("econ-unrate",
    [line(s["FRED_UNRATE.csv"].dates, s["FRED_UNRATE.csv"].value, "失业率", "#ef6c00", 1.3)],
    "失业率 (UNRATE, %)", "%");
  smallChart("econ-payems",
    [line(s["FRED_PAYEMS.csv"].dates, s["FRED_PAYEMS.csv"].value, "非农就业", "#2e7d32", 1.3)],
    "非农就业 (PAYEMS, 千人)", "千人");
  smallChart("econ-gdp",
    [line(s["FRED_GDPC1.csv"].dates, s["FRED_GDPC1.csv"].value, "实际 GDP", "#1565c0", 1.3),
     line(s["FRED_GDPPOT.csv"].dates, s["FRED_GDPPOT.csv"].value, "潜在 GDP", "#90a4ae", 1.1)],
    "实际 GDP vs 潜在 GDP (十亿美元)", "十亿美元");
  smallChart("econ-pce",
    [line(s["FRED_PCEPILFE.csv"].dates, s["FRED_PCEPILFE.csv"].value, "核心 PCE", "#6a1b9a", 1.3),
     line(s["FRED_PCEPILFE.csv"].dates, s["FRED_PCEPILFE.csv"].yoy, "同比", "#ce93d8", 1.1)],
    "核心 PCE 指数 (PCEPILFE)", "指数");
  smallChart("econ-hsn1f",
    [line(s["FRED_HSN1F.csv"].dates, s["FRED_HSN1F.csv"].value, "住房开工", "#00838f", 1.3)],
    "住房开工 (HSN1F, 千套)", "千套");
  smallChart("econ-rrsfs",
    [line(s["FRED_RRSFS.csv"].dates, s["FRED_RRSFS.csv"].value, "零售销售", "#5d4037", 1.3)],
    "实际零售销售 (RRSFS, 指数)", "指数");

  window.addEventListener("resize", () => {{
    ["chart-master", "chart-effr", "chart-fomc",
     "econ-cpi-mom", "econ-cpi-yoy", "econ-unrate", "econ-payems",
     "econ-gdp", "econ-pce", "econ-hsn1f", "econ-rrsfs"]
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
