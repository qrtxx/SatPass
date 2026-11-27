"""Admin commands.

    python -m app.cli set-password <username>   set a user's password (e.g. the seeded admin)
    python -m app.cli load-places               download GeoNames (~400 MB, once) and load towns/villages
"""

import argparse
import shutil
import sys
import time
import urllib.request
from getpass import getpass
from pathlib import Path

from pydantic import ValidationError

from app.db import SessionLocal
from app.errors import DomainError
from app.services.auth import set_password
from app.services.places import load_places

GEONAMES = "https://download.geonames.org/export/dump/"
DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "geonames"  # backend/data/geonames, git-ignored


def download(name: str) -> Path:
    """Fetch a GeoNames file unless it's already there (the full dump is ~400 MB, so it's kept between runs)."""
    target = DATA_DIR / name
    if target.exists():
        return target
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {GEONAMES}{name} …")
    partial = target.with_suffix(target.suffix + ".part")  # renamed only when complete, so a broken download is redone
    request = urllib.request.Request(GEONAMES + name, headers={"User-Agent": "SatPass/1.0"})
    with urllib.request.urlopen(request, timeout=60) as response, open(partial, "wb") as out:
        shutil.copyfileobj(response, out, length=1 << 20)
    partial.rename(target)
    return target


def cmd_set_password(username: str) -> int:
    password = getpass("New password: ")
    if getpass("Repeat it: ") != password:
        print("The passwords don't match.", file=sys.stderr)
        return 1
    with SessionLocal() as db:
        try:
            set_password(db, username, password)
        except DomainError as exc:
            print(exc.message, file=sys.stderr)
            return 1
        except ValidationError:
            print("The password must be 8 to 128 characters.", file=sys.stderr)
            return 1
    print(f"Password set for {username}")
    return 0


def cmd_load_places() -> int:
    regions = download("admin1CodesASCII.txt")
    places = download("allCountries.zip")
    print("Loading populated places into the database (a few minutes) …")
    started = time.perf_counter()
    with SessionLocal() as db:
        count = load_places(db, places, regions)
    print(f"Loaded {count:,} places in {time.perf_counter() - started:.0f} s")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("set-password", help="set a user's password (e.g. the seeded admin)").add_argument("username")
    commands.add_parser("load-places", help="download GeoNames and load towns and villages for place search")
    args = parser.parse_args(argv)
    if args.command == "load-places":
        return cmd_load_places()
    return cmd_set_password(args.username)


if __name__ == "__main__":
    sys.exit(main())
