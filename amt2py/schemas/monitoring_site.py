# -*- coding: utf-8 -*-
"""Infer monitoring site IDs from deployment paths and filenames."""

import os
import re

# Folder names that are not monitoring site IDs.
_SITE_ID_IGNORE = frozenset({
    "DATA", "ANALYSIS", "AUDIO", "MET", "METADATA", "RAW", "SPL", "PHOTOS", "NVSPL",
    "TIME", "HISTORY", "DEPLOYMENT", "PUBLIC", "DOCUMENTS", "EXPORT", "CSV",
})

# First matching pattern wins (checked in this order per token).
_SITE_ID_PATTERNS = (
    re.compile(r"^[A-Z]{4}\d{3}$"),  # e.g. CARE001
    re.compile(r"^[A-Z]{4,10}\d{3,5}$"),  # e.g. MORUA2503
    re.compile(r"^[A-Z]{6,14}$"),  # e.g. DENATRLA
)


def _normalize_token(token: str) -> str:
    return token.strip().upper()


def _classify_site_token(token: str) -> str:
    """Return site code if token matches a known shape, else empty string."""
    token = _normalize_token(token)
    if not token or token in _SITE_ID_IGNORE or token.isdigit():
        return ""
    for pattern in _SITE_ID_PATTERNS:
        if pattern.match(token):
            return token
    return ""


def _tokens_from_site_text(text: str) -> list[str]:
    if not text:
        return []
    normalized = re.sub(r"[^0-9A-Za-z]+", " ", text.upper())
    return [t for t in normalized.split() if t]


def infer_monitoring_site_id(*texts: str) -> str:
    """
    First site-like token found in priority order of texts, then left-to-right tokens.

    Each text is split on non-alphanumeric boundaries; the first token matching
    CARE001 / MORUA2503 / DENATRLA-style patterns is returned, or "".
    """
    for text in texts:
        for token in _tokens_from_site_text(text):
            hit = _classify_site_token(token)
            if hit:
                return hit
    return ""


def path_basename_chain(path: str, *, max_depth: int = 12) -> list[str]:
    names = []
    directory = os.path.abspath(path)
    if os.path.isfile(directory):
        directory = os.path.dirname(directory)
    for _ in range(max_depth):
        names.append(os.path.basename(directory))
        parent = os.path.dirname(directory)
        if parent == directory:
            break
        directory = parent
    return names


def infer_site_id_from_deployment_folder(folder: str) -> str:
    """Site ID hint from deployment folder path (821 combine / MET browse)."""
    return infer_monitoring_site_id(*path_basename_chain(folder))
