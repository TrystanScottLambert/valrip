import polars as pl
from pydantic_core import PydanticCustomError

from .data_types import ANSI, ClosedInterval, WAVESCustomExceptions

WHITESPACE_PADDING_LENGTH = 71


def check_data_type(polars_dtype: pl.DataType, waves_type: str) -> bool:
    return str(polars_dtype).lower() == waves_type.lower()


def check_column_range(
    data_frame: pl.DataFrame,
    column_name: str,
    min: float,
    max: float,
    include: ClosedInterval,
) -> bool:
    """
    Determines if a given column name is between the min max values assuming [min, max].
    Interval closed or open can be handled with the ClosedInterval enum.
    """
    contained = data_frame.select(
        pl.col(column_name).is_between(min, max, closed=include.value).all()
    ).item()
    return contained


def print_header(heading):
    """
    Prints a consistently-styled header.
    :param heading: Heading to print
    """
    print(f"\n{ANSI.BOLD}{'=' * 80}{ANSI.RESET}")
    print(f"{ANSI.BOLD}{heading}{ANSI.RESET}")
    print(f"{ANSI.BOLD}{'=' * 80}{ANSI.RESET}")


def raise_waves_list_error(error_message: str):
    """
    Raises a consistent error type when list values are incorrect.
    pydantic's handling of exceptions inside lists is not adqeuate, so we
    implement a custom validation and exception type to handle those use cases.
    """
    raise PydanticCustomError(
        WAVESCustomExceptions.LIST_EXCEPTION,
        error_message,
    )


def raise_waves_missing_error():
    """
    Raises a consistent error type when values are missing.
    This is required because pydantic doesn't treat empty strings as missing values,
    so we implement custom validation for empty strings.
    """
    raise PydanticCustomError(
        WAVESCustomExceptions.MISSING_EXCEPTION,
        "Field required",
    )


def format_waves_error_message(location: str, error_message: str):
    """
    :param location: The location (field with subfields if there are any) where the error occurs
    :type location: str
    :param error_message: The error message
    :type error_message: str
    """
    message = ""
    if location:
        message += f"{location}\n{ANSI.RED}→ {error_message}{ANSI.RESET}"
    else:
        message = f"{ANSI.RED}→ {error_message}{ANSI.RESET}"
    return message


def format_error_and_location(
    field: str | None,
    field_input: str | None,
    field_index: int | None,
    submodel_field: str | None,
    submodel_field_input: str | None,
    error_message: str,
):
    """
    :param field: The incorrect field
    :type field: str | None
    :param field_name: The input of the incorrect field - this should be the name if the element has one
    :type field_name: str | None
    :param field_index: The index of the incorrect field (if it is in a list)
    :type field_index: int | None
    :param submodel_field: The incorrect submodel field (if the error is in a submodel field)
    :type submodel_field: str | None
    :param submodel_field_input: The input of the incorrect submodel field
    :type submodel_field_input: str | None
    :param error_message: The error message
    :type error_message: str
    """
    # 1-based indexing is more intuitive for our output
    if field_index is not None:
        field_index += 1

    location_str = f"  > {field}"
    if field_input:
        if field_index is not None:
            location_str += f" ({field_input}, element {field_index})"
        else:
            location_str += f" ({field_input}"
    elif field_index is not None:
        location_str += f" (element {field_index})"

    if submodel_field:
        location_str += f"\n    > {submodel_field}"
        if submodel_field_input:
            location_str += f" ({submodel_field_input})"
        location_str += f"\n    {ANSI.RED}→ {error_message}{ANSI.RESET}"
    else:
        location_str += f"\n    {ANSI.RED}→ {error_message}{ANSI.RESET}"

    return location_str + "\n"
