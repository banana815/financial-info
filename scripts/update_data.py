#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
update_data.py — 每日更新联邦基金利率 / EFFR / FOMC 数据，并刷新 README.md 统计。

数据源（均无需 API key）:
  - FRED:   https://fred.stlouisfed.org/graph/fredgraph.csv?id=<SERIES>
  - 美联储: https://www.federalreserve.gov/  (FOMC 决议声明 / 会议纪要 / 日历)

用法:
  python3 scripts/update_data.py              # 全量更新（幂等，可每日运行）
  python3 scripts/update_data.py --readme-only  # 只根据现有 CSV 刷新 README 统计

该脚本被设计为幂等：重复运行不会产生重复行（按现有文件最大日期增量追加）。
任何网络/解析失败都会中止并保留现有数据文件不变。
"""

import argparse
import bisect
import csv
import datetime as dt
import html
import html.parser
import os
import re
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UA = "Mozilla/5.0 (financial-info auto-update; +https://github.com/banana815/financial-info)"


def log(msg):
    print(f"[{dt.datetime.now():%Y-%m-%d %H:%M:%S}] {msg}", flush=True)


# ---------------------------------------------------------------------------
# HTTP / FRED helpers
# ---------------------------------------------------------------------------

def http_get(url, timeout=30, retries=3):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except Exception as e:
            last_err = e
            if attempt < retries:
                time.sleep(2 * attempt)
    raise last_err


def fetch_fred(series_id):
    """返回 [(date_str, value_str)]，过滤缺失值（'' 或 '.'）。"""
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
    text = http_get(url)
    rows = []
    for line in text.splitlines()[1:]:  # 跳过 header
        if not line.strip():
            continue
        parts = line.split(",")
        if len(parts) < 2:
            continue
        date, val = parts[0].strip(), parts[1].strip()
        if not date or val in ("", "."):
            continue
        rows.append((date, val))
    return rows


# ---------------------------------------------------------------------------
# Local CSV helpers
# ---------------------------------------------------------------------------

def read_csv(path, skip_comment=True):
    """返回 (header, data_rows)；data_rows 为每行的字段列表。"""
    header, data = None, []
    with open(path, newline="", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.rstrip("\r\n")
            if not line.strip():
                continue
            if skip_comment and line.lstrip().startswith("#"):
                continue
            fields = next(csv.reader([line]))
            if header is None:
                header = fields
            else:
                data.append(fields)
    return header, data


def write_csv(path, header, rows):
    """原子写入：先写临时文件再 os.replace，避免中途崩溃留下半截文件。"""
    tmp = path + ".tmp"
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)
    os.replace(tmp, path)


def append_csv_rows(path, rows):
    """安全追加行：确保文件以换行结尾。"""
    with open(path, "rb") as f:
        f.seek(0, os.SEEK_END)
        if f.tell() > 0:
            f.seek(-1, os.SEEK_END)
            last = f.read(1)
        else:
            last = b"\n"
    with open(path, "a", newline="", encoding="utf-8") as f:
        if last != b"\n":
            f.write("\n")
        w = csv.writer(f, lineterminator="\n")
        w.writerows(rows)


def file_max_date(path, date_col=0):
    """返回文件数据区的最大日期字符串（跳过注释与 header）。"""
    maxd = None
    with open(path, newline="", encoding="utf-8", errors="replace") as f:
        first = True
        for line in f:
            line = line.rstrip("\r\n")
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            if first:
                first = False
                continue  # header
            d = line.split(",")[date_col].strip()
            if d and (maxd is None or d > maxd):
                maxd = d
    return maxd


# ---------------------------------------------------------------------------
# FRED 系列定义
# ---------------------------------------------------------------------------

# 每日核心利率（用于更新 FRED_*.csv 与派生文件）
DAILY_SERIES = {
    "DFF":      "FRED_DFF.csv",
    "EFFR":     None,                      # EFFR 无独立 FRED_*.csv，用于派生文件
    "DFEDTAR":  "FRED_DFEDTAR.csv",
    "DFEDTARL": "FRED_DFEDTARL.csv",
    "DFEDTARU": "FRED_DFEDTARU.csv",
}

# 补充经济数据（FRED 官方 CSV 端点，无需 key）
SUPP_SERIES = {
    "CPIAUCSL": ("FRED_CPIAUCSL.csv", "Consumer Price Index (CPI)", "Monthly"),
    "UNRATE":   ("FRED_UNRATE.csv", "Unemployment Rate", "Monthly"),
    "GDPC1":    ("FRED_GDPC1.csv", "Real GDP", "Quarterly"),
    "GDPPOT":   ("FRED_GDPPOT.csv", "Potential GDP", "Quarterly"),
    "PAYEMS":   ("FRED_PAYEMS.csv", "Nonfarm Payrolls", "Monthly"),
    "PCEPILFE": ("FRED_PCEPILFE.csv", "Core PCE Price Index", "Monthly"),
    "HSN1F":    ("FRED_HSN1F.csv", "Housing Starts", "Monthly"),
    "RRSFS":    ("FRED_RRSFS.csv", "Real Retail Sales", "Monthly"),
}

CALCFI_HEADER_COMMENT = """# Federal Funds Rate
# Source: Federal Reserve via FRED (DFF)
# Primary URL: https://fred.stlouisfed.org/series/DFF
# Canonical: https://calcfi.app/data/interest-rates/federal-funds-rate
# Retrieved: {retrieved}
# License: CC-BY-4.0 (attribute to CalcFi + primary source when citing)"""


# ---------------------------------------------------------------------------
# Target range lookup
# ---------------------------------------------------------------------------

class TargetMap:
    """按日期查找当时生效的 DFEDTARL / DFEDTARU 值。"""

    def __init__(self, rows_low, rows_high):
        # rows: [(date, value_str)]
        self.dates = []
        self.lows = []
        self.highs = {}
        for d, v in rows_low:
            self.dates.append(d)
            self.lows.append(float(v))
        for d, v in rows_high:
            self.highs[d] = float(v)

    def get(self, date):
        """返回 (low, high)；若 date 前无 target 数据返回 None。"""
        i = bisect.bisect_right(self.dates, date) - 1
        if i < 0:
            return None
        d = self.dates[i]
        high = self.highs.get(d)
        return (self.lows[i], high)


def fmt_target(x):
    """与既有数据一致的 target 值格式：去尾零但至少保留 1 位小数（0.0 / 3.5 / 4.25）。"""
    s = f"{x:.2f}"
    s = s.rstrip("0").rstrip(".")
    if "." not in s:
        s += ".0"
    return s


# ---------------------------------------------------------------------------
# FOMC helpers
# ---------------------------------------------------------------------------

class DivExtractor(html.parser.HTMLParser):
    """提取包含指定 class 的 <div> 的完整内容（正确处理嵌套 div）。"""

    def __init__(self, target_class):
        super().__init__()
        self.target = target_class
        self.depth = 0
        self.capture = False
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag != "div":
            return
        classes = dict(attrs).get("class", "").split()
        if not self.capture and self.target in classes:
            self.capture = True
            self.depth = 1
        elif self.capture:
            self.depth += 1

    def handle_endtag(self, tag):
        if tag == "div" and self.capture:
            self.depth -= 1
            if self.depth == 0:
                self.capture = False

    def handle_data(self, data):
        if self.capture:
            self.parts.append(data)


def extract_release_text(page):
    """从美联储新闻发布页提取正文文本（col-md-8 容器）。"""
    p = DivExtractor("col-md-8")
    p.feed(page)
    text = " ".join(p.parts)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        text = re.sub(r"<[^>]+>", " ", page)
        text = html.unescape(text)
        text = re.sub(r"\s+", " ", text).strip()
    return text


def fomc_decision_from_text(text, prev_low, new_low):
    """判断 decision / change_bp：先看声明文本，幅度用 DFEDTARL 变化，文本兜底 ±25。
    文本优先可避免 DFEDTAR 更新滞后（声明日 delta 仍为 0）时误判为 Hold。"""
    t = text.lower()
    delta = None
    if new_low is not None and prev_low is not None:
        delta = round((new_low - prev_low) * 100)
    if "decided to maintain the target range" in t or "decided to keep the target range" in t:
        return "Hold", 0
    if "decided to lower the target range" in t:
        return "Cut", delta if (delta is not None and delta < 0) else -25
    if "decided to raise the target range" in t:
        return "Hike", delta if (delta is not None and delta > 0) else 25
    if delta is not None and delta != 0:
        return ("Cut" if delta < 0 else "Hike"), delta
    return "Hold", 0


def parse_press_date(page):
    """从页面提取 'Month D, YYYY' 形式的日期，取最大者（对 minutes 页即发布日期）。"""
    months = "(?:January|February|March|April|May|June|July|August|September|October|November|December)"
    found = re.findall(rf"{months} [\d]{{1,2}}, [\d]{{4}}", page)
    parsed = []
    for s in found:
        try:
            parsed.append(dt.datetime.strptime(s, "%B %d, %Y").date())
        except ValueError:
            continue
    return max(parsed) if parsed else None


# ---------------------------------------------------------------------------
# 更新步骤
# ---------------------------------------------------------------------------

def step_fred_files():
    """全量刷新 FRED_*.csv（Date,Value 格式）。返回核心系列数据。"""
    data = {}
    for sid in list(DAILY_SERIES) + list(SUPP_SERIES):
        log(f"下载 FRED 系列 {sid} ...")
        rows = fetch_fred(sid)
        if not rows:
            raise RuntimeError(f"FRED 系列 {sid} 返回空数据，中止以避免覆盖现有文件")
        data[sid] = rows
        fname = DAILY_SERIES.get(sid)
        if fname is None and sid in SUPP_SERIES:
            fname = SUPP_SERIES[sid][0]
        if fname:
            write_csv(os.path.join(ROOT, fname), ["Date", "Value"],
                      [(d, v) for d, v in rows])
            log(f"  已写入 {fname}: {len(rows)} 条, {rows[0][0]} → {rows[-1][0]}")
    return data


def step_calcfli_dff(dff_rows):
    """重建 DFF_federal_funds_effective_rate_daily.csv（注释头 + date,value,unit）。"""
    path = os.path.join(ROOT, "DFF_federal_funds_effective_rate_daily.csv")
    header = ["date", "value", "unit"]
    lines = [CALCFI_HEADER_COMMENT.format(retrieved=dt.datetime.now(dt.timezone.utc)
                                          .isoformat().replace("+00:00", "Z"))]
    lines.append(",".join(header))
    lines += [f"{d},{v},percent" for d, v in dff_rows]
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    log(f"已重建 {os.path.basename(path)}: {len(dff_rows)} 条, {dff_rows[0][0]} → {dff_rows[-1][0]}")


def file_order(path, date_col=0):
    """返回文件数据区的排列方向：'asc' / 'desc'（比较前两条不同日期的数据行）。"""
    with open(path, newline="", encoding="utf-8", errors="replace") as f:
        reader = csv.reader(f)
        dates = []
        first_line = True
        for row in reader:
            if not row or not row[0].strip() or row[0].lstrip().startswith("#"):
                continue
            if first_line:
                first_line = False
                continue
            d = row[date_col].strip()
            if d and (not dates or d != dates[-1]):
                dates.append(d)
                if len(dates) >= 2:
                    break
    if len(dates) < 2:
        return "asc"
    return "desc" if dates[0] > dates[1] else "asc"


def step_incremental(effr_rows, target_map):
    """增量追加 EFFR 相关派生文件（Master / EFFR_simplified / EFFR_nyfed / target_range）。"""
    effr = {d: float(v) for d, v in effr_rows}

    def append_after(path, build_row, date_col=0):
        maxd = file_max_date(path, date_col)
        new = []
        for d, v in effr_rows:
            if d <= maxd:
                continue
            row = build_row(d, float(v))
            if row is not None:
                new.append(row)
        if new:
            header, data = read_csv(path)
            # 保持文件既有的排列方向（Master 升序；EFFR 派生文件降序，最新在前）
            if file_order(path, date_col) == "desc":
                # 新行需按降序（最新在前）插入顶部
                data = list(reversed(new)) + data
                note = f"插入顶部 {len(new)} 条"
            else:
                data = data + new
                note = f"追加 {len(new)} 条"
            write_csv(path, header, data)
            log(f"  {os.path.basename(path)}: {note} ({new[-1][0]} → {new[0][0]})")
        else:
            log(f"  {os.path.basename(path)}: 已是最新（≤ {maxd}）")

    # Master_Federal_Funds_Rate_Daily.csv
    def master_row(d, v):
        t = target_map.get(d)
        if t is None or t[1] is None:
            return [d, f"{v:.2f}", "NYFED_EFFR", "", "", "", ""]
        low, high = t
        return [d, f"{v:.2f}", "NYFED_EFFR", "", fmt_target(low), fmt_target(high), "NYFED"]

    # EFFR_simplified.csv: date,rate,target_low,target_high
    def simp_row(d, v):
        t = target_map.get(d)
        low = fmt_target(t[0]) if t else ""
        high = fmt_target(t[1]) if t and t[1] is not None else ""
        return [d, f"{v:.2f}", low, high]

    # EFFR_nyfed_with_target_range.csv: 15 列，仅填可得字段
    def nyfed_row(d, v):
        t = target_map.get(d)
        if t is None or t[1] is None:
            return None  # 该文件只在 target range 制下有完整语义
        return [d, "", "", "", "", "", "", "", f"{v:.2f}", "", "", fmt_target(t[0]), fmt_target(t[1]), "EFFR", ""]

    # DFEDTAR_target_range_from_nyfed.csv: date,DFEDTARL,DFEDTARU,EFFR
    def trange_row(d, v):
        t = target_map.get(d)
        if t is None or t[1] is None:
            return None
        return [d, fmt_target(t[0]), fmt_target(t[1]), f"{v:.2f}"]

    log("增量更新 EFFR 派生文件:")
    append_after(os.path.join(ROOT, "Master_Federal_Funds_Rate_Daily.csv"), master_row)
    append_after(os.path.join(ROOT, "EFFR_simplified.csv"), simp_row)
    append_after(os.path.join(ROOT, "EFFR_nyfed_with_target_range.csv"), nyfed_row)
    append_after(os.path.join(ROOT, "DFEDTAR_target_range_from_nyfed.csv"), trange_row)


def comm_has(comm_path, date, type_):
    """检查 FOMC_communications 中是否已有该 (date, type) 记录（防重复追加）。"""
    with open(comm_path, newline="", encoding="utf-8", errors="replace") as f:
        for row in csv.reader(f):
            if len(row) >= 3 and row[0].strip() == date and row[2].strip() == type_:
                return True
    return False


def read_csv_full(path):
    """流式解析 CSV（正确处理多行引号字段），返回 (header, data)。"""
    header, data = None, []
    with open(path, newline="", encoding="utf-8", errors="replace") as f:
        for row in csv.reader(f):
            if not row or not row[0].strip():
                continue
            if row[0].lstrip().startswith("#"):
                continue
            if header is None:
                header = row
            else:
                data.append(row)
    return header, data


def append_comm(comm_path, row):
    """按文件既有排列方向追加 communications 行（降序文件插顶部）。"""
    if file_order(comm_path) == "desc":
        header, data = read_csv_full(comm_path)
        write_csv(comm_path, header, [row] + data)
    else:
        append_csv_rows(comm_path, [row])


def step_fomc(effr_rows, target_map):
    """FOMC 决议 / 声明 / 纪要 / 日历更新。"""
    decisions_path = os.path.join(ROOT, "FOMC_Rate_Decisions.csv")
    extended_path = os.path.join(ROOT, "FOMC_Rate_Decisions_Extended.csv")
    comm_path = os.path.join(ROOT, "FOMC_communications_vtasca.csv")

    _, dec_rows = read_csv(decisions_path)
    # 注意：FOMC_Rate_Decisions.csv 为降序（最新在前）
    latest = max(dec_rows, key=lambda r: r[0])
    last_dec_date = latest[0]
    log(f"FOMC 决议最新: {last_dec_date}")

    # 从日历页提取所有决议页链接
    cal = http_get("https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm")
    links = sorted(set(re.findall(r"monetary(20\d{6})a\.htm", cal)))
    new_dates = [d for d in links if d > last_dec_date.replace("-", "")]
    if not new_dates:
        log("FOMC: 无新决议")
    else:
        for ymd in new_dates:
            date = f"{ymd[:4]}-{ymd[4:6]}-{ymd[6:]}"
            url = f"https://www.federalreserve.gov/newsevents/pressreleases/monetary{ymd}a.htm"
            log(f"FOMC: 抓取 {date} 决议 ...")
            page = http_get(url)
            text = extract_release_text(page)
            if not text:
                log(f"  ! 无法提取 {url} 正文，跳过")
                continue
            # change_bp 用 DFEDTARL 在决议日相对前值的变化
            t_now = target_map.get(date)
            prev = target_map.get(latest[0])
            new_low = t_now[0] if t_now else None
            prev_low = prev[0] if prev else None
            decision, change = fomc_decision_from_text(text, prev_low, new_low)
            if new_low is not None and t_now and t_now[1] is not None:
                trange = f"{t_now[0]:.2f}-{t_now[1]:.2f}"
            else:
                trange = latest[3]
            cum = int(latest[4]) + change
            new_row = [date, decision, str(change), trange, str(cum)]
            dec_rows.insert(0, new_row)  # 保持降序
            latest = new_row
            log(f"  {date} {decision} {change:+d}bp → {trange} (cum {cum})")

            # Extended 文件
            _, ext_rows = read_csv(extended_path)
            ext_cum = int(ext_rows[-1][4]) + change
            ext_rows.append([date, decision, str(change), trange, str(ext_cum), "federalreserve.gov"])
            write_csv(extended_path, ["meeting_date", "decision", "change_bp",
                                      "target_rate_or_range", "cumulative_change_bp", "source"],
                      ext_rows)
            log(f"  FOMC_Rate_Decisions_Extended.csv: 追加 {date}")

            # 声明全文（先查重，防崩溃后重复追加）
            if comm_has(comm_path, date, "Statement"):
                log(f"  Statement ({date}) 已存在，跳过")
            else:
                append_comm(comm_path, [date, date, "Statement", text])
                log(f"  FOMC_communications_vtasca.csv: 追加 Statement ({date})")

            # 会议纪要（如有）
            min_url = f"https://www.federalreserve.gov/monetarypolicy/fomcminutes{ymd}.htm"
            try:
                min_page = http_get(min_url)
                min_text = extract_release_text(min_page)
                rd = parse_press_date(min_page)
                rel = rd.isoformat() if rd else dt.date.today().isoformat()
                if min_text and "Page not found" not in min_text:
                    if comm_has(comm_path, date, "Minute"):
                        log(f"  Minute ({date}) 已存在，跳过")
                    else:
                        append_comm(comm_path, [date, rel, "Minute", min_text])
                        log(f"  FOMC_communications_vtasca.csv: 追加 Minute ({date}, rel {rel})")
                else:
                    log(f"  {date} 纪要尚未发布")
            except Exception as e:
                log(f"  {date} 纪要抓取失败: {e}")

        write_csv(decisions_path, ["meeting_date", "decision", "change_bp",
                                   "target_rate_or_range", "cumulative_change_since_2003"],
                  dec_rows)
        log(f"FOMC_Rate_Decisions.csv: 已更新，最新决议 {dec_rows[0][0]}")

    # 日历：仅提示新年份（完整日历年底发布）
    if re.search(r"\b2028\b", cal):
        log("FOMC 日历: 页面已含 2028 占位，完整日历发布后需人工确认（2021-2027 已完整）")


# ---------------------------------------------------------------------------
# README 统计
# ---------------------------------------------------------------------------

PRIMARY_TABLE = [
    ("Master_Federal_Funds_Rate_Daily.csv", "Combined daily rate with target range", "Daily"),
    ("DFF_federal_funds_effective_rate_daily.csv", "Federal Funds Effective Rate (DFF) from CalcFi/FRED", "Daily"),
    ("EFFR_nyfed_with_target_range.csv", "EFFR from NY Fed with all columns", "Daily"),
    ("EFFR_simplified.csv", "EFFR simplified (date, rate, target_low, target_high)", "Daily"),
    ("FRED_DFF.csv", "Federal Funds Effective Rate from FRED", "Daily"),
]

TARGET_TABLE = [
    ("FRED_DFEDTAR.csv", "Target Federal Funds Rate (single rate, pre-2008)", "Daily"),
    ("FRED_DFEDTARL.csv", "Target Range Lower Limit (post-2008)", "Daily"),
    ("FRED_DFEDTARU.csv", "Target Range Upper Limit (post-2008)", "Daily"),
    ("DFEDTAR_target_range_from_nyfed.csv", "Target range extracted from NY Fed EFFR data", "Daily"),
]

FOMC_TABLE = [
    ("FOMC_Rate_Decisions.csv", "Official FOMC rate decisions"),
    ("FOMC_Rate_Decisions_Extended.csv", "All FOMC meetings 1982-2026 (pre-2003 derived from DFEDTAR)"),
    ("FOMC_Meeting_Calendars.csv", "FOMC meeting schedule (all official meetings since 1960)"),
    ("FOMC_communications_vtasca.csv", "FOMC statements and minutes (full text, official archive)"),
    ("final_fed_data.csv", "FOMC meeting-level data with analysis (static research snapshot)"),
]


def file_stats(path, date_col=0):
    """返回 (records, first_date, last_date)。用 csv.reader 正确处理多行文本字段。"""
    n, first, last = 0, None, None
    with open(path, newline="", encoding="utf-8", errors="replace") as f:
        reader = csv.reader(f)
        first_line = True
        for row in reader:
            if not row or not row[0].strip():
                continue
            if row[0].lstrip().startswith("#"):
                continue
            if first_line:
                first_line = False
                continue
            d = row[date_col].strip()
            if d:
                if first is None or d < first:
                    first = d
                if last is None or d > last:
                    last = d
            n += 1
    return n, first, last


def yr(d):
    return d[:4]


def render_table(entries, stat):
    lines = []
    for fname, desc, *freq in entries:
        n, first, last = stat[fname]
        date_range = f"{yr(first)}-{yr(last)}" if first else "—"
        if freq:
            lines.append(f"| `{fname}` | {desc} | {freq[0]} | {date_range} | {n:,} |")
        else:
            lines.append(f"| `{fname}` | {desc} | {date_range} | {n:,} |")
    return lines


def update_readme(stat, effr_date, effr_val, target_low, target_high, today):
    readme = os.path.join(ROOT, "README.md")
    with open(readme, encoding="utf-8") as f:
        text = f.read()

    # --- Data Summary 区 ---
    supp_lines = []
    for sid, (fname, desc, freq) in SUPP_SERIES.items():
        n, first, last = stat[fname]
        supp_lines.append(f"| `{fname}` | {desc} | {freq} | {yr(first)}-{yr(last)} | {n:,} |")

    summary = f"""## Data Summary

### Primary Rate Data

| File | Description | Frequency | Date Range | Records |
|------|-------------|-----------|------------|---------|
{chr(10).join(render_table(PRIMARY_TABLE, stat))}

### Target Rate Data

| File | Description | Frequency | Date Range | Records |
|------|-------------|-----------|------------|---------|
{chr(10).join(render_table(TARGET_TABLE, stat))}

### FOMC Data

| File | Description | Date Range | Records |
|------|-------------|------------|---------|
{chr(10).join(render_table(FOMC_TABLE, stat))}

### Supplementary Economic Data (from FRED)

| File | Description | Frequency | Date Range | Records |
|------|-------------|-----------|------------|---------|
{chr(10).join(supp_lines)}

"""

    text, n1 = re.subn(r"## Data Summary.*?(?=## Data Sources)", summary, text, flags=re.S)
    assert n1 == 1, "README 中未找到 ## Data Summary 区块"

    # --- Current Status 区 ---
    dec_path = os.path.join(ROOT, "FOMC_Rate_Decisions.csv")
    _, dec_rows = read_csv(dec_path)
    last_change = None
    for row in dec_rows:  # 降序：最新在前
        if row[1] != "Hold":
            last_change = row
            break
    if last_change:
        d = dt.date.fromisoformat(last_change[0])
        verb = "cut" if last_change[1] == "Cut" else ("hike" if last_change[1] == "Hike" else "change")
        desc = f"{last_change[2]}bp {verb} on {d.strftime('%B %-d, %Y')}"
    else:
        desc = "—"

    status = f"""## Current Status (as of {today.isoformat()})

- **Target Range**: {target_low:.2f}% – {target_high:.2f}%
- **Effective Rate (EFFR)**: {effr_val:.2f}% (as of {effr_date})
- **Last Change**: {desc}
- **Current Cycle**: Rate cutting cycle (since September 2024)

_此节由 `scripts/update_data.py` 自动生成，每日定时刷新。_

"""
    text, n2 = re.subn(r"## Current Status.*?(?=## Notes)", status, text, flags=re.S)
    assert n2 == 1, "README 中未找到 ## Current Status 区块"

    with open(readme, "w", encoding="utf-8") as f:
        f.write(text)
    log("README.md 已更新（Data Summary + Current Status）")


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--readme-only", action="store_true", help="仅根据现有 CSV 刷新 README")
    args = ap.parse_args()

    if args.readme_only:
        refresh_readme()
        return

    log("==== 开始每日数据更新 ====")
    fred = step_fred_files()

    dff_rows = fred["DFF"]
    effr_rows = fred["EFFR"]
    tmap = TargetMap(fred["DFEDTARL"], fred["DFEDTARU"])

    step_calcfli_dff(dff_rows)
    step_incremental(effr_rows, tmap)
    try:
        step_fomc(effr_rows, tmap)
    except Exception as e:
        log(f"FOMC 更新失败（数据文件已更新，不影响）：{e}")

    refresh_readme()
    log("==== 更新完成 ====")


def refresh_readme():
    stat = {}
    for fname in [t[0] for t in PRIMARY_TABLE + TARGET_TABLE + FOMC_TABLE] + \
                 [v[0] for v in SUPP_SERIES.values()]:
        stat[fname] = file_stats(os.path.join(ROOT, fname))

    effr_rows = fetch_fred("EFFR")
    tmap = TargetMap(fetch_fred("DFEDTARL"), fetch_fred("DFEDTARU"))
    effr_date, effr_val = effr_rows[-1]
    t = tmap.get(effr_date)
    if t is None or t[1] is None:
        raise RuntimeError(f"无法确定 {effr_date} 的 target range，README 刷新中止")
    update_readme(stat, effr_date, float(effr_val), t[0], t[1], dt.date.today())


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log(f"致命错误: {e}")
        sys.exit(1)
