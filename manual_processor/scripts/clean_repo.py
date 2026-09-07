#!/usr/bin/env python3
"""
Repository Cleanup Utility for Manual Processor.

Removes tracked-but-should-be-ignored artifacts:
  - __pycache__/
  - *.pyc
  - build/, dist/
  - *.egg-info/
  - manual_processor/temp/, logs/*.log, output/
  - .benchmarks/, coverage artifacts
  - Noise files (e.g., "新規 テキスト ドキュメント.txt")

Usage:
    python scripts/clean_repo.py            # actual cleanup
    python scripts/clean_repo.py --dry-run  # only show what would be removed
    python scripts/clean_repo.py --tracked  # also `git rm --cached` for tracked files
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

PATTERNS_DIRS = [
    "__pycache__",
    "build",
    "dist",
    ".benchmarks",
    ".pytest_cache",
    ".mypy_cache",
    ".hypothesis",
    ".tox",
    ".nox",
    ".eggs",
    "htmlcov",
    "egg-info",
]
PATTERNS_FILES_GLOBS = [
    "*.pyc",
    "*.pyo",
    "*.pyd",
    "*.egg-info",
    "*.egg",
    "*.so",
    ".coverage",
    ".coverage.*",
    "coverage.xml",
    "*.manifest",
    "*.spec",
]
SPECIFIC_FILES = [
    "=4.0.0",
    "新規 テキスト ドキュメント.txt",
    ".coverage",
]
SPECIFIC_DIRS = [
    "temp",
    "logs",
    "output",
    "manual_processor.egg-info",
    "build",
    "benchmark/benchmark_results.json",
]


def iter_targets() -> tuple[list[Path], list[Path]]:
    dirs: list[Path] = []
    files: list[Path] = []

    skip_dirs = {".git", "node_modules", ".venv", "venv", "env", ".benchmarks"}

    for root, dirnames, filenames in os.walk(PROJECT_ROOT, followlinks=False):
        rel_root = Path(root).relative_to(PROJECT_ROOT)
        if any(part in skip_dirs for part in rel_root.parts):
            dirnames[:] = []
            continue
        for d in dirnames:
            if d in PATTERNS_DIRS or d.endswith("egg-info"):
                dirs.append(rel_root / d)
        for fn in filenames:
            for glob in PATTERNS_FILES_GLOBS:
                if fn == glob or fn.endswith(glob.lstrip("*")):
                    files.append(rel_root / fn)
                    break

    for sf in SPECIFIC_DIRS:
        p = PROJECT_ROOT / sf
        if p.is_dir() and not p.is_symlink():
            rel = Path(sf)
            if str(rel) not in {str(x) for x in dirs}:
                dirs.append(rel)
    for sf in SPECIFIC_FILES:
        p = PROJECT_ROOT / sf
        if p.is_file():
            rel = Path(sf)
            if str(rel) not in {str(x) for x in files}:
                files.append(rel)

    return sorted(set(dirs), key=str), sorted(set(files), key=str)


def main() -> int:
    parser = argparse.ArgumentParser(description="Clean repository build/cache artifacts.")
    parser.add_argument("--dry-run", action="store_true", help="Only print targets; do not delete")
    parser.add_argument("--tracked", action="store_true", help="Also git rm --cached tracked files")
    args = parser.parse_args()

    dirs, files = iter_targets()
    print(f"Directories to remove: {len(dirs)}")
    for d in dirs:
        print(f"  dir : {d}")
    print(f"Files to remove: {len(files)}")
    for f in files:
        print(f"  file: {f}")

    if args.dry_run:
        print("\n(dry-run: nothing was changed)")
        return 0

    for d in dirs:
        target = PROJECT_ROOT / d
        if target.exists():
            shutil.rmtree(target, ignore_errors=True)
    for f in files:
        target = PROJECT_ROOT / f
        if target.exists() and target.is_file():
            target.unlink()

    if args.tracked:
        for f in files:
            try:
                subprocess.run(
                    ["git", "rm", "--cached", "-f", "--quiet", str(f)],
                    cwd=PROJECT_ROOT,
                    check=False,
                )
            except FileNotFoundError:
                pass
        for d in dirs:
            try:
                subprocess.run(
                    ["git", "rm", "--cached", "-r", "-f", "--quiet", str(d)],
                    cwd=PROJECT_ROOT,
                    check=False,
                )
            except FileNotFoundError:
                pass

    print("\nDone.")
    return 0


if __name__ == "__main__":
    sys.exit(main())