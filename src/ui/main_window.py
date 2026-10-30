"""Ventana principal de ExpoGuaviare AgroTech.

Rediseño visual de solo lectura: muestra datos reales, estados de
conexión y actividad recibida. Los controles del robot y del lanzador
son únicamente visuales y permanecen deshabilitados: esta aplicación
no publica órdenes MQTT.
"""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QSize, QTimer, Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from src.app_config import AppConfig
from src.app_state import (
    ESTADO_CONECTADO,
    ESTADO_DESCONECTADO,
    MAX_EVENTOS_ACTIVIDAD,
    UMBRAL_BOTON_NEUTRAL_SEG,
    UMBRAL_GATEWAY_ACTIVO_SEG,
    UMBRAL_SIN_DATOS_RECIENTES_SEG,
    EventoActividad,
    Lectura,
)
from src.messages import RANGO_GAS, RANGO_HUM, RANGO_PRESION, RANGO_TEMP
from src.ui.icons import icono
from src.ui.theme import COLORS, repolish, stylesheet
from src.ui.widgets import (
    ActivityRow,
    Card,
    ConnectionCard,
    LiveBadge,
    SensorCard,
    crear_icono,
    formatear_numero,
)


class MainWindow(QMainWindow):
    """Ventana principal de ExpoGuaviare AgroTech."""

    _ETIQUETAS_ESTADO = {
        "conectado": "Conectado",
        "desconectado": "Desconectado",
        "sin_datos": "Sin datos",
        "conectando": "Conectando",
    }

    def __init__(self, config: AppConfig | None = None) -> None:
        super().__init__()
        self.config = config or AppConfig()
        self.setWindowTitle("ExpoGuaviare AgroTech · Monitoreo en vivo")
        self.setMinimumSize(760, 560)
        self.resize(1280, 860)

        self._broker_principal_conectado = False
        self._broker_txt_conectado = False
        self._hay_lectura = False
        self._datos_recientes = False
        self._ultima_hora_lectura = ""
        self._hora_broker_principal: str | None = None
        self._hora_broker_txt: str | None = None
        self._nav_en_superior = True
        self._modos_layout: dict[str, int] = {}
        self._filas_actividad: list[ActivityRow] = []
        self._alertas_umbral_activas: set[str] = set()
        self._timer_velocidad: QTimer | None = None
        self._valor_velocidad_pendiente: int | None = None
        self._velocidad_aplicada: int | None = None
        self._timer_velocidad_confirmacion: QTimer | None = None
        self._VALOR_VELOCIDAD_TIMEOUT_SEG = 5.0
        self._timer_camara_timeout: QTimer | None = None
        self._txt_para_velocidad = False

        self.setStyleSheet(stylesheet())
        self._construir()
        self._reacomodar(force=True)
        self._marcar_nav("inicio")

    # -- Construcción de la interfaz --

    def _construir(self) -> None:
        raiz = QWidget()
        raiz.setObjectName("raiz")
        self.setCentralWidget(raiz)
        layout_raiz = QVBoxLayout(raiz)
        layout_raiz.setContentsMargins(0, 0, 0, 0)
        layout_raiz.setSpacing(0)

        self._construir_cabecera(layout_raiz)

        self.scroll = QScrollArea()
        self.scroll.setObjectName("scroll")
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.contenido = QWidget()
        self.contenido.setObjectName("contenido")
        self.layout_contenido = QVBoxLayout(self.contenido)
        self.layout_contenido.setContentsMargins(24, 22, 24, 24)
        self.layout_contenido.setSpacing(22)
        self.scroll.setWidget(self.contenido)
        self.scroll.viewport().setObjectName("viewportScroll")
        self.scroll.viewport().setAutoFillBackground(False)
        self.scroll.viewport().setStyleSheet(
            "QWidget#viewportScroll { background: transparent; }"
        )
        layout_raiz.addWidget(self.scroll, 1)

        self._construir_ambiente()
        self._construir_robot()
        self._construir_configuracion()

        pie = QLabel(
            "Datos en vivo sin persistencia · Actividad acotada a 30 eventos · "
            "La aplicación no publica órdenes MQTT."
        )
        pie.setObjectName("pie")
        pie.setWordWrap(True)
        pie.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout_contenido.addWidget(pie)

    def _construir_cabecera(self, layout_raiz: QVBoxLayout) -> None:
        self.cabecera = QFrame()
        self.cabecera.setObjectName("cabecera")
        self.cabecera_grid = QGridLayout(self.cabecera)
        self.cabecera_grid.setContentsMargins(24, 14, 24, 10)
        self.cabecera_grid.setHorizontalSpacing(18)
        self.cabecera_grid.setVerticalSpacing(4)
        self.cabecera_grid.setColumnStretch(0, 1)
        self.cabecera_grid.setColumnStretch(1, 0)
        self.cabecera_grid.setColumnStretch(2, 0)

        marca = QWidget()
        fila_marca = QHBoxLayout(marca)
        fila_marca.setContentsMargins(0, 0, 0, 0)
        fila_marca.setSpacing(12)
        fila_marca.addWidget(
            crear_icono("hoja", COLORS["verde_bosque"], 46, COLORS["lima"], 26)
        )
        textos_marca = QVBoxLayout()
        textos_marca.setSpacing(0)
        titulo = QLabel("AgroTech")
        titulo.setObjectName("marca")
        subtitulo = QLabel("ExpoGuaviare · Monitoreo ambiental en vivo")
        subtitulo.setObjectName("subtituloMarca")
        textos_marca.addWidget(titulo)
        textos_marca.addWidget(subtitulo)
        fila_marca.addLayout(textos_marca)
        fila_marca.addStretch(1)
        self.cabecera_grid.addWidget(marca, 0, 0)

        self.badge_vivo = LiveBadge()
        self.cabecera_grid.addWidget(
            self.badge_vivo, 0, 2, alignment=Qt.AlignmentFlag.AlignRight
        )

        self.nav_widget = QWidget()
        fila_nav = QHBoxLayout(self.nav_widget)
        fila_nav.setContentsMargins(0, 0, 0, 0)
        fila_nav.setSpacing(2)
        self.botones_nav: dict[str, QPushButton] = {}
        opciones = [
            ("inicio", "Inicio", "home"),
            ("sensores", "Sensores", "sensores"),
            ("robot", "Robot", "robot"),
            ("datos", "Datos", "datos"),
            ("configuracion", "Configuración", "config"),
        ]
        for clave, etiqueta, icono_nombre in opciones:
            boton = QPushButton(etiqueta)
            boton.setObjectName("nav")
            boton.setCheckable(True)
            boton.setAutoExclusive(True)
            boton.setCursor(Qt.CursorShape.PointingHandCursor)
            boton.setIcon(icono(icono_nombre, "#D7E3DA", 16))
            boton.setIconSize(QSize(16, 16))
            boton.setAccessibleName(f"Ir a {etiqueta}")
            boton.clicked.connect(
                lambda _marcado=False, destino=clave: self._ir_a(destino)
            )
            fila_nav.addWidget(boton)
            self.botones_nav[clave] = boton
        self.cabecera_grid.addWidget(
            self.nav_widget, 0, 1, alignment=Qt.AlignmentFlag.AlignRight
        )
        layout_raiz.addWidget(self.cabecera)

    def _construir_ambiente(self) -> None:
        self.seccion_sensores = QWidget()
        seccion = QVBoxLayout(self.seccion_sensores)
        seccion.setContentsMargins(0, 0, 0, 0)
        seccion.setSpacing(13)

        cabecera, fila = self._encabezado_seccion(
            "Ambiente",
            "Condiciones en tiempo real del entorno · ExpoGuaviare",
            "sensores",
            COLORS["verde_bosque"],
            COLORS["verde_suave"],
        )
        self.lbl_actualizacion = QLabel("Última actualización: —")
        self.lbl_actualizacion.setObjectName("subtituloSeccion")
        fila.addWidget(self.lbl_actualizacion)
        seccion.addWidget(cabecera)

        self.grid_conexiones = QGridLayout()
        self.grid_conexiones.setHorizontalSpacing(12)
        self.grid_conexiones.setVerticalSpacing(12)
        self.card_gateway = ConnectionCard(
            "Gateway", "wifi", COLORS["verde_bosque"], "sin_datos"
        )
        self.card_txt = ConnectionCard(
            "TXT", "enlace", COLORS["azul"], "sin_datos"
        )
        self.card_broker = ConnectionCard(
            "Broker PC", "broker", COLORS["ambar"], "conectando"
        )
        self._cards_conexiones = [
            self.card_gateway,
            self.card_txt,
            self.card_broker,
        ]
        seccion.addLayout(self.grid_conexiones)

        self.grid_sensores = QGridLayout()
        self.grid_sensores.setHorizontalSpacing(14)
        self.grid_sensores.setVerticalSpacing(14)
        self.tarjetas_cards: dict[str, SensorCard] = {}
        self.tarjetas: dict[str, QLabel] = {}
        self.etiquetas_estado: dict[str, QLabel] = {}
        definiciones = [
            (
                "temperatura",
                "Temperatura",
                "°C",
                "termometro",
                COLORS["naranja"],
                RANGO_TEMP,
                self.config.umbral_temp_alta,
                f"Alerta si > {formatear_numero(self.config.umbral_temp_alta)} °C",
            ),
            (
                "humedad",
                "Humedad",
                "%",
                "gota",
                COLORS["azul"],
                RANGO_HUM,
                self.config.umbral_hum_baja,
                f"Alerta si < {formatear_numero(self.config.umbral_hum_baja)} %",
            ),
            (
                "presion",
                "Presión",
                "hPa",
                "presion",
                COLORS["violeta"],
                RANGO_PRESION,
                self.config.umbral_presion_baja,
                f"Alerta si < {formatear_numero(self.config.umbral_presion_baja)} hPa",
            ),
            (
                "gas",
                "Gas",
                "kΩ",
                "gas",
                COLORS["oliva"],
                RANGO_GAS,
                self.config.umbral_gas_alto,
                f"Alerta si > {formatear_numero(self.config.umbral_gas_alto)} kΩ",
            ),
        ]
        for (
            clave,
            titulo,
            unidad,
            icono_nombre,
            color,
            rango,
            umbral,
            texto_umbral,
        ) in definiciones:
            tarjeta = SensorCard(
                clave,
                titulo,
                unidad,
                icono_nombre,
                color,
                color,
                rango,
                umbral,
                texto_umbral,
            )
            self.tarjetas_cards[clave] = tarjeta
            self.tarjetas[clave] = tarjeta.valor
            self.etiquetas_estado[clave] = tarjeta.estado.texto
        self._cards_sensores = list(self.tarjetas_cards.values())
        seccion.addLayout(self.grid_sensores)
        self.layout_contenido.addWidget(self.seccion_sensores)

    def _construir_robot(self) -> None:
        self.seccion_robot = QWidget()
        seccion = QVBoxLayout(self.seccion_robot)
        seccion.setContentsMargins(0, 0, 0, 0)
        seccion.setSpacing(13)

        banner = QFrame()
        banner.setObjectName("bannerRobot")
        banner.setFrameShape(QFrame.Shape.NoFrame)
        banner.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        fila_banner = QHBoxLayout(banner)
        fila_banner.setContentsMargins(20, 17, 20, 17)
        fila_banner.setSpacing(13)
        fila_banner.addWidget(
            crear_icono("robot", COLORS["verde_bosque"], 52, COLORS["lima"], 28)
        )
        textos = QVBoxLayout()
        textos.setSpacing(1)
        titulo = QLabel("Robot TXT 4.0")
        titulo.setObjectName("textoBanner")
        subtitulo = QLabel("Control y funciones del robot agrícola")
        subtitulo.setObjectName("subtextoBanner")
        textos.addWidget(titulo)
        textos.addWidget(subtitulo)
        fila_banner.addLayout(textos)
        fila_banner.addStretch(1)
        etiqueta = QLabel("SOLO LECTURA")
        etiqueta.setObjectName("etiquetaBanner")
        fila_banner.addWidget(etiqueta)
        seccion.addWidget(banner)

        self.grid_robot = QGridLayout()
        self.grid_robot.setHorizontalSpacing(14)
        self.grid_robot.setVerticalSpacing(14)
        self.panel_control = self._crear_panel_control()
        self.panel_lanzador = self._crear_panel_lanzador()
        self.panel_velocidad = self._crear_panel_velocidad()
        self.panel_camara = self._crear_panel_camara()

        self.columna_derecha_robot = QWidget()
        columna = QVBoxLayout(self.columna_derecha_robot)
        columna.setContentsMargins(0, 0, 0, 0)
        columna.setSpacing(14)
        columna.addWidget(self.panel_lanzador)
        columna.addWidget(self.panel_velocidad)
        columna.addWidget(self.panel_camara)
        columna.addStretch(1)

        self.seccion_datos = self._crear_panel_datos()
        seccion.addLayout(self.grid_robot)
        self.layout_contenido.addWidget(self.seccion_robot)

    def _crear_panel_control(self) -> Card:
        panel = Card()
        caja = QVBoxLayout(panel)
        caja.setContentsMargins(16, 15, 16, 15)
        caja.setSpacing(9)

        titulo = QLabel("Control de movimiento")
        titulo.setObjectName("tituloPanel")
        subtitulo = QLabel("Vista de los controles · órdenes deshabilitadas")
        subtitulo.setObjectName("subtituloPanel")
        caja.addWidget(titulo)
        caja.addWidget(subtitulo)

        bloqueo = QLabel(
            "Control deshabilitado: falta configurar permisos MQTT para "
            "órdenes seguras."
        )
        bloqueo.setObjectName("notaBloqueada")
        bloqueo.setWordWrap(True)
        caja.addWidget(bloqueo)

        pad = QGridLayout()
        pad.setHorizontalSpacing(8)
        pad.setVerticalSpacing(8)
        pad.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.btn_adelante = self._boton_direccion("arriba", "Adelante")
        self.btn_izquierda = self._boton_direccion("izquierda", "Izquierda")
        self.btn_derecha = self._boton_direccion("derecha", "Derecha")
        self.btn_atras = self._boton_direccion("abajo", "Atrás")
        self.btn_detener = QPushButton()
        self.btn_detener.setObjectName("detener")
        self.btn_detener.setFixedSize(72, 72)
        self.btn_detener.setIcon(icono("stop", "#FFFFFF", 28))
        self.btn_detener.setIconSize(QSize(28, 28))
        self.btn_detener.setEnabled(False)
        self.btn_detener.setAccessibleName("Detener")
        self.btn_detener.setToolTip("Detener · control deshabilitado")
        pad.addWidget(self.btn_adelante, 0, 1)
        pad.addWidget(self.btn_izquierda, 1, 0)
        pad.addWidget(self.btn_detener, 1, 1)
        pad.addWidget(self.btn_derecha, 1, 2)
        pad.addWidget(self.btn_atras, 2, 1)
        caja.addLayout(pad)

        self.lbl_direccion = QLabel("Dirección: Neutral")
        self.lbl_direccion.setObjectName("ultimoEvento")
        self.lbl_direccion.setAlignment(Qt.AlignmentFlag.AlignCenter)
        caja.addWidget(self.lbl_direccion)

        nota = QLabel(
            "Los controles solo reflejan eventos recibidos del gateway; "
            "esta aplicación no envía órdenes."
        )
        nota.setObjectName("notaInfo")
        nota.setWordWrap(True)
        caja.addWidget(nota)
        caja.addStretch(1)
        return panel

    def _crear_panel_lanzador(self) -> Card:
        panel = Card()
        panel.setObjectName("tarjetaLanzador")
        caja = QVBoxLayout(panel)
        caja.setContentsMargins(16, 15, 16, 15)
        caja.setSpacing(8)

        titulo = QLabel("Lanzador de pelota")
        titulo.setObjectName("tituloPanel")
        subtitulo = QLabel("Función del pulsador PELOTA")
        subtitulo.setObjectName("subtituloPanel")
        caja.addWidget(titulo)
        caja.addWidget(subtitulo)

        self.btn_orden = QPushButton("Lanzar pelota")
        self.btn_orden.setObjectName("lanzar")
        self.btn_orden.setIcon(icono("pelota", COLORS["verde_bosque"], 18))
        self.btn_orden.setIconSize(QSize(18, 18))
        self.btn_orden.setEnabled(False)
        self.btn_orden.setAccessibleName("Lanzar pelota")
        self.btn_orden.setToolTip("Lanzar pelota · control deshabilitado")
        self.btn_orden.clicked.connect(self._lanzar_pelota)
        caja.addWidget(self.btn_orden)

        self.lbl_pelota = QLabel("Sin eventos PELOTA")
        self.lbl_pelota.setObjectName("ultimoEvento")
        self.lbl_pelota.setWordWrap(True)
        caja.addWidget(self.lbl_pelota)

        self.nota_lanzador = QLabel(
            "Esperando conexión del TXT para habilitar el lanzador de pelota."
        )
        self.nota_lanzador.setObjectName("notaInfo")
        self.nota_lanzador.setWordWrap(True)
        caja.addWidget(self.nota_lanzador)
        return panel

    def _crear_panel_velocidad(self) -> Card:
        panel = Card()
        caja = QVBoxLayout(panel)
        caja.setContentsMargins(16, 15, 16, 15)
        caja.setSpacing(7)

        titulo = QLabel("Velocidad del TXT")
        titulo.setObjectName("tituloPanel")
        subtitulo = QLabel("Valor PWM 0..512 · se publica al soltar el deslizador")
        subtitulo.setObjectName("subtituloPanel")
        caja.addWidget(titulo)
        caja.addWidget(subtitulo)

        fila = QHBoxLayout()
        fila.setSpacing(5)
        self.lbl_velocidad = QLabel("0")
        self.lbl_velocidad.setObjectName("velocidadValor")
        unidad = QLabel("/ 512")
        unidad.setObjectName("velocidadUnidad")
        unidad.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom
        )
        fila.addWidget(self.lbl_velocidad)
        fila.addWidget(unidad)
        fila.addStretch(1)
        caja.addLayout(fila)

        self.slider_velocidad = QSlider(Qt.Orientation.Horizontal)
        self.slider_velocidad.setRange(0, 512)
        self.slider_velocidad.setValue(0)
        self.slider_velocidad.setEnabled(False)
        self.slider_velocidad.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.slider_velocidad.setTickInterval(256)
        self.slider_velocidad.setAccessibleName("Velocidad del TXT, 0 de 512")
        self.slider_velocidad.valueChanged.connect(
            self._on_slider_velocidad_cambiado
        )
        self.slider_velocidad.sliderReleased.connect(
            self._publicar_velocidad_pendiente
        )
        caja.addWidget(self.slider_velocidad)

        extremos = QHBoxLayout()
        minimo = QLabel("0")
        minimo.setObjectName("subtituloPanel")
        maximo = QLabel("512")
        maximo.setObjectName("subtituloPanel")
        extremos.addWidget(minimo)
        extremos.addStretch(1)
        extremos.addWidget(maximo)
        caja.addLayout(extremos)

        self.lbl_velocidad_estado = QLabel("TXT desconectado · velocidad sin aplicar")
        self.lbl_velocidad_estado.setObjectName("ultimoEvento")
        self.lbl_velocidad_estado.setWordWrap(True)
        caja.addWidget(self.lbl_velocidad_estado)

        self.nota_velocidad = QLabel(
            "Esperando conexión del TXT para habilitar el control de velocidad."
        )
        self.nota_velocidad.setObjectName("notaInfo")
        self.nota_velocidad.setWordWrap(True)
        caja.addWidget(self.nota_velocidad)
        return panel

    def _crear_panel_camara(self) -> Card:
        panel = Card()
        panel.setObjectName("tarjetaCamara")
        caja = QVBoxLayout(panel)
        caja.setContentsMargins(16, 15, 16, 15)
        caja.setSpacing(7)

        titulo = QLabel("Cámara del TXT")
        titulo.setObjectName("tituloPanel")
        subtitulo = QLabel("Vista previa de la cámara USB del TXT 4.0")
        subtitulo.setObjectName("subtituloPanel")
        caja.addWidget(titulo)
        caja.addWidget(subtitulo)

        self.lbl_camara = QLabel("Esperando cámara...")
        self.lbl_camara.setObjectName("camaraVistaPrevia")
        self.lbl_camara.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_camara.setMinimumSize(320, 240)
        self.lbl_camara.setScaledContents(True)
        self.lbl_camara.setStyleSheet(
            "background-color: #2A2A2A; color: #888888; border: 1px solid #555555;"
        )
        caja.addWidget(self.lbl_camara)

        self.lbl_camara_estado = QLabel("Cámara sin señal")
        self.lbl_camara_estado.setObjectName("ultimoEvento")
        self.lbl_camara_estado.setWordWrap(True)
        caja.addWidget(self.lbl_camara_estado)

        self.nota_camara = QLabel(
            "Esperando conexión del TXT para iniciar la transmisión de imagen."
        )
        self.nota_camara.setObjectName("notaInfo")
        self.nota_camara.setWordWrap(True)
        caja.addWidget(self.nota_camara)
        return panel

    def _crear_panel_datos(self) -> Card:
        panel = Card()
        panel.setObjectName("tarjetaDatos")
        caja = QVBoxLayout(panel)
        caja.setContentsMargins(16, 15, 16, 15)
        caja.setSpacing(10)

        cabecera = QHBoxLayout()
        cabecera.setSpacing(9)
        cabecera.addWidget(
            crear_icono(
                "actividad",
                COLORS["lima"],
                34,
                "#255642",
                tamano_icono=18,
            )
        )
        textos = QVBoxLayout()
        textos.setSpacing(0)
        titulo = QLabel("Datos / Actividad reciente")
        titulo.setObjectName("tituloDatos")
        subtitulo = QLabel("Eventos reales · máximo 30 en memoria")
        subtitulo.setObjectName("subtituloDatos")
        textos.addWidget(titulo)
        textos.addWidget(subtitulo)
        cabecera.addLayout(textos)
        cabecera.addStretch(1)
        caja.addLayout(cabecera)

        self.scroll_actividad = QScrollArea()
        self.scroll_actividad.setObjectName("scroll")
        self.scroll_actividad.setWidgetResizable(True)
        self.scroll_actividad.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_actividad.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.scroll_actividad.setMinimumHeight(210)
        self.scroll_actividad.setMaximumHeight(360)
        self.lista_actividad_widget = QWidget()
        self.layout_actividad = QVBoxLayout(self.lista_actividad_widget)
        self.layout_actividad.setContentsMargins(0, 0, 0, 0)
        self.layout_actividad.setSpacing(6)
        self.lbl_sin_actividad = QLabel("Sin actividad reciente")
        self.lbl_sin_actividad.setObjectName("sinActividad")
        self.lbl_sin_actividad.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_sin_actividad.setWordWrap(True)
        self.layout_actividad.addWidget(self.lbl_sin_actividad)
        self.layout_actividad.addStretch(1)
        self.scroll_actividad.setWidget(self.lista_actividad_widget)
        self.scroll_actividad.viewport().setObjectName("viewportActividad")
        self.scroll_actividad.viewport().setAutoFillBackground(False)
        self.scroll_actividad.viewport().setStyleSheet(
            "QWidget#viewportActividad { background: transparent; }"
        )
        self.lista_actividad_widget.setObjectName("listaActividad")
        self.lista_actividad_widget.setStyleSheet(
            "QWidget#listaActividad { background: transparent; }"
        )
        caja.addWidget(self.scroll_actividad, 1)

        titulo_alertas = QLabel("Alertas")
        titulo_alertas.setObjectName("tituloAlertas")
        caja.addWidget(titulo_alertas)
        self.lista_alertas = QListWidget()
        self.lista_alertas.setObjectName("listaAlertas")
        self.lista_alertas.setMaximumHeight(112)
        self.lbl_sin_alertas = QLabel("Sin alertas")
        self.lbl_sin_alertas.setObjectName("sinAlertas")
        self.lbl_sin_alertas.setWordWrap(True)
        caja.addWidget(self.lista_alertas)
        caja.addWidget(self.lbl_sin_alertas)

        pie = QLabel(
            "La actividad se reconstruye desde mensajes reales; no se guarda en disco."
        )
        pie.setObjectName("subtituloDatos")
        pie.setWordWrap(True)
        caja.addWidget(pie)
        return panel

    def _construir_configuracion(self) -> None:
        self.seccion_configuracion = QWidget()
        seccion = QVBoxLayout(self.seccion_configuracion)
        seccion.setContentsMargins(0, 0, 0, 0)
        seccion.setSpacing(13)

        cabecera, _fila = self._encabezado_seccion(
            "Configuración",
            "Solo lectura · la edición se realiza en config.ini",
            "config",
            COLORS["verde_bosque"],
            COLORS["verde_suave"],
        )
        seccion.addWidget(cabecera)

        self.grid_config = QGridLayout()
        self.grid_config.setHorizontalSpacing(12)
        self.grid_config.setVerticalSpacing(12)

        tarjeta_conexiones, filas_conexiones = self._tarjeta_config("Conexiones")
        self.cfg_broker_principal = self._etiqueta_config("Conectando", "conectando")
        self.cfg_broker_txt = self._etiqueta_config(
            "Conectando" if self.config.txt_broker_host else "Mismo broker",
            "conectando" if self.config.txt_broker_host else "sin_datos",
        )
        self.cfg_gateway = self._etiqueta_config("Sin datos", "sin_datos")
        self.cfg_txt = self._etiqueta_config("Sin datos", "sin_datos")
        self._fila_config(filas_conexiones, "Broker PC", self.cfg_broker_principal)
        self._fila_config(filas_conexiones, "Broker TXT", self.cfg_broker_txt)
        self._fila_config(filas_conexiones, "Gateway", self.cfg_gateway)
        self._fila_config(filas_conexiones, "TXT", self.cfg_txt)

        tarjeta_umbrales, filas_umbrales = self._tarjeta_config("Umbrales")
        self._fila_config(
            filas_umbrales,
            "Temperatura alta",
            self._etiqueta_config(
                f"> {formatear_numero(self.config.umbral_temp_alta)} °C"
            ),
        )
        self._fila_config(
            filas_umbrales,
            "Humedad baja",
            self._etiqueta_config(
                f"< {formatear_numero(self.config.umbral_hum_baja)} %"
            ),
        )
        self._fila_config(
            filas_umbrales,
            "Presión baja",
            self._etiqueta_config(
                f"< {formatear_numero(self.config.umbral_presion_baja)} hPa"
            ),
        )
        self._fila_config(
            filas_umbrales,
            "Gas alto",
            self._etiqueta_config(
                f"> {formatear_numero(self.config.umbral_gas_alto)} kΩ"
            ),
        )

        tarjeta_tiempos, filas_tiempos = self._tarjeta_config("Tiempos")
        self._fila_config(
            filas_tiempos,
            "Timeout TXT",
            self._etiqueta_config(f"{self.config.timeout_txt_seg} s"),
        )
        self._fila_config(
            filas_tiempos,
            "Datos vencidos",
            self._etiqueta_config(f"{UMBRAL_SIN_DATOS_RECIENTES_SEG} s"),
        )
        self._fila_config(
            filas_tiempos,
            "Gateway sin actividad",
            self._etiqueta_config(f"{UMBRAL_GATEWAY_ACTIVO_SEG} s"),
        )
        self._fila_config(
            filas_tiempos,
            "Botón a neutral",
            self._etiqueta_config(f"{UMBRAL_BOTON_NEUTRAL_SEG} s · visual"),
        )

        self._cards_config = [
            tarjeta_conexiones,
            tarjeta_umbrales,
            tarjeta_tiempos,
        ]
        seccion.addLayout(self.grid_config)
        self.layout_contenido.addWidget(self.seccion_configuracion)

    def _encabezado_seccion(
        self,
        titulo: str,
        subtitulo: str,
        icono_nombre: str,
        color_icono: str,
        fondo_icono: str,
    ) -> tuple[QWidget, QHBoxLayout]:
        contenedor = QWidget()
        fila = QHBoxLayout(contenedor)
        fila.setContentsMargins(0, 0, 0, 0)
        fila.setSpacing(11)
        fila.addWidget(
            crear_icono(icono_nombre, color_icono, 42, fondo_icono, 22)
        )
        textos = QVBoxLayout()
        textos.setSpacing(1)
        etiqueta_titulo = QLabel(titulo)
        etiqueta_titulo.setObjectName("tituloSeccion")
        etiqueta_subtitulo = QLabel(subtitulo)
        etiqueta_subtitulo.setObjectName("subtituloSeccion")
        etiqueta_subtitulo.setWordWrap(True)
        textos.addWidget(etiqueta_titulo)
        textos.addWidget(etiqueta_subtitulo)
        fila.addLayout(textos)
        fila.addStretch(1)
        return contenedor, fila

    def _tarjeta_config(self, titulo: str) -> tuple[QFrame, QVBoxLayout]:
        tarjeta = QFrame()
        tarjeta.setObjectName("configTarjeta")
        tarjeta.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        caja = QVBoxLayout(tarjeta)
        caja.setContentsMargins(16, 14, 16, 14)
        caja.setSpacing(8)
        etiqueta = QLabel(titulo)
        etiqueta.setObjectName("configTitulo")
        caja.addWidget(etiqueta)
        return tarjeta, caja

    def _etiqueta_config(self, texto: str, estado: str = "") -> QLabel:
        etiqueta = QLabel(texto)
        etiqueta.setObjectName("configValor")
        if estado:
            etiqueta.setProperty("estado", estado)
        return etiqueta

    def _fila_config(
        self, caja: QVBoxLayout, clave: str, valor: QLabel
    ) -> None:
        fila = QHBoxLayout()
        fila.setSpacing(8)
        etiqueta = QLabel(clave)
        etiqueta.setObjectName("configClave")
        fila.addWidget(etiqueta)
        fila.addStretch(1)
        fila.addWidget(valor)
        caja.addLayout(fila)

    def _boton_direccion(self, icono_nombre: str, etiqueta: str) -> QPushButton:
        boton = QPushButton()
        boton.setObjectName("direccion")
        boton.setFixedSize(72, 52)
        boton.setIcon(icono(icono_nombre, COLORS["texto_suave"], 22))
        boton.setIconSize(QSize(22, 22))
        boton.setEnabled(False)
        boton.setAccessibleName(etiqueta)
        boton.setToolTip(f"{etiqueta} · control deshabilitado")
        return boton

    # -- Distribución responsiva --

    def resizeEvent(self, evento) -> None:  # noqa: N802 (API de Qt)
        super().resizeEvent(evento)
        if hasattr(self, "cabecera_grid"):
            self._reacomodar()

    def _reacomodar(self, force: bool = False) -> None:
        ancho = self.width()

        nav_superior = ancho >= 1120
        if force or self._nav_en_superior != nav_superior:
            self.cabecera_grid.removeWidget(self.nav_widget)
            if nav_superior:
                self.cabecera_grid.addWidget(
                    self.nav_widget, 0, 1, alignment=Qt.AlignmentFlag.AlignRight
                )
            else:
                self.cabecera_grid.addWidget(self.nav_widget, 1, 0, 1, 3)
            self._nav_en_superior = nav_superior

        columnas = 4 if ancho >= 1180 else 2 if ancho >= 700 else 1
        if force or self._modos_layout.get("sensores") != columnas:
            self._refluir_grid(self.grid_sensores, self._cards_sensores, columnas)
            self._modos_layout["sensores"] = columnas

        columnas = 3 if ancho >= 980 else 2 if ancho >= 640 else 1
        if force or self._modos_layout.get("conexiones") != columnas:
            self._refluir_grid(
                self.grid_conexiones, self._cards_conexiones, columnas
            )
            self._modos_layout["conexiones"] = columnas

        modo_robot = 3 if ancho >= 1180 else 2 if ancho >= 900 else 1
        if force or self._modos_layout.get("robot") != modo_robot:
            self._refluir_robot(modo_robot)
            self._modos_layout["robot"] = modo_robot

        columnas = 3 if ancho >= 1050 else 2 if ancho >= 700 else 1
        if force or self._modos_layout.get("config") != columnas:
            self._refluir_grid(self.grid_config, self._cards_config, columnas)
            self._modos_layout["config"] = columnas

    def _refluir_grid(
        self,
        grid: QGridLayout,
        widgets: list[QWidget],
        columnas: int,
    ) -> None:
        for widget in widgets:
            grid.removeWidget(widget)
        sobran = len(widgets) % columnas if columnas > 1 else 0
        for indice, widget in enumerate(widgets):
            if sobran == 1 and indice == len(widgets) - 1:
                grid.addWidget(widget, indice // columnas, 0, 1, columnas)
            else:
                grid.addWidget(widget, indice // columnas, indice % columnas)
        for columna in range(4):
            grid.setColumnStretch(columna, 1 if columna < columnas else 0)

    def _refluir_robot(self, modo: int) -> None:
        for widget in (
            self.panel_control,
            self.columna_derecha_robot,
            self.seccion_datos,
        ):
            self.grid_robot.removeWidget(widget)
        if modo == 3:
            self.grid_robot.addWidget(self.panel_control, 0, 0)
            self.grid_robot.addWidget(self.columna_derecha_robot, 0, 1)
            self.grid_robot.addWidget(self.seccion_datos, 0, 2)
        elif modo == 2:
            self.grid_robot.addWidget(self.panel_control, 0, 0)
            self.grid_robot.addWidget(self.columna_derecha_robot, 0, 1)
            self.grid_robot.addWidget(self.seccion_datos, 1, 0, 1, 2)
        else:
            self.grid_robot.addWidget(self.panel_control, 0, 0)
            self.grid_robot.addWidget(self.columna_derecha_robot, 1, 0)
            self.grid_robot.addWidget(self.seccion_datos, 2, 0)
        for columna in range(3):
            self.grid_robot.setColumnStretch(
                columna, 1 if columna < min(modo, 3) else 0
            )

    def _ir_a(self, clave: str) -> None:
        self._marcar_nav(clave)
        if clave == "inicio":
            self.scroll.verticalScrollBar().setValue(0)
            return
        seccion = {
            "sensores": self.seccion_sensores,
            "robot": self.seccion_robot,
            "datos": self.seccion_datos,
            "configuracion": self.seccion_configuracion,
        }.get(clave)
        if seccion is not None:
            self.scroll.ensureWidgetVisible(seccion, 0, 18)

    def _marcar_nav(self, clave: str) -> None:
        for nombre, boton in self.botones_nav.items():
            boton.setChecked(nombre == clave)

    # -- Métodos de presentación (sin red ni persistencia) --

    @staticmethod
    def _clave_estado(estado: str) -> str:
        return {
            ESTADO_CONECTADO: "conectado",
            ESTADO_DESCONECTADO: "desconectado",
            "Conectado": "conectado",
            "Desconectado": "desconectado",
            "Sin datos": "sin_datos",
        }.get(estado, estado)

    def _fijar_config(
        self, etiqueta: QLabel, estado: str, texto: str | None = None
    ) -> None:
        if texto is not None:
            etiqueta.setText(texto)
        etiqueta.setProperty("estado", estado)
        repolish(etiqueta)

    def set_estado_gateway(self, conectado: bool) -> None:
        """Compatibilidad con la firma anterior (booleana)."""
        self.set_estado_gateway_detallado(
            ESTADO_CONECTADO if conectado else ESTADO_DESCONECTADO
        )

    def set_estado_gateway_detallado(
        self, estado: str, hora: datetime | None = None
    ) -> None:
        clave = self._clave_estado(estado)
        hora_texto = hora.strftime("%H:%M:%S") if hora else None
        self.card_gateway.set_estado(clave, hora_texto)
        self._fijar_config(
            self.cfg_gateway,
            clave,
            self._ETIQUETAS_ESTADO.get(clave, "Sin datos"),
        )

    def set_estado_txt(self, conectado: bool) -> None:
        """Compatibilidad con la firma anterior (booleana)."""
        self.set_estado_txt_detallado(
            ESTADO_CONECTADO if conectado else ESTADO_DESCONECTADO
        )

    def set_estado_txt_detallado(
        self, estado: str, hora: datetime | None = None
    ) -> None:
        clave = self._clave_estado(estado)
        hora_texto = hora.strftime("%H:%M:%S") if hora else None
        self.card_txt.set_estado(clave, hora_texto)
        self._fijar_config(
            self.cfg_txt,
            clave,
            self._ETIQUETAS_ESTADO.get(clave, "Sin datos"),
        )

    def set_estado_broker(
        self, nombre: str, conectado: bool, detalle: str = ""
    ) -> None:
        """Actualiza el broker principal o el broker dedicado del TXT.

        No muestra host, usuario ni contraseña. El broker es el enlace
        MQTT de la PC, no el hardware.
        """
        ahora = datetime.now().strftime("%H:%M:%S")
        clave = "conectado" if conectado else "desconectado"
        texto = "Conectado" if conectado else "Desconectado"
        if nombre.lower() == "txt":
            self._broker_txt_conectado = conectado
            if conectado:
                self._hora_broker_txt = ahora
            self._fijar_config(self.cfg_broker_txt, clave, texto)
            return

        self._broker_principal_conectado = conectado
        if conectado:
            self._hora_broker_principal = ahora
        self.card_broker.set_estado(
            clave,
            ahora if conectado else self._hora_broker_principal,
            detalle,
        )
        self._fijar_config(self.cfg_broker_principal, clave, texto)
        self._actualizar_vivo()

    def _actualizar_vivo(self) -> None:
        if not self._broker_principal_conectado:
            self.badge_vivo.set_estado("sin_conexion", "SIN CONEXIÓN")
        elif not self._hay_lectura or not self._datos_recientes:
            self.badge_vivo.set_estado("sin_datos", "SIN DATOS")
        else:
            self.badge_vivo.set_estado("en_vivo", "EN VIVO")

    def mostrar_lectura(self, lectura: Lectura, hora_texto: str = "") -> None:
        """Refleja una lectura válida; los ausentes no se inventan."""
        hora = hora_texto or datetime.now().strftime("%H:%M:%S")
        self._hay_lectura = True
        self._datos_recientes = True
        self._ultima_hora_lectura = hora

        alerta_temp = lectura.temperatura > self.config.umbral_temp_alta
        alerta_hum = lectura.humedad < self.config.umbral_hum_baja

        self.tarjetas_cards["temperatura"].actualizar(
            lectura.temperatura,
            "alerta" if alerta_temp else "normal",
            "Alerta" if alerta_temp else "Normal",
            hora,
            f"Alerta si > {formatear_numero(self.config.umbral_temp_alta)} °C",
        )
        self.tarjetas_cards["humedad"].actualizar(
            lectura.humedad,
            "alerta" if alerta_hum else "normal",
            "Alerta" if alerta_hum else "Normal",
            hora,
            f"Alerta si < {formatear_numero(self.config.umbral_hum_baja)} %",
        )

        if lectura.presion is None:
            estado = (
                "no_disponible"
                if lectura.presion_no_disponible
                else "sin_datos"
            )
            self.tarjetas_cards["presion"].actualizar(
                None,
                estado,
                "No disponible" if lectura.presion_no_disponible else "Sin dato",
                hora,
                "El sensor no entregó presión en la última lectura.",
            )
        else:
            alerta_presion = lectura.presion < self.config.umbral_presion_baja
            self.tarjetas_cards["presion"].actualizar(
                lectura.presion,
                "alerta" if alerta_presion else "normal",
                "Alerta" if alerta_presion else "Normal",
                hora,
                f"Alerta si < {formatear_numero(self.config.umbral_presion_baja)} hPa",
            )

        if lectura.gas is None:
            estado = (
                "no_disponible" if lectura.gas_no_disponible else "sin_datos"
            )
            self.tarjetas_cards["gas"].actualizar(
                None,
                estado,
                "No disponible" if lectura.gas_no_disponible else "Sin dato",
                hora,
                "El sensor no entregó gas en la última lectura.",
            )
        else:
            alerta_gas = lectura.gas > self.config.umbral_gas_alto
            self.tarjetas_cards["gas"].actualizar(
                lectura.gas,
                "alerta" if alerta_gas else "normal",
                "Alerta" if alerta_gas else "Normal",
                hora,
                f"Alerta si > {formatear_numero(self.config.umbral_gas_alto)} kΩ",
            )

        self._actualizar_alertas_umbral(lectura)
        self.lbl_actualizacion.setText(f"Última actualización: {hora}")
        self._actualizar_vivo()

    def _actualizar_alertas_umbral(self, lectura: Lectura) -> None:
        """Registra un aviso al entrar en cada condición fuera de rango."""
        condiciones = {
            "temperatura": (
                lectura.temperatura > self.config.umbral_temp_alta,
                f"Temperatura alta: {formatear_numero(lectura.temperatura)} °C "
                f"(umbral > {formatear_numero(self.config.umbral_temp_alta)} °C).",
            ),
            "humedad": (
                lectura.humedad < self.config.umbral_hum_baja,
                f"Humedad baja: {formatear_numero(lectura.humedad)} % "
                f"(umbral < {formatear_numero(self.config.umbral_hum_baja)} %).",
            ),
            "presion": (
                lectura.presion is not None
                and lectura.presion < self.config.umbral_presion_baja,
                f"Presión baja: {formatear_numero(lectura.presion or 0.0)} hPa "
                f"(umbral < {formatear_numero(self.config.umbral_presion_baja)} hPa).",
            ),
            "gas": (
                lectura.gas is not None
                and lectura.gas > self.config.umbral_gas_alto,
                f"Gas alto: {formatear_numero(lectura.gas or 0.0)} kΩ "
                f"(umbral > {formatear_numero(self.config.umbral_gas_alto)} kΩ).",
            ),
        }
        for clave, (activa, mensaje) in condiciones.items():
            if activa:
                if clave not in self._alertas_umbral_activas:
                    self.mostrar_alerta(mensaje)
                    self._alertas_umbral_activas.add(clave)
            else:
                self._alertas_umbral_activas.discard(clave)

    def marcar_sin_actualizacion(self) -> None:
        """Marca datos vencidos conservando la última lectura visible."""
        self._datos_recientes = False
        for tarjeta in self.tarjetas_cards.values():
            tarjeta.marcar_vencido()
        if self._hay_lectura:
            self.lbl_actualizacion.setText(
                f"Última actualización: {self._ultima_hora_lectura} · "
                "sin datos recientes"
            )
        self._actualizar_vivo()

    def mostrar_estado_broker(self, texto: str) -> None:
        """Compatibilidad: no expone el texto crudo del cliente MQTT.

        El texto de Paho puede incluir host/puerto; esta adaptación solo
        deriva un estado genérico y actualiza las etiquetas visuales.
        """
        minusculas = texto.lower()
        if any(
            palabra in minusculas
            for palabra in ("error", "perdida", "pérdida", "desconect", "rechaz")
        ):
            conectado = False
        else:
            conectado = "conectado" in minusculas
        self.set_estado_broker(
            "principal",
            conectado,
            "Estado del enlace MQTT actualizado." if conectado else "",
        )

    def mostrar_boton(self, token: str) -> None:
        """Muestra el último evento recibido del gateway."""
        self.lbl_direccion.setText(f"Dirección: {token}")
        self.lbl_direccion.setProperty("estado", "activo")
        repolish(self.lbl_direccion)

    def marcar_boton_neutral(self) -> None:
        """Vuelve el indicador a Neutral por timeout (solo visual)."""
        self.lbl_direccion.setText("Dirección: Neutral")
        self.lbl_direccion.setProperty("estado", "")
        repolish(self.lbl_direccion)

    def mostrar_pelota_recibida(self) -> None:
        """Refleja un PELOTA real, sin afirmar que el servo se movió."""
        self.lbl_pelota.setText(
            "Evento PELOTA recibido · sin confirmación del servo"
        )
        self.lbl_pelota.setProperty("estado", "activo")
        repolish(self.lbl_pelota)

    # -- Control de velocidad del TXT --

    def _on_slider_velocidad_cambiado(self, valor: int) -> None:
        """Debounce del deslizador: programa la publicación al estabilizarse."""
        self.lbl_velocidad.setText(str(valor))
        self._valor_velocidad_pendiente = valor
        if self._timer_velocidad is None:
            self._timer_velocidad = QTimer(self)
            self._timer_velocidad.setSingleShot(True)
            self._timer_velocidad.timeout.connect(
                self._publicar_velocidad_pendiente
            )
        self._timer_velocidad.start(300)

    def _publicar_velocidad_pendiente(self) -> None:
        """Publica el valor pendiente si hay un cliente MQTT y el TXT está listo."""
        if self._valor_velocidad_pendiente is None:
            return
        valor = self._valor_velocidad_pendiente
        self._valor_velocidad_pendiente = None
        # Si hay broker dedicado para el TXT, publicar por ahí; si no, por el principal.
        cliente = getattr(self, "_cliente_txt_mqtt", None)
        if cliente is None:
            cliente = getattr(self, "_cliente_mqtt", None)
        if cliente is not None:
            cliente.publicar_velocidad(valor)
            self.lbl_velocidad_estado.setText(
                f"Velocidad {valor} enviada · esperando confirmación del TXT"
            )
            self.lbl_velocidad_estado.setProperty("estado", "activo")
            repolish(self.lbl_velocidad_estado)
            self._iniciar_tiempo_espera_velocidad()

    def _iniciar_tiempo_espera_velocidad(self) -> None:
        """Arranca el temporizador de espera de confirmación de velocidad."""
        self._detener_tiempo_espera_velocidad()
        self._timer_velocidad_confirmacion = QTimer(self)
        self._timer_velocidad_confirmacion.setSingleShot(True)
        self._timer_velocidad_confirmacion.setInterval(
            int(self._VALOR_VELOCIDAD_TIMEOUT_SEG * 1000)
        )
        self._timer_velocidad_confirmacion.timeout.connect(
            self._velocidad_confirmacion_timeout
        )
        self._timer_velocidad_confirmacion.start()

    def _detener_tiempo_espera_velocidad(self) -> None:
        """Detiene el temporizador de espera de confirmación de velocidad."""
        if self._timer_velocidad_confirmacion is not None:
            self._timer_velocidad_confirmacion.stop()
            self._timer_velocidad_confirmacion = None

    def _velocidad_confirmacion_timeout(self) -> None:
        """Se dispara si el TXT no confirma la velocidad a tiempo."""
        self._detener_tiempo_espera_velocidad()
        valor = self._valor_velocidad_pendiente
        texto_valor = str(valor) if valor is not None else "desconocido"
        self.lbl_velocidad_estado.setText(
            f"Velocidad {texto_valor}: no se recibió confirmación del TXT (timeout {self._VALOR_VELOCIDAD_TIMEOUT_SEG:.0f}s)"
        )
        self.lbl_velocidad_estado.setProperty("estado", "alerta")
        repolish(self.lbl_velocidad_estado)
        self.mostrar_alerta(
            f"Velocidad {texto_valor} enviada pero el TXT no confirmó aplicación a M1-M4."
        )

    def _lanzar_pelota(self) -> None:
        """Publica exactamente un PELOTA en agrotech/botones (sin retención)."""
        # Si hay broker dedicado para el TXT, publicar por ahí; si no, por el principal.
        cliente = getattr(self, "_cliente_txt_mqtt", None)
        if cliente is None:
            cliente = getattr(self, "_cliente_mqtt", None)
        if cliente is not None:
            cliente.publicar_boton("PELOTA")
            self.lbl_pelota.setText(
                "Evento PELOTA enviado · esperando ejecución en el TXT"
            )
            self.lbl_pelota.setProperty("estado", "activo")
            repolish(self.lbl_pelota)

    def set_velocidad_confirmada(self, valor: int) -> None:
        """Refleja la confirmación de velocidad aplicada por el TXT."""
        self._detener_tiempo_espera_velocidad()
        self._velocidad_aplicada = valor
        self.lbl_velocidad.setText(str(valor))
        self.slider_velocidad.setValue(valor)
        self.lbl_velocidad_estado.setText(
            f"Velocidad {valor} aplicada en el TXT"
        )
        self.lbl_velocidad_estado.setProperty("estado", "conectado")
        repolish(self.lbl_velocidad_estado)

    def set_txt_para_velocidad(self, conectado: bool) -> None:
        """Habilita o deshabilita el control de velocidad según el TXT."""
        self._txt_para_velocidad = conectado
        self.slider_velocidad.setEnabled(conectado)
        self.btn_orden.setEnabled(conectado)
        if conectado:
            self.nota_velocidad.setText(
                "Desliza para fijar la velocidad PWM (0..512) del TXT."
            )
            self.lbl_velocidad_estado.setText(
                "TXT conectado · velocidad lista para aplicar"
            )
            self.lbl_velocidad_estado.setProperty("estado", "conectado")
            self.nota_lanzador.setText(
                "Haz clic en «Lanzar pelota» para enviar PELOTA al TXT."
            )
            self.nota_lanzador.setProperty("estado", "")
            self.btn_orden.setToolTip("Lanzar pelota · envía PELOTA al TXT")
        else:
            self.nota_velocidad.setText(
                "Esperando conexión del TXT para habilitar el control de velocidad."
            )
            self.lbl_velocidad_estado.setText(
                "TXT desconectado · velocidad sin aplicar"
            )
            self.lbl_velocidad_estado.setProperty("estado", "desconectado")
            self.nota_lanzador.setText(
                "Esperando conexión del TXT para habilitar el lanzador de pelota."
            )
            self.nota_lanzador.setProperty("estado", "desconectado")
            self.btn_orden.setToolTip("Lanzar pelota · control deshabilitado")
        repolish(self.lbl_velocidad_estado)
        repolish(self.nota_velocidad)
        repolish(self.nota_lanzador)
        repolish(self.btn_orden)

    # -- Cámara del TXT --

    def _iniciar_tiempo_espera_camara(self) -> None:
        """Arranca el temporizador de detección de señal interrumpida."""
        self._detener_tiempo_espera_camara()
        self._timer_camara_timeout = QTimer(self)
        self._timer_camara_timeout.setSingleShot(True)
        self._timer_camara_timeout.setInterval(3000)
        self._timer_camara_timeout.timeout.connect(
            self._camara_senal_interrumpida
        )
        self._timer_camara_timeout.start()

    def _detener_tiempo_espera_camara(self) -> None:
        """Detiene el temporizador de señal interrumpida de cámara."""
        if self._timer_camara_timeout is not None:
            self._timer_camara_timeout.stop()
            self._timer_camara_timeout = None

    def _camara_senal_interrumpida(self) -> None:
        """Se dispara si dejan de llegar cuadros de la cámara."""
        self._detener_tiempo_espera_camara()
        self.lbl_camara_estado.setText("Cámara: señal interrumpida")
        self.lbl_camara_estado.setProperty("estado", "alerta")
        repolish(self.lbl_camara_estado)
        self.nota_camara.setText(
            "No se reciben cuadros de la cámara del TXT."
        )
        self.mostrar_alerta(
            "Señal de cámara interrumpida: no llegan cuadros del TXT."
        )

    def mostrar_cuadro_camara(self, payload: bytes) -> None:
        """Muestra un cuadro JPEG recibido del TXT en la vista previa."""
        self._detener_tiempo_espera_camara()
        imagen = QImage.fromData(payload)
        if imagen.isNull():
            self.lbl_camara_estado.setText(
                "Cámara: cuadro JPEG inválido"
            )
            self.lbl_camara_estado.setProperty("estado", "alerta")
            repolish(self.lbl_camara_estado)
            self.mostrar_alerta(
                "Cuadro de cámara recibido pero no se pudo decodificar como JPEG."
            )
            return
        pixmap = QPixmap.fromImage(imagen)
        self.lbl_camara.setPixmap(pixmap)
        self.lbl_camara_estado.setText("Cámara: transmitiendo")
        self.lbl_camara_estado.setProperty("estado", "conectado")
        repolish(self.lbl_camara_estado)
        self.nota_camara.setText(
            f"Cuadro de cámara recibido ({len(payload)} bytes)."
        )
        self._iniciar_tiempo_espera_camara()

    def agregar_actividad(self, evento: EventoActividad) -> None:
        """Añade un evento real al panel acotado de actividad."""
        fila = ActivityRow(evento)
        self._filas_actividad.insert(0, fila)
        self.layout_actividad.insertWidget(0, fila)
        self.lbl_sin_actividad.setVisible(False)
        while len(self._filas_actividad) > MAX_EVENTOS_ACTIVIDAD:
            antigua = self._filas_actividad.pop()
            self.layout_actividad.removeWidget(antigua)
            antigua.deleteLater()
        self.scroll_actividad.verticalScrollBar().setValue(0)

    def mostrar_alerta(self, texto: str) -> None:
        """Agrega una alerta visible a la lista."""
        if self.lista_alertas.count() >= 50:
            self.lista_alertas.takeItem(0)
        self.lista_alertas.addItem(f"Alerta · {texto}")
        self.lbl_sin_alertas.setVisible(False)

    def limpiar_alertas(self) -> None:
        """Vacía la lista y vuelve a mostrar "Sin alertas"."""
        self.lista_alertas.clear()
        self.lbl_sin_alertas.setVisible(True)
