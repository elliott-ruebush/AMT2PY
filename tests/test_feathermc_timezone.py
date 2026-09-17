"""Unit tests for Feather MC timezone conversion helpers (no GUI).

Layout:
  - Conversion basics (zone list, Phoenix/Shiprock, fixed offset when deployment does not cross DST)
  - DST span scenarios for America/Denver in 2024 (spring forward / fall back)
  - Duplicate timestamp logging helpers
"""

from __future__ import annotations

import logging
import os
import sys
import unittest

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from amt2py.timezone_utils import (
    CURATED_US_TIMEZONES,
    build_timezone_list,
    convert_utc_to_local,
    drop_duplicate_utc_timestamps,
    dst_transitions_in_utc_range,
    find_duplicate_local_timestamp_groups,
    log_duplicate_local_timestamps,
    summarize_duplicate_loc_groups,
)

DENVER = "America/Denver"
PHOENIX = "America/Phoenix"
SHIPROCK = "America/Shiprock"
LOC_FMT = "%m/%d/%Y %H:%M:%S"

# America/Denver — 2024-03-10 spring forward (02:00 local does not exist)
SPRING_1AM_MST_UTC = "2024-03-10 08:00:00"
SPRING_3AM_MDT_UTC = "2024-03-10 09:00:00"

# America/Denver — 2024-11-03 fall back (01:00 local occurs twice under zone rules)
FALL_1AM_MDT_UTC = "2024-11-03 07:00:00"
FALL_1AM_MST_UTC = "2024-11-03 08:00:00"


class _ListHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.messages: list[str] = []

    def emit(self, record):
        self.messages.append(record.getMessage())


class _TimezoneTestCase(unittest.TestCase):
    """Shared logger and convert_utc_to_local helpers."""

    def setUp(self):
        self.logger = logging.getLogger("test_feathermc_timezone")
        self.logger.handlers.clear()
        self.logger.setLevel(logging.DEBUG)
        self._handler = _ListHandler()
        self.logger.addHandler(self._handler)

    def convert(self, *utc_strings: str, tz: str = DENVER, adjust_dst: bool = True):
        utc = pd.Series([pd.Timestamp(s) for s in utc_strings])
        local, abbr = convert_utc_to_local(utc, tz, adjust_dst, self.logger)
        return utc, local, abbr

    @staticmethod
    def loc_strings(local: pd.Series) -> list[str]:
        return local.dt.strftime(LOC_FMT).tolist()

    @staticmethod
    def abbr_list(abbr) -> list[str]:
        return abbr.tolist() if hasattr(abbr, "tolist") else list(abbr)

    @staticmethod
    def naive_wall_time(local: pd.Series, index: int = 0) -> pd.Timestamp:
        return local.iloc[index].replace(tzinfo=None)


class FeatherMCTimezoneBasicsTests(_TimezoneTestCase):
    def test_curated_us_zones_lead_timezone_list(self):
        tz_list = build_timezone_list()
        self.assertEqual(tz_list[: len(CURATED_US_TIMEZONES)], CURATED_US_TIMEZONES)
        self.assertEqual(len(tz_list), len(set(tz_list)))

    def test_phoenix_no_dst_rules_and_fixed_agree_in_summer(self):
        _, local_rules, abbr_rules = self.convert("2024-07-15 18:00:00", tz=PHOENIX, adjust_dst=True)
        _, local_fixed, abbr_fixed = self.convert("2024-07-15 18:00:00", tz=PHOENIX, adjust_dst=False)
        self.assertEqual(self.abbr_list(abbr_rules)[0], "MST")
        self.assertEqual(self.abbr_list(abbr_rules)[0], self.abbr_list(abbr_fixed)[0])
        self.assertEqual(local_rules.iloc[0].hour, 11)
        self.assertEqual(local_fixed.iloc[0].hour, 11)

    def test_phoenix_no_dst_rules_and_fixed_agree_in_winter(self):
        _, local_rules, abbr_rules = self.convert("2024-01-15 18:00:00", tz=PHOENIX, adjust_dst=True)
        _, local_fixed, abbr_fixed = self.convert("2024-01-15 18:00:00", tz=PHOENIX, adjust_dst=False)
        self.assertEqual(self.abbr_list(abbr_rules)[0], "MST")
        self.assertEqual(self.abbr_list(abbr_rules)[0], self.abbr_list(abbr_fixed)[0])
        self.assertEqual(local_rules.iloc[0].hour, local_fixed.iloc[0].hour)

    def test_shiprock_observes_dst_like_denver_in_summer(self):
        sample_utc = "2024-07-15 18:00:00"
        _, loc_phx, abbr_phx = self.convert(sample_utc, tz=PHOENIX, adjust_dst=True)
        _, loc_shp, abbr_shp = self.convert(sample_utc, tz=SHIPROCK, adjust_dst=True)
        _, loc_den, abbr_den = self.convert(sample_utc, tz=DENVER, adjust_dst=True)
        self.assertEqual(self.abbr_list(abbr_phx)[0], "MST")
        self.assertEqual(loc_phx.iloc[0].hour, 11)
        self.assertEqual(self.abbr_list(abbr_shp)[0], "MDT")
        self.assertEqual(self.abbr_list(abbr_den)[0], "MDT")
        self.assertEqual(loc_shp.iloc[0].hour, loc_den.iloc[0].hour)
        self.assertEqual(loc_shp.iloc[0].hour, loc_phx.iloc[0].hour + 1)

    def test_denver_zone_rules_mdt_in_summer(self):
        _, local, abbr = self.convert("2024-07-15 18:00:00", adjust_dst=True)
        self.assertEqual(self.abbr_list(abbr)[0], "MDT")
        self.assertEqual(local.iloc[0].hour, 12)

    def test_denver_fixed_offset_matches_zone_rules_when_start_is_summer(self):
        sample_utc = "2024-07-15 18:00:00"
        _, local_rules, abbr_rules = self.convert(sample_utc, adjust_dst=True)
        _, local_fixed, abbr_fixed = self.convert(sample_utc, adjust_dst=False)
        self.assertEqual(self.naive_wall_time(local_rules), local_fixed.iloc[0])
        self.assertEqual(self.abbr_list(abbr_rules)[0], self.abbr_list(abbr_fixed)[0])
        self.assertEqual(self.abbr_list(abbr_rules)[0], "MDT")

    def test_denver_fixed_offset_matches_zone_rules_when_start_is_winter(self):
        sample_utc = "2024-01-15 18:00:00"
        _, local_rules, abbr_rules = self.convert(sample_utc, adjust_dst=True)
        _, local_fixed, abbr_fixed = self.convert(sample_utc, adjust_dst=False)
        self.assertEqual(self.naive_wall_time(local_rules), local_fixed.iloc[0])
        self.assertEqual(self.abbr_list(abbr_rules)[0], self.abbr_list(abbr_fixed)[0])
        self.assertEqual(self.abbr_list(abbr_rules)[0], "MST")


class FeatherMCDstFallBackTests(_TimezoneTestCase):
    def test_zone_rules_repeat_local_hour_with_distinct_utc(self):
        utc, local, abbr = self.convert(FALL_1AM_MDT_UTC, FALL_1AM_MST_UTC, adjust_dst=True)
        loc = self.loc_strings(local)
        self.assertEqual(loc, ["11/03/2024 01:00:00", "11/03/2024 01:00:00"])
        self.assertEqual(self.abbr_list(abbr), ["MDT", "MST"])

        df = pd.DataFrame({"Date-Time (LOC)": loc, "UTC": utc})
        groups = find_duplicate_local_timestamp_groups(df)
        self.assertEqual(len(groups), 1)
        identical, distinct = summarize_duplicate_loc_groups(groups)
        self.assertEqual((identical, distinct), (0, 1))

    def test_fixed_offset_from_summer_start_avoids_duplicate_local_hour(self):
        _, local, abbr = self.convert(
            "2024-07-15 12:00:00",
            FALL_1AM_MDT_UTC,
            "2024-11-03 09:00:00",
            adjust_dst=False,
        )
        loc = self.loc_strings(local)
        self.assertEqual(len(loc), len(set(loc)))
        self.assertTrue(all(a == "MDT" for a in abbr))

    def test_dst_transition_detected_in_utc_range(self):
        utc_min = pd.Timestamp("2024-11-02 00:00:00")
        utc_max = pd.Timestamp("2024-11-04 00:00:00")
        self.assertTrue(dst_transitions_in_utc_range(DENVER, utc_min, utc_max))


class FeatherMCDstSpringForwardTests(_TimezoneTestCase):
    def test_zone_rules_skip_local_two_am(self):
        _, local, abbr = self.convert(SPRING_1AM_MST_UTC, SPRING_3AM_MDT_UTC, adjust_dst=True)
        self.assertEqual(
            self.loc_strings(local),
            ["03/10/2024 01:00:00", "03/10/2024 03:00:00"],
        )
        self.assertEqual(self.abbr_list(abbr), ["MST", "MDT"])

    def test_fixed_offset_from_winter_start_ignores_spring_forward(self):
        deployment_utc = (
            "2024-01-15 12:00:00",
            SPRING_1AM_MST_UTC,
            SPRING_3AM_MDT_UTC,
        )
        _, local_fixed, abbr_fixed = self.convert(*deployment_utc, adjust_dst=False)
        self.assertTrue(all(a == "MST" for a in abbr_fixed))
        loc_fixed = self.loc_strings(local_fixed)
        self.assertEqual(len(loc_fixed), len(set(loc_fixed)))
        self.assertEqual(loc_fixed[-1], "03/10/2024 02:00:00")

        _, local_rules, _ = self.convert(*deployment_utc, adjust_dst=True)
        self.assertEqual(
            self.naive_wall_time(local_rules, -1).strftime(LOC_FMT),
            "03/10/2024 03:00:00",
        )

    def test_dst_transition_detected_in_utc_range(self):
        utc_min = pd.Timestamp("2024-03-09 00:00:00")
        utc_max = pd.Timestamp("2024-03-11 00:00:00")
        self.assertTrue(dst_transitions_in_utc_range(DENVER, utc_min, utc_max))


class FeatherMCDuplicateTimestampTests(_TimezoneTestCase):
    def test_find_duplicate_loc_groups_with_distinct_utc(self):
        df = pd.DataFrame(
            {
                "Date-Time (LOC)": ["01/01/2024 10:00:00", "01/01/2024 10:00:00", "01/01/2024 11:00:00"],
                "UTC": [
                    pd.Timestamp("2024-01-01 17:00:00"),
                    pd.Timestamp("2024-01-01 17:00:05"),
                    pd.Timestamp("2024-01-01 18:00:00"),
                ],
            }
        )
        groups = find_duplicate_local_timestamp_groups(df)
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0][0], "01/01/2024 10:00:00")
        self.assertEqual(len(groups[0][1]), 2)
        identical, distinct = summarize_duplicate_loc_groups(groups)
        self.assertEqual((identical, distinct), (0, 1))

    def test_log_duplicate_loc_truncates_long_example_lists(self):
        rows = []
        for i in range(10):
            loc = f"01/01/2024 10:00:{i:02d}"
            utc = pd.Timestamp(f"2024-01-01 17:00:{i:02d}")
            rows.append({"Date-Time (LOC)": loc, "UTC": utc})
            rows.append({"Date-Time (LOC)": loc, "UTC": utc})
        df = pd.DataFrame(rows)
        self.assertEqual(len(find_duplicate_local_timestamp_groups(df)), 10)
        log_duplicate_local_timestamps(df, self.logger, max_examples_per_end=2)
        text = "\n".join(self._handler.messages)
        self.assertIn("first 2 and last 2", text)
        self.assertIn("6 of 10 omitted", text)
        self.assertIn("identical UTC", text)

    def test_drop_duplicate_utc_keeps_first_row(self):
        df = pd.DataFrame(
            {
                "Date-Time (UTC)": ["2026-08-02 00:53:43", "2026-08-02 00:53:43"],
                "val": [1.0, 2.0],
            }
        )
        df["UTC"] = pd.to_datetime(df["Date-Time (UTC)"])
        out = drop_duplicate_utc_timestamps(df, self.logger)
        self.assertEqual(len(out), 1)
        self.assertEqual(out.iloc[0]["val"], 1.0)
        self.assertTrue(any("Removed 1 duplicate" in m for m in self._handler.messages))


if __name__ == "__main__":
    unittest.main()
