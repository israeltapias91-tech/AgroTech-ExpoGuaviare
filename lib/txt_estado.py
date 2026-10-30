"""Servicio del TXT 4.0: heartbeat ONLINE y control de motores por botones.

Publica ONLINE en `agrotech/estado/txt` cada 15 s (heartbeat existente) y
se suscribe solo a `agrotech/botones`, el topic real del gateway. Aplica
las ordenes ADELANTE/ATRAS/IZQUIERDA/DERECHA a los cuatro motores y los
detiene con LIBERADO, un mensaje invalido, la perdida de conexion o el
timeout sin ordenes nuevas. No publica ordenes MQTT.

Estructura del proyecto (ROBO Pro Coding):
- Este script vive en `lib/txt_estado.py`.
- El controlador vive en `lib/controlador_motores.py`.
- La configuracion vive en `data/broker_privado.json` (formato INI, aunque
  la extension sea .json), con la seccion [broker] y host, port, user,
  password. Es privado y nunca se muestra ni se registra su contenido.
- El servomotor S1 vive en `lib/servo.py` y usa la misma instancia de
  `fischertechnik.factories` que M1..M4. `PELOTA` alterna RECARGADO
  (250 -> 0) y DISPARADO (512). La seccion opcional [servo] con
  `espera_pelota_ms = 300` ajusta la pausa de asentamiento; si no
  existe, se usan 300 ms.

API de motores: ROBO Pro Coding (`fischertechnik.factories` y
`fischertechnik.controller.Motor`), verificada en ejemplos oficiales.
No se usa ftrobopy. No se usa `ft_robot` porque su API de motores no
esta documentada de forma verificable.

Requisito en el TXT: interprete Python con Paho (`paho.mqtt.client`) y la
API de ROBO Pro Coding. Si Paho o la API de motores no estan disponibles,
el script lo informa y mantiene el heartbeat sin mover motores; no
instala paquetes.
"""

import configparser
import sys
from pathlib import Path

try:
    from controlador_motores import ejecutar
except ImportError:
    from lib.controlador_motores import ejecutar


def ruta_config() -> Path:
    """Ubica data/broker_privado.json relativo a la raiz del proyecto."""
    return Path(__file__).resolve().parent.parent / "data" / "broker_privado.json"


def leer_config() -> dict:
    """Lee data/broker_privado.json (formato INI). La contrasena no se expone."""
    ruta = ruta_config()
    if not ruta.exists():
        print(
            "Falta {ruta}. Créelo con la sección [broker] (host, port, user, "
            "password); no se muestran credenciales.".format(ruta=ruta)
        )
        sys.exit(2)
    ini = configparser.ConfigParser()
    ini.read(str(ruta), encoding="utf-8")
    try:
        espera_ms = ini.getint("servo", "espera_pelota_ms", fallback=300)
    except ValueError:
        espera_ms = 300
    return {
        "host": ini.get("broker", "host", fallback=""),
        "port": ini.getint("broker", "port", fallback=1883),
        "user": ini.get("broker", "user", fallback=""),
        "password": ini.get("broker", "password", fallback=""),
        "espera_pelota_seg": max(0, espera_ms) / 1000.0,
    }


def main() -> int:
    """Conecta, publica ONLINE cada 15 s y atiende solo los botones."""
    cfg = leer_config()
    if not cfg["host"] or "TU_" in cfg["host"]:
        print("data/broker_privado.json sin completar (host pendiente).")
        return 2
    return ejecutar(cfg)


if __name__ == "__main__":
    raise SystemExit(main())
