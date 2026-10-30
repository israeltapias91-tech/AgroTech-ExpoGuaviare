"""Control del servomotor S1 del mecanismo de pelota (AgroTech).

Adaptado del modulo `lib/servo` del ejemplo RoboMission_motor_servo:
- No importa `lib.controller` ni crea el servomotor. La instancia la crea
  `AdaptadorMotoresTXT` con el mismo controlador y la misma fabrica que
  usa para M1..M4, y se entrega con `configurar_servomotor`.
- Calibracion de AgroTech: disparo = 0, preparado = 250, recarga = 512.
- `servo_move_wait` conserva su firma y actualiza `s1_pos` con el valor
  realmente aplicado, recortado a [s1_min, s1_max]. Si la solicitud queda
  fuera del rango, lo informa en lugar de recortar en silencio.

Este modulo no inicializa `fischertechnik.factories`.
"""

import threading
import time

TXT_M_S1_servomotor = None

S1_MIN = 0
S1_DISPARO = 0
S1_PREPARADO = 250
S1_RECARGA = 512
S1_MAX = 512

s1_min = S1_MIN
s1_pos = S1_RECARGA
s1_max = S1_MAX
s1_step = 1
s1_home = S1_RECARGA

_candado = threading.Lock()


def configurar_servomotor(
    servomotor, minimo=S1_MIN, maximo=S1_MAX, home=S1_RECARGA, paso=1
):
    """Asocia el S1 ya creado y fija la calibracion de AgroTech."""
    global TXT_M_S1_servomotor, s1_min, s1_pos, s1_max, s1_step, s1_home
    if servomotor is None:
        raise RuntimeError(
            "S1 no creado; asigne S1 en Controller Configuration."
        )
    minimo = int(minimo)
    maximo = int(maximo)
    if maximo <= minimo:
        raise ValueError("Rango de S1 invalido: maximo debe ser mayor que minimo.")
    home = int(min(maximo, max(minimo, int(home))))
    paso = max(1, abs(int(paso)))
    with _candado:
        TXT_M_S1_servomotor = servomotor
        s1_min = minimo
        s1_max = maximo
        s1_home = home
        s1_step = paso
        TXT_M_S1_servomotor.set_position(home)
        s1_pos = home


def init_calib_servo(
    servomotor=None, minimo=S1_MIN, maximo=S1_MAX, home=S1_RECARGA, paso=1
):
    """Calibra S1. Sin argumentos usa 0/512 y el servo ya asociado."""
    if servomotor is None:
        servomotor = TXT_M_S1_servomotor
    configurar_servomotor(servomotor, minimo, maximo, home, paso)


def get_s1_pos():
    with _candado:
        return s1_pos


def servo(pos):
    servo_move_wait(pos)


def servo_up():
    servo_move_wait(s1_min)


def servo_down():
    servo_move_wait(s1_max)


def upRange(start, stop, step):
    while start <= stop:
        yield start
        start += abs(step)


def downRange(start, stop, step):
    while start >= stop:
        yield start
        start -= abs(step)


def servo_move_wait(s1_pos_target):
    global s1_pos
    with _candado:
        if TXT_M_S1_servomotor is None:
            raise RuntimeError(
                "S1 no disponible; asigne S1 en Controller Configuration."
            )
        solicitado = int(round(s1_pos_target))
        objetivo = int(min(max(solicitado, s1_min), s1_max))
        if objetivo != solicitado:
            print(
                "  servo_move_wait: solicitud {} fuera de rango [{}, {}]; "
                "se aplica {}".format(
                    solicitado, s1_min, s1_max, objetivo
                )
            )
        print(
            "  servo_move_wait target:{} from pos:{}".format(objetivo, s1_pos)
        )
        if s1_pos != objetivo:
            if s1_pos <= objetivo:
                recorrido = upRange(s1_pos, objetivo, s1_step)
            else:
                recorrido = downRange(s1_pos, objetivo, s1_step)
            for i in recorrido:
                TXT_M_S1_servomotor.set_position(
                    int(min(max(i, s1_min), s1_max))
                )
                time.sleep(0.001)
        TXT_M_S1_servomotor.set_position(objetivo)
        s1_pos = objetivo
