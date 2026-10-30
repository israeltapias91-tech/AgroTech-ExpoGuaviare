"""Cliente MQTT de solo lectura (fase gateway/botones).

Se suscribe a sensores, estado del gateway y botones (el segundo
cliente, opcional, solo al estado del TXT en el broker dedicado).
No publica nada y no toca `comandos/txt` ni `ack/txt`.

La red corre en el hilo interno de Paho (`loop_start`), por lo que la
interfaz PySide6 nunca se bloquea. Toda comunicación hacia la UI se
hace mediante señales Qt (seguras entre hilos).

Un mensaje publicado desde consola es una prueba de MQTT, no una
lectura de hardware real. En particular, nunca se publica ONLINE de
prueba en el topic del TXT: solo un ONLINE recibido puede marcarlo
conectado, y la comunicación real del TXT sigue pendiente.
"""

from __future__ import annotations

import paho.mqtt.client as mqtt
from PySide6.QtCore import QObject, Signal

from src.app_config import AppConfig
from src.messages import validar_boton, validar_sensores, validar_velocidad


class SenalesMQTT(QObject):
    """Señales Qt emitidas desde los callbacks de red de Paho."""

    # Datos normalizados de una lectura ambiental válida.
    lectura_valida = Signal(dict)
    # True si el gateway reportó ONLINE, False si reportó OFFLINE.
    gateway_conectado = Signal(bool)
    # Token de botón válido (ADELANTE/ATRAS/IZQUIERDA/DERECHA/LIBERADO).
    boton_evento = Signal(str)
    # PELOTA recibido: evento real del pulsador, sin confirmación del servo.
    pelota_evento = Signal()
    # ONLINE válido recibido en el topic de estado del TXT.
    txt_online = Signal()
    # Valor de velocidad confirmado por el TXT (entero 0..512).
    velocidad_confirmada = Signal(int)
    # Cuadro JPEG recibido de la cámara del TXT (bytes crudos).
    camara_recibida = Signal(bytes)
    # Motivo legible de un payload rechazado (no reemplaza el último dato).
    mensaje_rechazado = Signal(str)
    # Avisos sobre la conexión con el broker local (no es hardware).
    broker_conectado = Signal(str)
    broker_error = Signal(str)
    broker_desconectado = Signal(str)


class ClienteMQTT:
    """Envuelve a Paho con la configuración central de la aplicación."""

    def __init__(
        self,
        config: AppConfig,
        nombre: str = "broker local",
        host: str | None = None,
        port: int | None = None,
        usuario: str | None = None,
        contrasena: str | None = None,
        suscribir_todo: bool = True,
        incluir_txt: bool = True,
    ) -> None:
        """Crea el cliente sin conectarse todavía.

        `nombre` solo etiqueta los avisos de UI (jamás incluye secretos).
        `host`/`port` opcionales para un broker dedicado; si se omiten se
        usan los de la configuración central.
        `usuario`/`contrasena` son opcionales (broker dedicado con auth).
        Con `suscribir_todo=False` solo se suscribe el estado del TXT.
        Con `incluir_txt=False` el cliente principal no toca el estado del
        TXT (lo atiende el cliente dedicado y se evita el doble manejo).
        """
        self.config = config
        self.nombre = nombre
        self.host = host or config.mqtt_host
        self.port = port or config.mqtt_port
        self.suscribir_todo = suscribir_todo
        self.incluir_txt = incluir_txt
        self.senales = SenalesMQTT()
        self._cliente = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        if usuario:
            # La contraseña nunca se registra en logs ni mensajes.
            self._cliente.username_pw_set(usuario, contrasena)
        # Reconexión automática con espera creciente, sin bucles bloqueantes.
        self._cliente.reconnect_delay_set(min_delay=1, max_delay=30)
        self._cliente.on_connect = self._al_conectar
        self._cliente.on_message = self._al_recibir
        self._cliente.on_disconnect = self._al_desconectar
        self._en_marcha = False

    def iniciar(self) -> None:
        """Conecta de forma asíncrona e inicia el hilo de red.

        No bloquea a quien llama. Si el broker no está disponible,
        Paho reintenta en segundo plano.
        """
        try:
            self._cliente.connect_async(self.host, self.port, keepalive=30)
        except Exception as exc:  # p. ej. host inválido en la configuración
            self.senales.broker_error.emit(
                f"No se pudo iniciar MQTT hacia {self.nombre}: {exc}"
            )
            return
        self._cliente.loop_start()
        self._en_marcha = True

    def detener(self) -> None:
        """Desconecta limpiamente y detiene el hilo de red."""
        if not self._en_marcha:
            return
        self._en_marcha = False
        try:
            self._cliente.disconnect()
        except Exception:
            pass
        try:
            self._cliente.loop_stop()
        except Exception:
            pass

    def publicar_velocidad(self, valor: int) -> None:
        """Publica un valor de velocidad en el topic de comando del TXT.

        No usa retención. Si el cliente no está en marcha, no publica nada.
        """
        if not self._en_marcha:
            return
        payload = str(int(valor))
        self._cliente.publish(
            self.config.topic_velocidad_txt, payload, qos=0, retain=False
        )

    def publicar_boton(self, token: str) -> None:
        """Publica un evento de botón (p. ej. PELOTA) en agrotech/botones.

        No usa retención. Si el cliente no está en marcha, no publica nada.
        """
        if not self._en_marcha:
            return
        self._cliente.publish(
            self.config.topic_botones, str(token), qos=0, retain=False
        )

    # -- Callbacks de Paho (corren en el hilo de red) --

    def _al_conectar(self, cliente, userdata, flags, reason_code, properties) -> None:
        """Suscribe los topics de lectura al establecer conexión."""
        codigo = getattr(reason_code, "value", reason_code)
        if codigo != 0:
            self.senales.broker_error.emit(
                f"{self.nombre} rechazó la conexión (código {codigo})."
            )
            return
        if self.suscribir_todo:
            temas = [
                (self.config.topic_sensores, 0),
                (self.config.topic_estado_gateway, 0),
                (self.config.topic_botones, 0),
            ]
            if self.incluir_txt:
                temas.append((self.config.topic_estado_txt, 0))
            temas.append((self.config.topic_ack_velocidad, 0))
            temas.append((self.config.topic_camara_txt, 0))
            cliente.subscribe(temas)
        else:
            cliente.subscribe([(self.config.topic_estado_txt, 0)])
        self.senales.broker_conectado.emit(
            f"Conectado al {self.nombre} {self.host}:"
            f"{self.port} · esperando lecturas"
        )

    def _al_recibir(self, cliente, userdata, mensaje) -> None:
        """Clasifica cada mensaje por topic; el estado nunca pasa por el parser."""
        # La cámara envía bytes JPEG binarios: no intentar decodificar UTF-8.
        if mensaje.topic == self.config.topic_camara_txt:
            self.senales.camara_recibida.emit(mensaje.payload)
            return
        try:
            texto = mensaje.payload.decode("utf-8", errors="strict").strip()
        except (UnicodeDecodeError, ValueError):
            self.senales.mensaje_rechazado.emit("Payload no es texto UTF-8 válido.")
            return
        if mensaje.topic == self.config.topic_sensores:
            valido, datos = validar_sensores(texto)
            if valido:
                self.senales.lectura_valida.emit(datos)
            else:
                self.senales.mensaje_rechazado.emit(
                    datos.get("motivo", "Lectura inválida.")
                )
        elif mensaje.topic == self.config.topic_estado_gateway:
            estado = texto.upper()
            if estado == "ONLINE":
                self.senales.gateway_conectado.emit(True)
            elif estado == "OFFLINE":
                self.senales.gateway_conectado.emit(False)
            else:
                self.senales.mensaje_rechazado.emit(
                    f"Estado de gateway no reconocido: {texto or '(vacío)'}."
                )
        elif mensaje.topic == self.config.topic_botones:
            valido, resultado = validar_boton(texto)
            if valido:
                # PELOTA es una acción discreta; se informa aparte para la
                # actividad, sin publicar nada ni confirmar el servo.
                if resultado == "PELOTA":
                    self.senales.pelota_evento.emit()
                else:
                    self.senales.boton_evento.emit(resultado)
            else:
                self.senales.mensaje_rechazado.emit(
                    resultado.get("motivo", "Evento de botón inválido.")
                )
        elif mensaje.topic == self.config.topic_estado_txt:
            # Solo ONLINE marca al TXT como conectado. No se acepta OFFLINE
            # ni se finge estado: sin heartbeat, la app lo vence por timeout.
            if texto.upper() == "ONLINE":
                self.senales.txt_online.emit()
            else:
                self.senales.mensaje_rechazado.emit(
                    f"Estado de TXT no reconocido: {texto or '(vacío)'}."
                )
        elif mensaje.topic == self.config.topic_ack_velocidad:
            valido, valor = validar_velocidad(texto)
            if valido:
                self.senales.velocidad_confirmada.emit(valor)
            else:
                self.senales.mensaje_rechazado.emit(
                    f"Confirmación de velocidad inválida: {valor.get('motivo', texto)}."
                )
        # Cualquier otro topic se ignora: jamás se tocan comandos/ack.

    def _al_desconectar(self, cliente, userdata, *args) -> None:
        """Avisa la pérdida de conexión (la reconexión la gestiona Paho)."""
        if self._en_marcha:
            self.senales.broker_desconectado.emit(
                f"Conexión con el {self.nombre} perdida · reintentando"
            )
