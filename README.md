# Mirrored NSNSD Acoustic Monitoring Toolbox (AMT)

Python ports of core **NSNSD Acoustic Monitoring Toolbox (AMT)** workflows — originally a C# app for processing, visualizing, and summarizing acoustic data. This repo replaces much of [Type1-821envtools](https://github.com/emeyer34/Type1-821envtools) by producing **NVSPL in Python** and supporting flexible wind-data merge, without reformatting raw data for AMT first.

**821‑env:** combine G4 Time History CSVs and optional Feather MC wind data → hourly NVSPL for AMT.  
**LD 831:** merge logger folders into `.831` files and convert to NVSPL (CLI / edit-constants scripts).

All **821** processing scripts open a **GUI** — nothing to edit in source before running.

---

## Documentation

| Doc | Purpose |
|-----|---------|
| **This file** | Clone, venv, dependencies, script index |
| **`README_821_Pipeline.md`** | **821 workflow** — folder layout, steps 0–4 |
| **`README_DataDownload.md`** | Field download SOP (G4, Feather MC, Song Meter) |
| **`README_ld821_combine.md`**, **`README_FeatherMC_combine.md`**, **`README_ld821_to_nvspl.md`** | 821 GUI fields, columns, troubleshooting |
| **`README_831_Renamer.md`**, **`README_831_to_NVSPL.md`** | LD 831 CLI workflows |

**821:** set up below, then follow **`README_821_Pipeline.md`**.

---

## Prepare your machine

### Prerequisites

1. **Python 3.9+** (Company Portal)
2. **Git** (Company Portal)

### One-time setup

1. Open **Git Bash** or Command Prompt and go where you want the repo:

```Shell
cd [path to the place where you would like to save the project]
```

2. Clone and enter the repo:

```Shell
git clone https://github.com/emeyer34/AMT2PY.git
cd AMT2PY
```

3. Create and activate a virtual environment:

```Shell
python -m venv .venv
```

```Shell
# Command Prompt
.venv\Scripts\activate

# Git Bash
source .venv/Scripts/activate
```

4. Install dependencies:

```Shell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Installs `pandas`, `pytz` (821 GUIs), and `tzdata` (831 `LD_TZ` / `MET_TZ` on Windows). **`831Renamer.py`** is stdlib-only — skip `pip install` if you only run that script and don't need 821 deps.

5. Run scripts from the repo folder with the venv active, e.g. `python ld821_combine.py`.

### Pulling updates

```Shell
cd [path where you have saved the project]
git pull
```

Re-run `pip install -r requirements.txt` if dependencies changed. To discard local changes and match remote:

```Shell
git fetch --all
git reset --hard origin/main
```

---

## Scripts

| Script | Workflow | Detail |
|--------|----------|--------|
| `ld821_combine.py` | Merge G4 Time History CSVs | [`README_821_Pipeline.md`](README_821_Pipeline.md) · [`README_ld821_combine.md`](README_ld821_combine.md) |
| `FeatherMC_combine.py` | Combine Feather MC wind CSVs | [`README_821_Pipeline.md`](README_821_Pipeline.md) · [`README_FeatherMC_combine.md`](README_FeatherMC_combine.md) |
| `ld821_to_nvspl.py` | Time History → hourly NVSPL (+ optional MET) | [`README_821_Pipeline.md`](README_821_Pipeline.md) · [`README_ld821_to_nvspl.md`](README_ld821_to_nvspl.md) |
| `831Renamer.py` | Merge LD831 folders → `.831` | [`README_831_Renamer.md`](README_831_Renamer.md) |
| `831_to_NVSPL_external_wind_log.py` | `.831` → NVSPL (+ optional wind CSV) | [`README_831_to_NVSPL.md`](README_831_to_NVSPL.md) |

Deployment folders for 821: `AUDIO/`, `MET/`, `METADATA/`, `RAW/` — see the pipeline doc. G4 exports go in **`RAW/`** only.

---

## Acknowledgments

- Original **AMT C#** implementation
- Larson Davis **LD831/LD821** data specifications
