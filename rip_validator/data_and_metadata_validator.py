"""
Module to handle validating the consistency of data in the Parquet file and the
metadata in the MAML file.

TODO #4: Extend this to validate the consistency of the DAML file too.
"""

from pathlib import Path
from dataclasses import dataclass
import polars as pl
from typing import ClassVar

from .status import Status, State
from .WAVES_config import ClosedInterval, ColumnMetaData
from .helper_validator_methods import check_column_range, check_data_type, print_header
from .data_validator import read_and_validate_parquet
from .maml import read_and_validate_maml, MAMLMetaData
from .report import Report


def _compare_column_type(
    column_name: str, data: pl.LazyFrame, metadata_columns: dict[str, ColumnMetaData]
) -> Status:
    """
    Compares the information for the given column name in both the data and the metadata.
    """
    actual_dtype = data.collect_schema()[column_name]
    expected_type = metadata_columns[column_name].data_type
    if check_data_type(actual_dtype, expected_type):
        return Status.passed()
    else:
        return Status.failed(
            f"Invalid datatype. MAML indicates the expected type is {expected_type} but the Parquet shows type actually is {actual_dtype}",
        )


def _compare_column_range(
    column_name: str, data: pl.LazyFrame, metadata_columns: dict[str, ColumnMetaData]
) -> Status:
    """
    Compares the information for the given column name in both the data and the metadata.
    metadata_columns[column_name].qc has to exist.
    """
    if not metadata_columns[column_name].qc:
        raise ValueError(f"metadata_columns[{column_name}] does not have a qc value.")

    is_valid = check_column_range(
        data,
        column_name,
        metadata_columns[column_name].qc.min,
        metadata_columns[column_name].qc.max,
        ClosedInterval.BOTH,
    )

    if is_valid:
        return Status.passed()
    else:
        return Status.failed(
            f"Invalid range. Data must be between the supplied minimum {metadata_columns[column_name].qc.min} and the supplied maximum {metadata_columns[column_name].qc.max}",
        )


@dataclass
class DataMetadataValueReport(Report):
    column_in_both_files: Status
    valid_column_datatypes: Status | None
    valid_column_ranges: Status | None

    TITLE: ClassVar[str] = "Consistency Validation Report"
    CHECK_LABELS: ClassVar[dict[str, str]] = {
        "column_in_both_files": "Column present in both files:",
        "valid_column_datatypes": "Valid column data types:",
        "valid_column_ranges": "Valid column ranges:",
    }


def validate_data_and_metadata(
    table_name: str,
    data: pl.LazyFrame,
    metadata: MAMLMetaData,
    quiet: bool = False,
    verbose: bool = False,
    return_reports: bool = False,
) -> None | list[DataMetadataValueReport]:
    if not quiet:
        print_header("Data and Metadata Column Consistency Validation Report")

    metadata_columns = metadata.fields
    data_column_names = set(data.collect_schema().names())
    metadata_column_names = set(metadata_columns.columns)
    all_columns = data_column_names | metadata_column_names

    column_reports: list[DataMetadataValueReport] = []

    for column_name in all_columns:
        in_both_files = Status.passed()
        valid_range = None
        valid_datatype = None

        if column_name in data_column_names and column_name in metadata_column_names:
            in_both_files = Status.passed()
            if metadata_columns.columns[column_name].qc:
                valid_range = _compare_column_range(
                    column_name, data, metadata_columns.columns
                )
            else:
                valid_range = Status.passed()
            valid_datatype = _compare_column_type(
                column_name, data, metadata_columns.columns
            )

            column_reports.append(
                DataMetadataValueReport(in_both_files, valid_datatype, valid_range)
            )
        elif column_name in data_column_names:
            in_both_files = Status.failed(
                f"{column_name} found in {table_name}.parquet but not in {table_name}.maml",
            )
            column_reports.append(
                DataMetadataValueReport(in_both_files, valid_datatype, valid_range)
            )
        else:  # column_name in metadata_column_names only
            in_both_files = Status.failed(
                f"{column_name} found in {table_name}.maml but not in {table_name}.parquet",
            )
            column_reports.append(
                DataMetadataValueReport(in_both_files, valid_datatype, valid_range)
            )

    if not quiet:
        for report in column_reports:
            report.print_report(verbose)
        print(f"{'=' * 80}")

    if return_reports:
        return column_reports


def consistency_state(directory: Path, quiet: bool, verbose: bool) -> State:
    """Validates the parquet, maml, and the consistency between both for all parquet files.

    This function does the same checks as valrip consistency but only returns the State of FAIL or PASS.
    Both the data and metadata validator methods will be called.
    """
    final_state = State.PASS
    parquet_files = [p.stem for p in directory.glob("*.parquet")]
    for file in parquet_files:
        lf, data_report = read_and_validate_parquet(
            directory / f"{file}.parquet", quiet, verbose, return_reports=True
        )
        if not data_report.is_valid:
            final_state = State.FAIL

        maml_file = directory / f"{file}.maml"
        if maml_file.is_file():
            maml = read_and_validate_maml(maml_file, quiet, verbose)
            if not maml:
                final_state = State.FAIL
            else:
                reports = validate_data_and_metadata(
                    file, lf, maml, quiet, verbose, return_reports=True
                )
                for report in reports:
                    if not report.is_valid:
                        final_state = State.FAIL
    return final_state
