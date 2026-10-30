# Guía ROBO Pro Coding — cliente de estado en el TXT 4.0

Este documento explica cómo llevar el programa al TXT 4.0, en qué carpeta
copiar los archivos, cómo ejecutarlo y qué mensajes deberían aparecer.

## Compatibilidad del código con el TXT

Los scripts de `txt/` están escritos para ser compatibles con intérpretes
Python antiguos (sin f-strings, sin `pathlib` y sin anotaciones de tipo),
tal como ejecuta el TXT. No instalar paquetes ni modificar el firmware del TXT.

## Qué copiar al TXT

Usar el flujo oficial de transferencia confirmado por el usuario (servidor web
del TXT o USB, según su documentación). No se subió ni ejecutó nada remotamente
porque no hay un método confirmado en este repositorio.

Copiar al TXT, en una misma carpeta (por ejemplo la raíz del usuario o la
carpeta de scripts del TXT):

- `txt/txt_estado.py`
- `txt/controlador_motores.py` (copia idéntica a `lib/controlador_motores.py`)
- `txt/servo.py` (copia idéntica a `lib/servo.py`)
- `txt/broker_privado.example.ini` → copiar como `broker_privado.ini` junto al script

**No copiar nunca al TXT:** contraseñas reales, claves privadas, ni archivos
con secretos del PC. `broker_privado.ini` se completa solo en el TXT y nunca
vuelve al repositorio.

## Configuración en el TXT

Copiar `broker_privado.example.ini` como `broker_privado.ini` junto al script y
completar con el broker de la PC:

```ini
[broker]
host = IP_DEL_PC_BROKER      ; IP actual del PC que hospeda Mosquitto
port = 1884
user = agrotech_txt
password = (contraseña creada con mosquitto_passwd)
```

Opcional, bajo `[servo]`: `espera_pelota_ms = 300` (pausa entre pasos del servo;
por defecto 300 ms).
Opcional, bajo `[motores]`: `velocidad_inicial = 280` (velocidad PWM inicial).

El formato del archivo es INI aunque termine en `.json`. Las credenciales se
guardan en texto claro; por eso el archivo es privado y permanece solo en el TXT.

## Cómo ejecutar en el TXT

1. Verificar que el Python del TXT tiene Paho (sin instalar nada desde este
   repositorio):

   ```powershell
   python3 -c "import paho.mqtt.client; print('Paho OK')"
   ```

   Si falla, Paho no está verificado en ese TXT; el script mantiene solo el
   heartbeat sin mover motores e informa la falta.

2. Ejecutar:

   ```powershell
   python3 txt_estado.py
   ```

3. Para detener: interrumpir el script (Ctrl+C). No publica `OFFLINE`; el
   vencimiento lo detecta la app de la PC por timeout (45 s por defecto).

## Mensajes que deberían aparecer

- `Control de motores listo (velocidad 280, timeout 5 s, espera pelota 300 ms, S1=disponible).`
  (o `S1=no disponible` si no hay servomotor asignado).
- `Conectado a <host>:<port>. Publicando ONLINE cada 15 s.`
- `Conectado. Suscrito a agrotech/botones y agrotech/robot/velocidad/set.`
- `DIAG S1: PELOTA aceptado; estado RECARGADO.` / `DIAG S1: estado DISPARADO.`
- `DIAG velocidad: 0 -> motores detenidos, direccion limpiada`
- `DIAG procesar: ADELANTE -> M1=CW M2=CCW M3=CW M4=CCW velocidad=280`

En la app de la PC debería aparecer `TXT: Conectado` tras el primer `ONLINE`
real y volver a `Desconectado` si pasan 45 s sin heartbeat.

## Límites

- No actualizar firmware, no instalar paquetes, no usar el puerto 3883.
- No guardar API keys ni contraseñas Wi-Fi en ningún archivo.
- La prueba lógica del código no confirma el movimiento físico del servo ni
  del carro; validar en el TXT real antes de la exposición.
