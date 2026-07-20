
# LD821_to_NVSPL Script Documentation (with Diagrams)

## Overview
This script converts LD821 Time History CSV files to standard NVSPL hourly text files (54 columns) and optionally merges MET (wind) data from external data loggers.

---
## Workflow Diagram

```
LD821 Time History CSV
        |
        v
 +-----------------------+
 |  Parse & Normalize    |  --> Clean SPL dataframe
 +-----------------------+
        |
        v
MET CSV (optional)
        |
        v
 +-----------------------+
 |  Timestamp Align      |  --> Match MET samples to SPL seconds
 +-----------------------+
        |
        v
 +-----------------------+
 |  Merge SPL + MET      |  --> Add windspeed, winddir, temp
 +-----------------------+
        |
        v
 +-----------------------+
 | Generate NVSPL Files  |
 | one file per hour     |
 +-----------------------+
        |
        v
NVSPL__YYYY_MM_DD_HH.txt
```

---
## NVSPL Hourly File Structure

```
+--------------------------------------------------------------+
| Column Name            | Description                         |
+--------------------------------------------------------------+
| SiteID                 | Code for monitoring site            |
| DateTime               | YYYY-MM-DD HH:MM:SS                 |
| LAFmax                 | A-weighted SPL                       |
| LAFmin                 | ... (standard 54-col NVSPL schema)  |
| WindSpeed              | merged MET data (optional)          |
| WindDir                | merged MET data (optional)          |
| TempOut                | merged MET data (optional)          |
+--------------------------------------------------------------+
```

---
## User Configuration — ld821_to_nvspl.py

### Paths & Site Identity

**INPUT_CSV (string, required)**
Full path to LD821 Time History CSV.

**OUTPUT_DIR (string, required)**
Folder where hourly NVSPL files will be saved.

**SITE_ID (string, required)**
The monitoring site code.

---
### MET (Wind) Merge Controls

**MERGE_MET (bool)** — Whether wind should be merged.

**MET_CSV_PATH (string)** — Path to MET logger CSV.

**MET_TIMESTAMP_IDX (int)** — Timestamp column index.

**MET_WINDSPD_IDX (int)** — Wind speed column.

**MET_WINDDIR_IDX (int)** — Wind direction column.

**MET_EXTERNTEMP_IDX (int)** — External temperature column.

---
### Timestamp Semantics & Fill Strategy

Diagram: How timestamps affect bin alignment

```
MET Sample
|-------Interval--------|
^ start
        ^ center
                ^ end

start:   assign sample time at interval start
center:  shift sample left by half interval
end:     shift sample left by full interval
```

**MET_SAMPLE_STAMP** — 'start', 'center', 'end'

**FILL_METHOD** — 'bin', 'forward', 'nearest'

```
bin:     Assign SPL second into MET bin interval
forward: Carry last MET sample forward until next
nearest: Choose the closest MET sample per SPL second
```

**NEAREST_TOLERANCE_SEC** — allowable seconds difference for nearest sample.

**BACKFILL_BEFORE_FIRST** — whether to fill values before first MET sample.

---
### Units & Value Normalization

```
MET_SPEED_UNITS: mps or mph
CONVERT_MPH_TO_MPS: mph --> mps
Invalid speeds removed: {"39.9"}
```

---
## Example Configuration for Typical Deployment

```
MERGE_MET = True
MET_CSV_PATH = r".../MET_log.csv"
MET_TIMESTAMP_IDX = 5
MET_WINDSPD_IDX = 3
MET_WINDDIR_IDX = None
MET_EXTERNTEMP_IDX = None
MET_SAMPLE_STAMP = "start"
FILL_METHOD = "bin"
NEAREST_TOLERANCE_SEC = 2
BACKFILL_BEFORE_FIRST = False
MET_SPEED_UNITS = "mps"
CONVERT_MPH_TO_MPS = False
```

---
## Full Workflow Diagram (SPL + MET)

```
+------------------------+
| Load SPL CSV           |
+------------------------+
           |
           v
+------------------------+
| Validate schema        |
+------------------------+
           |
           v
+------------------------+
| Load MET CSV (optional)|
+------------------------+
           |
           v
+------------------------+
| Align timestamps       |
+------------------------+
           |
           v
+------------------------+
| Fill per-second MET    |
+------------------------+
           |
           v
+------------------------+
| Merge SPL + MET        |
+------------------------+
           |
           v
+------------------------+
| Export hourly NVSPL    |
+------------------------+
```

---
## Troubleshooting
- If MET fields are blank: check `MERGE_MET`, indices, encoding.
- If wind seems time-shifted: adjust `MET_SAMPLE_STAMP`.
- If SPL hours missing: verify SPL timestamps are contiguous.

