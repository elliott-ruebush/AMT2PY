# Mirrored NSNSD Acoustic Monitoring Toolbox (AMT)

This repository mirrors the **NSNSD Acoustic Monitoring Toolbox (AMT)** — originally a C# executable used to process, visualize, and summarize acoustic data. Due to loss of in‑house C# expertise, this project ports core AMT workflows to **Python**, enabling easier maintenance, extension, and integration with modern data pipelines.

NOTE: This mostly replaces Type1-821envtools repository `https://github.com/emeyer34/Type1-821envtools` because that toolbox was meant to transition 821 and hobo data into AMT, which required several slight changes in formatting of raw data prior to AMT injestion. The AMT2PY makes this obsolute due to 1.) addressing NVSPL creation in python instead of AMT; and 2.) adopting a more flexible wind data injestion (time step and formatting) in python.

The current focus is on:

- Standardized file organization
- SPL/NVSPL preparation
- Merging meteorological (wind) data
- Processing workflows for **Larson Davis 831** and **821‑env** acoustic monitoring systems

---

## Project Overview

The Python tools in this repository provide functionality equivalent to key AMT components:

### Core Capabilities

- **Merge LD821‑ENV SPL logs** into a single combined Time History CSV
- **Merge wind logger data** with combined SPL CSV during NVSPL conversion
- **Merge LD831 SPL logs** into a single `.831` file with correct `NPSLD831` header and offsets
- **Merge wind logger data** with `.831` files during NVSPL conversion

These workflows replicate AMT behavior while offering greater flexibility and transparency.

---

# Prepare Your Machine

## Installation Guide

1. Install **Python** (via Company Portal)
2. Install **Git** (via Company Portal)

---

## Preparing Your Workstation (One‑Time Setup)

1. Open **Git Bash** and navigate to the directory where you want to store the project:

```Shell
cd [path to the place where you would like to save the project]
```

2. Clone the repository:

```Shell
git clone https://github.com/emeyer34/AMT2PY.git
```

3. Fetch any updates:

```Shell
git fetch
```

4. Pull the latest changes:

```Shell
git pull origin main
```

---

## Pulling Updates Later

1. Open a terminal and navigate to the project:

```Shell
cd [path where you have saved the project]
```

2. Pull updates:

```Shell
git pull
```

3. If you encounter conflicts or pull errors due to local changes, you can overwrite your local version:

```Shell
git fetch --all
git reset --hard origin/master
```

---

# Download & Organize Project Data

Use **README_DataDownload.md** for detailed instructions on downloading data from **821‑ENV systems**. This includes SPL logs, MET (wind) data, and required deployment folder structure.

---

# Processing Scripts

Below is a summary of included scripts and their roles in the processing pipeline.

---

## LD 821‑ENV Workflow

See **`README_821_Pipeline.md`** for a step-by-step guide (setup, folder layout, and all three scripts).

### 1. `ld821_combine.py`

- Combines all SPL **Time History** files exported from G4 Utility
- Produces a single analysis‑ready SPL file from the entire deployment
- Applies standardized naming (Site, deployment date, system, etc)

---

### 2. `FeatherMC_combine.py`

- Combines wind data collected by an ultrasonic anemometer by a **Feather MC data logger**
- Converts UTC → local time and includes optional Daylight Savings offset
- Outputs a cleaned, standardized MET file with serial number and deployment date

---

### 3. `ld821_to_nvspl.py`

- Converts combined SPL and MET data to **NVSPL**
- Merges one‑second SPL with one‑second wind speed
- After creating NVSPL files, users may return to **AMT** for final processing, graphing, and analysis

---

## LD 831 Workflow

### 1. `831Renamer.py`

**Purpose:**

- Recursively identifies folders containing `OverAll`, `SLog`, and `THist` files
- Merges these files into a single `.831` file with proper `NPSLD831` header and offsets
- Renames output to:

```Shell
SPL_<SITE>_<yyyy_MM_dd_HHmmss>.831
```

 Saved two levels above the `THist` folder

- Supports optional timestamp adjustments for time‑history records

**Quick Start:**

```Shell
python 831Renamer.py /path/to/root --site ABC

# Preview only:
python 831Renamer.py /path/to/root --site ABC --dry-run

# Adjust timestamps:
python 831Renamer.py /path/to/root --site ABC --new-date "2025-04-10 12:34:56"
```

---

### 2. `831_to_NVSPL_external_wind_log.py`

**Purpose:**

- Converts `.831` files (legacy & new formats) to hourly **NVSPL** `.txt` **files**
- Optionally merges external wind data using bin-repeat, forward‑fill, or nearest‑neighbor methods

**Configuration:** Edit constants at the top of the script:

- `INPUT_PATH`
- `OUTPUT_PATH`
- `MERGE_MET`
- `MET_CSV_PATH`

**Quick Start:**

```Shell
# Basic conversion (SPL only):
python 831_to_NVSPL_external_wind_log.py

# With wind merge:
MERGE_MET = True
MET_CSV_PATH = "path/to/met.csv"
```

---

# Requirements

- Python **3.9+**
- Third-party packages (821 combine scripts): `pandas`, `pytz`
- Optional: `tzdata` for timezone handling in the 831 NVSPL script on some platforms

```Shell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

---

# Why Python?

- Easier to maintain than C#
- Transparent, readable workflows
- Simple extensibility for future NSNSD metadata, QA/QC tools, and automated reporting
- Compatible with scientific computing tools and Jupyter workflows

---

# Acknowledgments

- Original **AMT C#** implementation
- Larson Davis **LD831/LD821** data specifications
