import os
import logging
from logging import Formatter, StreamHandler, FileHandler
from datetime import datetime

import pandas as pd
import pytz
from tkinter import Tk, filedialog, Toplevel, StringVar, BooleanVar
from tkinter import ttk

# ---------------- USER INPUT (defaults; can be overridden by the picker) ----------------
site_name = "MORUA2503"
deploy = "20260626"
serial = "00000018"

# Default time zone & DST handling — the picker will let you change these interactively
deploy_tzone = "America/Denver"
adjust_for_dst = False  # True = apply DST; False = use fixed standard offset
# ---------------------------------------------------------------------------------------


def select_met_files():
    root = Tk()
    root.withdraw()
    file_paths = filedialog.askopenfilenames(
        title="Select wind CSV files (exclude MD files)",
        filetypes=[("CSV files", "*.csv")]
    )
    return list(file_paths)

COMMON_TZS = [
    "America/New_York", "America/Chicago", "America/Denver", "America/Los_Angeles",
    "America/Phoenix", "America/Anchorage", "America/Honolulu",
    "UTC", "Europe/London", "Europe/Berlin", "Europe/Paris",
    "Asia/Tokyo", "Asia/Shanghai", "Australia/Sydney"
]

def pick_timezone(default_tz: str = "America/Denver", default_dst: bool = True):
    try:
        all_tzs = [tz for tz in pytz.all_timezones if tz not in COMMON_TZS]
        tz_list = COMMON_TZS + all_tzs
    except Exception:
        tz_list = COMMON_TZS

    dlg = Toplevel()
    dlg.title("Select Time Zone")
    dlg.geometry("460x200")
    dlg.resizable(False, False)
    dlg.grab_set()

    tz_var = StringVar(value=default_tz)
    dst_var = BooleanVar(value=default_dst)
    result = {"tz": None, "dst": None}

    ttk.Label(dlg, text="Time Zone:", font=("Segoe UI", 10, "bold")).pack(pady=(12, 4))
    tz_combo = ttk.Combobox(dlg, textvariable=tz_var, values=tz_list, width=52, state="readonly")
    tz_combo.pack(pady=2)
    tz_combo.set(default_tz if default_tz in tz_list else tz_list[0])

    ttk.Label(dlg, text="DST handling:", font=("Segoe UI", 10, "bold")).pack(pady=(10, 2))
    dst_check = ttk.Checkbutton(
        dlg,
        text="Apply local DST rules (unchecked = fixed standard-time offset)",
        variable=dst_var
    )
    dst_check.pack()

    btn_frame = ttk.Frame(dlg)
    btn_frame.pack(pady=16)

    def on_ok():
        result["tz"] = tz_var.get()
        result["dst"] = dst_var.get()
        dlg.destroy()

    def on_cancel():
        result["tz"] = None
        result["dst"] = None
        dlg.destroy()

    ttk.Button(btn_frame, text="OK", command=on_ok).pack(side="left", padx=8)
    ttk.Button(btn_frame, text="Cancel", command=on_cancel).pack(side="left", padx=8)

    dlg.wait_window()
    return result["tz"], result["dst"]

def setup_logger(output_dir: str) -> logging.Logger:
    log_ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_path = os.path.join(output_dir, f"feathermc_clean_{log_ts}.log")

    logger = logging.getLogger("feathermc_clean")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    console_handler = StreamHandler()
    file_handler = FileHandler(log_path, encoding="utf-8")

    fmt = Formatter("%(asctime)s | %(levelname)s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    console_handler.setFormatter(fmt)
    file_handler.setFormatter(fmt)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    logger.info("----- FeatherMC wind clean prep run started -----")
    logger.info(f"Site: {site_name} | Deploy: {deploy} | Serial: {serial}")
    logger.info(f"Log file: {log_path}")
    return logger

def read_and_combine_files(file_paths, logger: logging.Logger) -> pd.DataFrame:
    if not file_paths:
        raise SystemExit("No files were selected.")

    logger.info(f"Total files selected: {len(file_paths)}")
    for f in file_paths:
        logger.info(f"  - {f}")

    dfs = []
    for f in file_paths:
        try:
            df = pd.read_csv(f)
            dfs.append(df)
            logger.info(f"Read OK: {f} | Rows: {len(df)} | Columns: {list(df.columns)}")
        except Exception as e:
            logger.error(f"Failed to read {f}: {e}")
            raise

    combined_df = pd.concat(dfs, ignore_index=True)
    logger.info(f"Combined DataFrame rows: {len(combined_df)}; columns: {list(combined_df.columns)}")
    return combined_df

def clean_repeated_headers(df: pd.DataFrame, logger: logging.Logger) -> pd.DataFrame:
    before = len(df)
    # Remove rows where '#' is not numeric (these are repeated headers or corrupt rows)
    df_clean = df[pd.to_numeric(df['#'], errors='coerce').notnull()].copy()
    after = len(df_clean)
    removed = before - after
    logger.info(f"Removed {removed} repeated header/corrupt rows based on '#' column.")
    return df_clean

def convert_utc_to_local(utc_series: pd.Series, tz_name: str, adjust_dst: bool, logger: logging.Logger):
    local_tz = pytz.timezone(tz_name)
    utc_aware = utc_series.dt.tz_localize('UTC')

    if adjust_dst:
        local_times = utc_aware.dt.tz_convert(local_tz)
        tz_abbr = local_times.dt.strftime('%Z')
        logger.info(f"Converted timestamps from UTC to {tz_name} with DST rules applied.")
    else:
        standard_offset = local_tz.utcoffset(datetime(2025, 1, 1))
        local_times = utc_aware.dt.tz_localize(None) + standard_offset
        tz_abbr_val = local_tz.localize(datetime(2025, 1, 1)).tzname()
        tz_abbr = [tz_abbr_val] * len(local_times)
        logger.info(f"Converted timestamps from UTC to {tz_name} using a fixed standard-time offset (no DST).")

    return local_times, tz_abbr

def clean_and_format_data(df: pd.DataFrame, tz: str, adjust_dst: bool, logger: logging.Logger) -> pd.DataFrame:
    # Remove repeated headers
    df = clean_repeated_headers(df, logger)

    # Parse UTC column
    if 'Date-Time (UTC)' not in df.columns:
        msg = "Required column 'Date-Time (UTC)' not found."
        logger.error(msg)
        raise ValueError(msg)

    df['UTC'] = pd.to_datetime(df['Date-Time (UTC)'], errors='coerce')
    nat_before = df['UTC'].isna().sum()
    if nat_before:
        logger.info(f"Rows with non-parsable UTC timestamps: {nat_before}")
    df = df.dropna(subset=['UTC']).copy()

    # Convert UTC -> Local
    local_time, tz_abbr = convert_utc_to_local(df['UTC'], tz, adjust_dst, logger)
    df['Date-Time (LOC)'] = local_time.dt.strftime('%m/%d/%Y %H:%M:%S')
    df['Time Zone'] = tz_abbr

    unique_abbr = pd.Series(tz_abbr).unique().tolist()
    logger.info(f"Time zone abbreviations present after conversion: {unique_abbr}")

    # Ensure numeric types for '#' if present
    if '#' in df.columns:
        df['#'] = pd.to_numeric(df['#'], errors='coerce')

    # Sort by local time
    df['_loc_dt'] = pd.to_datetime(df['Date-Time (LOC)'], format='%m/%d/%Y %H:%M:%S', errors='coerce')
    nat_loc = df['_loc_dt'].isna().sum()
    if nat_loc:
        logger.info(f"Non-parsable local timestamps during sort: {nat_loc} (these rows will sort last).")

    df = df.sort_values(by='_loc_dt', kind='stable').drop(columns=['_loc_dt']).reset_index(drop=True)
    logger.info("Data sorted by 'Date-Time (LOC)'.")

    # Log first/last local times
    if len(df) > 0:
        logger.info(f"First local time: {df['Date-Time (LOC)'].iloc[0]} | "
                    f"Last local time: {df['Date-Time (LOC)'].iloc[-1]}")

    return df

def export_data(df: pd.DataFrame, file_paths, serial: str, logger: logging.Logger):
    output_dir = os.path.dirname(file_paths[0])
    last_date_str = df['Date-Time (LOC)'].iloc[-1]
    last_dt = datetime.strptime(last_date_str, "%m/%d/%Y %H:%M:%S")
    formatted_date = last_dt.strftime("%Y-%m-%d %H%M%S")
    filename = f"{serial} {formatted_date}.csv"
    output_path = os.path.join(output_dir, filename)
    df.to_csv(output_path, index=False)
    logger.info(f"All columns written to output: {list(df.columns)}")
    logger.info(f"Output written: {output_path}")
    logger.info("----- FeatherMC wind clean prep run completed -----")
    print(f"Exported to:\n{output_path}")

if __name__ == "__main__":
    file_paths = select_met_files()
    if not file_paths:
        raise SystemExit("No files were selected.")

    output_dir_for_logs = os.path.dirname(file_paths[0])
    logger = setup_logger(output_dir_for_logs)

    sel_tz, sel_dst = pick_timezone(default_tz=deploy_tzone, default_dst=adjust_for_dst)
    if sel_tz is None:
        logger.info("User cancelled time zone selection. Exiting.")
        raise SystemExit("Time zone selection cancelled.")
    else:
        deploy_tzone = sel_tz
        adjust_for_dst = sel_dst
        logger.info(f"Time zone selected: {deploy_tzone} | adjust_for_dst={adjust_for_dst}")
        logger.info("A UTC → local time conversion will be applied based on the selection.")

    raw_data = read_and_combine_files(file_paths, logger)
    clean_data = clean_and_format_data(raw_data, deploy_tzone, adjust_for_dst, logger)
    export_data(clean_data, file_paths, serial, logger)