import argparse
from getpass import getpass

from backend.app.auth import create_user
from backend.app.config import settings


def main() -> None:
    parser = argparse.ArgumentParser(description="Provision an administrator without placing credentials in shell history.")
    parser.add_argument("email", help="Email address for the administrator account")
    args = parser.parse_args()

    settings.validate()
    password = getpass("Administrator password (minimum 8 characters): ")
    confirmation = getpass("Confirm password: ")
    if password != confirmation:
        parser.error("Passwords do not match.")
    if len(password) < 12:
        parser.error("Use an administrator password of at least 12 characters.")

    user = create_user(args.email, password, "admin")
    print(f"Provisioned administrator account for {user.email}.")


if __name__ == "__main__":
    main()
