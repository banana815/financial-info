#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""构建 GitHub Pages 静态站点（数据概览页）到 site/。"""
import csv, datetime as dt, html, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "site")
os.makedirs(OUT, exist_ok=True)


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


FILES = [
    ("Master_Federal_Funds_Rate_Daily.csv", "Combined daily rate with target range"),
    ("DFF_federal_funds_effective_rate_daily.csv", "Effective Federal Funds Rate (DFF)"),
    ("EFFR_simplified.csv", "EFFR simplified (rate + target range)"),
    ("EFFR_nyfed_with_target_range.csv", "EFFR from NY Fed (all columns)"),
    ("DFEDTAR_target_range_from_nyfed.csv", "Target range extracted from EFFR data"),
    ("FOMC_Rate_Decisions.csv", "Official FOMC rate decisions (2003+)"),
    ("FOMC_Rate_Decisions_Extended.csv", "All FOMC meetings 1982-2026"),
    ("FOMC_Meeting_Calendars.csv", "FOMC meeting schedule (1960-2027)"),
    ("FOMC_communications_vtasca.csv", "FOMC statements & minutes (1994-2026)"),
]

# Current status: 最新 EFFR 与 target
effr_rows = read_csv_rows(os.path.join(ROOT, "FRED_DFF.csv"))
status = {}
try:
    with open(os.path.join(ROOT, "FRED_DFEDTARL.csv"), encoding="utf-8") as f:
        lows = [r for r in csv.reader(f)][1:]
    with open(os.path.join(ROOT, "FRED_DFEDTARU.csv"), encoding="utf-8") as f:
        highs = [r for r in csv.reader(f)][1:]
    last_l = lows[-1] if lows else ["-", "-"]
    last_h = highs[-1] if highs else ["-", "-"]
    last_effr = effr_rows[-1] if effr_rows else ["-", "-"]
    status = {"low": last_l[1], "high": last_h[1], "effr": last_effr[1],
              "effr_date": last_effr[0], "date": dt.date.today().isoformat()}
except Exception:
    pass


def esc(s):
    return html.escape(str(s))


rows_html = ""
for fname, desc in FILES:
    n, first, last = stats(os.path.join(ROOT, fname))
    url = f"https://raw.githubusercontent.com/banana815/financial-info/main/{fname}"
    rows_html += (f"<tr><td><a href='{url}'>{esc(fname)}</a></td>"
                  f"<td>{esc(desc)}</td><td>{first} → {last}</td>"
                  f"<td style='text-align:right'>{n:,}</td></tr>\n")

status_html = ""
if status:
    status_html = f"""
    <div class="status">
      <div><span>Target Range</span><b>{esc(status['low'])}% – {esc(status['high'])}%</b></div>
      <div><span>EFFR (as of {esc(status['effr_date'])})</span><b>{esc(status['effr'])}%</b></div>
      <div><span>Updated</span><b>{esc(status['date'])}</b></div>
    </div>"""

page = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Federal Funds Rate &amp; FOMC Data</title>
<style>
  body {{ font-family: -apple-system, "Segoe UI", Roboto, "PingFang SC", sans-serif;
         margin: 0; background: #f6f8fa; color: #24292f; }}
  header {{ background: #0d1117; color: #fff; padding: 28px 24px; }}
  header h1 {{ margin: 0 0 6px; font-size: 24px; }}
  header p {{ margin: 0; color: #8b949e; }}
  main {{ max-width: 900px; margin: 24px auto; padding: 0 16px; }}
  .status {{ display: flex; gap: 16px; flex-wrap: wrap; margin-bottom: 20px; }}
  .status div {{ background: #fff; border: 1px solid #d0d7de; border-radius: 8px;
                 padding: 14px 18px; flex: 1; min-width: 180px; }}
  .status span {{ display: block; color: #57606a; font-size: 12px; margin-bottom: 4px; }}
  .status b {{ font-size: 20px; }}
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
  <p>Effective Federal Funds Rate · target range · FOMC decisions/statements/minutes</p>
</header>
<main>
{status_html}
  <h2>Data Files</h2>
  <table>
    <tr><th>File</th><th>Description</th><th>Date Range</th><th>Records</th></tr>
{rows_html}
  </table>
  <footer>Auto-generated from the repository CSV files · 每日由 GitHub Actions 自动更新</footer>
</main>
</body>
</html>
"""
with open(os.path.join(OUT, "index.html"), "w", encoding="utf-8") as f:
    f.write(page)
print(f"已生成 {os.path.join(OUT, 'index.html')}（{len(page)} 字节）")
