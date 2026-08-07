#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一次性补全：
1) FOMC_Meeting_Calendars.csv 补 1960-2020（官方 fomchistorical 页面）
2) FOMC_communications_vtasca.csv 补 1994-1999 官方声明与纪要全文
"""
import csv, os, re, sys, datetime as dt
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from scripts.update_data import (ROOT, http_get, read_csv, write_csv, read_csv_full,
                                 append_csv_rows, extract_release_text, parse_press_date, log)

MEETINGS = os.path.join(ROOT, ".cache", "fomc_meetings_1960_2020.csv")


def load_meetings():
    with open(MEETINGS, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def backfill_calendar(meetings):
    """补 FOMC_Meeting_Calendars.csv：1960-2020（现有 2021-2027 保留）。"""
    path = os.path.join(ROOT, "FOMC_Meeting_Calendars.csv")
    hdr, existing = read_csv(path)  # 2021-2027 升序
    existing_dates = {r[2] for r in existing}
    new_rows = []
    for m in meetings:
        if m["start_date"] == "2003-09-15":
            continue  # 官方页面的重复条目（2003 年实际 9/16 一次）
        if m["start_date"] in existing_dates:
            continue
        note = m["note"]
        notes = f"{m['label']} meeting" + (f" ({note})" if note else "")
        new_rows.append([m["year"], "", m["start_date"], m["end_date"], m["has_sep"], notes])
    # 按年内日期编号
    by_year = {}
    for r in sorted(new_rows, key=lambda r: r[2]):
        by_year.setdefault(r[0], []).append(r)
    for y, rows in by_year.items():
        for i, r in enumerate(rows, 1):
            r[1] = str(i)
    all_rows = sorted(new_rows + existing, key=lambda r: r[2])
    write_csv(path, hdr, all_rows)
    log(f"FOMC_Meeting_Calendars.csv: 补 {len(new_rows)} 条历史会议，共 {len(all_rows)} 条 "
        f"({all_rows[0][2]} → {all_rows[-1][2]})")


def fetch_comm(year, end_date, url, kind):
    """抓取声明/纪要文本，返回 (Date, Release Date, Type, Text) 或 None。"""
    try:
        page = http_get("https://www.federalreserve.gov" + url, timeout=45)
    except Exception as e:
        log(f"  ! {url} 抓取失败: {e}")
        return None
    text = extract_release_text(page)
    if not text:
        log(f"  ! {url} 文本为空，跳过")
        return None
    if kind == "Statement":
        rel = end_date
    else:
        m = re.search(r"Released\s+([A-Za-z]+ \d{1,2}, \d{4})", page)
        if m:
            try:
                rel = dt.datetime.strptime(m.group(1), "%B %d, %Y").date().isoformat()
            except ValueError:
                rel = None
        else:
            rel = None
        if not rel:
            pd = parse_press_date(page)
            rel = pd.isoformat() if pd else end_date
    return [year, rel, kind, text]


def backfill_communications(meetings):
    """补 1994-1999 官方声明与纪要全文（追加到文件最旧端，保持降序）。"""
    path = os.path.join(ROOT, "FOMC_communications_vtasca.csv")
    hdr, data = read_csv_full(path)
    existing = {(r[0], r[2]) for r in data}
    new_rows = []
    for m in meetings:
        if not 1994 <= int(m["year"]) <= 1999:
            continue
        if m["statement_url"]:
            if (m["start_date"], "Statement") not in existing:
                r = fetch_comm(m["start_date"], m["end_date"], m["statement_url"], "Statement")
                if r:
                    new_rows.append(r)
        if m["minutes_url"]:
            if (m["start_date"], "Minute") not in existing:
                r = fetch_comm(m["start_date"], m["end_date"], m["minutes_url"], "Minute")
                if r:
                    new_rows.append(r)
    # 按 (Date desc, Release desc) 排序，追加到文件末尾（降序文件的最旧端）
    new_rows.sort(key=lambda r: (r[0], r[1] or ""), reverse=True)
    if new_rows:
        append_csv_rows(path, new_rows)
    log(f"FOMC_communications_vtasca.csv: 补 {len(new_rows)} 条 (1994-1999)，"
        f"共 {len(data) + len(new_rows)} 条 ({data[0][0]} → {new_rows[-1][0]})")
    # 摘要
    from collections import Counter
    c = Counter((r[0][:4], r[2]) for r in new_rows)
    for k in sorted(c): log(f"    {k[0]} {k[1]}: {c[k]}")


def main():
    meetings = load_meetings()
    log(f"载入官方会议清单 {len(meetings)} 条")
    backfill_calendar(meetings)
    backfill_communications(meetings)
    log("补全完成")


if __name__ == "__main__":
    main()
