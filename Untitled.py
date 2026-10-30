#
# Heartbeat del TXT: publica ONLINE en agrotech/estado/txt cada 15 segundos.
# No se suscribe a topics, no publica ordenes ni comandos y no usa motores.
# Lee data/broker_privado.json (formato INI, seccion [broker] con host, port,
# user y password). Nunca se imprimen credenciales.
#
# Archivo autocontenido para ROBO Pro Coding: no importa nada de lib/.
# Compatible con interpretes Python 3 antiguos (sin f-strings, sin pathlib
# y sin anotaciones de tipo). Pulsa el boton de ejecutar para iniciarlo.

import configparser
import os
import sys
import time

try:
    import paho.mqtt.client as mqtt
except ImportError:
    print("Paho no disponible en este TXT; no se instala nada desde aqui.")
    sys.exit(2)

TOPIC_ESTADO_TXT = "agrotech/estado/txt"
PAYLOAD_ONLINE = "ONLINE"
HEARTBEAT_SEG = 15


def ruta_config():
    base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "data", "broker_privado.json")


def leer_config():
    ruta = ruta_config()
    if not os.path.exists(ruta):
        print("Falta {ruta}. No se muestran credenciales.".format(ruta=ruta))
        sys.exit(2)
    ini = configparser.ConfigParser()
    ini.read(ruta, encoding="utf-8")
    return {
        "host": ini.get("broker", "host", fallback=""),
        "port": ini.getint("broker", "port", fallback=1883),
        "user": ini.get("broker", "user", fallback=""),
        "password": ini.get("broker", "password", fallback=""),
    }


def conectar(cfg):
    cliente = mqtt.Client()
    if cfg["user"]:
        cliente.username_pw_set(cfg["user"], cfg["password"] or None)
    cliente.connect(cfg["host"], cfg["port"], keepalive=30)
    cliente.loop_start()
    return cliente


def cerrar(cliente):
    try:
        cliente.disconnect()
    except Exception:
        pass
    try:
        cliente.loop_stop()
    except Exception:
        pass


def main():
    cfg = leer_config()
    if not cfg["host"] or "TU_" in cfg["host"]:
        print("data/broker_privado.json sin completar (host pendiente).")
        return 2
    try:
        while True:
            cliente = None
            try:
                cliente = conectar(cfg)
                print(
                    "Conectado a {host}:{port}. Publicando ONLINE cada 15 s.".format(
                        host=cfg["host"], port=cfg["port"]
                    )
                )
                while True:
                    info = cliente.publish(TOPIC_ESTADO_TXT, PAYLOAD_ONLINE, qos=1)
                    if getattr(info, "rc", 0) != 0:
                        raise RuntimeError("publish rc={rc}".format(rc=info.rc))
                    time.sleep(HEARTBEAT_SEG)
            except KeyboardInterrupt:
                break
            except Exception as exc:
                print(
                    "Error de conexion con {host}:{port} ({exc}). "
                    "Reintento en {seg} s.".format(
                        host=cfg["host"],
                        port=cfg["port"],
                        exc=exc,
                        seg=HEARTBEAT_SEG,
                    )
                )
                time.sleep(HEARTBEAT_SEG)
            finally:
                if cliente is not None:
                    cerrar(cliente)
    except KeyboardInterrupt:
        pass
    return 0


main()
