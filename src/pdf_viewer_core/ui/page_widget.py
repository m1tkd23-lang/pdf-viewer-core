# src/pdf_viewer_core/ui/page_widget.py
from __future__ import annotations

import pypdfium2 as pdfium
from PyQt6.QtCore import Qt, QRectF, QPointF
from PyQt6.QtGui import QImage, QPainter, QPixmap, QColor, QPen, QTransform
from PyQt6.QtWidgets import QLabel, QWidget, QVBoxLayout

from pdf_viewer_core.ui.page_rotation import Rotation, rotated_size, map_rect_unrot_to_rot, map_point_unrot_to_rot


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

        self._pixmap_unrot: QPixmap | None = None
        self._page_w: float = 1.0
        self._page_h: float = 1.0

        self._rotation = Rotation(0)

        self._active_match: bool = False
        self._highlight_rects: list[tuple[float, float, float, float]] = []

        self._render()

    # ---- public ----

    def set_zoom(self, zoom: float) -> None:
        if abs(self._zoom - zoom) < 1e-6:
            return
        self._zoom = zoom
        self._render()

    def set_rotation_cw(self) -> None:
        self._rotation = self._rotation.cw()
        self._render_overlay()

    def set_rotation_ccw(self) -> None:
        self._rotation = self._rotation.ccw()
        self._render_overlay()

    def reset_rotation(self) -> None:
        self._rotation = Rotation(0)
        self._render_overlay()

    def set_highlight_rects(self, rects: list[tuple[float, float, float, float]]) -> None:
        self._highlight_rects = rects
        self._render_overlay()

    def set_active_match(self, active: bool) -> None:
        if self._active_match == active:
            return
        self._active_match = active
        self._render_overlay()

    def pdf_y_to_local_y(self, y_pdf: float) -> float:
        """
        PDF座標の y を、現在の回転/ズームでレンダ済み画像（ローカル）座標へ変換した y を返す。
        """
        if not self._pixmap_unrot:
            return 0.0

        # unrot画像内での点（xは中央寄せで 0.5 あたりを使う）
        x_pdf = self._page_w * 0.5
        p = self._pdf_point_to_image_point(x_pdf, y_pdf, self._pixmap_unrot.width(), self._pixmap_unrot.height())

        # 回転後座標へ
        rp = map_point_unrot_to_rot(p.x(), p.y(), self._pixmap_unrot.width(), self._pixmap_unrot.height(), self._rotation.normalized())
        return float(rp.y())

    # ---- internal ----

    def _render(self) -> None:
        page = self._doc.get_page(self.page_index)

        # ページサイズ（PDFポイント）
        w_pt, h_pt = page.get_size()
        self._page_w = float(w_pt)
        self._page_h = float(h_pt)

        # レンダリング倍率（ざっくり）
        scale = self._zoom * 2.0

        bitmap = page.render(scale=scale)
        pil = bitmap.to_pil()

        rgba = pil.convert("RGBA")
        data = rgba.tobytes("raw", "RGBA")
        qimg = QImage(data, rgba.width, rgba.height, QImage.Format.Format_RGBA8888)

        self._pixmap_unrot = QPixmap.fromImage(qimg)
        self._render_overlay()

    def page_size_pt(self) -> tuple[float, float]:
        return (self._page_w, self._page_h)


    def _render_overlay(self) -> None:
        if not self._pixmap_unrot:
            return

        # 回転したベース画像を作る（ここは「表示用」）
        pm_base = self._rotated_pixmap(self._pixmap_unrot, self._rotation.normalized())

        pm = QPixmap(pm_base)  # copyして上に描く
        painter = QPainter(pm)

        # ヒットページの強調（枠線）
        if self._active_match:
            painter.setOpacity(0.9)
            pen = painter.pen()
            pen.setWidth(6)
            pen.setColor(Qt.GlobalColor.blue)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(0, 0, pm.width() - 1, pm.height() - 1)

        # ハイライト描画（半透明）
        painter.setOpacity(0.55)
        pen = QPen(QColor(180, 140, 40))
        pen.setWidth(2)
        painter.setPen(pen)
        painter.setBrush(QColor(255, 230, 120))

        # rect: PDF座標→unrot画像→rot画像
        for (l, t, r, b) in self._highlight_rects:
            rect_unrot = self._pdf_rect_to_image_rect_unrot(l, t, r, b, self._pixmap_unrot.width(), self._pixmap_unrot.height())
            rect_rot = map_rect_unrot_to_rot(rect_unrot, self._pixmap_unrot.width(), self._pixmap_unrot.height(), self._rotation.normalized())
            painter.drawRoundedRect(rect_rot, 4.0, 4.0)

        painter.end()
        self._label.setPixmap(pm)

    def _rotated_pixmap(self, pm: QPixmap, rot_deg: int) -> QPixmap:
        r = rot_deg % 360
        if r == 0:
            return pm

        # ここは「見た目」をCWにしたいので、Qtの回転(反時計回り)に合わせて符号を反転
        # CW 90 => Qtでは -90
        qt_deg = -r
        tr = QTransform()
        tr.rotate(qt_deg)
        return pm.transformed(tr, Qt.TransformationMode.SmoothTransformation)

    def _pdf_point_to_image_point(self, x_pdf: float, y_pdf: float, img_w: int, img_h: int) -> QPointF:
        """
        PDF座標 -> unrot画像座標（ページ描画に対応した向き）
        PDFは下原点想定で反転して合わせる。
        """
        x0 = x_pdf / self._page_w
        y0 = 1.0 - (y_pdf / self._page_h)

        px = x0 * img_w
        py = y0 * img_h
        return QPointF(px, py)

    def _pdf_rect_to_image_rect_unrot(self, l: float, t: float, r: float, b: float, img_w: int, img_h: int) -> QRectF:
        """
        PDFium矩形(l,t,r,b) -> unrot画像座標へ。
        """
        # 正規化
        x0 = min(l, r) / self._page_w
        x1 = max(l, r) / self._page_w

        # PDFは下原点想定（b,tを反転）
        y0 = 1.0 - (min(b, t) / self._page_h)
        y1 = 1.0 - (max(b, t) / self._page_h)

        px0 = x0 * img_w
        px1 = x1 * img_w
        py0 = y1 * img_h
        py1 = y0 * img_h

        return QRectF(px0, py0, max(1.0, px1 - px0), max(1.0, py1 - py0))
    
    
    def rotation_deg(self) -> int:
        return self._rotation.normalized()
