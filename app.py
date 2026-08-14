"""Prototype parser and calculation engine for Lantek-to-Fortran TXT input.

This reproduces relationships that can be proven from the supplied sample.
For exact Fortran parity, populate the operation/rule configuration from the
Fortran source, lookup tables, or additional validated input/output pairs.
"""
from __future__ import annotations

import streamlit as st
import pandas as pd

st.title("TXT STD Calculator")

st.write("My First Streamlit Application")

# ====================================
# Option 3 - Machine Selection
# ====================================

machine = st.selectbox(
    "Select Machine",
    [
        "Laser",
        "Press Brake",
        "RoboBend",
        "ShotBlast"
    ]
)

st.write("Selected Machine:", machine)

# ====================================
# Option 2 - STD Calculator
# ====================================

cut_length = st.number_input(
    "Cut Length",
    min_value=0.0
)

machine_speed = st.number_input(
    "Machine Speed",
    min_value=1.0
)

if st.button("Calculate STD"):
    std_time = cut_length / machine_speed
    st.success(
        f"STD Time = {std_time:.2f} minutes"
    )

# ====================================
# Option 1 - TXT Upload
# ====================================

uploaded_txt = st.file_uploader(
    "Upload TXT File",
    type=["txt"]
)

if uploaded_txt is not None:

    content = uploaded_txt.read().decode(
        "utf-8"
    )

    st.text_area(
        "TXT Content",
        content,
        height=300
    )

# ====================================
# Option 4 - Excel Upload
# ====================================

uploaded_excel = st.file_uploader(
    "Upload Excel File",
    type=["xlsx"]
)

if uploaded_excel:

    df = pd.read_excel(
        uploaded_excel
    )

    st.dataframe(
        df.head()
    )

# ====================================
# Existing Code
# ====================================

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List
import argparse
import json
import math


@dataclass
class NestHeader:
    material_code: str
    nest_number: str
    plates: int
    burns_per_nest: int
    thickness_in: float
    sheet_length_in: float
    sheet_width_in: float
    number_of_pieces: int
    machine_id: int
    piercing_min: float
    rapid_min: float
    contour_min: float


@dataclass
class PartRecord:
    part_number: str
    part_weight_lb: float
    part_width_in: float
    part_length_in: float
    quantity: int
    pieces_per_part: int
    periphery_in: float
    slugs_fall_through: int
    slugs_stay_on_bed: int
    slugs_hand_aside: int
    slugs_magnet_unload: int


@dataclass
class LantekInput:
    header: NestHeader
    parts: List[PartRecord]


def parse_lantek_txt(path: str | Path) -> LantekInput:
    """Parse the fixed-sequence whitespace-delimited input shown in the sample."""
    lines = [ln.strip() for ln in Path(path).read_text(encoding="utf-8-sig").splitlines() if ln.strip()]
    if len(lines) < 4:
        raise ValueError("Expected at least four non-empty lines: header, counts, times, and one part.")

    h = lines[0].replace("\\_", "_").split()
    c = lines[1].split()
    t = lines[2].split()
    if len(h) != 7 or len(c) != 2 or len(t) != 3:
        raise ValueError(f"Unexpected header layout: header={len(h)}, counts={len(c)}, times={len(t)} tokens")

    header = NestHeader(
        material_code=h[0], nest_number=h[1], plates=int(h[2]), burns_per_nest=int(h[3]),
        thickness_in=float(h[4]), sheet_length_in=float(h[5]), sheet_width_in=float(h[6]),
        number_of_pieces=int(c[0]), machine_id=int(c[1]),
        piercing_min=float(t[0]), rapid_min=float(t[1]), contour_min=float(t[2]),
    )

    parts: List[PartRecord] = []
    for line_no, line in enumerate(lines[3:], start=4):
        p = line.replace("\\_", "_").split()
        if len(p) != 11:
            raise ValueError(f"Line {line_no}: expected 11 part fields, found {len(p)}: {p}")
        parts.append(PartRecord(
            part_number=p[0], part_weight_lb=float(p[1]), part_width_in=float(p[2]),
            part_length_in=float(p[3]), quantity=int(p[4]), pieces_per_part=int(p[5]),
            periphery_in=float(p[6]), slugs_fall_through=int(p[7]),
            slugs_stay_on_bed=int(p[8]), slugs_hand_aside=int(p[9]),
            slugs_magnet_unload=int(p[10]),
        ))

    return LantekInput(header=header, parts=parts)


def round_half_up(value: float, digits: int = 3) -> float:
    factor = 10 ** digits
    return math.floor(value * factor + 0.5) / factor


def calculate_known_relationships(data: LantekInput, find_sheet_min: float = 0.450,
                                  total_r_time_min: float = 10.559,
                                  siemens_d_total_min: float = 0.953) -> dict:
    """Calculate only relationships demonstrated by the supplied Fortran output.

    Defaults 0.450, 10.559 and 0.953 are sample-specific Fortran-derived values,
    exposed as parameters rather than presented as universal rules.
    """
    h = data.header
    machine_time = h.piercing_min + h.rapid_min + h.contour_min + find_sheet_min
    total_qty = sum(p.quantity for p in data.parts)
    if total_qty <= 0:
        raise ValueError("Total part quantity must be positive")

    allocated = []
    for p in data.parts:
        share = p.quantity / total_qty
        # Equal per-piece allocations are proven for the one-part sample.
        r_per_piece = total_r_time_min / total_qty
        d_per_piece = siemens_d_total_min / total_qty
        allocated.append({
            "part_number": p.part_number,
            "qty": p.quantity,
            "finish_weight_lb": p.part_weight_lb,
            "rough_weight_lb_each": round_half_up(p.part_weight_lb / 0.9015, 2),
            "rough_weight_lb_total": round_half_up((p.part_weight_lb / 0.9015) * p.quantity, 2),
            "d_time_min_each": round_half_up(d_per_piece, 3),
            "r_time_min_each": round_half_up(r_per_piece, 3),
            "input_share": share,
        })

    return {
        "nest_number": h.nest_number,
        "starting_dimension": [round(h.sheet_length_in, 2), round(h.sheet_width_in, 2), round(h.thickness_in, 2)],
        "input_times": {
            "piercing_min": h.piercing_min,
            "rapid_min": h.rapid_min,
            "contour_min": h.contour_min,
            "find_sheet_min": find_sheet_min,
        },
        "machine_time_min": round_half_up(machine_time, 3),
        "total_r_time_min": total_r_time_min,
        "siemens_d_total_min": siemens_d_total_min,
        "allocated_parts": allocated,
        "warning": "IDA, labor-element selection, occurrence/cycle values, allowances and final STD require Fortran rules or more validated pairs.",
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("input_txt")
    ap.add_argument("--json", default="fortran_relationships.json")
    args = ap.parse_args()
    data = parse_lantek_txt(args.input_txt)
    result = calculate_known_relationships(data)
    Path(args.json).write_text(json.dumps({"parsed_input": {"header": asdict(data.header), "parts": [asdict(x) for x in data.parts]}, "calculated": result}, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    print(f"Saved: {args.json}")


if __name__ == "__main__":
    main()
