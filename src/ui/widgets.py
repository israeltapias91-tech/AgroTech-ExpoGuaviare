"""Componentes visuales reutilizables del rediseño AgroTech."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from src.app_state import EventoActividad
from src.ui.icons import pixmap
from src.ui.theme import COLORS, repolish


def _sombra(widget: QWidget) -> QGraphicsDropShadowEffect:
    efecto = QGraphicsDropShadowEffect(widget)
    efecto.setBlurRadius(22)
    efecto.setOffset(0, 6)
    efecto.setColor(QColor(22, 59, 43, 28))
    return efecto


def crear_icono(
    nombre: str,
    color: str,
    tamano: int = 36,
    fondo: str = "rgba(255, 255, 255, 185)",
    tamano_icono: int = 20,
) -> QLabel:
    """Crea una etiqueta con un icono vectorial y un fondo circular."""
    etiqueta = QLabel()
    etiqueta.setFixedSize(tamano, tamano)
    etiqueta.setAlignment(Qt.AlignmentFlag.AlignCenter)
    etiqueta.setPixmap(pixmap(nombre, color, tamano_icono))
    etiqueta.setStyleSheet(
        f"background-color: {fondo}; border-radius: {tamano // 2}px;"
    )
    etiqueta.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
    return etiqueta


def formatear_numero(valor: float | int | None) -> str:
    """Formatea una lectura sin inventar decimales ni valores ausentes."""
    if valor is None:
        return "Sin dato"
    if isinstance(valor, float):
        if valor.is_integer():
            return str(int(valor))
        return f"{valor:.1f}".rstrip("0").rstrip(".")
    return str(valor)


class StatusLine(QWidget):
    """Estado con icono y texto; el color nunca es el único indicador."""

    _ESTILOS = {
        "normal": ("check", COLORS["verde_estado"]),
        "conectado": ("check", COLORS["verde_estado"]),
        "alerta": ("alerta", COLORS["rojo"]),
        "desconectado": ("alerta", COLORS["rojo"]),
        "vencido": ("reloj", COLORS["ambar"]),
        "conectando": ("reloj", COLORS["ambar"]),
        "sin_datos": ("reloj", COLORS["texto_suave"]),
        "no_disponible": ("info", COLORS["texto_suave"]),
        "activo": ("punto", COLORS["verde_estado"]),
    }

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        fila = QHBoxLayout(self)
        fila.setContentsMargins(0, 0, 0, 0)
        fila.setSpacing(5)
        self.icono = QLabel()
        self.icono.setFixedSize(14, 14)
        self.icono.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.texto = QLabel()
        self.texto.setObjectName("estadoTarjeta")
        self.texto.setStyleSheet("font-size: 11px; font-weight: 700;")
        fila.addWidget(self.icono)
        fila.addWidget(self.texto)
        fila.addStretch(1)
        self.set_estado("sin_datos", "Sin dato")

    def set_estado(self, estado: str, texto: str) -> None:
        nombre_icono, color = self._ESTILOS.get(
            estado, ("info", COLORS["texto_suave"])
        )
        self.icono.setPixmap(pixmap(nombre_icono, color, 14))
        self.texto.setText(texto)
        self.texto.setProperty("estado", estado)
        repolish(self.texto)


class RangeBar(QWidget):
    """Barra de rango real con marca de umbral; no es un historial."""

    def __init__(
        self,
        minimo: float,
        maximo: float,
        umbral: float | None,
        color: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.minimo = minimo
        self.maximo = maximo
        self.umbral = umbral
        self.color = color
        self._valor: float | None = None
        self._vencido = False
        self.setMinimumHeight(10)
        self.setMaximumHeight(10)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_dato(self, valor: float | None, vencido: bool = False) -> None:
        self._valor = valor
        self._vencido = vencido
        self.update()

    def set_vencido(self, vencido: bool = True) -> None:
        """Atenúa la marca sin borrar el último valor real."""
        self._vencido = vencido
        self.update()

    def _x(self, valor: float, ancho: float) -> float:
        if self.maximo <= self.minimo:
            return 0.0
        proporcion = (valor - self.minimo) / (self.maximo - self.minimo)
        return max(0.0, min(1.0, proporcion)) * ancho

    def paintEvent(self, evento) -> None:  # noqa: N802 (API de Qt)
        ancho = float(self.width())
        if ancho <= 2:
            return
        pintor = QPainter(self)
        pintor.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        y = self.height() / 2.0 - 3.0

        pintor.setPen(Qt.PenStyle.NoPen)
        pintor.setBrush(QColor(255, 255, 255, 170))
        pintor.drawRoundedRect(QRectF(0, y, ancho, 6), 3, 3)

        if self.umbral is not None:
            x_umbral = self._x(float(self.umbral), ancho)
            lapiz = QPen(QColor(COLORS["texto_suave"]), 1)
            lapiz.setStyle(Qt.PenStyle.DashLine)
            pintor.setPen(lapiz)
            pintor.drawLine(
                QPointF(x_umbral, y - 2), QPointF(x_umbral, y + 8)
            )

        if self._valor is not None:
            x_valor = self._x(float(self._valor), ancho)
            color = QColor(self.color)
            if self._vencido:
                color.setAlpha(105)
            pintor.setPen(Qt.PenStyle.NoPen)
            relleno = QColor(color)
            relleno.setAlpha(70)
            pintor.setBrush(relleno)
            pintor.drawRoundedRect(QRectF(0, y, x_valor, 6), 3, 3)
            pintor.setBrush(color)
            pintor.drawEllipse(QPointF(x_valor, y + 3), 4, 4)
        pintor.end()


class Card(QFrame):
    """Tarjeta base con borde redondeado y sombra discreta."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("tarjeta", True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setGraphicsEffect(_sombra(self))


class SensorCard(Card):
    """Tarjeta de una variable ambiental."""

    def __init__(
        self,
        clave: str,
        titulo: str,
        unidad: str,
        icono_nombre: str,
        color_icono: str,
        color_barra: str,
        rango: tuple[float, float],
        umbral: float,
        texto_umbral: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.clave = clave
        self.unidad_texto = unidad
        self.texto_umbral = texto_umbral
        self._tiene_dato = False
        self._hubo_lectura = False
        self._ultima_hora = ""
        self.setProperty("categoria", clave)

        caja = QVBoxLayout(self)
        caja.setContentsMargins(16, 14, 16, 14)
        caja.setSpacing(7)

        cabecera = QHBoxLayout()
        cabecera.setSpacing(9)
        cabecera.addWidget(crear_icono(icono_nombre, color_icono))
        etiqueta_titulo = QLabel(titulo)
        etiqueta_titulo.setObjectName("tituloTarjeta")
        cabecera.addWidget(etiqueta_titulo)
        cabecera.addStretch(1)
        caja.addLayout(cabecera)

        fila_valor = QHBoxLayout()
        fila_valor.setSpacing(6)
        self.valor = QLabel("Sin dato")
        self.valor.setObjectName("valorSensor")
        self.unidad = QLabel(unidad)
        self.unidad.setObjectName("unidadSensor")
        self.unidad.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom
        )
        fila_valor.addWidget(self.valor)
        fila_valor.addWidget(self.unidad)
        fila_valor.addStretch(1)
        caja.addLayout(fila_valor)

        self.estado = StatusLine()
        caja.addWidget(self.estado)

        self.barra = RangeBar(rango[0], rango[1], umbral, color_barra)
        caja.addWidget(self.barra)

        self.detalle = QLabel(texto_umbral)
        self.detalle.setObjectName("detalleTarjeta")
        self.detalle.setWordWrap(True)
        caja.addWidget(self.detalle)

        self.hora = QLabel("Sin actualización")
        self.hora.setObjectName("detalleTarjeta")
        caja.addWidget(self.hora)

    def actualizar(
        self,
        valor: float | None,
        estado: str,
        texto_estado: str,
        hora_texto: str,
        detalle: str = "",
    ) -> None:
        self._hubo_lectura = True
        self._ultima_hora = hora_texto
        self._tiene_dato = valor is not None
        if valor is None:
            self.valor.setText("Sin dato")
            self.valor.setStyleSheet(f"color: {COLORS['texto_suave']};")
            self.barra.set_dato(None)
        else:
            self.valor.setText(formatear_numero(valor))
            self.valor.setStyleSheet("")
            self.barra.set_dato(float(valor))
        self.estado.set_estado(estado, texto_estado)
        self.detalle.setText(detalle or self.texto_umbral)
        self.hora.setText(
            f"Actualizado {hora_texto}" if hora_texto else "Sin actualización"
        )

    def marcar_vencido(self) -> None:
        if not self._hubo_lectura:
            return
        self.estado.set_estado("vencido", "Sin datos recientes")
        self.detalle.setText("No se recibieron datos nuevos en el tiempo esperado.")
        self.hora.setText(
            f"Última: {self._ultima_hora}" if self._ultima_hora else "—"
        )
        if self._tiene_dato:
            self.barra.set_vencido(True)


class ConnectionCard(Card):
    """Tarjeta de estado de un enlace, sin mezclar hardware y broker."""

    _TEXTOS = {
        "conectado": "Conectado",
        "desconectado": "Desconectado",
        "sin_datos": "Sin datos",
        "conectando": "Conectando",
    }
    _DETALLES = {
        "conectado": "Enlace activo",
        "desconectado": "Sin comunicación",
        "sin_datos": "Aún no se ha recibido información",
        "conectando": "Estableciendo enlace MQTT",
    }

    def __init__(
        self,
        titulo: str,
        icono_nombre: str,
        color_icono: str,
        estado_inicial: str = "sin_datos",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        caja = QVBoxLayout(self)
        caja.setContentsMargins(15, 13, 15, 13)
        caja.setSpacing(6)

        cabecera = QHBoxLayout()
        cabecera.setSpacing(9)
        cabecera.addWidget(crear_icono(icono_nombre, color_icono, 34, tamano_icono=18))
        etiqueta = QLabel(titulo)
        etiqueta.setObjectName("tituloConexion")
        cabecera.addWidget(etiqueta)
        cabecera.addStretch(1)
        caja.addLayout(cabecera)

        self.estado = StatusLine()
        caja.addWidget(self.estado)
        self.detalle = QLabel()
        self.detalle.setObjectName("detalleConexion")
        self.detalle.setWordWrap(True)
        caja.addWidget(self.detalle)
        self.hora = QLabel()
        self.hora.setObjectName("detalleConexion")
        caja.addWidget(self.hora)
        self.set_estado(estado_inicial)

    def set_estado(
        self, estado: str, hora_texto: str | None = None, detalle: str = ""
    ) -> None:
        self.estado.set_estado(estado, self._TEXTOS.get(estado, estado))
        self.detalle.setText(detalle or self._DETALLES.get(estado, ""))
        if hora_texto and estado == "conectado":
            self.hora.setText(f"Actualizado {hora_texto}")
        elif hora_texto and estado == "desconectado":
            self.hora.setText(f"Última actividad {hora_texto}")
        elif estado == "sin_datos":
            self.hora.setText("Sin actualización")
        else:
            self.hora.setText("—")


class ActivityRow(QFrame):
    """Fila de un evento real de la actividad reciente."""

    _ESTILOS = {
        "broker": ("broker", "#8FCB3B"),
        "gateway": ("wifi", "#9BD9B0"),
        "txt": ("enlace", "#8FCB3B"),
        "lectura": ("termometro", "#F2C08B"),
        "boton": ("flecha", "#B7E36A"),
        "pelota": ("pelota", "#B7E36A"),
        "error": ("alerta", "#F08A7E"),
    }

    def __init__(self, evento: EventoActividad, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("filaActividad")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        fila = QHBoxLayout(self)
        fila.setContentsMargins(9, 7, 9, 7)
        fila.setSpacing(9)

        nombre_icono, color = self._ESTILOS.get(
            evento.tipo, ("actividad", COLORS["texto_claro_suave"])
        )
        fila.addWidget(
            crear_icono(nombre_icono, color, 28, "#255642", tamano_icono=15)
        )

        textos = QVBoxLayout()
        textos.setSpacing(1)
        titulo = QLabel(evento.titulo)
        titulo.setObjectName("actividadTitulo")
        titulo.setWordWrap(True)
        textos.addWidget(titulo)
        if evento.detalle:
            detalle = QLabel(evento.detalle)
            detalle.setObjectName("actividadDetalle")
            detalle.setWordWrap(True)
            textos.addWidget(detalle)
        fila.addLayout(textos, 1)

        hora = QLabel(evento.hora.strftime("%H:%M:%S"))
        hora.setObjectName("actividadHora")
        hora.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight
        )
        fila.addWidget(hora)


class LiveBadge(QFrame):
    """Distintivo global derivado del estado real de la aplicación."""

    _COLORES = {
        "en_vivo": COLORS["verde_estado"],
        "sin_datos": COLORS["ambar"],
        "sin_conexion": COLORS["rojo"],
    }

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("badgeVivo")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        fila = QHBoxLayout(self)
        fila.setContentsMargins(10, 4, 10, 4)
        fila.setSpacing(6)
        self.icono = QLabel()
        self.icono.setFixedSize(12, 12)
        self.icono.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.texto = QLabel()
        self.texto.setObjectName("badgeTexto")
        fila.addWidget(self.icono)
        fila.addWidget(self.texto)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.set_estado("sin_conexion", "SIN CONEXIÓN")

    def set_estado(self, estado: str, texto: str) -> None:
        color = self._COLORES.get(estado, COLORS["texto_suave"])
        self.icono.setPixmap(pixmap("punto", color, 12))
        self.texto.setText(texto)
        self.setProperty("estado", estado)
        self.texto.setProperty("estado", estado)
        repolish(self)
        repolish(self.texto)
