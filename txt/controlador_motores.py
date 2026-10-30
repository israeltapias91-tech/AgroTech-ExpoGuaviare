"""Control de M1..M4 y del servomotor S1 del TXT 4.0 por MQTT.

Recibe solo el topic real del protocolo (`agrotech/botones`) y acepta
los tokens de movimiento (`ADELANTE`, `ATRAS`, `IZQUIERDA`, `DERECHA`),
el evento discreto `PELOTA` y el paro de emergencia (`LIBERADO`).
No publica ordenes MQTT: el unico mensaje que emite es el heartbeat
ONLINE en `agrotech/estado/txt` y la confirmacion de velocidad en
`agrotech/ack/velocidad`.

`PELOTA` no se ejecuta dentro del callback de Paho: se encola para un
hilo propio con una maquina de estados. En RECARGADO mueve S1 a 250 y
luego a 0 (DISPARADO); en DISPARADO lo devuelve a 512 (RECARGADO). Asi
la recepcion de ADELANTE/ATRAS/IZQUIERDA/DERECHA/LIBERADO no se bloquea
durante el ciclo del servo.

API de motores y servos verificada en ejemplos oficiales de ROBO Pro Coding:
    import fischertechnik.factories as txt_factory
    from fischertechnik.controller.Motor import Motor
    txt_factory.init()
    txt_factory.init_motor_factory()
    txt_factory.init_servomotor_factory()
    controlador = txt_factory.controller_factory.create_graphical_controller()
    motor = txt_factory.motor_factory.create_encodermotor(controlador, 1)
    txt_factory.initialized()
    motor.set_speed(280, Motor.CW)
    motor.start_sync()
    motor.stop_sync()
    servo = txt_factory.servomotor_factory.create_servomotor(controlador, 1)
    servo.set_position(512)

No se usa ftrobopy (no esta instalado en el TXT). Tampoco se usa la
libreria `ft_robot`: no se encontro documentacion verificable de su API
de motores, asi que no se inventan llamadas.

Seguridad:
- Las credenciales solo se pasan al cliente Paho; nunca se imprimen.
- Los motores quedan en 0 al iniciar, al salir, al recibir LIBERADO,
  ante un mensaje invalido, al perder la conexion o al vencer el timeout.
- PELOTA se procesa fuera del callback MQTT para no bloquear la red.
"""

import threading
import time
import traceback

try:
    import cv2
except ImportError:
    cv2 = None

try:
    from txt import servo as servo_s1
except ImportError:
    import servo as servo_s1

TOPIC_BOTONES = "agrotech/botones"
TOPIC_VELOCIDAD = "agrotech/robot/velocidad/set"
TOPIC_ESTADO_TXT = "agrotech/estado/txt"
TOPIC_ACK_VELOCIDAD = "agrotech/ack/velocidad"
TOPIC_CAMARA = "agrotech/camara/txt"
PAYLOAD_ONLINE = "ONLINE"
HEARTBEAT_SEG = 15
INTERVALO_REVISION_SEG = 0.2

TOKENS_VALIDOS = ("ADELANTE", "ATRAS", "IZQUIERDA", "DERECHA", "LIBERADO", "PELOTA")

# Rango del PWM del TXT 4.0: 0..512. Se usa 280 como velocidad inicial.
VELOCIDAD_INICIAL = 280
VELOCIDAD_MINIMA = 0
VELOCIDAD_MAXIMA = 512

# El nodo repite el boton mantenido cada 2000 ms (REPETIR_BOTON en
# firmware/nodo_esp32_1/nodo_esp32_1.ino). 5 s tolera un evento perdido
# y coincide con el timeout visual documentado en docs/PROTOCOLO.md.
TIMEOUT_ORDEN_SEG = 5.0

# Mecanismo de pelota: S1 dispara en 0 y recarga en 512. El paso 250 -> 0
# es un solo evento; el siguiente evento completa 512 -> RECARGADO.
SERVO_DISPARO = 0
SERVO_PREPARADO = 250
SERVO_RECARGA = 512
ESPERA_PELOTA_SEG = 0.3

# Mapa confirmado fisicamente en ROBO Pro Coding.
MAPA_MOTORES = {
    "ADELANTE": {1: "CW", 2: "CCW", 3: "CW", 4: "CCW"},
    "ATRAS": {1: "CCW", 2: "CW", 3: "CCW", 4: "CW"},
    "IZQUIERDA": {1: "CCW", 2: "CCW", 3: "CCW", 4: "CCW"},
    "DERECHA": {1: "CW", 2: "CW", 3: "CW", 4: "CW"},
}


class MecanismoPelota(object):
    """Maquina de estados de S1, ejecutada fuera del callback de Paho."""

    RECARGADO = "RECARGADO"
    DISPARADO = "DISPARADO"

    def __init__(
        self,
        adaptador,
        espera_seg=ESPERA_PELOTA_SEG,
        recarga=SERVO_RECARGA,
        preparado=SERVO_PREPARADO,
        disparo=SERVO_DISPARO,
    ):
        self._adaptador = adaptador
        self._espera_seg = max(0.0, float(espera_seg))
        self._recarga = int(recarga)
        self._preparado = int(preparado)
        self._disparo = int(disparo)
        self._estado = self.RECARGADO
        self._ocupado = False
        self._candado = threading.Lock()
        self._solicitud = threading.Event()
        self._terminar = threading.Event()
        self._hilo = threading.Thread(target=self._bucle, name="servo-pelota")
        self._hilo.daemon = True
        self._hilo.start()
        print(
            "DIAG S1: estado inicial {}; objetivo {}.".format(
                self._estado, self._recarga
            )
        )

    def estado_actual(self):
        with self._candado:
            return self._estado

    def solicitar(self):
        """Acepta un paso completo; ignora eventos mientras S1 se mueve."""
        with self._candado:
            if self._terminar.is_set():
                print("DIAG S1: PELOTA ignorado; mecanismo cerrando.")
                return False
            if self._ocupado:
                print(
                    "DIAG S1: PELOTA ignorado; ciclo en curso ({}).".format(
                        self._estado
                    )
                )
                return False
            self._ocupado = True
            self._solicitud.set()
            print(
                "DIAG S1: PELOTA aceptado; estado {}.".format(self._estado)
            )
            return True

    def _bucle(self):
        while not self._terminar.is_set():
            if not self._solicitud.wait(0.2):
                continue
            self._solicitud.clear()
            if self._terminar.is_set():
                break
            with self._candado:
                if not self._ocupado:
                    continue
                estado = self._estado
            self._ejecutar_paso(estado)

    def _mover(self, objetivo, accion):
        if self._terminar.is_set():
            return False
        print(
            "DIAG S1: {} -> objetivo {} (desde {}).".format(
                accion, objetivo, self._adaptador.posicion_servo()
                if hasattr(self._adaptador, "posicion_servo") else "?"
            )
        )
        self._adaptador.mover_servo(objetivo)
        if self._espera_seg and self._terminar.wait(self._espera_seg):
            return False
        return not self._terminar.is_set()

    def _ejecutar_paso(self, estado):
        try:
            if estado == self.RECARGADO:
                if not self._mover(self._preparado, "preparando"):
                    return
                if not self._mover(self._disparo, "disparando"):
                    return
                with self._candado:
                    self._estado = self.DISPARADO
                print("DIAG S1: estado DISPARADO.")
            else:
                if not self._mover(self._recarga, "recargando"):
                    return
                with self._candado:
                    self._estado = self.RECARGADO
                print("DIAG S1: estado RECARGADO.")
        except Exception:
            print(
                "DIAG S1: excepcion ejecutando paso desde {}; "
                "el estado no cambia:".format(estado)
            )
            traceback.print_exc()
        finally:
            with self._candado:
                self._ocupado = False

    def cerrar(self):
        """Detiene el hilo del mecanismo; no mueve S1 al cerrar."""
        self._terminar.set()
        self._solicitud.set()
        self._hilo.join(timeout=2.0)
        if self._hilo.is_alive():
            print("DIAG S1: el hilo del mecanismo no termino en 2 s.")


class ControladorMotores(object):
    """Logica pura: valida tokens, aplica el mapa y vigila el timeout."""

    def __init__(
        self,
        adaptador,
        velocidad=VELOCIDAD_INICIAL,
        timeout=TIMEOUT_ORDEN_SEG,
        mecanismo_pelota=None,
    ):
        self._adaptador = adaptador
        self._velocidad = max(VELOCIDAD_MINIMA, min(VELOCIDAD_MAXIMA, int(velocidad)))
        self._direccion_actual = None
        self._timeout = float(timeout)
        self._ultima_orden = 0.0
        self._en_movimiento = False
        self._candado = threading.RLock()
        self._mecanismo_pelota = mecanismo_pelota
        self._controlador_txt = (
            adaptador.controlador if hasattr(adaptador, "controlador") else None
        )
        self.detener()

    @property
    def controlador(self):
        """Devuelve el controlador gráfico TXT existente (compartido con cámara)."""
        return self._controlador_txt

    def establecer_velocidad(self, valor, cliente_mqtt=None, ahora=None):
        """Fija la velocidad PWM (0..512) del TXT.

        - Valor 0: detiene los cuatro motores. Tras detenerse, no arranca
          solo por mensajes repetidos de una dirección mantenida; espera
          una orden de movimiento nueva.
        - Valor 1..512 mientras hay movimiento: actualiza el PWM de los
          cuatro motores conservando la dirección actual.
        - Valor 1..512 mientras está detenido: guarda el valor para el
          próximo movimiento; no arranca los motores por sí solo.

        Publica confirmación en agrotech/ack/velocidad si se pasa cliente_mqtt.
        Devuelve True si el valor es válido; False si no.
        """
        try:
            valor_int = int(valor)
        except (ValueError, TypeError):
            return False
        if not VELOCIDAD_MINIMA <= valor_int <= VELOCIDAD_MAXIMA:
            return False
        with self._candado:
            instante = time.monotonic() if ahora is None else ahora
            self._velocidad = valor_int
            if valor_int == 0:
                # Paro por velocidad 0: detener y bloquear arranque automático.
                self._detener_sin_candado()
                self._direccion_actual = None
                self._ultima_orden = 0.0
                print("DIAG velocidad: 0 -> motores detenidos, direccion limpiada")
            elif self._en_movimiento:
                # En movimiento: actualizar velocidad conservando dirección.
                if self._direccion_actual is not None:
                    mapa = MAPA_MOTORES.get(self._direccion_actual)
                    if mapa is not None:
                        for numero in (1, 2, 3, 4):
                            self._adaptador.mover(
                                numero, self._velocidad, mapa[numero]
                            )
                        self._ultima_orden = instante
                        print(
                            "DIAG velocidad: {v} en movimiento, direccion={d}".format(
                                v=self._velocidad, d=self._direccion_actual
                            )
                        )
            else:
                # Detenido: guardar velocidad para el próximo movimiento.
                # Publicar confirmación para que la app sepa que se aceptó
                # el valor (se aplicará cuando haya una orden de movimiento).
                print(
                    "DIAG velocidad: {v} guardada para próximo movimiento (detenido)".format(
                        v=self._velocidad
                    )
                )
            if cliente_mqtt is not None:
                try:
                    info = cliente_mqtt.publish(
                        TOPIC_ACK_VELOCIDAD, str(self._velocidad), qos=0
                    )
                    print(
                        "DIAG velocidad: confirmación publicada en {t} = {v}".format(
                            t=TOPIC_ACK_VELOCIDAD, v=self._velocidad
                        )
                    )
                except Exception:
                    print("DIAG velocidad: excepcion publicando ack:")
                    traceback.print_exc()
            return True

    def procesar(self, token, ahora=None):
        """Aplica un token. Devuelve True si era valido; False si no.

        Un token invalido detiene los motores y no reemplaza la orden
        anterior. El token debe llegar tal cual lo publica el gateway.
        PELOTA es un evento independiente y no detiene ni cambia la marcha.
        """
        if token is None:
            return self._invalido()
        texto = token.strip()
        with self._candado:
            print("DIAG procesar: token={!r}".format(texto))
            if texto == "LIBERADO":
                print("DIAG procesar: LIBERADO -> detener M1..M4")
                self.detener()
                return True
            if texto == "PELOTA":
                # Evento independiente: no detener ni cambiar la orden de marcha.
                if self._mecanismo_pelota is None:
                    print("Evento PELOTA recibido; S1 no disponible, se ignora.")
                    return True
                aceptado = self._mecanismo_pelota.solicitar()
                if aceptado:
                    print("Evento PELOTA aceptado; paso S1 iniciado.")
                else:
                    print("Evento PELOTA ignorado; S1 ocupado o cerrando.")
                return True
            mapa = MAPA_MOTORES.get(texto)
            if mapa is None:
                print("DIAG procesar: token no valido -> detener M1..M4")
                self._detener_sin_candado()
                return False
            # Si el carro fue detenido por velocidad 0, no arrancar solo
            # por una dirección mantenida. Se espera una orden nueva.
            if self._velocidad == 0:
                print(
                    "DIAG procesar: velocidad en 0, ignorando dirección {!r}".format(
                        texto
                    )
                )
                return True
            print(
                "DIAG procesar: {t} -> M1={m1} M2={m2} M3={m3} M4={m4} "
                "velocidad={v}".format(
                    t=texto,
                    m1=mapa[1],
                    m2=mapa[2],
                    m3=mapa[3],
                    m4=mapa[4],
                    v=self._velocidad,
                )
            )
            for numero in (1, 2, 3, 4):
                self._adaptador.mover(numero, self._velocidad, mapa[numero])
            self._en_movimiento = True
            self._direccion_actual = texto
            self._ultima_orden = time.monotonic() if ahora is None else ahora
            return True

    def verificar_timeout(self, ahora=None):
        """Detiene los motores si vencio el plazo sin una orden nueva."""
        with self._candado:
            if not self._en_movimiento:
                return False
            instante = time.monotonic() if ahora is None else ahora
            if instante - self._ultima_orden > self._timeout:
                self._detener_sin_candado()
                self._direccion_actual = None
                self._ultima_orden = 0.0
                return True
            return False

    def detener(self):
        """Detiene los cuatro motores de forma inmediata e idempotente."""
        with self._candado:
            self._detener_sin_candado()
            self._direccion_actual = None
            self._ultima_orden = 0.0

    def cerrar(self):
        """Deja los motores en 0 y detiene el hilo de S1 antes de terminar."""
        self.detener()
        if self._mecanismo_pelota is not None:
            self._mecanismo_pelota.cerrar()

    def _detener_sin_candado(self):
        self._adaptador.detener_todos()
        self._en_movimiento = False

    def _invalido(self):
        with self._candado:
            self._detener_sin_candado()
        return False


class AdaptadorMotoresTXT(object):
    """Adaptador a la API de ROBO Pro Coding. No se importa al compilar."""

    def __init__(self):
        try:
            import fischertechnik.factories as txt_factory
            from fischertechnik.controller.Motor import Motor
        except ImportError as exc:
            raise RuntimeError(
                "API de motores de ROBO Pro Coding no disponible "
                "(fischertechnik.factories). Ejecute este programa desde "
                "ROBO Pro Coding en el TXT; no se usa ftrobopy."
            ) from exc

        self._Motor = Motor
        self._servo = None

        # Una sola fabrica, un solo controlador para M1..M4, S1 y camara USB.
        txt_factory.init()
        txt_factory.init_motor_factory()
        try:
            txt_factory.init_usb_factory()
        except Exception as exc:
            print(
                "DIAG camara: init_usb_factory no disponible ({!r}); "
                "la camara USB no se podra iniciar.".format(exc)
            )
        try:
            txt_factory.init_camera_factory()
        except Exception as exc:
            print(
                "DIAG camara: init_camera_factory no disponible ({!r}); "
                "la camara USB no se podra iniciar.".format(exc)
            )
        try:
            txt_factory.init_servomotor_factory()
        except Exception as exc:
            print(
                "DIAG S1: init_servomotor_factory no disponible ({!r}); "
                "M1..M4 siguen operativos.".format(exc)
            )

        self._controlador = txt_factory.controller_factory.create_graphical_controller()

        fabrica = txt_factory.motor_factory
        crear = getattr(fabrica, "create_encodermotor", None)
        if crear is None:
            raise RuntimeError(
                "La API de ROBO Pro Coding no expone create_encodermotor; "
                "no se inventan llamadas alternativas."
            )
        self._motores = {}
        for numero in (1, 2, 3, 4):
            print("DIAG M{n}: creando motor para salida M{n}".format(n=numero))
            try:
                self._motores[numero] = crear(self._controlador, numero)
            except Exception:
                print("DIAG M{n}: EXCEPCION creando motor".format(n=numero))
                traceback.print_exc()
                raise
            print(
                "DIAG M{n}: creado para salida M{n}: {obj!r}".format(
                    n=numero, obj=self._motores[numero]
                )
            )

        fabrica_servo = getattr(txt_factory, "servomotor_factory", None)
        crear_servo = getattr(fabrica_servo, "create_servomotor", None)
        if crear_servo is None:
            print(
                "DIAG S1: la API no expone create_servomotor; "
                "M1..M4 siguen operativos sin mecanismo de pelota."
            )
        else:
            try:
                self._servo = crear_servo(self._controlador, 1)
                print("DIAG S1: creado para salida S1: {!r}".format(self._servo))
            except Exception:
                self._servo = None
                print(
                    "DIAG S1: no se pudo crear S1. Asigne S1 en "
                    "Controller Configuration; M1..M4 siguen operativos."
                )
                traceback.print_exc()

        txt_factory.initialized()

        if self._servo is not None:
            try:
                servo_s1.configurar_servomotor(
                    self._servo,
                    minimo=SERVO_DISPARO,
                    maximo=SERVO_RECARGA,
                    home=SERVO_RECARGA,
                )
                print(
                    "DIAG S1: calibrado disparo={} preparado={} recarga={}.".format(
                        SERVO_DISPARO, SERVO_PREPARADO, SERVO_RECARGA
                    )
                )
            except Exception:
                self._servo = None
                print("DIAG S1: no se pudo calibrar; se ignora el mecanismo.")
                traceback.print_exc()

        # Estado inicial seguro: los cuatro motores en 0.
        self.detener_todos()

    @property
    def controlador(self):
        """Devuelve el controlador gráfico TXT existente (compartido con motores, servo y cámara)."""
        return self._controlador

    def mover(self, numero, velocidad, sentido):
        direccion = self._Motor.CW if sentido == "CW" else self._Motor.CCW
        motor = self._motores[numero]
        print(
            "DIAG M{n}: antes set_speed(velocidad={v}, direccion={s})".format(
                n=numero, v=int(velocidad), s=sentido
            )
        )
        try:
            motor.set_speed(int(velocidad), direccion)
        except Exception:
            print("DIAG M{n}: EXCEPCION en set_speed".format(n=numero))
            traceback.print_exc()
            raise
        print("DIAG M{n}: despues set_speed OK".format(n=numero))
        print("DIAG M{n}: antes start_sync()".format(n=numero))
        try:
            motor.start_sync()
        except Exception:
            print("DIAG M{n}: EXCEPCION en start_sync".format(n=numero))
            traceback.print_exc()
            raise
        en_marcha = None
        if hasattr(motor, "is_running"):
            try:
                en_marcha = motor.is_running()
            except Exception:
                print("DIAG M{n}: EXCEPCION en is_running".format(n=numero))
                traceback.print_exc()
        print(
            "DIAG M{n}: despues start_sync OK; is_running()={r}".format(
                n=numero, r=en_marcha
            )
        )

    def detener(self, numero):
        motor = self._motores[numero]
        print("DIAG M{n}: antes stop_sync()".format(n=numero))
        try:
            motor.stop_sync()
        except Exception:
            print("DIAG M{n}: EXCEPCION en stop_sync".format(n=numero))
            traceback.print_exc()
            raise
        print("DIAG M{n}: despues stop_sync OK".format(n=numero))

    def detener_todos(self):
        for numero in (1, 2, 3, 4):
            self.detener(numero)

    def tiene_servo(self):
        return self._servo is not None

    def mover_servo(self, posicion):
        if self._servo is None:
            raise RuntimeError(
                "S1 no disponible; asigne S1 en Controller Configuration."
            )
        try:
            print(
                "DIAG S1: moviendo a posicion {}".format(int(posicion))
            )
            servo_s1.servo_move_wait(int(posicion))
            print(
                "DIAG S1: llegado a posicion {}".format(int(posicion))
            )
        except Exception:
            print(
                "DIAG S1: excepcion moviendo servo a {}:".format(posicion)
            )
            traceback.print_exc()
            raise

    def posicion_servo(self):
        if self._servo is None:
            return None
        return servo_s1.get_s1_pos()


def crear_controlador(velocidad_inicial=VELOCIDAD_INICIAL, espera_pelota_seg=ESPERA_PELOTA_SEG):
    """Crea el controlador con hardware real. Puede lanzar RuntimeError."""
    adaptador = AdaptadorMotoresTXT()
    mecanismo = None
    if adaptador.tiene_servo():
        mecanismo = MecanismoPelota(adaptador, espera_seg=espera_pelota_seg)
    return ControladorMotores(
        adaptador,
        velocidad=velocidad_inicial,
        mecanismo_pelota=mecanismo,
    )


class CameraCapture(object):
    """Captura cuadros JPEG de la cámara USB del TXT y los publica por MQTT.

    Usa el cliente MQTT ya conectado por el programa del TXT; no crea un
    segundo cliente ni cambia el identificador de conexión. Reutiliza el
    controlador gráfico TXT ya existente (el mismo que manejan M1..M4 y S1)
    para crear la cámara en USB1, de modo que no se crea un segundo
    controlador.

    La cámara se inicializa con la API oficial de fischertechnik para ROBO
    Pro Coding:
        txt_factory.init_usb_factory()      (una sola vez, en AdaptadorMotoresTXT)
        txt_factory.init_camera_factory()   (una sola vez, en AdaptadorMotoresTXT)
        camara = txt_factory.usb_factory.create_camera(controlador_existente, 1)
        camara.set_rotate(False)
        camara.set_height(240)
        camara.set_width(320)
        camara.set_fps(15)
        camara.start()

    Los cuadros se capturan con camara.read_frame() y se codifican a JPEG
    con cv2.imencode(".jpeg", frame, [1, 30]). Se publican como bytes
    crudos en agrotech/camara/txt, QoS 0, retain=false, a como maximo 5 FPS.
    La captura corre en un hilo daemon aparte para no bloquear el callback
    MQTT de motores ni el bucle principal del TXT.
    """

    def __init__(self, cliente_mqtt, topic_camara, controlador=None, intervalo_seg=0.067):
        self._cliente = cliente_mqtt
        self._topic = topic_camara
        self._intervalo_seg = max(0.05, float(intervalo_seg))
        self._camara = None
        self._controlador = controlador
        self._hilo = None
        self._terminar = threading.Event()
        self._activo = False
        self._cuadros_enviados = 0
        self._ultimo_envio = 0.0
        self._cuadro_ultimo = None
        self._inicializar_camara()

    def _inicializar_camara(self):
        if cv2 is None:
            print(
                "DIAG cv2: no disponible en este entorno; la camara no se "
                "puede inicializar sin opencv-python."
            )
            return
        try:
            import fischertechnik.factories as txt_factory
        except ImportError:
            print(
                "DIAG camara: fischertechnik.factories no disponible; "
                "la camara permanece inactiva."
            )
            return

        # Las fabricas USB y camara ya se inicializaron en AdaptadorMotoresTXT.
        # Aquí solo creamos la camara USB1 usando el controlador existente.
        try:
            if self._controlador is None:
                print(
                    "DIAG camara: no se proporciono controlador TXT existente; "
                    "no se puede crear la camara USB1 sin un controlador."
                )
                return

            self._camara = txt_factory.usb_factory.create_camera(
                self._controlador, 1
            )
            self._camara.set_rotate(False)
            try:
                self._camara.set_height(720)
                self._camara.set_width(1280)
                self._camara.set_fps(15)
                resolucion = "1280x720"
                fps = 15
            except Exception:
                # Resolucion no compatible: fallback a 640x480.
                self._camara.set_height(480)
                self._camara.set_width(640)
                self._camara.set_fps(15)
                resolucion = "640x480"
                fps = 15
            self._camara.start()
            self._activo = True
            self._hilo = threading.Thread(
                target=self._bucle_camara, name="camara-txt", daemon=True
            )
            self._hilo.start()
            print(
                "DIAG camara: USB1 iniciada ({}, {} FPS configurada, "
                "publicacion limitada a {} FPS en {}).".format(
                    resolucion, fps, int(1 / self._intervalo_seg), self._topic
                )
            )
        except Exception as exc:
            print("DIAG camara: no se pudo iniciar USB1 ({!r})".format(exc))
            traceback.print_exc()
            self._camara = None

    def _bucle_camara(self):
        """Hilo de captura: lee el cuadro mas reciente, lo codifica a JPEG
        y lo publica por MQTT. Los cuadros intermedios se descartan para no
        acumular retraso."""
        while not self._terminar.is_set():
            try:
                if self._camara is None:
                    break
                # Leer el cuadro mas reciente disponible.
                frame = self._camara.read_frame()
                if frame is None:
                    time.sleep(self._intervalo_seg)
                    continue
                self._cuadro_ultimo = frame

                ahora = time.monotonic()
                if ahora - self._ultimo_envio < self._intervalo_seg:
                    time.sleep(self._intervalo_seg)
                    continue
                self._ultimo_envio = ahora

                frame_para_enviar = self._cuadro_ultimo
                ok, jpeg_buf = cv2.imencode(
                    ".jpeg",
                    frame_para_enviar,
                    [int(cv2.IMWRITE_JPEG_QUALITY), 85],
                )
                if not ok:
                    print("DIAG camara: cv2.imencode devolvio False.")
                    continue
                jpeg_bytes = jpeg_buf.tobytes()
                if self._cliente is not None and self._cliente.is_connected():
                    try:
                        self._cliente.publish(
                            self._topic,
                            jpeg_bytes,
                            qos=0,
                            retain=False,
                        )
                        self._cuadros_enviados += 1
                        print(
                            "DIAG camara: cuadro publicado en {} ({} bytes, "
                            "total {})".format(
                                self._topic,
                                len(jpeg_bytes),
                                self._cuadros_enviados,
                            )
                        )
                    except Exception:
                        print(
                            "DIAG camara: excepcion publicando cuadro por "
                            "MQTT:"
                        )
                        traceback.print_exc()
                else:
                    # Broker no conectado: omitir este cuadro y continuar.
                    pass
            except Exception:
                print("DIAG camara: excepcion en bucle de captura:")
                traceback.print_exc()
            time.sleep(self._intervalo_seg)

    def esta_activo(self):
        return self._activo

    def detener(self):
        """Detiene el hilo de captura y, si existe, la camara."""
        self._terminar.set()
        if self._hilo is not None:
            self._hilo.join(timeout=2.0)
        if self._camara is not None and hasattr(self._camara, "stop"):
            try:
                self._camara.stop()
            except Exception:
                print("DIAG camara: excepcion al detener la camara:")
                traceback.print_exc()


def _loop_activo(cliente):
    """DIAG temporal: indica si el hilo interno de Paho sigue vivo."""
    hilo = getattr(cliente, "_thread", None)
    try:
        return bool(hilo is not None and hilo.is_alive())
    except Exception:
        return False


def ejecutar(cfg):
    """Servicio del TXT: heartbeat ONLINE, control por botones y S1.

    cfg contiene host, port, user y password del broker, y opcionalmente
    `velocidad_inicial` y `espera_pelota_seg`. Las credenciales no se
    imprimen en ningun mensaje. Devuelve el codigo de salida.
    """
    try:
        import paho.mqtt.client as mqtt
    except ImportError:
        print(
            "Paho no disponible en este TXT. Verifique segun LEEME_TXT.md "
            "si su firmware lo incluye; no se instala nada desde aqui."
        )
        return 2

    velocidad_inicial = int(cfg.get("velocidad_inicial", VELOCIDAD_INICIAL))
    velocidad_inicial = max(
        VELOCIDAD_MINIMA, min(VELOCIDAD_MAXIMA, velocidad_inicial)
    )

    espera_pelota_seg = cfg.get("espera_pelota_seg", ESPERA_PELOTA_SEG)
    try:
        espera_pelota_seg = max(0.0, float(espera_pelota_seg))
    except (TypeError, ValueError):
        espera_pelota_seg = ESPERA_PELOTA_SEG

    try:
        controlador = crear_controlador(
            velocidad_inicial=velocidad_inicial,
            espera_pelota_seg=espera_pelota_seg,
        )
        s1_estado = (
            "disponible"
            if controlador._mecanismo_pelota is not None
            else "no disponible"
        )
        s1_estado = (
            "disponible"
            if controlador._mecanismo_pelota is not None
            else "no disponible"
        )
        print(
            "Control de motores listo (velocidad {v}, timeout {t} s, "
            "espera pelota {e} ms, S1={s1}).".format(
                v=velocidad_inicial,
                t=TIMEOUT_ORDEN_SEG,
                e=int(round(espera_pelota_seg * 1000)),
                s1=s1_estado,
            )
        )
    except Exception as exc:
        controlador = None
        print(
            "Control de motores no disponible ({exc}). "
            "Se mantiene solo el heartbeat ONLINE; no se movera ningun motor.".format(
                exc=exc
            )
        )
        print("DIAG traceback de inicializacion de motores:")
        traceback.print_exc()

    estado = {"ultimo_hb": 0.0, "cliente": None, "camara": None}

    def publicar_online(cliente):
        info = cliente.publish(TOPIC_ESTADO_TXT, PAYLOAD_ONLINE, qos=1)
        return getattr(info, "rc", 0) == 0

    def al_conectar(cliente, userdata, flags, rc):
        if rc != 0:
            print("Conexion rechazada por el broker (rc={rc}).".format(rc=rc))
            return
        cliente.subscribe(TOPIC_BOTONES, qos=0)
        cliente.subscribe(TOPIC_VELOCIDAD, qos=0)
        # DIAG temporal: confirma que este cliente es el mismo y que su loop vive.
        print(
            "DIAG on_connect: mismo_cliente={mismo} topic={topic!r} "
            "loop_activo={loop} conectado={conectado} on_message={om}".format(
                mismo=(cliente is estado["cliente"]),
                topic=TOPIC_BOTONES,
                loop=_loop_activo(cliente),
                conectado=cliente.is_connected(),
                om=(cliente.on_message is al_recibir),
            )
        )
        estado["ultimo_hb"] = 0.0
        print(
            "Conectado. Suscrito a {t1} y {t2}.".format(
                t1=TOPIC_BOTONES, t2=TOPIC_VELOCIDAD
            )
        )

    def al_desconectar(cliente, userdata, rc):
        if controlador is not None:
            try:
                controlador.detener()
            except Exception:
                print("DIAG excepcion deteniendo motores al desconectar:")
                traceback.print_exc()
        if rc != 0:
            print("Conexion perdida; motores detenidos. Reintentando...")

    def al_recibir(cliente, userdata, mensaje):
        # DIAG temporal: topic y payload decodificado, sin credenciales.
        try:
            texto = mensaje.payload.decode("utf-8")
            payload_diag = repr(texto)
        except (UnicodeDecodeError, AttributeError):
            texto = None
            payload_diag = repr(mensaje.payload)
        print(
            "DIAG callback: mismo_cliente={mismo} topic={topic!r} "
            "payload={payload}".format(
                mismo=(cliente is estado["cliente"]),
                topic=mensaje.topic,
                payload=payload_diag,
            )
        )
        # Manejo de velocidad (topic independiente de botones).
        if mensaje.topic == TOPIC_VELOCIDAD:
            if controlador is None:
                print("DIAG callback: sin controlador de motores; se ignora.")
                return
            if texto is None:
                print("Mensaje de velocidad no decodificable; se ignora.")
                return
            valido = controlador.establecer_velocidad(
                texto, cliente_mqtt=cliente
            )
            if not valido:
                print(
                    "DIAG velocidad: valor invalido {!r}; se ignora.".format(texto)
                )
            return
        if mensaje.topic == TOPIC_BOTONES:
            print(
                "DIAG botones: recibido topic={} payload={!r}".format(
                    mensaje.topic, mensaje.payload
                )
            )
        if mensaje.topic != TOPIC_BOTONES:
            return
        if controlador is None:
            print("DIAG callback: sin controlador de motores; se ignora.")
            return
        if texto is None:
            controlador.detener()
            print("Mensaje de botones no decodificable; motores detenidos.")
            return
        token = texto.strip()
        if token in TOKENS_VALIDOS:
            print("DIAG orden reconocida: {!r}".format(token))
        else:
            print("DIAG orden NO reconocida: {!r}; se detendran motores.".format(token))
        try:
            valido = controlador.procesar(texto)
        except Exception:
            print("DIAG excepcion ejecutando motores:")
            traceback.print_exc()
            try:
                controlador.detener()
            except Exception:
                print("DIAG excepcion deteniendo motores tras el fallo:")
                traceback.print_exc()
            return
        if not valido:
            print("DIAG mensaje invalido; motores detenidos.")

    while True:
        cliente = None
        try:
            cliente = mqtt.Client()
            estado["cliente"] = cliente
            if cfg.get("user"):
                cliente.username_pw_set(cfg["user"], cfg.get("password") or None)
            cliente.on_connect = al_conectar
            cliente.on_disconnect = al_desconectar
            cliente.on_message = al_recibir
            cliente.connect(cfg["host"], cfg["port"], keepalive=30)
            cliente.loop_start()
            # DIAG temporal: callback y loop pertenecen a este mismo cliente.
            print(
                "DIAG Paho: cliente_id={cid} on_message_asignado={om} "
                "on_connect_asignado={oc} loop_activo={loop}".format(
                    cid=id(cliente),
                    om=(cliente.on_message is al_recibir),
                    oc=(cliente.on_connect is al_conectar),
                    loop=_loop_activo(cliente),
                )
            )
            # Iniciar captura de cámara usando el mismo cliente MQTT conectado
            # y el controlador TXT existente (compartido con motores y servo).
            if controlador is not None:
                estado["camara"] = CameraCapture(
                    cliente,
                    TOPIC_CAMARA,
                    controlador=controlador.controlador,
                    intervalo_seg=0.2,
                )
                print(
                    "DIAG cámara: captura iniciada (activa={}).".format(
                        estado["camara"].esta_activo()
                    )
                )
            print(
                "Conectado a {h}:{p}. Publicando ONLINE cada {s} s.".format(
                    h=cfg["host"], p=cfg["port"], s=HEARTBEAT_SEG
                )
            )
            while True:
                if controlador is not None:
                    try:
                        controlador.verificar_timeout()
                    except Exception:
                        print("DIAG excepcion verificando timeout:")
                        traceback.print_exc()
                        raise
                ahora = time.monotonic()
                if ahora - estado["ultimo_hb"] >= HEARTBEAT_SEG:
                    if not publicar_online(cliente):
                        raise ConnectionError("publish rc distinto de 0")
                    estado["ultimo_hb"] = ahora
                time.sleep(INTERVALO_REVISION_SEG)
        except KeyboardInterrupt:
            break
        except Exception as exc:
            # Solo host/puerto en el mensaje: nunca usuario ni contrasena.
            print(
                "Error de conexion con {h}:{p} ({exc}). "
                "Reintento en {s} s.".format(
                    h=cfg["host"], p=cfg["port"], exc=exc, s=HEARTBEAT_SEG
                )
            )
            if controlador is not None:
                controlador.detener()
            time.sleep(HEARTBEAT_SEG)
        finally:
            if controlador is not None:
                try:
                    controlador.detener()
                except Exception:
                    print("DIAG excepcion deteniendo motores al cerrar:")
                    traceback.print_exc()
            if estado["camara"] is not None:
                print("DIAG camara: deteniendo captura.")
                try:
                    estado["camara"].detener()
                except Exception:
                    print(
                        "DIAG camara: excepcion deteniendo captura:"
                    )
                    traceback.print_exc()
                estado["camara"] = None
            if cliente is not None:
                try:
                    cliente.disconnect()
                except Exception:
                    pass
                try:
                    cliente.loop_stop()
                except Exception:
                    pass

    if controlador is not None:
        try:
            controlador.cerrar()
        except Exception:
            print("DIAG excepcion cerrando el controlador:")
            traceback.print_exc()
    return 0
