"""
Module for meta-data YAML (MAML) handling.
"""

import dataclasses
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import ClassVar, Self

import yaml

from rip_validator.yaml_convience_functions import NoDatesSafeLoader
from rip_validator.yaml_errors import validate_yaml_file

from .helper_validator_methods import (
    is_blank,
    optional_list,
    requires_not_none,
    requires_type,
    validate_author,
    validate_coauthors,
    validate_date,
    validate_description,
    validate_empty_optionals,
    validate_license,
    validate_order,
    validate_survey,
)
from .report import Report
from .status import Status
from .ucd_validator import validate_ucd
from .column_name_validator import validate_table_name, validate_field_names
from .WAVES_config import (
    ANSI,
    MAML_VERSION,
    ColumnMetaData,
    Columns,
    Dependency,
    Doi,
    License,
    MinMax,
    SurveyName,
    WAVESDataTypes,
)

MAML_ORDER = [
    "survey",
    "dataset",
    "table",
    "version",
    "date",
    "author",
    "coauthors",
    "DOIs",
    "depends",
    "description",
    "comments",
    "license",
    "keywords",
    "MAML_version",
    "fields",
]

MAML_REQUIRED = [
    "survey",
    "dataset",
    "table",
    "version",
    "date",
    "author",
    "description",
    "license",
    "MAML_version",
    "fields",
]

DOI_ALLOWED_KEYS = {"DOI", "type"}
DEPENDS_ALLOWED_KEYS = {"survey", "dataset", "table", "version"}
FIELD_ALLOWED_KEYS = {"name", "unit", "info", "ucd", "data_type", "qc"}
QC_ALLOWED_KEYS = {"min", "max"}


@dataclass
class MAMLReport(Report):
    survey: Status
    dataset: Status
    table: Status
    table_name: Status
    table_matches_filename: Status
    version: Status
    date: Status
    author: Status
    coauthors: Status
    DOIs: Status
    depends: Status
    description: Status
    comments: Status
    license: Status
    keywords: Status
    MAML_version: Status
    fields: Status
    field_names: Status
    no_extra_fields: Status
    no_empty_optionals: Status
    keys_in_order: Status

    TITLE: ClassVar[str] = "MAML Validation Report"
    CHECK_LABELS: ClassVar[dict[str, str]] = {
        "survey": "Valid survey name:",
        "dataset": "Dataset name present:",
        "table": "Table name present:",
        "table_name": "Table name valid:",
        "table_matches_filename": "Table name matches filename:",
        "version": "Version is integer:",
        "date": "Date valid iso format:",
        "author": "Author is correctly formatted:",
        "coauthors": "Coauthors are correctly formatted:",
        "DOIs": "DOIs are valid:",
        "depends": "Dependencies are valid:",
        "description": "Description is present:",
        "comments": "Comments are valid:",
        "license": "License:",
        "keywords": "Keywords are valid:",
        "MAML_version": "MAML version is correct:",
        "fields": "Fields are valid:",
        "field_names": "Field names are valid:",
        "no_extra_fields": "No extra fields:",
        "no_empty_optionals": "Optional fields aren't empty:",
        "keys_in_order": "Fields are in the correct order:",
    }


@requires_not_none("dataset")
@requires_type("dataset")
def _validate_dataset(dataset: str) -> Status:
    """MAML only requires that dataset is a non-empty string. The DAML check
    that it matches the RIP name is handled at the DAML layer."""
    if not dataset:
        return Status.failed("'dataset' is missing or empty and is a required field.")
    return Status.passed()


@requires_not_none("table")
@requires_type("table")
def _validate_table(table: str) -> Status:
    if not table:
        return Status.failed("'table' is missing or empty and is a required field.")
    return Status.passed()


def _validate_table_name(table_name: Path) -> Status:
    return validate_table_name(table_name)


def _validate_table_matches_filename(maml_file: Path, raw_yaml: dict | None) -> Status:
    """Checks that <name>.maml has 'name' as the table field in that MAML."""
    if raw_yaml is None:
        return Status.passed()
    expected = maml_file.stem
    actual = raw_yaml.get("table")
    if actual != expected:
        return Status.failed(
            f"'{maml_file.name}' has 'table: {actual}' instead of 'table: {expected}'."
        )
    return Status.passed()


@requires_not_none("version")
def _validate_version(version: int) -> Status:
    """Mirror pydantic's StrictInt: reject anything that isn't a plain int.
    Note: bool is an int subclass in Python, so it must be rejected explicitly."""
    if isinstance(version, bool) or not isinstance(version, int):
        return Status.failed(
            f"'version' must be of type int, got {type(version).__name__}."
        )
    return Status.passed()


@requires_not_none("MAML_version")
@requires_type("MAML_version")
def _validate_maml_version(MAML_version: float) -> Status:
    if MAML_version != MAML_VERSION:
        return Status.failed(
            f"MAML_version should be {MAML_VERSION}, got {MAML_version}."
        )
    return Status.passed()


@optional_list("DOIs")
def _validate_dois(DOIs: list[dict] | None) -> Status:
    """DOIs is optional — None passes. If present, must be a non-empty list
    of dicts each with non-empty 'DOI' and 'type' fields."""

    errors = []
    for i, doi in enumerate(DOIs, start=1):
        if not doi:
            errors.append(f"DOIs[{i}]: entry is empty.")
            continue
        if not isinstance(doi, dict):
            errors.append(f"DOIs[{i}]: must be a DOI object.")
            continue
        if not doi.get("DOI"):
            errors.append(f"DOIs[{i}]: 'DOI' field is required.")
        if not doi.get("type"):
            errors.append(f"DOIs[{i}]: 'type' field is required.")
        extras = set(doi.keys()) - DOI_ALLOWED_KEYS
        if extras:
            errors.append(f"DOIs[{i}]: unexpected fields {sorted(extras)}.")

    if errors:
        return Status.failed(
            f"'DOIs' has the following errors:\n\t- {'\n\t- '.join(errors)}"
        )
    return Status.passed()


@optional_list("depends")
def _validate_depends(depends: list[dict] | None) -> Status:
    """depends is optional. If present, must be a non-empty list of dicts each
    with non-empty 'survey', 'dataset', 'table', and 'version' fields."""
    errors = []
    for i, dep in enumerate(depends, start=1):
        if not dep:
            errors.append(f"depends[{i}]: entry is empty.")
            continue
        if not isinstance(dep, dict):
            errors.append(f"depends[{i}]: must be a depend object.")
            continue
        for required_key in ("survey", "dataset", "table", "version"):
            if not dep.get(required_key):
                errors.append(f"depends[{i}]: '{required_key}' field is required.")
        extras = set(dep.keys()) - DEPENDS_ALLOWED_KEYS
        if extras:
            errors.append(f"depends[{i}]: unexpected fields {sorted(extras)}.")

    if errors:
        return Status.failed(
            f"'depends' has the following errors:\n\t- {'\n\t- '.join(errors)}"
        )
    return Status.passed()


@optional_list("comments")
def _validate_comments(comments: list[str] | None) -> Status:
    """comments is optional. If present, must be a non-empty list of non-empty strings."""
    errors = []
    for i, comment in enumerate(comments, start=1):
        if not comment:
            errors.append(f"comments[{i}]: entry is empty.")
    if errors:
        return Status.failed(
            f"'comments' has the following errors:\n\t- {'\n\t- '.join(errors)}"
        )
    return Status.passed()


@optional_list("keywords")
def _validate_keywords(keywords: list[str] | None) -> Status:
    """keywords is optional. If present, must be a list of non-empty strings.
    The original pydantic schema didn't enforce element non-emptiness here,
    but it's consistent with `comments` and harmless to add."""
    errors = []
    for i, keyword in enumerate(keywords, start=1):
        if not keyword:
            errors.append(f"keywords[{i}]: entry is empty.")
    if errors:
        return Status.failed(
            f"'keywords' has the following errors:\n\t- {'\n\t- '.join(errors)}"
        )
    return Status.passed()


def _validate_fields(fields: list[dict]) -> Status:
    """The 'fields' validator is the most involved. It checks:
    1. fields is a non-empty list of dicts,
    2. each dict has the required keys (name, unit, info, ucd, data_type),
    3. ucd validates via astropy,
    4. data_type is one of WAVESDataTypes,
    5. qc, if present, is type-consistent with data_type and has min and max,
    6. no duplicate field names.
    """
    if fields is None:
        return Status.failed("'fields' is missing or empty and is a required field.")
    if not isinstance(fields, list):
        return Status.failed(f"'fields' must be a list, got {type(fields).__name__}.")

    if len(fields) == 0:
        return Status.failed("'fields' is present but empty.")

    errors = []
    seen_names: dict[str, list[int]] = {}

    for i, _field in enumerate(fields, start=1):
        prefix = f"fields[{i}]"
        if not _field:
            errors.append(f"{prefix}: entry is empty.")
            continue
        if not isinstance(_field, dict):
            errors.append(f"{prefix}: must be a field object.")
            continue

        name = _field.get("name")
        named_prefix = f"fields[{i}] ('{name}')" if name else prefix

        for key in ("name", "unit", "info", "ucd", "data_type"):
            if not _field.get(key):
                errors.append(f"{named_prefix}: '{key}' field is required.")

        if name:
            if name in seen_names:
                errors.append(
                    f"{named_prefix}: duplicate field name (also at indices {seen_names[name]})."
                )
            seen_names.setdefault(name, []).append(i)

        if _field.get("ucd"):
            try:
                validate_ucd(_field["ucd"])
            except ValueError as e:
                errors.append(f"{named_prefix}: invalid UCD '{_field['ucd']}': {e}")

        dtype = _field.get("data_type")
        if dtype and dtype not in WAVESDataTypes:
            valid = [e.value for e in WAVESDataTypes]
            errors.append(
                f"{named_prefix}: data_type must be one of {valid}, got '{dtype}'."
            )

        # qc is optional, but if the key is present it must have a value.
        if "qc" in _field:
            if is_blank(_field["qc"]):
                errors.append(
                    f"{named_prefix}: 'qc' is present but empty — "
                    f"either remove it or provide both 'min' and 'max'."
                )
            else:
                errors.extend(_validate_qc(_field["qc"], dtype, named_prefix))

        extras = set(_field.keys()) - FIELD_ALLOWED_KEYS
        if extras:
            errors.append(f"{named_prefix}: unexpected fields {sorted(extras)}.")

    if errors:
        return Status.failed(
            f"'fields' has the following errors:\n\t- {'\n\t- '.join(errors)}"
        )
    return Status.passed()


def _validate_field_names(fields: list[dict[str, str]]) -> Status:
    field_names = [_field.get("name") for _field in fields]
    return validate_field_names(field_names)


def _validate_qc(qc, dtype: str | None, prefix: str) -> list[str]:
    """Returns a list of qc-related error strings (empty list if all good).

    - qc is only allowed on numeric fields,
    - both min and max must be present and have values,
    - qc value types must match the field's data_type.
    """
    errors: list[str] = []
    if not isinstance(qc, dict):
        errors.append(f"{prefix}: qc must be an object with 'min' and 'max'.")
        return errors

    extras = set(qc.keys()) - QC_ALLOWED_KEYS
    if extras:
        errors.append(f"{prefix}: qc has unexpected fields {sorted(extras)}.")

    # Catches both "key absent" and "key present but blank". Use `is None`
    # rather than falsy so a legitimate value of 0 isn't misread as missing.
    if qc.get("min") is None or qc.get("max") is None:
        missing = [k for k in ("min", "max") if qc.get(k) is None]
        errors.append(f"{prefix}: qc {missing} must be present and have a value.")
        return errors

    if dtype and dtype not in WAVESDataTypes.numeric():
        errors.append(
            f"{prefix}: qc only allowed on numeric fields, this field is type '{dtype}'."
        )
        return errors

    if dtype in WAVESDataTypes.integer():
        if isinstance(qc["min"], float) or isinstance(qc["max"], float):
            errors.append(
                f"{prefix}: field is integer type ({dtype}) but qc value(s) are float — types must match."
            )
    elif dtype in WAVESDataTypes.floating_point():
        # bool is an int subclass; treat plain ints as a mismatch but ignore bools.
        min_is_int = isinstance(qc["min"], int) and not isinstance(qc["min"], bool)
        max_is_int = isinstance(qc["max"], int) and not isinstance(qc["max"], bool)
        if min_is_int or max_is_int:
            errors.append(
                f"{prefix}: field is float type ({dtype}) but qc value(s) are integer — types must match."
            )

    return errors


def _validate_no_extra_fields(raw_yaml: dict | None) -> Status:
    if raw_yaml is None:
        return Status.passed()
    extras = set(raw_yaml.keys()) - set(MAML_ORDER)
    if extras:
        return Status.failed(
            f"Unexpected field(s) in MAML: {sorted(extras)}. Allowed fields are: {MAML_ORDER}."
        )
    return Status.passed()


def _capture_unknown_error(file_path: Path, error_message: Exception) -> None:
    """Reads in the corrupted file and writes contents + error to error.log."""
    with open(file_path, encoding="utf-8") as file:
        corrupted_contents = file.readlines()
    with open("error.log", "w", encoding="utf-8") as file:
        file.write("-----CONTENTS_START------\n")
        file.writelines(corrupted_contents)
        file.write("-----CONTENTS_END------\n")
        file.write("-----ERROR_STARTS------\n")
        file.write(f"{error_message}")
        file.write("\n-----ERROR_ENDS------\n")


def _load_maml_yaml(file_name: Path) -> dict:
    """Validates and loads a MAML file, exiting with a friendly message on failure."""
    try:
        validate_yaml_file(file_name)
    except ValueError as e:
        print(e)
        sys.exit()

    with open(file_name) as file:
        try:
            yaml_data = yaml.load(file, Loader=NoDatesSafeLoader)
        except Exception as e:
            _capture_unknown_error(file_name, e)
            print(
                f"{ANSI.RED}MAML file appears to not be valid YAML with an error that the team has not yet implemented validation for."
                f" Please ensure that file is valid YAML before continuing."
                f" An error log has been created called {ANSI.RESET}{ANSI.GREEN}'error.log'{ANSI.RESET}{ANSI.RED}."
                f" Please report the error by sharing the 'error.log' file in"
                f" a new issue on the WAVES GitLab: {ANSI.RESET}{ANSI.YELLOW}(https://dev.aao.org.au/waves/twg6/rip-validator/-/issues){ANSI.RESET}"
            )
            print(f"\nError: {e}")
            sys.exit()

    if not isinstance(yaml_data, dict):
        print(
            f"{ANSI.RED}{file_name} is not valid YAML. Expected a mapping at the top level.{ANSI.RESET}"
        )
        sys.exit()

    return yaml_data


@dataclass
class MAMLMetaData:
    survey: SurveyName
    dataset: str
    table: str
    version: int
    author: str
    description: str
    maml_version: float
    fields: Columns
    date: str = str(datetime.today()).split(" ")[0]
    coauthors: list[str] | None = None
    dois: list[Doi] | None = None
    depends: list[Dependency] | None = None
    comments: list[str] | None = None
    license: License = License.PRIVATE
    keywords: list[str] | None = None


@dataclass
class PreMAML:
    survey: str
    dataset: str
    table: str
    version: int
    date: str
    author: str
    coauthors: list[str] | None
    DOIs: list[dict] | None
    depends: list[dict] | None
    description: str
    comments: list[str] | None
    license: str
    keywords: list[str] | None
    MAML_version: float
    fields: list[dict]
    _raw_yaml: dict | None = field(default=None, repr=False)
    _maml_file: Path | None = field(default=None, repr=False)

    def validate(self) -> MAMLReport:
        assert (
            self._maml_file
        )  # I'm not sure if this can ever be none but we should check.
        return MAMLReport(
            survey=validate_survey(self.survey),
            dataset=_validate_dataset(self.dataset),
            table=_validate_table(self.table),
            table_name=_validate_table_name(self._maml_file),
            table_matches_filename=_validate_table_matches_filename(
                self._maml_file, self._raw_yaml
            )
            if self._maml_file is not None
            else Status.passed(),
            version=_validate_version(self.version),
            date=validate_date(self.date),
            author=validate_author(self.author),
            coauthors=validate_coauthors(self.coauthors),
            DOIs=_validate_dois(self.DOIs),
            depends=_validate_depends(self.depends),
            description=validate_description(self.description),
            comments=_validate_comments(self.comments),
            license=validate_license(self.license),
            keywords=_validate_keywords(self.keywords),
            MAML_version=_validate_maml_version(self.MAML_version),
            fields=_validate_fields(self.fields),
            field_names=_validate_field_names(self.fields),
            no_extra_fields=_validate_no_extra_fields(self._raw_yaml),
            no_empty_optionals=validate_empty_optionals(self._raw_yaml, MAML_REQUIRED),
            keys_in_order=validate_order(self._raw_yaml, MAML_ORDER),
        )

    @classmethod
    def from_file(cls, file_name: Path) -> Self:
        """Reads a .maml file into a PreMAML object."""
        yaml_data = _load_maml_yaml(file_name)

        fields = {f.name for f in dataclasses.fields(cls)}
        instance = cls(
            **{f: yaml_data.get(f, None) for f in fields if not f.startswith("_")}  # type: ignore[arg-type]
        )
        instance._raw_yaml = yaml_data
        instance._maml_file = file_name
        return instance

    def to_metadata(self) -> MAMLMetaData:
        """Builds a MAMLMetaData from a validated PreMAML.

        Should only be called when validate().is_valid is True; it assumes the
        required fields are present and well-formed.
        """
        coauthors: list[str] | None = None
        if self.coauthors:
            coauthors = []
            for coauthor in self.coauthors:
                coauthors.append(coauthor)
            if not coauthors:
                coauthors = None

        dois = [Doi(d["DOI"], d["type"]) for d in self.DOIs] if self.DOIs else None

        depends = (
            [
                Dependency(d["survey"], d["dataset"], d["table"], d["version"])
                for d in self.depends
            ]
            if self.depends
            else None
        )

        columns = Columns({})
        for f in self.fields:
            qc = MinMax(f["qc"]["min"], f["qc"]["max"]) if f.get("qc") else None
            columns.columns[f["name"]] = ColumnMetaData(
                name=f["name"],
                unit=f["unit"],
                info=f["info"],
                ucd=f["ucd"],
                data_type=f["data_type"],
                qc=qc,
            )

        return MAMLMetaData(
            survey=SurveyName(self.survey),
            dataset=self.dataset,
            table=self.table,
            version=self.version,
            date=self.date,
            author=self.author,
            coauthors=coauthors,
            dois=dois,
            depends=depends,
            description=self.description,
            comments=self.comments,
            license=License(self.license),
            keywords=self.keywords,
            maml_version=self.MAML_version,
            fields=columns,
        )


def read_and_validate_maml(
    maml_file: Path, quiet: bool = False, verbose: bool = False
) -> MAMLMetaData | None:
    """Reads a MAML file, validates it, and returns a MAMLMetaData if valid."""
    if not maml_file.is_file():
        print(f"{ANSI.BOLD}{ANSI.RED} File Not Found: {maml_file}{ANSI.RESET}")
        return

    pre_maml = PreMAML.from_file(maml_file)
    report = pre_maml.validate()

    if not quiet:
        print(f"\n{ANSI.BOLD}File Name:{ANSI.RESET} {maml_file}")
        report.print_report(verbose=verbose)

    if not report.is_valid:
        return

    return pre_maml.to_metadata()
