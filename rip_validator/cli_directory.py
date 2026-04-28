"""
Controller for the click command 'directory'.
Separating into a separate file to limit import costs at runtime.
"""

import os
from pathlib import Path

from rip_validator.status import State

from .daml import PreDAML
from .data_and_metadata_validator import consistency_state
from .internet_checker import is_connected
from .rip_level_validator import (
    build_submission_report,
    check_directory,
    read_in_maml,
)
from .WAVES_config import ANSI


def validate_directory(directory: Path, quiet=False, verbose=False):
    """
    Does the overall validation for the RIP directory.
    """
    if not is_connected():
        print(
            f"{ANSI.RED}{ANSI.BOLD}'valrip directory' requires an internet connection to check consistency with GitLab. You appear to be disconnected.{ANSI.RESET}"
        )
        return

    maml_data = read_in_maml(directory)
    consistent = consistency_state(directory, quiet, verbose)
    rip_name = directory.resolve().name

    report = check_directory(directory)
    report.print_report(verbose=verbose)
    daml_name = directory / f"{rip_name}.daml"
    daml_exists = os.path.exists(daml_name)

    if daml_exists:
        daml_report = PreDAML.from_file(daml_name).validate(rip_name, maml_data)
        daml_report.print_report(verbose=verbose)
        daml_valid = daml_report.is_valid
    else:
        daml_valid = True  # No need to check if daml doesn't exist yet

    if report.is_valid and consistent == State.PASS and daml_valid:
        if not daml_exists:
            PreDAML.from_maml_data(maml_data, rip_name).to_file(str(daml_name))
            print(
                f"\n{ANSI.GREEN}Directory has been validated successfully and DAML file has been built here: '{daml_name}'. {ANSI.RESET}{ANSI.BOLD}{ANSI.RED}Please add a description to the DAML file and then run 'valrip directory {directory}' again to finalise validation.{ANSI.RESET}"
            )
        else:
            build_submission_report(directory)
            print(
                f"\n{ANSI.BOLD}{ANSI.GREEN}Directory has been validated and can now be uploaded to the cloud space. Reports written to '{directory.resolve()}'.{ANSI.RESET}"
            )

    else:
        print(
            f"\n{ANSI.BOLD}{ANSI.RED}Directory has failed validation! Please see errors or run 'valrip directory --verbose {directory}'.{ANSI.RESET}"
        )
