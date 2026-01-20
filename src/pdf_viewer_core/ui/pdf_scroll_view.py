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
    rects: list[tuple[float, float, float, float]]
    active_rect: int = 0


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

            # 1) ページ全文テキストを取得（char index と対応する前提）
            try:
                n = int(textpage.count_chars())
                full = textpage.get_text_range(0, n) or ""
            except Exception:
                continue

            # 2) 出現位置を全部拾う（ページ内すべてハイライト）
            starts: list[int] = []
            pos = 0
            while True:
                idx = full.find(q, pos)
                if idx < 0:
                    break
                starts.append(idx)
                pos = idx + max(1, len(q))

            if not starts:
                continue

            # 3) 文字 bbox を取り、行ごとにマージして rects を作る
            rects: list[tuple[float, float, float, float]] = []

            for s in starts:
                e = min(n, s + len(q))

                # 文字ごとの矩形を集める
                char_rects: list[tuple[float, float, float, float]] = []
                for ci in range(s, e):
                    try:
                        box = textpage.get_charbox(ci)
                    except Exception:
                        continue

                    # box が Rect オブジェクト or タプルの両対応
                    if hasattr(box, "left"):
                        l = float(box.left)
                        b = float(getattr(box, "bottom", 0.0))
                        r = float(box.right)
                        t = float(getattr(box, "top", 0.0))
                    else:
                        # 典型: (left, bottom, right, top)
                        l, b, r, t = map(float, box)

                    # 座標の上下が逆でも成立するように正規化
                    l2 = min(l, r)
                    r2 = max(l, r)
                    b2 = min(b, t)
                    t2 = max(b, t)

                    # 無効矩形を弾く（正規化後）
                    if r2 <= l2 or t2 <= b2:
                        continue

                    char_rects.append((l2, t2, r2, b2))  # (l, t, r, b)


                # 4) 同一行っぽい矩形をまとめて「行の帯」を作る
                if not char_rects:
                    continue

                # topの近さで行クラスタリング（yは PDF座標系）
                # 同一行の判定幅は「代表文字高さ」から算出
                # char_rects: (l, t, r, b)
                char_rects.sort(key=lambda x: (-(x[1]), x[0]))  # top降順, x昇順

                # 代表的な文字高さ（中央値）を使って頑健にする
                heights = sorted((t - b) for (_, t, _, b) in char_rects if t > b)
                if heights:
                    h_med = heights[len(heights) // 2]
                else:
                    h_med = 1.0

                line_tol = max(1e-3, h_med * 0.7)  # topの許容幅（行判定）

                # 行クラスタを作る
                lines: list[list[tuple[float, float, float, float]]] = []
                cur: list[tuple[float, float, float, float]] = [char_rects[0]]
                cur_top = char_rects[0][1]

                for (l, t, r, b) in char_rects[1:]:
                    if abs(t - cur_top) <= line_tol:
                        cur.append((l, t, r, b))
                        # 行の代表topを少し追随させる（ドリフト抑制）
                        cur_top = (cur_top * 0.8) + (t * 0.2)
                    else:
                        lines.append(cur)
                        cur = [(l, t, r, b)]
                        cur_top = t
                lines.append(cur)

                # 行ごとに帯(rect)を作る：Xはその行内の検索語範囲、Yは行高
                for line in lines:
                    lmin = min(x[0] for x in line)
                    tmax = max(x[1] for x in line)
                    rmax = max(x[2] for x in line)
                    bmin = min(x[3] for x in line)

                    # 見やすさ用の余白（PDF座標系で加える）
                    pad_x = h_med * 0.15
                    pad_y = h_med * 0.25

                    rects.append((
                        lmin - pad_x,
                        tmax + pad_y,
                        rmax + pad_x,
                        bmin - pad_y,
                    ))

            if rects:
                self._hits.append(Hit(page_index=i, rects=rects))


    def _clear_all_highlights(self) -> None:
        for i in range(self._layout.count()):
            w = self._layout.itemAt(i).widget()
            if isinstance(w, PageWidget):
                w.set_highlight_rects([])

    def _apply_hit(self, hit: Hit) -> None:
        # まず全ページの表示状態を更新（ターゲット以外は消す）
        target_widget: PageWidget | None = None

        for i in range(self._layout.count()):
            w = self._layout.itemAt(i).widget()
            if not isinstance(w, PageWidget):
                continue

            is_target = (w.page_index == hit.page_index)
            w.set_active_match(is_target)

            if is_target:
                w.set_highlight_rects(hit.rects)
                target_widget = w
            else:
                w.set_highlight_rects([])

        # ターゲットページが無い / rectが無い場合は従来通り
        if not target_widget or not hit.rects:
            if target_widget:
                self.ensureWidgetVisible(target_widget, xMargin=0, yMargin=40)
            return

        # ---- 中央スクロール（ターゲットページのみ）----
        w = target_widget
        l, t, r, b = hit.rects[min(hit.active_rect, len(hit.rects) - 1)]

        # PDF座標での中心y
        y_pdf_center = (t + b) * 0.5

        # PageWidget内のローカルy（画像座標系）
        y_local = w.pdf_y_to_local_y(y_pdf_center)

        # ScrollAreaのビューポート中央に合わせる
        viewport_h = self.viewport().height()
        target_in_widget = int(y_local - viewport_h * 0.5)

        # PageWidgetのScrollArea内での位置（widget上端のオフセット）
        y_in_container = w.y() + target_in_widget

        sb = self.verticalScrollBar()
        sb.setValue(max(sb.minimum(), min(sb.maximum(), y_in_container)))



    def find_next(self, query: str) -> bool:
        if not self._doc:
            return False

        q = query.strip()
        if not q:
            return False

        if not self._hits or self._last_query != q:
            self._last_query = q
            self._build_hits(q)

        if not self._hits:
            return False

        # 初回
        if self._hit_cursor == -1:
            self._hit_cursor = 0
            self._hits[0] = Hit(self._hits[0].page_index, self._hits[0].rects, active_rect=0)
            self._apply_hit(self._hits[0])
            return True

        hit = self._hits[self._hit_cursor]
        if hit.rects and hit.active_rect < len(hit.rects) - 1:
            # 同ページ内で次のrectへ
            self._hits[self._hit_cursor] = Hit(hit.page_index, hit.rects, active_rect=hit.active_rect + 1)
            self._apply_hit(self._hits[self._hit_cursor])
            return True

        # 次ページへ
        if self._hit_cursor < len(self._hits) - 1:
            self._hit_cursor += 1
            hit2 = self._hits[self._hit_cursor]
            self._hits[self._hit_cursor] = Hit(hit2.page_index, hit2.rects, active_rect=0)
            self._apply_hit(self._hits[self._hit_cursor])
            return True

        # 最後まで行ったら末尾で止める（循環させたいならここを変える）
        self._apply_hit(self._hits[self._hit_cursor])
        return True


    def find_prev(self, query: str) -> bool:
        if not self._doc:
            return False

        q = query.strip()
        if not q:
            return False

        if not self._hits or self._last_query != q:
            self._last_query = q
            self._build_hits(q)

        if not self._hits:
            return False

        # 初回（prev押下時は最後へ）
        if self._hit_cursor == -1:
            self._hit_cursor = len(self._hits) - 1
            hit = self._hits[self._hit_cursor]
            last_idx = max(0, len(hit.rects) - 1)
            self._hits[self._hit_cursor] = Hit(hit.page_index, hit.rects, active_rect=last_idx)
            self._apply_hit(self._hits[self._hit_cursor])
            return True

        hit = self._hits[self._hit_cursor]
        if hit.rects and hit.active_rect > 0:
            # 同ページ内で前のrectへ
            self._hits[self._hit_cursor] = Hit(hit.page_index, hit.rects, active_rect=hit.active_rect - 1)
            self._apply_hit(self._hits[self._hit_cursor])
            return True

        # 前ページへ
        if self._hit_cursor > 0:
            self._hit_cursor -= 1
            hit2 = self._hits[self._hit_cursor]
            last_idx = max(0, len(hit2.rects) - 1)
            self._hits[self._hit_cursor] = Hit(hit2.page_index, hit2.rects, active_rect=last_idx)
            self._apply_hit(self._hits[self._hit_cursor])
            return True

        # 先頭まで行ったら先頭で止める
        self._apply_hit(self._hits[self._hit_cursor])
        return True


    def get_search_status(self) -> tuple[int, int, int] | None:
        """
        Returns (current_index_1based, total_hits, current_page_1based)
        何もヒットしていなければ None
        """
        if not self._hits or self._hit_cursor < 0:
            return None

        # 総ヒット数（rect総数）
        total = sum(len(h.rects) for h in self._hits)
        if total <= 0:
            return None

        hit = self._hits[self._hit_cursor]
        active = min(hit.active_rect, max(0, len(hit.rects) - 1))

        # 先頭からの通し番号を作る
        before = 0
        for k in range(self._hit_cursor):
            before += len(self._hits[k].rects)

        current_1based = before + active + 1
        page_1based = hit.page_index + 1
        return (current_1based, total, page_1based)
