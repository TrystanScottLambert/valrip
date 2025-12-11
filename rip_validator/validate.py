"""
Module which combines the reports from the various validations
"""

from dataclasses import dataclass

import polars as pl
import click

from .helper_validator_methods import print_header
from .data_validator import validate_table
from .column_name_validator import validate_column_name
from .metadata_validator import read_and_validate_maml
from .data_and_metadata_validator import validate_data_and_metadata


@dataclass
class DataValidationReport:
    valid_data: bool
    valid_column_names: bool


@dataclass
class DataMetadataValidationReport:
    valid_metadata: bool
    valid_column_names: bool


def validate_df(
    df: pl.DataFrame, name_of_table: str, print_output=True, verbose=False
) -> DataValidationReport:
    """
    Validates a data frame both the data and the column names.
    """
    table_report = validate_table(df, name_of_table)

    column_names = df.columns
    column_reports = [validate_column_name(column_name) for column_name in column_names]

    # Check if all column names are valid
    names_valid = all(report.valid for report in column_reports)

    if print_output:
        table_report.print_report(verbose)
        print_header("Column Name Validation Report")

        for report in column_reports:
            report.print_report(verbose)

        print(f"{'=' * 80}")

    return DataValidationReport(table_report.valid, names_valid)


@click.group()
def cli():
    pass


@click.command(name="parquet")
@click.argument("file_name")
@click.option(
    "--print_output",
    default=True,
    help="Boolean flag that indicates whether to print the output or not.",
)
@click.option(
    "--verbose",
    default=False,
    help="Boolean flag that indicates whether to print all output even when it might not be useful, ot not.",
)
def validate_parquet(
    file_name: str, print_output=True, verbose=False
) -> DataValidationReport:
    """
    Does the overall validation for the parquet file.
    """
    return _validate_parquet(file_name, print_output, verbose)


def _validate_parquet(
    file_name: str, print_output=True, verbose=False
) -> DataValidationReport:
    """
    Does the overall validation for the parquet file.
    """
    df = pl.read_parquet(file_name)
    return validate_df(df, file_name, print_output, verbose)


@click.command(name="maml")
@click.argument("file_name")
@click.option(
    "--print_output",
    default=True,
    is_flag=True,
    help="Boolean flag that indicates whether to print the output or not.",
)
@click.option(
    "--verbose",
    default=False,
    is_flag=True,
    help="Boolean flag that indicates whether to print all output even when it might not be useful, ot not.",
)
def validate_maml(file_name: str, print_output=True, verbose=False):
    """
    Does the overall validation for the MAML file.
    """
    _validate_maml(file_name, print_output, verbose)


def _validate_maml(file_name: str, print_output=True, verbose=False):
    """
    Does the overall validation for the MAML file.
    """
    read_and_validate_maml(file_name, print_output, verbose)


@click.command(name="both")
@click.argument("file_name")
@click.option(
    "--print_output",
    default=True,
    is_flag=True,
    help="Boolean flag that indicates whether to print the output or not.",
)
@click.option(
    "--verbose",
    default=False,
    is_flag=True,
    help="Boolean flag that indicates whether to print all output even when it might not be useful, ot not.",
)
def validate_maml_and_parquet(file_name: str, print_output=True, verbose=False):
    """
    Performs the validation for a pair of MAML and Parquet files together.
    This involves validating both the MAML file and the Parquet
    file individually, before validating their consistency.
    """
    _validate_maml_and_parquet(file_name, print_output, verbose)


def _validate_maml_and_parquet(file_name: str, print_output=True, verbose=False):
    """
    Performs the validation for a pair of MAML and Parquet files together.
    This involves validating both the MAML file and the Parquet
    file individually, before validating their consistency.
    """
    parquet_file = file_name + ".parquet"
    _validate_parquet(parquet_file, print_output, verbose)
    data = pl.read_parquet(parquet_file)

    maml_file = file_name + ".maml"
    maml = read_and_validate_maml(maml_file, print_output, verbose)

    if maml:
        if print_output:
            print_header("Data and Metadata Column Consistency Validation Report")
        column_reports = validate_data_and_metadata(file_name, data, maml)

        if print_output:
            for report in column_reports:
                report.print_report(verbose)

            print(f"{'=' * 80}")


cli.add_command(validate_maml)
cli.add_command(validate_parquet)
cli.add_command(validate_maml_and_parquet)
