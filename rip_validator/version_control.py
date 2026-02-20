"""
Module to handle versioning
"""

from typing import Optional
import httpx
from rip_validator import __version__
from .data_types import ANSI

GIT_HUB_URL = "https://github.com/TrystanScottLambert/valrip"


def get_latest_version() -> Optional[str]:
    """
    Scrapes the latest tagged version on github.
    """
    try:
        page = httpx.request("GET", GIT_HUB_URL)
        return page.text.split("max-width: none;")[1].split("</span>")[0].split("v")[-1]
    except Exception as e:
        print(
            f"{ANSI.YELLOW}Warning: Unable to check latest version. \n {e}{ANSI.RESET}"
        )


def get_current_version() -> str:
    """
    Gets the version that is being run in the current package
    """
    return __version__


class Version:
    def __init__(self) -> None:
        self.latest = get_latest_version()
        self.current = get_current_version()

    def version_call(self) -> str:
        """
        Method for making a version string for the click version decorator.
        Meant to be seen when using the --version tag.
        """
        if self.latest != self.current:
            return f"{self.current} ❌ {ANSI.GREY}(Outdated. Latest version is: {self.latest}){ANSI.RESET}"
        else:
            return f"{self.current} ✅"

    def check_version(self) -> Optional[str]:
        """
        Returns a warning string if latest version is not the same as current. Else None.
        """
        if self.latest:
            if self.latest != self.current:
                print(
                    f"{ANSI.YELLOW}WARNING: This version of valrip appears outdated. "
                    f"This version is {ANSI.RESET}{ANSI.RED}{self.current}{ANSI.RESET},"
                    f"{ANSI.YELLOW} but the latest version is {ANSI.RESET}{ANSI.GREEN}{self.latest}{ANSI.RESET}"
                    f"{ANSI.YELLOW}. Please make sure you are using the latest version for building RIPs. "
                    f"See: https://github.com/TrystanScottLambert/valrip/releases for the latest release.{ANSI.RESET}"
                )
        return None
