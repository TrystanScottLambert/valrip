"""
All logic related to the click command 'parquet'.
Separating into a separate file to limit import costs at runtime.
"""

from dataclasses import dataclass
import polars as pl

from .data_validator import validate_table
from .helper_validator_methods import print_header

from .column_name_validator import validate_column_name


@dataclass
class DataValidationReport:
    valid_data: bool
    valid_column_names: bool


def validate_df(
    df: pl.DataFrame, name_of_table: str, quiet=False, verbose=False
) -> DataValidationReport:
    """
    Validates a data frame both the data and the column names.
    """
    table_report = validate_table(df, name_of_table)

    column_names = df.columns
    column_reports = [validate_column_name(column_name) for column_name in column_names]

    # Check if all column names are valid
    names_valid = all(report.valid for report in column_reports)

    if not quiet:
        table_report.print_report(verbose)
        print_header("Column Name Validation Report")

        for report in column_reports:
            report.print_report(verbose)

        print(f"{'=' * 80}")

    return DataValidationReport(table_report.valid, names_valid)


def _validate_parquet(
    file_name: str, quiet=False, verbose=False
) -> DataValidationReport:
    """
    Does the overall validation for the parquet file.
    """
    df = pl.read_parquet(file_name)
    return validate_df(df, file_name, quiet, verbose)
