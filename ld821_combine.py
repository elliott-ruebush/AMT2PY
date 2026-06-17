import os
import re
import csv
import logging
from logging import Formatter, StreamHandler, FileHandler
from datetime import datetime

import pandas as pd
from tkinter import filedialog, Tk

# ---------- USER INPUT ----------
sitename = "SAGU017"
deploy = "20260410"
# --------------------------------

# Tkinter: open file picker without showing the root window
root = Tk()
root.withdraw()

# Let user select CSVs (you can multi-select)
files = filedialog.askopenfilenames(
    title="Select SLM CSV Files (Time History)",
    filetypes=[("CSV files", "*.csv")]
)

if not files:
    raise SystemExit("No files were selected.")

# Keep only files whose basename matches: ...Time History[ optional number ].csv
time_history_pattern = re.compile(r'Time History(?:\s*\d+)?\.csv$', re.IGNORECASE)
selected_files = [f for f in files if time_history_pattern.search(os.path.basename(f))]
skipped_files = [f for f in files if f not in selected_files]

if not selected_files:
    raise SystemExit("No selected files matched the 'Time History' pattern.")

# ---------- Logging setup ----------
# Log to console + to file in the same directory as the first selected file
output_dir = os.path.dirname(selected_files[0])
log_ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
log_path = os.path.join(output_dir, f"combine_slm_{log_ts}.log")

logger = logging.getLogger("combine_slm")
logger.setLevel(logging.INFO)
logger.handlers.clear()  # ensure idempotent setup

console_handler = StreamHandler()
file_handler = FileHandler(log_path, encoding="utf-8")

fmt = Formatter(
    "%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
console_handler.setFormatter(fmt)
file_handler.setFormatter(fmt)

logger.addHandler(console_handler)
logger.addHandler(file_handler)

logger.info("----- Combine SLM Time History run started -----")
logger.info(f"Sitename: {sitename} | Deploy: {deploy}")
logger.info(f"Total files selected: {len(files)}")
logger.info("Files selected:")
for f in files:
    logger.info(f"  - {f}")

logger.info(f"Files matched Time History pattern: {len(selected_files)}")
for f in selected_files:
    logger.info(f"  ✔ {f}")

if skipped_files:
    logger.info(f"Files skipped (did not match pattern): {len(skipped_files)}")
    for f in skipped_files:
        logger.info(f"  ✖ {f}")

# ---------- Read CSVs ----------
dfs = []
for f in selected_files:
    try:
        df = pd.read_csv(f)
        dfs.append(df)
        logger.info(f"Read OK: {f} | Rows: {len(df)} | Columns: {list(df.columns)}")
    except Exception as e:
        logger.error(f"Failed to read {f}: {e}")
        raise

# Combine into a single DataFrame
data = pd.concat(dfs, ignore_index=True)
logger.info(f"Combined DataFrame rows: {len(data)}; columns: {list(data.columns)}")

# ---------- Sort by time column ----------
def find_time_column(df: pd.DataFrame) -> str:
    # First pass: columns that look like time/date/timestamp
    name_candidates = [c for c in df.columns if re.search(r'(time|date|timestamp)', str(c), re.IGNORECASE)]
    for c in name_candidates:
        try:
            pd.to_datetime(df[c], errors='raise')
            return c
        except Exception:
            continue

    # Second pass: try to parse each column as datetime, pick the first that succeeds
    for c in df.columns:
        try:
            pd.to_datetime(df[c], errors='raise')
            return c
        except Exception:
            continue

    # Fallbacks
    if len(df.columns) >= 2:
        return df.columns[1]
    return df.columns[0]

time_col = find_time_column(data)
logger.info(f"Detected time column: '{time_col}'")

# Parse and sort (coerce invalids to NaT so they sink to the bottom after sort)
parsed = pd.to_datetime(data[time_col], errors='coerce')
nat_count = parsed.isna().sum()
logger.info(f"Non-parsable timestamps (NaT) before sort: {nat_count}")

data[time_col] = parsed
data = data.sort_values(by=time_col, kind='stable').reset_index(drop=True)
logger.info("Data sorted by time column.")

# ---------- Output naming ----------
base_fname = os.path.basename(selected_files[-1])
standardized_fname = re.sub(
    r'Time History(?:\s*\d+)?\.csv$', 'Time History.csv',
    base_fname, flags=re.IGNORECASE
)
output_fname = f"{sitename}_{standardized_fname}"
output_path = os.path.join(output_dir, output_fname)

# Write CSV with no extra quoting (mirroring your original settings)
data.to_csv(output_path, index=False, quoting=csv.QUOTE_NONE, escapechar='\\')
logger.info(f"Output written: {output_path}")
logger.info(f"Log file saved: {log_path}")
logger.info("----- Combine SLM Time History run completed -----")

