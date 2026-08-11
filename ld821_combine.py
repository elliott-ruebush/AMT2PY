# -*- coding: utf-8 -*-
import os
import re
import csv
import logging
import threading
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
def setup_logger(output_dir: str, sitename: str, deploy: str):
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
    return logger, log_path

def close_logger(logger: logging.Logger):
    for handler in logger.handlers[:]:
        handler.close()
        logger.removeHandler(handler)

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

def process_slm_files(selected_files: list, sitename: str, deploy: str, logger: logging.Logger, output_dir: str, progress_callback=None):
    n = len(selected_files)
    total = n + 2

    def report(step, msg):
        if progress_callback:
            progress_callback(step, total, msg)

    logger.info(f"Files matched Time History pattern: {n}")
    for f in selected_files:
        logger.info(f"  ✔ {f}")

    report(0, "Starting…")

    # Read CSVs
    dfs = []
    for i, f in enumerate(selected_files):
        report(i + 1, f"Reading file {i + 1} of {n}…")
        try:
            df = pd.read_csv(f)
            dfs.append(df)
            logger.info(f"Read OK: {f} | Rows: {len(df)} | Columns: {list(df.columns)}")
        except Exception as e:
            logger.error(f"Failed to read {f}: {e}")
            raise

    report(n + 1, "Combining and sorting…")

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

    # Output naming — always write to the folder the user selected in the GUI
    base_fname = os.path.basename(selected_files[-1])
    standardized_fname = re.sub(
        r'Time History(?:\s*\d+)?\.csv$', 'Time History.csv',
        base_fname, flags=re.IGNORECASE
    )
    output_fname = f"{sitename}_{standardized_fname}"
    output_path = os.path.join(output_dir, output_fname)

    report(n + 2, "Writing output…")

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

        # --- Folder Selector Group ---
        grp_folder = ttk.LabelFrame(main_frame, text=" RAW Folder Selector ", padding="10")
        grp_folder.pack(fill=tk.BOTH, expand=True, pady=5)

        btn_browse = ttk.Button(grp_folder, text="Select High-Level Directory Where Time History Files Live (e.g. RAW)...", command=self.browse_folder)
        btn_browse.pack(anchor="w", pady=(0, 5))
        self.btn_browse = btn_browse

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

    def browse_folder(self):
        if self._worker_running:
            return
        folder = filedialog.askdirectory(title="Select High-Level Directory (RAW)")
        if not folder:
            return

        self.selected_folder = folder
        self.matched_files = []
        self.lst_files.delete(0, tk.END)
        self._set_result("")

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
        if self._worker_running:
            return
        if not self.matched_files:
            messagebox.showwarning("Missing Input", "Please select a directory containing 'Time History' CSV files first.")
            return

        sitename = self.var_sitename.get().strip()
        deploy = self.var_deploy.get().strip()

        source_dirs = {os.path.dirname(f) for f in self.matched_files}
        if len(source_dirs) > 1:
            proceed = messagebox.askyesno(
                "Multiple source folders",
                f"Time History files were found in {len(source_dirs)} different subfolders.\n\n"
                "Please confirm these are the files you want to combine.\n\n"
                "Continue?"
            )
            if not proceed:
                return

        output_dir = self.selected_folder
        files = list(self.matched_files)

        self._worker_running = True
        self._set_busy(True)
        self._set_result("")
        self._update_progress(0, 1, "Starting…")

        threading.Thread(
            target=self._run_worker,
            args=(output_dir, sitename, deploy, files),
            daemon=True,
        ).start()

    def _run_worker(self, output_dir, sitename, deploy, files):
        logger = None

        def progress(step, total, message):
            self._on_ui(self._update_progress, step, total, message)

        try:
            logger, log_path = setup_logger(output_dir, sitename, deploy)
            output_path = process_slm_files(
                files, sitename, deploy, logger, output_dir,
                progress_callback=progress,
            )
            self._on_ui(self._on_success, output_path, log_path, len(files))
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
            f"LD821 combine done — {file_count} file(s)\n"
            f"Output: {output_path}\n"
            f"Log: {log_path}",
            ok=True,
        )
        messagebox.showinfo(
            "LD821 Combine — Complete",
            f"LD821 Time History Combiner finished successfully.\n\n"
            f"Combined {file_count} file(s).\n\nOutput saved to:\n{output_path}"
        )

    def _on_failure(self, error):
        self._reset_progress()
        self._set_result(f"Failed — {error}", ok=False)
        messagebox.showerror(
            "LD821 Combine — Error",
            f"LD821 Time History Combiner failed:\n{error}"
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
    app = LD821CombineApp()
    app.mainloop()