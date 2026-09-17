# -*- coding: utf-8 -*-
"""Timezone helpers for Feather MC combine (no GUI dependencies)."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import List, Sequence, Tuple

import pandas as pd
import pytz

CURATED_US_TIMEZONES: List[str] = [
    "America/New_York",
    "America/Chicago",
    "America/Denver",
    "America/Phoenix",
    "America/Shiprock",
    "America/Los_Angeles",
    "America/Anchorage",
    "America/Honolulu",
]


def build_timezone_list() -> List[str]:
    curated = set(CURATED_US_TIMEZONES)
    try:
        rest = [tz for tz in pytz.all_timezones if tz not in curated]
        return list(CURATED_US_TIMEZONES) + rest
    except Exception:
        return list(CURATED_US_TIMEZONES)


def convert_utc_to_local(
    utc_series: pd.Series,
    tz_name: str,
    adjust_dst: bool,
    logger: logging.Logger,
):
    local_tz = pytz.timezone(tz_name)
    utc_aware = utc_series.dt.tz_localize("UTC")

    if adjust_dst:
        local_times = utc_aware.dt.tz_convert(local_tz)
        tz_abbr = local_times.dt.strftime("%Z")
        logger.info(f"Converted timestamps from UTC to {tz_name} with DST rules applied.")
    else:
        anchor_ts = utc_series.min()
        anchor_dt = anchor_ts.to_pydatetime()
        if getattr(anchor_ts, "tzinfo", None) is None:
            anchor_utc = pytz.UTC.localize(anchor_dt)
        else:
            anchor_utc = anchor_dt.astimezone(pytz.UTC)
        local_at_start = anchor_utc.astimezone(local_tz)
        fixed_offset = local_at_start.utcoffset()
        tz_abbr_val = local_at_start.tzname()
        local_times = utc_aware.dt.tz_localize(None) + fixed_offset
        tz_abbr = [tz_abbr_val] * len(local_times)
        logger.info(
            "Converted timestamps from UTC to %s using fixed offset from deployment start "
            "(%s UTC → %s, abbr %s; DST transitions after start are not applied).",
            tz_name,
            anchor_utc.strftime("%Y-%m-%d %H:%M:%S"),
            local_at_start.strftime("%Y-%m-%d %H:%M:%S"),
            tz_abbr_val,
        )

    return local_times, tz_abbr


def conversion_mode_description(adjust_dst: bool) -> str:
    if adjust_dst:
        return "IANA zone rules (including DST when this zone observes it)"
    return "fixed offset from deployment start (manual override; ignores DST transitions)"


def unique_timezone_abbreviations(tz_abbr: Sequence) -> List:
    return pd.Series(list(tz_abbr)).unique().tolist()


def log_mixed_timezone_abbreviations(tz_abbr: Sequence, logger: logging.Logger) -> List:
    unique_abbr = unique_timezone_abbreviations(tz_abbr)
    if len(unique_abbr) > 1:
        logger.warning(
            "More than one time zone abbreviation in 'Time Zone' column (%s). "
            "This is expected when data span a DST transition with zone rules enabled; "
            "verify the selected deployment zone.",
            unique_abbr,
        )
    return unique_abbr


def find_duplicate_local_timestamp_groups(
    df: pd.DataFrame,
) -> List[Tuple[str, List[pd.Timestamp]]]:
    """Return (LOC string, list of UTC timestamps) for each duplicated LOC value."""
    if "Date-Time (LOC)" not in df.columns or "UTC" not in df.columns:
        return []
    dup_loc = df.loc[df.duplicated(subset=["Date-Time (LOC)"], keep=False), "Date-Time (LOC)"]
    if dup_loc.empty:
        return []
    groups: List[Tuple[str, List[pd.Timestamp]]] = []
    for loc in dup_loc.unique():
        utc_vals = df.loc[df["Date-Time (LOC)"] == loc, "UTC"].tolist()
        groups.append((loc, utc_vals))
    return groups


def drop_duplicate_utc_timestamps(
    df: pd.DataFrame,
    logger: logging.Logger,
) -> pd.DataFrame:
    """Drop repeated UTC instants; keep first row (concat / file order)."""
    if "UTC" not in df.columns or df.empty:
        return df
    before = len(df)
    out = df.drop_duplicates(subset=["UTC"], keep="first")
    removed = before - len(out)
    if removed:
        logger.info(
            "Removed %d duplicate row(s) with the same UTC timestamp "
            "(kept first by combine order).",
            removed,
        )
    return out


def duplicate_loc_group_has_distinct_utc(utc_vals: Sequence) -> bool:
    """True when duplicate LOC rows map to more than one UTC instant (e.g. DST fall-back)."""
    normalized = {pd.Timestamp(u) for u in utc_vals}
    return len(normalized) > 1


def summarize_duplicate_loc_groups(
    groups: Sequence[Tuple[str, List[pd.Timestamp]]],
) -> Tuple[int, int]:
    """Return (identical_utc_count, distinct_utc_count) for duplicate LOC groups."""
    identical = 0
    distinct = 0
    for _, utc_vals in groups:
        if duplicate_loc_group_has_distinct_utc(utc_vals):
            distinct += 1
        else:
            identical += 1
    return identical, distinct


def _format_duplicate_loc_example(loc: str, utc_vals: Sequence) -> str:
    utc_strs = [str(u) for u in utc_vals]
    kind = "distinct UTC" if duplicate_loc_group_has_distinct_utc(utc_vals) else "identical UTC"
    return f"Duplicate LOC {loc!r} ({kind}) → UTC: {', '.join(utc_strs)}"


def _duplicate_loc_groups_for_log(
    groups: Sequence[Tuple[str, List[pd.Timestamp]]],
    max_examples_per_end: int,
) -> Tuple[List[Tuple[str, List[pd.Timestamp]]], bool]:
    """First N and last N groups; omit middle when len(groups) > 2 * max_examples_per_end."""
    n = len(groups)
    cap = max_examples_per_end * 2
    if n <= cap:
        return list(groups), False
    return list(groups[:max_examples_per_end]) + list(groups[-max_examples_per_end:]), True


def log_duplicate_local_timestamps(
    df: pd.DataFrame,
    logger: logging.Logger,
    max_examples_per_end: int = 3,
) -> int:
    groups = find_duplicate_local_timestamp_groups(df)
    if not groups:
        return 0
    row_count = int(df.duplicated(subset=["Date-Time (LOC)"], keep=False).sum())
    identical, distinct = summarize_duplicate_loc_groups(groups)
    logger.warning(
        "Duplicate 'Date-Time (LOC)' strings: %d unique local timestamp(s) repeat "
        "(%d row(s) involved). Groups with identical UTC: %d; "
        "groups with distinct UTC (same LOC, different instants): %d. "
        "Downstream NVSPL merge keys on LOC only.",
        len(groups),
        row_count,
        identical,
        distinct,
    )
    examples, truncated = _duplicate_loc_groups_for_log(groups, max_examples_per_end)
    if truncated:
        omitted = len(groups) - len(examples)
        logger.warning(
            "Logging first %d and last %d example group(s) only (%d of %d omitted).",
            max_examples_per_end,
            max_examples_per_end,
            omitted,
            len(groups),
        )
    for i, (loc, utc_vals) in enumerate(examples):
        if truncated and i == max_examples_per_end:
            logger.warning("  …")
        logger.warning("  %s", _format_duplicate_loc_example(loc, utc_vals))
    return len(groups)


def dst_transitions_in_utc_range(
    tz_name: str,
    utc_min: pd.Timestamp,
    utc_max: pd.Timestamp,
) -> List[datetime]:
    """Return naive-UTC transition instants for the zone that fall inside [utc_min, utc_max]."""
    local_tz = pytz.timezone(tz_name)
    transition_times = getattr(local_tz, "_utc_transition_times", None)
    if transition_times is None or utc_min is pd.NaT or utc_max is pd.NaT:
        return []
    matched: List[datetime] = []
    for trans in transition_times:
        if utc_min.to_pydatetime() <= trans <= utc_max.to_pydatetime():
            matched.append(trans)
    return matched


def log_timezone_conversion_summary(
    df: pd.DataFrame,
    tz_name: str,
    adjust_dst: bool,
    logger: logging.Logger,
) -> None:
    if df.empty or "UTC" not in df.columns:
        return

    utc_min = df["UTC"].min()
    utc_max = df["UTC"].max()
    logger.info("UTC data range: %s → %s", utc_min, utc_max)
    logger.info("Conversion mode: %s", conversion_mode_description(adjust_dst))

    if "Date-Time (LOC)" in df.columns:
        logger.info(
            "Local range after conversion: %s → %s",
            df["Date-Time (LOC)"].iloc[0],
            df["Date-Time (LOC)"].iloc[-1],
        )

    transitions = dst_transitions_in_utc_range(tz_name, utc_min, utc_max)
    if transitions:
        formatted = ", ".join(t.strftime("%Y-%m-%d %H:%M:%S UTC") for t in transitions)
        logger.info(
            "DST transition(s) for %s within UTC data range: %s",
            tz_name,
            formatted,
        )
    else:
        logger.info(
            "No DST transition for %s falls inside UTC data range [%s, %s].",
            tz_name,
            utc_min,
            utc_max,
        )
