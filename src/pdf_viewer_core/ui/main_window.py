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
    QDockWidget,
    QListWidget,
    QListWidgetItem,
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
        self._build_results_dock()
        self._build_menus()

        self._update_search_status()
        self._refresh_results_list()

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

        act_rot_l = QAction("Rotate ⟲", self)
        act_rot_l.setShortcut(QKeySequence("Ctrl+Shift+R"))
        act_rot_l.triggered.connect(self._view.rotate_ccw)
        tb.addAction(act_rot_l)

        act_rot_r = QAction("Rotate ⟳", self)
        act_rot_r.setShortcut(QKeySequence("Ctrl+R"))
        act_rot_r.triggered.connect(self._view.rotate_cw)
        tb.addAction(act_rot_r)
        tb.addSeparator()

        act_fit = QAction("Fit", self)
        act_fit.setShortcut(QKeySequence("Ctrl+Shift+F"))
        act_fit.setStatusTip("Fit page to window (both width & height)")
        act_fit.triggered.connect(lambda: (self._view.zoom_fit_page(), self._update_zoom_status()))
        tb.addAction(act_fit)

        act_100 = QAction("100%", self)
        act_100.setStatusTip("Actual size (app-defined 100%)")
        act_100.triggered.connect(lambda: (self._view.zoom_100(), self._update_zoom_status()))
        tb.addAction(act_100)

        tb.addSeparator()

        act_zoomin = QAction("Zoom +", self)
        act_zoomin.setShortcut(QKeySequence.StandardKey.ZoomIn)
        act_zoomin.triggered.connect(lambda: (self._view.zoom_by(1.1), self._update_zoom_status()))
        tb.addAction(act_zoomin)

        act_zoomout = QAction("Zoom -", self)
        act_zoomout.setShortcut(QKeySequence.StandardKey.ZoomOut)
        act_zoomout.triggered.connect(lambda: (self._view.zoom_by(1 / 1.1), self._update_zoom_status()))
        tb.addAction(act_zoomout)



        tb.addSeparator()

        # 検索ステータス（常時表示）
        self._lbl_status = QLabel("0/0", self)
        self._lbl_status.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight)
        self._lbl_status.setMinimumWidth(140)
        tb.addWidget(self._lbl_status)

        # Ctrl+F で検索欄へ
        act_focus_find = QAction("Find", self)
        act_focus_find.setShortcut(QKeySequence.StandardKey.Find)
        act_focus_find.triggered.connect(self._focus_search)
        self.addAction(act_focus_find)

    def _build_results_dock(self) -> None:
        self._dock = QDockWidget("Results", self)
        self._dock.setAllowedAreas(Qt.DockWidgetArea.RightDockWidgetArea | Qt.DockWidgetArea.LeftDockWidgetArea)

        self._results = QListWidget(self)
        self._results.itemActivated.connect(self._on_result_activated)  # ダブルクリック/Enter
        self._results.itemClicked.connect(self._on_result_clicked)
        self._dock.setWidget(self._results)

        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self._dock)

        # 表示/非表示切り替え（Ctrl+L みたいなショートカットが欲しければ後で付ける）
        self._dock.setVisible(True)

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

        # PDFを開いたら検索状態の表示更新（結果は空になる想定）
        self._update_search_status()
        self._refresh_results_list()
        self._view.zoom_fit_page()

    def _update_search_status(self) -> None:
        st = self._view.get_search_status() if hasattr(self._view, "get_search_status") else None
        if not st:
            self._lbl_status.setText("0/0")
            return
        cur, total, page = st
        self._lbl_status.setText(f"{cur}/{total} (page {page})")

    def _refresh_results_list(self) -> None:
        """
        PdfScrollView 側の検索結果（last_query）をリスト表示
        """
        self._results.clear()

        if not hasattr(self._view, "get_search_results"):
            self._results.addItem("(not supported)")
            self._results.setEnabled(False)
            return

        results = self._view.get_search_results()
        if not results:
            self._results.addItem("(no results)")
            self._results.setEnabled(False)
            return

        self._results.setEnabled(True)

        for r in results:
            item = QListWidgetItem(r.snippet)
            # page_index / rect_index を埋め込む
            item.setData(Qt.ItemDataRole.UserRole, (r.page_index, r.rect_index))
            self._results.addItem(item)

    def _jump_to_item(self, item: QListWidgetItem) -> None:
        data = item.data(Qt.ItemDataRole.UserRole)
        if not data:
            return
        page_index, rect_index = data
        ok = self._view.goto_result(int(page_index), int(rect_index))
        if ok:
            self._update_search_status()

    def _on_result_clicked(self, item: QListWidgetItem) -> None:
        self._jump_to_item(item)

    def _on_result_activated(self, item: QListWidgetItem) -> None:
        self._jump_to_item(item)

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
        self._refresh_results_list()

    def on_find_prev(self) -> None:
        q = self._search.text().strip()
        if not q:
            return

        ok = self._view.find_prev(q)
        if not ok:
            self._notify_no_matches()

        self._update_search_status()
        self._refresh_results_list()

    # Shift+Enter を検索欄で拾って Prev にする
    def eventFilter(self, obj, event):
        if obj is self._search and event.type() == event.Type.KeyPress:
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                    self.on_find_prev()
                    return True
        return super().eventFilter(obj, event)

    def _update_zoom_status(self) -> None:
        self.statusBar().showMessage(f"Zoom: {self._view.get_zoom_percent()}%", 1500)
