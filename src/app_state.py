"""Estado en memoria de la sesión (Fase 1).

Guarda únicamente la lectura actual, la hora de recepción y los
estados del gateway y del TXT. No persiste nada en disco ni en
base de datos.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime


TEXTO_SIN_DATO = "Sin dato"
ESTADO_DESCONECTADO = "Desconectado"
ESTADO_CONECTADO = "Conectado"
ESTADO_SIN_DATOS = "Sin datos"

# La actividad reciente vive solo en memoria y nunca crece sin límite.
MAX_EVENTOS_ACTIVIDAD = 30

# Umbral de presentación: segundos sin recepción para considerar
# los datos como vencidos ("Sin datos recientes"). Solo afecta a la
# interfaz; no cambia el contrato de mensajes ni persiste nada.
UMBRAL_SIN_DATOS_RECIENTES_SEG = 30

# Segundos sin eventos de botón para volver el indicador a Neutral.
# Solo visual; NO es un mecanismo de seguridad para movimientos.
UMBRAL_BOTON_NEUTRAL_SEG = 5

# El nodo publica sensores cada 10 s (PERIODO_SENSORES del firmware).
# 30 s tolera hasta tres publicaciones perdidas antes de considerar
# desconectado al gateway. Solo presentación; no afecta al TXT.
UMBRAL_GATEWAY_ACTIVO_SEG = 30


@dataclass
class Lectura:
    """Lectura ambiental normalizada (puede tener presión/gas no disponibles)."""

    temperatura: float
    humedad: float
    presion: float | None
    gas: float | None
    a_th: int
    a_pg: int
    presion_no_disponible: bool = False
    gas_no_disponible: bool = False


@dataclass(frozen=True)
class EventoActividad:
    """Evento real mostrado en la actividad reciente (solo memoria)."""

    tipo: str
    titulo: str
    detalle: str = ""
    hora: datetime = field(default_factory=datetime.now)


@dataclass
class SessionState:
    """Estado de la sesión, todo en memoria."""

    lectura: Lectura | None = None
    hora_recepcion: datetime | None = None
    estado_gateway: str = ESTADO_DESCONECTADO
    estado_txt: str = ESTADO_DESCONECTADO
    # Hora de la última actividad válida del gateway (None = nunca).
    hora_gateway: datetime | None = None
    # Hora del último mensaje del gateway, incluso si fue OFFLINE.
    hora_gateway_mensaje: datetime | None = None
    # Hora del último ONLINE recibido del TXT (None = nunca).
    hora_txt: datetime | None = None
    # Indican si alguna vez se recibió información real de cada enlace.
    gateway_visto: bool = False
    txt_visto: bool = False
    # Último evento de botón del gateway y su hora (None = ninguno).
    ultimo_boton: str | None = None
    hora_boton: datetime | None = None
    # Velocidad del TXT: último valor enviado por el slider y último valor
    # confirmado por el TXT (None = sin confirmación aún).
    velocidad_actual: int = 0
    velocidad_confirmada: int | None = None
    alertas: list = field(default_factory=list)
    # Actividad reciente acotada: nunca crece más de MAX_EVENTOS_ACTIVIDAD.
    actividad: deque[EventoActividad] = field(
        default_factory=lambda: deque(maxlen=MAX_EVENTOS_ACTIVIDAD)
    )

    def actualizar_lectura(self, lectura: Lectura) -> None:
        """Guarda la lectura actual y su hora. No hay historial."""
        self.lectura = lectura
        self.hora_recepcion = datetime.now()

    def marcar_estado_gateway(self, estado: str) -> None:
        """Actualiza el estado del gateway y su última actividad.

        Un estado distinto de Desconectado (p. ej. ONLINE explícito)
        cuenta como actividad; Desconectado limpia la marca de
        actividad, pero conserva la hora del último mensaje para la UI.
        """
        ahora = datetime.now()
        self.estado_gateway = estado
        self.gateway_visto = True
        self.hora_gateway_mensaje = ahora
        self.hora_gateway = ahora if estado != ESTADO_DESCONECTADO else None

    def marcar_gateway_activo(self) -> None:
        """Registra actividad válida del gateway (sensores o botones)."""
        ahora = datetime.now()
        self.estado_gateway = ESTADO_CONECTADO
        self.gateway_visto = True
        self.hora_gateway = ahora
        self.hora_gateway_mensaje = ahora

    def gateway_sin_comunicacion(
        self, timeout_seg: int = UMBRAL_GATEWAY_ACTIVO_SEG
    ) -> bool:
        """True si no hay actividad reciente del gateway.

        Solo lectura del estado en memoria; el TXT tiene su propio
        temporizador independiente.
        """
        if self.hora_gateway is None:
            return True
        return (datetime.now() - self.hora_gateway).total_seconds() > timeout_seg

    def marcar_estado_txt(self, estado: str) -> None:
        """Actualiza el estado del TXT."""
        self.estado_txt = estado

    def marcar_txt_online(self) -> None:
        """Registra un ONLINE válido del TXT con su hora (Fase 5A)."""
        self.estado_txt = ESTADO_CONECTADO
        self.hora_txt = datetime.now()
        self.txt_visto = True

    def txt_sin_comunicacion(self, timeout_seg: int) -> bool:
        """Indica si el TXT venció por ausencia de heartbeat.

        True si nunca llegó ONLINE o si el último supera el timeout.
        Solo lectura del estado en memoria.
        """
        if self.hora_txt is None:
            return True
        return (datetime.now() - self.hora_txt).total_seconds() > timeout_seg

    def actualizar_boton(self, token: str) -> None:
        """Guarda el último evento de botón y su hora. No hay historial."""
        self.ultimo_boton = token
        self.hora_boton = datetime.now()

    def actualizar_velocidad(self, valor: int) -> None:
        """Guarda el valor de velocidad enviado por el slider."""
        self.velocidad_actual = max(0, min(512, int(valor)))

    def confirmar_velocidad(self, valor: int) -> None:
        """Registra la confirmación de velocidad recibida del TXT."""
        self.velocidad_confirmada = max(0, min(512, int(valor)))

    def boton_vencido(
        self, timeout_seg: int = UMBRAL_BOTON_NEUTRAL_SEG
    ) -> bool:
        """Indica si el indicador debe volver a Neutral por timeout.

        Solo presentación; no es seguridad para movimientos.
        """
        if self.ultimo_boton is None or self.hora_boton is None:
            return True
        return (datetime.now() - self.hora_boton).total_seconds() > timeout_seg

    def registrar_actividad(
        self, tipo: str, titulo: str, detalle: str = ""
    ) -> EventoActividad:
        """Añade un evento real a la actividad reciente acotada."""
        evento = EventoActividad(tipo=tipo, titulo=titulo, detalle=detalle)
        self.actividad.append(evento)
        return evento

    def limpiar(self) -> None:
        """Vuelve al estado inicial: sin dato y desconectado."""
        self.lectura = None
        self.hora_recepcion = None
        self.estado_gateway = ESTADO_DESCONECTADO
        self.estado_txt = ESTADO_DESCONECTADO
        self.hora_gateway = None
        self.hora_gateway_mensaje = None
        self.hora_txt = None
        self.gateway_visto = False
        self.txt_visto = False
        self.ultimo_boton = None
        self.hora_boton = None
        self.velocidad_actual = 0
        self.velocidad_confirmada = None
        self.alertas = []
        self.actividad.clear()

    def sin_datos_recientes(
        self, umbral_seg: int = UMBRAL_SIN_DATOS_RECIENTES_SEG
    ) -> bool:
        """Indica si los datos están vencidos para la presentación.

        Devuelve True si no hay lectura o si la última recepción
        supera el umbral. Solo lectura del estado en memoria.
        """
        if self.lectura is None or self.hora_recepcion is None:
            return True
        return (datetime.now() - self.hora_recepcion).total_seconds() > umbral_seg
