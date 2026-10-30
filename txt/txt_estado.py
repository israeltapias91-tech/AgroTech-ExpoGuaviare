"""Servicio del TXT 4.0: heartbeat ONLINE y control de motores por botones.

Publica ONLINE en `agrotech/estado/txt` cada 15 s (heartbeat existente) y
se suscribe solo a `agrotech/botones`, el topic real del gateway. Aplica
las ordenes ADELANTE/ATRAS/IZQUIERDA/DERECHA a los cuatro motores y los
detiene con LIBERADO, un mensaje invalido, la perdida de conexion o el
timeout sin ordenes nuevas. Procesa PELOTA para alternar el servomotor S1
entre RECARGADO (512) y DISPARADO (250 -> 0). Publica confirmaciones de
velocidad en `agrotech/ack/velocidad`. No publica ordenes MQTT.

Archivos del bundle en el TXT:
- `txt_estado.py`
- `controlador_motores.py` (copia identica a lib/controlador_motores.py)
- `servo.py` (copia identica a lib/servo.py)
- `broker_privado.ini` (privado, con host/port/user/password)

Archivo de configuracion:
- `broker_privado.ini` junto al script. Seccion [broker] con host, port,
  user, password. Seccion opcional [servo] con `espera_pelota_ms`.
  Seccion opcional [motores] con `velocidad_inicial`.

API de motores y servos: ROBO Pro Coding (`fischertechnik.factories` y
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


def leer_config() -> dict:
    """Lee data/broker_privado.json desde la raíz del proyecto.
    El archivo usa formato INI con seccion [broker], aunque su nombre
    termine en .json. No expone credenciales.
    """
    ruta = Path(__file__).resolve().parent.parent / "data" / "broker_privado.json"
    if not ruta.exists():
        print(
            "Falta {ruta}. Verifique que exista data/broker_privado.json "
            "en la raiz del proyecto. No se muestran credenciales.".format(
                ruta=str(ruta)
            )
        )
        sys.exit(2)
    ini = configparser.ConfigParser()
    ini.read(str(ruta), encoding="utf-8")
    try:
        espera_ms = ini.getint("servo", "espera_pelota_ms", fallback=300)
    except ValueError:
        espera_ms = 300
    try:
        velocidad_inicial = ini.getint("motores", "velocidad_inicial", fallback=280)
    except ValueError:
        velocidad_inicial = 280
    return {
        "host": ini.get("broker", "host", fallback=""),
        "port": ini.getint("broker", "port", fallback=1883),
        "user": ini.get("broker", "user", fallback=""),
        "password": ini.get("broker", "password", fallback=""),
        "espera_pelota_seg": max(0, espera_ms) / 1000.0,
        "velocidad_inicial": velocidad_inicial,
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
