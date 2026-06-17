"""
Module for handling the gitlab pushes, MRs and credentials
"""

import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime

import keyring

from .owncloud_utils import (
    download_trackable_data,
    get_metadata_from_prerip,
    list_all_qc,
    login_to_dc_cloud,
    validate_checksums,
)
from .settings_config import QC_LEAD_USER_NAME, RIP_DIRECTORY_NAME
from .WAVES_config import ANSI

_VERSION_DIR_RE = re.compile(r"^v(\d+)$")


@dataclass
class GitLabCredentials:
    token: str | None
    email: str | None
    username: str | None

    def __post_init__(self) -> None:
        if not self.token:
            request_gitlab_token()
            self.token = keyring.get_password("valrip", "gitlab_token")

        if not self.email:
            request_gitlab_email()
            self.email = keyring.get_password("valrip", "gitlab_email")

        if not self.username:
            request_gitlab_username()
            self.username = keyring.get_password("valrip", "gitlab_username")


def request_gitlab_token() -> None:
    token = input("Enter WAVES git-bot token: ")
    keyring.set_password("valrip", "gitlab_token", token)


def request_gitlab_email() -> None:
    email = input("Enter WAVES GitLab email: ")
    keyring.set_password("valrip", "gitlab_email", email)


def request_gitlab_username() -> None:
    username = input(
        "Enter WAVES GitLab username (this is usually your email without the @ part): "
    )
    keyring.set_password("valrip", "gitlab_username", username)


def get_gitlab_credentials() -> GitLabCredentials:
    token = keyring.get_password("valrip", "gitlab_token")
    email = keyring.get_password("valrip", "gitlab_email")
    username = keyring.get_password("valrip", "gitlab_username")

    return GitLabCredentials(token=token, email=email, username=username)


def run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    """Run a command and raise on failure."""
    return subprocess.run(cmd, check=True, text=True, capture_output=True, **kwargs)


def format_metadata_table(metadata: list[dict]) -> str:
    headers = list(dict.fromkeys(h for row in metadata for h in row))
    col_widths = {
        h: max(len(h), max((len(str(row.get(h, ""))) for row in metadata), default=0))
        for h in headers
    }

    header_row = " | ".join(h.ljust(col_widths[h]) for h in headers)
    separator = "-+-".join("-" * col_widths[h] for h in headers)

    data_rows = [
        " | ".join(str(row.get(h, "")).ljust(col_widths[h]) for h in headers)
        for row in metadata
    ]

    return f"{'\n'.join([header_row, separator] + data_rows)}\n"


def _list_version_dirs(ref: str) -> list[int]:
    """Return the sorted list of version numbers under `{ref}` as a
    git-tree path. `ref` should be of the form `<rev>:<path>`, e.g.
    `origin/main:mocks` or `HEAD:mocks`.

    If the path does not exist on that ref, returns an empty list.
    Any entries that do not match `v<digits>` exactly are ignored.
    """
    try:
        result = run(["git", "ls-tree", "--name-only", ref])
    except subprocess.CalledProcessError:
        return []
    versions: list[int] = []
    for entry in result.stdout.splitlines():
        m = _VERSION_DIR_RE.match(entry.strip())
        if m:
            versions.append(int(m.group(1)))
    return sorted(versions)


def _determine_version(rip_name: str, branch_exists: bool) -> str:
    """Work out which `vN` subdirectory this submission should target.

    Rules:
    - On an existing branch, reuse the highest `vN` dir already present on
      that branch. The user is iterating on an open MR, so we don't bump.
    - On a new branch, look at `origin/main` for `{rip_name}/v*/` dirs and
      return the next number (max + 1), or `v1` if none exist.

    Must be called from inside the cloned repo with the target branch
    already checked out.
    """
    if branch_exists:
        versions = _list_version_dirs(f"HEAD:{rip_name}")
        if versions:
            return f"v{versions[-1]}"
    main_versions = _list_version_dirs(f"origin/main:{rip_name}")
    next_n = (main_versions[-1] + 1) if main_versions else 1
    return f"v{next_n}"


def push_to_gitlab(
    rip_name: str,
    metadata: list[dict],
    extra_files: list[str] | None = None,
    credentials: GitLabCredentials | None = None,
    rip_directory_name: str = RIP_DIRECTORY_NAME,
    qc_lead_user_name: str = QC_LEAD_USER_NAME,
) -> None:
    """Clone the repo, create/checkout a branch, work out the correct
    `vN` subdirectory, and push with MR options.

    The version is determined automatically:
      - On an existing branch: reuse the highest `vN` already on it.
      - On a new branch: one higher than the highest `vN` currently
        merged into main (or `v1` if the rip has never been submitted).

    `extra_files` is a list of absolute paths to additional files to be
    committed alongside `meta_owncloud.txt` in `{rip_name}/{version}/`
    (e.g. the `.checksums` sidecar and any `.maml`/`.daml`/`.md` files).
    """
    if not credentials:
        credentials = get_gitlab_credentials()

    directory = (
        f"https://oauth2:{credentials.token}"
        f"@dev.aao.org.au/waves/twg6/{rip_directory_name}.git"
    )

    git_env = {
        **os.environ,
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_SYSTEM": os.devnull,
    }

    try:
        run(["git", "clone", directory], env=git_env)
    except subprocess.CalledProcessError:
        print(
            f"{ANSI.RED} ERROR: Failed to clone the repository.{ANSI.RESET} The GitLab token may be expired or incorrect, or your GitLab credentials may be wrong. "
            f"Try running {ANSI.BOLD}{ANSI.YELLOW}'valrip login gitlab'{ANSI.RESET} to update credentials."
        )
        return
    os.chdir(rip_directory_name)

    # Doing these asserts here since this should never fail.
    assert credentials.email
    assert credentials.username
    run(["git", "config", "user.email", credentials.email])
    run(["git", "config", "user.name", credentials.username])

    try:
        # Check if the branch already exists on the remote
        result = run(["git", "ls-remote", "--heads", "origin", rip_name])
        branch_exists = result.stdout.strip() != ""

        if branch_exists:
            run(["git", "switch", rip_name])
        else:
            run(["git", "checkout", "-b", rip_name])

        version = _determine_version(rip_name, branch_exists)
        rip_version_dir = os.path.join(rip_name, version)
        os.makedirs(rip_version_dir, exist_ok=True)

        with open(os.path.join(rip_version_dir, "meta_owncloud.txt"), "w") as file:
            file.write(format_metadata_table(metadata))

        if extra_files:
            for src in extra_files:
                dst = os.path.join(rip_version_dir, os.path.basename(src))
                shutil.copy2(src, dst)

        run(["git", "add", "."])
        result = run(["git", "status", "--porcelain"])
        if result.stdout.strip():
            run(["git", "commit", "-m", f"{str(datetime.now())}"])
        else:
            print(f"The pre-rip file '{rip_name}' has no changes to commit!")
            return

        mr_title = f"{rip_name}_{version}"
        push_options = [
            "-o",
            "merge_request.create",
            "-o",
            "merge_request.target=main",
            "-o",
            f"merge_request.title={mr_title}",
            "-o",
            f"merge_request.assign={qc_lead_user_name}",
            "-o",
            f'merge_request.description="QC submission for RIP: {rip_name} ({version}) by @{credentials.username}"',
        ]

        if branch_exists:
            run(["git", "push"] + push_options)
        else:
            run(["git", "push", "--set-upstream", "origin", rip_name] + push_options)

    finally:
        os.chdir("..")
        shutil.rmtree(rip_directory_name, ignore_errors=True)


def submit_owncloud_metadata_to_gitlab(prerip_name: str) -> None:
    """
    Full submission pipeline:

    1. Log in to Data Central.
    2. Pull metadata + SHA1 checksums for every file in the pre-rip dir.
    3. Validate those checksums against the `{prerip_name}.checksums` sidecar.
       Exits if the sidecar is missing or any file mismatches / is missing /
       is extra.
    4. Download the non-parquet trackable files (and the .checksums sidecar)
       into an isolated temp directory so nothing in the user's CWD is ever
       overwritten.
    5. Push the metadata table + downloaded files to GitLab as an MR.
    """
    login_to_dc_cloud()

    meta_data = get_metadata_from_prerip(prerip_name)
    if not meta_data:
        print(
            f"{ANSI.BOLD}{ANSI.RED}No pre-rip called {prerip_name}. Available prerips are: {list_all_qc()}{ANSI.RESET}"
        )
        return

    computed_checksums = {
        row["file_name"]: row["sha1"] for row in meta_data if row.get("sha1")
    }
    validate_checksums(prerip_name, computed_checksums)

    # Isolated download directory — never the user's CWD.
    tmp_dir = tempfile.mkdtemp(prefix=f"valrip_{prerip_name}_")
    try:
        extra_files = download_trackable_data(prerip_name, dest_dir=tmp_dir)
        push_to_gitlab(prerip_name, metadata=meta_data, extra_files=extra_files)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
    print(f"\n{ANSI.GREEN}{ANSI.BOLD}Submitted to GitLab for QC.{ANSI.RESET}")
