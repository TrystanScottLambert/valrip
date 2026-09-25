"""
Filter checking module to handle searching for erroneous filters that might exist.
"""

import itertools

from thefuzz import fuzz

from .settings_config import filter_words
from .status import Messages

INSTRUMENT_TYPO_RATIO = 75  # "sdds" vs "sdss" scores exactly 75

# compact spelling (either word order) -> canonical filter name
_LOOKUP: dict[str, str] = {}
# (band, instrument, canonical) for typo detection on two-part names
_PAIRS: list[tuple[str, str, str]] = []

for _f in filter_words:
    _toks = _f.name.split("_")
    _LOOKUP["".join(_toks).lower()] = _f.name  # r_SDSS -> rsdss
    _LOOKUP["".join(_toks[-1:] + _toks[:-1]).lower()] = _f.name  # sdss_r / alma_band8
    if len(_toks) == 2:
        _PAIRS.append((_toks[0].lower(), _toks[1].lower(), _f.name))

_INSTRUMENTS = {inst for _, inst, _ in _PAIRS}
# windows are bounded by compact length, so any number of "__" inside still fits
_MAX_COMPACT = max(len(k) for k in _LOOKUP)


def check_filter(name: str) -> Messages:
    """
    Checks that the string doesn't contain some attempt at using a filter name and if it does
    actively suggests the correct version.
    """
    messages = Messages()
    tokens = name.split("_")  # keep empties so "__" survives the rebuild
    flagged: set[str] = set()

    # Exact matches on whole-token runs, case/order-insensitive
    for i, start in enumerate(tokens):
        if not start:
            continue  # windows never start on an empty token
        compact = ""
        for j in range(i, len(tokens)):
            compact += tokens[j].lower()
            if len(compact) > _MAX_COMPACT:
                break
            if not tokens[j]:
                continue  # ...or end on one
            canonical = _LOOKUP.get(compact)
            if canonical is None or canonical in flagged:
                continue
            if "_".join(tokens[i : j + 1]) != canonical:
                flagged.add(canonical)
                messages.add_fail(f"{name} is incorrect, please use {canonical}.")

    # Typos: band token exact, adjacent instrument token is a near miss
    words = [t.lower() for t in tokens if t]
    for a, b in itertools.pairwise(words):
        for band, inst, canonical in _PAIRS:
            if canonical in flagged:
                continue
            for got_band, got_inst in ((a, b), (b, a)):
                if (
                    got_band == band
                    and got_inst not in _INSTRUMENTS
                    and len(got_inst) >= 3
                    and fuzz.ratio(got_inst, inst) >= INSTRUMENT_TYPO_RATIO
                ):
                    flagged.add(canonical)
                    messages.add_warning(
                        f"Possible filter name violation on {name}, did you mean {canonical}?"
                    )
                    break

    return messages
