"""
Path Resolver Module
Handles path resolution for normal execution and PyInstaller frozen executables.
"""

import sys
from pathlib import Path

def get_base_path() -> Path:
    """
    アプリケーションのベースパスを取得する。
    PyInstaller等でフリーズされている場合は sys._MEIPASS または 実行ファイル直下、
    通常のPython実行時はプロジェクトルートのパスを返す。
    """
    if getattr(sys, 'frozen', False):
        if hasattr(sys, '_MEIPASS'):
            return Path(sys._MEIPASS)
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent.parent

def get_resource_path(relative_path: str) -> Path:
    """
    相対パスからリソースの絶対パスを取得する。
    
    Args:
        relative_path: ベースパスからの相対パス文字列
    
    Returns:
        Pathオブジェクト
    """
    return get_base_path() / relative_path
