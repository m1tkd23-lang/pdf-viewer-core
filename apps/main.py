"""
アプリケーションのエントリポイント。
CLI / GUI / Web いずれの場合も、このファイルは"薄く"保つ。
"""
from src.pdf_viewer_core.core import main


if __name__ == "__main__":
    main()
