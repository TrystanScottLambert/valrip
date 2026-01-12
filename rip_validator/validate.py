"""
Module which combines the reports from the various validations
"""

import click


@click.group()
def cli():
    pass


@click.command(name="parquet")
@click.argument("file_name")
@click.option(
    "--quiet", "-q",
    default=False,
    is_flag=True,
    help="Boolean flag that indicates whether to run in quiet mode, or not.",
)
@click.option(
    "--verbose", "-v",
    default=False,
    is_flag=True,
    help="Boolean flag that indicates whether to print all output even when it might not be useful, or not.",
)
def validate_parquet(file_name: str, quiet=False, verbose=False):
    """
    Does the overall validation for the parquet file.
    """
    from .cli_parquet import _validate_parquet

    return _validate_parquet(file_name, quiet, verbose)


@click.command(name="maml")
@click.argument("file_name")
@click.option(
    "--quiet", "-q",
    default=False,
    is_flag=True,
    help="Boolean flag that indicates whether to run in quiet mode, or not.",
)
@click.option(
    "--verbose", "-v",
    default=False,
    is_flag=True,
    help="Boolean flag that indicates whether to print all output even when it might not be useful, or not.",
)
def validate_maml(file_name: str, quiet=False, verbose=False):
    """
    Does the overall validation for the MAML file.
    """
    from .cli_maml import _validate_maml

    _validate_maml(file_name, quiet, verbose)


@click.command(name="both")
@click.argument("file_name")
@click.option(
    "--quiet", "-q",
    default=False,
    is_flag=True,
    help="Boolean flag that indicates whether to run in quiet mode, or not.",
)
@click.option(
    "--verbose", "-v",
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
    from .cli_both import _validate_maml_and_parquet

    _validate_maml_and_parquet(file_name, quiet, verbose)


@click.command(name="generate")
@click.argument("parquet_file_name")
def gen_maml(parquet_file_name: str):
    """
    Generates a skeletal-MAML from the provided Parquet file.
    """

    from .cli_generate import make_maml

    make_maml(parquet_file_name)


cli.add_command(validate_maml)
cli.add_command(validate_parquet)
cli.add_command(validate_maml_and_parquet)
cli.add_command(gen_maml)
