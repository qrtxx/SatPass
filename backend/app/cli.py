"""Admin commands.

    python -m app.cli set-password <username>   set a user's password (e.g. the seeded admin)
    python -m app.cli load-places [--full]      load towns/villages from GeoNames: allCountries.zip if present
                                                (or --full, ~400 MB), else KZ.zip + cities1000.zip (~14 MB)
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


FULL = "allCountries.zip"  # every populated place in the world, ~400 MB
SMALL = ["KZ.zip", "cities1000.zip"]  # every place in Kazakhstan + towns of 1,000+ worldwide, ~14 MB


def choose_files(full: bool) -> list[str]:
    """allCountries.zip if it's there (or --full); else whichever small files are there; else the small set."""
    if full or (DATA_DIR / FULL).exists():
        return [FULL]
    present = [name for name in SMALL if (DATA_DIR / name).exists()]
    return present or SMALL


def cmd_load_places(full: bool) -> int:
    regions = download("admin1CodesASCII.txt")
    names = choose_files(full)
    files = [download(name) for name in names]
    print(f"Loading populated places from {', '.join(names)} (a few minutes for the full file) …")
    started = time.perf_counter()
    with SessionLocal() as db:
        count = load_places(db, files, regions)
    print(f"Loaded {count:,} places in {time.perf_counter() - started:.0f} s")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("set-password", help="set a user's password (e.g. the seeded admin)").add_argument("username")
    places = commands.add_parser("load-places", help="load towns and villages for place search (downloads GeoNames if needed)")
    places.add_argument("--full", action="store_true", help="use allCountries.zip (~400 MB) instead of KZ.zip + cities1000.zip")
    args = parser.parse_args(argv)
    if args.command == "load-places":
        return cmd_load_places(args.full)
    return cmd_set_password(args.username)


if __name__ == "__main__":
    sys.exit(main())
