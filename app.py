"""Prototype parser and calculation engine for Lantek-to-Fortran TXT input.

This reproduces relationships that can be proven from the supplied sample.
For exact Fortran parity, populate the operation/rule configuration from the
Fortran source, lookup tables, or additional validated input/output pairs.
"""
from __future__ import annotations

import re
from io import BytesIO

import pandas as pd
import streamlit as st

st.title("TXT STD Calculator")

st.write("Upload a Lantek-to-Fortran TXT file to extract and review STD values.")

st.write("My First Streamlit Application")

# ============================================================
# TXT file upload
# ============================================================

uploaded_txt = st.file_uploader(
    "Upload Lantek TXT File",
    type=["txt"],
    key="lantek_txt_upload"
)


def split_fields(line):
    """Split a fixed-width or whitespace-delimited TXT row."""
    return re.split(r"\s+", line.strip())


def to_number(value):
    """
    Convert a text value to int or float when possible.
    Keep identifiers such as T227630_B2 as text.
    """
    try:
        number = float(value)

        if number.is_integer() and "." not in value:
            return int(number)

        return number

    except ValueError:
        return value


def parse_lantek_txt(content):
    """
    Parse the observed four-record Lantek/Fortran TXT structure.

    Expected structure:
    Row 1: Header record
    Row 2: Count/settings record
    Row 3: Time/factor record
    Row 4 onward: Part/result records
    """

    lines = [
        line.strip()
        for line in content.splitlines()
        if line.strip()
    ]

    if len(lines) < 4:
        raise ValueError(
            "The TXT file must contain at least four non-empty rows."
        )

    token_rows = [
        [to_number(value) for value in split_fields(line)]
        for line in lines
    ]

    # Validate against the uploaded sample structure.
    if len(token_rows[0]) < 7:
        raise ValueError(
            "Header row does not contain the expected 7 values."
        )

    if len(token_rows[1]) < 2:
        raise ValueError(
            "Second row does not contain the expected 2 values."
        )

    if len(token_rows[2]) < 3:
        raise ValueError(
            "Third row does not contain the expected 3 values."
        )

    # Descriptive positional names are used until the Fortran
    # field specification confirms the business names.
    header = {
        "Header_Value_1": token_rows[0][0],
        "Nest_Number": token_rows[0][1],
        "Header_Value_3": token_rows[0][2],
        "Header_Value_4": token_rows[0][3],
        "Thickness": token_rows[0][4],
        "Sheet_Length": token_rows[0][5],
        "Sheet_Width": token_rows[0][6],
        "Second_Row_Value_1": token_rows[1][0],
        "Second_Row_Value_2": token_rows[1][1],
        "Third_Row_Value_1": token_rows[2][0],
        "Third_Row_Value_2": token_rows[2][1],
        "Third_Row_Value_3": token_rows[2][2],
    }

    records = []

    for row_number, values in enumerate(token_rows[3:], start=4):
        record = {
            "Source_Row": row_number
        }

        for index, value in enumerate(values, start=1):
            if index == 1:
                record["Part_or_Record_ID"] = value
            else:
                record[f"Result_Value_{index - 1}"] = value

        records.append(record)

    header_df = pd.DataFrame(
        {
            "Field": list(header.keys()),
            "Value": list(header.values())
        }
    )

    results_df = pd.DataFrame(records)

    # Preserve the original TXT rows for traceability.
    raw_df = pd.DataFrame(
        {
            "Line_Number": range(1, len(lines) + 1),
            "TXT_Data": lines
        }
    )

    return header, header_df, results_df, raw_df


if uploaded_txt is not None:

    # Read uploaded file once.
    content = uploaded_txt.getvalue().decode(
        "utf-8",
        errors="ignore"
    )

    try:
        header, header_df, extracted_df, raw_df = (
            parse_lantek_txt(content)
        )

        st.success("TXT file parsed successfully.")

        # ====================================================
        # File preview
        # ====================================================

        with st.expander("View Original TXT File"):
            st.text_area(
                "Original File Contents",
                content,
                height=180
            )

        # ====================================================
        # Header values
        # ====================================================

        st.subheader("Extracted Header Values")
        st.dataframe(
            header_df,
            use_container_width=True,
            hide_index=True
        )

        # ====================================================
        # Extracted STD/result values
        # ====================================================

        st.subheader("Extracted STD Result Values")
        st.dataframe(
            extracted_df,
            use_container_width=True,
            hide_index=True
        )

        # ====================================================
        # Configurable STD calculation
        # ====================================================

        st.subheader("STD Calculation")

        st.info(
            "The uploaded TXT sample contains result values, "
            "but it does not define the business meaning of each "
            "position or the official Fortran STD formula. "
            "The calculation below is therefore configurable."
        )

        calculation_mode = st.selectbox(
            "Select Calculation Mode",
            [
                "Display extracted values only",
                "Calculate Cut Length / Machine Speed"
            ]
        )

        calculated_df = extracted_df.copy()

        if calculation_mode == "Calculate Cut Length / Machine Speed":

            numeric_columns = [
                column
                for column in extracted_df.columns
                if column.startswith("Result_Value_")
            ]

            if numeric_columns:

                cut_length_column = st.selectbox(
                    "Select the column containing Cut Length",
                    numeric_columns,
                    index=0
                )

                machine_speed = st.number_input(
                    "Enter Machine Speed",
                    min_value=0.000001,
                    value=1.0,
                    step=1.0
                )

                handling_time = st.number_input(
                    "Enter Additional Handling Time",
                    min_value=0.0,
                    value=0.0,
                    step=0.1
                )

                quantity = st.number_input(
                    "Enter Number of Pieces",
                    min_value=1,
                    value=1,
                    step=1
                )

                calculated_df["Calculated_Machine_Time"] = (
                    pd.to_numeric(
                        calculated_df[cut_length_column],
                        errors="coerce"
                    )
                    / machine_speed
                )

                calculated_df["Calculated_Total_Time"] = (
                    calculated_df["Calculated_Machine_Time"]
                    + handling_time
                )

                calculated_df["Calculated_STD_Per_Piece"] = (
                    calculated_df["Calculated_Total_Time"]
                    / quantity
                )

                st.warning(
                    "These calculated columns use the temporary formula "
                    "(selected value / machine speed + handling time) "
                    "/ quantity. Replace this formula with the validated "
                    "Fortran business rule before production use."
                )

        st.subheader("Final STD Results")
        st.dataframe(
            calculated_df,
            use_container_width=True,
            hide_index=True
        )

        # ====================================================
        # Raw line table
        # ====================================================

        with st.expander("View Raw TXT Rows"):
            st.dataframe(
                raw_df,
                use_container_width=True,
                hide_index=True
            )

        # ====================================================
        # Download CSV
        # ====================================================

        csv_data = calculated_df.to_csv(
            index=False
        ).encode("utf-8")

        st.download_button(
            label="Download STD Results as CSV",
            data=csv_data,
            file_name="extracted_STD_results.csv",
            mime="text/csv"
        )

        # ====================================================
        # Download Excel
        # ====================================================

        excel_buffer = BytesIO()

        with pd.ExcelWriter(
            excel_buffer,
            engine="openpyxl"
        ) as writer:

            header_df.to_excel(
                writer,
                sheet_name="Header",
                index=False
            )

            calculated_df.to_excel(
                writer,
                sheet_name="STD Results",
                index=False
            )

            raw_df.to_excel(
                writer,
                sheet_name="Raw TXT",
                index=False
            )

        st.download_button(
            label="Download Complete STD Report as Excel",
            data=excel_buffer.getvalue(),
            file_name="STD_Report.xlsx",
            mime=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            )
        )

    except Exception as error:
        st.error(
            f"Unable to process this TXT file: {error}"
        )

else:
    st.info(
        "Upload a TXT file to begin extraction."
    )

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
