# -*- coding: utf-8 -*-
import os
import re
import csv
import logging
from logging import Formatter, StreamHandler, FileHandler
from datetime import datetime

import pandas as pd
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# Compile regex pattern to match: ...Time History[ optional number ].csv
TIME_HISTORY_PATTERN = re.compile(r'Time History(?:\s*\d+)?\.csv$', re.IGNORECASE)

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
def setup_logger(output_dir: str, sitename: str, deploy: str) -> logging.Logger:
    log_ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_path = os.path.join(output_dir, f"combine_slm_{log_ts}.log")

    logger = logging.getLogger("combine_slm")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

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
    logger.info(f"Log file: {log_path}")
    return logger

def find_time_column(df: pd.DataFrame) -> str:
    # First pass: columns that look like time/date/timestamp
    name_candidates = [c for c in df.columns if re.search(r'(time|date|timestamp)', str(c), re.IGNORECASE)]
    for c in name_candidates:
        try:
            pd.to_datetime(df[c], errors='raise')
            return c
        except Exception:
            continue

    # Second pass: try to parse each column as datetime
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

def process_slm_files(selected_files: str, sitename: str, deploy: str, logger: logging.Logger):
    logger.info(f"Files matched Time History pattern: {len(selected_files)}")
    for f in selected_files:
        logger.info(f"  ✔ {f}")

    # Read CSVs
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

    # Sort by time column
    time_col = find_time_column(data)
    logger.info(f"Detected time column: '{time_col}'")

    parsed = pd.to_datetime(data[time_col], errors='coerce')
    nat_count = parsed.isna().sum()
    logger.info(f"Non-parsable timestamps (NaT) before sort: {nat_count}")

    data[time_col] = parsed
    data = data.sort_values(by=time_col, kind='stable').reset_index(drop=True)
    logger.info("Data sorted by time column.")

    # Output naming
    output_dir = os.path.dirname(selected_files[0])
    base_fname = os.path.basename(selected_files[-1])
    standardized_fname = re.sub(
        r'Time History(?:\s*\d+)?\.csv$', 'Time History.csv',
        base_fname, flags=re.IGNORECASE
    )
    output_fname = f"{sitename}_{standardized_fname}"
    output_path = os.path.join(output_dir, output_fname)

    # Write CSV
    data.to_csv(output_path, index=False, quoting=csv.QUOTE_NONE, escapechar='\\')
    logger.info(f"Output written: {output_path}")
    logger.info("----- Combine SLM Time History run completed -----")
    return output_path

# ------------------------------------------------------------------------------
# Main Application GUI
# ------------------------------------------------------------------------------
class LD821CombineApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("LD821 Time History Combiner")
        self.geometry("560x520")
        self.resizable(True, True)

        self.selected_folder = ""
        self.matched_files = []
        self._build_gui()

    def _build_gui(self):
        main_frame = ttk.Frame(self, padding="12")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # --- Folder Selector Group ---
        grp_folder = ttk.LabelFrame(main_frame, text=" RAW Folder Selector ", padding="10")
        grp_folder.pack(fill=tk.BOTH, expand=True, pady=5)

        btn_browse = ttk.Button(grp_folder, text="Select High-Level Directory Where Time History Files Live (e.g. RAW)...", command=self.browse_folder)
        btn_browse.pack(anchor="w", pady=(0, 5))

        self.lbl_folder_status = ttk.Label(grp_folder, text="No folder selected", font=("Segoe UI", 9, "italic"))
        self.lbl_folder_status.pack(anchor="w", pady=(0, 2))

        # Listbox displaying downstream matched Time History files
        list_frame = ttk.Frame(grp_folder)
        list_frame.pack(fill=tk.BOTH, expand=True)

        self.lst_files = tk.Listbox(list_frame, height=6, selectmode=tk.EXTENDED)
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.lst_files.yview)
        self.lst_files.configure(yscrollcommand=scrollbar.set)

        self.lst_files.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # --- Metadata Inputs Group ---
        grp_meta = ttk.LabelFrame(main_frame, text=" Site & Deployment Settings ", padding="10")
        grp_meta.pack(fill=tk.X, pady=5)

        # sitename
        lbl_site = ttk.Label(grp_meta, text="Site Name:", width=18, anchor="w")
        lbl_site.grid(row=0, column=0, sticky="w", pady=4)
        self.var_sitename = tk.StringVar(value="PARK001")
        ent_site = ttk.Entry(grp_meta, textvariable=self.var_sitename)
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

        # --- Run Button ---
        btn_run = ttk.Button(main_frame, text="Combine and Process Files", command=self.run_process)
        btn_run.pack(fill=tk.X, pady=12)

    def browse_folder(self):
        folder = filedialog.askdirectory(title="Select High-Level Directory (RAW)")
        if not folder:
            return

        self.selected_folder = folder
        self.matched_files = []
        self.lst_files.delete(0, tk.END)

        # Recursively search for matching "Time History" CSV files
        for root, _, filenames in os.walk(folder):
            for f in filenames:
                if TIME_HISTORY_PATTERN.search(f):
                    full_path = os.path.join(root, f)
                    self.matched_files.append(full_path)

        if self.matched_files:
            self.lbl_folder_status.config(
                text=f"Found {len(self.matched_files)} 'Time History' file(s) in {os.path.basename(folder)}"
            )
            for f in self.matched_files:
                rel_path = os.path.relpath(f, folder)
                self.lst_files.insert(tk.END, rel_path)
        else:
            self.lbl_folder_status.config(text="No matching 'Time History' CSV files found in directory.")
            messagebox.showwarning(
                "No Matching Files",
                f"No CSV files ending with 'Time History.csv' (or 'Time History 1.csv', etc.) were found in:\n{folder}"
            )

    def run_process(self):
        if not self.matched_files:
            messagebox.showwarning("Missing Input", "Please select a directory containing 'Time History' CSV files first.")
            return

        sitename = self.var_sitename.get().strip()
        deploy = self.var_deploy.get().strip()

        output_dir = os.path.dirname(self.matched_files[0])

        try:
            logger = setup_logger(output_dir, sitename, deploy)
            output_path = process_slm_files(self.matched_files, sitename, deploy, logger)

            messagebox.showinfo(
                "Processing Complete",
                f"Successfully combined {len(self.matched_files)} file(s).\n\nOutput saved to:\n{output_path}"
            )
        except Exception as e:
            messagebox.showerror("Execution Error", f"An error occurred while combining files:\n{e}")

# ------------------------------------------------------------------------------
# Entry Point
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    app = LD821CombineApp()
    app.mainloop()