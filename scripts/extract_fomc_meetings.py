#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一次性工具：从美联储官网提取 1960-2020 年 FOMC 历史会议清单与 1994-1999 声明/纪要链接。
输出到 .cache/fomc_meetings_1960_2020.csv。"""
import csv, os, re, sys, time, html, datetime as dt
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from scripts.update_data import http_get, ROOT

CACHE = os.path.join(ROOT, ".cache")
os.makedirs(CACHE, exist_ok=True)
OUT = os.path.join(CACHE, "fomc_meetings_1960_2020.csv")

MONTHS = {m: i + 1 for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July",
     "August", "September", "October", "November", "December"])}


ABBR_MONTHS = {m[:3].lower(): i + 1 for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July",
     "August", "September", "October", "November", "December"])}


def month_num(s):
    s = s.strip().lower()
    if s in ABBR_MONTHS:
        return ABBR_MONTHS[s]
    return MONTHS.get(s.capitalize())


def parse_meeting_date(s):
    """解析会议日期标签（含双空格 / 缩写月份 'Jan/Feb 31-1' / 跨月）。
    返回 (mon1, day1, mon2, day2, note)。"""
    note = ""
    m = re.search(r"\(([^)]+)\)", s)
    if m:
        note = m.group(1)
        s = s[: m.start()].strip()
    # 格式: [Month] D [- [Month] D]
    m = re.match(r"([A-Za-z/]+)\s+(\d+)(?:-\s*([A-Za-z/]+)\s+(\d+)|-\s*(\d+))?", s)
    if not m:
        return None
    m1s, d1, m2s, d2b, d2c = m.group(1), int(m.group(2)), m.group(3), m.group(4), m.group(5)
    if "/" in m1s:
        a, b = m1s.split("/", 1)
        mon1 = month_num(a)
        mon2 = month_num(b)  # 如 "Jan/Feb 31-1" = Jan 31 → Feb 1
    else:
        mon1 = month_num(m1s)
        mon2 = month_num(m2s) if m2s else mon1
    if mon1 is None:
        return None
    if d2b:
        day2 = int(d2b)
    elif d2c:
        day2 = int(d2c)
    else:
        day2 = d1
    return mon1, d1, mon2, day2, note


def extract_year_page(year):
    url = f"https://www.federalreserve.gov/monetarypolicy/fomchistorical{year}.htm"
    page = http_get(url, timeout=40)
    meetings = []
    # 每个会议是一个 panel（2011 年起 class 含 panel-padded）
    panels = re.split(r'<div class="panel[^"]*">', page)
    for p in panels[1:]:
        hm = re.search(r"<h5[^>]*>\s*(.+?)\s*Meeting - (\d{4})\s*</h5>", p)
        if not hm:
            continue
        label, yr = hm.group(1), int(hm.group(2))
        dm = parse_meeting_date(label)
        if not dm or yr != year:
            continue
        mon1, d1, mon2, d2, note = dm
        start = f"{yr:04d}-{mon1:02d}-{d1:02d}"
        end = f"{yr:04d}-{mon2:02d}-{d2:02d}"
        stmt = re.search(r'href="(/fomc/\d{8}default\.htm)"', p)
        mins = re.search(r'href="(/fomc/MINUTES/\d{4}/\d{8}min\.htm)"', p)
        has_sep = bool(re.search(r"Projections|projections|SEP", p))
        meetings.append({
            "year": yr, "label": label, "start_date": start, "end_date": end,
            "statement_url": stmt.group(1) if stmt else "",
            "minutes_url": mins.group(1) if mins else "",
            "has_sep": "Yes" if has_sep else "No",
            "note": note,
        })
    return meetings


def main():
    all_m = []
    for year in range(1960, 2021):
        for attempt in range(3):
            try:
                ms = extract_year_page(year)
                break
            except Exception as e:
                if attempt == 2:
                    print(f"!! {year}: {e}")
                    ms = []
                else:
                    time.sleep(3)
        print(f"{year}: {len(ms)} 次会议" + (f" (SEP x{sum(1 for m in ms if m['has_sep']=='Yes')})" if ms else ""))
        all_m.extend(ms)
        time.sleep(0.4)
    all_m.sort(key=lambda m: m["start_date"])
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["year", "label", "start_date", "end_date",
                                          "statement_url", "minutes_url", "has_sep", "note"])
        w.writeheader()
        w.writerows(all_m)
    print(f"\n共 {len(all_m)} 次会议 → {OUT}")
    # 摘要
    from collections import Counter
    print("按年分布:", dict(sorted(Counter(m['year'] for m in all_m).items())))


if __name__ == "__main__":
    main()
