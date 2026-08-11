# -*- coding: utf-8 -*-
"""Exact column names for FeatherMC combined MET CSV (NVSPL merge contract)."""

from schemas.utils import col_index, header_columns

# Added by FeatherMC_combine.clean_and_format_data
FEATHERMC_COMBINED_TIMESTAMP = "Date-Time (LOC)"
FEATHERMC_ADDED_COLUMNS = ("UTC", FEATHERMC_COMBINED_TIMESTAMP, "Time Zone")

# Raw logger columns preserved by combine (microSD export header strings)
FEATHERMC_WIND_GUST = ("Wind Spd Max", "Gust m/s")
FEATHERMC_WIND_DIR = ("Dir",)
FEATHERMC_TEMP = ("Temp",)


def is_feathermc_combined_header(header_row):
    return FEATHERMC_COMBINED_TIMESTAMP in header_columns(header_row)


def infer_feathermc_met_gui_indices(header_row):
    """Exact header-name lookup for FeatherMC combined CSV."""
    cols = header_columns(header_row)
    ts_i = col_index(cols, (FEATHERMC_COMBINED_TIMESTAMP,))
    gust_i = col_index(cols, FEATHERMC_WIND_GUST)
    dir_i = col_index(cols, FEATHERMC_WIND_DIR)
    tmp_i = col_index(cols, FEATHERMC_TEMP)
    return {
        "MET_TIMESTAMP_IDX": str(ts_i) if ts_i is not None else "",
        "MET_WINDSPD_IDX": str(gust_i) if gust_i is not None else "",
        "MET_WINDDIR_IDX": str(dir_i) if dir_i is not None else "None",
        "MET_EXTERNTEMP_IDX": str(tmp_i) if tmp_i is not None else "None",
    }


def feathermc_met_runtime_indices(header_row):
    """Same names as infer_feathermc_met_gui_indices, for load_met_samples schema."""
    cols = header_columns(header_row)
    return {
        "ts_idx": col_index(cols, (FEATHERMC_COMBINED_TIMESTAMP,)),
        "spd_idx": col_index(cols, FEATHERMC_WIND_GUST),
        "dir_idx": col_index(cols, FEATHERMC_WIND_DIR),
        "tmp_idx": col_index(cols, FEATHERMC_TEMP),
    }
