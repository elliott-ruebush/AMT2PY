# -*- coding: utf-8 -*-
import os
import logging
import threading
from logging import Formatter, StreamHandler, FileHandler
from datetime import datetime

import pandas as pd
import pytz
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# Timezone definitions
COMMON_TZS = [
    "America/New_York", "America/Chicago", "America/Denver", "America/Los_Angeles",
    "America/Phoenix", "America/Anchorage", "America/Honolulu",
    "UTC", "Europe/London", "Europe/Berlin", "Europe/Paris",
    "Asia/Tokyo", "Asia/Shanghai", "Australia/Sydney"
]

try:
    all_tzs = [tz for tz in pytz.all_timezones if tz not in COMMON_TZS]
    TIMEZONE_LIST = COMMON_TZS + all_tzs
except Exception:
    TIMEZONE_LIST = COMMON_TZS

# ------------------------------------------------------------------------------
# ToolTip Helper
# ------------------------------------------------------------------------------
class ToolTip:
    """Helper to display hover tooltips for UI widgets."""
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tip_window = None
        self.widget.bind("<Enter>", self.show_tip)
        self.widget.bind("<Leave>", self.hide_tip)

    def show_tip(self, event=None):
        if self.tip_window or not self.text:
            return
        x, y, _, _ = self.widget.bbox("insert")
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 25
        self.tip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        label = tk.Label(tw, text=self.text, justify=tk.LEFT, background="#ffffe0",
                         relief=tk.SOLID, borderwidth=1, font=("tahoma", "8", "normal"))
        label.pack(ipadx=1)

    def hide_tip(self, event=None):
        if self.tip_window:
            self.tip_window.destroy()
            self.tip_window = None

# ------------------------------------------------------------------------------
# Core Processing Functions
# ------------------------------------------------------------------------------
def setup_logger(output_dir: str, site_name: str, deploy: str, serial: str):
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
    return logger, log_path

def close_logger(logger: logging.Logger):
    for handler in logger.handlers[:]:
        handler.close()
        logger.removeHandler(handler)

def read_and_combine_files(file_paths, logger: logging.Logger, progress_callback=None) -> pd.DataFrame:
    if not file_paths:
        raise ValueError("No files were selected.")

    n = len(file_paths)
    total = n + 2

    def report(step, msg):
        if progress_callback:
            progress_callback(step, total, msg)

    logger.info(f"Total files selected: {n}")
    for f in file_paths:
        logger.info(f"  - {f}")

    dfs = []
    for i, f in enumerate(file_paths):
        report(i + 1, f"Reading file {i + 1} of {n}…")
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
    if '#' not in df.columns:
        msg = "Required column '#' not found."
        logger.error(msg)
        raise ValueError(msg)
    before = len(df)
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
    df = clean_repeated_headers(df, logger)

    if 'Date-Time (UTC)' not in df.columns:
        msg = "Required column 'Date-Time (UTC)' not found."
        logger.error(msg)
        raise ValueError(msg)

    df['UTC'] = pd.to_datetime(df['Date-Time (UTC)'], errors='coerce')
    nat_before = df['UTC'].isna().sum()
    if nat_before:
        logger.info(f"Rows with non-parsable UTC timestamps: {nat_before}")
    df = df.dropna(subset=['UTC']).copy()

    local_time, tz_abbr = convert_utc_to_local(df['UTC'], tz, adjust_dst, logger)
    df['Date-Time (LOC)'] = local_time.dt.strftime('%m/%d/%Y %H:%M:%S')
    df['Time Zone'] = tz_abbr

    unique_abbr = pd.Series(tz_abbr).unique().tolist()
    logger.info(f"Time zone abbreviations present after conversion: {unique_abbr}")

    if '#' in df.columns:
        df['#'] = pd.to_numeric(df['#'], errors='coerce')

    df['_loc_dt'] = pd.to_datetime(df['Date-Time (LOC)'], format='%m/%d/%Y %H:%M:%S', errors='coerce')
    nat_loc = df['_loc_dt'].isna().sum()
    if nat_loc:
        logger.info(f"Non-parsable local timestamps during sort: {nat_loc} (these rows will sort last).")

    df = df.sort_values(by='_loc_dt', kind='stable').drop(columns=['_loc_dt']).reset_index(drop=True)
    logger.info("Data sorted by 'Date-Time (LOC)'.")

    if len(df) > 0:
        logger.info(f"First local time: {df['Date-Time (LOC)'].iloc[0]} | "
                    f"Last local time: {df['Date-Time (LOC)'].iloc[-1]}")

    return df

def export_data(df: pd.DataFrame, file_paths, serial: str, logger: logging.Logger):
    if df.empty:
        msg = "No valid data rows remain after cleaning and UTC conversion."
        logger.error(msg)
        raise ValueError(msg)
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
    return output_path

# ------------------------------------------------------------------------------
# Main Application GUI
# ------------------------------------------------------------------------------
class FeatherMCApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("FeatherMC Wind Data Combination Tool")
        self.geometry("560x600")
        self.resizable(True, True)

        self.selected_files = []
        self._worker_running = False
        self._build_gui()

    def _on_ui(self, func, *args, **kwargs):
        self.after(0, lambda: func(*args, **kwargs))

    def _update_progress(self, step, total, message):
        self.progress.config(maximum=total, value=step)
        self.lbl_progress.config(text=message)

    def _reset_progress(self):
        self.progress.config(value=0)
        self.lbl_progress.config(text="")

    def _result_text_key(self, event):
        mod = event.state & 0x4 or event.state & 0x8  # Ctrl (Win/Linux) or Command (macOS)
        if mod and event.keysym.lower() in ("c", "a"):
            return
        return "break"

    def _set_result(self, text, ok=None):
        if ok is True:
            color = "#1a7f37"
        elif ok is False:
            color = "#b42318"
        else:
            color = "#666666"
        self.txt_result.config(fg=color)
        self.txt_result.delete("1.0", tk.END)
        if text:
            self.txt_result.insert("1.0", text)

    def _build_gui(self):
        main_frame = ttk.Frame(self, padding="12")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # --- File Selector Group ---
        grp_files = ttk.LabelFrame(main_frame, text=" Met File Selector ", padding="10")
        grp_files.pack(fill=tk.BOTH, expand=True, pady=5)

        btn_browse = ttk.Button(grp_files, text="Select Wind CSV Files...", command=self.browse_files)
        btn_browse.pack(anchor="w", pady=(0, 5))
        self.btn_browse = btn_browse

        self.lbl_file_count = ttk.Label(grp_files, text="No files selected", font=("Segoe UI", 9, "italic"))
        self.lbl_file_count.pack(anchor="w", pady=(0, 2))

        # Listbox to display selected file paths
        list_frame = ttk.Frame(grp_files)
        list_frame.pack(fill=tk.BOTH, expand=True)

        self.lst_files = tk.Listbox(list_frame, height=5, selectmode=tk.EXTENDED)
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.lst_files.yview)
        self.lst_files.configure(yscrollcommand=scrollbar.set)

        self.lst_files.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # --- User Input & Metadata Group ---
        grp_meta = ttk.LabelFrame(main_frame, text=" Site & Deployment Settings ", padding="10")
        grp_meta.pack(fill=tk.X, pady=5)

        # site_name
        lbl_site = ttk.Label(grp_meta, text="Site Name:", width=18, anchor="w")
        lbl_site.grid(row=0, column=0, sticky="w", pady=4)
        self.var_site_name = tk.StringVar(value="PARK001")
        ent_site = ttk.Entry(grp_meta, textvariable=self.var_site_name)
        ent_site.grid(row=0, column=1, sticky="ew", padx=5, pady=4)
        grp_meta.columnconfigure(1, weight=1)
        hint_site = "Alpha numeric park code and site number"
        ToolTip(ent_site, hint_site)
        ToolTip(lbl_site, hint_site)

        # deploy
        lbl_deploy = ttk.Label(grp_meta, text="Deploy Date:", width=18, anchor="w")
        lbl_deploy.grid(row=1, column=0, sticky="w", pady=4)
        self.var_deploy = tk.StringVar(value="20260101")
        ent_deploy = ttk.Entry(grp_meta, textvariable=self.var_deploy)
        ent_deploy.grid(row=1, column=1, sticky="ew", padx=5, pady=4)
        hint_deploy = "YYYYMMDD"
        ToolTip(ent_deploy, hint_deploy)
        ToolTip(lbl_deploy, hint_deploy)

        # serial
        lbl_serial = ttk.Label(grp_meta, text="Serial Number:", width=18, anchor="w")
        lbl_serial.grid(row=2, column=0, sticky="w", pady=4)
        self.var_serial = tk.StringVar(value="00000018")
        ent_serial = ttk.Entry(grp_meta, textvariable=self.var_serial)
        ent_serial.grid(row=2, column=1, sticky="ew", padx=5, pady=4)
        hint_serial = "Located in metadata files"
        ToolTip(ent_serial, hint_serial)
        ToolTip(lbl_serial, hint_serial)

        # --- Timezone & DST Group ---
        grp_tz = ttk.LabelFrame(main_frame, text=" Time Zone & DST Handling ", padding="10")
        grp_tz.pack(fill=tk.X, pady=5)

        lbl_tz = ttk.Label(grp_tz, text="Time Zone:", width=18, anchor="w")
        lbl_tz.grid(row=0, column=0, sticky="w", pady=4)
        self.var_tzone = tk.StringVar(value="America/Denver")
        cmb_tz = ttk.Combobox(grp_tz, textvariable=self.var_tzone, values=TIMEZONE_LIST, state="readonly")
        cmb_tz.grid(row=0, column=1, sticky="ew", padx=5, pady=4)
        grp_tz.columnconfigure(1, weight=1)

        self.var_dst = tk.BooleanVar(value=False)
        chk_dst = ttk.Checkbutton(
            grp_tz,
            text="Adjust for DST (apply local DST rules vs fixed standard offset)",
            variable=self.var_dst
        )
        chk_dst.grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 0))

        # --- Action Button ---
        self.btn_run = ttk.Button(main_frame, text="Combine and Process Files", command=self.run_process)
        self.btn_run.pack(fill=tk.X, pady=(12, 4))

        self.lbl_progress = ttk.Label(main_frame, text="", font=("Segoe UI", 9))
        self.lbl_progress.pack(fill=tk.X, pady=(0, 2))

        self.progress = ttk.Progressbar(main_frame, mode="determinate", maximum=100)
        self.progress.pack(fill=tk.X, pady=(0, 6))

        self.lbl_result = tk.Label(
            main_frame, text="Result (select text to copy):", anchor="w",
            font=("Segoe UI", 9), foreground="#444444"
        )
        self.lbl_result.pack(fill=tk.X, pady=(0, 2))

        self.txt_result = tk.Text(
            main_frame, height=4, wrap=tk.WORD, font=("Segoe UI", 9),
            relief=tk.GROOVE, borderwidth=1, padx=4, pady=4, foreground="#666666"
        )
        self.txt_result.pack(fill=tk.X, pady=(0, 4))
        self.txt_result.bind("<Key>", self._result_text_key)

    def _set_busy(self, busy):
        if busy:
            self.btn_run.config(state=tk.DISABLED, text="Processing…")
            self.btn_browse.config(state=tk.DISABLED)
        else:
            self.btn_run.config(state=tk.NORMAL, text="Combine and Process Files")
            self.btn_browse.config(state=tk.NORMAL)

    def browse_files(self):
        if self._worker_running:
            return
        file_paths = filedialog.askopenfilenames(
            title="Select wind CSV files (exclude MD files)",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if file_paths:
            self.selected_files = list(file_paths)
            self.lst_files.delete(0, tk.END)
            for f in self.selected_files:
                self.lst_files.insert(tk.END, os.path.basename(f))
            self.lbl_file_count.config(text=f"{len(self.selected_files)} file(s) selected")
            self._set_result("")

    def run_process(self):
        if self._worker_running:
            return
        if not self.selected_files:
            messagebox.showwarning("Selection Missing", "Please select met data CSV files first.")
            return

        site_name = self.var_site_name.get().strip()
        deploy = self.var_deploy.get().strip()
        serial = self.var_serial.get().strip()
        deploy_tzone = self.var_tzone.get().strip()
        adjust_for_dst = self.var_dst.get()

        output_dir_for_logs = os.path.dirname(self.selected_files[0])
        files = list(self.selected_files)

        self._worker_running = True
        self._set_busy(True)
        self._set_result("")
        self._update_progress(0, 1, "Starting…")

        threading.Thread(
            target=self._run_worker,
            args=(output_dir_for_logs, site_name, deploy, serial, deploy_tzone, adjust_for_dst, files),
            daemon=True,
        ).start()

    def _run_worker(self, output_dir, site_name, deploy, serial, deploy_tzone, adjust_for_dst, files):
        logger = None
        n = len(files)
        total = n + 2

        def progress(step, total, message):
            self._on_ui(self._update_progress, step, total, message)

        try:
            logger, log_path = setup_logger(output_dir, site_name, deploy, serial)
            logger.info(f"Time zone selected: {deploy_tzone} | adjust_for_dst={adjust_for_dst}")

            raw_data = read_and_combine_files(files, logger, progress_callback=progress)
            progress(n + 1, total, "Cleaning and converting timestamps…")
            clean_data = clean_and_format_data(raw_data, deploy_tzone, adjust_for_dst, logger)
            progress(n + 2, total, "Writing output…")
            output_path = export_data(clean_data, files, serial, logger)

            self._on_ui(self._on_success, output_path, log_path, n)
        except Exception as e:
            self._on_ui(self._on_failure, str(e))
        finally:
            if logger:
                close_logger(logger)
            self._on_ui(self._on_worker_done)

    def _on_success(self, output_path, log_path, file_count):
        total = int(float(self.progress.cget("maximum")))
        self._update_progress(total, total, "Done")
        self._set_result(
            f"FeatherMC combine done — {file_count} file(s)\n"
            f"Output: {output_path}\n"
            f"Log: {log_path}",
            ok=True,
        )
        messagebox.showinfo(
            "FeatherMC Combine — Complete",
            f"FeatherMC Wind Combiner finished successfully.\n\n"
            f"Combined {file_count} file(s).\n\nOutput saved to:\n{output_path}"
        )

    def _on_failure(self, error):
        self._reset_progress()
        self._set_result(f"Failed — {error}", ok=False)
        messagebox.showerror(
            "FeatherMC Combine — Error",
            f"FeatherMC Wind Combiner failed:\n{error}"
        )

    def _on_worker_done(self):
        self._worker_running = False
        self._set_busy(False)
        if float(self.progress.cget("value")) < float(self.progress.cget("maximum")):
            self._reset_progress()

# ------------------------------------------------------------------------------
# Entry Point
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    app = FeatherMCApp()
    app.mainloop()