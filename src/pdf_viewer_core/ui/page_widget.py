# src/pdf_viewer_core/ui/page_widget.py
from __future__ import annotations

from pathlib import Path

import pypdfium2 as pdfium
from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QImage, QPainter, QPixmap
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

    def _render(self) -> None:
        page = self._doc.get_page(self.page_index)

        # ページサイズ（PDFポイント）
        w_pt, h_pt = page.get_size()
        self._page_w = float(w_pt)
        self._page_h = float(h_pt)

        # レンダリング倍率（ざっくり: zoom * 150dpi 相当）
        # 後で DPI/品質は調整しやすいようにする
        scale = self._zoom * 2.0

        bitmap = page.render(scale=scale)
        pil = bitmap.to_pil()

        # PIL -> QImage
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

        # ハイライト描画（半透明）
        painter.setOpacity(0.35)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(Qt.GlobalColor.yellow)

        for (l, t, r, b) in self._highlight_rects:
            rect = self._pdf_rect_to_image_rect(l, t, r, b, pm.width(), pm.height())
            painter.drawRect(rect)

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
