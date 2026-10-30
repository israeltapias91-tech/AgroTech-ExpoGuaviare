"""Punto de entrada de la aplicación (fase gateway/botones).

Ventana de exposición + estado en memoria + MQTT de solo lectura:
broker principal (sensores, gateway, botones) y, si hay [broker_txt]
privado, broker dedicado autenticado (solo estado del TXT).
Sin base de datos, sin órdenes al TXT y sin actuadores.
"""

import sys
from pathlib import Path

# Permite ejecutar como `python src/main.py` desde la raíz del proyecto.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from src.app_config import load_config
from src.app_state import (
    ESTADO_CONECTADO,
    ESTADO_DESCONECTADO,
    UMBRAL_BOTON_NEUTRAL_SEG,
    UMBRAL_GATEWAY_ACTIVO_SEG,
    UMBRAL_SIN_DATOS_RECIENTES_SEG,
    Lectura,
    SessionState,
)
from src.mqtt_client import ClienteMQTT
from src.ui.main_window import MainWindow
from src.ui.widgets import formatear_numero


def main() -> int:
    """Crea la aplicación, conecta MQTT en segundo plano y muestra la ventana."""
    config = load_config()
    estado = SessionState()

    app = QApplication(sys.argv)
    ventana = MainWindow(config)

    def registrar(tipo: str, titulo: str, detalle: str = "") -> None:
        """Añade un evento real, acotado por SessionState."""
        evento = estado.registrar_actividad(tipo, titulo, detalle)
        ventana.agregar_actividad(evento)

    def resumen_lectura(lectura: Lectura) -> str:
        presion = (
            "P sin dato"
            if lectura.presion is None
            else f"P {formatear_numero(lectura.presion)} hPa"
        )
        gas = (
            "G sin dato"
            if lectura.gas is None
            else f"G {formatear_numero(lectura.gas)} kΩ"
        )
        return (
            f"T {formatear_numero(lectura.temperatura)} °C · "
            f"H {formatear_numero(lectura.humedad)} % · {presion} · {gas}"
        )

    registrar(
        "actividad",
        "Monitoreo iniciado",
        "Esperando conexión MQTT y datos reales del sistema.",
    )

    cliente = ClienteMQTT(
        config,
        usuario=config.mqtt_user or None,
        contrasena=config.mqtt_password or None,
        # Si hay cliente dedicado, él atiende el estado del TXT y se
        # evita el doble manejo del mismo topic.
        incluir_txt=not bool(config.txt_broker_host),
    )
    ventana._cliente_mqtt = cliente

    def marcar_gateway_activo(origen: str) -> None:
        """Marca al gateway conectado por actividad válida real."""
        anterior = estado.estado_gateway
        estado.marcar_gateway_activo()
        ventana.set_estado_gateway_detallado(
            ESTADO_CONECTADO, estado.hora_gateway_mensaje
        )
        if anterior != ESTADO_CONECTADO:
            registrar("gateway", "Gateway conectado", f"Actividad válida: {origen}.")

    def al_recibir_lectura(datos: dict) -> None:
        """Actualiza tarjetas, hora de recepción y estado de espera/vencimiento."""
        lectura = Lectura(
            temperatura=datos["temperatura"],
            humedad=datos["humedad"],
            presion=datos["presion"],
            gas=datos["gas"],
            a_th=datos["a_th"],
            a_pg=datos["a_pg"],
            presion_no_disponible=datos["presion_no_disponible"],
            gas_no_disponible=datos["gas_no_disponible"],
        )
        estado.actualizar_lectura(lectura)
        marcar_gateway_activo("lectura de sensores")
        hora = (
            estado.hora_recepcion.strftime("%H:%M:%S")
            if estado.hora_recepcion
            else ""
        )
        ventana.mostrar_lectura(lectura, hora)
        registrar("lectura", "Lectura ambiental", resumen_lectura(lectura))

    def al_estado_gateway(conectado: bool) -> None:
        """Marca el gateway conectado/desconectado (solo por su topic)."""
        anterior = estado.estado_gateway
        nuevo = ESTADO_CONECTADO if conectado else ESTADO_DESCONECTADO
        estado.marcar_estado_gateway(nuevo)
        ventana.set_estado_gateway_detallado(
            nuevo, estado.hora_gateway_mensaje
        )
        if anterior != nuevo:
            registrar(
                "gateway",
                "Gateway conectado" if conectado else "Gateway desconectado",
                "Estado ONLINE recibido."
                if conectado
                else "Estado OFFLINE recibido.",
            )

    def al_txt_online() -> None:
        """Marca el TXT conectado (solo por ONLINE real del TXT)."""
        anterior = estado.estado_txt
        estado.marcar_txt_online()
        ventana.set_estado_txt_detallado(ESTADO_CONECTADO, estado.hora_txt)
        ventana.set_txt_para_velocidad(True)
        if anterior != ESTADO_CONECTADO:
            registrar("txt", "TXT conectado", "Heartbeat ONLINE recibido.")

    def al_pelota() -> None:
        """Informa un PELOTA real sin confirmar el movimiento del servo."""
        marcar_gateway_activo("evento PELOTA")
        ventana.mostrar_pelota_recibida()
        registrar(
            "pelota",
            "Evento PELOTA recibido",
            "Pulsador físico · sin confirmación del servo.",
        )

    def al_mensaje_rechazado(motivo: str) -> None:
        """Muestra el motivo sin reemplazar el último dato válido."""
        ventana.mostrar_alerta(f"Mensaje rechazado: {motivo}")
        registrar("error", "Mensaje rechazado", motivo)

    def al_boton(token: str) -> None:
        """Refleja el evento de botón del gateway en el indicador."""
        estado.actualizar_boton(token)
        marcar_gateway_activo(f"botón {token}")
        ventana.mostrar_boton(token)
        registrar("boton", f"Botón recibido: {token}", "Evento del gateway.")

    broker_estados: dict[str, bool | None] = {"principal": None, "TXT": None}

    def al_broker(nombre: str, conectado: bool, _texto: str) -> None:
        """Actualiza el enlace MQTT sin exponer host ni credenciales."""
        anterior = broker_estados[nombre]
        broker_estados[nombre] = conectado
        ventana.set_estado_broker(
            nombre,
            conectado,
            "Enlace MQTT establecido." if conectado else "",
        )
        if anterior != conectado:
            registrar(
                "broker",
                f"Broker {nombre} conectado"
                if conectado
                else f"Broker {nombre} desconectado",
                "Enlace MQTT de la PC."
                if conectado
                else "Se reintentará automáticamente.",
            )

    cliente.senales.lectura_valida.connect(al_recibir_lectura)
    cliente.senales.gateway_conectado.connect(al_estado_gateway)
    cliente.senales.txt_online.connect(al_txt_online)
    cliente.senales.boton_evento.connect(al_boton)
    cliente.senales.pelota_evento.connect(al_pelota)
    cliente.senales.mensaje_rechazado.connect(al_mensaje_rechazado)
    cliente.senales.velocidad_confirmada.connect(
        ventana.set_velocidad_confirmada
    )
    cliente.senales.camara_recibida.connect(ventana.mostrar_cuadro_camara)
    cliente.senales.broker_conectado.connect(
        lambda texto: al_broker("principal", True, texto)
    )
    cliente.senales.broker_error.connect(
        lambda texto: al_broker("principal", False, texto)
    )
    cliente.senales.broker_desconectado.connect(
        lambda texto: al_broker("principal", False, texto)
    )

    # Segundo cliente opcional al broker dedicado autenticado (Fase 5B).
    # Solo existe si config.ini privado trae [broker_txt] con host.
    cliente_txt = None
    if config.txt_broker_host:
        cliente_txt = ClienteMQTT(
            config,
            nombre="broker TXT",
            host=config.txt_broker_host,
            port=config.txt_broker_port,
            usuario=config.txt_broker_user or None,
            contrasena=config.txt_broker_password or None,
            suscribir_todo=False,
        )
        cliente_txt.senales.txt_online.connect(al_txt_online)
        cliente_txt.senales.mensaje_rechazado.connect(al_mensaje_rechazado)
        cliente_txt.senales.velocidad_confirmada.connect(
            ventana.set_velocidad_confirmada
        )
        cliente_txt.senales.broker_conectado.connect(
            lambda texto: al_broker("TXT", True, texto)
        )
        cliente_txt.senales.broker_error.connect(
            lambda texto: al_broker("TXT", False, texto)
        )
        cliente_txt.senales.broker_desconectado.connect(
            lambda texto: al_broker("TXT", False, texto)
        )
        ventana._cliente_txt_mqtt = cliente_txt

    # Revisa el vencimiento sin bloquear: si la última lectura supera el
    # umbral existente, se muestra "Sin datos recientes" en lugar de
    # presentar valores antiguos como actuales.
    vigilante = QTimer(ventana)
    vigilante.setInterval(5000)

    def revisar_vencimiento() -> None:
        """Marca datos vencidos cuando aplica (solo si ya hubo una lectura)."""
        if estado.lectura is not None and estado.sin_datos_recientes(
            UMBRAL_SIN_DATOS_RECIENTES_SEG
        ):
            ventana.marcar_sin_actualizacion()
        # Sin heartbeat del TXT dentro del timeout configurable, vuelve a
        # Desconectado. Solo actúa si estaba marcado como conectado.
        if estado.estado_txt != ESTADO_DESCONECTADO and estado.txt_sin_comunicacion(
            config.timeout_txt_seg
        ):
            estado.marcar_estado_txt(ESTADO_DESCONECTADO)
            ventana.set_estado_txt_detallado(
                ESTADO_DESCONECTADO, estado.hora_txt
            )
            ventana.set_txt_para_velocidad(False)
            registrar(
                "txt",
                "TXT desconectado",
                "Sin heartbeat dentro del timeout configurado.",
            )
        # Sin actividad válida del gateway dentro del umbral (3 ciclos de
        # sensores de 10 s), vuelve a Desconectado. El TXT es independiente.
        if (
            estado.estado_gateway != ESTADO_DESCONECTADO
            and estado.gateway_sin_comunicacion(UMBRAL_GATEWAY_ACTIVO_SEG)
        ):
            hora_ultima = estado.hora_gateway_mensaje
            estado.marcar_estado_gateway(ESTADO_DESCONECTADO)
            ventana.set_estado_gateway_detallado(
                ESTADO_DESCONECTADO, hora_ultima
            )
            registrar(
                "gateway",
                "Gateway desconectado",
                "Sin actividad dentro del umbral de presentación.",
            )
        # Indicador de botones a Neutral tras 5 s sin eventos.
        # Solo visual; no es seguridad para movimientos.
        if estado.ultimo_boton is not None and estado.boton_vencido(
            UMBRAL_BOTON_NEUTRAL_SEG
        ):
            estado.ultimo_boton = None
            estado.hora_boton = None
            ventana.marcar_boton_neutral()

    vigilante.timeout.connect(revisar_vencimiento)
    vigilante.start()

    cliente.iniciar()
    if cliente_txt is not None:
        cliente_txt.iniciar()
    # Al cerrar la aplicación se desconecta MQTT y se detiene el hilo de red.
    app.aboutToQuit.connect(cliente.detener)
    if cliente_txt is not None:
        app.aboutToQuit.connect(cliente_txt.detener)

    ventana.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
