"""
Module to handle validating the data in the parquet file.
"""

from dataclasses import dataclass
import os
from pathlib import Path
import polars as pl
from typing import ClassVar


from .status import Status
from .WAVES_config import ClosedInterval, ANSI
from .helper_validator_methods import (
    check_column_range,
)
from .report import Report
from .column_name_validator import validate_table_name, validate_field_names


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
        return Status.passed()
    valid = check_column_range(lazy_frame, ra_column_name, 0, 360, ClosedInterval.LEFT)
    if valid:
        return Status.passed()
    return Status.failed(f"{ra_column_name} not in range [0, 360)")


def check_dec(lazy_frame: pl.LazyFrame, dec_column_name=None) -> Status:
    """
    Checks that the dec column is correct if it exists.
    """
    if not dec_column_name:
        dec_column_name = find_column("dec", lazy_frame)
    if not dec_column_name:
        return Status.passed()
    valid = check_column_range(
        lazy_frame, dec_column_name, -90, 90, ClosedInterval.BOTH
    )
    if valid:
        return Status.passed()
    return Status.failed(f"{dec_column_name} not in range [-90, 90]")


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
        return Status.passed()

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
        return Status.passed()
    return Status.failed(",".join(bad_columns))


@dataclass
class DataValueReport(Report):
    valid_table_name: Status
    valid_column_name: Status
    valid_ra: Status
    valid_dec: Status
    no_999: Status

    TITLE: ClassVar[str] = "Parquet Validation Report"
    CHECK_LABELS: ClassVar[dict[str, str]] = {
        "valid_table_name": "Valid table name:",
        "valid_column_name": "Valid column names:",
        "valid_ra": "Valid Right Ascension column:",
        "valid_dec": "Valid Declination column:",
        "no_999": "No illegal Nones (-999 check):",
    }


def check_table(lf: pl.LazyFrame, table_name: Path) -> DataValueReport:
    """
    Performs all the data validation checks on the given table.
    """
    table_name_valid = validate_table_name(table_name)
    column_names = lf.collect_schema().names()
    column_name_valid = validate_field_names(column_names)
    ra_valid = check_ra(lf)
    dec_valid = check_dec(lf)
    no_999 = check_no_minus_999(lf)
    return DataValueReport(
        table_name_valid,
        column_name_valid,
        ra_valid,
        dec_valid,
        no_999,
    )


def read_and_validate_parquet(
    file_name: Path,
    quiet: bool = False,
    verbose: bool = False,
    return_reports: bool = False,
) -> pl.LazyFrame | tuple[pl.LazyFrame, DataValueReport] | None:
    """
    Validates the contents of a Parquet file, both the data and the column names.
    """
    if not os.path.isfile(file_name):
        print(f"{ANSI.BOLD}{ANSI.RED} File Not Found: {file_name}{ANSI.RESET}")
        return None
    lf = pl.scan_parquet(file_name)
    table_report = check_table(lf, file_name)

    if not quiet:
        table_report.print_report(verbose)
        print(f"{'=' * 80}")

    if return_reports:
        return lf, table_report

    return lf
