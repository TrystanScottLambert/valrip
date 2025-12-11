"""
Module for validating parquet data ensuring tables follow the style standards.
"""

from dataclasses import dataclass

from thefuzz import fuzz

from .filter_check import check_filter
from .status import Status, State
from .data_types import ANSI
from .config import (
    MAX_COLUMN_LENGTH,
    WARN_COLUMN_LENGTH,
    protected_words,
    filter_words,
    exceptions,
)

NOT_ALLOWED = [
    "fred",
    "bob",
    "thing",
    "something",
    "whatever",
    "words",
    "blahblahblah",
    "abc123",
    "xyz",
]


def check_length(name: str) -> Status:
    """
    Checks that the lengths is less than the max length. Warns if more than 25.
    """
    name_length = len(name)
    if name_length <= WARN_COLUMN_LENGTH:
        return Status(State.PASS)
    if name_length > MAX_COLUMN_LENGTH:
        return Status(State.FAIL)
    return Status(State.WARNING)


def check_decimals(name: str) -> Status:
    if "." not in name:
        return Status(State.PASS)
    return Status(State.FAIL)


def check_allowed(name: str) -> Status:
    """
    Checks that the list of not allowed words isn't being used.
    """
    for na in NOT_ALLOWED:
        if na in name:
            return Status(State.FAIL, na)
    # fuzzy searching:
    for na in NOT_ALLOWED:
        for word in name.split("_"):
            ratio = fuzz.ratio(na, word.lower())
            if ratio > 80:
                return Status(State.FAIL, f"{name} contains banned word: {na}")
            if ratio > 60:
                return Status(State.WARNING, f"{name} contains possible banned word: {na}")
    
    return Status(State.PASS)


def check_protected(name: str) -> Status:
    """
    Checks that protected names aren't being used in the tables.
    """
    for protected_word in protected_words:
        for word in protected_word.common_representations:
            if word == name:
                return Status(State.FAIL, protected_word.name)
            for target_word in name.split("_"):
                if word.lower() == target_word.lower():
                    return Status(State.WARNING, protected_word.name)
    return Status(State.PASS)


def check_exceptions(name: str) -> Status:
    """
    Checks that if the exceptions exist that they are in the correct case.
    """
    real_string = name.replace("_", "")
    for exc in exceptions:
        if exc.name.lower() in real_string.lower():
            if exc.name in real_string:
                return Status(State.PASS)
            return Status(State.FAIL, exc.name)
    return Status(State.PASS)


def check_alphanumeric(name: str) -> Status:
    """
    Checks that the given string is alpha numeric (excepting underscore)
    """
    no_underscores = name.replace("_", "")
    if no_underscores.isalnum():
        return Status(State.PASS)
    return Status(State.FAIL)


def check_alphabetical_start(name: str) -> Status:
    """
    Checks that the string doesn't start with a number.
    """
    if name[0].isalpha():
        return Status(State.PASS)
    return Status(State.FAIL)


def check_snake_case(name: str) -> Status:
    """
    Checks that the name is in snake case excluding the filter names and the exceptions list
    """
    if name.startswith("_"):
        return Status(State.FAIL, "Starts with underscore.")
    if name.endswith("_"):
        return Status(State.FAIL, "Ends with underscore.")
    if "__" in name:
        return Status(State.FAIL, "Multiple underscores in a row.")
    actual_string = name
    for filter_name in filter_words:
        actual_string = actual_string.replace(filter_name.name, "")
    for exception in exceptions:
        actual_string = actual_string.replace(exception.name, "")
    if actual_string == "":
        return Status(State.PASS)
    if actual_string.islower():
        if not check_alphanumeric(actual_string):
            return Status(State.FAIL)
        return Status(State.PASS)
    return Status(State.FAIL)


@dataclass
class ColumnNameReport:
    """
    Checks for given column name
    """

    column_name: str
    alpha_numeric: Status
    starts_with_letter: Status
    snake_case: Status  # taking into account filters and exceptions
    length: Status
    no_decimals: Status
    filter_name: Status
    allowed_words: Status
    no_exception_violation: Status
    not_protected: Status

    def __post_init__(self) -> None:
        self.valid: bool = all(
            [
                self.alpha_numeric.state == State.PASS,
                self.starts_with_letter.state == State.PASS,
                self.snake_case.state == State.PASS,
                self.length.state == State.PASS,
                self.no_decimals.state == State.PASS,
                self.filter_name.state == State.PASS,
                self.allowed_words.state == State.PASS,
                self.no_exception_violation.state == State.PASS,
                self.not_protected.state == State.PASS,
            ]
        )

    def print_report(self, verbose=False):
        """
        Print a professional validation report with color-coded results.
        """
        # Helper function for status
        def status(given_status: Status) -> str:
            match given_status.state:
                case State.PASS:
                    return f"{ANSI.GREEN}✓ PASS{ANSI.RESET}"
                case State.FAIL:
                    return f"{ANSI.RED}✗ FAIL{ANSI.RESET}"
                case State.WARNING:
                    return f"{ANSI.YELLOW}⚠ WARNING"

        # Overall column status
        overall_color = ANSI.GREEN if self.valid else ANSI.RED
        overall_status = "VALID" if self.valid else "INVALID"
        print(f"\n{ANSI.BOLD}Column:{ANSI.RESET} {self.column_name} | {ANSI.BOLD}Overall Status:{ANSI.RESET} {overall_color}{overall_status}{ANSI.RESET}")

        if not self.valid or verbose:
          print(f"\n{ANSI.BOLD}Validation Checks:{ANSI.RESET}")
          print(f"{'-' * 80}")

          if self.alpha_numeric.state == State.FAIL or verbose:
              print(
                  f"  Alphanumeric (letters, numbers, underscores): {status(self.alpha_numeric)}"
              )

          if self.starts_with_letter.state == State.FAIL or verbose:
              print(
                  f"  Starts with letter:                           {status(self.starts_with_letter)}"
              )

          if self.snake_case.state == State.FAIL or verbose:
              print(
                  f"  Snake case format:                            {status(self.snake_case)}"
              )

          length_status = status(self.length)
          length_info = ""
          if self.length.state == State.WARNING:
              length_info = f"\n    {ANSI.YELLOW} → Length is valid but long ({len(self.column_name)}/{MAX_COLUMN_LENGTH}).{ANSI.RESET}"
          elif self.length.state == State.FAIL:
              length_info = f"\n     {ANSI.RED} → Column name is too long ({len(self.column_name)}/{MAX_COLUMN_LENGTH}).{ANSI.RESET}"
          
          if self.length.state!= State.PASS or verbose:
              print(
                  f"  Length < {MAX_COLUMN_LENGTH} characters:                       {length_status}{length_info}"
              )

          if self.no_decimals.state == State.FAIL or verbose:
              print(
                  f"  No decimal points:                            {status(self.no_decimals)}"
              )

          filter_status = status(self.filter_name)
          filter_info = ""
          if self.filter_name.state == State.WARNING:
              filter_info = f"\n    {ANSI.YELLOW} → Possible filter name violation: did you mean '{self.filter_name.message}'?{ANSI.RESET}"
          elif self.filter_name.state == State.FAIL:
              filter_info = f"\n    {ANSI.RED} → Required: Use '{self.filter_name.message}'{ANSI.RESET}" if self.filter_name.state == State.FAIL else ""
          
          if self.filter_name.state != State.PASS or verbose:
              print(
                  f"  Valid filter name usage:                      {filter_status}{filter_info}"
              )
          
          exception_status = status(self.no_exception_violation)
          exception_info = f"\n    {ANSI.RED} → Required: Use correct case '{self.no_exception_violation.message}'{ANSI.RESET}" if self.no_exception_violation.state != State.PASS else ""
          if self.no_exception_violation.state != State.PASS or verbose:
              print(
                  f"  Exception words in correct case:              {exception_status}{exception_info}"
              )

          protected_status = status(self.not_protected)
          protected_info = ""
          if self.not_protected.state == State.WARNING:
              protected_info = f"\n    {ANSI.YELLOW} → Protected word in use: Use correct form. Maybe '{self.not_protected.message}'?{ANSI.RESET}"
          elif self.not_protected.state == State.FAIL:
              protected_info = f"\n    {ANSI.RED} → Protected word in use: Use correct case: '{self.not_protected.message}'{ANSI.RESET}"
              
          if self.not_protected.state == State.WARNING or self.not_protected.state == State.FAIL or verbose:
              print(
                  f"  Not violating protected standards:            {protected_status}{protected_info}"
              )
          
          allowed_status = status(self.allowed_words)
          allowed_info = ""
          if self.allowed_words.state == State.WARNING:
              allowed_info = f"\n    {ANSI.YELLOW} → {self.allowed_words.message}{ANSI.RESET}"
          elif self.allowed_words.state == State.FAIL:
              allowed_info = f"\n    {ANSI.RED} → {self.allowed_words.message}{ANSI.RESET}"
          if self.allowed_words.state != State.PASS or verbose:
              print(
                  f"  No banned words:                              {allowed_status}{allowed_info}"
              )

          print(f"{'-' * 80}")


def validate_column_name(name: str) -> ColumnNameReport:
    """
    Checks that the column names are correct and returns a report
    """
    alphanumeric = check_alphanumeric(name)
    letter_start = check_alphabetical_start(name)
    valid_length = check_length(name)
    snake_case = check_snake_case(name)
    no_decimals = check_decimals(name)
    valid_filter = check_filter(name)
    allowed = check_allowed(name)
    violates_exception = check_exceptions(name)
    not_protected_word = check_protected(name)

    return ColumnNameReport(
        column_name=name,
        alpha_numeric=alphanumeric,
        starts_with_letter=letter_start,
        snake_case=snake_case,
        length=valid_length,
        no_decimals=no_decimals,
        filter_name=valid_filter,
        allowed_words=allowed,
        no_exception_violation=violates_exception,
        not_protected=not_protected_word,
    )
