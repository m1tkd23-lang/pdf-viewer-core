# src/pdf_viewer_core/ui/page_widget.py
from __future__ import annotations

import pypdfium2 as pdfium
from PyQt6.QtCore import Qt, QRectF, QPointF
from PyQt6.QtGui import QImage, QPainter, QPixmap, QColor, QPen, QTransform
from PyQt6.QtWidgets import QLabel, QWidget, QVBoxLayout

from pdf_viewer_core.ui.page_rotation import (
    Rotation,
    map_rect_unrot_to_rot,
    map_point_unrot_to_rot,
    qt_display_transform_for_pixmap,
)


class PageWidget(QWidget):
    def __init__(self, doc: pdfium.PdfDocument, page_index: int, zoom: float) -> None:
        super().__init__()
        self._doc = doc
        self.page_index = page_index
        self._zoom = zoom

        self._label = QLabel(self)
        # 検索ジャンプ/ハイライト座標は「画像左上=原点」で扱うため、表示も左上固定にする

        self._label.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)


        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self._label)

        self._pixmap_unrot: QPixmap | None = None
        self._page_w: float = 1.0
        self._page_h: float = 1.0

        # Rotation.deg は「見た目(CW)」で保持（pdf_scroll_view 側とも一致させる）
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

    def rotation_deg(self) -> int:
        return self._rotation.normalized()

    def set_highlight_rects(self, rects: list[tuple[float, float, float, float]]) -> None:
        self._highlight_rects = rects
        self._render_overlay()

    def set_active_match(self, active: bool) -> None:
        if self._active_match == active:
            return
        self._active_match = active
        self._render_overlay()

    def page_size_pt(self) -> tuple[float, float]:
        return (self._page_w, self._page_h)

    def pdf_point_to_local(self, x_pdf: float, y_pdf: float) -> QPointF:
        """
        PDF座標(x_pdf,y_pdf)を、現在の zoom + rotation で表示中の画像ローカル座標へ変換。
        ※「回転後検索のジャンプ位置」を正しくするための中核API。
        """
        if not self._pixmap_unrot:
            return QPointF(0.0, 0.0)

        # PDF -> unrot画像座標
        p_unrot = self._pdf_point_to_image_point(
            x_pdf, y_pdf, self._pixmap_unrot.width(), self._pixmap_unrot.height()
        )

        # unrot画像 -> rot画像座標（RotationはCWを正）
        p_rot = map_point_unrot_to_rot(
            p_unrot.x(),
            p_unrot.y(),
            self._pixmap_unrot.width(),
            self._pixmap_unrot.height(),
            self._rotation.normalized(),
        )
        return p_rot
    

    def pixmap_offset_in_widget(self) -> QPointF:
        """
        QLabel の中で pixmap が実際に描かれている左上位置（PageWidget座標）を返す。
        検索ジャンプで「pixmap座標→Widget座標」へ補正するために使う。
        """
        pm = self._label.pixmap()
        if pm is None:
            return QPointF(0.0, 0.0)

        cr = self._label.contentsRect()
        align = self._label.alignment()

        dx = 0.0
        dy = 0.0

        # Horizontal
        if align & Qt.AlignmentFlag.AlignHCenter:
            dx = (cr.width() - pm.width()) * 0.5
        elif align & Qt.AlignmentFlag.AlignRight:
            dx = (cr.width() - pm.width()) * 1.0
        else:
            dx = 0.0  # Left

        # Vertical（今回は Top 想定だが、一応）
        if align & Qt.AlignmentFlag.AlignVCenter:
            dy = (cr.height() - pm.height()) * 0.5
        elif align & Qt.AlignmentFlag.AlignBottom:
            dy = (cr.height() - pm.height()) * 1.0
        else:
            dy = 0.0  # Top

        # offset は「labelの座標 + contentsRect内のoffset」
        return QPointF(self._label.x() + cr.x() + dx, self._label.y() + cr.y() + dy)



    def pdf_y_to_local_y(self, y_pdf: float) -> float:
        """
        互換用。PDF座標のyを、回転込みのローカルyへ。
        """
        x_pdf = self._page_w * 0.5
        p = self.pdf_point_to_local(x_pdf, y_pdf)
        return float(p.y())

    # ---- internal ----

    def _render(self) -> None:
        page = self._doc.get_page(self.page_index)

        w_pt, h_pt = page.get_size()
        self._page_w = float(w_pt)
        self._page_h = float(h_pt)

        scale = self._zoom * 2.0
        bitmap = page.render(scale=scale)
        pil = bitmap.to_pil()

        rgba = pil.convert("RGBA")
        data = rgba.tobytes("raw", "RGBA")
        qimg = QImage(data, rgba.width, rgba.height, QImage.Format.Format_RGBA8888)

        self._pixmap_unrot = QPixmap.fromImage(qimg)
        self._render_overlay()

    def _render_overlay(self) -> None:
        if not self._pixmap_unrot:
            return

        # 表示用の回転済みベース
        pm_base = self._rotated_pixmap(self._pixmap_unrot, self._rotation.normalized())

        pm = QPixmap(pm_base)
        painter = QPainter(pm)

        if self._active_match:
            painter.setOpacity(0.9)
            pen = painter.pen()
            pen.setWidth(6)
            pen.setColor(Qt.GlobalColor.blue)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(0, 0, pm.width() - 1, pm.height() - 1)

        # ハイライト
        painter.setOpacity(0.55)
        pen = QPen(QColor(180, 140, 40))
        pen.setWidth(2)
        painter.setPen(pen)
        painter.setBrush(QColor(255, 230, 120))

        for (l, t, r, b) in self._highlight_rects:
            rect_unrot = self._pdf_rect_to_image_rect_unrot(
                l, t, r, b, self._pixmap_unrot.width(), self._pixmap_unrot.height()
            )
            rect_rot = map_rect_unrot_to_rot(
                rect_unrot,
                self._pixmap_unrot.width(),
                self._pixmap_unrot.height(),
                self._rotation.normalized(),
            )
            painter.drawRoundedRect(rect_rot, 4.0, 4.0)

        painter.end()

        self._label.setPixmap(pm)
        # QLabel はレイアウトで伸ばし、pixmap は alignment に従って中で配置させる
        self._label.updateGeometry()



    def _rotated_pixmap(self, pm: QPixmap, rot_deg: int) -> QPixmap:
        r = rot_deg % 360
        if r == 0:
            return pm

        # 座標変換（検索ジャンプ/ハイライトと必ず同一）を使用する
        tr = qt_display_transform_for_pixmap(pm.width(), pm.height(), r)
        return pm.transformed(tr, Qt.TransformationMode.SmoothTransformation)

    def _pdf_point_to_image_point(self, x_pdf: float, y_pdf: float, img_w: int, img_h: int) -> QPointF:
        # PDFは下原点想定 → y反転
        x0 = x_pdf / self._page_w
        y0 = 1.0 - (y_pdf / self._page_h)
        return QPointF(x0 * img_w, y0 * img_h)

    def _pdf_rect_to_image_rect_unrot(self, l: float, t: float, r: float, b: float, img_w: int, img_h: int) -> QRectF:
        x0 = min(l, r) / self._page_w
        x1 = max(l, r) / self._page_w

        # PDF下原点想定
        y0 = 1.0 - (min(b, t) / self._page_h)
        y1 = 1.0 - (max(b, t) / self._page_h)

        px0 = x0 * img_w
        px1 = x1 * img_w
        py0 = y1 * img_h
        py1 = y0 * img_h

        return QRectF(px0, py0, max(1.0, px1 - px0), max(1.0, py1 - py0))
