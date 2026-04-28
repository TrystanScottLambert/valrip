"""
Stripped down clone of the astropy ucd checker https://docs.astropy.org/en/stable/_modules/astropy/io/votable/ucd.html#check_ucd
"""

import re
import httpx
import json
from itertools import permutations

from rip_validator import resources_dir
from .settings_config import protected_words, filter_words, exceptions


class UCDWords:
    """
    Manages a list of acceptable UCD words.

    Works by reading in a data file exactly as provided by IVOA.  This
    file resides in extdata/ucd1p-words.txt.
    """

    def __init__(self):
        self._primary = set()
        self._secondary = set()
        self._descriptions = {}
        self._capitalization = {}

        with open(f"{resources_dir}/ucd1p-words.txt", encoding="ascii") as fd:
            for line in fd.readlines():
                if line.startswith("#"):
                    continue

                type, name, descr = (x.strip() for x in line.split("|"))
                name_lower = name.lower()
                if type in "QPEVC":
                    self._primary.add(name_lower)
                if type in "QSEVC":
                    self._secondary.add(name_lower)
                self._descriptions[name_lower] = descr
                self._capitalization[name_lower] = name

    def is_primary(self, name):
        """
        Returns True if *name* is a valid primary name.
        """
        return name.lower() in self._primary

    def is_secondary(self, name):
        """
        Returns True if *name* is a valid secondary name.
        """
        return name.lower() in self._secondary

    def get_description(self, name):
        """
        Returns the official English description of the given UCD
        *name*.
        """
        return self._descriptions[name.lower()]

    def normalize_capitalization(self, name):
        """
        Returns the standard capitalization form of the given name.
        """
        return self._capitalization[name.lower()]


def validate_ucd(ucd: str) -> None:
    """
    Parse the UCD into its component parts.

    :param ucd: The UCD string


    Raises
    ------
    ValueError
        If ucd is invalid.
    """
    if ucd == "":
        return None
    global _ucd_singleton
    _ucd_singleton = UCDWords()

    m = re.search(r"[^A-Za-z0-9_.;\-]", ucd)
    if m is not None:
        raise ValueError(f"UCD has invalid character '{m.group(0)}' in '{ucd}'")

    word_component_re = r"[A-Za-z0-9][A-Za-z0-9\-_]*"
    word_re = rf"{word_component_re}(\.{word_component_re})*"

    parts = ucd.split(";")
    for i, word in enumerate(parts):
        if not re.match(word_re, word):
            raise ValueError(f"Invalid word '{word}'")

        if i == 0:
            if not _ucd_singleton.is_primary(word):
                if _ucd_singleton.is_secondary(word):
                    raise ValueError(
                        f"Secondary word '{word}' is not valid as a primary word"
                    )
                else:
                    raise ValueError(f"Unknown word '{word}'")
        else:
            if not _ucd_singleton.is_secondary(word):
                if _ucd_singleton.is_primary(word):
                    raise ValueError(
                        f"Primary word '{word}' is not valid as a secondary word"
                    )
                else:
                    raise ValueError(f"Unknown word '{word}'")


def scrape_waves_ucd(column_name: str) -> str:
    """
    Helper function will try to guess the UCD from the protected_words and filter configs.
    """
    is_filter = False
    current_ucds = []
    for exception in exceptions:
        if exception.name in column_name:
            current_ucds += [exception.ucd]
    for protected_word in protected_words:
        if "_" in protected_word.name:
            if protected_word.name in column_name:
                current_ucds += protected_word.ucd
        else:
            for word in column_name.split("_"):
                if word == protected_word.name:
                    current_ucds += protected_word.ucd
    for filter_word in filter_words:
        if filter_word.name in column_name:
            current_ucds += [filter_word.secondary_ucd]
            is_filter = True
    full_ucds = list(dict.fromkeys(";".join(current_ucds).split(";")))

    combined = ";".join(full_ucds)
    if ";" not in combined and is_filter and "phot.mag" not in combined:
        combined = f"phot.mag;{combined}"
        is_filter = False

    # Validate the ucd and permuate until we find a valid one. Else give up
    try:
        validate_ucd(combined)
    except ValueError:
        # Try all permutations to see if any are valid.
        words = combined.split(";")
        current_solution = ""
        for i in range(len(words) - 1):
            for permutation in permutations(words, i + 1):
                try:
                    permeated_combination = ";".join(permutation)
                    validate_ucd(permeated_combination)
                    if permeated_combination.count(";") > current_solution.count(";"):
                        current_solution = permeated_combination
                except ValueError:
                    pass
        return current_solution

    return combined


def scrape_cds_ucd(column_name: str) -> str | None:
    """
    Makes a request to https://cdsweb.u-strasbg.fr/UCD/ucd-finder/ and returns best guess at UCD.
    """
    sanitized_string = column_name.translate(str.maketrans("-_.", "   "))
    re = httpx.get(
        f"https://cdsweb.u-strasbg.fr/UCD/ucd-finder/suggest?d={sanitized_string}"
    )
    re_dict = json.loads(re.text)
    try:
        return re_dict["ucd"][0]["ucd"]
    except IndexError:
        return None


def guess_ucd(column_name: str, web_search: bool = True) -> str | None:
    """
    Looks for a WAVES UCD if it exists or else scrapes the CDS website (if web_search is true).
    """
    ucd = scrape_waves_ucd(column_name)
    if ucd == "" and web_search:
        ucd = scrape_cds_ucd(column_name)
    return ucd
