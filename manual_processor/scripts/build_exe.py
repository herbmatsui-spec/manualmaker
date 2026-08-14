"""
Script to build standalone executable using PyInstaller
"""

import os
import shutil
import subprocess
from pathlib import Path

def build_exe():
    project_root = Path(__file__).parent.parent
    dist_dir = project_root / "dist"
    build_dir = project_root / "build"
    spec_file = project_root / "manual_processor.spec"

    print("--- 既存のビルド成果物をクリーンアップ中 ---")
    if dist_dir.exists():
        shutil.rmtree(dist_dir)
    if build_dir.exists():
        shutil.rmtree(build_dir)

    print(f"--- PyInstaller ビルド開始: {spec_file.name} ---")
    cmd = [
        "pyinstaller",
        "--clean",
        str(spec_file)
    ]
    
    res = subprocess.run(cmd, cwd=project_root)
    if res.returncode == 0:
        exe_path = dist_dir / "ManualProcessor.exe"
        if exe_path.exists():
            size_mb = exe_path.stat().st_size / (1024 * 1024)
            print(f"\n✅ ビルド成功！: {exe_path} ({size_mb:.2f} MB)")
        else:
            print(f"\n✅ ビルド完了（出力先: {dist_dir}）")
    else:
        print(f"\n❌ ビルド失敗 (Return code: {res.returncode})")

if __name__ == "__main__":
    build_exe()
