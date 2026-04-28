"""
Module to handle validating the consistency of data in the Parquet file and the
metadata in the MAML file.

TODO #4: Extend this to validate the consistency of the DAML file too.
"""

from pathlib import Path
from dataclasses import dataclass
import polars as pl

from .status import Status, State
from .WAVES_config import ClosedInterval, ANSI, ColumnMetaData, MamlMetaData
from .helper_validator_methods import check_column_range, check_data_type, print_header
from .data_validator import read_and_validate_parquet
from .metadata_validator import read_and_validate_maml


def _compare_column_type(
    column_name: str, data: pl.LazyFrame, metadata_columns: dict[str, ColumnMetaData]
) -> Status:
    """
    Compares the information for the given column name in both the data and the metadata.
    """
    actual_dtype = data.collect_schema()[column_name]
    expected_type = metadata_columns[column_name].data_type
    if check_data_type(actual_dtype, expected_type):
        return Status(State.PASS)
    else:
        return Status(
            State.FAIL,
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
        return Status(State.PASS)
    else:
        return Status(
            State.FAIL,
            f"Invalid range. Data must be between the supplied minimum {metadata_columns[column_name].qc.min} and the supplied maximum {metadata_columns[column_name].qc.max}",
        )


@dataclass
class DataMetadataValueReport:
    column_name: str
    column_in_both_files: Status
    valid_column_datatypes: Status | None
    valid_column_ranges: Status | None

    def __post_init__(self) -> None:
        self.valid = State.PASS
        if any(
            [
                self.column_in_both_files.state == State.WARNING,
                self.valid_column_datatypes
                and self.valid_column_datatypes.state == State.WARNING,
                self.valid_column_ranges
                and self.valid_column_ranges.state == State.WARNING,
            ]
        ):
            self.valid = State.WARNING
        elif any(
            [
                self.column_in_both_files.state == State.FAIL,
                self.valid_column_datatypes
                and self.valid_column_datatypes.state == State.FAIL,
                self.valid_column_ranges
                and self.valid_column_ranges.state == State.FAIL,
            ]
        ):
            self.valid = State.FAIL

    def print_report(self, verbose=False) -> None:
        """
        Print a professional validation report with color-coded results.
        """
        # Overall column status
        is_valid = self.valid == State.PASS
        overall_color = ANSI.GREEN if is_valid else ANSI.RED
        overall_status = "VALID" if is_valid else "INVALID"
        print(
            f"\n{ANSI.BOLD}Column:{ANSI.RESET} {self.column_name} | {ANSI.BOLD}Overall Status:{ANSI.RESET} {overall_color}{overall_status}{ANSI.RESET}"
        )

        if self.valid != State.PASS or verbose:
            print(f"\n{ANSI.BOLD}Validation Checks:{ANSI.RESET}")
            print(f"{'-' * 80}")

            column_in_both_files_info = (
                f"\n     {ANSI.RED} → {self.column_in_both_files.message}.{ANSI.RESET}"
                if self.column_in_both_files.state == State.FAIL
                else ""
            )
            if self.column_in_both_files.state == State.FAIL or verbose:
                print(
                    f"  Column present in both files:                 {self.column_in_both_files.output()}{column_in_both_files_info}"
                )

            if self.valid_column_datatypes:
                valid_column_datatypes_info = (
                    f"\n     {ANSI.RED} → {self.valid_column_datatypes.message}.{ANSI.RESET}"
                    if self.valid_column_datatypes.state == State.FAIL
                    else ""
                )
                if self.valid_column_datatypes.state == State.FAIL or verbose:
                    print(
                        f"  Valid column datatype:                        {self.valid_column_datatypes.output()} {valid_column_datatypes_info}"
                    )

            if self.valid_column_ranges:
                valid_column_ranges_info = (
                    f"\n     {ANSI.RED} → {self.valid_column_ranges.message}.{ANSI.RESET}"
                    if self.valid_column_ranges.state == State.FAIL
                    else ""
                )
                if self.valid_column_ranges.state == State.FAIL or verbose:
                    print(
                        f"  Valid column range:                           {self.valid_column_ranges.output()} {valid_column_ranges_info}"
                    )

            print(f"{'-' * 80}")


def validate_data_and_metadata(
    table_name: str,
    data: pl.LazyFrame,
    metadata: MamlMetaData,
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
        in_both_files = Status(State.PASS)
        valid_range = None
        valid_datatype = None

        if column_name in data_column_names and column_name in metadata_column_names:
            in_both_files = Status(State.PASS)
            if metadata_columns.columns[column_name].qc:
                valid_range = _compare_column_range(
                    column_name, data, metadata_columns.columns
                )
            else:
                valid_range = Status(State.PASS)
            valid_datatype = _compare_column_type(
                column_name, data, metadata_columns.columns
            )

            column_reports.append(
                DataMetadataValueReport(
                    column_name, in_both_files, valid_datatype, valid_range
                )
            )
        elif column_name in data_column_names:
            in_both_files = Status(
                State.FAIL,
                f"{column_name} found in {table_name}.parquet but not in {table_name}.maml",
            )
            column_reports.append(
                DataMetadataValueReport(
                    column_name, in_both_files, valid_datatype, valid_range
                )
            )
        else:  # column_name in metadata_column_names only
            in_both_files = Status(
                State.FAIL,
                f"{column_name} found in {table_name}.maml but not in {table_name}.parquet",
            )
            column_reports.append(
                DataMetadataValueReport(
                    column_name, in_both_files, valid_datatype, valid_range
                )
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
        lf, data_report, name_reports = read_and_validate_parquet(
            directory / f"{file}.parquet", quiet, verbose, return_reports=True
        )
        if data_report.valid == State.FAIL:
            final_state = State.FAIL
        for column_report in name_reports:
            if column_report.valid == State.FAIL:
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
                    if report.valid == State.FAIL:
                        final_state = State.FAIL
    return final_state
