# src/pdf_viewer_core/core.py
"""
プロジェクトの中核ロジック。
UI（PyQt）を起動し、アプリ全体を統括するエントリ。
"""

from __future__ import annotations

import sys
from pathlib import Path

from PyQt6.QtWidgets import QApplication

from pdf_viewer_core.ui.main_window import MainWindow


def main() -> None:
    app = QApplication(sys.argv)
    win = MainWindow()

    # 起動引数でPDFパスを受け取る（任意）
    # 例: pdf-viewer-core.exe path.pdf
    if len(sys.argv) >= 2:
        p = Path(sys.argv[1]).expanduser()
        if p.exists() and p.is_file() and p.suffix.lower() == ".pdf":
            win.open_pdf(p)

    win.show()
    sys.exit(app.exec())
