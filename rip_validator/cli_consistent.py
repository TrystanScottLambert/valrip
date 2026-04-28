"""
Controller for the click command 'consistency'.
Separating into a separate file to limit import costs at runtime.
"""

from pathlib import Path
from .data_validator import read_and_validate_parquet
from .metadata_validator import read_and_validate_maml
from .data_and_metadata_validator import validate_data_and_metadata


def validate_maml_and_parquet(file_name: str, quiet=False, verbose=False):
    """
    Performs the validation for a pair of MAML and Parquet files together.
    This involves validating both the MAML file and the Parquet
    file individually, before validating their consistency.
    """
    parquet_file = Path(file_name + ".parquet")
    data = read_and_validate_parquet(parquet_file, quiet, verbose)

    maml_file = Path(file_name + ".maml")
    maml = read_and_validate_maml(maml_file, quiet, verbose)

    if maml:
        validate_data_and_metadata(file_name, data, maml, quiet, verbose)
