from dataclasses import dataclass
from datetime import date

import keyring

from .status import State, Status
from .WAVES_config import ANSI

SERVICE_NAME = "valrip"
MASK = "*" * 8
TOKEN_EXPIRY_WARNING_DAYS = 30
GITLAB_WIKI_URL = "https://waves.wiki.org.au/en/Working-Groups/TWG6-Internal-QC/Using-the-WAVES-GitLab-for-QC"

# (display name, keyring key, is_secret)
GITLAB_CREDENTIALS = (
    ("GitLab username", "gitlab_username", False),
    ("GitLab email", "gitlab_email", False),
    ("WAVES git-bot token", "gitlab_token", True),
)

OWNCLOUD_CREDENTIALS = (
    ("Data Central username", "data_central_username", False),
    ("Data Central password", "data_central_password", True),
)


def login_gitlab(user: bool, email: bool, token: bool, all_creds: bool):
    """Store GitLab credentials."""
    from .submit import (
        request_gitlab_email,
        request_gitlab_token,
        request_gitlab_username,
    )

    # default to everything if nothing is selected
    if not any([user, email, token, all_creds]):
        all_creds = True

    if user or all_creds:
        request_gitlab_username()
    if email or all_creds:
        request_gitlab_email()
    if token or all_creds:
        request_gitlab_token()
    print("GitLab credentials saved.")


def login_owncloud(user: bool, password: bool, all_creds: bool):
    """Store Data Central ownCloud credentials."""
    from .owncloud_utils import (
        request_data_central_password,
        request_data_central_username,
    )

    if not any([user, password, all_creds]):
        all_creds = True

    if user or all_creds:
        request_data_central_username()
    if password or all_creds:
        request_data_central_password()

    print("Data Central credentials saved.")


def format_credential(value: str | None, is_secret: bool, show_secrets: bool) -> str:
    """
    Formats a single stored credential for display, masking secrets unless asked.
    """
    if value is None:
        return f"{ANSI.GREY}not set{ANSI.RESET}"
    if is_secret and not show_secrets:
        return MASK
    return value


def print_credential_group(
    title: str,
    credentials: tuple[tuple[str, str, bool], ...],
    show_secrets: bool,
    width: int,
) -> None:
    """
    Prints every credential of a single group as it is currently stored in the keyring.
    """
    print(f"{ANSI.BOLD}{title}{ANSI.RESET}")
    for name, key, is_secret in credentials:
        value = keyring.get_password(SERVICE_NAME, key)
        print(f"  {name:<{width}}  {format_credential(value, is_secret, show_secrets)}")


def show_credentials(show_secrets: bool) -> None:
    """Print all the credentials that valrip currently has stored."""
    width = max(len(name) for name, _, _ in GITLAB_CREDENTIALS + OWNCLOUD_CREDENTIALS)
    print_credential_group("GitLab", GITLAB_CREDENTIALS, show_secrets, width)
    print()
    print_credential_group("Data Central", OWNCLOUD_CREDENTIALS, show_secrets, width)
    if not show_secrets:
        print(
            f"\n{ANSI.GREY}Secrets are hidden. Use --show-secrets to reveal them."
            f"{ANSI.RESET}"
        )


@dataclass
class CredentialCheck:
    """
    The outcome of checking one service's credentials, and why.

    FAIL means we know something is wrong and submitting will not work.
    WARNING means we could not find out, which is not the same as being fine.
    """

    state: State
    message: str

    @property
    def is_fail(self) -> bool:
        return self.state == State.FAIL

    def render(self) -> str:
        return f"{Status(self.state).output()}  {self.message}"


def missing_credentials(credentials: tuple[tuple[str, str, bool], ...]) -> list[str]:
    """
    The display names of every credential in the group that is not stored yet.
    """
    return [
        name
        for name, key, _ in credentials
        if not keyring.get_password(SERVICE_NAME, key)
    ]


def check_data_central(online: bool) -> list[CredentialCheck]:
    """
    Checks the Data Central credentials by asking Data Central itself, so this
    catches passwords that were changed on the website after being stored here.
    """
    missing = missing_credentials(OWNCLOUD_CREDENTIALS)
    if missing:
        return [
            CredentialCheck(
                State.FAIL,
                f"Not stored yet: {', '.join(missing)}. "
                f"Run {ANSI.BOLD}{ANSI.YELLOW}'valrip login owncloud'{ANSI.RESET}.",
            )
        ]

    if not online:
        return [
            CredentialCheck(
                State.WARNING,
                "No internet connection, so the credentials could not be checked "
                "against Data Central.",
            )
        ]

    from .owncloud_utils import DATA_CENTRAL_URL, probe_data_central_auth

    username = keyring.get_password(SERVICE_NAME, "data_central_username")
    password = keyring.get_password(SERVICE_NAME, "data_central_password")
    assert username and password  # guaranteed by the missing check above

    import requests

    try:
        status_code = probe_data_central_auth(username, password)
    except requests.RequestException as err:
        return [
            CredentialCheck(
                State.WARNING,
                f"Could not reach Data Central ({err.__class__.__name__}), so the "
                f"credentials could not be checked. Check {DATA_CENTRAL_URL}.",
            )
        ]

    match status_code:
        case 200 | 207:
            check = CredentialCheck(
                State.PASS, "Data Central accepted these credentials."
            )
        case 401:
            check = CredentialCheck(
                State.FAIL,
                f"Data Central rejected these credentials. If your account has "
                f"two-factor authentication turned on you need an app password "
                f"here, not your normal password. "
                f"Run {ANSI.BOLD}{ANSI.YELLOW}'valrip login owncloud'{ANSI.RESET}.",
            )
        case 404:
            check = CredentialCheck(
                State.FAIL,
                f"The password was accepted but Data Central has no storage for "
                f"'{username}'. Usernames are case sensitive, so check it and "
                f"run {ANSI.BOLD}{ANSI.YELLOW}'valrip login owncloud -u'{ANSI.RESET}.",
            )
        case _:
            check = CredentialCheck(
                State.WARNING,
                f"Data Central answered with an unexpected {status_code}, so the "
                f"credentials could not be checked. Check {DATA_CENTRAL_URL}.",
            )
    return [check]


def check_token_expiry(metadata: dict) -> list[CredentialCheck]:
    """
    Warns about a token that is about to expire, so that it can be replaced
    before a submission fails rather than after.

    An already expired token cannot reach here: GitLab rejects it outright, so
    the only expiry worth reporting is one in the future.
    """
    expires_at = metadata.get("expires_at")
    if not expires_at:
        return []

    try:
        expiry = date.fromisoformat(expires_at)
    except ValueError:
        return []

    days_left = (expiry - date.today()).days
    if days_left <= TOKEN_EXPIRY_WARNING_DAYS:
        return [
            CredentialCheck(
                State.WARNING,
                f"The token expires on {expires_at}, in {days_left} days. "
                f"Get a new one before then: {GITLAB_WIKI_URL}",
            )
        ]
    return []


def check_project_access(token: str) -> list[CredentialCheck]:
    """
    Checks the token can push to the repo that `submit` actually pushes to,
    which is the thing that decides whether a submission works.
    """
    from .submit import (
        DEVELOPER_ACCESS_LEVEL,
        gitlab_project_path,
        probe_gitlab_project,
    )

    project_path = gitlab_project_path()
    response = probe_gitlab_project(token, project_path)

    if response.status_code == 404:
        return [
            CredentialCheck(
                State.FAIL,
                f"The token cannot reach {ANSI.BOLD}{project_path}{ANSI.RESET}, which "
                f"is where submissions go. This is what a token belonging to a "
                f"different project looks like, so check you are not holding a "
                f"testing token. See {GITLAB_WIKI_URL}",
            )
        ]

    if response.status_code != 200:
        return [
            CredentialCheck(
                State.WARNING,
                f"GitLab answered with an unexpected {response.status_code} when "
                f"asked about {project_path}, so access could not be checked.",
            )
        ]

    permissions = response.json().get("permissions") or {}
    access_levels = [
        (permissions.get(kind) or {}).get("access_level") or 0
        for kind in ("project_access", "group_access")
    ]
    if max(access_levels) < DEVELOPER_ACCESS_LEVEL:
        return [
            CredentialCheck(
                State.FAIL,
                f"The token can read {project_path} but not push to it "
                f"(access level {max(access_levels)}, needs "
                f"{DEVELOPER_ACCESS_LEVEL}). Ask for Developer access.",
            )
        ]

    return [
        CredentialCheck(
            State.PASS, f"The token can push to {ANSI.BOLD}{project_path}{ANSI.RESET}."
        )
    ]


def check_commit_identity(token: str) -> list[CredentialCheck]:
    """
    Checks the username and email that get stamped onto the commits. Neither
    can stop a push, so nothing here is ever a failure, but a wrong one
    quietly detaches the commits from their author's GitLab account.
    """
    from .submit import probe_gitlab_user

    checks = []
    username = keyring.get_password(SERVICE_NAME, "gitlab_username")
    email = keyring.get_password(SERVICE_NAME, "gitlab_email")
    assert username and email  # guaranteed by the missing check in check_gitlab

    response = probe_gitlab_user(token, username)
    if response.status_code == 200 and not response.json():
        checks.append(
            CredentialCheck(
                State.WARNING,
                f"No GitLab account is called '{username}', so commits will not be "
                f"linked to their author. It is usually your email without the "
                f"@ part.",
            )
        )

    from email_validator import EmailNotValidError, validate_email

    try:
        validate_email(email, check_deliverability=False, dns_resolver=False)
    except EmailNotValidError as err:
        checks.append(
            CredentialCheck(State.WARNING, f"'{email}' is not a valid email. {err}")
        )

    return checks


def check_gitlab(online: bool) -> list[CredentialCheck]:
    """
    Checks whether the GitLab credentials can actually complete a submission,
    in the order that a submission needs them: the token has to work, it has
    to reach the RIP repo, and it has to be able to push there. The username
    and email only label the commits, so they are checked last and never fail.

    Stops at the first failure, since nothing after it can be checked anyway.
    """
    missing = missing_credentials(GITLAB_CREDENTIALS)
    if missing:
        return [
            CredentialCheck(
                State.FAIL,
                f"Not stored yet: {', '.join(missing)}. "
                f"Run {ANSI.BOLD}{ANSI.YELLOW}'valrip login gitlab'{ANSI.RESET}.",
            )
        ]

    if not online:
        return [
            CredentialCheck(
                State.WARNING,
                "No internet connection, so the credentials could not be checked "
                "against GitLab.",
            )
        ]

    from .submit import (
        GITLAB_HOST,
        probe_gitlab_token,
        probe_gitlab_token_metadata,
    )

    token = keyring.get_password(SERVICE_NAME, "gitlab_token")
    assert token  # guaranteed by the missing check above

    import requests

    try:
        response = probe_gitlab_token(token)
    except requests.RequestException as err:
        return [
            CredentialCheck(
                State.WARNING,
                f"Could not reach {GITLAB_HOST} ({err.__class__.__name__}), so the "
                f"credentials could not be checked.",
            )
        ]

    if response.status_code == 401:
        return [
            CredentialCheck(
                State.FAIL,
                f"{GITLAB_HOST} rejected the git-bot token. It is wrong, expired "
                f"or revoked. Get a new one and run "
                f"{ANSI.BOLD}{ANSI.YELLOW}'valrip login gitlab -t'{ANSI.RESET}. "
                f"See {GITLAB_WIKI_URL}",
            )
        ]

    if response.status_code != 200:
        return [
            CredentialCheck(
                State.WARNING,
                f"{GITLAB_HOST} answered with an unexpected {response.status_code}, "
                f"so the credentials could not be checked.",
            )
        ]

    checks = [
        CredentialCheck(
            State.PASS,
            f"{GITLAB_HOST} accepted the git-bot token "
            f"('{response.json().get('name')}').",
        )
    ]

    metadata_response = probe_gitlab_token_metadata(token)
    if metadata_response.status_code == 200:
        checks += check_token_expiry(metadata_response.json())

    checks += check_project_access(token)
    if any(check.is_fail for check in checks):
        return checks

    return checks + check_commit_identity(token)


def check_credentials() -> bool:
    """
    Prints the state of every stored credential and whether it works, returning
    True when nothing is known to be broken. Secrets are never printed.

    A WARNING does not count as a failure: a service being unreachable says
    nothing about whether the credentials are right, and a username that does
    not resolve still pushes fine, so neither should block a submission.
    """
    from .internet_checker import is_connected

    online = is_connected()
    width = max(len(name) for name, _, _ in GITLAB_CREDENTIALS + OWNCLOUD_CREDENTIALS)

    services = [
        ("Data Central", OWNCLOUD_CREDENTIALS, check_data_central),
        ("GitLab", GITLAB_CREDENTIALS, check_gitlab),
    ]

    broken = []
    for title, credentials, check in services:
        print_credential_group(title, credentials, show_secrets=False, width=width)
        results = check(online)
        for result in results:
            print(f"  {result.render()}")
        print()
        if any(result.is_fail for result in results):
            broken.append(title)

    if broken:
        print(
            f"{ANSI.RED}{' and '.join(broken)} will not work until the problems "
            f"above are fixed.{ANSI.RESET}"
        )
    return not broken
