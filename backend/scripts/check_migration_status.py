from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


REVISION_RE = re.compile(r"^([0-9a-fA-F]+)")


@dataclass(frozen=True)
class MigrationStatus:
    is_at_head: bool
    head_revisions: list[str]
    current_revisions: list[str]
    message: str


def parse_revisions(output: str) -> list[str]:
    revisions: list[str] = []
    for line in output.splitlines():
        match = REVISION_RE.match(line.strip())
        if match:
            revisions.append(match.group(1))
    return revisions


def assess_migration_status(heads_output: str, current_output: str) -> MigrationStatus:
    head_revisions = parse_revisions(heads_output)
    current_revisions = parse_revisions(current_output)

    if not head_revisions:
        return MigrationStatus(
            is_at_head=False,
            head_revisions=[],
            current_revisions=current_revisions,
            message="Unable to determine Alembic head revision.",
        )

    is_at_head = any(revision in head_revisions for revision in current_revisions)
    if is_at_head:
        return MigrationStatus(
            is_at_head=True,
            head_revisions=head_revisions,
            current_revisions=current_revisions,
            message="Database schema is already at Alembic head.",
        )

    return MigrationStatus(
        is_at_head=False,
        head_revisions=head_revisions,
        current_revisions=current_revisions,
        message=(
            "Database schema is not upgraded to Alembic head.\n\n"
            "Run:\n"
            "cd D:\\projects\\PDFAI\\backend\n"
            ".\\.venv\\Scripts\\python.exe -m alembic upgrade head\n"
        ),
    )


def run_alembic(args: list[str], backend_dir: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=backend_dir,
        text=True,
        capture_output=True,
        check=False,
    )


def main() -> int:
    backend_dir = Path(__file__).resolve().parents[1]

    heads = run_alembic(["heads"], backend_dir)
    if heads.returncode != 0:
        print("Unable to read Alembic heads.", file=sys.stderr)
        print(heads.stdout, file=sys.stderr)
        print(heads.stderr, file=sys.stderr)
        return 1

    current = run_alembic(["current"], backend_dir)
    if current.returncode != 0:
        print("Unable to read current database migration.", file=sys.stderr)
        print(current.stdout, file=sys.stderr)
        print(current.stderr, file=sys.stderr)
        return 1

    status = assess_migration_status(heads.stdout, current.stdout)
    print(status.message)
    if status.head_revisions:
        print(f"Heads: {', '.join(status.head_revisions)}")
    if status.current_revisions:
        print(f"Current: {', '.join(status.current_revisions)}")
    else:
        print("Current: <none>")

    return 0 if status.is_at_head else 1


if __name__ == "__main__":
    raise SystemExit(main())
