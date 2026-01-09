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
    "--print_output",
    default=True,
    is_flag=True,
    help="Boolean flag that indicates whether to print the output or not.",
)
@click.option(
    "--verbose",
    default=False,
    is_flag=True,
    help="Boolean flag that indicates whether to print all output even when it might not be useful, ot not.",
)
def validate_parquet(file_name: str, print_output=True, verbose=False):
    """
    Does the overall validation for the parquet file.
    """
    from .cli_parquet import _validate_parquet

    return _validate_parquet(file_name, print_output, verbose)


@click.command(name="maml")
@click.argument("file_name")
@click.option(
    "--print_output",
    default=True,
    is_flag=True,
    help="Boolean flag that indicates whether to print the output or not.",
)
@click.option(
    "--verbose",
    default=False,
    is_flag=True,
    help="Boolean flag that indicates whether to print all output even when it might not be useful, ot not.",
)
def validate_maml(file_name: str, print_output=True, verbose=False):
    """
    Does the overall validation for the MAML file.
    """
    from .cli_maml import _validate_maml

    _validate_maml(file_name, print_output, verbose)


@click.command(name="both")
@click.argument("file_name")
@click.option(
    "--print_output",
    default=True,
    is_flag=True,
    help="Boolean flag that indicates whether to print the output or not.",
)
@click.option(
    "--verbose",
    default=False,
    is_flag=True,
    help="Boolean flag that indicates whether to print all output even when it might not be useful, ot not.",
)
def validate_maml_and_parquet(file_name: str, print_output=True, verbose=False):
    """
    Performs the validation for a pair of MAML and Parquet files together.
    This involves validating both the MAML file and the Parquet
    file individually, before validating their consistency.
    """
    from .cli_both import _validate_maml_and_parquet

    _validate_maml_and_parquet(file_name, print_output, verbose)


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
