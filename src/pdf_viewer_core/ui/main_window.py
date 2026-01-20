# src/pdf_viewer_core/ui/main_window.py
from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QKeySequence
from PyQt6.QtWidgets import (
    QFileDialog,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QToolBar,
    QLabel,
)

from pdf_viewer_core.services.recent_files import RecentFiles
from pdf_viewer_core.ui.pdf_scroll_view import PdfScrollView


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("pdf-viewer-core")

        self._recent = RecentFiles(app_name="pdf-viewer-core")
        self._view = PdfScrollView()
        self.setCentralWidget(self._view)

        self._build_toolbar()
        self._build_menus()

        # 起動直後の表示
        self._update_search_status()

        # 起動時に最後のファイルを開く（履歴があれば）
        last = self._recent.get_last()
        if last and Path(last).exists():
            self.open_pdf(Path(last))

    def _build_toolbar(self) -> None:
        tb = QToolBar("Main")
        tb.setMovable(False)
        self.addToolBar(tb)

        act_open = QAction("Open", self)
        act_open.setShortcut(QKeySequence.StandardKey.Open)
        act_open.triggered.connect(self.open_pdf_dialog)
        tb.addAction(act_open)

        tb.addSeparator()

        # 検索ボックス
        self._search = QLineEdit(self)
        self._search.setPlaceholderText("Search text... (Enter=Next, Shift+Enter=Prev)")
        tb.addWidget(self._search)

        # Enter / Shift+Enter で Next/Prev（検索欄にフォーカスしたまま操作できる）
        self._search.returnPressed.connect(self.on_find_next)
        self._search.installEventFilter(self)

        act_prev = QAction("Prev", self)
        act_prev.setShortcut(QKeySequence(Qt.Key.Key_F3 | Qt.KeyboardModifier.ShiftModifier))
        act_prev.triggered.connect(self.on_find_prev)
        tb.addAction(act_prev)

        act_next = QAction("Next", self)
        act_next.setShortcut(QKeySequence(Qt.Key.Key_F3))
        act_next.triggered.connect(self.on_find_next)
        tb.addAction(act_next)

        tb.addSeparator()

        act_zoomin = QAction("Zoom +", self)
        act_zoomin.setShortcut(QKeySequence.StandardKey.ZoomIn)
        act_zoomin.triggered.connect(lambda: self._view.zoom_by(1.1))
        tb.addAction(act_zoomin)

        act_zoomout = QAction("Zoom -", self)
        act_zoomout.setShortcut(QKeySequence.StandardKey.ZoomOut)
        act_zoomout.triggered.connect(lambda: self._view.zoom_by(1 / 1.1))
        tb.addAction(act_zoomout)

        tb.addSeparator()

        # 検索ステータス（常時表示）
        self._lbl_status = QLabel("0/0", self)
        self._lbl_status.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight)
        self._lbl_status.setMinimumWidth(140)
        tb.addWidget(self._lbl_status)

        # Ctrl+F で検索欄へ（ブラウザっぽい）
        act_focus_find = QAction("Find", self)
        act_focus_find.setShortcut(QKeySequence.StandardKey.Find)
        act_focus_find.triggered.connect(self._focus_search)
        self.addAction(act_focus_find)

    def _build_menus(self) -> None:
        m_file = self.menuBar().addMenu("File")

        act_open = QAction("Open...", self)
        act_open.setShortcut(QKeySequence.StandardKey.Open)
        act_open.triggered.connect(self.open_pdf_dialog)
        m_file.addAction(act_open)

        m_recent = m_file.addMenu("Recent")
        self._recent_menu = m_recent
        self._refresh_recent_menu()

        m_file.addSeparator()

        act_exit = QAction("Exit", self)
        act_exit.setShortcut(QKeySequence.StandardKey.Quit)
        act_exit.triggered.connect(self.close)
        m_file.addAction(act_exit)

    def _refresh_recent_menu(self) -> None:
        self._recent_menu.clear()
        paths = self._recent.list_paths()
        for p in paths:
            act = QAction(p, self)
            act.triggered.connect(lambda _=False, s=p: self.open_pdf(Path(s)))
            self._recent_menu.addAction(act)
        if not paths:
            self._recent_menu.addAction("(empty)").setEnabled(False)

    def _focus_search(self) -> None:
        self._search.setFocus(Qt.FocusReason.ShortcutFocusReason)
        self._search.selectAll()

    def open_pdf_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Open PDF", "", "PDF Files (*.pdf)")
        if not path:
            return
        self.open_pdf(Path(path))

    def open_pdf(self, path: Path) -> None:
        try:
            self._view.load_pdf(path)
        except Exception as e:
            QMessageBox.critical(self, "Open failed", f"{e}")
            return

        self._recent.push(str(path))
        self._refresh_recent_menu()

        # PDFを開いたら検索状態をリセット（表示更新）
        self._update_search_status()

    def _update_search_status(self) -> None:
        st = self._view.get_search_status() if hasattr(self._view, "get_search_status") else None
        if not st:
            self._lbl_status.setText("0/0")
            return
        cur, total, page = st
        self._lbl_status.setText(f"{cur}/{total} (page {page})")

    def _notify_no_matches(self) -> None:
        self.statusBar().showMessage("No matches", 1500)

    def on_find_next(self) -> None:
        q = self._search.text().strip()
        if not q:
            return

        ok = self._view.find_next(q)
        if not ok:
            self._notify_no_matches()
        self._update_search_status()

    def on_find_prev(self) -> None:
        q = self._search.text().strip()
        if not q:
            return

        ok = self._view.find_prev(q)
        if not ok:
            self._notify_no_matches()
        self._update_search_status()

    # Shift+Enter を検索欄で拾って Prev にする
    def eventFilter(self, obj, event):
        if obj is self._search and event.type() == event.Type.KeyPress:
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                    self.on_find_prev()
                    return True
        return super().eventFilter(obj, event)
