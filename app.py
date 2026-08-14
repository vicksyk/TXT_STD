"""Prototype parser and calculation engine for Lantek-to-Fortran TXT input.

This reproduces relationships that can be proven from the supplied sample.
For exact Fortran parity, populate the operation/rule configuration from the
Fortran source, lookup tables, or additional validated input/output pairs.
"""
from datetime import date
from io import BytesIO
import re

import pandas as pd
import streamlit as st

# ============================================================
# CONFIGURATION
# Replace these values after validating the Fortran rules.
# ============================================================

DEFAULT_CONFIG = {
    "factory": "DUBUQUE",
    "department": "112",
    "operation": "LC/0000",
    "page": 1,
    "labor_grade": 6,

    # Fixed or lookup-based values observed in the sample output
    "table_shuttle_time": 0.300,
    "machine_time_143007": 0.000,
    "machine_time_17033": 18.750,
    "find_sheet_time": 0.450,

    "aside_time": 3.232,
    "load_sheet_time": 1.879,
    "load_next_nest_time": 0.275,
    "cancel_previous_nest_time": 0.530,
    "remove_skeleton_time": 3.668,
    "tally_count_time": 0.040,
    "tally_miscuts_time": 0.641,
    "record_scrap_time": 0.294,
    "place_parts_time": 0.000,
    "aside_parts_time": 3.232,

    # Values that must be confirmed from Fortran or lookup tables
    "calculated_143007_d_time": 0.015,
    "calculated_17033_d_time": 0.953,
    "ida_total_17033": 1.980,

    # Sample-specific conversion factors
    "hours_100_factor_143007": 1.766263,
    "hours_100_factor_17033": 1.779359,

    # Rough-weight conversion observed in the sample
    "rough_weight_factor": 1.108401,
}


def split_fields(line):
    """Split fixed-width or whitespace-delimited input rows."""
    return re.split(r"\s+", line.strip())


def parse_numeric(value):
    """Convert numeric text to int or float, otherwise keep text."""
    try:
        number = float(value)

        if "." not in value and number.is_integer():
            return int(number)

        return number

    except ValueError:
        return value


def parse_std_input(content):
    """
    Parse the observed four-row TXT structure.
    """

    lines = [
        line.strip()
        for line in content.splitlines()
        if line.strip()
    ]

    if len(lines) < 4:
        raise ValueError(
            "Expected at least four non-empty rows in the TXT file."
        )

    header_1 = [
        parse_numeric(value)
        for value in split_fields(lines[0])
    ]

    header_2 = [
        parse_numeric(value)
        for value in split_fields(lines[1])
    ]

    header_3 = [
        parse_numeric(value)
        for value in split_fields(lines[2])
    ]

    part_values = [
        parse_numeric(value)
        for value in split_fields(lines[3])
    ]

    if len(header_1) < 7:
        raise ValueError(
            "First row must contain at least 7 values."
        )

    if len(header_2) < 2:
        raise ValueError(
            "Second row must contain at least 2 values."
        )

    if len(header_3) < 3:
        raise ValueError(
            "Third row must contain at least 3 values."
        )

    if len(part_values) < 11:
        raise ValueError(
            "Part row must contain at least 11 values."
        )

    parsed = {
        "material_code": str(header_1[0]),
        "nest_number": str(header_1[1]),
        "plates": int(header_1[2]),
        "burns_per_nest": int(header_1[3]),
        "thickness": float(header_1[4]),
        "sheet_length": float(header_1[5]),
        "sheet_width": float(header_1[6]),

        "header_2_value_1": header_2[0],
        "header_2_value_2": header_2[1],

        "siemens_act_1": float(header_3[0]),
        "siemens_act_2": float(header_3[1]),
        "siemens_value_3": float(header_3[2]),

        "part_number": str(part_values[0]),
        "finish_weight": float(part_values[1]),
        "part_value_2": float(part_values[2]),
        "part_value_3": float(part_values[3]),

        # This position produces quantity 4 in the supplied example.
        "quantity": int(part_values[4]),

        "part_value_5": part_values[5],
        "part_value_6": part_values[6],
        "part_value_7": part_values[7],
        "part_value_8": part_values[8],
        "part_value_9": part_values[9],
        "part_value_10": part_values[10],
    }

    return parsed


def calculate_std_values(data, config):
    """
    Calculate values using relationships visible in the supplied
    input/output example.

    IMPORTANT:
    Lookup constants must be validated against the Fortran source
    before production use.
    """

    quantity = max(int(data["quantity"]), 1)

    total_r_time = (
        config["aside_time"]
        + config["load_sheet_time"]
        + config["load_next_nest_time"]
        + config["cancel_previous_nest_time"]
        + config["remove_skeleton_time"]
        + config["tally_count_time"]
        + config["tally_miscuts_time"]
        + config["record_scrap_time"]
        + config["place_parts_time"]
        + config["aside_parts_time"]
    )

    # The attached legacy output explicitly reports 10.559.
    # The visible individual operation values add to a different
    # total because not every legacy allocation rule is known.
    # Allow the validated total to be entered separately.
    validated_total_r_time = config.get(
        "validated_total_r_time",
        10.559
    )

    r_time_per_part = (
        validated_total_r_time / quantity
    )

    d_time_143007 = (
        config["calculated_143007_d_time"] / quantity
    )

    d_time_17033 = (
        config["calculated_17033_d_time"] / quantity
    )

    ida_143007 = 0.0

    ida_17033 = (
        config["ida_total_17033"] / quantity
    )

    total_143007 = (
        d_time_143007
        + r_time_per_part
        + ida_143007
    )

    total_17033 = (
        d_time_17033
        + r_time_per_part
        + ida_17033
    )

    std_minutes_143007 = (
        total_143007 * quantity
    )

    std_minutes_17033 = (
        total_17033 * quantity
    )

    hours_100_143007 = (
        total_143007
        * config["hours_100_factor_143007"]
    )

    hours_100_17033 = (
        total_17033
        * config["hours_100_factor_17033"]
    )

    rough_weight_lb = (
        data["finish_weight"]
        * config["rough_weight_factor"]
    )

    rough_weight_kg = (
        rough_weight_lb * 0.45359237
    )

    total_weight_lb = (
        rough_weight_lb * quantity
    )

    return {
        "visible_operation_sum": total_r_time,
        "validated_total_r_time": validated_total_r_time,
        "r_time_per_part": r_time_per_part,
        "d_time_143007": d_time_143007,
        "d_time_17033": d_time_17033,
        "ida_143007": ida_143007,
        "ida_17033": ida_17033,
        "total_143007": total_143007,
        "total_17033": total_17033,
        "hours_100_143007": hours_100_143007,
        "hours_100_17033": hours_100_17033,
        "std_minutes_143007": std_minutes_143007,
        "std_minutes_17033": std_minutes_17033,
        "rough_weight_lb": rough_weight_lb,
        "rough_weight_kg": rough_weight_kg,
        "total_weight_lb": total_weight_lb,
    }


def make_allocated_rows(data, calculated):
    """
    Build the two allocated per-part report rows.
    """

    common = {
        "Part Number": data["part_number"],
        "Finish Weight": data["finish_weight"],
        "R-Time": calculated["r_time_per_part"],
        "Quantity": data["quantity"],
        "Rough Weight Pounds": calculated["rough_weight_lb"],
        "Rough Weight KG": calculated["rough_weight_kg"],
        "Total Pounds": calculated["total_weight_lb"],
    }

    row_143007 = {
        "Machine": "143007",
        **common,
        "D-Time": calculated["d_time_143007"],
        "IDA": calculated["ida_143007"],
        "Total": calculated["total_143007"],
        "HRS/100": calculated["hours_100_143007"],
        "STD Minutes": calculated["std_minutes_143007"],
    }

    row_17033 = {
        "Machine": "17033",
        **common,
        "D-Time": calculated["d_time_17033"],
        "IDA": calculated["ida_17033"],
        "Total": calculated["total_17033"],
        "HRS/100": calculated["hours_100_17033"],
        "STD Minutes": calculated["std_minutes_17033"],
    }

    return pd.DataFrame([
        row_143007,
        row_17033
    ])


def make_operation_table(config):
    return pd.DataFrame([
        ["CALC", "TABLE SHUTTLE TIME", "MT", "1/1",
         config["table_shuttle_time"]],

        ["CALC", "MACHINE TIME FOR 143007", "MT", "1/1",
         config["machine_time_143007"]],

        ["CALC", "MACHINE TIME FOR 17033", "MT", "1/1",
         config["machine_time_17033"]],

        ["TX2060", "ASIDE", "R", "1/1",
         config["aside_time"]],

        ["TX7351", "LOAD SHEET TO TABLE", "R", "1/1",
         config["load_sheet_time"]],

        ["TX7367", "LOAD NEXT NEST", "R", "1/1",
         config["load_next_nest_time"]],

        ["TX7482", "CANCEL PREVIOUS NEST", "R", "1/1",
         config["cancel_previous_nest_time"]],

        ["TX7368", "REMOVE SKELETON FROM TABLE", "R", "1/1",
         config["remove_skeleton_time"]],

        ["A118", "TALLY COUNT FOR DIFFERENT PARTS", "R", "1/1",
         config["tally_count_time"]],

        ["T21983", "TALLY ALL MISCUTS", "R", "1/1",
         config["tally_miscuts_time"]],

        ["T21727", "RECORD GOOD, SCRAP AND RECLAIM PARTS", "R", "1/1",
         config["record_scrap_time"]],

        ["A1491", "PLACE PARTS TO STACK ON TABLE", "R", "0/1",
         config["place_parts_time"]],

        ["TX7354", "ASIDE PARTS WITH HOIST", "R", "4/1",
         config["aside_parts_time"]],
    ], columns=[
        "Code",
        "Elemental Description",
        "R/MT",
        "Occurrence/Cycle",
        "STD Minutes/Cycle"
    ])


def build_fixed_width_report(data, config, calculated):
    """
    Create a downloadable text report similar to the supplied
    legacy fixed-width report.
    """

    report_date = date.today().strftime("%d/%b/%Y")

    lines = []

    lines.append(
        f"{'FACTORY':>58}    {'NEST NUMBER':<15} "
        f"{'PT/OPER':<10} {'PAGE':<5}"
    )

    lines.append(
        f"{config['factory']:>58}    "
        f"{data['nest_number']:<15} "
        f"{config['operation']:<10} "
        f"{config['page']:<5}"
    )

    lines.append(
        f"{'DEPT NO.':<12}{'MACH NO.':<12}"
        f"{'OPERATION DESCRIPTION':>35}"
        f"{'LABOR GRADE':>20}"
    )

    lines.append(
        f"{config['department']:<12}"
        f"{'17033':<12}"
        f"{'TRUMPF LASER':>35}"
        f"{config['labor_grade']:>20}"
    )

    lines.append("")

    lines.append(
        f"{'DATE':<20}"
        f"{'STARTING DIMENSION':>35}"
    )

    lines.append(
        f"{report_date:<20}"
        f"{data['sheet_length']:>15.2f} X "
        f"{data['sheet_width']:.2f} X "
        f"{data['thickness']:.2f}"
    )

    lines.append("")
    lines.append(
        f"{'CODE':<10}"
        f"{'ELEMENTAL DESCRIPTION':<48}"
        f"{'R/MT':>6}"
        f"{'OCC./CYCLE':>13}"
        f"{'STD. MIN./CYCLE':>18}"
    )

    operation_df = make_operation_table(config)

    for _, row in operation_df.iterrows():
        lines.append(
            f"{row['Code']:<10}"
            f"{row['Elemental Description']:<48}"
            f"{row['R/MT']:>6}"
            f"{row['Occurrence/Cycle']:>13}"
            f"{row['STD Minutes/Cycle']:>18.3f}"
        )

    lines.append("")
    lines.append(
        f"{'REF':<10}"
        f"{'TOTAL R TIME =':<30}"
        f"{calculated['validated_total_r_time']:>10.3f}"
    )

    lines.append(
        f"{'REF':<10}"
        f"{'CALCULATED SIEMENS D TIME =':<30}"
        f"{config['calculated_143007_d_time']:>10.3f}"
    )

    lines.append(
        f"{'REF':<10}"
        f"{'CALCULATED SIEMENS2 D TIME =':<30}"
        f"{config['calculated_17033_d_time']:>10.3f}"
    )

    lines.append("")
    lines.append(
        f"{'ALLOCATED PER-PART DATA FOR 143007'}"
    )

    lines.append(
        "PART NUMBER       FINISH WT   D-TIME   R-TIME   "
        "IDA   TOTAL   HRS/100   QTY   STD MIN   POUNDS"
    )

    lines.append(
        f"{data['part_number']:<17}"
        f"{data['finish_weight']:>9.2f}"
        f"{calculated['d_time_143007']:>9.3f}"
        f"{calculated['r_time_per_part']:>9.3f}"
        f"{calculated['ida_143007']:>7.3f}"
        f"{calculated['total_143007']:>8.3f}"
        f"{calculated['hours_100_143007']:>10.3f}"
        f"{data['quantity']:>6}"
        f"{calculated['std_minutes_143007']:>10.3f}"
        f"{calculated['total_weight_lb']:>10.2f}"
    )

    lines.append("")
    lines.append(
        f"{'ALLOCATED PER-PART DATA FOR 17033'}"
    )

    lines.append(
        "PART NUMBER       FINISH WT   D-TIME   R-TIME   "
        "IDA   TOTAL   HRS/100   QTY   STD MIN   POUNDS"
    )

    lines.append(
        f"{data['part_number']:<17}"
        f"{data['finish_weight']:>9.2f}"
        f"{calculated['d_time_17033']:>9.3f}"
        f"{calculated['r_time_per_part']:>9.3f}"
        f"{calculated['ida_17033']:>7.3f}"
        f"{calculated['total_17033']:>8.3f}"
        f"{calculated['hours_100_17033']:>10.3f}"
        f"{data['quantity']:>6}"
        f"{calculated['std_minutes_17033']:>10.3f}"
        f"{calculated['total_weight_lb']:>10.2f}"
    )

    return "\n".join(lines)


# ============================================================
# STREAMLIT USER INTERFACE
# ============================================================

st.title("TXT STD Calculator")

st.caption(
    "Upload a Lantek TXT file to extract nest data, "
    "calculate STD values, and generate a legacy-style report."
)

uploaded_txt = st.file_uploader(
    "Upload Lantek TXT File",
    type=["txt"],
    key="std_txt_upload"
)

with st.expander("STD Configuration"):
    st.warning(
        "The values below reproduce the supplied example. "
        "Validate them against the Fortran source or approved "
        "lookup tables before using the application for production."
    )

    config = DEFAULT_CONFIG.copy()

    config["department"] = st.text_input(
        "Department",
        value=config["department"]
    )

    config["factory"] = st.text_input(
        "Factory",
        value=config["factory"]
    )

    config["validated_total_r_time"] = st.number_input(
        "Validated Total R Time",
        min_value=0.0,
        value=10.559,
        step=0.001,
        format="%.3f"
    )

    config["calculated_143007_d_time"] = st.number_input(
        "Total Calculated D Time for 143007",
        min_value=0.0,
        value=config["calculated_143007_d_time"],
        step=0.001,
        format="%.3f"
    )

    config["calculated_17033_d_time"] = st.number_input(
        "Total Calculated D Time for 17033",
        min_value=0.0,
        value=config["calculated_17033_d_time"],
        step=0.001,
        format="%.3f"
    )

    config["ida_total_17033"] = st.number_input(
        "Total IDA for 17033",
        min_value=0.0,
        value=config["ida_total_17033"],
        step=0.001,
        format="%.3f"
    )


if uploaded_txt is not None:

    content = uploaded_txt.getvalue().decode(
        "utf-8",
        errors="ignore"
    )

    try:
        data = parse_std_input(content)

        calculated = calculate_std_values(
            data,
            config
        )

        operations_df = make_operation_table(
            config
        )

        allocated_df = make_allocated_rows(
            data,
            calculated
        )

        report_text = build_fixed_width_report(
            data,
            config,
            calculated
        )

        st.success(
            "TXT file processed successfully."
        )

        # ----------------------------------------------------
        # Header summary
        # ----------------------------------------------------

        st.subheader("Nest Summary")

        col1, col2, col3, col4 = st.columns(4)

        col1.metric(
            "Nest Number",
            data["nest_number"]
        )

        col2.metric(
            "Part Number",
            data["part_number"]
        )

        col3.metric(
            "Quantity",
            data["quantity"]
        )

        col4.metric(
            "Thickness",
            f"{data['thickness']:.3f}"
        )

        summary_df = pd.DataFrame([{
            "Material Code": data["material_code"],
            "Nest Number": data["nest_number"],
            "Sheet Length": data["sheet_length"],
            "Sheet Width": data["sheet_width"],
            "Thickness": data["thickness"],
            "Part Number": data["part_number"],
            "Finish Weight": data["finish_weight"],
            "Quantity": data["quantity"],
        }])

        st.dataframe(
            summary_df,
            use_container_width=True,
            hide_index=True
        )

        # ----------------------------------------------------
        # Operation times
        # ----------------------------------------------------

        st.subheader("Elemental Operation Times")

        st.dataframe(
            operations_df.style.format({
                "STD Minutes/Cycle": "{:.3f}"
            }),
            use_container_width=True,
            hide_index=True
        )

        # ----------------------------------------------------
        # Allocated report
        # ----------------------------------------------------

        st.subheader("Allocated Per-Part Results")

        st.dataframe(
            allocated_df.style.format({
                "Finish Weight": "{:.2f}",
                "D-Time": "{:.3f}",
                "R-Time": "{:.3f}",
                "IDA": "{:.3f}",
                "Total": "{:.3f}",
                "HRS/100": "{:.3f}",
                "STD Minutes": "{:.3f}",
                "Rough Weight Pounds": "{:.2f}",
                "Rough Weight KG": "{:.2f}",
                "Total Pounds": "{:.2f}",
            }),
            use_container_width=True,
            hide_index=True
        )

        # ----------------------------------------------------
        # Fixed-width report preview
        # ----------------------------------------------------

        st.subheader("Legacy-Style STD Output")

        st.code(
            report_text,
            language=None
        )

        # ----------------------------------------------------
        # Downloads
        # ----------------------------------------------------

        st.download_button(
            "Download Legacy STD TXT Report",
            data=report_text.encode("utf-8"),
            file_name=(
                f"{data['nest_number']}_STD_OUTPUT.txt"
            ),
            mime="text/plain"
        )

        excel_buffer = BytesIO()

        with pd.ExcelWriter(
            excel_buffer,
            engine="openpyxl"
        ) as writer:

            summary_df.to_excel(
                writer,
                sheet_name="Nest Summary",
                index=False
            )

            operations_df.to_excel(
                writer,
                sheet_name="Operations",
                index=False
            )

            allocated_df.to_excel(
                writer,
                sheet_name="Allocated Results",
                index=False
            )

        st.download_button(
            "Download STD Results as Excel",
            data=excel_buffer.getvalue(),
            file_name=(
                f"{data['nest_number']}_STD_RESULTS.xlsx"
            ),
            mime=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            )
        )

        # ----------------------------------------------------
        # Validation differences
        # ----------------------------------------------------

        with st.expander("Calculation Validation"):

            st.write(
                "Visible operation-time sum:",
                f"{calculated['visible_operation_sum']:.3f}"
            )

            st.write(
                "Validated total R time:",
                f"{calculated['validated_total_r_time']:.3f}"
            )

            st.write(
                "The two totals are intentionally shown separately "
                "because the supplied report does not expose all "
                "legacy allocation rules."
            )

    except Exception as error:

        st.error(
            f"Unable to process the TXT file: {error}"
        )

else:

    st.info(
        "Upload a TXT file to generate STD results."
    )
