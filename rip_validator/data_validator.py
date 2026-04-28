"""
Module to handle validating the data in the parquet file.
"""

from dataclasses import dataclass
import os
from pathlib import Path
import polars as pl


from .status import Status, State, output_state
from .WAVES_config import ClosedInterval, ANSI
from .helper_validator_methods import (
    WHITESPACE_PADDING_LENGTH,
    check_column_range,
    print_header,
)
from .column_name_validator import ColumnNameReport, get_column_name_report


def find_column(standard_root_name: str, lazy_frame: pl.LazyFrame) -> str | None:
    """
    Attempts to find the column name that matches the root name.
    e.g. 'ra' would be the root name and a column called ra_j2000 would be
    identified as the ra column.

    Assumes columns are in snake_case.
    """
    for column_name in lazy_frame.collect_schema().names():
        for word in column_name.split("_"):
            if word == standard_root_name:
                return column_name
    return None


def check_ra(lazy_frame: pl.LazyFrame, ra_column_name=None) -> Status:
    """
    Checks that the ra column is correct if it exists.
    """
    if not ra_column_name:
        ra_column_name = find_column("ra", lazy_frame)
    if not ra_column_name:
        return Status(State.PASS)
    valid = check_column_range(lazy_frame, ra_column_name, 0, 360, ClosedInterval.LEFT)
    if valid:
        return Status(State.PASS, f"{ra_column_name} in range [0, 360)")
    return Status(State.FAIL, f"{ra_column_name} not in range [0, 360)")


def check_dec(lazy_frame: pl.LazyFrame, dec_column_name=None) -> Status:
    """
    Checks that the dec column is correct if it exists.
    """
    if not dec_column_name:
        dec_column_name = find_column("dec", lazy_frame)
    if not dec_column_name:
        return Status(State.PASS)
    valid = check_column_range(
        lazy_frame, dec_column_name, -90, 90, ClosedInterval.BOTH
    )
    if valid:
        return Status(State.PASS, f"{dec_column_name} in range [-90, 90]")
    return Status(State.FAIL, f"{dec_column_name} not in range [-90, 90]")


def check_no_minus_999(data_frame: pl.LazyFrame, batch_size: int = 10) -> Status:
    """
    Checks that there are no -999 values anywhere in the table.
    Processed in batches to bound peak memory on wide tables.
    """
    schema = data_frame.collect_schema()

    # Only numeric and string columns can contain -999
    checkable = [
        (name, dtype)
        for name, dtype in schema.items()
        if dtype.is_numeric() or dtype == pl.String
    ]

    if not checkable:
        return Status(State.PASS)

    bad_columns = []
    for i in range(0, len(checkable), batch_size):  # Batching to reduce memory
        batch = checkable[i : i + batch_size]
        exprs = [
            (pl.col(name) == (-999 if dtype.is_numeric() else "-999")).any().alias(name)
            for name, dtype in batch
        ]
        result = data_frame.select(exprs).collect().row(0, named=True)
        bad_columns.extend(name for name, has_bad in result.items() if has_bad)

    if not bad_columns:
        return Status(State.PASS)
    return Status(State.FAIL, ",".join(bad_columns))


@dataclass
class DataValueReport:
    table_name: Path
    valid_ra: Status
    valid_dec: Status
    no_999: Status

    def __post_init__(self) -> None:
        self.valid = State.PASS
        if any(
            [
                self.valid_ra.state == State.WARNING,
                self.valid_dec.state == State.WARNING,
                self.no_999.state == State.WARNING,
            ]
        ):
            self.valid = State.WARNING
        if any(
            [
                self.valid_ra.state == State.FAIL,
                self.valid_dec.state == State.FAIL,
                self.no_999.state == State.FAIL,
            ]
        ):
            self.valid = State.FAIL

    def print_report(self, verbose=False) -> None:
        """
        Print a professional validation report with color-coded results.
        """

        print_header("Table Data Validation Report")

        # Overall status
        overall_color = ANSI.GREEN if self.valid else ANSI.RED
        print(
            f"\n{ANSI.BOLD}Table:{ANSI.RESET} {self.table_name} | {ANSI.BOLD}Overall Status:{ANSI.RESET} {overall_color}{output_state(self.valid)}{ANSI.RESET}"
        )

        if self.valid != State.PASS or verbose:
            print(f"\n{ANSI.BOLD}Validation Checks:{ANSI.RESET}")
            print(f"{'-' * 80}")

            valid_ra_info = (
                f"\n     {ANSI.RED} → {self.valid_ra.message}.{ANSI.RESET}"
                if self.valid_ra.state != State.PASS
                else ""
            )
            if self.valid_ra.state != State.PASS or verbose:
                print(
                    f"{'  Valid Right Ascension column: '.ljust(WHITESPACE_PADDING_LENGTH)}{self.valid_ra.output()}{valid_ra_info}"
                )

            valid_dec_info = (
                f"\n     {ANSI.RED} → {self.valid_dec.message}.{ANSI.RESET}"
                if self.valid_dec.state != State.PASS
                else ""
            )
            if self.valid_dec.state != State.PASS or verbose:
                print(
                    f"{'  Valid Declination column: '.ljust(WHITESPACE_PADDING_LENGTH)}{self.valid_dec.output()}{valid_dec_info}"
                )

            no_999_info = ""
            if self.no_999.state != State.PASS and self.no_999.message:
                bad_columns = self.no_999.message.split(",")
                for column_name in bad_columns:
                    no_999_info += f"\n      {ANSI.RED} → Column '{column_name}' has -999 values. Using -999 as a None value is not permited.{ANSI.RESET}"

            if self.no_999.state != State.PASS or verbose:
                print(
                    f"{'  No illegal Nones (-999 check): '.ljust(WHITESPACE_PADDING_LENGTH)}{self.no_999.output()}{no_999_info}"
                )


def check_table(lf: pl.LazyFrame, table_name: Path) -> DataValueReport:
    """
    Performs all the data validation checks on the given table.
    """
    ra_valid = check_ra(lf)
    dec_valid = check_dec(lf)
    no_999 = check_no_minus_999(lf)
    return DataValueReport(
        table_name,
        ra_valid,
        dec_valid,
        no_999,
    )


def read_and_validate_parquet(
    file_name: Path,
    quiet: bool = False,
    verbose: bool = False,
    return_reports: bool = False,
) -> pl.LazyFrame | tuple[pl.LazyFrame, DataValueReport, list[ColumnNameReport]]:
    """
    Validates the contents of a Parquet file, both the data and the column names.
    """
    if not os.path.isfile(file_name):
        print(f"{ANSI.BOLD}{ANSI.RED} File Not Found: {file_name}{ANSI.RESET}")
        return None
    lf = pl.scan_parquet(file_name)
    table_report = check_table(lf, file_name)

    column_names = lf.collect_schema().names()
    column_reports = [
        get_column_name_report(column_name) for column_name in column_names
    ]

    if not quiet:
        table_report.print_report(verbose)
        print_header("Column Name Validation Report")

        for report in column_reports:
            report.print_report(verbose)

        print(f"{'=' * 80}")

    if return_reports:
        return lf, table_report, column_reports

    return lf
