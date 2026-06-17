"""
Filter checking module to handle searching for erroneous filters that might exist.
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from thefuzz import fuzz
from .status import Messages

from .settings_config import filter_words

WARNING_TOLERANCE_RATIO = 70
FAIL_TOLERANCE_RATIO = 80


def check_filter(name: str) -> Messages:
    """
    Checks that the string doesn't contain some attempt at using a filter name and if it does
    actively suggests the correct version.
    """
    messages = Messages()

    simplified_string = name.lower().replace("_", "")
    # check inverse cases
    for filter_name in filter_words:
        if filter_name.inverse_name.replace("_", "").lower() in simplified_string:
            messages.add_fail(f"{name} is incorrect, please use {filter_name.name}.")

    # check cases are correct.
    for filter_name in filter_words:
        if filter_name.name.replace("_", "").lower() in simplified_string:
            if filter_name.name not in name:
                messages.add_fail(
                    f"{name} is incorrect, please use {filter_name.name}."
                )

    # fuzzy finding for possible violations
    for filter_name in filter_words:
        ratio = fuzz.ratio(filter_name.name.replace("_", "").lower(), simplified_string)

        ratio_inverse = fuzz.ratio(
            filter_name.inverse_name.replace("_", "").lower(), simplified_string
        )
        if ratio > FAIL_TOLERANCE_RATIO or ratio_inverse > FAIL_TOLERANCE_RATIO:
            messages.add_fail(f"{name} is incorrect, please use {filter_name.name}")
        if ratio > WARNING_TOLERANCE_RATIO or ratio_inverse > WARNING_TOLERANCE_RATIO:
            messages.add_warning(
                f"Possible filter name violation on {name}, did you mean {filter_name.name}?"
            )

    return messages
