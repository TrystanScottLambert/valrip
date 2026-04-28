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
