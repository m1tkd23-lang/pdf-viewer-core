# src/pdf_viewer_core/ui/pdf_scroll_view.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pypdfium2 as pdfium
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QScrollArea, QVBoxLayout, QWidget

from pdf_viewer_core.ui.page_widget import PageWidget


@dataclass(frozen=True)
class Hit:
    page_index: int
    rects: list[tuple[float, float, float, float]]  # (l, t, r, b)


class PdfScrollView(QScrollArea):
    def __init__(self) -> None:
        super().__init__()
        self.setWidgetResizable(True)

        self._container = QWidget()
        self._layout = QVBoxLayout(self._container)
        self._layout.setContentsMargins(8, 8, 8, 8)
        self._layout.setSpacing(12)
        self.setWidget(self._container)

        self._doc: pdfium.PdfDocument | None = None
        self._path: Path | None = None
        self._zoom: float = 1.0

        self._hits: list[Hit] = []
        self._hit_cursor: int = -1
        self._last_query: str | None = None

        # Ctrl+Wheel でズーム
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

    def clear(self) -> None:
        while self._layout.count():
            item = self._layout.takeAt(0)
            w = item.widget()
            if w:
                w.setParent(None)
        self._doc = None
        self._path = None
        self._hits = []
        self._hit_cursor = -1
        self._last_query = None

    def load_pdf(self, path: Path) -> None:
        self.clear()
        self._path = path
        self._doc = pdfium.PdfDocument(str(path))

        for i in range(len(self._doc)):
            pw = PageWidget(doc=self._doc, page_index=i, zoom=self._zoom)
            self._layout.addWidget(pw)

        self._layout.addStretch(1)

    def zoom_by(self, factor: float) -> None:
        self._zoom = max(0.2, min(5.0, self._zoom * factor))
        for i in range(self._layout.count()):
            w = self._layout.itemAt(i).widget()
            if isinstance(w, PageWidget):
                w.set_zoom(self._zoom)

    def wheelEvent(self, event) -> None:
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y()
            if delta > 0:
                self.zoom_by(1.1)
            elif delta < 0:
                self.zoom_by(1 / 1.1)
            event.accept()
            return
        super().wheelEvent(event)

    # ---- Search ----

    def _build_hits(self, query: str) -> None:
        if not self._doc:
            return

        self._hits = []
        self._hit_cursor = -1
        self._clear_all_highlights()

        q = query.strip()
        if not q:
            return

        for i in range(len(self._doc)):
            page = self._doc.get_page(i)
            textpage = page.get_textpage()

            # --- 1) まずページテキストを取る（API差吸収） ---
            text = ""
            try:
                if hasattr(textpage, "count_chars") and hasattr(textpage, "get_text_range"):
                    n = int(textpage.count_chars())
                    text = textpage.get_text_range(0, n) or ""
                elif hasattr(textpage, "get_text_range"):
                    # 実装によっては引数なしで全体を返す
                    text = textpage.get_text_range() or ""
                elif hasattr(textpage, "get_text_bounded"):
                    # 最終手段（範囲指定が必要な実装もある）
                    w, h = page.get_size()
                    text = textpage.get_text_bounded(0, 0, float(w), float(h)) or ""
            except Exception:
                text = ""

            # デバッグ（開発中のみ）：テキストが取れているか
            # print(f"[page {i}] chars={len(text)} sample={text[:30]!r}")

            # --- 2) Python側で一致判定（まずはこれで十分） ---
            if q in text:
                # いったん「このページにヒット」だけ確定させる
                # ハイライト矩形は後で精密化（次ステップ）
                self._hits.append(Hit(page_index=i, rects=[]))

    def _clear_all_highlights(self) -> None:
        for i in range(self._layout.count()):
            w = self._layout.itemAt(i).widget()
            if isinstance(w, PageWidget):
                w.set_highlight_rects([])

    def _apply_hit(self, hit: Hit) -> None:
        for i in range(self._layout.count()):
            w = self._layout.itemAt(i).widget()
            if isinstance(w, PageWidget):
                if w.page_index == hit.page_index:
                    w.set_highlight_rects(hit.rects)
                    self.ensureWidgetVisible(w, xMargin=0, yMargin=40)
                else:
                    w.set_highlight_rects([])

    def find_next(self, query: str) -> bool:
        if not self._doc:
            return False

        if not self._hits or self._last_query != query:
            self._last_query = query
            self._build_hits(query)

        if not self._hits:
            return False

        self._hit_cursor = min(len(self._hits) - 1, self._hit_cursor + 1)
        self._apply_hit(self._hits[self._hit_cursor])
        return True

    def find_prev(self, query: str) -> bool:
        if not self._doc:
            return False

        if not self._hits or self._last_query != query:
            self._last_query = query
            self._build_hits(query)

        if not self._hits:
            return False

        if self._hit_cursor == -1:
            self._hit_cursor = len(self._hits) - 1
        else:
            self._hit_cursor = max(0, self._hit_cursor - 1)

        self._apply_hit(self._hits[self._hit_cursor])
        return True
