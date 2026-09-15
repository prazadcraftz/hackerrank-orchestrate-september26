"""Build the deterministic, secret-free submission code archive."""
from __future__ import annotations

import json
import os
import tempfile
import zipfile
from pathlib import Path, PurePosixPath


class PackagingError(ValueError):
    """The code package cannot be built safely from the supplied tree."""


FIXED_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
FORBIDDEN_PARTS = {".cache", ".git", ".pytest_cache", "__pycache__", "runs", "tests"}
REQUIRED_MEMBERS = {
    "README.md",
    "evidence_manifest.json",
    "main.py",
    "buy_or_wait/__init__.py",
    "evaluation/main.py",
    "evaluation/usage_report.md",
}
USAGE_REPORT_MARKERS = (
    "# Final full-dataset model usage report",
    "Provider:",
    "Total API calls:",
    "Total tokens:",
    "Estimated Standard paid-list cost:",
)


def _is_forbidden(relative: Path) -> bool:
    parts = {part.lower() for part in relative.parts}
    name = relative.name.lower()
    return bool(parts & FORBIDDEN_PARTS) or name == "log.txt" or name == ".env" or name.startswith(".env.")


def _is_allowed(relative: Path) -> bool:
    posix = PurePosixPath(relative.as_posix())
    if posix in {PurePosixPath("README.md"), PurePosixPath("evidence_manifest.json"),
                 PurePosixPath("main.py"), PurePosixPath("package_submission.py")}:
        return True
    if len(posix.parts) >= 2 and posix.parts[0] == "buy_or_wait" and posix.suffix == ".py":
        return True
    return posix in {
        PurePosixPath("evaluation/main.py"),
        PurePosixPath("evaluation/usage_report.md"),
    }


def submission_members(code_root: Path) -> list[Path]:
    """Return validated package members relative to *code_root* in stable order."""
    code_root = code_root.resolve()
    if not code_root.is_dir():
        raise PackagingError(f"Code root is not a directory: {code_root}")

    members: list[Path] = []
    for candidate in code_root.rglob("*"):
        relative = candidate.relative_to(code_root)
        if _is_forbidden(relative) or not _is_allowed(relative):
            continue
        if candidate.is_symlink():
            raise PackagingError(f"Refusing symbolic link in package: {relative.as_posix()}")
        if candidate.is_file():
            members.append(relative)

    members.sort(key=lambda item: item.as_posix())
    names = {item.as_posix() for item in members}
    missing = sorted(REQUIRED_MEMBERS - names)
    if missing:
        raise PackagingError(f"Required package files are missing: {', '.join(missing)}")

    usage_report = (code_root / "evaluation" / "usage_report.md").read_text(encoding="utf-8")
    missing_markers = [marker for marker in USAGE_REPORT_MARKERS if marker not in usage_report]
    if missing_markers:
        raise PackagingError("evaluation/usage_report.md is not a completed final-run report")
    try:
        manifest = json.loads((code_root / "evidence_manifest.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PackagingError("evidence_manifest.json is not valid UTF-8 JSON") from exc
    if (manifest.get("sample_only") is not False or
            manifest.get("status") not in {"candidate_facts_ready", "needs_review"} or
            not isinstance(manifest.get("input_sha256"), dict) or
            not isinstance(manifest.get("source_results"), dict) or
            not isinstance(manifest.get("blocked_sources"), dict)):
        raise PackagingError("evidence_manifest.json is not a complete full extraction report")
    return members


def build_code_zip(code_root: Path, destination: Path, *, replace: bool = False) -> list[str]:
    """Atomically write a reproducible code.zip and return its member names."""
    code_root = code_root.resolve()
    destination = destination.resolve()
    if destination.suffix.lower() != ".zip":
        raise PackagingError("Package destination must have a .zip suffix")
    if destination.exists() and not replace:
        raise PackagingError(f"Destination already exists: {destination}")

    members = submission_members(code_root)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
        )
        os.close(descriptor)
        temporary = Path(temporary_name)
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for relative in members:
                info = zipfile.ZipInfo(relative.as_posix(), date_time=FIXED_TIMESTAMP)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.create_system = 3
                info.external_attr = 0o100644 << 16
                archive.writestr(info, (code_root / relative).read_bytes(), compresslevel=9)
        os.replace(temporary, destination)
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return [member.as_posix() for member in members]
