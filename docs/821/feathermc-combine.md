# FeatherMC_combine

Combines and cleans wind data from a **Feather MC data logger** (ultrasonic anemometer). Converts UTC → local time using a deployment IANA time zone, and writes a cleaned MET file named with serial number and deployment date.

Part of the [821 pipeline](pipeline.md) — optional step before `ld821_to_nvspl.py` when merging wind into NVSPL.

## Features

- Select MET folder via GUI (raw logger CSVs auto-detected)
- Skips prior combined outputs and non-logger CSVs
- Deployment time zone picker (US zones curated at top of list)
- Cleans repeated headers
- UTC to local conversion with zone rules (DST) by default

## Prerequisites

- Python 3.9+, pandas, pytz (see `requirements.txt`)

## Inputs

- MET folder containing microSD logger CSV exports (`*MD.CSV` metadata files ignored for combine)
- Only files with `Date-Time (UTC)` and without `Date-Time (LOC)` are combined
- Prior combined outputs (`{serial} {YYYY-MM-DD HHMMSS}.csv`) are skipped

## Outputs

- Combined cleaned CSV written to the selected MET folder (e.g. `00000018 2026-07-09 125259.csv`)
- `feathermc_clean_*.log` in the same folder (UTC/local ranges, conversion mode, DST transitions in range, duplicate LOC warnings)

## Usage

1. Run `python FeatherMC_combine.py`
2. Browse to the MET folder
3. Enter **Serial Number** (autofill from Feather MC `*MD.CSV` metadata, or type manually), **Site ID**, and **Deployment Time Zone** (site and time zone may autofill when you browse the MET folder)
4. Leave **Apply time zone rules** checked unless you need a fixed offset from deployment start (see below)
5. Run combine

## Configurable settings

| Setting | Default | Notes |
|--------|---------|--------|
| Site name | `PARK001` | Optional log metadata |
| Serial | from `*MD.CSV` or user | Output filename prefix; first line `Anemometer MetaData Log, {serial}` |
| Time zone | `America/Denver` | IANA name; US list starts with New York, Chicago, Denver, **Phoenix**, **Shiprock** (Navajo Nation — DST inside Arizona), Los Angeles, Anchorage, Honolulu, then all other pytz zones |
| Apply time zone rules | **On** | Uses IANA rules including DST when the zone observes it |
| Uncheck rules | — | **Manual override**: fixed UTC offset from the **start** of the deployment (earliest UTC in the combined data). Use when field clocks stayed on the offset at deployment start across a DST change (e.g. SLM not updated). Does not duplicate or skip local hours at transitions. |

### Phoenix vs Denver vs Shiprock

- **America/Denver** — Mountain Time with DST (MDT/MST).
- **America/Phoenix** — Arizona (no DST); MST year-round under zone rules.
- **America/Shiprock** — Navajo Nation within Arizona; observes DST like Denver when zone rules are on.

Pick the zone that matches where the logger was deployed, not where data are processed.

### Duplicate timestamps

After files are combined, rows with the **same UTC timestamp** are deduplicated (**first row kept**, in file order). The log reports how many were removed. We do **not** bump timestamps by a second to keep extra rows; that would misalign wind with SPL.

If duplicate **local** timestamps remain with **zone rules on** (log warns with **distinct UTC** — DST fall-back), NVSPL merge on `Date-Time (LOC)` can still be ambiguous; review zone settings and the duplicate examples in the log. With **rules off**, local times use one offset from deployment start, so fall-back duplicate LOC from DST should not occur.

## Troubleshooting

- **No logger CSVs found** — folder may only contain prior combined outputs; check that raw microSD exports have `Date-Time (UTC)` and not `Date-Time (LOC)`
- **Wrong times in NVSPL** — confirm deployment zone (Phoenix vs Shiprock vs Denver), ensure zone rules are on unless you intentionally use fixed offset from deployment start, then re-run Feather MC combine and NVSPL
- **ST/DST mix in log** — expected when data span a transition with zone rules on; verify the selected zone
- **Duplicate LOC warnings** — see above; fix zone/override or accept risk for NVSPL merge
