"""
Module for Report base class and helper functions.
"""

from typing import ClassVar

from .helper_validator_methods import WHITESPACE_PADDING_LENGTH, print_header
from .status import Status
from .WAVES_config import ANSI


class Report:
    CHECK_LABELS: ClassVar[dict[str, str]] = {}
    TITLE: ClassVar[str] = "Validation Report"

    def _status_fields(self) -> list[tuple[str, "Status"]]:
        """Yield (label, Status) for each check field declared in CHECK_LABELS."""
        return [
            (self.CHECK_LABELS[name], getattr(self, name)) for name in self.CHECK_LABELS
        ]

    @property
    def is_valid(self) -> bool:
        if any(status.is_fail for _, status in self._status_fields()):
            return False
        return True

    @property
    def has_warnings(self) -> bool:
        return any(status.is_warn for _, status in self._status_fields())

    def print_report(self, verbose: bool = False) -> None:
        is_valid = self.is_valid
        has_warnings = self.has_warnings

        if not is_valid:
            overall_color, overall_status = ANSI.RED, "INVALID"
        elif has_warnings:
            overall_color, overall_status = ANSI.YELLOW, "VALID (with warnings)"
        else:
            overall_color, overall_status = ANSI.GREEN, "VALID"

        print_header(self.TITLE)
        print(
            f"{ANSI.BOLD}Overall Status:{ANSI.RESET} "
            f"{overall_color}{overall_status}{ANSI.RESET}"
        )

        if is_valid and not has_warnings and not verbose:
            return

        print(f"\n{ANSI.BOLD}Validation Checks:{ANSI.RESET}")
        print("-" * 80)
        for label, status in self._status_fields():
            if status.is_pass and not verbose:
                continue

            if status.is_fail and status.message:
                detail = f"\n     {ANSI.RED} → {status.message}{ANSI.RESET}"
            elif status.is_warn and status.message:
                detail = f"\n     {ANSI.YELLOW} → {status.message}{ANSI.RESET}"
            else:
                detail = ""

            padded = label.ljust(WHITESPACE_PADDING_LENGTH)
            print(f"  {padded:<45} {status.output()}{detail}")
        print("-" * 80)
