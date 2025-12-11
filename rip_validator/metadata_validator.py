"""
Module for handling the WAVES-specific flavor of MAML
Helper functions for building the metadata for the datasets.
"""

from dataclasses import dataclass
import re
from datetime import datetime
import polars as pl
import httpx
import json
import yaml

from pydantic_core import ValidationError

from .helper_validator_methods import print_header
from .model_waves_maml import WavesMamlSchema
from .data_types import SurveyName, License, ANSI

from .config import protected_words, filter_words, exceptions


def _is_valid_email(email: str) -> bool:
    """
    Checking that an email is correct. Very basic validation checking . and @
    """
    if re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", email):
        return True
    return False


@dataclass
class Author:
    name: str
    surname: str
    email: str

    def __post_init__(self) -> None:
        """
        Validating email.
        """
        if not _is_valid_email(self.email):
            raise ValueError("Email is not valid")

    def __str__(self):
        return f"{self.name.capitalize()} {self.surname.capitalize()} <{self.email}>"


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
class TableMetaData:
    name: str
    version: str

    def _is_missing(self) -> list[str]:
        """
        Returns a list of all the fields that are None.
        """
        return [field for field, value in self.__dict__.items() if not value]

    def _to_daml_dict(self) -> dict[str, str]:
        """
        Puts the table data into the format that can be passed to pymaml
        """
        daml_dict = self.__dict__
        return daml_dict


@dataclass
class ColumnMetaData:
    name: str
    ucd: str | None
    data_type: str
    qc: MinMax | None
    unit: str | None = None
    info: str | None = None

    def _is_missing(self) -> list[str]:
        """
        Returns a list of all the fields that are None.
        """
        return [field for field, value in self.__dict__.items() if not value]

    def _to_maml_dict(self) -> dict[str, str]:
        """
        Puts the column data into the format that can be passed to pymaml
        """
        qc = self.qc.__dict__
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

    def set_minmax(self, column_name: str, min: float, max: float) -> None:
        """
        Sets the minimum and maximum values for the given column.
        If the column is not numerica this will raise an error."
        """
        if self.columns[column_name].data_type == "string":
            raise ValueError(
                f"Cannot set the min max of a 'string' type column: '{column_name}'"
            )
        try:
            self.columns[column_name].qc = MinMax(min=min, max=max)
        except KeyError:
            raise ValueError(f"No column with the name '{column_name}' found.")

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

    def is_complete(self) -> bool:
        """
        Returns True if the columns have all the metadata and false if there are fields missing.
        """
        for column in self.columns.values():
            if len(column._is_missing()) != 0:
                return False
        return True

    def missing_values(self) -> dict[str, list[str]]:
        """
        Returns a dictonary of all the columns that have missing fields and what
        those fields are.
        """
        missing_dict = {}
        for column_name, column in self.columns.items():
            missing_fields = column._is_missing()
            if len(missing_fields) != 0:
                missing_dict[column_name] = missing_fields
        return missing_dict


@dataclass
class Doi:
    doi: str
    doi_type: str


@dataclass
class MamlMetaData:
    survey: SurveyName
    dataset: str
    table: str
    version: str
    author: Author
    description: str
    fields: Columns
    date: str = str(datetime.today()).split(" ")[0]
    coauthors: list[Author] | None = None
    dois: list[Doi] | None = None
    depends: list[Dependency] | None = None
    comments: list[str] | None = None
    license: License = License.PRIVATE
    keywords: list[str] | None = None
    maml_version: str = "v1.1"

    def add_coauthor(self, coauthor: Author) -> None:
        """
        Adds a coauthor to the list of coauthors
        """
        if not isinstance(coauthor, Author):
            raise ValueError(
                "Coauthor needs to be an 'Author' type. Use Author('<name>', '<surname>', '<email>')"
            )
        if not self.coauthors:
            self.coauthors = [coauthor]
        else:
            self.coauthors.append(coauthor)

    def add_comment(self, comment: str) -> None:
        """
        Adds a comment to the comment list
        """
        if not self.comments:
            self.comments = [comment]
        else:
            self.comments.append(comment)

    def add_dependency(self, dependency: Dependency) -> None:
        if not isinstance(dependency, Dependency):
            raise ValueError(
                "dependency needs to be 'Dependency' type. Use Dependency(<survey>, <dataset>, <table>, <version>)."
            )
        if not self.depends:
            self.depends = [dependency]
        else:
            self.depends.append(dependency)

    def add_doi(self, doi: Doi) -> None:
        """
        Adds a doi to the metadata object.
        """
        if not isinstance(doi, Doi):
            raise ValueError(
                "doi needs to be a 'Doi' object. Use Doi(<doi string>, <type of doi>)."
            )
        if not self.dois:
            self.dois = [doi]
        else:
            self.dois.append(doi)

    def add_keyword(self, keyword: str) -> None:
        """
        Adds a keyword to the metadata object
        """
        if not self.keywords:
            self.keywords = [keyword]
        else:
            self.keywords.append(keyword)


def _split_author_string(author: str) -> Author:
    """
    Attempts to turn a string 'first last <first@somewhere.com>' into an Author object
    """
    words = author.split(" ")
    first_name = words[0]
    last_name = author[author.find(" ") : author.find("<")].strip()
    email = author.split("<")[-1].split(">")[0]
    return Author(first_name, last_name, email)


# TODO #5: make validation output consistent (put the validation into a Report object like in the 
# column validation and the table validation). Also implement the verbose output properly. 
def read_and_validate_maml(maml_file: str, print_output=True, verbose=False) -> MamlMetaData | None:
    """
    Reads in a maml file and parses it into a MetaData object, validating it in
    the process.
    """
    if print_output:
      print_header("MAML Validation Report")
      print(f"\n{ANSI.BOLD}File Name:{ANSI.RESET} {maml_file}")
    with open(maml_file) as file:
        maml_dict = yaml.safe_load(file)
    try:
        WavesMamlSchema.model_validate(maml_dict)
        if print_output:
          print(f"{ANSI.BOLD}Overall Status:{ANSI.RESET} {ANSI.GREEN}VALID{ANSI.RESET}")
    except ValidationError as e:
        if print_output:
          print(f"{ANSI.BOLD}Overall Status:{ANSI.RESET} {ANSI.RED}INVALID{ANSI.RESET}")
        for exception in e.errors():
            invalid_field = exception["loc"][-1]
            if print_output:
              print(f"\n{ANSI.BOLD}{invalid_field} ({exception["input"]}):{ANSI.RESET} {exception["msg"]} {ANSI.RED}✗ FAIL{ANSI.RESET}")
        return None
    
    if "coauthors" in maml_dict and maml_dict["coauthors"]:
        coauthors = []
        for coauthor in maml_dict["coauthors"]:
          try:
              coauthors.append(_split_author_string(coauthor))
          except ValueError:
              pass
        if not coauthors:
            coauthors = None
    else:
        coauthors = None

    if "dois" in maml_dict:
        dois = (
            [Doi(doi["DOI"], doi["type"]) for doi in maml_dict["DOIs"]]
            if maml_dict["DOIs"]
            else None
        )
    else:
        dois = None

    if "depends" in maml_dict:
        depends = (
            [
                Dependency(dep["survey"], dep["dataset"], dep["table"], dep["version"])
                for dep in maml_dict["depends"]
            ]
            if maml_dict["depends"]
            else None
        )
    else:
        depends = None

    if "comments" in maml_dict:
        comments = maml_dict["comments"]
    else:
        comments = None

    if "keywords" in maml_dict:
        keywords = maml_dict["keywords"]
    else:
        keywords = None

    columns = Columns({})
    for field in maml_dict["fields"]:
        if "qc" in field:
            qc = MinMax(field["qc"]["min"], field["qc"]["max"])
        else:
            qc = None
        columns.columns[field["name"]] = ColumnMetaData(
            name=field["name"],
            unit=field["unit"],
            info=field["info"],
            ucd=field["ucd"],
            data_type=field["data_type"],
            qc=qc,
        )

    return MamlMetaData(
        survey=SurveyName(maml_dict["survey"]),
        dataset=maml_dict["dataset"],
        table=maml_dict["table"],
        version=maml_dict["version"],
        date=maml_dict["date"],
        author=_split_author_string(maml_dict["author"]),
        coauthors=coauthors,
        dois=dois,
        depends=depends,
        description=maml_dict["description"],
        comments=comments,
        license=License(maml_dict["license"]),
        keywords=keywords,
        maml_version=maml_dict["MAML_version"],
        fields=columns,
    )


def _scrape_ucd(column_name: str) -> str:
    """
    Helper function will try to guess the ucd from the protected_words and filter configs.
    """
    current_ucds = []
    for exception in exceptions:
        if exception.name in column_name:
            current_ucds += [exception.ucd]
    for protected_word in protected_words:
        if "_" in protected_word.name:
            if protected_word.name in column_name:
                current_ucds += protected_word.ucd
        else:
            for word in column_name.split("_"):
                if word == protected_word.name:
                    current_ucds += protected_word.ucd
    for filter_word in filter_words:
        if filter_word.name in column_name:
            current_ucds += [filter_word.secondary_ucd]
    full_ucds = list(dict.fromkeys(";".join(current_ucds).split(";")))
    return ";".join(full_ucds)


def _scrape_cds_ucd(column_name: str) -> str | None:
    """
    Makes a request to https://cdsweb.u-strasbg.fr/UCD/ucd-finder/ and returns best guess at ucd.
    """
    sanitized_string = column_name.translate(str.maketrans("-_.", "   "))
    re = httpx.get(
        f"https://cdsweb.u-strasbg.fr/UCD/ucd-finder/suggest?d={sanitized_string}"
    )
    re_dict = json.loads(re.text)
    try:
        return re_dict["ucd"][0]["ucd"]
    except IndexError:
        return None


def guess_ucd(column_name: str, web_search: bool = True) -> str | None:
    """
    Looks for a WAVES ucd if it exists or else scrapes the CDS website.
    """
    ucd = _scrape_ucd(column_name)
    if ucd == "" and web_search:
        ucd = _scrape_cds_ucd(column_name)
    return ucd


def fields_from_df(data_frame: pl.DataFrame, web_search: bool = True) -> Columns:
    """
    Automatically generating as much field metadata as possible.

    This function will attempt to guess the ucd strings using the
    official WAVES lookup table. If the search cds is True
    then any other column names will make requests to the cds website.
    """
    column_names = data_frame.columns
    # We are lucky here that datacentral adopts the polars datatypes lower cased.
    data_types = [str(dtype).lower() for dtype in list(data_frame.dtypes)]

    mins = data_frame.min().row(0)
    maxs = data_frame.max().row(0)
    qcs = [
        MinMax(min, max) if not isinstance(min, str) else None
        for min, max in zip(mins, maxs)
    ]

    ucds = [guess_ucd(column_name, web_search) for column_name in column_names]
    units = []
    for column_name in column_names:
        possible_unit = None
        for protected_word in protected_words:
            if len(protected_word.name.split("_")) > 1:
                if protected_word.name in column_name:
                    if not possible_unit:
                        possible_unit = protected_word.unit[0]

            for word in column_name.split("_"):
                if word == protected_word.name:
                    if not possible_unit:
                        possible_unit = protected_word.unit[0]
        units.append(possible_unit)
    field_data = []

    for name, data_type, ucd, qc, unit in zip(
        column_names, data_types, ucds, qcs, units
    ):
        field_data.append(ColumnMetaData(name, ucd, data_type, qc, unit=unit))

    return Columns({column.name: column for column in field_data})
