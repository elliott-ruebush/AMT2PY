# FeatherMC_combine

Overview
This script combines and cleans FeatherMC wind CSV files.

Features
- Select MET CSVs via GUI
- Time zone picker
- Cleans repeated headers
- UTC to local conversion

Prerequisites
- Python3, pandas, pytz

Inputs
- Multiple CSV files (do not select metadata (MD) files)

Outputs
- Combined cleaned CSV

Usage
Run script and use GUI to pick files.

Configurable Settings
site_name, deploy, serial, deploy_tzone, adjust_for_dst

Example Workflow
1. Run script
2. Pick files

Troubleshooting
Check CSV headers.

Changelog
- Initial
