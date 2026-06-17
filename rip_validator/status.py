"""
Module for storing the Status and error handling data structures
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Self

from rip_validator.WAVES_config import ANSI


class State(Enum):
    PASS = 0
    WARNING = 1
    FAIL = 2


def output_state(state: State) -> str:
    match state:
        case State.PASS:
            return f"{ANSI.GREEN}VALID{ANSI.RESET}"
        case State.FAIL:
            return f"{ANSI.RED}INVALID{ANSI.RESET}"
        case State.WARNING:
            return f"{ANSI.YELLOW}WARNING"


@dataclass
class Status:
    state: State
    fail_message: str | None = None
    warning_message: str | None = None

    def output(self) -> str:
        match self.state:
            case State.PASS:
                return f"{ANSI.GREEN}✓ PASS{ANSI.RESET}"
            case State.FAIL:
                return f"{ANSI.RED}✗ FAIL{ANSI.RESET}"
            case State.WARNING:
                return f"{ANSI.YELLOW}⚠ WARNING{ANSI.RESET}"

    @classmethod
    def failed(cls, fail_message: str, warn_message: str | None = None) -> Self:
        """Helper function to make creating failed statuses easier."""
        return cls(State.FAIL, fail_message, warn_message)

    @classmethod
    def passed(cls) -> Self:
        """Helper function to make passed status easier."""
        return cls(State.PASS)

    @classmethod
    def warned(cls, warn_message: str, fail_message: str | None = None) -> Self:
        if warn_message is None:
            raise ValueError(
                "No warn_message provided, failed statuses require a warn_message."
            )
        """Helper method for building warning Statuses"""
        return cls(State.WARNING, fail_message, warn_message)

    @property
    def is_fail(self) -> bool:
        return self.state == State.FAIL

    @property
    def is_pass(self) -> bool:
        return self.state == State.PASS

    @property
    def is_warn(self) -> bool:
        return self.state == State.WARNING

    @property
    def is_passable(self) -> bool:
        """True for PASS or WARNING. Useful for cases where we need to only catch failures."""
        return self.state != State.FAIL


@dataclass
class Messages:
    fail: list[str] = field(default_factory=list)
    warning: list[str] = field(default_factory=list)

    def add_fail(self, fail: str) -> None:
        self.fail.append(fail)

    def add_warning(self, warning: str) -> None:
        self.warning.append(warning)
