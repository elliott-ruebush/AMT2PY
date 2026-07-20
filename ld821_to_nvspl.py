# -*- coding: utf-8 -*-
"""
LD821 Time History CSV -> NVSPL (C# parity) + MET merge (robust loader + bin/forward/nearest fill).

- Audio path mirrors Erik's LD821 C# conversion (LDCSV821 + ParseDailyFile) for exact field order & behavior.
- MET merge adopts the successful LD831 approach:
  * encoding & delimiter sniffing
  * flexible timestamp parsing (single column or Date+Time)
  * bin-repeat, forward-fill, or nearest-fill with configurable "stamp" (start/center/end)
  * normalizes compass directions (N, NE, ...) and filters invalid wind entries
- Output: hourly NVSPL .txt files (54 columns).

References:
- Prior LD821 (exact-match index, C# parity) script: for header, status, bands, and hour matrix behavior.  # [from uploaded ld821_to_nvspl.py]
- LD831 (robust MET loader & merger) script: for encoding/delimiter sniffing, flexible DT parsing, and bin/nearest fill logic.  # [from uploaded 831_to_NVSPL_external_wind_log.py]
"""

import os, csv, math, re, io, bisect
from datetime import datetime, timedelta

# ========= USER SETTINGS =========
INPUT_CSV = r"E:\TARs\MORU\MORUA2503_BreezyPoint_20260626\RAW\MORUA2503_821SE 40362-260702000-131159_Time History.csv"
OUTPUT_DIR = r"E:\TARs\MORU\MORUA2503_BreezyPoint_20260626\NVSPL"
SITE_ID = "MORUA2503"

# --- MET merge controls (robust) ---
MERGE_MET = True
MET_CSV_PATH = r"E:\TARs\MORU\MORUA2503_BreezyPoint_20260626\MET\00000018 2026-07-09 125259.csv"

# If any of these are None, auto-detection will infer them from header/data:
MET_TIMESTAMP_IDX = 5   # single timestamp column (0-based) if known
MET_WINDSPD_IDX   = 3   # wind speed column index (avg/gust)
MET_WINDDIR_IDX   = None   # wind direction column index (optional)
MET_EXTERNTEMP_IDX= None   # external temp column index (optional)

# Alignment/merge strategy (adopted from LD831):
MET_SAMPLE_STAMP = "start"   # "start" | "center" | "end" (how CSV timestamps represent the sampling bin)
FILL_METHOD      = "bin"   # "bin" | "forward" | "nearest"
NEAREST_TOLERANCE_SEC = 2
BACKFILL_BEFORE_FIRST = False  # bin/forward: fill seconds before first MET sample?

# Units and conversion
MET_SPEED_UNITS    = "mps"     # "mps" or "mph"
CONVERT_MPH_TO_MPS = False     # set True only if MET_SPEED_UNITS == "mph"

# Value cleanup (matches C# MX1105 behavior)
MET_INVALID_SPEED = {"39.9"}   # wipe invalid wind speed entries -> blank

# ==================================
# NVSPL header (54 columns, fixed order)
NVSPL_HEADER = [
    "SiteID","STime",
    "H12p5","H15p8","H20","H25","H31p5","H40","H50","H63","H80","H100",
    "H125","H160","H200","H250","H315","H400","H500","H630","H800","H1000","H1250",
    "H1600","H2000","H2500","H3150","H4000","H5000","H6300","H8000","H10000","H12500",
    "H16000","H20000",
    "dbA","dbC","dbF",
    "Voltage","WindSpeed","WindDir","TempIns","TempOut","Humidity",
    "INVID","INSID","GChar1","GChar2","GChar3",
    "AdjustmentsApplied","CalibrationAdjustment","GPSTimeAdjustment","GainAdjustment","Status"
]

# A-weighting array used for dbA fallback (first 32 bands)
AWT = [
    -63.4, -56.7, -50.5, -44.7, -39.4, -34.6, -30.2, -26.2, -22.5, -19.1,
    -16.1, -13.4, -10.9,  -8.6,  -6.6,  -4.8,  -3.2,  -1.9,  -0.8,   0.0,
      0.6,   1.0,   1.2,   1.3,   1.2,   1.0,   0.5,  -0.1,  -1.1,  -2.5,
     -4.3,  -6.6,  -9.3
]

# ---------- Utilities ----------
def ensure_dir(path: str):
    if not os.path.exists(path):
        os.makedirs(path)

def generate_filename(site: str, dt_hour: datetime) -> str:
    """Matches C# GenerateFilename (hasOB=True): NVSPL_<site>_yyyy_MM_dd_HH.txt."""
    return os.path.join(OUTPUT_DIR, f"NVSPL_{site}_{dt_hour.strftime('%Y_%m_%d_%H')}.txt")

def create_blank_hour(site: str, hour_start: datetime):
    """3600 rows with SiteID & STime (.000 ms), others blank—C# ParseDailyFile parity."""
    rows = []
    for sec in range(3600):
        t = hour_start + timedelta(seconds=sec)
        stime = t.strftime("%Y-%m-%d %H:%M:%S") + ".000"
        row = [site, stime] + [""] * (len(NVSPL_HEADER) - 2)
        rows.append(row)
    return rows

def write_hour_file(site: str, hour_start: datetime, filled_rows):
    ensure_dir(OUTPUT_DIR)
    path = generate_filename(site, hour_start)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(NVSPL_HEADER)
        for r in filled_rows:
            w.writerow(r)
    return path

# ---------- LD821 parsing (C# parity) ----------
def parse_timestamp_ld821(ts_str: str) -> datetime:
    """C# LDCSV821 uses %Y-%m-%d %H:%M:%S; %H tolerates single-digit hour inputs."""
    return datetime.strptime(ts_str.strip(), "%Y-%m-%d %H:%M:%S")

def compute_dba_from_bands(bands_33):
    """dbA fallback when LAeq missing; sum first 32 bands with A-weighting then 10*log10."""
    try:
        s = 0.0
        for i in range(32):
            s += 10.0 ** ((float(bands_33[i]) + float(AWT[i])) / 10.0)
        return f"{10.0 * math.log10(s):.1f}"
    except Exception:
        return ""

def parse_ld821_to_day_records(site: str, src_csv: str):
    """
    Replicate LDCSV821:
    - Find header line containing 'Record Type'.
    - Map indices for Date, LAeq, LZeq, LCeq, External Power, start of 12.5-band, and Invalid/OVLD.
    - Validate bands (parse & >= -50).
    - Status='9911' if Invalid non-empty.
    - Build 54-field records (SiteID, STime, 33 bands, dbA/dbC/dbF/Voltage + 13 blanks + Status).
    """
    with open(src_csv, "r", encoding="utf-8", newline="") as f:
        raw = f.read().splitlines()

    header_idx = -1
    for i, line in enumerate(raw):
        if "Record Type" in line:
            header_idx = i
            break
    if header_idx < 0:
        raise RuntimeError("LD821 header line containing 'Record Type' not found.")

    hdr = next(csv.reader([raw[header_idx]]))
    sdateLoc = dbaLoc = dbzLoc = dbcLoc = powerLoc = h12p5Loc = ovrLoc = -100
    for idx, name in enumerate(hdr):
        n = name.strip()
        if "Date" in n: sdateLoc = idx
        elif n == "LAeq": dbaLoc = idx
        elif n == "LZeq": dbzLoc = idx
        elif n == "LCeq": dbcLoc = idx
        elif n.startswith("External"): powerLoc = idx
        elif "12.5" in n: h12p5Loc = idx
        elif "Invalid" in n or n.startswith("OVLD"): ovrLoc = idx

    if not (h12p5Loc > 0 and sdateLoc > 0):
        raise RuntimeError("LD821 required columns not found (Date and 12.5 band).")

    sample_row = next(csv.reader([raw[header_idx + 1]]))
    day_switch = parse_timestamp_ld821(sample_row[sdateLoc])
    current_day = day_switch.strftime("%Y-%m-%d")
    out_per_day = {current_day: []}

    for l_idx in range(header_idx + 1, len(raw)):
        row_str = raw[l_idx]
        if not row_str.strip():
            continue
        row = next(csv.reader([row_str]))
        if len(row) <= h12p5Loc + 32:
            continue

        temp_ts = parse_timestamp_ld821(row[sdateLoc])
        row_day = temp_ts.strftime("%Y-%m-%d")
        if row_day != current_day:
            current_day = row_day
            out_per_day.setdefault(current_day, [])

        bands_33 = [row[h12p5Loc + i].strip() for i in range(33)]

        # Validate bands >= -50
        valid_line = True
        try:
            for v in bands_33:
                if float(v) < -50.0:
                    valid_line = False
                    break
        except Exception:
            valid_line = False
        if not valid_line:
            continue

        dbA = row[dbaLoc].strip() if dbaLoc > 0 else ""
        dbF = row[dbzLoc].strip() if dbzLoc > 0 else ""
        dbC = row[dbcLoc].strip() if dbcLoc > 0 else ""
        volt = row[powerLoc].strip() if powerLoc > 0 else ""
        status = ""
        if ovrLoc > 0 and row[ovrLoc].strip() != "":
            status = "9911"

        if (dbaLoc < 0) or (dbA == ""):
            dbA = compute_dba_from_bands(bands_33)

        stime = temp_ts.strftime("%Y-%m-%d %H:%M:%S") + ".000"
        record = [site, stime] + bands_33 + [dbA, dbC, dbF, volt] + [""] * 13 + [status]

        # ensure 54 fields
        if len(record) != len(NVSPL_HEADER):
            record = (record + [""] * (len(NVSPL_HEADER) - len(record)))[:len(NVSPL_HEADER)]

        out_per_day[current_day].append(record)

    return out_per_day

# ---------- Hour matrix & writing (C# ParseDailyFile parity) ----------
def parse_daily_file_to_hours(site: str, day_records: list):
    """Build hour bundles; fill columns 2..53 at secTot=minute*60+second; return sorted hour bundles."""
    if not day_records:
        return []

    def parse_stime(st):
        return datetime.strptime(st, "%Y-%m-%d %H:%M:%S.000")

    hours = {}
    for rec in day_records:
        dt_val = parse_stime(rec[1])
        hour_start = dt_val.replace(minute=0, second=0, microsecond=0)
        key = hour_start.strftime("%Y-%m-%d %H")
        if key not in hours:
            hours[key] = {"start": hour_start, "rows": create_blank_hour(site, hour_start)}
        sec_tot = dt_val.minute * 60 + dt_val.second
        hours[key]["rows"][sec_tot][2:] = rec[2:]

    return [hours[k] for k in sorted(hours.keys())]

# ---------- MET helpers (auto-detection retained) ----------
COMPASS_TO_DEG = {
    "N":0.0,"NNE":22.5,"NE":45.0,"ENE":67.5,"E":90.0,"ESE":112.5,"SE":135.0,"SSE":157.5,
    "S":180.0,"SSW":202.5,"SW":225.0,"WSW":247.5,"W":270.0,"WNW":292.5,"NW":315.0,"NNW":337.5
}

def read_csv_rows_by_index(path):
    with open(path, "r", encoding="utf-8", newline="") as f:
        r = csv.reader(f)
        return [row for row in r]

# Enhanced datetime parsing (from your original LD821 script)
def try_parse_dt_common(s: str):
    """
    Parse a single timestamp string into datetime (second resolution).
    Supports:
    - YYYY-MM-DD HH:MM:SS
    - YYYY/MM/DD HH:MM:SS
    - YYYY-MM-DD HHMMSS
    - YYYY/MM/DD HHMMSS
    - dd-MMM-yy HH:MM:SS
    """
    s = (s or "").strip()
    if not s:
        return None

    def _normalize_no_colon(ts: str):
        parts = ts.split(" ", 1)
        if len(parts) == 2 and len(parts[1]) == 6 and parts[1].isdigit():
            hh, mm, ss = parts[1][0:2], parts[1][2:4], parts[1][4:6]
            return parts[0] + " " + f"{hh}:{mm}:{ss}"
        return ts

    s_norm = _normalize_no_colon(s)
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S", "%d-%b-%y %H:%M:%S"):
        try:
            return datetime.strptime(s_norm, fmt).replace(microsecond=0)
        except Exception:
            pass
    return None

def try_parse_dt_from_two_cols(date_s: str, time_s: str):
    """
    Combine separate Date + Time columns, then parse to datetime.
    Handles:
    - Date: YYYY-MM-DD or YYYY/MM/DD or dd-MMM-yy
    - Time: HH:MM:SS or HHMMSS
    """
    date_s = (date_s or "").strip()
    time_s = (time_s or "").strip()
    if not date_s or not time_s:
        return None

    def _normalize_time(t: str):
        if len(t) == 6 and t.isdigit():
            return f"{t[0:2]}:{t[2:4]}:{t[4:6]}"
        return t

    t_norm = _normalize_time(time_s)
    candidate = f"{date_s} {t_norm}"
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S", "%d-%b-%y %H:%M:%S"):
        try:
            return datetime.strptime(candidate, fmt).replace(microsecond=0)
        except Exception:
            pass
    return None

def auto_detect_met_indices(rows, user_ts_idx, user_spd_idx, user_dir_idx, user_tmp_idx):
    """
    Detect MET schema:
    - Prefer a single parsable timestamp col; else try (Date + Time) pair.
    - MX1105 if 'ADC1'/'ADC2' headers present.
    - CV3 if 'dir' + 'spd/speed/gust' headers present.
    - Otherwise GENERIC (timestamp + numeric speed).
    Returns dict with keys:
    'ts_idx' OR ('date_idx','time_idx'), plus 'spd_idx','dir_idx','tmp_idx','source'.
    """
    header = rows[0] if rows else []
    hdr_tokens = [str(x or "").strip().lower() for x in header]
    has_header = any(any(c.isalpha() for c in (cell or "")) for cell in header)

    schema = {
        "ts_idx": user_ts_idx,
        "date_idx": None,
        "time_idx": None,
        "spd_idx": user_spd_idx,
        "dir_idx": user_dir_idx,
        "tmp_idx": user_tmp_idx,
        "source": "GENERIC_CSV"
    }

    # Detect source by header hints
    is_mx1105 = any("adc1" in h or "adc2" in h for h in hdr_tokens)
    has_dir_hdr = any("dir" in h for h in hdr_tokens)
    has_spd_hdr = any("spd" in h or "speed" in h or "gust" in h for h in hdr_tokens)

    if is_mx1105:
        schema["source"] = "MX1105_CSV"
        if schema["tmp_idx"] is None:
            for i, h in enumerate(hdr_tokens):
                if "adc1" in h:
                    schema["tmp_idx"] = i; break
        if schema["spd_idx"] is None:
            for i, h in enumerate(hdr_tokens):
                if "gust" in h:
                    schema["spd_idx"] = i; break
        if schema["spd_idx"] is None:
            for i, h in enumerate(hdr_tokens):
                if "spd" in h or "speed" in h:
                    schema["spd_idx"] = i; break

    elif has_dir_hdr and has_spd_hdr:
        schema["source"] = "CV3_CSV"
        if schema["dir_idx"] is None:
            for i, h in enumerate(hdr_tokens):
                if "dir" in h:
                    schema["dir_idx"] = i; break
        if schema["spd_idx"] is None:
            for i, h in enumerate(hdr_tokens):
                if "gust" in h or "spd" in h or "speed" in h:
                    schema["spd_idx"] = i; break
        if schema["tmp_idx"] is None:
            for i, h in enumerate(hdr_tokens):
                if "temp" in h or "ext" in h:
                    schema["tmp_idx"] = i; break

    # Timestamp detection
    if schema["ts_idx"] is None:
        start = 1 if has_header else 0
        sample_n = min(len(rows) - start, 500)
        if sample_n > 0:
            best_ts_idx, best_hits = None, -1
            row0_len = len(rows[start]) if start < len(rows) else 0
            # single column candidate
            for c in range(row0_len):
                hits = 0
                for i in range(start, start + sample_n):
                    if len(rows[i]) > c and try_parse_dt_common(rows[i][c]):
                        hits += 1
                if hits > best_hits:
                    best_ts_idx, best_hits = c, hits
            # if single weak, try Date+Time pair
            if best_hits < max(5, sample_n // 20):
                best_pair = (None, None, -1)
                for di in range(row0_len):
                    for ti in range(row0_len):
                        if di == ti:
                            continue
                        hits = 0
                        for i in range(start, start + sample_n):
                            row = rows[i]
                            if len(row) > max(di, ti):
                                dt_val = try_parse_dt_from_two_cols(row[di], row[ti])
                                if dt_val:
                                    hits += 1
                        if hits > best_pair[2]:
                            best_pair = (di, ti, hits)
                if best_pair[2] > best_hits:
                    schema["date_idx"], schema["time_idx"] = best_pair[0], best_pair[1]
                else:
                    schema["ts_idx"] = best_ts_idx
            else:
                schema["ts_idx"] = best_ts_idx

    # If speed not detected, choose numerically-dense column
    if schema["spd_idx"] is None and len(rows) > 1:
        start = 1 if has_header else 0
        sample_n = min(len(rows) - start, 300)
        max_cols = max((len(r) for r in rows[start:start + sample_n]), default=0)
        best_idx, best_nums = None, -1
        for c in range(max_cols):
            nums = 0
            for r in rows[start:start + sample_n]:
                if len(r) > c:
                    try:
                        float(r[c])
                        nums += 1
                    except Exception:
                        pass
            if nums > best_nums:
                best_idx, best_nums = c, nums
        schema["spd_idx"] = best_idx

    return schema

# ---------- New robust MET loader & merge (adopted from LD831) ----------
def _sniff_encoding(path):
    enc = "utf-8"
    try:
        with open(path, "rb") as fb:
            head = fb.read(4)
            if head.startswith(b"\xff\xfe"):
                enc = "utf-16-le"
            elif head.startswith(b"\xfe\xff"):
                enc = "utf-16-be"
            elif head.startswith(b"\xef\xbb\xbf"):
                enc = "utf-8-sig"
    except Exception:
        pass
    return enc

def _sniff_delimiter(sample_text):
    try:
        dialect = csv.Sniffer().sniff(sample_text, delimiters="\t,;")
        return dialect.delimiter
    except Exception:
        return ("\t" if "\t" in sample_text else ("," if "," in sample_text else ";"))

def _extract_dt_string(s: str):
    """Pull a recognizable date-time substring (MDY/HMS with optional AM/PM, or ISO) from messy cells."""
    if not s:
        return None
    s = s.replace("\ufeff", "").replace("\xa0", " ").strip().strip('"').strip("'")
    m = re.search(r'(?P<mdy>\b\d{1,2}/\d{1,2}/\d{2,4})\s+(?P<hms>\d{1,2}:\d{2}(?::\d{2})?)\s*(?P<ampm>\bAM\b|\bPM\b|\bam\b|\bpm\b)?', s)
    if m:
        dt_str = f"{m.group('mdy')} {m.group('hms')}"
        if m.group('ampm'):
            dt_str += f" {m.group('ampm').upper()}"
        return dt_str
    m = re.search(r'(?P<iso>\b\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(?::\d{2})?(?:\.\d+)?(?:Z|[+\-]\d{2}:\d{2})?)', s)
    if m:
        return m.group('iso')
    return None

def _parse_dt_flex(s: str, explicit_fmt: str | None):
    """Flexible datetime parse: explicit fmt first, then common MDY, ISO, and YMD fallbacks."""
    s = (s or "").strip()
    if not s:
        return None
    if explicit_fmt:
        try:
            return datetime.strptime(s, explicit_fmt).replace(microsecond=0)
        except Exception:
            pass
    core = _extract_dt_string(s) or s
    for cand in ("%m/%d/%Y %H:%M:%S", "%m/%d/%Y %H:%M",
                 "%m/%d/%Y %I:%M:%S %p", "%m/%d/%Y %I:%M %p",
                 "%m/%d/%y %H:%M:%S", "%m/%d/%y %H:%M",
                 "%m/%d/%y %I:%M:%S %p", "%m/%d/%y %I:%M %p"):
        try: return datetime.strptime(core, cand).replace(microsecond=0)
        except Exception: pass
    for cand in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M",
                 "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f",
                 "%Y-%m-%dT%H:%M"):
        try: return datetime.strptime(core, cand).replace(microsecond=0)
        except Exception: pass
    return None

def _infer_interval_seconds(times: list[datetime]) -> int:
    if len(times) < 2: return 1
    deltas = [(times[i] - times[i-1]).total_seconds() for i in range(1, len(times))]
    deltas = [d for d in deltas if d > 0]
    if not deltas: return 1
    deltas.sort()
    mid = len(deltas)//2
    median = deltas[mid] if len(deltas)%2==1 else (deltas[mid-1]+deltas[mid])/2.0
    for cand in (1,2,5,10,15,20,30,60,120,300):
        if abs(median - cand) <= 0.6:
            return cand
    return int(round(median))

def _shift_times_for_stamp(times: list[datetime], interval_sec: int, stamp: str) -> list[datetime]:
    s = (stamp or "start").lower()
    if interval_sec <= 0 or s == "start": return times
    shift = interval_sec/2.0 if s == "center" else (interval_sec if s == "end" else 0)
    if shift == 0: return times
    return [t - timedelta(seconds=shift) for t in times]

def _norm_speed(val: str) -> str:
    s = (str(val) or "").strip()
    if s in MET_INVALID_SPEED:
        return ""
    try: return f"{float(s):.1f}"
    except Exception: return ""

def _norm_dir(val: str) -> str:
    s = (str(val) or "").strip().upper()
    if s in COMPASS_TO_DEG:
        return f"{COMPASS_TO_DEG[s]:.1f}"
    try: return f"{float(s):.1f}"
    except Exception: return ""

def _norm_temp(val: str) -> str:
    try: return f"{float(str(val).strip()):.1f}"
    except Exception: return ""

def _load_met_samples_by_schema(csv_path: str, schema: dict, dt_format: str | None,
                                units: str, convert_mph_to_mps: bool):
    """
    Return [(time, {'spd':str,'dir':str,'tmp':str})] with flexible encoding/delimiter parsing.
    Uses single timestamp or (Date + Time) columns based on auto-detected schema.
    """
    enc = _sniff_encoding(csv_path)
    sample_bytes = b""
    try:
        with open(csv_path, "rb") as fb: sample_bytes = fb.read(65536)
    except Exception: pass
    try: sample_text = sample_bytes.decode(enc, errors="replace")
    except Exception: sample_text = sample_bytes.decode("utf-8", errors="replace")
    delim = _sniff_delimiter(sample_text)

    rows = []
    try:
        with open(csv_path, "r", encoding=enc, newline="") as f:
            reader = csv.reader(f, delimiter=delim)
            for row in reader:
                if not row: continue
                # skip obvious header-ish lines
                first = (row[0] or "").strip()
                if first.startswith("#") or "Date" in first or "Time" in first or "GMT" in first or "UTC" in first:
                    continue
                rows.append(row)
    except Exception:
        # manual fallback
        with open(csv_path, "r", encoding=enc, errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line: continue
                if "Plot Title" in line or line.startswith("#"):
                    continue
                for cand in ("\t", ",", ";"):
                    if cand in line:
                        reader = csv.reader(io.StringIO(line), delimiter=cand)
                        try: row = next(reader)
                        except Exception: row = None
                        if row: rows.append(row)
                        break

    # Build samples
    samples = []
    use_single = schema.get("ts_idx") is not None
    ts_i = schema.get("ts_idx")
    di, ti = schema.get("date_idx"), schema.get("time_idx")
    spd_i, dir_i, tmp_i = schema.get("spd_idx"), schema.get("dir_idx"), schema.get("tmp_idx")

    for row in rows:
        dt_val = None
        if use_single and ts_i is not None and len(row) > ts_i:
            dt_val = _parse_dt_flex(row[ts_i], dt_format)
            if not dt_val:
                dt_val = try_parse_dt_common(row[ts_i])
        elif di is not None and ti is not None and len(row) > max(di, ti):
            dt_val = try_parse_dt_from_two_cols(row[di], row[ti])
        if not dt_val: 
            continue

        # speed
        spd = ""
        if spd_i is not None and len(row) > spd_i:
            spd_raw = row[spd_i]
            try:
                v = float(str(spd_raw).strip())
                if units.lower() == "mph" and convert_mph_to_mps:
                    v *= 0.44704
                spd = f"{v:.1f}"
            except Exception:
                spd = _norm_speed(spd_raw)

        # direction
        drr = ""
        if dir_i is not None and len(row) > dir_i:
            drr = _norm_dir(row[dir_i])

        # external temp
        tmp = ""
        if tmp_i is not None and len(row) > tmp_i:
            tmp = _norm_temp(row[tmp_i])

        samples.append((dt_val.replace(microsecond=0), {"spd": spd, "dir": drr, "tmp": tmp}))

    samples.sort(key=lambda x: x[0])

    # quick peek
    if samples:
        print("[MET] Loaded", len(samples), "samples. First 3:",
              [(samples[i][0].strftime("%Y-%m-%d %H:%M:%S"), samples[i][1]) for i in range(min(3,len(samples)))])
    else:
        print("[MET] Parsed 0 samples; check delimiter/encoding/time columns.")

    return samples

def _overlay_met_bin(rows_3600: list, hour_start: datetime,
                     samples: list, stamp: str, backfill_before_first: bool):
    if not samples: return 0
    times = [t for (t, _) in samples]
    vals  = [v for (_, v) in samples]
    interval = _infer_interval_seconds(times)
    times_shifted = _shift_times_for_stamp(times, interval, stamp)

    # Build bin edges
    bins_start = times_shifted
    bins_end = [times_shifted[i+1] if i+1<len(times_shifted)
                else (times_shifted[i] + timedelta(seconds=interval))
                for i in range(len(times_shifted))]

    updated = 0
    j = 0
    for sec in range(3600):
        t = hour_start + timedelta(seconds=sec)
        # advance bin pointer
        while j < len(bins_start) and t >= bins_end[j]:
            j += 1
        if j < len(bins_start) and bins_start[j] <= t < bins_end[j]:
            v = vals[j]
            if v.get("spd"): rows_3600[sec][39] = v["spd"]
            if v.get("dir"): rows_3600[sec][40] = v["dir"]
            if v.get("tmp"): rows_3600[sec][42] = v["tmp"]
            updated += 1
        else:
            if backfill_before_first and j == 0 and len(vals) > 0:
                v = vals[0]
                if v.get("spd"): rows_3600[sec][39] = v["spd"]
                if v.get("dir"): rows_3600[sec][40] = v["dir"]
                if v.get("tmp"): rows_3600[sec][42] = v["tmp"]
                updated += 1
    print(f"[MERGE] bin-fill: interval={interval}s, stamp={stamp}, updated={updated} secs")
    return updated

def _overlay_met_forward(rows_3600: list, hour_start: datetime, samples: list):
    if not samples: return 0
    times = [t for (t, _) in samples]
    vals  = [v for (_, v) in samples]
    updated = 0
    latest = None
    j = 0
    for sec in range(3600):
        t = hour_start + timedelta(seconds=sec)
        while j < len(times) and times[j] <= t:
            latest = vals[j]; j += 1
        if latest:
            if latest.get("spd"): rows_3600[sec][39] = latest["spd"]
            if latest.get("dir"): rows_3600[sec][40] = latest["dir"]
            if latest.get("tmp"): rows_3600[sec][42] = latest["tmp"]
            updated += 1
    print(f"[MERGE] forward-fill: updated={updated} secs")
    return updated

def _overlay_met_nearest(rows_3600: list, hour_start: datetime, samples: list, tol_sec: int):
    if not samples: return 0
    mt = [t for (t, _) in samples]
    mv = [v for (_, v) in samples]
    updated = 0
    for sec in range(3600):
        t = hour_start + timedelta(seconds=sec)
        pos = bisect.bisect_left(mt, t)
        candidates = []
        if pos < len(mt): candidates.append((abs((mt[pos]-t).total_seconds()), mv[pos]))
        if pos > 0:       candidates.append((abs((mt[pos-1]-t).total_seconds()), mv[pos-1]))
        if candidates:
            best = min(candidates, key=lambda x: x[0])
            if best[0] <= tol_sec:
                v = best[1]
                if v.get("spd"): rows_3600[sec][39] = v["spd"]
                if v.get("dir"): rows_3600[sec][40] = v["dir"]
                if v.get("tmp"): rows_3600[sec][42] = v["tmp"]
                updated += 1
    print(f"[MERGE] nearest-fill: tol={tol_sec}s, updated={updated} secs")
    return updated

def merge_met_for_day(hour_bundles):
    if not MERGE_MET:
        return hour_bundles

    # 1) Read raw rows to let auto-detector infer indices & source
    raw_rows = read_csv_rows_by_index(MET_CSV_PATH)
    schema = auto_detect_met_indices(raw_rows, MET_TIMESTAMP_IDX, MET_WINDSPD_IDX, MET_WINDDIR_IDX, MET_EXTERNTEMP_IDX)
    print(f"[MET] Detected source={schema['source']}, ts_idx={schema['ts_idx']}, "
          f"date_idx={schema['date_idx']}, time_idx={schema['time_idx']}, "
          f"spd_idx={schema['spd_idx']}, dir_idx={schema['dir_idx']}, tmp_idx={schema['tmp_idx']}")

    # 2) Build flexible samples list (time + dict of spd/dir/tmp)
    samples = _load_met_samples_by_schema(
        MET_CSV_PATH,
        schema=schema,
        dt_format=None,                  # keep flexible unless you want to force a format
        units=MET_SPEED_UNITS,
        convert_mph_to_mps=CONVERT_MPH_TO_MPS
    )
    if not samples:
        print("[MET] No samples parsed; skipping merge.")
        return hour_bundles

    # 3) For each hour bundle, overlay via the chosen method
    total_updates = 0
    for b in hour_bundles:
        hour_start = b["start"]
        rows_3600  = b["rows"]

        if FILL_METHOD.lower() == "bin":
            total_updates += _overlay_met_bin(rows_3600, hour_start, samples, MET_SAMPLE_STAMP, BACKFILL_BEFORE_FIRST)
        elif FILL_METHOD.lower() == "forward":
            total_updates += _overlay_met_forward(rows_3600, hour_start, samples)
        else:
            total_updates += _overlay_met_nearest(rows_3600, hour_start, samples, NEAREST_TOLERANCE_SEC)

    print(f"[MERGE] Total NVSPL seconds updated across day: {total_updates}")
    return hour_bundles

# ---------- Orchestrate ----------
def main():
    ensure_dir(OUTPUT_DIR)

    # LD821 parse (C# parity) -> per-day records
    per_day = parse_ld821_to_day_records(SITE_ID, INPUT_CSV)  # LD821-only (C# parity)

    total_files = 0
    for day, recs in sorted(per_day.items()):
        # Build 3600-row hours (C# parity)
        hour_bundles = parse_daily_file_to_hours(SITE_ID, recs)
        # Overlay MET values (robust loader + bin/forward/nearest)
        hour_bundles = merge_met_for_day(hour_bundles)

        for b in hour_bundles:
            write_hour_file(SITE_ID, b["start"], b["rows"])
            total_files += 1

        print(f"[WRITE] Day {day} -> {len(hour_bundles)} hourly NVSPL files")

    print(f"\nDone. Total NVSPL files written: {total_files}")

if __name__ == "__main__":
    main()