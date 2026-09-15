"""Create the deterministic code.zip submission artifact."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from buy_or_wait.packaging import PackagingError, build_code_zip, submission_members


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the safe deterministic Buy or Wait? code.zip")
    parser.add_argument(
        "--code-root", type=Path, default=Path(__file__).resolve().parent,
        help="Source code directory (defaults to the directory containing this script)",
    )
    parser.add_argument(
        "--output", type=Path, default=Path(__file__).resolve().parent.parent / "code.zip",
        help="Destination archive (defaults to repository-root code.zip)",
    )
    parser.add_argument("--check", action="store_true", help="Validate and list members without writing an archive")
    parser.add_argument("--replace", action="store_true", help="Atomically replace an existing archive")
    args = parser.parse_args()

    try:
        if args.check:
            members = [path.as_posix() for path in submission_members(args.code_root)]
        else:
            members = build_code_zip(args.code_root, args.output, replace=args.replace)
    except (OSError, UnicodeError, PackagingError) as exc:
        print(json.dumps({"status": "blocked", "reason": str(exc)}, indent=2))
        return 1

    print(json.dumps({
        "status": "validated" if args.check else "created",
        "output": "" if args.check else str(args.output.resolve()),
        "members": members,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
