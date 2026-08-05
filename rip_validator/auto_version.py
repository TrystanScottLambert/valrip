"""
Module for handling the automatic version checks for valrip.
"""

import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from hashlib import sha1
from pathlib import Path

import yaml

from .owncloud_utils import FileChecksums
from .settings_config import RIP_DIRECTORY_NAME
from .submit import get_gitlab_credentials, run
from .WAVES_config import ANSI
from .xxh_waves import NO_XXH, XXH_KEYWORD, calculate_hash

_VERSION_DIR_RE = re.compile(r"^v(\d+)$")

# RIPs published before the xxh hash existed fall back to sha1; see
# _is_pre_xxh. By this date every RIP must have been re-published at least
# once, and the fallback can go.
SHA1_FALLBACK_REMOVAL = "August 2027"


@dataclass
class TableVersion:
    """Versioning info for a single table (parquet file).

    The checksums are normally WAVES xxh hashes, which cover the data bytes
    only, so that writing the hash into the footer does not itself change the
    hash. Tables last published before that hash existed are compared on sha1
    instead; both sides always use the same algorithm.
    """

    name: str
    local_checksum: str
    remote_checksum: str | None  # None if table is new
    remote_version: int | None  # None if table is new

    @property
    def next_version(self) -> int:
        if self.remote_version is None:
            return 1
        if self.local_checksum == self.remote_checksum:
            return self.remote_version
        return self.remote_version + 1


@dataclass
class RipVersion:
    """Versioning info for an entire RIP."""

    rip_name: str
    next_rip_version: int
    tables: list[TableVersion] = field(default_factory=list)

    def table_versions_map(self) -> dict[str, int]:
        return {t.name: t.next_version for t in self.tables}


def _clone_url(rip_directory_name: str = RIP_DIRECTORY_NAME) -> str:
    """Build the GitLab clone URL using the stored credentials."""
    credentials = get_gitlab_credentials()
    return (
        f"https://oauth2:{credentials.token}"
        f"@dev.aao.org.au/waves/twg6/{rip_directory_name}.git"
    )


def _ls_version_dirs(repo: Path, rip_name: str) -> list[int]:
    """List sorted version numbers under ``{rip_name}/`` on ``origin/main``.

    Returns an empty list if the RIP folder does not exist on main.
    """
    try:
        result = run(
            [
                "git",
                "-C",
                str(repo),
                "ls-tree",
                "--name-only",
                f"origin/main:{rip_name}",
            ]
        )
    except subprocess.CalledProcessError:
        return []
    versions: list[int] = []
    for entry in result.stdout.splitlines():
        m = _VERSION_DIR_RE.match(entry.strip())
        if m:
            versions.append(int(m.group(1)))
    return sorted(versions)


def _read_file_at_main(repo: Path, path_in_repo: str) -> str | None:
    """Read the contents of a file at ``origin/main:{path_in_repo}``.

    Returns ``None`` if the file does not exist on that ref.
    """
    try:
        result = run(["git", "-C", str(repo), "show", f"origin/main:{path_in_repo}"])
    except subprocess.CalledProcessError:
        return None
    return result.stdout


def sha1_checksum(file_name: Path) -> str:
    """Calculates the sha1 checksum of a given file."""
    sha1_hash = sha1()
    with open(file_name, "rb") as file:
        for chunk in iter(lambda: file.read(128 * sha1_hash.block_size), b""):
            sha1_hash.update(chunk)
        return sha1_hash.hexdigest()


def _parse_checksums(text: str) -> dict[str, FileChecksums]:
    """Parse a .checksums file into {filename: FileChecksums}.

    Data lines are ``filename: sha1: xxh``, where the xxh field is ``NO_XXH``
    for everything that isn't a parquet file. Sidecars published before the
    xxh hash existed carry only ``filename: sha1`` and come back with no xxh
    at all.
    """
    out: dict[str, FileChecksums] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or ":" not in line or line.startswith("#"):
            continue
        fields = [field.strip() for field in line.split(":")]
        name, sha1_sum = fields[0], fields[1]
        xxh = fields[2] if len(fields) > 2 else NO_XXH
        if name and sha1_sum:
            out[name] = FileChecksums(sha1=sha1_sum, xxh=None if xxh == NO_XXH else xxh)
    return out


def _parse_daml_table_versions(text: str) -> dict[str, int]:
    """Pull {table_name: version} out of a DAML file body."""

    data = yaml.safe_load(text) or {}
    tables = data.get("tables") or []
    return {entry["name"]: int(entry["version"]) for entry in tables if "name" in entry}


@dataclass
class _VersionSnapshot:
    """What one remote ``vN`` looks like for a RIP."""

    checksums: dict[str, FileChecksums]  # {filename: checksums}
    table_versions: dict[str, int]  # {table_name: version}


class _RemoteHistory:
    """Lazy view of every published ``vN`` of a RIP on ``origin/main``."""

    def __init__(self, repo: Path, rip_name: str):
        self._repo = repo
        self._rip_name = rip_name
        self._versions_desc: list[int] = sorted(
            _ls_version_dirs(repo, rip_name), reverse=True
        )
        self._cache: dict[int, _VersionSnapshot] = {}

    @property
    def latest_version(self) -> int | None:
        """Highest ``vN`` merged to main, or ``None`` if the RIP is new."""
        return self._versions_desc[0] if self._versions_desc else None

    def _snapshot(self, version: int) -> _VersionSnapshot:
        """Gets the state of ``vN`` checksum file and daml file."""
        if version not in self._cache:
            base = f"{self._rip_name}/v{version}"
            checksums_text = _read_file_at_main(
                self._repo, f"{base}/{self._rip_name}.checksums"
            )
            daml_text = _read_file_at_main(self._repo, f"{base}/{self._rip_name}.daml")
            self._cache[version] = _VersionSnapshot(
                checksums=_parse_checksums(checksums_text) if checksums_text else {},
                table_versions=(
                    _parse_daml_table_versions(daml_text) if daml_text else {}
                ),
            )
        return self._cache[version]

    def last_seen(
        self, table_name: str, parquet_filename: str
    ) -> tuple[FileChecksums, int] | None:
        """
        Return ``(checksums, table_version)`` for the most recent ``vN``
        that contained this table, or ``None`` if the table has never
        appeared on main.
        """
        for v in self._versions_desc:
            snap = self._snapshot(v)
            remote_sums = snap.checksums.get(parquet_filename)
            remote_ver = snap.table_versions.get(table_name)
            if remote_sums is not None and remote_ver is not None:
                return remote_sums, remote_ver
        return None


class _TempClone:
    """
    Context manager that clones the RIP repo into a temp dir.
    """

    def __init__(self, rip_directory_name: str = RIP_DIRECTORY_NAME):
        self._rip_directory_name = rip_directory_name
        self._tmp: str | None = None
        self.repo: Path | None = None

    def __enter__(self) -> Path:
        self._tmp = tempfile.mkdtemp(prefix="valrip_autoversion_")
        url = _clone_url(self._rip_directory_name)
        git_env = {
            **os.environ,
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_SYSTEM": os.devnull,
        }
        run(
            ["git", "clone", "--no-checkout", url, self._rip_directory_name],
            cwd=self._tmp,
            env=git_env,
        )
        self.repo = Path(self._tmp) / self._rip_directory_name
        return self.repo

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._tmp is not None:
            shutil.rmtree(self._tmp, ignore_errors=True)


def _is_pre_xxh(remote_sums: FileChecksums | None) -> bool:
    """Was this table last published before parquet files carried an xxh hash?

    Such a table has only a sha1 in its published sidecar, so that is the only
    thing the local file can be compared against.
    """
    return remote_sums is not None and not remote_sums.xxh


def _warn_sha1_fallback(table_names: list[str]) -> None:
    """Tell the user which tables were versioned on the deprecated sha1."""
    named = ", ".join(f"'{name}'" for name in sorted(set(table_names)))
    print(
        f"{ANSI.YELLOW}{ANSI.BOLD}DEPRECATION WARNING:{ANSI.RESET}{ANSI.YELLOW} "
        f"the last published version of {named} predates the '{XXH_KEYWORD}' hash, so "
        f"the version comparison fell back to sha1. sha1 covers the whole file, so "
        f"such a table takes one extra version bump once the '{XXH_KEYWORD}' hash is "
        f"written into its footer; that is expected. The sha1 fallback will be removed "
        f"in {SHA1_FALLBACK_REMOVAL}, by which point every RIP must have been "
        f"published at least once with an '{XXH_KEYWORD}' hash.{ANSI.RESET}"
    )


def get_next_version(rip_name: str) -> int:
    """
    Return the next RIP-level version integer.
    """
    with _TempClone() as repo:
        versions = _ls_version_dirs(repo, rip_name)
    return (versions[-1] + 1) if versions else 1


def get_rip_version_info(
    rip_name: str,
    maml_data: dict[str, dict],
    directory: Path,
) -> RipVersion:
    """
    Compute next versions for a RIP and all its tables.

    Tables are compared on their xxh hash, or on sha1 for the RIPs that were
    published before that hash existed. Mixing the two is never allowed: the
    algorithm is picked per table from what its last published version holds.
    """
    directory = Path(directory)

    with _TempClone() as repo:
        history = _RemoteHistory(repo, rip_name)
        latest = history.latest_version

        tables: list[TableVersion] = []
        sha1_fallbacks: list[str] = []
        for maml_filename, maml_content in sorted(maml_data.items()):
            table_name = maml_content["table"]
            parquet_filename = maml_filename.replace(".maml", ".parquet")
            parquet_path = directory / parquet_filename

            last = history.last_seen(table_name, parquet_filename)
            if last is None:
                remote_sums, remote_ver = None, None
            else:
                remote_sums, remote_ver = last

            use_sha1 = _is_pre_xxh(remote_sums)
            if use_sha1:
                sha1_fallbacks.append(table_name)

            if not parquet_path.exists():
                local_sum = ""
            elif use_sha1:
                local_sum = sha1_checksum(parquet_path)
            else:
                local_sum = calculate_hash(parquet_path)

            if remote_sums is None:
                remote_sum = None
            else:
                remote_sum = remote_sums.sha1 if use_sha1 else remote_sums.xxh

            tables.append(
                TableVersion(
                    name=table_name,
                    local_checksum=local_sum,
                    remote_checksum=remote_sum,
                    remote_version=remote_ver,
                )
            )

    if sha1_fallbacks:
        _warn_sha1_fallback(sha1_fallbacks)

    next_rip_version = (latest + 1) if latest is not None else 1

    return RipVersion(
        rip_name=rip_name,
        next_rip_version=next_rip_version,
        tables=tables,
    )


def get_next_table_versions(
    rip_name: str,
    maml_data: dict[str, dict],
    directory: Path,
) -> dict[str, int]:
    """
    Return ``{table_name: next_version}`` for every MAML in ``maml_data``.
    """
    return get_rip_version_info(rip_name, maml_data, directory).table_versions_map()
