"""Admin commands. Usage: python -m app.cli set-password <username>"""

import argparse
import sys
from getpass import getpass

from pydantic import ValidationError

from app.db import SessionLocal
from app.errors import DomainError
from app.services.auth import set_password


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("set-password", help="set a user's password (e.g. the seeded admin)").add_argument("username")
    args = parser.parse_args(argv)

    password = getpass("New password: ")
    if getpass("Repeat it: ") != password:
        print("The passwords don't match.", file=sys.stderr)
        return 1
    with SessionLocal() as db:
        try:
            set_password(db, args.username, password)
        except DomainError as exc:
            print(exc.message, file=sys.stderr)
            return 1
        except ValidationError:
            print("The password must be 8 to 128 characters.", file=sys.stderr)
            return 1
    print(f"Password set for {args.username}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
