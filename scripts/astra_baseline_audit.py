#!/usr/bin/env python3
"""Read-only ASTRA baseline inventory; tests/builds run only when explicitly requested.

Run from any directory:
  python scripts/astra_baseline_audit.py --repo-root . --output /tmp/astra-baseline.json
  python scripts/astra_baseline_audit.py --repo-root . --run-tests --run-builds --output /tmp/astra-baseline.json

Do not run against a working tree while another agent is actively modifying it.
The script does not install packages, mutate Git refs, delete files, contact hardware,
or enable RF. Optional test/build commands can create ordinary ignored cache/build files.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

IGNORED_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}


def run_capture(args: list[str], cwd: Path, timeout: int = 20) -> dict[str, Any]:
    started = time.monotonic()
    try:
        completed = subprocess.run(
            args,
            cwd=str(cwd),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
            timeout=timeout,
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
        )
        output = completed.stdout or ""
        return {
            "command": args,
            "cwd": str(cwd),
            "return_code": completed.returncode,
            "duration_seconds": round(time.monotonic() - started, 3),
            "output_tail": output[-6000:],
        }
    except subprocess.TimeoutExpired as exc:
        output = exc.stdout or ""
        if isinstance(output, bytes):
            output = output.decode("utf-8", errors="replace")
        return {
            "command": args,
            "cwd": str(cwd),
            "return_code": 124,
            "duration_seconds": round(time.monotonic() - started, 3),
            "timed_out": True,
            "timeout_seconds": timeout,
            "output_tail": str(output)[-6000:],
        }
    except OSError as exc:
        return {
            "command": args,
            "cwd": str(cwd),
            "return_code": 127,
            "duration_seconds": round(time.monotonic() - started, 3),
            "error": str(exc),
            "output_tail": "",
        }


def git_info(root: Path) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, args in (
        ("top_level", ["git", "rev-parse", "--show-toplevel"]),
        ("branch", ["git", "branch", "--show-current"]),
        ("commit", ["git", "rev-parse", "HEAD"]),
        ("status", ["git", "status", "--short", "--branch"]),
    ):
        item = run_capture(args, root, timeout=10)
        result[key] = item["output_tail"].strip() if item["return_code"] == 0 else None
        if item["return_code"] != 0:
            result.setdefault("git_errors", []).append({"command": args, "error": item.get("output_tail", "")})
    return result


def environment_info(root: Path) -> dict[str, Any]:
    return {
        "python_executable": sys.executable,
        "python_version": sys.version.replace("\n", " "),
        "platform": platform.platform(),
        "node_version": version_of("node", ["node", "--version"], root),
        "npm_version": version_of("npm", ["npm", "--version"], root),
    }


def version_of(name: str, command: list[str], cwd: Path) -> str | None:
    if shutil.which(name) is None:
        return None
    info = run_capture(command, cwd, timeout=10)
    return info["output_tail"].strip() if info["return_code"] == 0 else None


def hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def tree_manifest(directory: Path) -> dict[str, tuple[str, str]]:
    """Return relative entries and content hashes, skipping VCS/env/cache folders."""
    entries: dict[str, tuple[str, str]] = {}
    if not directory.is_dir():
        return entries
    for current, dirs, files in os.walk(directory, followlinks=False):
        current_path = Path(current)
        dirs[:] = sorted(
            name for name in dirs
            if name not in IGNORED_DIRS and not (current_path / name).is_symlink()
        )
        for name in dirs:
            path = current_path / name
            rel = path.relative_to(directory).as_posix()
            entries[rel] = ("directory", "")
        for name in sorted(files):
            path = current_path / name
            rel = path.relative_to(directory).as_posix()
            if path.is_symlink():
                entries[rel] = ("symlink", os.readlink(path))
            elif path.is_file():
                entries[rel] = ("file", hash_file(path))
    return entries


def compare_trees(root: Path, left_rel: str, right_rel: str) -> dict[str, Any]:
    left, right = root / left_rel, root / right_rel
    left_manifest, right_manifest = tree_manifest(left), tree_manifest(right)
    left_paths, right_paths = set(left_manifest), set(right_manifest)
    shared = left_paths & right_paths
    differing = sorted(p for p in shared if left_manifest[p] != right_manifest[p])
    only_left, only_right = sorted(left_paths - right_paths), sorted(right_paths - left_paths)
    return {
        "left": left_rel,
        "right": right_rel,
        "left_exists": left.is_dir(),
        "right_exists": right.is_dir(),
        "left_entries": len(left_manifest),
        "right_entries": len(right_manifest),
        "matching_entries": sum(left_manifest[p] == right_manifest[p] for p in shared),
        "shared_entries": len(shared),
        "different_entries": differing,
        "only_left": only_left,
        "only_right": only_right,
        "identical_under_manifest_rules": left.is_dir() and right.is_dir() and not differing and not only_left and not only_right,
        "ignored_directory_names": sorted(IGNORED_DIRS),
    }



TEXT_SUFFIXES = {
    ".md", ".py", ".sh", ".bash", ".bat", ".ps1", ".yml", ".yaml",
    ".json", ".toml", ".ini", ".cfg", ".txt", ".html", ".htm",
    ".ts", ".tsx", ".js", ".jsx", ".css", ".sql", ".service", ".grc",
}
REFERENCE_SCAN_MAX_BYTES = 2 * 1024 * 1024
REFERENCE_SCAN_EXCLUDED_PATHS = {
    "docs/audits/ASTRA_REMOTE_REPOSITORY_AUDIT_2026-10-23.md",
    "docs/plans/ASTRA_REINTEGRATION_GSD_PLAN.md",
}


def path_reference_audit(root: Path) -> dict[str, Any]:
    """Find explicit references to the nested field-app path from outside that copy.

    This is a conservative static scan, not a proof that deleting the nested copy is safe:
    parent-relative imports, dynamically constructed paths, and local/untracked files may
    still depend on it.
    """
    token = "Final-Project/SHADOWLINK-FIELD"
    files_scanned = 0
    large_files_skipped = 0
    unreadable_files_skipped = 0
    matches: list[dict[str, Any]] = []
    max_matches = 500
    nested_prefix = "Final-Project/SHADOWLINK-FIELD/"
    try:
        scanner_relative_path: str | None = Path(__file__).resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        # The script can audit another checkout via --repo-root.
        scanner_relative_path = None

    for current, dirs, files in os.walk(root, followlinks=False):
        current_path = Path(current)
        rel_current = current_path.relative_to(root).as_posix()
        dirs[:] = sorted(
            name for name in dirs
            if name not in IGNORED_DIRS
            and not (current_path / name).is_symlink()
            and not (rel_current == "Final-Project" and name == "SHADOWLINK-FIELD")
        )
        for name in sorted(files):
            path = current_path / name
            rel = path.relative_to(root).as_posix()
            if (rel.startswith(nested_prefix) or rel == "Final-Project/SHADOWLINK-FIELD"
                    or (scanner_relative_path is not None and rel == scanner_relative_path)
                    or rel in REFERENCE_SCAN_EXCLUDED_PATHS):
                continue
            if path.suffix.lower() not in TEXT_SUFFIXES or path.is_symlink() or not path.is_file():
                continue
            try:
                if path.stat().st_size > REFERENCE_SCAN_MAX_BYTES:
                    large_files_skipped += 1
                    continue
                content = path.read_text(encoding="utf-8")
            except (OSError, UnicodeError):
                unreadable_files_skipped += 1
                continue
            files_scanned += 1
            for line_number, line in enumerate(content.splitlines(), start=1):
                if token in line.replace(chr(92), "/"):
                    if len(matches) < max_matches:
                        if path.suffix.lower() in {".md", ".txt"}:
                            kind = "documentation"
                        elif rel.startswith("tests/") or "/tests/" in rel:
                            kind = "test_fixture"
                        elif rel.startswith(".github/workflows/"):
                            kind = "ci_config"
                        else:
                            kind = "code_or_config"
                        matches.append({
                            "path": rel,
                            "line": line_number,
                            "kind": kind,
                            "text": line.strip()[:300],
                        })

    return {
        "token": token,
        "excluded_reference_documents": sorted(REFERENCE_SCAN_EXCLUDED_PATHS),
        "files_scanned": files_scanned,
        "large_files_skipped": large_files_skipped,
        "unreadable_files_skipped": unreadable_files_skipped,
        "match_count_returned": len(matches),
        "documentation_match_count": sum(item["kind"] == "documentation" for item in matches),
        "code_or_config_match_count": sum(item["kind"] == "code_or_config" for item in matches),
        "ci_config_match_count": sum(item["kind"] == "ci_config" for item in matches),
        "test_fixture_match_count": sum(item["kind"] == "test_fixture" for item in matches),
        "matches_truncated": len(matches) >= max_matches,
        "matches": matches,
        "interpretation": (
            "Direct literal references found; review each before consolidating the nested copy."
            if matches else
            "No direct literal references were found outside the nested copy in scanned text files. "
            "This does not prove the nested copy can be deleted: inspect relative paths, local/untracked "
            "files, imports, packaging, and deployment assumptions."
        ),
    }


def root_inventory(root: Path) -> dict[str, Any]:
    app_roots = [
        "Final-Project",
        "SHADOWLINK-FIELD",
        "Final-Project/SHADOWLINK-FIELD",
    ]
    inventory: dict[str, Any] = {}
    for rel in app_roots:
        directory = root / rel
        tests = sorted(directory.glob("tests/**/test_*.py")) if directory.is_dir() else []
        inventory[rel] = {
            "exists": directory.is_dir(),
            "python_test_file_count": len(tests),
            "python_test_files": [p.relative_to(root).as_posix() for p in tests],
            "has_frontend_package_json": (directory / "frontend/package.json").is_file(),
            "has_frontend_lockfile": (directory / "frontend/package-lock.json").is_file(),
            "has_requirements_txt": (directory / "requirements.txt").is_file(),
            "has_app_root_github_workflow_dir": (directory / ".github/workflows").is_dir(),
        }
    workflow_dirs = [root / ".github/workflows"]
    return {
        "app_roots": inventory,
        "repo_root_workflow_files": sorted(p.relative_to(root).as_posix() for d in workflow_dirs if d.is_dir() for p in d.glob("*.yml"))
        + sorted(p.relative_to(root).as_posix() for d in workflow_dirs if d.is_dir() for p in d.glob("*.yaml")),
    }


def run_baseline_commands(root: Path, run_tests: bool, run_builds: bool, timeout: int) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    if run_tests:
        for rel in ("Final-Project", "SHADOWLINK-FIELD", "Final-Project/SHADOWLINK-FIELD"):
            cwd = root / rel
            if not cwd.is_dir():
                results.append({"label": f"pytest: {rel}", "return_code": 127, "error": "directory missing"})
                continue
            item = run_capture([sys.executable, "-m", "pytest", "-o", "addopts=-ra", "-q", "tests"], cwd, timeout=timeout)
            item["label"] = f"pytest: {rel}"
            results.append(item)
    if run_builds:
        for rel in ("Final-Project/frontend", "SHADOWLINK-FIELD/frontend", "Final-Project/SHADOWLINK-FIELD/frontend"):
            cwd = root / rel
            if not cwd.is_dir() or not (cwd / "package.json").is_file():
                results.append({"label": f"npm run build: {rel}", "return_code": 127, "error": "frontend package missing"})
                continue
            item = run_capture(["npm", "run", "build"], cwd, timeout=timeout)
            item["label"] = f"npm run build: {rel}"
            results.append(item)
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd(), help="ASTRA checkout root (default: current directory)")
    parser.add_argument("--output", type=Path, default=None, help="Optional JSON report path")
    parser.add_argument("--run-tests", action="store_true", help="Run pytest in the main and both SHADOWLINK-FIELD roots")
    parser.add_argument("--run-builds", action="store_true", help="Run npm run build in all present frontends (requires dependencies already installed)")
    parser.add_argument("--timeout-seconds", type=int, default=900, help="Timeout per test/build command (default: 900)")
    args = parser.parse_args()
    if args.timeout_seconds < 1:
        parser.error("--timeout-seconds must be positive")

    root = args.repo_root.expanduser().resolve()
    if not root.is_dir():
        parser.error(f"repository root does not exist: {root}")

    timestamp = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    report: dict[str, Any] = {
        "schema_version": 1,
        "generated_at_utc": timestamp,
        "repo_root": str(root),
        "mode": {"run_tests": args.run_tests, "run_builds": args.run_builds},
        "git": git_info(root),
        "environment": environment_info(root),
        "inventory": root_inventory(root),
        "duplicate_tree_comparison": compare_trees(root, "SHADOWLINK-FIELD", "Final-Project/SHADOWLINK-FIELD"),
        "nested_path_reference_audit": path_reference_audit(root),
        "github_context": {key: os.environ.get(key) for key in ("GITHUB_REF", "GITHUB_REF_NAME", "GITHUB_SHA", "GITHUB_HEAD_REF", "GITHUB_BASE_REF") if os.environ.get(key)},
        "baseline_commands": [],
        "notes": [
            "Inventory and file comparison are read-only.",
            "Test/build commands run only when explicitly requested and do not install dependencies.",
            "Do not run against a tree while another agent is actively editing it.",
            "A matching tree snapshot does not alone prove which path deployment scripts intend to use.",
            "No physical radio or RF operation is performed by this script.",
        ],
    }
    report["baseline_commands"] = run_baseline_commands(root, args.run_tests, args.run_builds, args.timeout_seconds)
    if args.output:
        output_path = args.output.expanduser().resolve()
        report["output_file"] = str(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 1 if any(item.get("return_code", 0) != 0 for item in report["baseline_commands"]) else 0

if __name__ == "__main__":
    raise SystemExit(main())
