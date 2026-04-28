"""
Small module for checking that we are connected to the internet.
"""

import httpx


def is_connected() -> bool:
    try:
        response = httpx.get("https://www.google.com", timeout=5.0)
        return response.status_code == 200
    except httpx.RequestError:
        return False
