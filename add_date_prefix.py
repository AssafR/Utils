#!/usr/bin/env python3

from __future__ import annotations

import argparse
import re
from datetime import datetime
from pathlib import Path


DATE_PREFIX_RE = re.compile(r"^\d{4}-\d{2}-\d{2}\s+")


def add_date_prefix(directory: Path, dry_run: bool = False) -> None:
    for path in directory.iterdir():
        if not path.is_file():
            continue

        # Idempotent: skip files that already start with YYYY-MM-DD
        if DATE_PREFIX_RE.match(path.name):
            print(f"SKIP: {path.name}")
            continue

        date_prefix = datetime.fromtimestamp(
            path.stat().st_mtime
        ).strftime("%Y-%m-%d")

        new_name = f"{date_prefix} - {path.name}"
        new_path = path.with_name(new_name)

        print(f"RENAME:               {path.name} \n ->      {new_name}")

        if not dry_run:
            path.rename(new_path)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prefix files with their modification date (YYYY-MM-DD)."
    )
    parser.add_argument(
        "directory",
        type=Path,
        help="Directory containing files to rename",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be renamed without making changes",
    )

    args = parser.parse_args()

    if not args.directory.is_dir():
        parser.error(f"Not a directory: {args.directory}")

    add_date_prefix(args.directory, dry_run=args.dry_run)


if __name__ == "__main__":
    main()