"""
Module which combines the reports from the various validations
"""

import click
from pathlib import Path
from .version_control import Version

version = Version()


@click.group()
@click.version_option(version=version.version_call(), package_name="valrip")
def cli():
    version.check_version()
    pass


@click.command(name="parquet")
@click.argument(
    "file_name", type=click.Path(exists=True, dir_okay=False, path_type=Path)
)
@click.option(
    "--quiet",
    "-q",
    default=False,
    is_flag=True,
    help="Boolean flag that indicates whether to run in quiet mode, or not.",
)
@click.option(
    "--verbose",
    "-v",
    default=False,
    is_flag=True,
    help="Boolean flag that indicates whether to print all output even when it might not be useful, or not.",
)
def validate_parquet(file_name: str, quiet=False, verbose=False):
    """
    Does the overall validation for the parquet file.
    """
    from .cli_parquet import validate_parquet

    return validate_parquet(file_name, quiet, verbose)


@click.command(name="maml")
@click.argument(
    "file_name",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
)
@click.option(
    "--quiet",
    "-q",
    default=False,
    is_flag=True,
    help="Boolean flag that indicates whether to run in quiet mode, or not.",
)
@click.option(
    "--verbose",
    "-v",
    default=False,
    is_flag=True,
    help="Boolean flag that indicates whether to print all output even when it might not be useful, or not.",
)
def validate_maml(file_name: Path, quiet=False, verbose=False):
    """
    Does the overall validation for the MAML file.
    """
    from .cli_maml import validate_maml

    validate_maml(file_name, quiet, verbose)


@click.command(name="consistent")
@click.argument("file_name")
@click.option(
    "--quiet",
    "-q",
    default=False,
    is_flag=True,
    help="Boolean flag that indicates whether to run in quiet mode, or not.",
)
@click.option(
    "--verbose",
    "-v",
    default=False,
    is_flag=True,
    help="Boolean flag that indicates whether to print all output even when it might not be useful, or not.",
)
def validate_maml_and_parquet(file_name: str, quiet=False, verbose=False):
    """
    Performs the validation for a pair of MAML and Parquet files together.
    This involves validating both the MAML file and the Parquet
    file individually, before validating their consistency.
    """
    from .cli_consistent import validate_maml_and_parquet

    validate_maml_and_parquet(file_name, quiet, verbose)


@click.command(name="gen-maml")
@click.argument(
    "parquet_file_name", type=click.Path(exists=True, dir_okay=False, path_type=Path)
)
def gen_maml(parquet_file_name: Path):
    """
    Generates a skeletal-MAML from the provided Parquet file.
    """

    from .cli_generate import make_maml

    make_maml(parquet_file_name)


@click.command(name="submit")
@click.argument("pre_rip_name")
def submit(pre_rip_name: str):
    """
    Submits the provided pre-rip to the QC process.
    """
    from .cli_submit import submit

    submit(pre_rip_name)


@click.group(name="login")
def login():
    """Store credentials in the system keyring."""
    pass


@login.command(name="gitlab")
@click.option("--user", "-u", is_flag=True, help="Set the GitLab username.")
@click.option("--email", "-e", is_flag=True, help="Set the GitLab email.")
@click.option("--token", "-t", is_flag=True, help="Set the WAVES git-bot token.")
@click.option(
    "--all", "-a", "all_creds", is_flag=True, help="Set all GitLab credentials."
)
def login_gitlab(user, email, token, all_creds):
    """Store GitLab credentials."""
    from .store_credentials import login_gitlab

    login_gitlab(user, email, token, all_creds)


@login.command(name="owncloud")
@click.option("--user", "-u", is_flag=True, help="Set the Data Central username.")
@click.option("--password", "-p", is_flag=True, help="Set the Data Central password.")
@click.option(
    "--all", "-a", "all_creds", is_flag=True, help="Set all Data Central credentials."
)
def login_owncloud(user, password, all_creds):
    """Store DataCentral OwnCloud credentials."""
    from .store_credentials import login_owncloud

    login_owncloud(user, password, all_creds)


@click.command(name="directory")
@click.argument(
    "directory",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
)
@click.option(
    "--quiet",
    "-q",
    default=False,
    is_flag=True,
    help="Boolean flag that indicates whether to run in quiet mode, or not.",
)
@click.option(
    "--verbose",
    "-v",
    default=False,
    is_flag=True,
    help="Boolean flag that indicates whether to print all output even when it might not be useful, or not.",
)
def validate_directory(directory: Path, quiet=False, verbose=False):
    """
    Performs RIP-level validation on an entire directory.
    Checks file consistency (maml/parquet pairs, markdown notes, extra files),
    dataset name consistency across mamls, and runs the combined maml+parquet
    validation on every pair.
    """
    from .cli_directory import validate_directory

    validate_directory(directory, quiet, verbose)


cli.add_command(validate_maml)
cli.add_command(validate_parquet)
cli.add_command(validate_maml_and_parquet)
cli.add_command(gen_maml)
cli.add_command(submit)
cli.add_command(login)
cli.add_command(validate_directory)
