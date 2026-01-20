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
    snippets: list[str]  # rects と同じ長さ
    active_rect: int = 0


@dataclass(frozen=True)
class SearchResult:
    page_index: int
    rect_index: int
    snippet: str


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

    # ---- Search (Public API) ----

    def get_search_results(self) -> list[SearchResult]:
        """
        現在の last_query に対する結果一覧を返す（ページ番号+抜粋用）
        """
        out: list[SearchResult] = []
        for h in self._hits:
            for j, snip in enumerate(h.snippets):
                out.append(SearchResult(page_index=h.page_index, rect_index=j, snippet=snip))
        return out

    def goto_result(self, page_index: int, rect_index: int) -> bool:
        """
        指定した (page_index, rect_index) のヒットへ移動
        """
        if not self._hits:
            return False

        hit_pos = -1
        for k, h in enumerate(self._hits):
            if h.page_index == page_index:
                hit_pos = k
                break

        if hit_pos < 0:
            return False

        h = self._hits[hit_pos]
        if not h.rects:
            return False

        rect_index = max(0, min(rect_index, len(h.rects) - 1))
        self._hit_cursor = hit_pos
        self._hits[hit_pos] = Hit(
            page_index=h.page_index,
            rects=h.rects,
            snippets=h.snippets,
            active_rect=rect_index,
        )
        self._apply_hit(self._hits[hit_pos])
        return True

    def get_search_status(self) -> tuple[int, int, int] | None:
        """
        Returns (current_index_1based, total_hits, current_page_1based)
        """
        if not self._hits or self._hit_cursor < 0:
            return None

        total = sum(len(h.rects) for h in self._hits)
        if total <= 0:
            return None

        hit = self._hits[self._hit_cursor]
        active = min(hit.active_rect, max(0, len(hit.rects) - 1))

        before = 0
        for k in range(self._hit_cursor):
            before += len(self._hits[k].rects)

        current_1based = before + active + 1
        page_1based = hit.page_index + 1
        return (current_1based, total, page_1based)

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
            h0 = self._hits[0]
            self._hits[0] = Hit(h0.page_index, h0.rects, h0.snippets, active_rect=0)
            self._apply_hit(self._hits[0])
            return True

        hit = self._hits[self._hit_cursor]
        if hit.rects and hit.active_rect < len(hit.rects) - 1:
            self._hits[self._hit_cursor] = Hit(hit.page_index, hit.rects, hit.snippets, active_rect=hit.active_rect + 1)
            self._apply_hit(self._hits[self._hit_cursor])
            return True

        # 次ページへ
        if self._hit_cursor < len(self._hits) - 1:
            self._hit_cursor += 1
            h2 = self._hits[self._hit_cursor]
            self._hits[self._hit_cursor] = Hit(h2.page_index, h2.rects, h2.snippets, active_rect=0)
            self._apply_hit(self._hits[self._hit_cursor])
            return True

        # 末尾で止める
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
            self._hits[self._hit_cursor] = Hit(hit.page_index, hit.rects, hit.snippets, active_rect=last_idx)
            self._apply_hit(self._hits[self._hit_cursor])
            return True

        hit = self._hits[self._hit_cursor]
        if hit.rects and hit.active_rect > 0:
            self._hits[self._hit_cursor] = Hit(hit.page_index, hit.rects, hit.snippets, active_rect=hit.active_rect - 1)
            self._apply_hit(self._hits[self._hit_cursor])
            return True

        # 前ページへ
        if self._hit_cursor > 0:
            self._hit_cursor -= 1
            hit2 = self._hits[self._hit_cursor]
            last_idx = max(0, len(hit2.rects) - 1)
            self._hits[self._hit_cursor] = Hit(hit2.page_index, hit2.rects, hit2.snippets, active_rect=last_idx)
            self._apply_hit(self._hits[self._hit_cursor])
            return True

        # 先頭で止める
        self._apply_hit(self._hits[self._hit_cursor])
        return True

    # ---- Search (Internal) ----

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

            try:
                n = int(textpage.count_chars())
                full = textpage.get_text_range(0, n) or ""
            except Exception:
                continue

            # 出現位置を拾う（単純な完全一致）
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

            rects: list[tuple[float, float, float, float]] = []
            snippets: list[str] = []

            for s in starts:
                e = min(n, s + len(q))

                # snippet（前後20文字、改行は空白に）
                left = max(0, s - 20)
                right = min(len(full), e + 20)
                snip = full[left:right].replace("\r", " ").replace("\n", " ")
                snip = " ".join(snip.split())  # 連続空白を詰める
                if left > 0:
                    snip = "..." + snip
                if right < len(full):
                    snip = snip + "..."
                snippets.append(f"p{i+1}: {snip}")

                # 文字 bbox を union して “その語” を囲う（行帯っぽくしたいなら pad を増やす）
                char_rects: list[tuple[float, float, float, float]] = []
                for ci in range(s, e):
                    try:
                        box = textpage.get_charbox(ci)
                    except Exception:
                        continue

                    if hasattr(box, "left"):
                        l = float(box.left)
                        b = float(getattr(box, "bottom", 0.0))
                        r = float(box.right)
                        t = float(getattr(box, "top", 0.0))
                    else:
                        l, b, r, t = map(float, box)

                    l2 = min(l, r)
                    r2 = max(l, r)
                    b2 = min(b, t)
                    t2 = max(b, t)
                    if r2 <= l2 or t2 <= b2:
                        continue

                    char_rects.append((l2, t2, r2, b2))

                if not char_rects:
                    # テキストはあるがbboxが取れないケースはスキップ
                    continue

                # 代表高さ（中央値）→見やすさ用余白に使う
                heights = sorted((t - b) for (_, t, _, b) in char_rects if t > b)
                h_med = heights[len(heights) // 2] if heights else 1.0

                lmin = min(x[0] for x in char_rects)
                tmax = max(x[1] for x in char_rects)
                rmax = max(x[2] for x in char_rects)
                bmin = min(x[3] for x in char_rects)

                pad_x = h_med * 0.20
                pad_y = h_med * 0.30

                rects.append((lmin - pad_x, tmax + pad_y, rmax + pad_x, bmin - pad_y))

            if rects:
                # rects/snippets は 1:1 なので長さを合わせる
                # bboxが取れずcontinueした分だけ snippets が先行している場合があるため、同期を取る
                # （bbox無しのsnippetは落とす）
                if len(snippets) != len(rects):
                    snippets = snippets[: len(rects)]
                self._hits.append(Hit(page_index=i, rects=rects, snippets=snippets, active_rect=0))

    def _clear_all_highlights(self) -> None:
        for i in range(self._layout.count()):
            w = self._layout.itemAt(i).widget()
            if isinstance(w, PageWidget):
                w.set_highlight_rects([])
                w.set_active_match(False)

    def _apply_hit(self, hit: Hit) -> None:
        # 対象ページだけハイライト、それ以外は消す
        for i in range(self._layout.count()):
            w = self._layout.itemAt(i).widget()
            if isinstance(w, PageWidget):
                is_target = (w.page_index == hit.page_index)
                w.set_active_match(is_target)

                if is_target:
                    w.set_highlight_rects(hit.rects)

                    # --- ヒット帯の中心を画面中央へ ---
                    if hit.rects:
                        l, t, r, b = hit.rects[min(hit.active_rect, len(hit.rects) - 1)]
                        y_pdf_center = (t + b) * 0.5

                        # PageWidget内のローカルy（画像座標系）
                        y_local = w.pdf_y_to_local_y(y_pdf_center)

                        viewport_h = self.viewport().height()
                        target_in_widget = int(y_local - viewport_h * 0.5)

                        y_in_container = w.y() + target_in_widget

                        sb = self.verticalScrollBar()
                        sb.setValue(max(sb.minimum(), min(sb.maximum(), y_in_container)))
                    else:
                        self.ensureWidgetVisible(w, xMargin=0, yMargin=40)
                else:
                    w.set_highlight_rects([])


    # ---- Rotation ----
    # ※ユーザー操作として「回転方向が逆」に感じるため、ここで入れ替える

    def rotate_cw(self) -> None:
        # 以前: w.set_rotation_cw()
        for i in range(self._layout.count()):
            w = self._layout.itemAt(i).widget()
            if isinstance(w, PageWidget):
                w.set_rotation_ccw()

    def rotate_ccw(self) -> None:
        # 以前: w.set_rotation_ccw()
        for i in range(self._layout.count()):
            w = self._layout.itemAt(i).widget()
            if isinstance(w, PageWidget):
                w.set_rotation_cw()


                w.set_rotation_cw()
    # ---- Zoom presets ----

    def zoom_100(self) -> None:
        """アプリ内定義の 100%（zoom=1.0）へ戻す"""
        self._zoom = 1.0
        for i in range(self._layout.count()):
            w = self._layout.itemAt(i).widget()
            if isinstance(w, PageWidget):
                w.set_zoom(self._zoom)

    def zoom_fit_page(self) -> None:
        """
        縦横どちらも収まる倍率（min）へ。
        いったん「先頭ページ」を基準にする（軽量＆安定）。
        """
        # viewport サイズ（スクロールバー等を除いた表示領域）
        vp = self.viewport()
        vp_w = max(1, vp.width())
        vp_h = max(1, vp.height())

        # レイアウト内の最初の PageWidget を拾う
        page_w: PageWidget | None = None
        for i in range(self._layout.count()):
            w = self._layout.itemAt(i).widget()
            if isinstance(w, PageWidget):
                page_w = w
                break
        if page_w is None:
            return

        # PageWidget は pt のサイズを内部に持っているのでそれを使う
        # （PageWidget 側に getter を生やすのが一番綺麗）
        pw_pt, ph_pt = page_w.page_size_pt()
        if not pw_pt or not ph_pt:
            return

        # PageWidget._render() の scale = zoom * 2.0 前提
        base_scale = 2.0

        # “ページ画像(px)” は概ね page_pt * (zoom*2.0)
        # なので zoom = vp / (page_pt*2.0)
        z_w = vp_w / (float(pw_pt) * base_scale)
        z_h = vp_h / (float(ph_pt) * base_scale)
        z = min(z_w, z_h)

        # 安全範囲
        z = max(0.2, min(5.0, z))

        self._zoom = z
        for i in range(self._layout.count()):
            w = self._layout.itemAt(i).widget()
            if isinstance(w, PageWidget):
                w.set_zoom(self._zoom)

    def get_zoom_percent(self) -> int:
        return int(round(self._zoom * 100))
