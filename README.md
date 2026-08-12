# Mirrored NSNSD Acoustic Monitoring Toolbox (AMT)

This repository mirrors the **NSNSD Acoustic Monitoring Toolbox (AMT)** — originally a C# application used to process, visualize, and summarize acoustic data. These tools port core AMT workflows to **Python** for easier maintenance and updates.

This mostly replaces the [Type1-821envtools](https://github.com/emeyer34/Type1-821envtools) repository. That toolbox was meant to transition 821 and HOBO data into AMT, which required reformatting raw data before AMT could use it. **AMT2PY** avoids that extra step by:

1. Creating **NVSPL in Python** instead of inside AMT
2. Supporting more flexible wind-data merge (timestep and formatting) during NVSPL conversion

**Current focus:**

- Standardized file organization
- SPL/NVSPL preparation
- Merging meteorological (wind) data
- Processing workflows for two **Larson Davis** sound level meter lines used in NSNSD monitoring

Both the **821‑ENV** and **Model 831** are [Larson Davis](https://www.larsondavis.com/Products/sound-level-meters) instruments. They use different download formats and software, so this repo has separate tool paths for each.

**821‑ENV** ([SoundExpert](https://www.larsondavis.com/Products/sound-level-meters/soundexpert-821env)) — **NSNSD’s current Type 1 field system** (LD meter + G4 Utility export, Feather MC wind, Song Meter audio). Start here: [`docs/821/pipeline.md`](docs/821/pipeline.md).  
**Model 831** — **earlier Larson Davis meter** ([discontinued in 2022](https://www.larsondavis.com/product-support/announcements/sound-level-meter-model-831-discontinued); successor is SoundAdvisor 831C). Use when you still have `.831` logger data: [`docs/831/README.md`](docs/831/README.md).

**821‑env:** combine G4 Time History CSVs and optional Feather MC wind data → hourly NVSPL for AMT.  
**LD 831:** merge logger folders into `.831` files and convert to NVSPL.

All **821** processing scripts open a **GUI** — there is nothing to edit in the code before running.

---

## Documentation

| Doc | Purpose |
|-----|---------|
| **This file** | Setup, script summary, and links to detailed guides |
| [`docs/821/pipeline.md`](docs/821/pipeline.md) | **821 workflow** — folder layout, steps 0–4 |
| [`docs/821/data-download.md`](docs/821/data-download.md) | Field download SOP (G4, Feather MC, Song Meter) |
| [`docs/821/ld821-combine.md`](docs/821/ld821-combine.md), [`docs/821/feathermc-combine.md`](docs/821/feathermc-combine.md), [`docs/821/ld821-to-nvspl.md`](docs/821/ld821-to-nvspl.md) | 821 GUI fields, columns, troubleshooting |
| [`docs/831/README.md`](docs/831/README.md), [`docs/831/renamer.md`](docs/831/renamer.md), [`docs/831/to-nvspl.md`](docs/831/to-nvspl.md) | LD 831 workflows |

**821:** complete setup below, then follow [`docs/821/pipeline.md`](docs/821/pipeline.md).  
**831:** see [`docs/831/README.md`](docs/831/README.md).  
**Download & organize field data first:** see [`docs/821/data-download.md`](docs/821/data-download.md) for SPL logs, MET (wind) data, and deployment folder structure.

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

4. Install required packages:

```Shell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

5. From the `AMT2PY` folder (with the environment from step 3 still active), run a script, e.g.:

```Shell
python ld821_combine.py
```

### Pulling updates

```Shell
cd [path where you have saved the project]
git pull
```

Re-run `pip install -r requirements.txt` if dependencies changed.

---

## Scripts

| Script | Workflow | Detail |
|--------|----------|--------|
| `ld821_combine.py` | Merge G4 Time History CSVs | [`docs/821/pipeline.md`](docs/821/pipeline.md) · [`docs/821/ld821-combine.md`](docs/821/ld821-combine.md) |
| `FeatherMC_combine.py` | Combine Feather MC wind CSVs | [`docs/821/pipeline.md`](docs/821/pipeline.md) · [`docs/821/feathermc-combine.md`](docs/821/feathermc-combine.md) |
| `ld821_to_nvspl.py` | Time History → hourly NVSPL (+ optional MET) | [`docs/821/pipeline.md`](docs/821/pipeline.md) · [`docs/821/ld821-to-nvspl.md`](docs/821/ld821-to-nvspl.md) |
| `831Renamer.py` | Merge LD831 folders → `.831` | [`docs/831/renamer.md`](docs/831/renamer.md) |
| `831_to_NVSPL_external_wind_log.py` | `.831` → NVSPL (+ optional wind CSV) | [`docs/831/to-nvspl.md`](docs/831/to-nvspl.md) |

Deployment folders for 821: `AUDIO/`, `MET/`, `METADATA/`, `RAW/` — see [`docs/821/pipeline.md`](docs/821/pipeline.md). G4 exports go in **`RAW/`** only.

---

## Acknowledgments

- Original **AMT C#** implementation
- Larson Davis **LD831/LD821** data specifications
