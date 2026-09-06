# Federal Funds Rate & FOMC Data Collection

Comprehensive historical data for the Effective Federal Funds Rate, Federal Funds Rate target, and FOMC monetary policy decisions.

## Data Summary

### Primary Rate Data

| File | Description | Frequency | Date Range | Records |
|------|-------------|-----------|------------|---------|
| `Master_Federal_Funds_Rate_Daily.csv` | Combined daily rate with target range | Daily | 1976-2026 | 18,324 |
| `DFF_federal_funds_effective_rate_daily.csv` | Federal Funds Effective Rate (DFF) from CalcFi/FRED | Daily | 1954-2026 | 26,363 |
| `EFFR_nyfed_with_target_range.csv` | EFFR from NY Fed with all columns | Daily | 2000-2026 | 6,578 |
| `EFFR_simplified.csv` | EFFR simplified (date, rate, target_low, target_high) | Daily | 2000-2026 | 6,578 |
| `FRED_DFF.csv` | Federal Funds Effective Rate from FRED | Daily | 1954-2026 | 26,363 |

### Target Rate Data

| File | Description | Frequency | Date Range | Records |
|------|-------------|-----------|------------|---------|
| `FRED_DFEDTAR.csv` | Target Federal Funds Rate (single rate, pre-2008) | Daily | 1982-2008 | 9,577 |
| `FRED_DFEDTARL.csv` | Target Range Lower Limit (post-2008) | Daily | 2008-2026 | 6,473 |
| `FRED_DFEDTARU.csv` | Target Range Upper Limit (post-2008) | Daily | 2008-2026 | 6,473 |
| `DFEDTAR_target_range_from_nyfed.csv` | Target range extracted from NY Fed EFFR data | Daily | 2008-2026 | 4,452 |

### FOMC Data

| File | Description | Date Range | Records |
|------|-------------|------------|---------|
| `FOMC_Rate_Decisions.csv` | Official FOMC rate decisions | 2003-2026 | 192 |
| `FOMC_Rate_Decisions_Extended.csv` | All FOMC meetings 1982-2026 (pre-2003 derived from DFEDTAR) | 1982-2026 | 453 |
| `FOMC_Meeting_Calendars.csv` | FOMC meeting schedule (all official meetings since 1960) | 1960-2027 | 674 |
| `FOMC_communications_vtasca.csv` | FOMC statements and minutes (full text, official archive) | 1994-2026 | 524 |
| `final_fed_data.csv` | FOMC meeting-level data with analysis (static research snapshot) | 1993-2021 | 247 |

### Supplementary Economic Data (from FRED)

| File | Description | Frequency | Date Range | Records |
|------|-------------|-----------|------------|---------|
| `FRED_CPIAUCSL.csv` | Consumer Price Index (CPI) | Monthly | 1947-2026 | 954 |
| `FRED_UNRATE.csv` | Unemployment Rate | Monthly | 1948-2026 | 943 |
| `FRED_GDPC1.csv` | Real GDP | Quarterly | 1947-2026 | 318 |
| `FRED_GDPPOT.csv` | Potential GDP | Quarterly | 1949-2036 | 352 |
| `FRED_PAYEMS.csv` | Nonfarm Payrolls | Monthly | 1939-2026 | 1,052 |
| `FRED_PCEPILFE.csv` | Core PCE Price Index | Monthly | 1959-2026 | 811 |
| `FRED_HSN1F.csv` | Housing Starts | Monthly | 1963-2026 | 763 |
| `FRED_RRSFS.csv` | Real Retail Sales | Monthly | 1992-2026 | 414 |

## Data Sources

1. **FRED (Federal Reserve Economic Data)**: Daily auto-update source for DFF, EFFR, DFEDTAR/DFEDTARL/DFEDTARU and supplementary series
   - Source: `https://fred.stlouisfed.org/graph/fredgraph.csv?id=<SERIES>` (no API key required)
   
2. **Federal Reserve Board**: FOMC calendars, policy statements and meeting minutes
   - Source: `https://www.federalreserve.gov/monetarypolicy/openmarket.htm`
   - Calendars: `https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm`
   - Statements: `https://www.federalreserve.gov/newsevents/pressreleases/monetary20XXXXXXa.htm`
   
3. **CalcFi Open Data** (datahub.io/calcfi): Historical daily DFF data from 1954, CC-BY-4.0
   - Source: `https://datahub.io/calcfi/calcfi-federal-funds-rate`
   
4. **Federal Reserve Bank of New York**: Original source of EFFR with target range (2000-present)
   - The `markets.newyorkfed.org` API is no longer reachable from this environment; daily updates now mirror EFFR via FRED
   
5. **vtasca/fed-statement-scraping** (GitHub): Historical FOMC statement and minute texts
   - Source: `https://github.com/vtasca/fed-statement-scraping`

## Automatic Updates

数据由 `scripts/update_data.py` 自动刷新并同步更新本 README 的统计与 Current Status：

- 每日自动拉取 FRED 系列（DFF / EFFR / DFEDTARL / DFEDTARU 及 8 个补充经济指标），增量追加到 Master 与各 EFFR/DFF 文件
- 自动检测 FOMC 新决议（声明 + 会议纪要全文，追加到 `FOMC_communications_vtasca.csv`）并更新 `FOMC_Rate_Decisions*.csv`
- 脚本幂等，可重复运行：`python3 scripts/update_data.py`

定时任务（二选一）：

- **cron**（本机）：`bash scripts/install_cron.sh`，配置见 `cron/financial-info-daily.cron`（每日 08:45 运行）
- **GitHub Actions**（推荐，无需本机常驻）：`.github/workflows/daily-update.yml` 每日 UTC 00:15 自动运行并提交更新

## Key Series IDs (FRED)

| Series ID | Name | Frequency |
|-----------|------|-----------|
| DFF | Federal Funds Effective Rate | Daily |
| EFFR | Effective Federal Funds Rate (NY Fed) | Daily |
| FEDFUNDS | Federal Funds Effective Rate | Monthly |
| DFEDTAR | Federal Funds Target Rate (historical, pre-2008) | Daily |
| DFEDTARL | Federal Funds Target Range - Lower Limit | Daily |
| DFEDTARU | Federal Funds Target Range - Upper Limit | Daily |

## Current Status (as of 2026-09-06)

- **Target Range**: 3.50% – 3.75%
- **Effective Rate (EFFR)**: 3.63% (as of 2026-09-03)
- **Last Change**: -25bp cut on December 10, 2025
- **Current Cycle**: Rate cutting cycle (since September 2024)

_此节由 `scripts/update_data.py` 自动生成，每日定时刷新。_

## Notes

- Before December 2008, the Fed set a single target rate (not a range)
- The target range system began on December 16, 2008
- The zero lower bound period lasted from December 2008 to December 2015
- Pre-2003 FOMC decisions in the extended file are derived from DFEDTAR rate changes; from 2003 they are official decisions, and from 1994 statements/minutes are official archive text
- FOMC post-meeting statements only became routine from 2000; 1994-1999 statements exist only for policy-action meetings (1996-02 to 1999-05 no statements were published). Minutes exist for every meeting since 1994
- Meeting calendars cover all official FOMC meetings 1960-2027 (1960-1981 meetings were more frequent; 1982-2020 from the Fed's fomchistorical archive, 2021+ from fomccalendars)
- `FOMC_Rate_Decisions.csv` covers official decisions 2003+; `FOMC_Rate_Decisions_Extended.csv` covers every meeting 1982-2026 (before Sep 1982 DFEDTAR data does not exist)
- `final_fed_data.csv` is a static research/analysis snapshot (1993-2021) requiring the original modeling pipeline to extend; it is not refreshed daily
- Note: the `cumulative_change_since_2003` column in `FOMC_Rate_Decisions.csv` is a historical snapshot and does not strictly follow a running-sum rule in all periods (only 2026 rows are maintained consistently by the auto-update)
- All FRED series files are refreshed daily from FRED's official CSV endpoint (previously the Quandl snapshot only went up to 2021)

## License

Data from FRED is subject to FRED's terms of use. CalcFi data is CC-BY-4.0.
Federal Reserve data is in the public domain. Please cite sources appropriately.
