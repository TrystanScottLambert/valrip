"""
Module for handling YAML specific formatting errors.
"""

from typing import Optional
from .data_types import ANSI
from .config import ucd_rules


def check_yaml_colon_spacing(yaml_content: str) -> Optional[str]:
    """
    Check if YAML content has missing spaces after colons in key-value pairs.
    """
    lines = yaml_content.split("\n")

    for line_num, line in enumerate(lines, start=1):
        # Skip empty lines and comments
        stripped = line.lstrip()
        if not stripped or stripped.startswith("#"):
            continue

        # Look for colons that are part of key-value pairs
        # Pattern: colon followed by non-whitespace (excluding quotes and special cases)
        # We need to be careful about:
        # - URLs (http://, https://)
        # - Time values (12:30)
        # - Colons inside quoted strings
        # - UCD namespaces

        in_single_quote = False
        in_double_quote = False

        for i, char in enumerate(line):
            # Track quote state
            if char == '"' and (i == 0 or line[i - 1] != "\\"):
                in_double_quote = not in_double_quote
            elif char == "'" and (i == 0 or line[i - 1] != "\\"):
                in_single_quote = not in_single_quote

            # Check for colon not in quotes
            if char == ":" and not in_single_quote and not in_double_quote:
                # Check if there's a next character
                if i + 1 < len(line):
                    next_char = line[i + 1]

                    # Colon should be followed by space, newline, or end of line
                    # Exception: URLs like http:// or https://, time values and UCD namespaces
                    if next_char not in (" ", "\t", "\n"):
                        # Check if it's part of a URL (http:// https:// ftp://)
                        is_url = False
                        if i >= 4 and line[i - 4 : i + 3] == "http://":
                            is_url = True
                        elif i >= 5 and line[i - 5 : i + 3] == "https://":
                            is_url = True
                        elif i >= 3 and line[i - 3 : i + 3] == "ftp://":
                            is_url = True

                        if not is_url:
                            # Check it's not a time value (number before and after)
                            prev_is_digit = i > 0 and line[i - 1].isdigit()
                            next_is_digit = next_char.isdigit()

                            # Check if the colon is part of a UCD namespace - this is not invalid YAML
                            is_namespace = False
                            for name in ucd_rules.namespaces:
                                if i >= len(name) and line[i - len(name) : i] == name:
                                    is_namespace = True
                                    break

                            if not (is_namespace or (prev_is_digit and next_is_digit)):
                                error_msg = (
                                    f"{ANSI.RED}Invalid YAML syntax on line {ANSI.RESET}{ANSI.GREEN}{line_num}{ANSI.RESET}{ANSI.RED}: "
                                    f"Missing space after colon. "
                                    f"YAML requires a space after ':' in key-value pairs.\n"
                                    f"  Found: {ANSI.RESET}{ANSI.YELLOW}'{line.strip()}'{ANSI.RESET}\n"
                                )
                                return error_msg

    return None


def validate_yaml_file(file_path: str) -> bool:
    """
    Validate a YAML file for proper colon spacing.
    """
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    error_msg = check_yaml_colon_spacing(content)
    if error_msg:
        print(error_msg)
        return False
    return True
