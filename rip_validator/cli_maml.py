"""
Logic for maml command
"""

from .metadata_validator import read_and_validate_maml


def _validate_maml(file_name: str, quiet=False, verbose=False):
    """
    Does the overall validation for the MAML file.
    """
    read_and_validate_maml(file_name, quiet, verbose)
