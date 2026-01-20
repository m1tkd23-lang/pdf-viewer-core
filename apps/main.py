#apps\main.py
"""
アプリケーションのエントリポイント。
CLI / GUI / Web いずれの場合も、このファイルは"薄く"保つ。
- 設定読み込み
- core初期化
- UI起動（またはCLI実行）
のみを担当する。
"""
from pdf_viewer_core.core import main


if __name__ == "__main__":
    main()