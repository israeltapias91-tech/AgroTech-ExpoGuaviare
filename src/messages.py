"""Contrato de mensajes (Fase 1, botones en fase gateway).

Validación pura del CSV de sensores y de eventos de botones, sin red
ni dependencias MQTT.
Formato sensores: T,H,P,G,A_TH,A_PG (exactamente seis campos, intacto).
Formato botones: un token en agrotech/botones (topic independiente).
"""

from __future__ import annotations

import math

# Topics (solo constantes; la suscripción vive en mqtt_client).
TOPICS = {
    "sensores": "agrotech/sensores",
    "estado_gateway": "agrotech/estado/gateway",
    "botones": "agrotech/botones",
    "comandos_txt": "agrotech/comandos/txt",
    "estado_txt": "agrotech/estado/txt",
    "ack_txt": "agrotech/ack/txt",
    "velocidad_txt": "agrotech/robot/velocidad/set",
    "ack_velocidad": "agrotech/ack/velocidad",
}

# Rangos amplios de validación.
RANGO_TEMP = (-40.0, 80.0)
RANGO_HUM = (0.0, 100.0)
RANGO_PRESION = (300.0, 1100.0)
RANGO_GAS = (0.0, 2000.0)

ESTADOS_VALIDOS = ("ONLINE", "OFFLINE")

# Eventos de botones del gateway (topic independiente, sin retención:
# el publicador debe enviar retained=false y la app neutraliza por timeout).
BOTONES_VALIDOS = (
    "ADELANTE", "ATRAS", "IZQUIERDA", "DERECHA", "LIBERADO", "PELOTA"
)
TEXTO_BOTON_NEUTRAL = "Neutral"

# Rango de velocidad del TXT 4.0: 0..512 (PWM).
VELOCIDAD_MINIMA = 0
VELOCIDAD_MAXIMA = 512


def validar_velocidad(payload: str) -> tuple[bool, int | dict]:
    """Valida un valor de velocidad para el TXT.

    Devuelve (True, valor_entero) o (False, {"motivo": ...}).
    """
    texto = payload.strip()
    if texto == "":
        return False, {"motivo": "Velocidad vacía."}
    try:
        valor = int(texto)
    except ValueError:
        return False, {"motivo": f"Velocidad no entera: {texto!r}."}
    if not VELOCIDAD_MINIMA <= valor <= VELOCIDAD_MAXIMA:
        return False, {
            "motivo": f"Velocidad {valor} fuera de rango {VELOCIDAD_MINIMA} a {VELOCIDAD_MAXIMA}."
        }
    return True, valor


def es_estado(payload: str) -> bool:
    """Indica si el payload es un estado (ONLINE/OFFLINE), no una medición."""
    return payload.strip().upper() in ESTADOS_VALIDOS


def _a_numero(texto: str) -> float | None:
    """Convierte a float finito; devuelve None si no es válido."""
    try:
        valor = float(texto)
    except ValueError:
        return None
    if not math.isfinite(valor):
        return None
    return valor


def validar_sensores(payload: str) -> tuple[bool, dict]:
    """Valida un payload CSV de sensores.

    Devuelve (True, datos_normalizados) o (False, {"motivo": ...}).
    Acepta espacios alrededor de los campos. Rechaza vacíos, no
    numéricos, NaN/infinitos, campos faltantes o adicionales.

    Marcador fallback DHT: P=0,G=0,A_PG=1 significa presión y gas
    sin dato (no una medición de cero). En ese caso se devuelven
    presion=None y gas=None con banderas *_no_disponible.
    """
    texto = payload.strip()
    if es_estado(texto):
        return False, {"motivo": "ONLINE/OFFLINE es un estado, no una medición ambiental."}
    partes = texto.split(",")
    if len(partes) != 6:
        return False, {"motivo": f"Se esperaban 6 campos T,H,P,G,A_TH,A_PG; llegaron {len(partes)}."}
    campos = [p.strip() for p in partes]
    for i, campo in enumerate(campos):
        if campo == "":
            return False, {"motivo": f"Campo {i + 1} vacío."}
    t = _a_numero(campos[0])
    h = _a_numero(campos[1])
    p = _a_numero(campos[2])
    g = _a_numero(campos[3])
    if t is None:
        return False, {"motivo": "Temperatura no numérica o no finita."}
    if h is None:
        return False, {"motivo": "Humedad no numérica o no finita."}
    if p is None:
        return False, {"motivo": "Presión no numérica o no finita."}
    if g is None:
        return False, {"motivo": "Gas no numérico o no finito."}
    # A_TH y A_PG deben ser 0 o 1 enteros.
    if campos[4] not in ("0", "1"):
        return False, {"motivo": "A_TH debe ser 0 o 1."}
    if campos[5] not in ("0", "1"):
        return False, {"motivo": "A_PG debe ser 0 o 1."}
    a_th = int(campos[4])
    a_pg = int(campos[5])
    if not RANGO_TEMP[0] <= t <= RANGO_TEMP[1]:
        return False, {"motivo": f"Temperatura {t} fuera de rango -40 a 80 °C."}
    if not RANGO_HUM[0] <= h <= RANGO_HUM[1]:
        return False, {"motivo": f"Humedad {h} fuera de rango 0 a 100 %."}
    # El marcador DHT (P=0,G=0,A_PG=1) se acepta pero como no disponible.
    es_fallback_dht = (p == 0 and g == 0 and a_pg == 1)
    if es_fallback_dht:
        return True, {
            "temperatura": t,
            "humedad": h,
            "presion": None,
            "gas": None,
            "a_th": a_th,
            "a_pg": a_pg,
            "presion_no_disponible": True,
            "gas_no_disponible": True,
        }
    if not RANGO_PRESION[0] <= p <= RANGO_PRESION[1]:
        return False, {"motivo": f"Presión {p} fuera de rango 300 a 1100 hPa."}
    if not RANGO_GAS[0] <= g <= RANGO_GAS[1]:
        return False, {"motivo": f"Gas {g} fuera de rango 0 a 2000 kΩ."}
    return True, {
        "temperatura": t,
        "humedad": h,
        "presion": p,
        "gas": g,
        "a_th": a_th,
        "a_pg": a_pg,
        "presion_no_disponible": False,
        "gas_no_disponible": False,
    }


def validar_boton(payload: str) -> tuple[bool, dict | str]:
    """Valida un evento de botón del gateway.

    Devuelve (True, token) con el token en mayúsculas, o
    (False, {"motivo": ...}). Solo acepta los tokens definidos;
    lo demás se rechaza con motivo legible sin tocar el último evento.
    """
    token = payload.strip().upper()
    if token in BOTONES_VALIDOS:
        return True, token
    return False, {"motivo": f"Botón no reconocido: {payload.strip() or '(vacío)'}. Se esperaba uno de {', '.join(BOTONES_VALIDOS)}."}
