"""
Module for storing the Status and error handling data structures
"""

from dataclasses import dataclass
from enum import Enum

from rip_validator.data_types import ANSI


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
                return f"{ANSI.YELLOW}⚠ WARNING"
