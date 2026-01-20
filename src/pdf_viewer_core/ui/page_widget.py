# src/pdf_viewer_core/ui/page_widget.py
from __future__ import annotations

import pypdfium2 as pdfium
from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QImage, QPainter, QPixmap, QColor, QPen
from PyQt6.QtWidgets import QLabel, QWidget, QVBoxLayout


class PageWidget(QWidget):
    def __init__(self, doc: pdfium.PdfDocument, page_index: int, zoom: float) -> None:
        super().__init__()
        self._doc = doc
        self.page_index = page_index
        self._zoom = zoom

        self._label = QLabel(self)
        self._label.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self._label)

        self._pixmap: QPixmap | None = None
        self._page_w: float = 1.0
        self._page_h: float = 1.0

        # 検索ヒットしたページの枠強調
        self._active_match: bool = False

        # PDF座標系のハイライト矩形（l,t,r,b）
        self._highlight_rects: list[tuple[float, float, float, float]] = []

        self._render()

    def set_zoom(self, zoom: float) -> None:
        if abs(self._zoom - zoom) < 1e-6:
            return
        self._zoom = zoom
        self._render()

    def set_highlight_rects(self, rects: list[tuple[float, float, float, float]]) -> None:
        self._highlight_rects = rects
        self._render_overlay()

    def set_active_match(self, active: bool) -> None:
        if self._active_match == active:
            return
        self._active_match = active
        self._render_overlay()

    def _render(self) -> None:
        page = self._doc.get_page(self.page_index)

        # ページサイズ（PDFポイント）
        w_pt, h_pt = page.get_size()
        self._page_w = float(w_pt)
        self._page_h = float(h_pt)

        # レンダリング倍率（zoom * 150dpi相当のざっくり）
        scale = self._zoom * 2.0

        bitmap = page.render(scale=scale)
        pil = bitmap.to_pil()

        # PIL -> QImage（RGBA）
        rgba = pil.convert("RGBA")
        data = rgba.tobytes("raw", "RGBA")
        qimg = QImage(data, rgba.width, rgba.height, QImage.Format.Format_RGBA8888)

        self._pixmap = QPixmap.fromImage(qimg)
        self._render_overlay()

    def _render_overlay(self) -> None:
        if not self._pixmap:
            return

        pm = QPixmap(self._pixmap)  # copy
        painter = QPainter(pm)

        # ---- ヒットページの強調（青枠） ----
        if self._active_match:
            # 枠は強めに
            pen = QPen(QColor(30, 110, 255, 230))
            pen.setWidth(6)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(0, 0, pm.width() - 1, pm.height() - 1)

        # ---- ハイライト描画（OneNote寄せ：塗り＋枠＋角丸） ----
        if self._highlight_rects:
            fill = QColor(255, 235, 120, 170)    # 透明度込み
            border = QColor(180, 140, 40, 220)   # 輪郭

            pen = QPen(border)
            pen.setWidth(2)
            painter.setPen(pen)
            painter.setBrush(fill)

            for (l, t, r, b) in self._highlight_rects:
                rect = self._pdf_rect_to_image_rect(l, t, r, b, pm.width(), pm.height())

                # 最低保証の行高（小さすぎるbbox対策）
                approx_line_h = pm.height() / 55.0

                # 文字サイズ由来の高さ（こちらが主役）
                h_char = max(1.0, rect.height())

                # 実際に使う“帯の基準高さ”
                band_h = max(h_char, approx_line_h * 0.55)

                pad_x = 3
                pad_y = band_h * 0.35

                # 下寄り補正：帯高さに応じて上に持ち上げる
                shift_up = band_h * 0.18

                rect = rect.adjusted(-pad_x, -pad_y, +pad_x, +pad_y)
                rect.translate(0.0, -shift_up)

                painter.drawRoundedRect(rect, 5, 5)







        painter.end()
        self._label.setPixmap(pm)

    def _pdf_rect_to_image_rect(self, l: float, t: float, r: float, b: float, img_w: int, img_h: int) -> QRectF:
        """
        PDFiumの矩形を画像座標へ変換。
        PDFの座標系は下原点になりがちなので、ここは一番ズレやすいポイント。
        まずは「上下反転」前提で実装し、ズレが出たらここだけ直す。
        """
        # PDF座標 -> 正規化
        x0 = l / self._page_w
        x1 = r / self._page_w

        # yは上下反転（PDFの下原点を想定）
        y0 = 1.0 - (b / self._page_h)
        y1 = 1.0 - (t / self._page_h)

        px0 = x0 * img_w
        px1 = x1 * img_w
        py0 = y0 * img_h
        py1 = y1 * img_h

        return QRectF(px0, py0, max(1.0, px1 - px0), max(1.0, py1 - py0))

    def pdf_y_to_local_y(self, y_pdf: float) -> float:
        """
        PDF座標(y) -> PageWidgetローカル座標(y) に変換する。
        y_pdf は PDF座標系（ページ下原点でも上原点でもOK）
        ここでは _pdf_rect_to_image_rect と同じ変換規約を使う。
        """
        if not self._pixmap:
            return 0.0

        img_h = float(self._pixmap.height())

        # _pdf_rect_to_image_rect と同じ「上下反転」前提
        y_norm = 1.0 - (y_pdf / self._page_h)
        y_img = y_norm * img_h

        # QLabel は PageWidget 内で上に配置されているので、そのまま返してOK
        return y_img
