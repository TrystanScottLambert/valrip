from enum import Enum, StrEnum
from dataclasses import dataclass
import polars as pl
import re

EMAIL_REGEX = re.compile(r"^(?P<name>.+?)\s*<(?P<email>[^>]+)>$")


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

    @classmethod
    def polars_dtype_to_WAVES_data_type(cls, polars_dtype: pl.DataType):
        if polars_dtype == pl.Int16:
            return cls.INT16.value
        if polars_dtype == pl.Int32:
            return cls.INT32.value
        if polars_dtype == pl.Int64:
            return cls.INT64.value
        if polars_dtype == pl.Float32:
            return cls.FLOAT32.value
        if polars_dtype == pl.Float64:
            return cls.FLOAT64.value
        if polars_dtype == pl.Boolean:
            return cls.BOOLEAN.value
        if polars_dtype == pl.String:
            return cls.STRING.value

        raise ValueError(
            f"Data type {polars_dtype} is not a valid WAVES data type. Accepted data types are: {[e.value for e in WAVESDataTypes]}"
        )


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


@dataclass
class Dependency:
    """
    Other tables or datasets that someone might be dependendt on.
    """

    survey: str
    dataset: str
    table: str
    version: str


@dataclass
class MinMax:
    min: float
    max: float


@dataclass
class ColumnMetaData:
    name: str
    ucd: str | None
    data_type: str
    qc: MinMax | None
    unit: str = "--"
    info: str = "--"

    def to_maml_dict(self) -> dict[str, str]:
        """
        Puts the column data into the format that can be passed to pymaml
        """
        qc = self.qc.__dict__ if self.qc else None
        maml_dict = self.__dict__
        maml_dict["qc"] = qc
        return maml_dict


@dataclass
class Columns:
    columns: dict[str, ColumnMetaData]

    def set_info(self, column_name: str, info: str) -> None:
        """
        Sets the info field for the given column.
        """
        try:
            self.columns[column_name].info = info
        except KeyError:
            raise ValueError(f"No column with the name '{column_name}' found.")

    def get_info(self, column_name: str) -> str | None:
        """
        Returns the info for the given column.
        """
        try:
            value = self.columns[column_name].info
        except KeyError:
            raise ValueError(f"No column with the name '{column_name}' found.")
        return value

    @property
    def info(self) -> list[str | None]:
        """
        returns a list of all the info strings for all the columns.
        """
        return [column.info for column in self.columns.values()]

    def set_unit(self, column_name: str, unit: str) -> None:
        """
        Sets the unit field for the given column.
        """
        try:
            self.columns[column_name].unit = unit
        except KeyError:
            raise ValueError(f"No column with the name '{column_name}' found.")

    def get_unit(self, column_name: str) -> str | None:
        """
        Returns the unit for the given column
        """
        try:
            value = self.columns[column_name].unit
        except KeyError:
            raise ValueError(f"No column with the name '{column_name}' found.")
        return value

    @property
    def units(self) -> list[str | None]:
        """
        Returns a list of all the unit strings for all the columns.
        """
        return [column.unit for column in self.columns.values()]

    def set_ucd(self, column_name: str, ucd: str) -> None:
        """
        Sets the ucd field for the given column.
        """
        try:
            self.columns[column_name].ucd = ucd
        except KeyError:
            raise ValueError(f"No column with the name '{column_name}' found.")

    def get_ucd(self, column_name: str) -> str | None:
        """
        Returns the unit for the given column.
        """
        try:
            value = self.columns[column_name].ucd
        except KeyError:
            raise ValueError(f"No column with the name '{column_name}' found.")
        return value

    @property
    def ucds(self) -> list[str | None]:
        """
        Returns a list of all the ucds for all the columns.
        """
        return [column.ucd for column in self.columns.values()]

    def get_minmax(self, column_name: str) -> MinMax | None:
        """
        Returns the qc (min max) for the given column.
        """
        try:
            value = self.columns[column_name].qc
        except KeyError:
            raise ValueError(f"No column with the name '{column_name}' found.")
        return value

    @property
    def qcs(self) -> list[MinMax | None]:
        """
        Returns a list of all the qcs for all the columns.
        """
        return [column.qc for column in self.columns.values()]

    @property
    def names(self) -> list[str]:
        """
        Returns a list of all the column names
        """
        return list(self.columns.keys())

    @property
    def data_types(self) -> list[str]:
        """
        Returns a list of all the datatypes
        """
        return [column.data_type for column in self.columns.values()]


@dataclass
class Doi:
    doi: str
    doi_type: str
