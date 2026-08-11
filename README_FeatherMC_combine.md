# FeatherMC_combine

Overview
This script combines and cleans FeatherMC wind CSV files.

Features
- Select MET folder via GUI (raw logger CSVs auto-detected)
- Skips prior combined outputs and non-logger CSVs
- Time zone picker
- Cleans repeated headers
- UTC to local conversion

Prerequisites
- Python3, pandas, pytz

Inputs
- MET folder containing microSD logger CSV exports (`.md` metadata files ignored)
- Only files with `Date-Time (UTC)` and without `Date-Time (LOC)` are combined
- Prior combined outputs (`{serial} {YYYY-MM-DD HHMMSS}.csv`) are skipped

Outputs
- Combined cleaned CSV written to the selected MET folder

Usage
Run script, browse to MET folder, then run combine.

Configurable Settings
site_name (optional log metadata), serial, deploy_tzone, adjust_for_dst

Example Workflow
1. Run script
2. Browse to MET folder
2. Pick files

Troubleshooting
Check CSV headers.

Changelog
- Initial
