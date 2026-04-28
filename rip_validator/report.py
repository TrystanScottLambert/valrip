"""
Module for Report base class and helper functions.
"""

from typing import ClassVar


from .WAVES_config import ANSI
from .helper_validator_methods import print_header, WHITESPACE_PADDING_LENGTH
from .status import State, Status


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
        if any(status.state == State.FAIL for _, status in self._status_fields()):
            return False
        return True

    def print_report(self, verbose: bool = False) -> None:
        is_valid = self.is_valid
        overall_color = ANSI.GREEN if is_valid else ANSI.RED
        overall_status = "VALID" if is_valid else "INVALID"

        print_header(self.TITLE)
        print(
            f"{ANSI.BOLD}Overall Status:{ANSI.RESET} "
            f"{overall_color}{overall_status}{ANSI.RESET}"
        )

        if is_valid and not verbose:
            return

        print(f"\n{ANSI.BOLD}Validation Checks:{ANSI.RESET}")
        print("-" * 80)
        for label, status in self._status_fields():
            if status.state == State.FAIL or verbose:
                detail = (
                    f"\n     {ANSI.RED} → {status.message}{ANSI.RESET}"
                    if status.state == State.FAIL and status.message
                    else ""
                )
                padded = label.ljust(WHITESPACE_PADDING_LENGTH)
                print(f"  {padded:<45} {status.output()}{detail}")
        print("-" * 80)
