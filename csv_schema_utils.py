# -*- coding: utf-8 -*-
"""Shared helpers for CSV header / column index lookup."""


def header_columns(header_row):
    return [str(c or "").strip() for c in (header_row or [])]


def col_index(cols, names):
    """First exact match among *names* in cols, or None."""
    for name in names:
        if name in cols:
            return cols.index(name)
    return None
