"""
Module for storing the Status and error handling data structures
"""

from dataclasses import dataclass
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
    message: str | None = None

    def output(self) -> str:
        match self.state:
            case State.PASS:
                return f"{ANSI.GREEN}✓ PASS{ANSI.RESET}"
            case State.FAIL:
                return f"{ANSI.RED}✗ FAIL{ANSI.RESET}"
            case State.WARNING:
                return f"{ANSI.YELLOW}⚠ WARNING{ANSI.RESET}"

    @classmethod
    def failed(cls, message: str) -> Self:
        """Helper function to make creating failed statuses easier."""
        return cls(State.FAIL, message)

    @classmethod
    def passed(cls, message: str | None = None) -> Self:
        """Helper function to make passed status easier."""
        return cls(State.PASS, message)

    @classmethod
    def warned(cls, message: str) -> Self:
        """Helper method for building warning Statuses"""
        return cls(State.WARNING, message)

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
