"""
Module for storing the Status and error handling data structures
"""

from dataclasses import dataclass
from enum import Enum


class State(Enum):
    PASS = 1
    FAIL = 0
    WARNING = 2


@dataclass
class Status:
    state: State
    message: str | None = None
