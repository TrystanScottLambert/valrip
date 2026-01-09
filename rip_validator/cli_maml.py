"""
Logic for maml command
"""

from .metadata_validator import read_and_validate_maml


def _validate_maml(file_name: str, print_output=True, verbose=False):
    """
    Does the overall validation for the MAML file.
    """
    read_and_validate_maml(file_name, print_output, verbose)
