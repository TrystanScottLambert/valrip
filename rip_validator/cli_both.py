import polars as pl
from .cli_parquet import _validate_parquet
from .metadata_validator import read_and_validate_maml
from .helper_validator_methods import print_header
from .data_and_metadata_validator import validate_data_and_metadata


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
