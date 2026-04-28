"""
Module for handling the WAVES-specific flavor of MAML
Helper functions for building the metadata for the datasets.
"""

from pathlib import Path
import sys
import os
import yaml
from pydantic_core import ValidationError

from .helper_validator_methods import (
    format_waves_error_message,
    print_header,
    WHITESPACE_PADDING_LENGTH,
)
from .model_waves_maml import WavesMamlSchema
from .status import State, Status
from .WAVES_config import (
    SurveyName,
    License,
    ANSI,
    WAVESCustomExceptions,
    Author,
    Doi,
    Dependency,
    Columns,
    MinMax,
    ColumnMetaData,
    MamlMetaData,
)
from .yaml_errors import validate_yaml_file


def _split_author_string(author: str) -> Author:
    """
    Attempts to turn a string 'first last <first@somewhere.com>' into an Author object
    """
    words = author.split(" ")
    first_name = words[0]
    last_name = author[author.find(" ") : author.find("<")].strip()
    email = author.split("<")[-1].split(">")[0]
    return Author(first_name, last_name, email)


def _get_error_field_location(loc: tuple[int | str, ...]):
    """
    Gets a consistently styled output from pydantics "loc" field.
    See https://docs.pydantic.dev/latest/errors/errors/ for more details.

    :param loc: The "loc" entry of the pydantic ValidationError error object.
    """
    return f"> {loc[0]}"


def _print_correct_fields(verbose: bool, fields: list[str]):
    if verbose:
        for field in fields:
            field_loc = f"> {field}"
            print(
                f"\n{ANSI.BOLD}{field_loc.ljust(WHITESPACE_PADDING_LENGTH)}{ANSI.RESET}{ANSI.GREEN}✓ PASS{ANSI.RESET}"
            )


def _validate_table_matches_filename(maml_file: Path, maml_dict: dict) -> Status:
    """Checks that file.maml has 'file' as the table field in that maml."""
    maml_root_name = maml_file.stem
    current_table_name = maml_dict.get("table")
    if current_table_name != maml_root_name:
        return Status(
            State.FAIL,
            f"'{maml_file.name}' has 'table: {current_table_name}' "
            f"instead of 'table: {maml_root_name}'.",
        )
    return Status(State.PASS)


# This Loader is used to override pyyamls (overly eager) interpretation of some strings as dates.
# See https://stackoverflow.com/a/37958106 for more details.
class NoDatesSafeLoader(yaml.SafeLoader):
    @classmethod
    def remove_implicit_resolver(cls, tag_to_remove):
        """
        Remove implicit resolvers for a particular tag

        Takes care not to modify resolvers in super classes.

        We want to load datetimes as strings, not dates, because we
        go on to serialise as json which doesn't have the advanced types
        of yaml, and leads to incompatibilities down the track.
        """
        if "yaml_implicit_resolvers" not in cls.__dict__:
            cls.yaml_implicit_resolvers = cls.yaml_implicit_resolvers.copy()

        for first_letter, mappings in cls.yaml_implicit_resolvers.items():
            cls.yaml_implicit_resolvers[first_letter] = [
                (tag, regexp) for tag, regexp in mappings if tag != tag_to_remove
            ]


def _capture_unknown_error(file_path: Path, error_message: Exception) -> None:
    """
    Reads in the corrrupted file and combines the error message and file contents into error.log
    """
    with open(file_path, encoding="utf-8") as file:
        corrupted_contents = file.readlines()
    error_string = f"{error_message}"
    with open("error.log", "w", encoding="utf-8") as file:
        file.write("-----CONTENTS_START------\n")
        file.writelines(corrupted_contents)
        file.write("-----CONTENTS_END------\n")
        file.write("-----ERROR_STARTS------\n")
        file.write(error_string)
        file.write("\n-----ERROR_ENDS------\n")


def read_and_validate_maml(
    maml_file: Path, quiet=False, verbose=False
) -> MamlMetaData | None:
    """
    Reads in a maml file and parses it into a MetaData object, validating it in
    the process.
    """
    if not quiet:
        print_header("MAML Validation Report")
        print(f"\n{ANSI.BOLD}File Name:{ANSI.RESET} {maml_file}")

    if not os.path.isfile(maml_file):
        print(f"{ANSI.BOLD}{ANSI.RED} File Not Found: {maml_file}{ANSI.RESET}")
        return None

    try:
        validate_yaml_file(maml_file)
    except ValueError as e:
        print(e)
        sys.exit()

    with open(maml_file) as file:
        NoDatesSafeLoader.remove_implicit_resolver("tag:yaml.org,2002:timestamp")
        try:
            maml_dict = yaml.load(file, Loader=NoDatesSafeLoader)
        except Exception as e:
            _capture_unknown_error(maml_file, e)
            message = (
                f"{ANSI.RED}MAML file appears to not be valid YAML with an error that the team has not yet implemented validation for."
                f" Please ensure that file is valid YAML before continuing."
                f" An error log has been created called {ANSI.RESET}{ANSI.GREEN}'error.log'{ANSI.RESET}{ANSI.RED}."
                f" Please report the error by sharing the 'error.log' file in"
                f" a new issue the WAVES GitLab: {ANSI.RESET}{ANSI.YELLOW}(https://dev.aao.org.au/waves/twg6/rip-validator/-/issues){ANSI.RESET}"
            )
            print(message)
            print("\n")
            print(f"Error: {e}")
            sys.exit()

    filename_status = _validate_table_matches_filename(maml_file, maml_dict)

    pydantic_valid = True
    try:
        WavesMamlSchema.model_validate(maml_dict)
        if not quiet and filename_status.state == State.PASS:
            print(
                f"{ANSI.BOLD}Overall Status:{ANSI.RESET} {ANSI.GREEN}VALID{ANSI.RESET}"
            )
    except ValidationError as e:
        pydantic_valid = False
        if not quiet:
            print(
                f"{ANSI.BOLD}Overall Status:{ANSI.RESET} {ANSI.RED}INVALID{ANSI.RESET}"
            )
            print(f"\n{ANSI.BOLD}Validation Checks:{ANSI.RESET}")
            print(f"{'-' * 80}")

            error_fields = {}
            for exception in e.errors():
                field = exception["loc"][0]
                field_exceptions = [ex for ex in e.errors() if ex["loc"][0] == field]
                error_fields[field] = field_exceptions

            _print_correct_fields(verbose, maml_dict.keys() - error_fields.keys())

            for field in error_fields.keys():
                for exception in error_fields[field]:
                    if (
                        exception["type"] == "missing"
                        or exception["type"] == WAVESCustomExceptions.MISSING_EXCEPTION
                    ):
                        print(
                            f"\n{ANSI.BOLD}{_get_error_field_location(exception['loc']).ljust(WHITESPACE_PADDING_LENGTH)}{ANSI.RED}✗ FAIL{ANSI.RESET}"
                        )
                        print(
                            f"{ANSI.RED}→ Missing element. {exception['msg']}{ANSI.RESET}"
                        )
                    elif exception["type"] != WAVESCustomExceptions.LIST_EXCEPTION:
                        location = f"{_get_error_field_location(exception['loc'])}"
                        if exception["input"]:
                            location += f" ({exception['input']})"
                        print(
                            f"\n{ANSI.BOLD}{location.ljust(WHITESPACE_PADDING_LENGTH)}{ANSI.RED}✗ FAIL{ANSI.RESET}"
                        )
                        print(format_waves_error_message("", exception["msg"]))
                    else:
                        print(
                            f"\n{ANSI.BOLD}{_get_error_field_location(exception['loc']).ljust(WHITESPACE_PADDING_LENGTH)}{ANSI.RED}✗ FAIL{ANSI.RESET}"
                        )
                        print(f"{exception['msg']}")

    if filename_status.state == State.FAIL and not quiet:
        if pydantic_valid:
            print(
                f"{ANSI.BOLD}Overall Status:{ANSI.RESET} {ANSI.RED}INVALID{ANSI.RESET}"
            )
            print(f"\n{ANSI.BOLD}Validation Checks:{ANSI.RESET}")
            print(f"{'-' * 80}")
            _print_correct_fields(verbose, maml_dict.keys())
        location = "> table (filename match)"
        print(
            f"\n{ANSI.BOLD}{location.ljust(WHITESPACE_PADDING_LENGTH)}"
            f"{ANSI.RED}✗ FAIL{ANSI.RESET}"
        )
        print(f"{ANSI.RED}→ {filename_status.message}{ANSI.RESET}")

    if not pydantic_valid or filename_status.state == State.FAIL:
        return None

    if not quiet:
        _print_correct_fields(verbose, maml_dict.keys())

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
