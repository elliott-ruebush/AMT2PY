# -*- coding: utf-8 -*-
"""G4 Time History / ld821_combine output column contract for NVSPL parsing."""

import csv
import os
import re

from schemas.utils import col_index, header_columns, normalize_gui_path

LD821_HEADER_MARKER = "Record Type"
LD821_RECORD_TYPE = "Record Type"
LD821_DATE = "Date"
LD821_LAEQ = "LAeq"
LD821_LZEQ = "LZeq"
LD821_LCEQ = "LCeq"
LD821_EXTERNAL_POWER = "External Power"
LD821_H12P5 = "H12.5"
LD821_OVLD = "OVLD"
LD821_TIMESTAMP_FMT = "%Y-%m-%d %H:%M:%S"
LD821_COMBINED_BASENAME = "Time History.csv"

LD821_BAND_COLUMNS = (
    "H12.5", "H15.8", "H20", "H25", "H31.5", "H40", "H50", "H63", "H80", "H100",
    "H125", "H160", "H200", "H250", "H315", "H400", "H500", "H630", "H800", "H1000",
    "H1250", "H1600", "H2000", "H2500", "H3150", "H4000", "H5000", "H6300", "H8000",
    "H10000", "H12500", "H16000", "H20000",
)

LD821_SPL_HEADER = (
    [LD821_RECORD_TYPE, LD821_DATE, LD821_LAEQ, LD821_LZEQ, LD821_LCEQ, LD821_EXTERNAL_POWER]
    + list(LD821_BAND_COLUMNS)
    + [LD821_OVLD]
)

_COMBINED_SPL_NAME = re.compile(
    rf"^(.+)_{re.escape(LD821_COMBINED_BASENAME)}$",
    re.IGNORECASE,
)


def is_ld821_time_history_header(header_row):
    return LD821_HEADER_MARKER in header_columns(header_row)


def find_ld821_header_fields(lines):
    """Return parsed header row from first line containing Record Type."""
    for line in lines:
        if LD821_HEADER_MARKER in line:
            return next(csv.reader([line]))
    return None


def _external_power_index(cols):
    i = col_index(cols, (LD821_EXTERNAL_POWER,))
    if i is not None:
        return i
    for idx, name in enumerate(cols):
        if name.startswith("External"):
            return idx
    return None


def _overload_index(cols):
    i = col_index(cols, (LD821_OVLD,))
    if i is not None:
        return i
    for idx, name in enumerate(cols):
        if "Invalid" in name or name.startswith("OVLD"):
            return idx
    return None


def ld821_spl_runtime_indices(header_row):
    """Exact G4 column lookup; optional columns may be None."""
    cols = header_columns(header_row)
    return {
        "sdate_idx": col_index(cols, (LD821_DATE,)),
        "dba_idx": col_index(cols, (LD821_LAEQ,)),
        "dbz_idx": col_index(cols, (LD821_LZEQ,)),
        "dbc_idx": col_index(cols, (LD821_LCEQ,)),
        "power_idx": _external_power_index(cols),
        "h12p5_idx": col_index(cols, (LD821_H12P5,)),
        "ovr_idx": _overload_index(cols),
    }


def validate_ld821_header(header_row):
    idx = ld821_spl_runtime_indices(header_row)
    if idx["sdate_idx"] is None or idx["h12p5_idx"] is None:
        raise RuntimeError("LD821 required columns not found (Date and H12.5 band).")
    return idx


def parse_site_from_combined_spl_filename(path):
    """Extract site prefix from '{site}_Time History.csv' (ld821_combine output)."""
    match = _COMBINED_SPL_NAME.match(os.path.basename(path))
    return match.group(1).strip() if match else ""


def infer_spl_gui_defaults(csv_path):
    """SITE_ID and OUTPUT_DIR hints when browsing combined SPL in NVSPL GUI."""
    site = parse_site_from_combined_spl_filename(csv_path)
    if not site:
        return {}
    csv_dir = os.path.dirname(os.path.abspath(csv_path))
    nvspl_dir = os.path.join(csv_dir, "NVSPL")
    output_dir = nvspl_dir if os.path.isdir(nvspl_dir) else csv_dir
    return {
        "SITE_ID": site,
        "OUTPUT_DIR": normalize_gui_path(output_dir),
    }
