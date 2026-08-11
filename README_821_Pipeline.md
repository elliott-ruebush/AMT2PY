# LD 821-ENV processing

G4 Time History CSVs (+ optional Feather MC wind) → hourly **NVSPL** for AMT. Three **GUI** scripts; setup is in **`README.md`** → *Prepare your machine*.

Per-script reference: [`README_ld821_combine.md`](README_ld821_combine.md), [`README_FeatherMC_combine.md`](README_FeatherMC_combine.md), [`README_ld821_to_nvspl.md`](README_ld821_to_nvspl.md).

## Folder layout

```
MORUA2503_20260626/
├── AUDIO/      Song Meter .wav files
├── MET/        Feather MC wind logger CSVs (from microSD)
├── METADATA/   datasheets, photos
└── RAW/        G4 export folder(s) with Time History CSVs
```

Site name in the folder name should match what you enter in the scripts when applicable. Nested paths are fine (e.g. `2026 DENATRLA Triple Lakes\01 DATA\MET`); scripts use the folder you browse to.

## Step 0 — Download field data

Full SOP: **`README_DataDownload.md`**. Summary:

- **MET/** — copy Feather MC microSD `.csv` / `.md`; verify counts; clear card.
- **AUDIO/** — copy Song Meter `.wav` and summary files; verify; clear card.
- **RAW/** — G4 Utility: download deployment → **File → Export to CSV** → copy the export folder (OBA, Session Log, Settings, Summary, Time History CSVs) into `RAW/`.

## Step 1 — Combine wind data (optional)

```bash
python FeatherMC_combine.py
```

Browse to the MET folder; enter serial, timezone, and optional DST. Prior combined outputs are skipped automatically.

**Output:** cleaned CSV in `MET/` (e.g. `00000018 2026-07-09 125259.csv`) and `feathermc_clean_*.log`. Skip if not merging wind into NVSPL.

## Step 2 — Combine Time History CSVs

```bash
python ld821_combine.py
```

Browse to the folder with G4 Time History CSVs (usually `RAW/`). Enter **Site Name** for the output filename.

**Output:** `{site}_Time History.csv` and `combine_slm_*.log` in the browsed folder. Multi-subfolder layouts prompt for confirmation before combining.

## Step 3 — Convert to NVSPL

```bash
python ld821_to_nvspl.py
```

1. Browse to `{site}_Time History.csv` from step 2 — **Site ID** and **Output folder** autofill (`schemas/ld821_spl.py`).
2. Confirm output directory (e.g. new `NVSPL/` under the deployment).
3. For wind merge: **Merge MET Data** → `True`, browse the step 1 MET CSV. Column indices autofill from header names (`schemas/feathermc_met.py`). Defaults: `bin` fill, m/s, 10 s Feather MC intervals.
4. Run. GUI log shows progress and merge stats.

**Output:** `NVSPL_{SITE}_{YYYY_MM_DD_HH}.txt` per hour (3600 rows, 54 columns).

## Step 4 — AMT

Load NVSPL `.txt` files into AMT for graphing and analysis.

## Processing order

Steps 1 and 2 are independent (either order or parallel). Step 3 must be last.

```
G4 export → RAW/
                ↓
         ld821_combine.py  →  {site}_Time History.csv
                ↓
MET/ CSVs → FeatherMC_combine.py  →  cleaned MET CSV  (optional)
                ↓
         ld821_to_nvspl.py  →  NVSPL_*.txt
                ↓
              AMT
```

## Troubleshooting

- **Wrong timestamps in NVSPL** — re-check timezone/DST in Feather MC combine, then re-run NVSPL.
- **Blank wind columns** — confirm merge is on, MET path is the *combined* CSV, and column indices match the header (re-browse MET file to autofill).
- **Logs** — each combine script writes a timestamped log next to its output.
