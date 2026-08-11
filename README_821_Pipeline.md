# LD 821-ENV processing

Python scripts that take G4-exported Time History CSVs (and optional Feather MC wind data) and produce hourly NVSPL files for AMT. All three processing scripts open a GUI — there is nothing to edit in the source code before running.

## Setup

Python 3.9 or newer. Clone this repo, then create a virtual environment and install dependencies:

```bash
cd AMT2PY
python -m venv .venv
```

Activate it:

```bash
# Windows Command Prompt
.venv\Scripts\activate

# Git Bash (Windows)
source .venv/Scripts/activate

# macOS / Linux
source .venv/bin/activate
```

Then install packages:

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Run the scripts from the repo folder with the venv active. On Windows, Git Bash or Command Prompt both work:

```bash
python ld821_combine.py
python FeatherMC_combine.py
python ld821_to_nvspl.py
```

## Folder layout

Organize each deployment like this before processing:

```
MORUA2503_20260626/
├── AUDIO/      Song Meter .wav files
├── MET/        Feather MC wind logger CSVs (from microSD)
├── METADATA/   datasheets, photos
└── RAW/        G4 export folder(s) with Time History CSVs
```

Site name and deploy date in the folder name should match what you enter in the scripts.

## Step 0 — Download field data

**Feather MC (wind logger)**  
Copy all `.csv` and `.md` files from the microSD card into `MET/`. Verify file counts match, then clear the card and put it back in the logger.

**Song Meter**  
Copy `.wav` files and summary files into `AUDIO/`. Same verify-and-clear routine.

**821-env SPL meter (G4 Utility)**  
1. Disconnect power, mic cable, and battery plate. Connect via USB.  
2. Open G4 LD Utility, select the unit by serial number.  
3. Download the deployment, then open it and use **File → Export to CSV**.  
4. Find the export folder (default: `C:\Users\Public\Documents\PCB Piezotronics\G4\Meters\...`).  
5. Confirm the folder has OBA, Session Log, Settings, Summary, and one or more **Time History** CSVs (long deployments may have `Time History 1.csv`, `Time History 2.csv`, etc.).  
6. Copy the whole export folder into `RAW/`.

More detail on field download: `README_DataDownload.md` (821 sections; ignore the duplicate/conflicting copy instructions at the bottom — use `RAW/` only).

## Step 1 — Combine wind data (optional)

```bash
python FeatherMC_combine.py
```

1. Browse to `MET/` and select the wind CSV files (skip `.md` metadata files).  
2. Enter site name, deploy date (`YYYYMMDD`), logger serial number, and local timezone.  
3. Turn on DST adjustment if needed.  
4. Run.

**Output:** one cleaned CSV in `MET/`, named like `00000018 2026-07-09 125259.csv`, plus a log file `feathermc_clean_*.log`.

Skip this step if you are not merging wind into NVSPL.

## Step 2 — Combine Time History CSVs

```bash
python ld821_combine.py
```

1. Browse to the deployment folder or `RAW/` — the script finds Time History CSVs in all subfolders.  
2. Enter site name and deploy date.  
3. Run.

**Output:** `{site}_Time History.csv` and `combine_slm_*.log` in the folder you browsed to (not inside a subfolder). If files are found in multiple subfolders, you'll get a warning before combining.

## Step 3 — Convert to NVSPL

```bash
python ld821_to_nvspl.py
```

1. **Input CSV:** the combined file from step 2.  
2. **Output directory:** where you want hourly NVSPL files (e.g. a new `NVSPL/` folder in the deployment).  
3. **Site ID:** same site code used earlier.  
4. If merging wind, set **Merge MET Data** to True, browse to the cleaned MET CSV from step 1, and check the column indices match your file (defaults assume timestamp in column 5, wind speed in column 3).  
5. **Fill method:** `bin` repeats each MET sample across its interval; `forward` and `nearest` are alternatives if bin does not look right.  
6. Run.

**Output:** one file per hour: `NVSPL_{SITE}_{YYYY_MM_DD_HH}.txt` (3600 one-second rows, 54 columns). Progress and MET merge details appear in the GUI log window.

## Step 4 — AMT

Load the NVSPL `.txt` files into the original AMT application for graphing and analysis. These scripts stop at NVSPL creation.

## Typical order

Wind combine and SPL combine are independent — either order works, or run them in parallel. NVSPL conversion must come last.

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

## Logs and troubleshooting

Each combine script writes a timestamped log next to its output. If timestamps look wrong in NVSPL, check timezone and DST settings in Feather MC combine before re-running NVSPL. If wind columns are blank, open the MET CSV and confirm the column index numbers in the NVSPL GUI match the actual columns.

## Other docs

| Script | Detail doc |
|--------|------------|
| `ld821_combine.py` | `README_ld821_combine.md` |
| `FeatherMC_combine.py` | `README_FeatherMC_combine.md` |
| `ld821_to_nvspl.py` | `README_ld821_to_nvspl.md` |
