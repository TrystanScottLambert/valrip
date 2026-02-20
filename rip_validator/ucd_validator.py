"""
Stripped down clone of the astropy ucd checker https://docs.astropy.org/en/stable/_modules/astropy/io/votable/ucd.html#check_ucd
"""

import re
from rip_validator import resources_dir


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

    Parameters
    ----------
    ucd: The UCD string


    Raises
    ------
    ValueError
        if *ucd* is invalid
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
        colon_count = word.count(":")
        if colon_count > 0:
            raise ValueError(f"Too many colons in '{word}'. Name spaces not allowed")

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
