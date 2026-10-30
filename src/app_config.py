"""Configuración local de la aplicación (Fase 1).

Lee config.example.ini o un config.ini local si existe.
No establece ninguna conexión de red. Si no hay archivo,
devuelve valores por defecto seguros equivalentes al ejemplo.
"""

from __future__ import annotations

import configparser
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class AppConfig:
    """Valores de configuración en memoria, sin secretos."""

    mqtt_host: str = "127.0.0.1"
    mqtt_port: int = 1883
    # Usuario/clave opcionales del broker principal (broker LAN con auth).
    # Reales solo en config.ini privado; vacíos = anónimo (desarrollo).
    mqtt_user: str = ""
    mqtt_password: str = ""
    topic_sensores: str = "agrotech/sensores"
    topic_estado_gateway: str = "agrotech/estado/gateway"
    topic_comandos_txt: str = "agrotech/comandos/txt"
    topic_estado_txt: str = "agrotech/estado/txt"
    topic_ack_txt: str = "agrotech/ack/txt"
    topic_botones: str = "agrotech/botones"
    topic_velocidad_txt: str = "agrotech/robot/velocidad/set"
    topic_ack_velocidad: str = "agrotech/ack/velocidad"
    topic_camara_txt: str = "agrotech/camara/txt"
    umbral_temp_alta: float = 35.0
    umbral_hum_baja: float = 20.0
    umbral_presion_baja: float = 950.0
    umbral_gas_alto: float = 500.0
    # Segundos sin ONLINE del TXT para volver a Desconectado.
    timeout_txt_seg: int = 45
    # Broker dedicado para el TXT (Fase 5B). Vacío = sin segundo cliente.
    # Host/usuario/contraseña reales solo viven en config.ini privado.
    txt_broker_host: str = ""
    txt_broker_port: int = 1884
    txt_broker_user: str = ""
    txt_broker_password: str = ""


def load_config(ruta: str | Path | None = None) -> AppConfig:
    """Carga la configuración desde un .ini o usa los valores por defecto.

    No requiere que el archivo exista. Nunca abre conexiones.
    """
    config = AppConfig()
    if ruta is None:
        # Por defecto se busca config.ini junto a la raíz; si no existe,
        # se usan los valores de ejemplo.
        candidata = Path(__file__).resolve().parent.parent / "config.ini"
        ejemplo = Path(__file__).resolve().parent.parent / "config.example.ini"
        ruta = candidata if candidata.exists() else (ejemplo if ejemplo.exists() else None)
    if ruta is None:
        return config
    parser = configparser.ConfigParser()
    try:
        parser.read(ruta, encoding="utf-8")
    except (configparser.Error, OSError):
        return config
    if parser.has_section("mqtt"):
        config.mqtt_host = parser.get("mqtt", "host", fallback=config.mqtt_host)
        config.mqtt_port = parser.getint("mqtt", "port", fallback=config.mqtt_port)
        # Claves privadas (config.ini, excluido de versiones). Jamás en logs.
        config.mqtt_user = parser.get("mqtt", "user", fallback=config.mqtt_user)
        config.mqtt_password = parser.get(
            "mqtt", "password", fallback=config.mqtt_password
        )
    if parser.has_section("topics"):
        config.topic_sensores = parser.get("topics", "sensores", fallback=config.topic_sensores)
        config.topic_estado_gateway = parser.get(
            "topics", "estado_gateway", fallback=config.topic_estado_gateway
        )
        config.topic_comandos_txt = parser.get(
            "topics", "comandos_txt", fallback=config.topic_comandos_txt
        )
        config.topic_estado_txt = parser.get(
            "topics", "estado_txt", fallback=config.topic_estado_txt
        )
        config.topic_ack_txt = parser.get("topics", "ack_txt", fallback=config.topic_ack_txt)
        config.topic_botones = parser.get(
            "topics", "botones", fallback=config.topic_botones
        )
        config.topic_velocidad_txt = parser.get(
            "topics", "velocidad_txt", fallback=config.topic_velocidad_txt
        )
        config.topic_ack_velocidad = parser.get(
            "topics", "ack_velocidad", fallback=config.topic_ack_velocidad
        )
        config.topic_camara_txt = parser.get(
            "topics", "camara_txt", fallback=config.topic_camara_txt
        )
    if parser.has_section("umbrales"):
        config.umbral_temp_alta = parser.getfloat(
            "umbrales", "temp_alta", fallback=config.umbral_temp_alta
        )
        config.umbral_hum_baja = parser.getfloat(
            "umbrales", "hum_baja", fallback=config.umbral_hum_baja
        )
        config.umbral_presion_baja = parser.getfloat(
            "umbrales", "presion_baja", fallback=config.umbral_presion_baja
        )
        config.umbral_gas_alto = parser.getfloat(
            "umbrales", "gas_alto", fallback=config.umbral_gas_alto
        )
    if parser.has_section("tiempos"):
        config.timeout_txt_seg = parser.getint(
            "tiempos", "timeout_txt", fallback=config.timeout_txt_seg
        )
    if parser.has_section("broker_txt"):
        # Sección privada (config.ini, excluido de versiones). Jamás se
        # registra su contenido en logs.
        config.txt_broker_host = parser.get(
            "broker_txt", "host", fallback=config.txt_broker_host
        )
        config.txt_broker_port = parser.getint(
            "broker_txt", "port", fallback=config.txt_broker_port
        )
        config.txt_broker_user = parser.get(
            "broker_txt", "user", fallback=config.txt_broker_user
        )
        config.txt_broker_password = parser.get(
            "broker_txt", "password", fallback=config.txt_broker_password
        )
    return config
