"""
Controller for the click command 'submit'.
Separating into a separate file to limit import costs at runtime.
"""

from .internet_checker import is_connected
from .submit import submit_owncloud_metadata_to_gitlab
from .WAVES_config import ANSI


def submit(prerip_name: str) -> None:
    if is_connected():
        submit_owncloud_metadata_to_gitlab(prerip_name)
    else:
        print(
            f"{ANSI.RED}{ANSI.BOLD}'valrip submit' requires an internet connection to submit to GitLab. You appear to be disconnected.{ANSI.RESET}"
        )
