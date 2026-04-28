"""
Controller for the click command 'parquet'.
Separating into a separate file to limit import costs at runtime.
"""

from .data_validator import read_and_validate_parquet


def validate_parquet(file_name: str, quiet=False, verbose=False):
    """
    Does the overall validation for the parquet file.
    """
    read_and_validate_parquet(file_name, quiet, verbose)
