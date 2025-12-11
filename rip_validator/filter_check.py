"""
Filter checking module to handle searching for erroneous filters that might exist.
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from thefuzz import fuzz
from .status import Status, State

from .config import filter_words

WARNING_TOLERANCE_RATIO = 70
FAIL_TOLERANCE_RATIO = 80


def check_filter(name: str) -> Status:
    """
    Checks that the string doesn't contain some attempt at using a filter name and if it does
    actively suggests the correct version.
    """
    for filter_name in filter_words:
        if filter_name.name in name:
            return Status(State.PASS)
    simplified_string = name.lower().replace("_", "")
    # check cases are correct.
    for filter_name in filter_words:
        if filter_name.name.replace("_", "").lower() in simplified_string:
            if filter_name.name not in name:
                return Status(State.FAIL, filter_name.name)

    # check inverse cases
    for filter_name in filter_words:
        if filter_name.inverse_name.replace("_", "").lower() in simplified_string:
            return Status(State.FAIL, filter_name.name)

    # fuzzy finding for possible violations
    for filter_name in filter_words:
        ratio = fuzz.ratio(filter_name.name.replace("_", "").lower(), simplified_string)

        ratio_inverse = fuzz.ratio(
            filter_name.inverse_name.replace("_", "").lower(), simplified_string
        )
        if ratio > WARNING_TOLERANCE_RATIO or ratio_inverse > WARNING_TOLERANCE_RATIO:
            return Status(State.WARNING, filter_name.name)
        if ratio > FAIL_TOLERANCE_RATIO or ratio_inverse > FAIL_TOLERANCE_RATIO:
            return Status(State.FAIL, filter_name.name)

    return Status(State.PASS)
