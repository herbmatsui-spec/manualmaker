#!/usr/bin/env python3
"""
Checksum Generator for Manual Processor
Generates SHA256 checksums for distribution files.
"""

import hashlib
import os
from pathlib import Path
import sys


def calculate_sha256(file_path: Path) -> str:
    """Calculate SHA256 hash of a file."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            sha256_hash.update(chunk)
    return sha256_hash.hexdigest()


def generate_checksums(dist_dir: Path, output_file: Path = None) -> None:
    """
    Generate checksums for all files in dist directory.

    Args:
        dist_dir: Path to dist directory containing files to checksum
        output_file: Optional path to output checksum file
    """
    if not dist_dir.exists():
        print(f"Error: Directory not found: {dist_dir}")
        sys.exit(1)

    files = sorted(dist_dir.glob("*"))
    if not files:
        print("No files found in dist directory")
        sys.exit(1)

    checksums = []
    for file_path in files:
        if file_path.is_file():
            checksum = calculate_sha256(file_path)
            checksums.append(f"{checksum}  {file_path.name}")
            print(f"{checksum}  {file_path.name}")

    if output_file:
        output_file.write_text("\n".join(checksums) + "\n")
        print(f"\nChecksums saved to: {output_file}")


def verify_checksums(dist_dir: Path, checksum_file: Path) -> bool:
    """
    Verify checksums against files in dist directory.

    Args:
        dist_dir: Path to dist directory
        checksum_file: Path to checksum file

    Returns:
        True if all checksums match, False otherwise
    """
    if not checksum_file.exists():
        print(f"Error: Checksum file not found: {checksum_file}")
        return False

    lines = checksum_file.read_text().strip().split("\n")
    all_match = True

    for line in lines:
        if not line.strip():
            continue
        parts = line.split()
        if len(parts) != 2:
            continue
        expected_hash, filename = parts
        file_path = dist_dir / filename

        if not file_path.exists():
            print(f"MISSING: {filename}")
            all_match = False
            continue

        actual_hash = calculate_sha256(file_path)
        if actual_hash == expected_hash:
            print(f"OK: {filename}")
        else:
            print(f"MISMATCH: {filename}")
            all_match = False

    return all_match


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Generate or verify file checksums")
    parser.add_argument("command", choices=["generate", "verify"],
                       help="Command: generate or verify checksums")
    parser.add_argument("--dist-dir", type=Path, default=Path("dist"),
                       help="Path to dist directory (default: dist)")
    parser.add_argument("--output", type=Path, default=Path("dist/checksums.txt"),
                       help="Output file for checksums (default: dist/checksums.txt)")
    parser.add_argument("--checksum-file", type=Path, default=Path("dist/checksums.txt"),
                       help="Checksum file to verify (default: dist/checksums.txt)")

    args = parser.parse_args()

    if args.command == "generate":
        generate_checksums(args.dist_dir, args.output)
    else:
        if verify_checksums(args.dist_dir, args.checksum_file):
            print("\nAll checksums verified successfully!")
            sys.exit(0)
        else:
            print("\nChecksum verification FAILED!")
            sys.exit(1)


if __name__ == "__main__":
    main()
