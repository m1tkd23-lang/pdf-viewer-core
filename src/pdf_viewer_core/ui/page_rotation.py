# src/pdf_viewer_core/ui/page_rotation.py
from __future__ import annotations

from dataclasses import dataclass
from PyQt6.QtCore import QPointF, QRectF


def _norm_rot(deg: int) -> int:
    d = deg % 360
    if d < 0:
        d += 360
    # 90度刻みに丸め（念のため）
    return (d // 90) * 90


@dataclass(frozen=True)
class Rotation:
    """
    90度刻みの回転状態を保持する。
    """
    deg: int = 0  # 0, 90, 180, 270

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


def map_point_unrot_to_rot(x: float, y: float, w: int, h: int, rot_deg: int) -> QPointF:
    """
    unrot画像(幅w, 高さh)上の点(x,y)を、rot_deg だけ回転した画像座標へ変換する。
    回転は「時計回り」を正（Qtのrotate(90)は反時計回りだが、QPixmap変換に合わせてここでは
    "見た目"に合わせてCWを採用。※後段の実装もCWで統一）
    """
    r = _norm_rot(rot_deg)

    if r == 0:
        return QPointF(x, y)

    if r == 90:
        # 90° CW: (x,y) -> (h - y, x)
        return QPointF(h - y, x)

    if r == 180:
        # 180°: (x,y) -> (w - x, h - y)
        return QPointF(w - x, h - y)

    if r == 270:
        # 270° CW (= 90° CCW): (x,y) -> (y, w - x)
        return QPointF(y, w - x)

    return QPointF(x, y)


def map_rect_unrot_to_rot(rect: QRectF, w: int, h: int, rot_deg: int) -> QRectF:
    """
    unrot画像上の矩形を、回転後画像座標へ（外接矩形として）変換する。
    """
    # 四隅を変換して外接矩形を取る
    p1 = map_point_unrot_to_rot(rect.left(), rect.top(), w, h, rot_deg)
    p2 = map_point_unrot_to_rot(rect.right(), rect.top(), w, h, rot_deg)
    p3 = map_point_unrot_to_rot(rect.right(), rect.bottom(), w, h, rot_deg)
    p4 = map_point_unrot_to_rot(rect.left(), rect.bottom(), w, h, rot_deg)

    xs = [p1.x(), p2.x(), p3.x(), p4.x()]
    ys = [p1.y(), p2.y(), p3.y(), p4.y()]

    x0, x1 = min(xs), max(xs)
    y0, y1 = min(ys), max(ys)

    return QRectF(x0, y0, max(1.0, x1 - x0), max(1.0, y1 - y0))
