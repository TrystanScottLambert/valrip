"""
Module for validating parquet data ensuring tables follow the style standards.
"""

from pathlib import Path
from thefuzz import fuzz

from .filter_check import check_filter
from .settings_config import (
    MAX_COLUMN_LENGTH,
    WARN_COLUMN_LENGTH,
    exceptions,
    filter_words,
    protected_words,
)
from .status import Messages, Status

NOT_ALLOWED = [
    "fred",
    "bob",
    "thing",
    "whatever",
    "words",
    "blahblahblah",
    "abc123",
    "xyz",
    "duff",
]


def check_length(name: str) -> Messages:
    """
    Checks that the lengths is less than the max length. Warns if more than 25.
    """
    messages = Messages()

    name_length = len(name)
    if name_length > MAX_COLUMN_LENGTH:
        messages.add_fail(f"Column name is too long ({len(name)}/{MAX_COLUMN_LENGTH})")
    elif name_length > WARN_COLUMN_LENGTH:
        messages.add_warning(
            f"This length is valid but long ({len(name)}/{MAX_COLUMN_LENGTH})"
        )

    return messages


def check_no_decimals(name: str) -> Messages:
    messages = Messages()
    if "." in name:
        messages.add_fail(f"No decimal points allowed, see {name}")
    return messages


def check_allowed(name: str) -> Messages:
    """
    Checks that the list of not allowed words isn't being used.
    """
    messages = Messages()

    fail_ratio = 85
    warning_ratio = 80
    # If the word is >85% similar then it fails. If it's less than 85 but greater than 80 it's a warning.
    for banned_word in NOT_ALLOWED:
        if banned_word in name:
            messages.add_fail(f"{banned_word} is banned.")
    # fuzzy searching:
    for banned_word in NOT_ALLOWED:
        for word in name.split("_"):
            ratio = fuzz.ratio(
                banned_word, word.lower()
            )  # This is how similar the word is to the banned word in percentage.
            if ratio > fail_ratio:
                messages.add_fail(f"{name} contains banned word: {banned_word}.")
            if ratio > warning_ratio:
                messages.add_warning(
                    f"{name} contains possible banned word: {banned_word}."
                )

    return messages


def check_protected(name: str) -> Messages:
    """
    Checks that protected names aren't being used in the tables.
    """
    messages = Messages()

    for protected_word in protected_words:
        for representation in protected_word.common_representations:
            if representation == name:
                messages.add_fail(f"Protected word in use, use: {protected_word.name}")
            for target_word in name.split("_"):
                if representation.lower() == target_word.lower():
                    messages.add_warning(
                        f"Protected word in use, did you mean: {protected_word.name}"
                    )
    return messages


def check_exceptions(name: str) -> Messages:
    """
    Checks that if the exceptions exist they are in the correct case.
    """
    messages = Messages()
    real_string = name.replace("_", "")
    for exc in exceptions:
        if exc.name.lower() in real_string.lower():
            if exc.name not in real_string:
                messages.add_fail(f"exception word {exc.name} is in incorrect case.")
    return messages


def check_alphabetical_start(name: str) -> Messages:
    """
    Checks that the string doesn't start with a number.
    """
    messages = Messages()
    if not name[0].isalpha():
        messages.add_fail(f"{name} does not start with a letter.")
    return messages


def check_snake_case(name: str) -> Messages:
    """
    Checks that the name is in snake_case excluding the filter names and the exceptions list, returns a list of errors
    """
    messages = Messages()

    if name.endswith("_"):
        messages.add_fail(f"{name} ends with an underscore.")
    if name.startswith("_"):
        messages.add_fail(f"{name} starts with an underscore.")
    if "__" in name:
        messages.add_fail(f"{name} has multiple underscores in a row.")
    actual_string = name
    for filter_name in filter_words:
        actual_string = actual_string.replace(filter_name.name, "")
    for exception in exceptions:
        actual_string = actual_string.replace(exception.name, "")

    if not actual_string.islower() and actual_string != "":
        messages.add_fail(
            f"{name} is not snake_case (should be all lowercase, except for known exceptions)."
        )
    no_underscores = name.replace("_", "")
    if not no_underscores.isalnum():
        messages.add_fail(f"{name} has non alpha-numeric characters.")

    return messages


def validate_table_name(name: Path) -> Status:
    """
    Checks that the table name is correct and returns a Status object
    """
    errors = []
    warnings = []

    # Get just the table name if the file name was passed in.
    no_file_extension = name.stem

    messages = check_alphabetical_start(no_file_extension)
    errors += messages.fail
    warnings += messages.warning

    messages = check_snake_case(no_file_extension)
    errors += messages.fail
    warnings += messages.warning

    messages = check_no_decimals(no_file_extension)
    errors += messages.fail
    warnings += messages.warning

    messages = check_exceptions(no_file_extension)
    errors += messages.fail
    warnings += messages.warning

    messages = check_protected(no_file_extension)
    errors += messages.fail
    warnings += messages.warning

    if errors and warnings:
        return Status.failed(
            f"'{name}' has the following errors:\n\t- {'\n\t- '.join(filter(None, errors))}\n\n '{name}' also has the following warnings:\n\t- {'\n\t- '.join(filter(None, warnings))}"
        )
    if errors:
        return Status.failed(
            f"'{name}' has the following errors:\n\t- {'\n\t- '.join(filter(None, errors))}"
        )
    if warnings:
        return Status.warned(
            f"'{name}' has the following warnings:\n\t- {'\n\t- '.join(filter(None, warnings))}"
        )
    return Status.passed()


def validate_field_names(names: str | list[str | None]) -> Status:
    """
    Checks that the field names are correct and returns a Status object
    """
    errors = []
    warnings = []

    for name in names:
        if name:
            messages = check_alphabetical_start(name)
            errors += messages.fail
            warnings += messages.warning

            messages = check_length(name)
            errors += messages.fail
            warnings += messages.warning

            messages = check_snake_case(name)
            errors += messages.fail
            warnings += messages.warning

            messages = check_no_decimals(name)
            errors += messages.fail
            warnings += messages.warning

            messages = check_filter(name)
            errors += messages.fail
            warnings += messages.warning

            messages = check_allowed(name)
            errors += messages.fail
            warnings += messages.warning

            messages = check_exceptions(name)
            errors += messages.fail
            warnings += messages.warning

            messages = check_protected(name)
            errors += messages.fail
            warnings += messages.warning

    fail_message = None
    if errors:
        fail_message = f"Found the following errors in the field names:\n\t- {'\n\t- '.join(filter(None, errors))}"

    warning_message = None
    if warnings:
        warning_message = f"Found the following warnings in the field names:\n\t- {'\n\t- '.join(filter(None, warnings))}"

    if fail_message:
        return Status.failed(fail_message, warning_message)

    if warning_message:
        return Status.warned(warning_message)

    return Status.passed()
