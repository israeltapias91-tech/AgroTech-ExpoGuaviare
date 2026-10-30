"""Iconos vectoriales dibujados con QPainter (sin archivos externos)."""

from __future__ import annotations

from functools import lru_cache

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap, QPolygonF


def _preparar(lienzo: int, color: str) -> tuple[QPixmap, QPainter]:
    pixmap = QPixmap(lienzo * 2, lienzo * 2)
    pixmap.setDevicePixelRatio(2.0)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    # El lienzo físico es 2x (devicePixelRatio); el diseño base mide 24x24.
    # QPainter ya aplica el DPR, así que solo ajustamos 24 -> tamaño lógico.
    factor = lienzo / 24.0
    painter.scale(factor, factor)
    lapiz = QPen(QColor(color), 1.8)
    lapiz.setCapStyle(Qt.PenCapStyle.RoundCap)
    lapiz.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(lapiz)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    return pixmap, painter


def _dibujar(nombre: str, p: QPainter, color: str) -> None:
    if nombre == "hoja":
        hoja = QPainterPath(QPointF(5, 18))
        hoja.cubicTo(8, 10, 13, 4, 20, 4)
        hoja.cubicTo(19, 12, 14, 19, 5, 18)
        p.drawPath(hoja)
        p.drawLine(QPointF(5, 18), QPointF(10, 13))
    elif nombre == "termometro":
        p.drawRoundedRect(QRectF(9, 3, 6, 13), 3, 3)
        p.drawEllipse(QPointF(12, 19), 3.4, 3.4)
        p.drawLine(QPointF(12, 8), QPointF(12, 16))
    elif nombre == "gota":
        gota = QPainterPath(QPointF(12, 3))
        gota.cubicTo(7, 9, 5, 12, 5, 15)
        gota.cubicTo(5, 19, 8, 21, 12, 21)
        gota.cubicTo(16, 21, 19, 19, 19, 15)
        gota.cubicTo(19, 12, 17, 9, 12, 3)
        p.drawPath(gota)
    elif nombre == "presion":
        p.drawArc(QRectF(4, 4, 16, 16), 30 * 16, 300 * 16)
        p.drawLine(QPointF(12, 12), QPointF(17, 8))
        p.drawEllipse(QPointF(12, 12), 1.2, 1.2)
    elif nombre == "gas":
        p.drawEllipse(QPointF(9, 12), 4.2, 4.2)
        p.drawEllipse(QPointF(14, 10), 5.0, 5.0)
        p.drawEllipse(QPointF(17, 14), 3.2, 3.2)
        p.drawLine(QPointF(7, 17), QPointF(18, 17))
    elif nombre == "wifi":
        p.drawArc(QRectF(8, 14, 8, 8), 45 * 16, 90 * 16)
        p.drawArc(QRectF(4, 10, 16, 16), 45 * 16, 90 * 16)
        p.drawArc(QRectF(0, 6, 24, 24), 45 * 16, 90 * 16)
        p.setBrush(QColor(color))
        p.drawEllipse(QPointF(12, 18), 1.4, 1.4)
    elif nombre == "enlace":
        p.save()
        p.translate(12, 12)
        p.rotate(-35)
        p.drawRoundedRect(QRectF(-10, -4, 11, 8), 4, 4)
        p.drawRoundedRect(QRectF(-1, -4, 11, 8), 4, 4)
        p.restore()
    elif nombre == "robot":
        p.drawRoundedRect(QRectF(5, 8, 14, 8), 3, 3)
        p.drawLine(QPointF(12, 8), QPointF(12, 5))
        p.drawEllipse(QPointF(12, 3.6), 1.2, 1.2)
        p.drawEllipse(QPointF(8, 19), 2.2, 2.2)
        p.drawEllipse(QPointF(16, 19), 2.2, 2.2)
        p.setBrush(QColor(color))
        p.drawEllipse(QPointF(9, 12), 1.0, 1.0)
        p.drawEllipse(QPointF(15, 12), 1.0, 1.0)
    elif nombre == "actividad":
        for y in (6, 12, 18):
            p.drawEllipse(QPointF(5, y), 1.2, 1.2)
            p.drawLine(QPointF(8, y), QPointF(19, y))
    elif nombre == "config":
        p.drawEllipse(QPointF(12, 12), 4.0, 4.0)
        for grados in range(0, 360, 45):
            p.save()
            p.translate(12, 12)
            p.rotate(grados)
            p.drawLine(QPointF(0, -6.5), QPointF(0, -9.5))
            p.restore()
    elif nombre == "home":
        p.drawPolyline(QPolygonF([QPointF(3, 11), QPointF(12, 4), QPointF(21, 11)]))
        p.drawRoundedRect(QRectF(6, 11, 12, 9), 1, 1)
        p.drawRect(QRectF(10, 15, 4, 5))
    elif nombre == "sensores":
        p.drawRoundedRect(QRectF(4, 10, 4, 10), 1.5, 1.5)
        p.drawRoundedRect(QRectF(10, 5, 4, 15), 1.5, 1.5)
        p.drawRoundedRect(QRectF(16, 13, 4, 7), 1.5, 1.5)
    elif nombre == "datos":
        p.drawEllipse(QRectF(5, 4, 14, 5))
        p.drawLine(QPointF(5, 6.5), QPointF(5, 17.5))
        p.drawLine(QPointF(19, 6.5), QPointF(19, 17.5))
        p.drawArc(QRectF(5, 15, 14, 5), 180 * 16, 180 * 16)
        p.drawArc(QRectF(5, 10, 14, 5), 180 * 16, 180 * 16)
    elif nombre == "broker":
        for y in (4, 10, 16):
            p.drawRoundedRect(QRectF(4, y, 16, 4), 1.5, 1.5)
            p.setBrush(QColor(color))
            p.drawEllipse(QPointF(7.5, y + 2), 0.8, 0.8)
            p.setBrush(Qt.BrushStyle.NoBrush)
    elif nombre == "flecha":
        p.drawLine(QPointF(5, 12), QPointF(19, 12))
        p.drawPolyline(
            QPolygonF([QPointF(13, 7), QPointF(19, 12), QPointF(13, 17)])
        )
    elif nombre == "arriba":
        p.drawLine(QPointF(12, 19), QPointF(12, 5))
        p.drawPolyline(
            QPolygonF([QPointF(7, 11), QPointF(12, 5), QPointF(17, 11)])
        )
    elif nombre == "abajo":
        p.drawLine(QPointF(12, 5), QPointF(12, 19))
        p.drawPolyline(
            QPolygonF([QPointF(7, 13), QPointF(12, 19), QPointF(17, 13)])
        )
    elif nombre == "izquierda":
        p.drawLine(QPointF(19, 12), QPointF(5, 12))
        p.drawPolyline(
            QPolygonF([QPointF(11, 7), QPointF(5, 12), QPointF(11, 17)])
        )
    elif nombre == "derecha":
        p.drawLine(QPointF(5, 12), QPointF(19, 12))
        p.drawPolyline(
            QPolygonF([QPointF(13, 7), QPointF(19, 12), QPointF(13, 17)])
        )
    elif nombre == "stop":
        octagono = QPolygonF(
            [
                QPointF(8, 3), QPointF(16, 3), QPointF(21, 8),
                QPointF(21, 16), QPointF(16, 21), QPointF(8, 21),
                QPointF(3, 16), QPointF(3, 8),
            ]
        )
        p.drawPolygon(octagono)
        p.drawLine(QPointF(8, 12), QPointF(16, 12))
    elif nombre == "pelota":
        p.drawEllipse(QPointF(12, 12), 8, 8)
        p.drawArc(QRectF(7, 3, 10, 18), 90 * 16, 180 * 16)
        p.drawArc(QRectF(4, 8, 16, 8), 0, 180 * 16)
    elif nombre == "lock":
        p.drawArc(QRectF(8, 4, 8, 9), 0, 180 * 16)
        p.drawRoundedRect(QRectF(6, 10, 12, 9), 2, 2)
        p.setBrush(QColor(color))
        p.drawEllipse(QPointF(12, 14), 1.0, 1.0)
        p.drawLine(QPointF(12, 15), QPointF(12, 17))
    elif nombre == "info":
        p.drawEllipse(QPointF(12, 12), 8, 8)
        p.setBrush(QColor(color))
        p.drawEllipse(QPointF(12, 8), 1.1, 1.1)
        p.drawLine(QPointF(12, 11), QPointF(12, 16))
    elif nombre == "check":
        p.drawEllipse(QPointF(12, 12), 8, 8)
        p.drawPolyline(
            QPolygonF([QPointF(8, 12), QPointF(11, 15), QPointF(16, 9)])
        )
    elif nombre == "alerta":
        p.drawPolygon(
            QPolygonF([QPointF(12, 3), QPointF(21, 20), QPointF(3, 20)])
        )
        p.drawLine(QPointF(12, 9), QPointF(12, 14))
        p.setBrush(QColor(color))
        p.drawEllipse(QPointF(12, 17), 1.0, 1.0)
    elif nombre == "reloj":
        p.drawEllipse(QPointF(12, 12), 8, 8)
        p.drawLine(QPointF(12, 12), QPointF(12, 7))
        p.drawLine(QPointF(12, 12), QPointF(16, 13))
    elif nombre == "punto":
        p.setBrush(QColor(color))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPointF(12, 12), 5, 5)
    else:
        p.drawEllipse(QPointF(12, 12), 8, 8)


@lru_cache(maxsize=256)
def pixmap(nombre: str, color: str, tamano: int = 24) -> QPixmap:
    """Devuelve un QPixmap con el icono solicitado."""
    lienzo, painter = _preparar(tamano, color)
    try:
        _dibujar(nombre, painter, color)
    finally:
        painter.end()
    return lienzo


def icono(nombre: str, color: str, tamano: int = 24) -> QIcon:
    """Devuelve un QIcon reutilizable para botones y etiquetas."""
    return QIcon(pixmap(nombre, color, tamano))
