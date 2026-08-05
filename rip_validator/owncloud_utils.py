"""
Module for interfacing with the Data Central cloud space. Data Central implements owncloud (https://owncloud.com/), so we use the owncloud Python library (https://github.com/owncloud/pyocclient)
"""

import os
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass

import keyring
import maskpass
import owncloud
import polars as pl
import requests

from .footer_handler import MAGIC, TAIL_SIZE
from .WAVES_config import ANSI
from .xxh_waves import NO_XXH, XXH_KEYWORD

QC_PATH = "./WAVES/QC/"
RIP_PATH = "./WAVES/RIPs/"
DATA_CENTRAL_URL = "https://cloud.datacentral.org.au"
CREDENTIAL_CHECK_TIMEOUT = 10.0
oc = owncloud.Client(DATA_CENTRAL_URL)


@dataclass
class FileChecksums:
    sha1: str | None = None
    xxh: str | None = None


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


def dav_root_url(username: str) -> str:
    """
    The WebDAV root of a Data Central user's own storage.
    """
    return f"{DATA_CENTRAL_URL}/remote.php/dav/files/{username}"


def _dav_url(username: str, directory: str, filename: str) -> str:
    directory = directory.strip("/").removeprefix("./").strip("/")
    return f"{dav_root_url(username)}/{directory}/{filename}"


def probe_data_central_auth(
    username: str, password: str, timeout: float = CREDENTIAL_CHECK_TIMEOUT
) -> int:
    """
    Asks Data Central whether these credentials authenticate, returning the raw
    HTTP status code so that the caller can tell the failure modes apart:

      207 - authenticated, the storage is there.
      401 - rejected. Wrong username or password, or the account needs an app
            password because it has two-factor authentication enabled.
      404 - authenticated, but the account has no storage under this username,
            which means the stored username does not match the account.

    Raises `requests.RequestException` if Data Central cannot be reached at all,
    which says nothing about whether the credentials are any good.
    """
    response = requests.request(
        "PROPFIND",
        f"{dav_root_url(username)}/",
        auth=(username, password),
        headers={"Depth": "0"},
        timeout=timeout,
    )
    return response.status_code


def _get_remote_file_size(url: str, auth: tuple[str, str]) -> int:
    """
    The size of a remote file in bytes, taken from the HEAD response.
    """
    response = requests.head(url, auth=auth, allow_redirects=True)
    response.raise_for_status()
    if "Content-Length" not in response.headers:
        raise RuntimeError("No Content-Length on HEAD; cannot locate the footer.")
    return int(response.headers["Content-Length"])


def _get_remote_byte_range(
    url: str, start: int, end: int, auth: tuple[str, str]
) -> bytes:
    """
    Fetches the bytes [start, end] (inclusive) of a remote file. Bails out if
    the server ignores the Range header, since the body would then be the
    entire file.
    """
    headers = {"Range": f"bytes={start}-{end}"}
    with requests.get(url, auth=auth, headers=headers, stream=True) as response:
        response.raise_for_status()
        if response.status_code != 206:
            raise RuntimeError(
                f"Server ignored the Range header (returned {response.status_code}); "
                "cannot read the footer remotely."
            )
        return response.content


def _fetch_parquet_footer(url: str, auth: tuple[str, str]) -> tuple[int, bytes]:
    """
    Returns the (file size, footer bytes) of a remote parquet file using two
    small range requests. A parquet file is laid out as
    `PAR1 <data> <thrift FileMetaData> <4-byte LE footer length> PAR1`.
    """
    size = _get_remote_file_size(url, auth)
    tail = _get_remote_byte_range(url, size - TAIL_SIZE, size - 1, auth)
    if tail[-len(MAGIC) :] != MAGIC:
        raise ValueError("Not a parquet file. Missing the magic PAR1 keyword.")
    footer_len = int.from_bytes(tail[:4], "little")
    footer = _get_remote_byte_range(url, size - TAIL_SIZE - footer_len, size - 1, auth)
    return size, footer


def _sparse_parquet_stub(size: int, footer: bytes) -> str:
    """
    Writes a sparse local file of `size` bytes containing only the leading
    magic and the footer, so that a parquet reader can open it. The hole in
    the middle costs essentially no disk. Returns the path of the stub, which
    is the caller's job to delete.
    """
    file_descriptor, path = tempfile.mkstemp(suffix=".parquet")
    with os.fdopen(file_descriptor, "r+b") as stub:
        stub.truncate(size)
        stub.write(MAGIC)
        stub.seek(size - len(footer))
        stub.write(footer)
    return path


def read_remote_parquet_metadata(url: str, auth: tuple[str, str]) -> dict[str, str]:
    """
    Reads the key-value metadata out of the footer of a remote parquet file
    without downloading the file itself.
    """
    size, footer = _fetch_parquet_footer(url, auth)
    stub_path = _sparse_parquet_stub(size, footer)
    try:
        return pl.read_parquet_metadata(stub_path)
    finally:
        os.unlink(stub_path)


def get_xxh_checksums_from_dc(
    directory: str, files: list[str]
) -> dict[str, str | None]:
    """
    Reads the WAVES xxh checksum out of the footer of each of the given remote
    parquet files. Only the footer is fetched, so nothing is downloaded. Files
    whose footer cannot be read, or which carry no xxh checksum, come back as
    `None`.
    """
    dc_credentials = get_data_central_credentials()
    assert dc_credentials.password
    assert dc_credentials.username

    auth = (dc_credentials.username, dc_credentials.password)
    checksums: dict[str, str | None] = {}

    for filename in files:
        url = _dav_url(dc_credentials.username, directory, filename)
        print(f"Reading the '{XXH_KEYWORD}' checksum from the footer of '{filename}'.")
        try:
            metadata = read_remote_parquet_metadata(url, auth)
        except (requests.RequestException, RuntimeError, ValueError, OSError) as err:
            print(
                f"{ANSI.RED}Could not read the footer of '{filename}': {err}{ANSI.RESET}"
            )
            checksums[filename] = None
            continue
        checksums[filename] = metadata.get(XXH_KEYWORD)

    return checksums


def calculate_checksums_from_dc(directory: str, files: list[str]) -> dict:
    """
    Manually streams the given files into the sha1sum function. This comes pre-installed in
    nearly all linux distros and on mac. Curl is also preinstalled on mac and linux.

    Parquet files are never streamed. They are validated with the xxh hash in
    their footer (see `get_xxh_checksums_from_dc`), so pulling them down would
    be a large download for nothing.
    """
    dc_credentials = get_data_central_credentials()
    assert dc_credentials.password
    assert dc_credentials.username

    checksums = {}

    for filename in files:
        if filename.endswith(".parquet"):
            continue

        url = _dav_url(dc_credentials.username, directory, filename)
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


def get_checksums(directory: str) -> dict[str, FileChecksums]:
    """
    Gets the checksums of every file in a directory.

    Parquet files are checksummed with the WAVES xxh hash stored in their
    footer, which is read remotely without downloading the file. Everything
    else uses SHA1: first OwnCloud's own stored checksums via PROPFIND, and
    then, for whatever is still missing, a manual stream through sha1sum.
    """
    sha1s = get_checksums_from_dc(directory)

    parquet_files = [name for name in sha1s if name.endswith(".parquet")]
    missing = [
        name
        for name, sha1 in sha1s.items()
        if sha1 is None and not name.endswith(".parquet")
    ]

    if missing:
        print(f"{len(missing)} file(s) missing checksums, calculating manually...")
        sha1s.update(calculate_checksums_from_dc(directory, missing))

    xxhs = get_xxh_checksums_from_dc(directory, parquet_files) if parquet_files else {}

    return {
        name: FileChecksums(sha1=sha1s.get(name), xxh=xxhs.get(name)) for name in sha1s
    }


def _parse_checksums_file(contents: str) -> dict[str, FileChecksums]:
    """
    Parses the contents of a `{prerip}.checksums` file produced by
    `valrip directory`. Lines starting with '#' are comments. Each data line
    is of the form `filename: sha1hash: xxhhash`, where the xxh hash is '0'
    for everything that isn't a parquet file. Sidecars written before the xxh
    hash existed carry only `filename: sha1hash`.
    """
    expected: dict[str, FileChecksums] = {}
    for raw_line in contents.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        fields = [field.strip() for field in line.split(":")]
        if len(fields) < 2:
            continue
        filename, sha1 = fields[0], fields[1]
        xxh = fields[2] if len(fields) > 2 else NO_XXH
        if not filename or not sha1:
            continue
        expected[filename] = FileChecksums(
            sha1=sha1, xxh=None if xxh == NO_XXH else xxh
        )
    return expected


def validate_checksums(
    prerip_name: str, computed: dict[str, FileChecksums]
) -> dict[str, FileChecksums]:
    """
    Compares the checksums computed from the cloud directory against the
    `{prerip_name}.checksums` sidecar file in the same QC directory.

    Parquet files are compared on their WAVES xxh hash, which is stored in the
    parquet footer; a parquet file without an xxh hash on either side fails.
    Every other file is compared on its SHA1.

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
        name: checksums for name, checksums in computed.items() if name != sidecar_name
    }

    expected_names = set(expected)
    computed_names = set(computed_for_compare)

    missing_from_cloud = sorted(expected_names - computed_names)
    extra_in_cloud = sorted(computed_names - expected_names)

    mismatched: list[tuple[str, str, str, str]] = []
    missing_xxh: list[str] = []
    for name in sorted(expected_names & computed_names):
        if name.endswith(".parquet"):
            algorithm = XXH_KEYWORD
            expected_hash = expected[name].xxh
            actual_hash = computed_for_compare[name].xxh
            if not expected_hash or not actual_hash:
                missing_xxh.append(name)
                continue
        else:
            algorithm = "SHA1"
            expected_hash = expected[name].sha1
            actual_hash = computed_for_compare[name].sha1
        if expected_hash != actual_hash:
            mismatched.append(
                (name, algorithm, expected_hash or "<none>", actual_hash or "<none>")
            )

    if missing_from_cloud or extra_in_cloud or mismatched or missing_xxh:
        print(
            f"{ANSI.RED}ERROR: Checksum validation failed for '{prerip_name}'.{ANSI.RESET}"
        )
        if mismatched:
            print(f"\n{ANSI.BOLD}Files with mismatched hashes:{ANSI.RESET}")
            for name, algorithm, expected_hash, actual_hash in mismatched:
                print(
                    f"  {name} ({algorithm})\n"
                    f"    expected: {expected_hash}\n"
                    f"    actual:   {actual_hash}"
                )
        if missing_xxh:
            print(
                f"\n{ANSI.BOLD}Parquet files without a '{XXH_KEYWORD}' checksum:{ANSI.RESET}"
            )
            for name in missing_xxh:
                print(f"  {name}")
            print(
                f"  Parquet files are validated with the '{XXH_KEYWORD}' hash written "
                f"into their footer, so one is required on both the local sidecar and "
                f"the uploaded file."
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
        file_checksums = checksums.get(file.get_name(), FileChecksums())
        current_metadata["sha1"] = file_checksums.sha1
        current_metadata["xxh"] = file_checksums.xxh
        all_metadata.append(current_metadata)
    return all_metadata
