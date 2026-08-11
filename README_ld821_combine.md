# ld821_combine

Combines G4-exported LD821 Time History CSVs into one sorted file for NVSPL conversion.

## Features

- Folder browse for `*Time History*.csv` files (recursive)
- Concatenate + sort by timestamp
- Timestamped log next to output

## Prerequisites

- Python 3.9+, pandas (see `requirements.txt`)

## Inputs

- One or more G4 Time History CSVs under the browsed folder (e.g. `RAW/`)

## Outputs

- **`{site}_Time History.csv`** in the browsed folder
- **`combine_slm_*.log`**

Column headers are **unchanged from G4 export** (passthrough). Expected layout:

| Column | Name |
|--------|------|
| 0 | `Record Type` |
| 1 | `Date` |
| 2 | `LAeq` |
| 3 | `LZeq` |
| 4 | `LCeq` |
| 5 | `External Power` |
| 6–38 | `H12.5` … `H20000` (33 octave bands) |
| 39 | `OVLD` |

See `schemas/ld821_spl.py` for the full column contract used by `ld821_to_nvspl.py`.

## Usage

1. Run `python ld821_combine.py`
2. Browse to your RAW (or SPL data) folder
3. Enter **Site Name** — used in the output filename (e.g. `DENATRLA_Time History.csv`)
4. Run combine

## NVSPL handoff

Browse the combined file in `ld821_to_nvspl.py` — **Site ID** and **Output folder** autofill from the `{site}_Time History.csv` filename.

## Troubleshooting

- **Invalid timestamps:** check G4 export; `Date` column must be `YYYY-MM-DD HH:MM:SS`
- **NVSPL can't parse output:** confirm first header row contains `Record Type` (no extra preamble lines above the header)
