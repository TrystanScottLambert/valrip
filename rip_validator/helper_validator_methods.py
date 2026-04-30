import datetime
import functools
import inspect
import typing

import polars as pl
from email_validator import EmailNotValidError, validate_email

from .status import Status
from .WAVES_config import (
    ANSI,
    EMAIL_REGEX,
    ClosedInterval,
    License,
    SurveyName,
)

WHITESPACE_PADDING_LENGTH = 71


def requires_not_none(field_param: str):
    """Decorator that checks a named parameter is not None before running validation."""

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            sig = inspect.signature(func)
            bound = sig.bind(*args, **kwargs)
            bound.apply_defaults()
            value = bound.arguments.get(field_param)

            if value is None:
                return Status.failed(
                    f"'{field_param}' is missing or empty and is a required field."
                )
            return func(*args, **kwargs)

        return wrapper

    return decorator


def requires_type(field_param: str):
    """Decorator that checks a named parameter matches its annotated type before running validation."""

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            sig = inspect.signature(func)
            bound = sig.bind(*args, **kwargs)
            bound.apply_defaults()
            value = bound.arguments.get(field_param)

            # Get the expected type from the type hint
            hints = typing.get_type_hints(func)
            expected_type = hints.get(field_param)

            if expected_type is not None and not isinstance(value, expected_type):
                return Status.failed(
                    f"'{field_param}' must be of type {expected_type.__name__}, "
                    f"got {type(value).__name__}.",
                )
            return func(*args, **kwargs)

        return wrapper

    return decorator


def optional_list(field_param: str):
    """Decorator that checks a named parameter is not an empty list, but can be None."""

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            sig = inspect.signature(func)
            bound = sig.bind(*args, **kwargs)
            bound.apply_defaults()
            value = bound.arguments.get(field_param)

            if value is None:
                return Status.passed()
            if not isinstance(value, list):
                return Status.failed(
                    f"'{field_param}' must be a list, got {type(value).__name__}."
                )
            if len(value) == 0:
                return Status.failed(f"{field_param} is present but empty.")

            return func(*args, **kwargs)

        return wrapper

    return decorator


def is_blank(value) -> bool:
    """An optional value counts as 'blank' if it's None, an
    empty string, or an empty container. Used so the same rule applies to
    nested optionals (e.g. qc) as to top-level optionals."""
    return value is None or value == "" or value == [] or value == {}


def validate_empty_optionals(
    raw_yaml: dict | None, required_fields: list[str]
) -> Status:
    if raw_yaml is None:
        return Status.passed()
    empty = []
    for key, value in raw_yaml.items():
        if key in required_fields:
            continue  # handled by dedicated validator
        if is_blank(value):
            empty.append(key)
    if empty:
        return Status.failed(
            f"Optional field(s) {empty} are present but empty. Remove them or provide a value."
        )
    return Status.passed()


@requires_not_none("description")
@requires_type("description")
def validate_description(description: str) -> Status:
    return Status.passed()


@requires_not_none("survey")
@requires_type("survey")
def validate_survey(survey: str) -> Status:
    correct_names = [variant.value for variant in SurveyName]
    if survey not in correct_names:
        return Status.failed(
            f"'{survey}' is not a valid survey. Survey must be one of these: {correct_names}."
        )
    return Status.passed()


@requires_not_none("author")
@requires_type("author")
def validate_author(author: str) -> Status:
    match = EMAIL_REGEX.match(author)
    if not match:
        return Status.failed(
            f"'{author}' is not a valid author string. Author must be in the format 'Full Name <email@example.com>'.",
        )
    email = match.group("email")
    try:
        validate_email(email, check_deliverability=True)
    except Exception:
        try:
            validate_email(email, check_deliverability=False, dns_resolver=False)
        except EmailNotValidError as e:
            return Status.failed(f"'{email}' is not a valid email in '{author}'. {e}")
        return Status.warned(
            f"Deliverability of email address '{email}' could not be checked (no network or DNS unavailable)."
        )
    return Status.passed()


@optional_list("coauthors")
def validate_coauthors(coauthors: list[str] | None) -> Status:
    fail_messages = []
    warn_messages = []
    for author in coauthors:
        current = validate_author(author)
        if current.is_fail:
            fail_messages.append(f"'{author}': {current.message}")
        elif current.is_warn:
            warn_messages.append(f"'{author}': {current.message}")

    if fail_messages:
        if len(fail_messages) == 1:
            return Status.failed(fail_messages[0])
        return Status.failed(
            "The following coauthors are not valid:\n\t- "
            + "\n\t- ".join(fail_messages)
        )

    if warn_messages:
        if len(warn_messages) == 1:
            return Status.warned(warn_messages[0])
        return Status.warned(
            "Some coauthors had warnings:\n\t- " + "\n\t- ".join(warn_messages)
        )

    return Status.passed()


@requires_not_none("date")
@requires_type("date")
def validate_date(date: str) -> Status:
    try:
        datetime.date.fromisoformat(date)
    except ValueError:
        return Status.failed(f"'{date}' is not a valid isoformat.")
    return Status.passed()


@requires_not_none("license")
@requires_type("license")
def validate_license(license: str) -> Status:
    accepted_licenses = [variant.value for variant in License]
    if license not in accepted_licenses:
        return Status.failed(
            f"'{license}' is not an accepted license. License must be one of the following: {accepted_licenses}."
        )
    return Status.passed()


def validate_order(raw_yaml: dict | None, order_of_fields: list[str]) -> Status:
    if raw_yaml is None:
        return Status.passed()
    expected = [key for key in order_of_fields if key in raw_yaml]
    actual = [key for key in raw_yaml.keys() if key in order_of_fields]
    if expected != actual:
        return Status.failed(
            f"Fields are not in the correct order. Expected: {expected}. Got: {actual}."
        )
    return Status.passed()


def check_data_type(polars_dtype: pl.DataType, waves_type: str) -> bool:
    return str(polars_dtype).lower() == waves_type.lower()


def check_column_range(
    lazy_frame: pl.LazyFrame,
    column_name: str,
    min: float,
    max: float,
    include: ClosedInterval,
) -> bool:
    """
    Determines if a given column name is between the min max values assuming [min, max].
    Interval closed or open can be handled with the ClosedInterval enum.
    """
    contained = (
        lazy_frame.select(
            pl.col(column_name).is_between(min, max, closed=include.value).all()
        )
        .collect()
        .item()
    )
    return contained


def print_header(heading):
    """
    Prints a consistently-styled header.

    :param heading: Heading to print
    """
    print(f"\n{ANSI.BOLD}{'=' * 80}{ANSI.RESET}")
    print(f"{ANSI.BOLD}{heading}{ANSI.RESET}")
    print(f"{ANSI.BOLD}{'=' * 80}{ANSI.RESET}")
