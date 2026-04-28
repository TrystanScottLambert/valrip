"""
Module to validate an entire RIP-level product.
"""

from pathlib import Path
from typing import ClassVar
import os
from dataclasses import dataclass
import yaml
from .status import Status, State
from .report import Report
from .auto_version import get_next_table_versions, sha1_checksum


@dataclass
class DirectoryReport(Report):
    rip_name: str
    maml_files: Status
    parquet_files: Status
    markdown_files: Status
    additional_files: Status
    consistent_rip_name: Status
    table_versions: Status

    TITLE: ClassVar[str] = "RIP-level Validation Report"
    CHECK_LABELS: ClassVar[dict[str, str]] = {
        "maml_files": "All maml files have parquet:",
        "parquet_files": "All parquet files have maml:",
        "markdown_files": "Markdown files have parquet or RIP:",
        "additional_files": "No extra files:",
        "consistent_rip_name": "Correct RIP name in mamls:",
        "table_versions": "Table versions are consistent with remote versions:",
    }


@dataclass
class Files:
    maml_files: list[str]
    parquet_files: list[str]
    markdown_files: list[str]
    extra_files: list[str]

    def check_all_maml_has_parquet(self) -> Status:
        if len(self.maml_files) == 0:
            return Status(State.FAIL, "No maml files")
        extra_maml = []
        for maml_file in self.maml_files:
            if maml_file.replace(".maml", ".parquet") not in self.parquet_files:
                extra_maml.append(maml_file)
        if len(extra_maml) != 0:
            return Status(
                State.FAIL,
                f"These maml files don't have corresponding parquet files: {extra_maml}",
            )
        return Status(State.PASS)

    def check_all_parquet_has_maml(self) -> Status:
        if len(self.parquet_files) == 0:
            return Status(State.FAIL, "No parquet files")
        extra_parquet = []
        for parquet_file in self.parquet_files:
            if parquet_file.replace(".parquet", ".maml") not in self.maml_files:
                extra_parquet.append(parquet_file)
        if len(extra_parquet) != 0:
            return Status(
                State.FAIL,
                f"These parquet files don't have corresponding maml files: {extra_parquet}",
            )
        return Status(State.PASS)

    def check_markdown_files(self, rip_name: str) -> Status:
        notes_file = f"{rip_name}.md"
        if notes_file not in self.markdown_files:
            return Status(State.FAIL, f"Missing RIP notes file: {notes_file}")

        extra_markdown = []
        for markdown_file in self.markdown_files:
            if (
                markdown_file.replace(".md", ".parquet") not in self.parquet_files
                and markdown_file != notes_file
            ):
                extra_markdown.append(markdown_file)
        if len(extra_markdown) != 0:
            return Status(
                State.FAIL,
                f"These md files don't have corresponding parquet files: {extra_markdown}",
            )
        return Status(State.PASS)

    def check_extra_files(self, rip_name: str) -> Status:
        local_files = self.extra_files
        checksum_file = f"{rip_name}.checksums"
        daml_file = f"{rip_name}.daml"
        if checksum_file in local_files:
            local_files.remove(checksum_file)
        if daml_file in local_files:
            local_files.remove(daml_file)
        if len(local_files) != 0:
            return Status(
                State.FAIL,
                f"There are extra files that should not be in a RIP: {local_files}",
            )
        return Status(State.PASS)


def get_files(directory: Path) -> Files:
    all_files = os.listdir(directory)
    maml_files, parquet_files, markdown_files, extra_files = (
        [],
        [],
        [],
        [],
    )
    for file in all_files:
        match file.split(".")[-1]:
            case "maml":
                maml_files.append(file)
            case "parquet":
                parquet_files.append(file)
            case "md":
                markdown_files.append(file)
            case _:
                extra_files.append(file)

    return Files(maml_files, parquet_files, markdown_files, extra_files)


def check_directory(directory: Path) -> DirectoryReport:
    rip_name = directory.resolve().name
    files = get_files(directory)
    maml_data = read_in_maml(directory)

    return DirectoryReport(
        rip_name,
        files.check_all_maml_has_parquet(),
        files.check_all_parquet_has_maml(),
        files.check_markdown_files(rip_name),
        files.check_extra_files(rip_name),
        check_dataset_name_in_mamls(rip_name, maml_data),
        check_table_versions(rip_name, maml_data, directory),
    )


def read_in_maml(directory: Path) -> dict[str, dict]:
    """Helper function to load in maml files as dictionary objects using the yaml loader."""
    all_files = os.listdir(directory)
    maml_files = [file for file in all_files if file.endswith(".maml")]
    loaded_files = {}
    for maml_file in maml_files:
        with open(directory / maml_file) as file:
            loaded_files[maml_file] = yaml.safe_load(file)
    return loaded_files


def check_table_versions(
    rip_name: str,
    loaded_maml_files: dict[str, dict],
    directory: Path,
) -> Status:
    """Checks that each MAML's declared table version matches the version on Gitlab."""
    expected = get_next_table_versions(rip_name, loaded_maml_files, directory)
    current = {
        maml_content["table"]: maml_content["version"]
        for maml_content in loaded_maml_files.values()
    }

    mismatches = []
    for table_name, expected_version in expected.items():
        actual_version = current.get(table_name)
        if actual_version != expected_version:
            mismatches.append(
                f"'{table_name}' has the incorrect version: {actual_version} should be {expected_version} to be consistent with the QC GitLab history."
            )

    if mismatches:
        return Status(
            State.FAIL,
            "The following tables have incorrect versions:\n\t- "
            + "\n\t- ".join(mismatches),
        )
    return Status(State.PASS)


def check_dataset_name_in_mamls(
    rip_name: str, loaded_maml_files: dict[str, dict]
) -> Status:
    bad_mamls = []
    for maml_name, loaded_maml in loaded_maml_files.items():
        if loaded_maml["dataset"] != rip_name:
            bad_mamls.append(maml_name)

    if len(bad_mamls) != 0:
        return Status(
            State.FAIL,
            f"The following maml files do not have '{rip_name}' as the dataset value: {bad_mamls}",
        )
    return Status(State.PASS)


def build_submission_report(directory: Path) -> None:
    """Creates the checksum report for all the files in the directory"""
    all_files = os.listdir(directory)
    rip_name = directory.resolve().name
    checksum_name = directory / f"{rip_name}.checksums"
    if os.path.exists(checksum_name):
        all_files.remove(str(checksum_name.name))
        os.remove(checksum_name)
    with open(checksum_name, "w") as file:
        file.write(
            "# This file is automatically generated upon a successful valrip directory command.\n"
        )
        file.write("# !!DO NOT EDIT THIS FILE BY HAND!!\n")
        file.write(
            f"# Make sure to upload this file to WAVES/QC/{rip_name} along with the rest of the directory\n"
        )
        for current_file in all_files:
            checksum = sha1_checksum(directory / current_file)
            file.write(f"{current_file}: {checksum}\n")
