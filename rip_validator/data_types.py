from enum import Enum, StrEnum

class SurveyName(Enum):
    WAVES = "WAVES"
    FOURC3R2 = "WAVES-4C3R2"
    STEPS = "WAVES-StePS"
    ORCHIDSS = "WAVES-ORCHIDSS"
    

class License(Enum):
    PRIVATE = "Copyright WAVES [Private]"
    PUBLIC = "MIT"


class ClosedInterval(Enum):
    """
    Contains the possible intervals over which a range can be closed or open.
    'left' => [a, b)
    'right' => (a, b]
    'both' => [a, b]
    'none' => (a, b)
    """

    LEFT = "left"
    RIGHT = "right"
    BOTH = "both"
    NONE = "none"


class ANSI(StrEnum):
    """
    Contains the colours and their colour mapping for use in terminal output. 
    """
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BOLD = "\033[1m"
    RESET = "\033[0m"