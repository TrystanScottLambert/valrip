"""
Module to handle validating the data in the parquet file.
"""

from dataclasses import dataclass
import polars as pl
from polars.exceptions import InvalidOperationError

from .status import Status, State, output_state
from .data_types import ClosedInterval, ANSI
from .helper_validator_methods import (
    WHITESPACE_PADDING_LENGTH,
    check_column_range,
    print_header,
)


def _find_column(standard_root_name: str, data_frame: pl.DataFrame) -> str | None:
    """
    Attempts to find the column name that matches the root name.
    e.g. 'ra' would be the root name and a column called ra_j2000 would be
    identified as the ra column.

    Assumes columns are in snake_case.
    """
    for column_name in data_frame.columns:
        for word in column_name.split("_"):
            if word == standard_root_name:
                return column_name
    return None


def validate_ra(data_frame: pl.DataFrame, ra_column_name=None) -> Status:
    """
    Checks that the ra column is correct if it exists.
    """
    if not ra_column_name:
        ra_column_name = _find_column("ra", data_frame)
    if not ra_column_name:
        return Status(State.PASS)
    valid = check_column_range(data_frame, ra_column_name, 0, 360, ClosedInterval.LEFT)
    if valid:
        return Status(State.PASS, f"{ra_column_name} in range [0, 360)")
    return Status(State.FAIL, f"{ra_column_name} not in range [0, 360)")


def validate_dec(data_frame: pl.DataFrame, dec_column_name=None) -> Status:
    """
    Checks that the dec column is correct if it exists.
    """
    if not dec_column_name:
        dec_column_name = _find_column("dec", data_frame)
    if not dec_column_name:
        return Status(State.PASS)
    valid = check_column_range(
        data_frame, dec_column_name, -90, 90, ClosedInterval.BOTH
    )
    if valid:
        return Status(State.PASS, f"{dec_column_name} in range [-90, 90]")
    return Status(State.FAIL, f"{dec_column_name} not in range [-90, 90]")


def check_no_minus_999(data_frame: pl.DataFrame) -> Status:
    """
    Checks that there are no -999 values anywhere in the table.

    True => There aren't any.
    False => There are.

    Also returns a list of all columns that do have -999 value in them.
    """
    valid = True
    bad_columns = []
    for column in data_frame:
        try:
            if -999 in column:
                valid = False
                bad_columns.append(column.name)
        except InvalidOperationError:
            pass

        try:
            if "-999" in column:
                valid = False
                bad_columns.append(column.name)
        except InvalidOperationError:
            pass
    if len(bad_columns) == 0:
        bad_columns = None
    if valid:
        return Status(State.PASS)
    return Status(
        State.FAIL, ",".join(bad_columns)
    )  


@dataclass
class DataValueReport:
    table_name: str
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
                bad_columns = self.no_999.message.split(
                    ","
                )
                for column_name in bad_columns:
                    no_999_info += f"\n      {ANSI.RED} → Column '{column_name}' has -999 values. Using -999 as a None value is not permited.{ANSI.RESET}"

            if self.no_999.state != State.PASS or verbose:
                print(
                    f"{'  No illegal Nones (-999 check): '.ljust(WHITESPACE_PADDING_LENGTH)}{self.no_999.output()}{no_999_info}"
                )


def validate_table(df: pl.DataFrame, table_name: str) -> DataValueReport:
    """
    Performs all the data validation checks on the given table.
    """
    ra_valid = validate_ra(df)
    dec_valid = validate_dec(df)
    no_999 = check_no_minus_999(df)
    return DataValueReport(
        table_name,
        ra_valid,
        dec_valid,
        no_999,
    )
