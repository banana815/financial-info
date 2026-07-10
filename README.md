# Federal Funds Rate & FOMC Data Collection

Comprehensive historical data for the Effective Federal Funds Rate, Federal Funds Rate target, and FOMC monetary policy decisions.

## Data Summary

### Primary Rate Data

| File | Description | Frequency | Date Range | Records |
|------|-------------|-----------|------------|---------|
| `Master_Federal_Funds_Rate_Daily.csv` | Combined daily rate with target range | Daily | 1976-2026 | 18,284 |
| `DFF_federal_funds_effective_rate_daily.csv` | Federal Funds Effective Rate (DFF) from CalcFi/FRED | Daily | 1954-2026 | 18,247 |
| `EFFR_nyfed_with_target_range.csv` | EFFR from NY Fed with all columns | Daily | 2000-2026 | 6,538 |
| `EFFR_simplified.csv` | EFFR simplified (date, rate, target_low, target_high) | Daily | 2000-2026 | 6,538 |
| `FRED_DFF.csv` | Federal Funds Effective Rate from FRED/Quandl | Daily | 1980-2021 | 15,205 |

### Target Rate Data

| File | Description | Frequency | Date Range | Records |
|------|-------------|-----------|------------|---------|
| `FRED_DFEDTAR.csv` | Target Federal Funds Rate (single rate, pre-2008) | Daily | 1982-2008 | 9,577 |
| `FRED_DFEDTARL.csv` | Target Range Lower Limit (post-2008) | Daily | 2008-2021 | 4,627 |
| `FRED_DFEDTARU.csv` | Target Range Upper Limit (post-2008) | Daily | 2008-2021 | 4,627 |
| `DFEDTAR_target_range_from_nyfed.csv` | Target range extracted from NY Fed EFFR data | Daily | 2008-2026 | 4,412 |

### FOMC Data

| File | Description | Date Range | Records |
|------|-------------|------------|---------|
| `FOMC_Rate_Decisions.csv` | Official FOMC rate decisions | 2003-2026 | 191 |
| `FOMC_Rate_Decisions_Extended.csv` | Extended FOMC decisions (derived + official) | 1982-2026 | includes pre-2003 |
| `FOMC_Meeting_Calendars.csv` | FOMC meeting schedule | 2021-2027 | 56 |
| `FOMC_communications_vtasca.csv` | FOMC statements and minutes (full text) | 1982-2026 | 66,760 |
| `final_fed_data.csv` | FOMC meeting-level data with analysis | 1993-2021 | 248 |

### Supplementary Economic Data (from FRED)

| File | Description | Frequency |
|------|-------------|-----------|
| `FRED_CPIAUCSL.csv` | Consumer Price Index (CPI) | Monthly |
| `FRED_UNRATE.csv` | Unemployment Rate | Monthly |
| `FRED_GDPC1.csv` | Real GDP | Quarterly |
| `FRED_GDPPOT.csv` | Potential GDP | Quarterly |
| `FRED_PAYEMS.csv` | Nonfarm Payrolls | Monthly |
| `FRED_PCEPILFE.csv` | Core PCE Price Index | Monthly |
| `FRED_HSN1F.csv` | Housing Starts | Monthly |
| `FRED_RRSFS.csv` | Real Retail Sales | Monthly |

## Data Sources

1. **CalcFi Open Data** (datahub.io/calcfi): Daily DFF data from 1954, CC-BY-4.0
   - Source: `https://datahub.io/calcfi/calcfi-federal-funds-rate`
   
2. **Federal Reserve Bank of New York**: EFFR data with target range (2000-present)
   - API: `https://markets.newyorkfed.org/api/rates/unsecured/effr/`
   
3. **Federal Reserve Board**: FOMC calendars and policy actions
   - Source: `https://www.federalreserve.gov/monetarypolicy/openmarket.htm`
   - Calendars: `https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm`
   
4. **FRED (Federal Reserve Economic Data)** via Quandl: Historical target rates and supplementary data
   - Source: `https://fred.stlouisfed.org/`
   - Downloaded from: michelleazee/fed_funds_rate (GitHub)
   
5. **vtasca/fed-statement-scraping** (GitHub): FOMC statement and minute texts
   - Source: `https://github.com/vtasca/fed-statement-scraping`

## Key Series IDs (FRED)

| Series ID | Name | Frequency |
|-----------|------|-----------|
| DFF | Federal Funds Effective Rate | Daily |
| EFFR | Effective Federal Funds Rate (NY Fed) | Daily |
| FEDFUNDS | Federal Funds Effective Rate | Monthly |
| DFEDTAR | Federal Funds Target Rate (historical, pre-2008) | Daily |
| DFEDTARL | Federal Funds Target Range - Lower Limit | Daily |
| DFEDTARU | Federal Funds Target Range - Upper Limit | Daily |

## Current Status (as of 2026-07-09)

- **Target Range**: 3.50% – 3.75%
- **Effective Rate (EFFR)**: 3.62%
- **Last Change**: -25bp cut on December 11, 2025
- **Current Cycle**: Rate cutting cycle (since September 2024)

## Notes

- Before December 2008, the Fed set a single target rate (not a range)
- The target range system began on December 16, 2008
- The zero lower bound period lasted from December 2008 to December 2015
- Pre-2003 FOMC decisions in the extended file are derived from DFEDTAR rate changes
- Some supplementary FRED data files only go up to 2021 (from the Quandl source)

## License

Data from FRED is subject to FRED's terms of use. CalcFi data is CC-BY-4.0.
Federal Reserve data is in the public domain. Please cite sources appropriately.
