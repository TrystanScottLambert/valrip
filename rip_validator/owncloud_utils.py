"""
Module for interfacing with the Data Central cloud space. Data Central implements owncloud (https://owncloud.com/), so we use the owncloud Python library (https://github.com/owncloud/pyocclient)
"""

import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass

import keyring
import maskpass
import owncloud
import requests

from .WAVES_config import ANSI

QC_PATH = "./WAVES/QC/"
RIP_PATH = "./WAVES/RIPs/"
DATA_CENTRAL_URL = "https://cloud.datacentral.org.au"
oc = owncloud.Client(DATA_CENTRAL_URL)


@dataclass
class OwnCloudCredentials:
    password: str | None
    username: str | None

    def __post_init__(self) -> None:
        if not self.username:
            request_data_central_username()
            self.username = keyring.get_password("valrip", "data_central_username")
        if not self.password:
            request_data_central_password()
            self.password = keyring.get_password("valrip", "data_central_password")


def request_data_central_password() -> None:
    password = maskpass.askpass(prompt="Enter Data Central Password: ")
    keyring.set_password("valrip", "data_central_password", password)


def request_data_central_username() -> None:
    username = input("Enter Data Central username: ")
    keyring.set_password("valrip", "data_central_username", username)


def get_data_central_credentials() -> OwnCloudCredentials:
    password = keyring.get_password("valrip", "data_central_password")
    username = keyring.get_password("valrip", "data_central_username")

    return OwnCloudCredentials(password=password, username=username)


def login_to_dc_cloud():
    """
    Saves the username and password to the .env file.
    """
    dc_credentials = get_data_central_credentials()
    try:
        oc.login(dc_credentials.username, dc_credentials.password)
    except owncloud.HTTPResponseError as err:
        raise ValueError(
            f"{err}. Credentials could be incorrect or there may be problems with the Data Central cloud. Try 'set_dc_cloud_credentials()' with the correct username and password and check the status of https://cloud.datacentral.org.au."
        )


def list_all_qc() -> list[str]:
    """
    List all current folders in the QC directory.
    """
    return [qc.name for qc in oc.list(QC_PATH)]


def list_all_rips() -> list[str]:
    """
    List all the current folders in the RIP Directory.
    """
    return [rip.name for rip in oc.list(RIP_PATH)]


def _parse_checksum_response(response: str) -> dict:
    """
    Parses the string response that we get into a structured dictionary of checksum values.
    """
    checksums = response.split(" ")
    checksum_dict = {
        checksum.split(":")[0]: checksum.split(":")[1] for checksum in checksums
    }
    return checksum_dict


def calculate_checksums_from_dc(directory: str, files: list[str]) -> dict:
    """
    Manually streams the given files into the sha1sum function. This comes pre-installed in
    nearly all linux distros and on mac. Curl is also preinstalled on mac and linux.
    """
    dc_credentials = get_data_central_credentials()
    assert dc_credentials.password
    assert dc_credentials.username

    base_url = f"https://cloud.datacentral.org.au/remote.php/dav/files/{dc_credentials.username}"

    checksums = {}

    for filename in files:
        url = f"{base_url}/{directory}/{filename}"
        print(f"Hashing '{filename}': ")

        result = subprocess.run(
            f"curl -# -u'{dc_credentials.username}:{dc_credentials.password}' '{url}' | sha1sum",
            shell=True,
            stdout=subprocess.PIPE,
            text=True,
        )

        if result.returncode == 0:
            sha1 = result.stdout.strip().split()[0]
            checksums[filename] = sha1
        else:
            checksums[filename] = None

    return checksums


def get_checksums_from_dc(directory: str) -> dict:
    """
    Scrapes the SHA1 checksums for the given directory via WebDAV PROPFIND.
    Returns {filename: sha1_hash} for files that have checksums,
    and {filename: None} for files that don't.
    """
    dc_credentials = get_data_central_credentials()
    assert dc_credentials.password
    assert dc_credentials.username
    url = (
        f"{DATA_CENTRAL_URL}/remote.php/dav/files/{dc_credentials.username}/{directory}"
    )
    xml_body = """<?xml version="1.0"?>
    <d:propfind xmlns:d="DAV:" xmlns:oc="http://owncloud.org/ns">
    <d:prop>
        <oc:checksums/>
    </d:prop>
    </d:propfind>
    """
    headers = {"Depth": "1", "Content-Type": "application/xml"}
    response = requests.request(
        "PROPFIND",
        url,
        headers=headers,
        data=xml_body,
        auth=(dc_credentials.username, dc_credentials.password),
    )
    response.raise_for_status()
    root = ET.fromstring(response.text)
    namespaces = {"d": "DAV:", "oc": "http://owncloud.org/ns"}
    checksums = {}
    for resp in root.findall("d:response", namespaces):
        href = resp.find("d:href", namespaces)
        checksum = resp.find(".//oc:checksum", namespaces)
        if href is not None:
            filename = href.text.split("/")[-1]
            if not filename:
                continue  # skip the directory entry itself
            if checksum is not None and checksum.text:
                parsed = _parse_checksum_response(checksum.text)
                checksums[filename] = parsed.get("SHA1")
            else:
                checksums[filename] = None
    return checksums


def get_checksums(directory: str) -> dict[str, str]:
    """
    Gets SHA1 checksums for all files in a directory. First tries to fetch them
    from OwnCloud's stored checksums via PROPFIND. Any files missing checksums
    are then calculated manually by streaming through sha1sum.
    """
    checksums = get_checksums_from_dc(directory)

    missing = [f for f, sha1 in checksums.items() if sha1 is None]

    if missing:
        print(f"{len(missing)} file(s) missing checksums, calculating manually...")
        calculated = calculate_checksums_from_dc(directory, missing)
        checksums.update(calculated)

    return checksums


def _parse_checksums_file(contents: str) -> dict[str, str]:
    """
    Parses the contents of a `{prerip}.checksums` file produced by
    `valrip directory`. Lines starting with '#' are comments. Each data line
    is of the form `filename: sha1hash`.
    """
    expected: dict[str, str] = {}
    for raw_line in contents.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        filename, sha1 = line.split(":", 1)
        expected[filename.strip()] = sha1.strip()
    return expected


def validate_checksums(prerip_name: str, computed: dict[str, str]) -> dict[str, str]:
    """
    Compares the SHA1 checksums computed from the cloud directory against the
    `{prerip_name}.checksums` sidecar file in the same QC directory.

    The sidecar must exist. If it does not, this function prints an error and
    calls `sys.exit()` — nothing should be submitted to GitLab without it.

    Every file in the cloud directory must appear in the sidecar with a
    matching hash, and vice-versa. The `.checksums` file itself is excluded
    from comparison (it does not list itself).
    """
    sidecar_name = f"{prerip_name}.checksums"
    remote_sidecar_path = f"{QC_PATH}{prerip_name}/{sidecar_name}"

    try:
        raw = oc.get_file_contents(remote_sidecar_path)
    except owncloud.HTTPResponseError:
        print(
            f"{ANSI.RED}ERROR: No '{sidecar_name}' file found in {QC_PATH}{prerip_name}.{ANSI.RESET}\n"
            f"Nothing will be submitted until the checksums sidecar exists. "
            f"Run {ANSI.BOLD}{ANSI.YELLOW}'valrip directory'{ANSI.RESET} on the local files "
            f"and upload the resulting '{sidecar_name}' to {QC_PATH}{prerip_name}."
        )
        sys.exit(1)

    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    expected = _parse_checksums_file(raw)

    # The sidecar does not list itself, so drop it
    computed_for_compare = {
        name: sha1 for name, sha1 in computed.items() if name != sidecar_name
    }

    expected_names = set(expected)
    computed_names = set(computed_for_compare)

    missing_from_cloud = sorted(expected_names - computed_names)
    extra_in_cloud = sorted(computed_names - expected_names)
    mismatched = sorted(
        name
        for name in expected_names & computed_names
        if expected[name] != computed_for_compare[name]
    )

    if missing_from_cloud or extra_in_cloud or mismatched:
        print(
            f"{ANSI.RED}ERROR: Checksum validation failed for '{prerip_name}'.{ANSI.RESET}"
        )
        if mismatched:
            print(f"\n{ANSI.BOLD}Files with mismatched SHA1 hashes:{ANSI.RESET}")
            for name in mismatched:
                print(
                    f"  {name}\n"
                    f"    expected: {expected[name]}\n"
                    f"    actual:   {computed_for_compare[name]}"
                )
        if missing_from_cloud:
            print(
                f"\n{ANSI.BOLD}Files listed in '{sidecar_name}' but missing from the cloud:{ANSI.RESET}"
            )
            for name in missing_from_cloud:
                print(f"  {name}")
        if extra_in_cloud:
            print(
                f"\n{ANSI.BOLD}Files in the cloud but not listed in '{sidecar_name}':{ANSI.RESET}"
            )
            for name in extra_in_cloud:
                print(f"  {name}")
        print(
            f"\nNothing will be submitted until this is resolved. Re-run "
            f"{ANSI.BOLD}{ANSI.YELLOW}'valrip directory'{ANSI.RESET} on the local files "
            f"and re-upload the directory to {QC_PATH}{prerip_name}."
        )
        sys.exit(1)

    return expected


def download_trackable_data(prerip_name: str, dest_dir: str) -> list[str]:
    """
    Downloads all non-`.parquet` files from the pre-rip's QC directory into
    `dest_dir`. This includes the `.checksums` file.
    """
    files = oc.list(f"{QC_PATH}{prerip_name}")
    if files is None:
        print(f"No files found in {QC_PATH}{prerip_name}")
        return []

    non_parquet_files = [f for f in files if not f.get_name().endswith(".parquet")]

    if not non_parquet_files:
        print(f"No trackable (non-.parquet) files found in {prerip_name}")
        return []

    os.makedirs(dest_dir, exist_ok=True)
    downloaded_paths: list[str] = []

    for file in non_parquet_files:
        remote_path = f"{QC_PATH}{prerip_name}/{file.get_name()}"
        local_path = os.path.join(dest_dir, file.get_name())
        oc.get_file(remote_path, local_path)
        downloaded_paths.append(os.path.abspath(local_path))
        print(f"Downloaded {file.get_name()} -> {local_path}")

    return downloaded_paths


def get_metadata_from_prerip(prerip_name: str) -> list[dict] | None:
    """
    Scrapes the metadata of all the files in the given directory.
    """
    login_to_dc_cloud()
    try:
        files = oc.list(f"{QC_PATH}{prerip_name}")
    except owncloud.HTTPResponseError as e:
        if e.status_code == 404:
            return
        raise
    if not files:
        return

    checksums = get_checksums(f"{QC_PATH}{prerip_name}")

    all_metadata = []
    for file in files:
        current_metadata = {}
        current_metadata["etag"] = file.get_etag()
        current_metadata["file_name"] = file.get_name()
        current_metadata["modified"] = str(file.get_last_modified())
        current_metadata["directory"] = file.get_path()
        current_metadata["sha1"] = checksums.get(file.get_name())
        all_metadata.append(current_metadata)
    return all_metadata
