"""
Module for data-set meta yaml (DAML) handling.
"""

import dataclasses
import datetime
import functools
import inspect
import sys
import typing
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar, Self

import yaml
from email_validator import EmailNotValidError, validate_email
from yaml import SafeDumper

from rip_validator.yaml_errors import validate_yaml_file

from .report import Report
from .status import State, Status
from .WAVES_config import ANSI, EMAIL_REGEX, License, SurveyName
from .auto_version import get_next_version

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

SafeDumper.add_representer(
    type(None),
    lambda dumper, _: dumper.represent_scalar("tag:yaml.org,2002:null", ""),
)


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
    }


def requires_not_none(field_param: str):
    """Decorator that checks a named parameter is not None before running validation."""

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            sig = inspect.signature(func)
            bound = sig.bind(*args, **kwargs)
            bound.apply_defaults()
            value = bound.arguments.get(field_param)

            if value is None:
                return Status(
                    State.FAIL,
                    f"'{field_param}' is missing or empty and is a required field.",
                )
            return func(*args, **kwargs)

        return wrapper

    return decorator


def requires_type(field_param: str):
    """Decorator that checks a named parameter matches its annotated type before running validation."""

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            sig = inspect.signature(func)
            bound = sig.bind(*args, **kwargs)
            bound.apply_defaults()
            value = bound.arguments.get(field_param)

            # Get the expected type from the type hint
            hints = typing.get_type_hints(func)
            expected_type = hints.get(field_param)

            if expected_type is not None and not isinstance(value, expected_type):
                return Status(
                    State.FAIL,
                    f"'{field_param}' must be of type {expected_type.__name__}, "
                    f"got {type(value).__name__}.",
                )
            return func(*args, **kwargs)

        return wrapper

    return decorator


@requires_not_none("description")
@requires_type("description")
def _validate_description(description: str) -> Status:
    return Status(State.PASS)


@requires_not_none("survey")
@requires_type("survey")
def _validate_survey(survey: str) -> Status:
    correct_names = [variant.value for variant in SurveyName]
    if survey not in correct_names:
        return Status(
            State.FAIL,
            f"'{survey}' is not a valid survey. Survey must be one of these: {correct_names}.",
        )
    return Status(State.PASS)


@requires_not_none("dataset")
@requires_type("dataset")
def _validate_dataset(dataset: str, rip_name: str) -> Status:
    """Validataes that the dataset is equal to the given rip_name."""
    if dataset != rip_name:
        return Status(
            State.FAIL,
            f"{dataset} is incorrect, it does not match the name of the directory. Suggest using '{rip_name}' instead.",
        )
    return Status(State.PASS)


@requires_not_none("author")
@requires_type("author")
def _validate_author(author: str) -> Status:
    match = EMAIL_REGEX.match(author)
    if not match:
        return Status(
            State.FAIL,
            f"'{author}' is not a valid author string. Author must be in the format 'Full Name <email@example.com>'.",
        )
    email = match.group("email")
    try:
        validate_email(email, check_deliverability=True)  # You need internet for DAML.
    except EmailNotValidError as e:
        return Status(State.FAIL, f"'{email}' is not a valid email in '{author}'. {e}")
    return Status(State.PASS)


def _validate_coauthors(coauthors: list[str] | None) -> Status:
    if not coauthors:
        return Status(State.PASS)
    bad_authors = []
    messages = []
    for author in coauthors:
        current_validation = _validate_author(author)
        if current_validation.state == State.FAIL:
            bad_authors.append(author)
            messages.append(current_validation.message)

    if len(bad_authors) == 1:
        return Status(
            State.FAIL,
            message=f"'{bad_authors[0]}' is not a valid author string: {messages[0]}.",
        )
    if len(bad_authors) > 1:
        return Status(
            State.FAIL,
            message=f"The following authors are not valid author strings:\n\t- {'\n\t- '.join(messages)}.",
        )
    return Status(State.PASS)


@requires_not_none("date")
@requires_type("date")
def _validate_date(date: str) -> Status:
    try:
        datetime.date.fromisoformat(date)
    except ValueError:
        return Status(State.FAIL, f"'{date}' is not a valid isoformat.")
    return Status(State.PASS)


@requires_not_none("license")
@requires_type("license")
def _validate_license(license: str) -> Status:
    accepted_licenses = [variant.value for variant in License]
    if license not in accepted_licenses:
        return Status(
            State.FAIL,
            f"license '{license}' is not an accepted license. License must be one of the following: {accepted_licenses}.",
        )
    return Status(State.PASS)


@requires_not_none("version")
@requires_type("version")
def _validate_version(version: int, rip_name: str) -> Status:
    correct_version = get_next_version(rip_name)
    if version != correct_version:
        return Status(
            State.FAIL,
            f"'{rip_name}' has the incorrect version: {version} should be {correct_version} to be consistent with the QC GitLab history.",
        )
    return Status(State.PASS)


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
        return Status(
            State.FAIL,
            f"Tables in DAML file are not consistent with the MAML files, they contain the following errors:\n\t- {'\n\t- '.join(all_error_messages)}",
        )
    return Status(State.PASS)


def _validate_extra_fields(raw_yaml: dict | None) -> Status:
    if raw_yaml is None:
        return Status(State.PASS)  # built from MAML, not from file
    extras = set(raw_yaml.keys()) - set(DAML_ORDER)
    if extras:
        return Status(
            State.FAIL,
            f"Unexpected field(s) in DAML: {sorted(extras)}. "
            f"Allowed fields are: {DAML_ORDER}.",
        )
    return Status(State.PASS)


def _validate_empty(raw_yaml: dict | None) -> Status:
    if raw_yaml is None:
        return Status(State.PASS)
    empty = []
    for key, value in raw_yaml.items():
        if key in DAML_REQUIRED:
            continue  # handled by dedicated validator
        if value is None or value == "" or value == [] or value == {}:
            empty.append(key)
    if empty:
        return Status(
            State.FAIL,
            f"Optional field(s) {empty} are present but empty. Remove them or provide a value.",
        )
    return Status(State.PASS)


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
            survey=_validate_survey(self.survey),
            dataset=_validate_dataset(self.dataset, rip_name),
            author=_validate_author(self.author),
            coauthors=_validate_coauthors(self.coauthors),
            date=_validate_date(self.date),
            description=_validate_description(self.description),
            license=_validate_license(self.license),
            version=_validate_version(self.version, rip_name),
            tables=_validate_tables(self.tables, maml_data),
            no_empty_optionals=_validate_empty(self._raw_yaml),
            no_extra_fields=_validate_extra_fields(self._raw_yaml),
        )

    @classmethod
    def from_maml_data(cls, maml_data: dict[str, dict], rip_name) -> Self:
        """Maml data is parsed and the daml is built from that. maml_data is obtained from read_maml in the rip_level_validator.py"""
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
        """Reads in a .daml file into a PreDAML object."""
        try:
            validate_yaml_file(file_name)
        except ValueError as e:
            print(f"{ANSI.RED}{file_name} not valid yaml{ANSI.RESET}", e)
            sys.exit()
        with open(file_name) as file:
            try:
                yaml_data = yaml.safe_load(file)
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
            yaml.safe_dump(
                no_nones,
                file,
                sort_keys=False,
                default_flow_style=False,
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
