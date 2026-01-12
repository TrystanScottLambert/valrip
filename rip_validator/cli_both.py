import polars as pl
from .cli_parquet import _validate_parquet
from .metadata_validator import read_and_validate_maml
from .helper_validator_methods import print_header
from .data_and_metadata_validator import validate_data_and_metadata


def _validate_maml_and_parquet(file_name: str, quiet=False, verbose=False):
    """
    Performs the validation for a pair of MAML and Parquet files together.
    This involves validating both the MAML file and the Parquet
    file individually, before validating their consistency.
    """
    parquet_file = file_name + ".parquet"
    _validate_parquet(parquet_file, quiet, verbose)
    data = pl.read_parquet(parquet_file)

    maml_file = file_name + ".maml"
    maml = read_and_validate_maml(maml_file, quiet, verbose)

    if maml:
        if not quiet:
            print_header("Data and Metadata Column Consistency Validation Report")
        column_reports = validate_data_and_metadata(file_name, data, maml)

        if not quiet:
            for report in column_reports:
                report.print_report(verbose)

            print(f"{'=' * 80}")
