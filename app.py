"""Prototype parser and calculation engine for Lantek-to-Fortran TXT input.

This reproduces relationships that can be proven from the supplied sample.
For exact Fortran parity, populate the operation/rule configuration from the
Fortran source, lookup tables, or additional validated input/output pairs.
"""
from __future__ import annotations

from io import BytesIO
from pathlib import Path
import re

import pandas as pd
import streamlit as st


# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="TXT STD Calculator",
    page_icon="⚙️",
    layout="wide"
)


# ============================================================
# VALIDATED LEGACY REPORT PROFILES
#
# These totals come from the two supplied legacy outputs.
# Additional nests require either:
# 1. Their validated legacy totals, or
# 2. The original Fortran formulas/lookup tables.
# ============================================================

VALIDATED_PROFILES = {
    "T227630_1703": {
        "factory": "DUBUQUE",
        "department": "112",
        "machine": "17033",
        "operation": "LC/0000",
        "labor_grade": 6,

        "total_r_time": 10.559,
        "total_d_time_143007": 0.015,
        "total_d_time_17033": 0.953,

        # 13.490 - 10.559 - 0.953
        "total_ida_17033": 1.978,

        "total_std_143007": 10.574,
        "total_std_17033": 13.490,

        "total_hours_100_143007": 18.686,
        "total_hours_100_17033": 23.837,

        "table_shuttle_time": 0.300,
        "machine_time_143007": 0.000,
        "machine_time_17033": 18.750,
    },

    "T175833_1703": {
        "factory": "DUBUQUE",
        "department": "112",
        "machine": "17033",
        "operation": "LC/0000",
        "labor_grade": 6,

        "total_r_time": 32.323,
        "total_d_time_143007": 0.015,
        "total_d_time_17033": 3.196,

        # 44.779 - 32.323 - 3.196
        "total_ida_17033": 9.260,

        "total_std_143007": 32.338,
        "total_std_17033": 44.779,

        "total_hours_100_143007": 57.144,
        "total_hours_100_17033": 79.125,

        "table_shuttle_time": 0.300,
        "machine_time_143007": 0.000,
        "machine_time_17033": 63.610,
    },
}


# ============================================================
# INPUT PARSER
# ============================================================

def split_fields(line: str) -> list:
    """
    Split whitespace or fixed-width records.
    """
    return re.split(r"\s+", line.strip())

def to_number(value: str):
    """Convert numeric text to int or float."""
    try:
        number = float(value)

        if "." not in value and number.is_integer():
            return int(number)

        return number

    except ValueError:
        return value


def clean_identifier(value) -> str:
    """Remove escaped underscores from displayed identifiers."""
    return str(value).replace("\\_", "_")


def parse_std_txt(content: str):
    """
    Parse the complete TXT file.

    The first three non-empty lines are header records.
    Every remaining non-empty line is treated as a part record.
    """

    lines = [
        line.strip()
        for line in content.splitlines()
        if line.strip()
    ]

    if len(lines) < 4:
        raise ValueError(
            "The TXT file must contain three header rows "
            "and at least one part row."
        )

    rows = [
        [to_number(value) for value in split_fields(line)]
        for line in lines
    ]

    header_1 = rows[0]
    header_2 = rows[1]
    header_3 = rows[2]
    part_rows = rows[3:]

    if len(header_1) < 7:
        raise ValueError(
            "The first header row must contain at least 7 values."
        )

    header = {
        "Material Code": clean_identifier(header_1[0]),
        "Nest Number": clean_identifier(header_1[1]),
        "Plates": int(header_1[2]),
        "Burns per Nest": int(header_1[3]),
        "Thickness": float(header_1[4]),
        "Sheet Length": float(header_1[5]),
        "Sheet Width": float(header_1[6]),
        "Header 2 Value 1": header_2[0],
        "Header 2 Value 2": header_2[1],
        "Siemens Act 1": float(header_3[0]),
        "Siemens Act 2": float(header_3[1]),
        "Siemens Value 3": float(header_3[2]),
    }

    nest_number = header["Nest Number"]

    # Validated from the two highlighted input examples.
    quantity_position_by_nest = {
        "T227630_1703": 4,
        "T175833_1703": 5,
    }

    quantity_position = quantity_position_by_nest.get(
        nest_number,
        4
    )

    parts = []

    for source_row, row in enumerate(part_rows, start=4):

        if len(row) < 11:
            raise ValueError(
                f"Part row {source_row} contains only "
                f"{len(row)} values. At least 11 are expected."
            )

        part = {
            "Source Row": source_row,
            "Part Number": clean_identifier(row[0]),
            "Finish Weight": float(row[1]),
            "Input Value 2": float(row[2]),
            "Input Value 3": float(row[3]),
            "Input Value 4": int(row[4]),
            "Input Value 5": int(row[5]),
            "Allocation Value": float(row[6]),
            "Input Value 7": row[7],
            "Input Value 8": row[8],
            "Input Value 9": row[9],
            "Input Value 10": row[10],
        }

        part["Quantity"] = int(row[quantity_position])

        if part["Quantity"] <= 0:
            raise ValueError(
                f"Quantity must be greater than zero for "
                f"{part['Part Number']}."
            )

        parts.append(part)

    if not parts:
        raise ValueError(
            "No part records were found."
        )

    parts_df = pd.DataFrame(parts)

    return header, parts_df, lines

# ============================================================
# REPORT PROFILE
# ============================================================

def get_profile(nest_number: str):
    """Return validated totals for a known nest."""

    clean_nest = clean_identifier(nest_number)

    if clean_nest in VALIDATED_PROFILES:
        return VALIDATED_PROFILES[clean_nest].copy(), True

    return {
        "factory": "DUBUQUE",
        "department": "112",
        "machine": "17033",
        "operation": "LC/0000",
        "labor_grade": 6,

        "total_r_time": 0.0,
        "total_d_time_143007": 0.015,
        "total_d_time_17033": 0.0,
        "total_ida_17033": 0.0,

        "total_std_143007": 0.015,
        "total_std_17033": 0.0,

        "total_hours_100_143007": 0.0,
        "total_hours_100_17033": 0.0,

        "table_shuttle_time": 0.300,
        "machine_time_143007": 0.000,
        "machine_time_17033": 0.000,
    }, False


# ============================================================
# ALLOCATION LOGIC
# ============================================================

def allocate_pool_total_by_part(
    parts_df: pd.DataFrame,
    total_pool: float
) -> pd.Series:
    """
    Allocate a total pool across every part row.

    Allocation is weighted by:
    Allocation Value × Quantity
    """

    allocation_base = (
        parts_df["Allocation Value"]
        * parts_df["Quantity"]
    )

    total_base = allocation_base.sum()

    if total_base <= 0:
        raise ValueError(
            "The total allocation base must be greater than zero."
        )

    return (
        total_pool
        * allocation_base
        / total_base
    )


def convert_total_to_single_piece(
    allocated_total: pd.Series,
    quantities: pd.Series
) -> pd.Series:
    """
    Divide each allocated row total by its highlighted quantity
    to produce the result for one piece.
    """

    safe_quantities = quantities.where(
        quantities > 0
    )

    if safe_quantities.isna().any():
        raise ValueError(
            "Every part quantity must be greater than zero."
        )

    return allocated_total / safe_quantities


def calculate_allocated_results(
    parts_df: pd.DataFrame,
    profile: dict
):
    """
    Allocate each time pool across all part rows.

    The allocated row total is divided by the highlighted
    quantity so displayed times represent one piece.
    """

    base_df = parts_df.copy()

    base_df["Allocation Base"] = (
        base_df["Allocation Value"]
        * base_df["Quantity"]
    )

    # ========================================================
    # Allocate complete pools to every part row
    # ========================================================

    total_r_by_row = allocate_pool_total_by_part(
        base_df,
        profile["total_r_time"]
    )

    total_d_143007_by_row = allocate_pool_total_by_part(
        base_df,
        profile["total_d_time_143007"]
    )

    total_d_17033_by_row = allocate_pool_total_by_part(
        base_df,
        profile["total_d_time_17033"]
    )

    total_ida_17033_by_row = allocate_pool_total_by_part(
        base_df,
        profile["total_ida_17033"]
    )

    total_hrs_143007_by_row = allocate_pool_total_by_part(
        base_df,
        profile["total_hours_100_143007"]
    )

    total_hrs_17033_by_row = allocate_pool_total_by_part(
        base_df,
        profile["total_hours_100_17033"]
    )

    # ========================================================
    # Machine 143007, single-piece values
    # ========================================================

    result_143007 = base_df.copy()
    result_143007["Machine"] = "143007"

    result_143007["D-Time"] = convert_total_to_single_piece(
        total_d_143007_by_row,
        result_143007["Quantity"]
    )

    result_143007["R-Time"] = convert_total_to_single_piece(
        total_r_by_row,
        result_143007["Quantity"]
    )

    result_143007["IDA"] = 0.0

    result_143007["Total Per Piece"] = (
        result_143007["D-Time"]
        + result_143007["R-Time"]
        + result_143007["IDA"]
    )

    result_143007["HRS/100"] = (
        convert_total_to_single_piece(
            total_hrs_143007_by_row,
            result_143007["Quantity"]
        )
    )

    result_143007["Total for Quantity"] = (
        result_143007["Total Per Piece"]
        * result_143007["Quantity"]
    )

    # ========================================================
    # Machine 17033, single-piece values
    # ========================================================

    result_17033 = base_df.copy()
    result_17033["Machine"] = "17033"

    result_17033["D-Time"] = convert_total_to_single_piece(
        total_d_17033_by_row,
        result_17033["Quantity"]
    )

    result_17033["R-Time"] = convert_total_to_single_piece(
        total_r_by_row,
        result_17033["Quantity"]
    )

    result_17033["IDA"] = convert_total_to_single_piece(
        total_ida_17033_by_row,
        result_17033["Quantity"]
    )

    result_17033["Total Per Piece"] = (
        result_17033["D-Time"]
        + result_17033["R-Time"]
        + result_17033["IDA"]
    )

    result_17033["HRS/100"] = (
        convert_total_to_single_piece(
            total_hrs_17033_by_row,
            result_17033["Quantity"]
        )
    )

    result_17033["Total for Quantity"] = (
        result_17033["Total Per Piece"]
        * result_17033["Quantity"]
    )

    # ========================================================
    # Weight outputs
    # ========================================================

    for result_df in [
        result_143007,
        result_17033
    ]:
        result_df["Rough Weight Pounds"] = (
            result_df["Finish Weight"]
        )

        result_df["Rough Weight KG"] = (
            result_df["Rough Weight Pounds"]
            * 0.45359237
        )

        result_df["Total Pounds"] = (
            result_df["Rough Weight Pounds"]
            * result_df["Quantity"]
        )

    output_columns = [
        "Machine",
        "Part Number",
        "Finish Weight",
        "D-Time",
        "R-Time",
        "IDA",
        "Total Per Piece",
        "HRS/100",
        "Rough Weight Pounds",
        "Rough Weight KG",
        "Quantity",
        "Total for Quantity",
        "Total Pounds",
        "Allocation Value",
        "Allocation Base",
    ]

    return (
        result_143007[output_columns],
        result_17033[output_columns]
    )
    # --------------------------------------------------------
    # Weight handling
    #
    # Finish weight is directly available.
    # Rough weight is kept configurable because the two reports
    # do not establish one common conversion formula.
    # --------------------------------------------------------

    for result_df in [result_143007, result_17033]:

        result_df["Rough Weight Pounds"] = (
            result_df["Finish Weight"]
        )

        result_df["Rough Weight KG"] = (
            result_df["Rough Weight Pounds"]
            * 0.45359237
        )

        result_df["Total Pounds"] = (
            result_df["Rough Weight Pounds"]
            * result_df["Quantity"]
        )

    wanted_columns = [
        "Machine",
        "Part Number",
        "Finish Weight",
        "D-Time",
        "R-Time",
        "IDA",
        "Total",
        "HRS/100",
        "Rough Weight Pounds",
        "Rough Weight KG",
        "Quantity",
        "STD Minutes",
        "Total Pounds",
        "Allocation Value",
        "Allocation Base",
    ]

    return (
        result_143007[wanted_columns],
        result_17033[wanted_columns]
    )


# ============================================================
# FIXED-WIDTH REPORT
# ============================================================

def format_allocated_section(
    title: str,
    result_df: pd.DataFrame
) -> list[str]:

    lines = ["", title, ""]

    lines.append(
        "PART NUMBER       FINISH     D-TIME   R-TIME   "
        "IDA     TOTAL   HRS/100   ROUGH LB   KG     "
        "QTY   STD MIN   POUNDS"
    )

    lines.append(
        "----------------  --------  -------  -------  "
        "------  -------  --------  --------  ------  "
        "----  --------  --------"
    )

    for _, row in result_df.iterrows():

        prefix = (
            "B"
            if row["Machine"] == "143007"
            else "C"
        )

        lines.append(
            f"{prefix} {row['Part Number']:<14}"
            f"{row['Finish Weight']:>9.2f}"
            f"{row['D-Time']:>9.3f}"
            f"{row['R-Time']:>9.3f}"
            f"{row['IDA']:>8.3f}"
            f"{row['Total']:>9.3f}"
            f"{row['HRS/100']:>10.3f}"
            f"{row['Rough Weight Pounds']:>10.2f}"
            f"{row['Rough Weight KG']:>8.2f}"
            f"{int(row['Quantity']):>6}"
            f"{row['STD Minutes']:>10.3f}"
            f"{row['Total Pounds']:>10.2f}"
        )

    lines.append(
        f"{'TOTAL':>91}"
        f"{result_df['Total for Quantity'].sum():>10.3f}"
        f"{result_df['Total Pounds'].sum():>10.2f}"
    )

    return lines


def build_report(
    header: dict,
    profile: dict,
    result_143007: pd.DataFrame,
    result_17033: pd.DataFrame
) -> str:

    lines = []

    lines.append(
        f"{'FACTORY':>48}    "
        f"{'NEST NUMBER':<16}"
        f"{'PT/OPER':<10}"
        f"{'PAGE':<5}"
    )

    lines.append(
        f"{profile['factory']:>48}    "
        f"{header['Nest Number']:<16}"
        f"{profile['operation']:<10}"
        f"{1:<5}"
    )

    lines.append("")

    lines.append(
        f"{'DEPT NO.':<12}"
        f"{'MACH NO.':<12}"
        f"{'OPERATION DESCRIPTION':>32}"
        f"{'LABOR GRADE':>20}"
    )

    lines.append(
        f"{profile['department']:<12}"
        f"{profile['machine']:<12}"
        f"{'TRUMPF LASER':>32}"
        f"{profile['labor_grade']:>20}"
    )

    lines.append("")

    lines.append(
        f"{'STARTING DIMENSION':>42}"
    )

    lines.append(
        f"{header['Sheet Length']:>25.2f} X "
        f"{header['Sheet Width']:.2f} X "
        f"{header['Thickness']:.2f}"
    )

    lines.append("")

    lines.append(
        f"{'REF':<10}"
        f"{'TOTAL R TIME =':<35}"
        f"{profile['total_r_time']:>10.3f}"
    )

    lines.append(
        f"{'REF':<10}"
        f"{'CALCULATED SIEMENS D TIME =':<35}"
        f"{profile['total_d_time_143007']:>10.3f}"
    )

    lines.append(
        f"{'REF':<10}"
        f"{'CALCULATED SIEMENS2 D TIME =':<35}"
        f"{profile['total_d_time_17033']:>10.3f}"
    )

    lines.extend(
        format_allocated_section(
            "ALLOCATED PER-PART DATA FOR 143007",
            result_143007
        )
    )

    lines.extend(
        format_allocated_section(
            "ALLOCATED PER-PART DATA FOR 17033",
            result_17033
        )
    )

    return "\n".join(lines)


# ============================================================
# STREAMLIT INTERFACE
# ============================================================

st.title("TXT STD Calculator")

st.write(
    "Upload a Lantek TXT file to extract part records, "
    "allocate time pools, and create a legacy-style STD report."
)

uploaded_txt = st.file_uploader(
    "Upload Lantek TXT File",
    type=["txt"],
    key="lantek_std_upload"
)


if uploaded_txt is not None:

    content = uploaded_txt.getvalue().decode(
        "utf-8",
        errors="ignore"
    )

    try:
        header, parts_df, raw_lines = parse_std_txt(
     st.subheader("Quantity Validation")

quantity_source = st.selectbox(
    "Select the TXT field containing part quantity",
    [
        "Detected quantity",
        "Input Value 4",
        "Input Value 5"
    ],
    help=(
        "Use Input Value 4 for T227630_1703. "
        "Use Input Value 5 for T175833_1703."
    )
)

if quantity_source == "Input Value 4":
    parts_df["Quantity"] = (
        parts_df["Input Value 4"].astype(int)
    )

elif quantity_source == "Input Value 5":
    parts_df["Quantity"] = (
        parts_df["Input Value 5"].astype(int)
    )

invalid_quantity = parts_df["Quantity"] <= 0

if invalid_quantity.any():
    invalid_parts = parts_df.loc[
        invalid_quantity,
        "Part Number"
    ].tolist()

    raise ValueError(
        "Quantity is zero or negative for: "
        + ", ".join(invalid_parts)
    )

st.dataframe(
    parts_df[
        [
            "Part Number",
            "Input Value 4",
            "Input Value 5",
            "Quantity"
        ]
    ],
    use_container_width=True,
    hide_index=True
)
content
        )

        profile, validated_profile = get_profile(
            header["Nest Number"]
        )

        if validated_profile:
            st.success(
                "A validated report profile was found for "
                f"{header['Nest Number']}."
            )
        else:
            st.warning(
                "No validated legacy profile exists for this nest. "
                "Enter the validated totals in the configuration "
                "section before using the report."
            )

        # ----------------------------------------------------
        # Configuration
        # ----------------------------------------------------

        with st.expander(
            "Report Time-Pool Configuration",
            expanded=not validated_profile
        ):

            profile["total_r_time"] = st.number_input(
                "Total R Time",
                min_value=0.0,
                value=float(profile["total_r_time"]),
                step=0.001,
                format="%.3f"
            )

            profile["total_d_time_143007"] = st.number_input(
                "Total D Time for 143007",
                min_value=0.0,
                value=float(
                    profile["total_d_time_143007"]
                ),
                step=0.001,
                format="%.3f"
            )

            profile["total_d_time_17033"] = st.number_input(
                "Total D Time for 17033",
                min_value=0.0,
                value=float(
                    profile["total_d_time_17033"]
                ),
                step=0.001,
                format="%.3f"
            )

            profile["total_ida_17033"] = st.number_input(
                "Total IDA for 17033",
                min_value=0.0,
                value=float(
                    profile["total_ida_17033"]
                ),
                step=0.001,
                format="%.3f"
            )

            profile["total_hours_100_143007"] = (
                st.number_input(
                    "Total HRS/100 for 143007",
                    min_value=0.0,
                    value=float(
                        profile[
                            "total_hours_100_143007"
                        ]
                    ),
                    step=0.001,
                    format="%.3f"
                )
            )

            profile["total_hours_100_17033"] = (
                st.number_input(
                    "Total HRS/100 for 17033",
                    min_value=0.0,
                    value=float(
                        profile["total_hours_100_17033"]
                    ),
                    step=0.001,
                    format="%.3f"
                )
            )

result_143007.style.format({
    "Finish Weight": "{:.2f}",
    "D-Time": "{:.3f}",
    "R-Time": "{:.3f}",
    "IDA": "{:.3f}",
    "Total Per Piece": "{:.3f}",
    "HRS/100": "{:.3f}",
    "Rough Weight Pounds": "{:.2f}",
    "Rough Weight KG": "{:.2f}",
    "Total for Quantity": "{:.3f}",
    "Total Pounds": "{:.2f}",
    "Allocation Value": "{:.2f}",
    "Allocation Base": "{:.2f}",
})

result_17033.style.format({
    "Finish Weight": "{:.2f}",
    "D-Time": "{:.3f}",
    "R-Time": "{:.3f}",
    "IDA": "{:.3f}",
    "Total Per Piece": "{:.3f}",
    "HRS/100": "{:.3f}",
    "Rough Weight Pounds": "{:.2f}",
    "Rough Weight KG": "{:.2f}",
    "Total for Quantity": "{:.3f}",
    "Total Pounds": "{:.2f}",
    "Allocation Value": "{:.2f}",
    "Allocation Base": "{:.2f}",
})

    except Exception as error:
        st.error(
            f"Unable to process the TXT file: {error}"
        )
