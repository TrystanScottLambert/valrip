from enum import Enum, StrEnum


class WAVESCustomExceptions(StrEnum):
    # pydantic handling of exceptions inside lists is not adqeuate, so we
    # implement a custom validation and exception type to handle those use cases
    LIST_EXCEPTION = "waves_custom_list_exception"
    # pydantic does not recognise empty strings as missing values,
    # so we implement custom validation for empty strings as "missing" values
    MISSING_EXCEPTION = "waves_custom_missing_exception"


class SurveyName(Enum):
    WAVES = "WAVES"
    FOURC3R2 = "WAVES-4C3R2"
    STEPS = "WAVES-StePS"
    ORCHIDSS = "WAVES-ORCHIDSS"


MAML_VERSION = 1.1


class License(Enum):
    PRIVATE = "Copyright WAVES [Private]"
    PUBLIC = "MIT"


class WAVESDataTypes(Enum):
    INT16 = "int16"
    INT32 = "int32"
    INT64 = "int64"
    FLOAT32 = "float32"
    FLOAT64 = "float64"
    BOOLEAN = "boolean"
    STRING = "string"

    @classmethod
    def numeric(cls):
        return {
            cls.INT16.value,
            cls.INT32.value,
            cls.INT64.value,
            cls.FLOAT32.value,
            cls.FLOAT64.value,
        }

    @classmethod
    def integer(cls):
        return {cls.INT16.value, cls.INT32.value, cls.INT64.value}

    @classmethod
    def floating_point(cls):
        return {cls.FLOAT32.value, cls.FLOAT64.value}


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
    GREY = "\033[90m"
    RESET = "\033[0m"
