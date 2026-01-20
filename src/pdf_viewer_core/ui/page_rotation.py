# src/pdf_viewer_core/ui/page_rotation.py
from __future__ import annotations

from dataclasses import dataclass
from PyQt6.QtCore import QPointF, QRectF
from PyQt6.QtGui import QTransform


def _norm_rot(deg: int) -> int:
    d = deg % 360
    if d < 0:
        d += 360
    return (d // 90) * 90


@dataclass(frozen=True)
class Rotation:
    deg: int = 0  # 0, 90, 180, 270 (CW)

    def cw(self) -> "Rotation":
        return Rotation(_norm_rot(self.deg + 90))

    def ccw(self) -> "Rotation":
        return Rotation(_norm_rot(self.deg - 90))

    def normalized(self) -> int:
        return _norm_rot(self.deg)


def rotated_size(w: int, h: int, rot_deg: int) -> tuple[int, int]:
    r = _norm_rot(rot_deg)
    if r in (90, 270):
        return (h, w)
    return (w, h)


def qt_display_transform_for_pixmap(w: int, h: int, rot_deg_cw: int) -> QTransform:
    """
    QPixmap.transformed() に渡す「表示と同一の」座標変換を返す。

    - rot_deg_cw は「見た目(CW)」を正とする
    - Qtの rotate は CCW 正なので、角度は符号反転して渡す（CW -> -deg）
    - 回転で負になる領域を +方向へ寄せる translate を入れる
    """
    r = _norm_rot(rot_deg_cw)
    if r == 0:
        return QTransform()

    qt_deg = -r  # CW を正にしたいので符号反転

    tr = QTransform()
    tr.rotate(qt_deg)

    # 回転後の外接矩形（負座標に食い込むのを補正）
    br = tr.mapRect(QRectF(0, 0, float(w), float(h)))
    tr2 = QTransform()
    tr2.translate(-br.left(), -br.top())

    return tr2 * tr



def map_point_unrot_to_rot(x: float, y: float, w: int, h: int, rot_deg: int) -> QPointF:
    tr = qt_display_transform_for_pixmap(w, h, rot_deg)
    return tr.map(QPointF(x, y))



def map_rect_unrot_to_rot(rect: QRectF, w: int, h: int, rot_deg: int) -> QRectF:
    tr = qt_display_transform_for_pixmap(w, h, rot_deg)
    out = tr.mapRect(rect)

    if out.width() < 1.0:
        out.setWidth(1.0)
    if out.height() < 1.0:
        out.setHeight(1.0)
    return out

