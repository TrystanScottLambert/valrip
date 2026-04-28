"""
Controller for the click command 'maml'.
Separating into a separate file to limit import costs at runtime.
"""

from pathlib import Path
from .metadata_validator import read_and_validate_maml


def validate_maml(file_name: Path, quiet=False, verbose=False):
    """
    Does the overall validation for the MAML file.
    """
    read_and_validate_maml(file_name, quiet, verbose)
