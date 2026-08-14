"""Parser and calculation engine for Lantek-to-Fortran TXT input."""

from __future__ import annotations

from io import BytesIO
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
        "total_ida_17033": 1.978,
        "total_std_143007": 10.574,
        "total_std_17033": 13.490,
        "total_hours_100_143007": 18.686,
        "total_hours_100_17033": 23.837,
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
        "total_ida_17033": 9.260,
        "total_std_143007": 32.338,
        "total_std_17033": 44.779,
        "total_hours_100_143007": 57.144,
        "total_hours_100_17033": 79.125,
    },
}


# ============================================================
# INPUT PARSER
# ============================================================

def split_fields(line: str) -> list
"""Split a whitespace-delimited TXT row."""
    return re.split(r"\s+", line.strip())


def to_number(value: str):
    """Convert numeric text to int or float when possible."""
    try:
        number = float(value)

        if "." not in value and number.is_integer():
            return int(number)

        return number

    except ValueError:
        return value


def clean_identifier(value) -> str:
    """Remove escaped underscores from identifiers."""
    return str(value).replace("\\_", "_")


def parse_std_txt(content: str):
    """
    Parse the complete TXT file.

    First three non-empty lines:
    Header records.

    Remaining non-empty lines:
    Individual part records.
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
        [
            to_number(value)
            for value in split_fields(line)
        ]
        for line in lines
    ]

    header_1 = rows[0]
    header_2 = rows[1]
    header_3 = rows[2]
    part_rows = rows[3:]

    if (
        len(header_1) < 7
        or len(header_2) < 2
        or len(header_3) < 3
    ):
        raise ValueError(
            "Header rows do not contain the expected values."
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

    quantity_position_by_nest = {
        "T227630_1703": 4,
        "T175833_1703": 5,
    }

    default_quantity_position = (
        quantity_position_by_nest.get(
            header["Nest Number"],
            4
        )
    )

    parts = []

    for source_row, row in enumerate(
        part_rows,
        start=4
    ):
        if len(row) < 11:
            raise ValueError(
                f"Part row {source_row} contains "
                f"{len(row)} values. At least 11 are required."
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
            "Quantity": int(
                row[default_quantity_position]
            ),
        }

        parts.append(part)

    parts_df = pd.DataFrame(parts)

    if parts_df.empty:
        raise ValueError(
            "No part records were found."
        )

    return header, parts_df, lines


# ============================================================
# REPORT PROFILE
# ============================================================

def get_profile(nest_number: str):
    """Return the validated profile for the nest."""

    clean_nest = clean_identifier(nest_number)

    if clean_nest in VALIDATED_PROFILES:
        return (
            VALIDATED_PROFILES[
                clean_nest
            ].copy(),
            True
        )

    default_profile = {
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
    }

    return default_profile, False


# ============================================================
# ALLOCATION LOGIC
# ============================================================

def allocate_pool_total_by_part(
    parts_df: pd.DataFrame,
    total_pool: float
) -> pd.Series:
    """
    Allocate a complete total pool to all part rows.

    Allocation weight:
    Allocation Value multiplied by Quantity.
    """

    allocation_base = (
        parts_df["Allocation Value"]
        * parts_df["Quantity"]
    )

    total_base = allocation_base.sum()

    if total_base <= 0:
        raise ValueError(
            "The total allocation base must be "
            "greater than zero."
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
    Convert an allocated row total to the value
    for one piece.
    """

    if (quantities <= 0).any():
        raise ValueError(
            "Every part quantity must be "
            "greater than zero."
        )

    return allocated_total / quantities


def calculate_allocated_results(
    parts_df: pd.DataFrame,
    profile: dict
):
    """
    Calculate single-piece values for every part.

    The complete time pools are:
    1. Allocated across all part rows.
    2. Divided by each part quantity.
    """

    base_df = parts_df.copy()

    base_df["Allocation Base"] = (
        base_df["Allocation Value"]
        * base_df["Quantity"]
    )

    total_r_by_row = allocate_pool_total_by_part(
        base_df,
        profile["total_r_time"]
    )

    total_d_143007_by_row = (
        allocate_pool_total_by_part(
            base_df,
            profile["total_d_time_143007"]
        )
    )

    total_d_17033_by_row = (
        allocate_pool_total_by_part(
            base_df,
            profile["total_d_time_17033"]
        )
    )

    total_ida_17033_by_row = (
        allocate_pool_total_by_part(
            base_df,
            profile["total_ida_17033"]
        )
    )

    total_hrs_143007_by_row = (
        allocate_pool_total_by_part(
            base_df,
            profile[
                "total_hours_100_143007"
            ]
        )
    )

    total_hrs_17033_by_row = (
        allocate_pool_total_by_part(
            base_df,
            profile[
                "total_hours_100_17033"
            ]
        )
    )

    def make_result(
        machine: str,
        d_total: pd.Series,
        ida_total,
        hrs_total: pd.Series
    ):
        result = base_df.copy()

        result["Machine"] = machine

        result["D-Time"] = (
            convert_total_to_single_piece(
                d_total,
                result["Quantity"]
            )
        )

        result["R-Time"] = (
            convert_total_to_single_piece(
                total_r_by_row,
                result["Quantity"]
            )
        )

        if isinstance(ida_total, float):
            result["IDA"] = 0.0
        else:
            result["IDA"] = (
                convert_total_to_single_piece(
                    ida_total,
                    result["Quantity"]
                )
            )

        result["Total Per Piece"] = (
            result["D-Time"]
            + result["R-Time"]
            + result["IDA"]
        )

        result["HRS/100"] = (
            convert_total_to_single_piece(
                hrs_total,
                result["Quantity"]
            )
        )

        result["Total for Quantity"] = (
            result["Total Per Piece"]
            * result["Quantity"]
        )

        result["Rough Weight Pounds"] = (
            result["Finish Weight"]
        )

        result["Rough Weight KG"] = (
            result["Rough Weight Pounds"]
            * 0.45359237
        )

        result["Total Pounds"] = (
            result["Rough Weight Pounds"]
            * result["Quantity"]
        )

        return result

    result_143007 = make_result(
        machine="143007",
        d_total=total_d_143007_by_row,
        ida_total=0.0,
        hrs_total=total_hrs_143007_by_row
    )

    result_17033 = make_result(
        machine="17033",
        d_total=total_d_17033_by_row,
        ida_total=total_ida_17033_by_row,
        hrs_total=total_hrs_17033_by_row
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


# ============================================================
# FIXED-WIDTH REPORT
# ============================================================

def format_allocated_section(
    title: str,
    result_df: pd.DataFrame
) -> list
"""Create one allocated-results report section."""

    lines = [
        "",
        title,
        ""
    ]

    lines.append(
        "PART NUMBER       FINISH   D-TIME   "
        "R-TIME    IDA    TOTAL  HRS/100  "
        "QTY   STD MIN"
    )

    for _, row in result_df.iterrows():

        prefix = (
            "B"
            if row["Machine"] == "143007"
            else "C"
        )

        lines.append(
            f"{prefix} "
            f"{row['Part Number']:<14}"
            f"{row['Finish Weight']:>8.2f}"
            f"{row['D-Time']:>9.3f}"
            f"{row['R-Time']:>9.3f}"
            f"{row['IDA']:>8.3f}"
            f"{row['Total Per Piece']:>9.3f}"
            f"{row['HRS/100']:>9.3f}"
            f"{int(row['Quantity']):>5}"
            f"{row['Total for Quantity']:>10.3f}"
        )

    lines.append(
        f"{'TOTAL':>82}"
        f"{result_df['Total for Quantity'].sum():>10.3f}"
    )

    return lines


def build_report(
    header: dict,
    profile: dict,
    result_143007: pd.DataFrame,
    result_17033: pd.DataFrame
) -> str:
    """Generate the legacy-style text output."""

    lines = [
        (
            f"{'FACTORY':>48}    "
            f"{'NEST NUMBER':<16}"
            f"{'PT/OPER':<10}"
            f"{'PAGE':<5}"
        ),
        (
            f"{profile['factory']:>48}    "
            f"{header['Nest Number']:<16}"
            f"{profile['operation']:<10}"
            f"{1:<5}"
        ),
        "",
        f"{'STARTING DIMENSION':>42}",
        (
            f"{header['Sheet Length']:>25.2f} X "
            f"{header['Sheet Width']:.2f} X "
            f"{header['Thickness']:.3f}"
        ),
        "",
        (
            f"{'REF':<10}"
            f"{'TOTAL R TIME =':<35}"
            f"{profile['total_r_time']:>10.3f}"
        ),
        (
            f"{'REF':<10}"
            f"{'CALCULATED SIEMENS D TIME =':<35}"
            f"{profile['total_d_time_143007']:>10.3f}"
        ),
        (
            f"{'REF':<10}"
            f"{'CALCULATED SIEMENS2 D TIME =':<35}"
            f"{profile['total_d_time_17033']:>10.3f}"
        ),
    ]

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
    "Upload a Lantek TXT file to calculate "
    "single-piece values for every part."
)

uploaded_txt = st.file_uploader(
    "Upload Lantek TXT File",
    type=["txt"],
    key="lantek_std_upload"
)


if uploaded_txt is None:

    st.info(
        "Upload a TXT file to begin."
    )

else:

    try:
        content = uploaded_txt.getvalue().decode(
            "utf-8",
            errors="ignore"
        )

        header, parts_df, raw_lines = (
            parse_std_txt(content)
        )

        profile, validated_profile = get_profile(
            header["Nest Number"]
        )

        if validated_profile:
            st.success(
                "Validated profile found for "
                f"{header['Nest Number']}."
            )
        else:
            st.warning(
                "No validated profile was found for this nest. "
                "Enter the validated totals in the "
                "configuration section."
            )

        # ====================================================
        # QUANTITY SELECTION
        # ====================================================

        st.subheader("Quantity Validation")

        quantity_source = st.selectbox(
            "Select the TXT field containing part quantity",
            [
                "Detected quantity",
                "Input Value 4",
                "Input Value 5"
            ],
            help=(
                "T227630_1703 uses Input Value 4. "
                "T175833_1703 uses Input Value 5."
            )
        )

        if quantity_source == "Input Value 4":

            parts_df["Quantity"] = (
                parts_df["Input Value 4"]
                .astype(int)
            )

        elif quantity_source == "Input Value 5":

            parts_df["Quantity"] = (
                parts_df["Input Value 5"]
                .astype(int)
            )

        if (parts_df["Quantity"] <= 0).any():

            invalid_parts = parts_df.loc[
                parts_df["Quantity"] <= 0,
                "Part Number"
            ].tolist()

            raise ValueError(
                "Quantity must be greater than zero for: "
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

        # ====================================================
        # CONFIGURATION
        # ====================================================

        with st.expander(
            "Report Time-Pool Configuration",
            expanded=not validated_profile
        ):

            profile["total_r_time"] = (
                st.number_input(
                    "Total R Time",
                    min_value=0.0,
                    value=float(
                        profile["total_r_time"]
                    ),
                    step=0.001,
                    format="%.3f"
                )
            )

            profile["total_d_time_143007"] = (
                st.number_input(
                    "Total D Time for 143007",
                    min_value=0.0,
                    value=float(
                        profile[
                            "total_d_time_143007"
                        ]
                    ),
                    step=0.001,
                    format="%.3f"
                )
            )

            profile["total_d_time_17033"] = (
                st.number_input(
                    "Total D Time for 17033",
                    min_value=0.0,
                    value=float(
                        profile[
                            "total_d_time_17033"
                        ]
                    ),
                    step=0.001,
                    format="%.3f"
                )
            )

            profile["total_ida_17033"] = (
                st.number_input(
                    "Total IDA for 17033",
                    min_value=0.0,
                    value=float(
                        profile[
                            "total_ida_17033"
                        ]
                    ),
                    step=0.001,
                    format="%.3f"
                )
            )

            profile[
                "total_hours_100_143007"
            ] = st.number_input(
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

            profile[
                "total_hours_100_17033"
            ] = st.number_input(
                "Total HRS/100 for 17033",
                min_value=0.0,
                value=float(
                    profile[
                        "total_hours_100_17033"
                    ]
                ),
                step=0.001,
                format="%.3f"
            )

        # ====================================================
        # CALCULATE RESULTS
        # ====================================================

        result_143007, result_17033 = (
            calculate_allocated_results(
                parts_df,
                profile
            )
        )

        report_text = build_report(
            header,
            profile,
            result_143007,
            result_17033
        )

        st.success(
            "TXT file processed successfully."
        )

        formats = {
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
        }

        # ====================================================
        # MACHINE 143007
        # ====================================================

        st.subheader(
            "Allocated Per-Part Data for 143007"
        )

        st.dataframe(
            result_143007.style.format(
                formats
            ),
            use_container_width=True,
            hide_index=True
        )

        # ====================================================
        # MACHINE 17033
        # ====================================================

        st.subheader(
            "Allocated Per-Part Data for 17033"
        )

        st.dataframe(
            result_17033.style.format(
                formats
            ),
            use_container_width=True,
            hide_index=True
        )

        # ====================================================
        # VALIDATION
        # ====================================================

        validation_df = pd.DataFrame(
            [
                {
                    "Machine": "143007",
                    "Calculated STD Total": (
                        result_143007[
                            "Total for Quantity"
                        ].sum()
                    ),
                    "Expected STD Total": (
                        profile[
                            "total_std_143007"
                        ]
                    ),
                },
                {
                    "Machine": "17033",
                    "Calculated STD Total": (
                        result_17033[
                            "Total for Quantity"
                        ].sum()
                    ),
                    "Expected STD Total": (
                        profile[
                            "total_std_17033"
                        ]
                    ),
                },
            ]
        )

        validation_df["Difference"] = (
            validation_df[
                "Calculated STD Total"
            ]
            - validation_df[
                "Expected STD Total"
            ]
        )

        st.subheader("Validation Totals")

        st.dataframe(
            validation_df.style.format(
                {
                    "Calculated STD Total": "{:.3f}",
                    "Expected STD Total": "{:.3f}",
                    "Difference": "{:.3f}",
                }
            ),
            use_container_width=True,
            hide_index=True
        )

        # ====================================================
        # REPORT PREVIEW
        # ====================================================

        st.subheader(
            "Legacy-Style STD Output"
        )

        st.code(
            report_text,
            language=None
        )

        # ====================================================
        # TXT DOWNLOAD
        # ====================================================

        st.download_button(
            label="Download Legacy STD TXT Report",
            data=report_text.encode("utf-8"),
            file_name=(
                f"{header['Nest Number']}"
                "_STD_OUTPUT.txt"
            ),
            mime="text/plain"
        )

        # ====================================================
        # EXCEL DOWNLOAD
        # ====================================================

        excel_buffer = BytesIO()

        with pd.ExcelWriter(
            excel_buffer,
            engine="openpyxl"
        ) as writer:

            pd.DataFrame(
                [header]
            ).to_excel(
                writer,
                sheet_name="Nest Summary",
                index=False
            )

            parts_df.to_excel(
                writer,
                sheet_name="Input Parts",
                index=False
            )

            result_143007.to_excel(
                writer,
                sheet_name="Machine 143007",
                index=False
            )

            result_17033.to_excel(
                writer,
                sheet_name="Machine 17033",
                index=False
            )

            validation_df.to_excel(
                writer,
                sheet_name="Validation",
                index=False
            )

        st.download_button(
            label=(
                "Download Complete STD Results "
                "as Excel"
            ),
            data=excel_buffer.getvalue(),
            file_name=(
                f"{header['Nest Number']}"
                "_STD_RESULTS.xlsx"
            ),
            mime=(
                "application/vnd.openxmlformats-"
                "officedocument.spreadsheetml.sheet"
            )
        )

        # ====================================================
        # ORIGINAL INPUT
        # ====================================================

        with st.expander(
            "View Original TXT Input"
        ):
            st.text_area(
                "TXT Contents",
                content,
                height=250
            )

    except Exception as error:

        st.error(
            f"Unable to process the TXT file: {error}"
        )
