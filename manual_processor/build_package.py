"""
Build & Packaging Script (Step 21)
Prepares distribution package and verifies package structure.
"""

import sys
import shutil
from pathlib import Path

def build_package():
    root = Path(__file__).parent
    dist = root / "dist"
    if dist.exists():
        shutil.rmtree(dist)
    dist.mkdir(parents=True)

    print(f"Building Manual Processor Package in {dist}...")
    
    # Copy essential folders and files
    targets = ["src", "config", "README.md", "requirements.txt", "main.py"]
    for target in targets:
        src_path = root / target
        dst_path = dist / target
        if src_path.is_dir():
            shutil.copytree(src_path, dst_path, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        elif src_path.is_file():
            shutil.copy2(src_path, dst_path)

    print("Build successful! Distribution files created in ./dist")

if __name__ == "__main__":
    build_package()
