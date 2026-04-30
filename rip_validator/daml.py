"""
Module for data-set meta yaml (DAML) handling.
"""

import dataclasses
import datetime
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar, Self

import yaml

from .yaml_errors import validate_yaml_file
from .yaml_convience_functions import NoDatesSafeLoader, SafeDumper
from .report import Report
from .status import Status
from .WAVES_config import ANSI, License
from .auto_version import get_next_version
from .helper_validator_methods import (
    requires_type,
    requires_not_none,
    validate_author,
    validate_coauthors,
    validate_date,
    validate_description,
    validate_license,
    validate_survey,
    validate_order,
    validate_empty_optionals,
)

DAML_ORDER = [
    "survey",
    "dataset",
    "version",
    "date",
    "author",
    "coauthors",
    "dois",
    "description",
    "comments",
    "license",
    "keywords",
    "ancillary",
    "tables",
]

DAML_REQUIRED = [
    "survey",
    "dataset",
    "version",
    "date",
    "author",
    "description",
    "license",
    "tables",
]


@dataclass
class DAMLReport(Report):
    survey: Status
    dataset: Status
    author: Status
    coauthors: Status
    date: Status
    description: Status
    license: Status
    version: Status
    tables: Status
    no_extra_fields: Status
    no_empty_optionals: Status
    keys_in_order: Status

    TITLE: ClassVar[str] = "DAML Validation Report"
    CHECK_LABELS: ClassVar[dict[str, str]] = {
        "survey": "Valid survey name:",
        "dataset": "Dataset name is the same as RIP name:",
        "author": "Author is correctly formatted:",
        "coauthors": "Coauthors are correctly formatted:",
        "date": "Date valid iso format:",
        "description": "Valid description of RIP:",
        "license": "License:",
        "version": "Version is int:",
        "tables": "Consistent tables:",
        "no_extra_fields": "No extra fields:",
        "no_empty_optionals": "Optional fields aren't empty:",
        "keys_in_order": "Fields are in the correct order:",
    }


@requires_not_none("dataset")
@requires_type("dataset")
def _validate_dataset(dataset: str, rip_name: str) -> Status:
    """Validates that the dataset is equal to the given rip_name."""
    if dataset != rip_name:
        return Status.failed(
            f"{dataset} is incorrect, it does not match the name of the directory. Suggest using '{rip_name}' instead."
        )
    return Status.passed()


@requires_not_none("version")
@requires_type("version")
def _validate_version(version: int, rip_name: str) -> Status:
    correct_version = get_next_version(rip_name)
    if version != correct_version:
        return Status.failed(
            f"'{rip_name}' has the incorrect version: {version} should be {correct_version} to be consistent with the QC GitLab history."
        )
    return Status.passed()


@requires_not_none("tables")
def _validate_tables(
    tables: list[dict[str, int]], maml_data: dict[str, dict]
) -> Status:
    """Validates that the current tables are correct for the given maml_data"""
    all_error_messages = []
    correct_tables = _get_tables(maml_data)
    correct_table_names = [correct_table["name"] for correct_table in correct_tables]
    current_table_names = [current_table["name"] for current_table in tables]
    difference = list(set(correct_table_names) - set(current_table_names))
    if len(difference) != 0:
        all_error_messages.append(
            f"Table(s) '{difference}' referenced in MAMLs but not present in DAML."
        )

    for table in tables:
        if table["name"] not in correct_table_names:
            all_error_messages.append(
                f"Table '{table['name']}' is not in any of the MAML files."
            )
        else:
            correct_version = correct_tables[correct_table_names.index(table["name"])][
                "version"
            ]
            if table["version"] != correct_version:
                all_error_messages.append(
                    f"'{table['name']}' has version {table['version']} in DAML but version {correct_version} in MAML."
                )

    if len(all_error_messages) != 0:
        return Status.failed(
            f"Tables in DAML file are not consistent with the MAML files, they contain the following errors:\n\t- {'\n\t- '.join(all_error_messages)}"
        )
    return Status.passed()


def _validate_extra_fields(raw_yaml: dict | None) -> Status:
    if raw_yaml is None:
        return Status.passed()
    extras = set(raw_yaml.keys()) - set(DAML_ORDER)
    if extras:
        return Status.failed(
            f"Unexpected field(s) in DAML: {sorted(extras)}. Allowed fields are: {DAML_ORDER}.",
        )
    return Status.passed()


@dataclass
class PreDAML:
    survey: str
    dataset: str
    author: str
    coauthors: list[str] | None
    dois: list[str] | None
    comments: list[str] | None
    keywords: list[str] | None
    ancillary: str | None
    tables: list[dict[str, int]]
    version: int
    date: str = field(default_factory=lambda: datetime.date.today().isoformat())
    license: str = License.PRIVATE.value
    description: str = ""
    _raw_yaml: dict | None = field(default=None, repr=False)

    def validate(self, rip_name: str, maml_data: dict[str, dict]) -> DAMLReport:
        return DAMLReport(
            survey=validate_survey(self.survey),
            dataset=_validate_dataset(self.dataset, rip_name),
            author=validate_author(self.author),
            coauthors=validate_coauthors(self.coauthors),
            date=validate_date(self.date),
            description=validate_description(self.description),
            license=validate_license(self.license),
            version=_validate_version(self.version, rip_name),
            tables=_validate_tables(self.tables, maml_data),
            no_empty_optionals=validate_empty_optionals(self._raw_yaml, DAML_REQUIRED),
            no_extra_fields=_validate_extra_fields(self._raw_yaml),
            keys_in_order=validate_order(self._raw_yaml, DAML_ORDER),
        )

    @classmethod
    def from_maml_data(cls, maml_data: dict[str, dict], rip_name) -> Self:
        """Maml data is parsed and the DAML is built from that. maml_data is obtained from read_maml in the rip_level_validator.py"""
        return cls(
            survey=_get_survey(maml_data),
            dataset=_get_dataset(maml_data),
            author=_get_author(maml_data),
            coauthors=_get_coauthors(maml_data),
            tables=_get_tables(maml_data),
            version=get_next_version(rip_name),
            dois=None,
            comments=None,
            keywords=None,
            ancillary=None,
        )

    @classmethod
    def from_file(cls, file_name: Path) -> Self:
        """Reads in a .DAML file into a PreDAML object."""
        try:
            validate_yaml_file(file_name)
        except ValueError as e:
            print(f"{ANSI.RED}{file_name} not valid yaml{ANSI.RESET}", e)
            sys.exit()
        with open(file_name) as file:
            try:
                yaml_data = yaml.load(file, Loader=NoDatesSafeLoader)
            except (Exception, AttributeError) as e:
                print(f"{ANSI.RED}{file_name} not valid yaml{ANSI.RESET}", e)
                sys.exit()
        if isinstance(yaml_data, str):
            print(
                f"{ANSI.RED}{file_name} is not valid yaml. It's just a string{ANSI.RESET}"
            )
            sys.exit()

        fields = {f.name for f in dataclasses.fields(cls)}  # All fields in preDAML.
        instance = cls(**{field: yaml_data.get(field, None) for field in fields})
        instance._raw_yaml = yaml_data  # stash for validation
        return instance

    def to_file(self, file_name: str) -> None:
        dict_rep = dataclasses.asdict(self)
        dict_rep_ordered = {entry: dict_rep[entry] for entry in DAML_ORDER}
        no_nones = {k: v for k, v in dict_rep_ordered.items() if v is not None}
        if no_nones["description"] == "":
            no_nones["description"] = None

        with open(file_name, "w") as file:
            yaml.dump(
                no_nones,
                file,
                sort_keys=False,
                default_flow_style=False,
                Dumper=SafeDumper,
            )


def _unique_list(string_list: list[str]) -> list[str]:
    return list(dict.fromkeys(string_list))


def _get_survey(maml_data: dict[str, dict]) -> str:
    """Scrapes the maml data and returns a single survey string."""
    survey_strings = _unique_list([data["survey"] for data in maml_data.values()])
    if len(survey_strings) == 1:
        return survey_strings[0]
    return "WAVES"


def _get_dataset(maml_data: dict[str, dict]) -> str:
    """Scrapes the maml data and gets the dataset name. This should only ever be one thing."""
    dataset_strings = _unique_list([data["dataset"] for data in maml_data.values()])

    if len(dataset_strings) != 1:
        raise ValueError(
            f"Differing dataset names {dataset_strings}. This is incorrect."
        )
    return dataset_strings[0]


def _get_author(maml_data: dict[str, dict]) -> str:
    """Scrapes the maml data and assigns the most popular author."""

    authors = [data["author"] for data in maml_data.values()]
    counts = Counter(authors)
    return counts.most_common(1)[0][0]


def _get_coauthors(maml_data: dict[str, dict]) -> list[str] | None:
    """Scrapes the maml data and concatenates all coauthors"""
    coauthors = []
    for data in maml_data.values():
        coauthors += data.get("coauthors", [])
    coauthors = _unique_list(coauthors)
    if not coauthors:
        return None
    return coauthors


def _get_tables(maml_data: dict[str, dict]) -> list[dict[str, int]]:
    """Scrapes the maml data and returns a dictionary of the table_names and versions."""
    return [
        {"name": data["table"], "version": data["version"]}
        for data in maml_data.values()
    ]
