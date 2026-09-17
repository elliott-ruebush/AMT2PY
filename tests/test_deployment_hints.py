"""Tests for deployment path / MET folder metadata hints."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from amt2py.schemas.deployment_hints import apply_deployment_hints, infer_feathermc_serial_from_met_folder
from amt2py.schemas.ld821_spl import infer_site_id_from_spl_csv_path
from amt2py.schemas.monitoring_site import infer_monitoring_site_id

_FEATHERMC_MD_SAMPLE = """Anemometer MetaData Log, 00000003
#,Date-Time(UTC),Temperature,Last GPS Sync,RTC Drift (s)
1,5/21/2026 19:38:32,12.25,5_21,1.00
"""


class DeploymentHintsTests(unittest.TestCase):
    def test_site_from_alaska_style_path(self):
        path = r"/data/2026 DENATRLA Triple Lakes/01 DATA/MET"
        hints = apply_deployment_hints(path)
        self.assertEqual(hints["site_id"], "DENATRLA")

    def test_site_care001_token(self):
        self.assertEqual(infer_monitoring_site_id("CARE001_Time History.csv"), "CARE001")

    def test_site_long_prefix_extracts_code(self):
        site = infer_monitoring_site_id(
            "2026 DENATRLA Triple Lakes extra stuff",
            "MORUA2503_20260626",
        )
        self.assertEqual(site, "DENATRLA")

    def test_first_match_across_sources(self):
        self.assertEqual(
            infer_monitoring_site_id("MORUA2503_20260626", "2026 DENATRLA Triple Lakes"),
            "MORUA2503",
        )

    def test_serial_not_inferred_from_combined_csv_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            open(os.path.join(tmp, "00000018 2026-07-09 125259.csv"), "w").close()
            self.assertEqual(infer_feathermc_serial_from_met_folder(tmp), "")

    def test_serial_from_feathermc_md_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "0521MD.CSV")
            with open(path, "w", encoding="utf-8") as f:
                f.write(_FEATHERMC_MD_SAMPLE)
            self.assertEqual(infer_feathermc_serial_from_met_folder(tmp), "00000003")

    def test_serial_from_md_csv_when_combined_output_also_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            open(os.path.join(tmp, "00000018 2026-07-09 125259.csv"), "w").close()
            path = os.path.join(tmp, "0521MD.CSV")
            with open(path, "w", encoding="utf-8") as f:
                f.write(_FEATHERMC_MD_SAMPLE)
            self.assertEqual(infer_feathermc_serial_from_met_folder(tmp), "00000003")

    def test_spl_path_inference(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw = os.path.join(tmp, "2026 DENATRLA Triple Lakes", "01 DATA", "RAW")
            os.makedirs(raw)
            csv_path = os.path.join(raw, "DENATRLA_Time History.csv")
            open(csv_path, "w").close()
            self.assertEqual(infer_site_id_from_spl_csv_path(csv_path), "DENATRLA")


if __name__ == "__main__":
    unittest.main()
