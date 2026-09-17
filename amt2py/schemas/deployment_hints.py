# -*- coding: utf-8 -*-
"""Shared deployment metadata hints for 821 / Feather MC GUIs."""

from __future__ import annotations

import os
import re
from collections import Counter

from amt2py.schemas.monitoring_site import infer_monitoring_site_id, path_basename_chain

# Feather MC microSD metadata file (e.g. 0521MD.CSV), first line:
# Anemometer MetaData Log, 00000003
_METADATA_FIRST_LINE = re.compile(
    r"^Anemometer\s+MetaData\s+Log\s*,\s*(\d+)\s*$",
    re.IGNORECASE,
)


def _is_feathermc_metadata_csv_filename(name: str) -> bool:
    return name.upper().endswith("MD.CSV")


def _serial_from_metadata_csv(path: str) -> str:
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            line = f.readline().strip()
    except OSError:
        return ""
    match = _METADATA_FIRST_LINE.match(line)
    return match.group(1) if match else ""


def infer_feathermc_serial_from_met_folder(folder: str) -> str:
    """Unit serial from Feather MC ``*MD.CSV`` metadata in the MET folder."""
    folder = os.path.abspath(folder)
    try:
        names = sorted(os.listdir(folder))
    except OSError:
        return ""

    serials: list[str] = []
    for name in names:
        if not _is_feathermc_metadata_csv_filename(name):
            continue
        path = os.path.join(folder, name)
        if not os.path.isfile(path):
            continue
        serial = _serial_from_metadata_csv(path)
        if serial:
            serials.append(serial)

    if not serials:
        return ""
    return Counter(serials).most_common(1)[0][0]


def apply_deployment_hints(folder: str, *, infer_serial: bool = False) -> dict[str, str]:
    """
    Hints from folder path (and optional MET contents).

    Returns ``site_id`` and, when ``infer_serial`` is True, ``serial`` (empty if unknown).
    """
    folder = os.path.abspath(folder)
    site_id = infer_monitoring_site_id(*path_basename_chain(folder))
    result = {"site_id": site_id}
    if infer_serial:
        result["serial"] = infer_feathermc_serial_from_met_folder(folder)
    return result
