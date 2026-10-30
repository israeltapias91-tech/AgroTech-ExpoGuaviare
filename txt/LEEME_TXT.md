# Cliente de estado en el TXT (Fases 5A/5B) — instrucciones físicas

Este bundle (`txt_estado.py`, `controlador_motores.py`, `servo.py` +
`broker_privado.example.ini`) está preparado pero **no cargado ni
ejecutado en el TXT**. La comunicación real del TXT sigue pendiente.

## Compatibilidad verificada del script (solo código, sin TXT)

`txt_estado.py` usa únicamente APIs presentes tanto en Paho 1.x como en
2.x (`Client()`, `connect`, `loop_start`, `publish`, `disconnect`,
`username_pw_set`), así que vale para la versión que traiga el firmware.
Lo que sigue sin verificarse es si Paho existe en este TXT concreto.

## Qué debe revisar el usuario (sin instalar nada)

1. Si el Python del TXT tiene Paho: en el TXT, ejecutar
   `python3 -c "import paho.mqtt.client; print('Paho OK')"`.
   Si falla, Paho **no** está verificado: no se instala nada desde aquí;
   anote el resultado. Las notas de Fischertechnik sobre Paho en una
   versión previa no sustituyen esta comprobación en su equipo
   (firmware 3.1.10, TXT-API 6.4.2).
2. Qué flujo oficial admite su firmware para copiar archivos al TXT
   (servidor web del equipo o USB, según su documentación). No se subió
   ni ejecutó nada remotamente porque no hay un método confirmado.

## Cómo copiar y ejecutar (cuando lo anterior esté confirmado)

1. Copiar `txt_estado.py`, `controlador_motores.py` y `servo.py` al TXT
   mediante el flujo oficial confirmado.
2. En el TXT, copiar `broker_privado.example.ini` como
   `broker_privado.ini` junto al script y completar host/puerto/usuario/
   contraseña del broker de la PC. Ese archivo privado nunca vuelve al
   repositorio (ver `.gitignore`).
3. Opcionalmente, en `broker_privado.ini` añadir bajo `[servo]` la clave
   `espera_pelota_ms = 300` (pausa de asentamiento del servo entre pasos;
   por defecto 300 ms) y bajo `[motores]` la clave
   `velocidad_inicial = 280` (velocidad PWM inicial del carro).
4. Ejecutar en el TXT: `python3 txt_estado.py`. Debe publicar `ONLINE`
   en `agrotech/estado/txt` al conectar y cada 15 s. La app de la PC lo
   mostrará como `TXT: Conectado`; si se detiene, la PC vuelve a
   `Desconectado` por timeout (45 s por defecto).
5. Para detener: interrumpir el script (Ctrl+C). No publica `OFFLINE`;
   el vencimiento lo detecta la PC.

## Funcionamiento implementado

- **Control de velocidad**: el TXT se suscribe a `agrotech/robot/velocidad/set`.
  Un entero 0..512 fija el PWM de M1..M4. Valor 0 detiene y bloquea el
  rearranque por dirección mantenida; valores >0 en movimiento actualizan
  el PWM conservando la dirección; valores >0 detenidos se guardan para
  el próximo movimiento. Confirmación en `agrotech/ack/velocidad`.
- **Lanzador de pelota (servo S1)**: el TXT se suscribe a `agrotech/botones`
  y procesa el evento `PELOTA` con una máquina de estados:
  - RECARGADO (S1 en 512): al recibir PELOTA mueve S1 a 250, espera,
    luego a 0, espera. Pasa a DISPARADO.
  - DISPARADO: al siguiente PELOTA mueve S1 a 512, espera. Vuelve a
    RECARGADO.
  Los duplicados o eventos mientras S1 se mueve se ignoran. El ciclo se
  ejecuta en un hilo aparte para no bloquear la red MQTT.

## Límites

- No actualizar firmware, no instalar paquetes, no usar el puerto 3883.
- No guardar API keys ni contraseñas Wi-Fi en ningún archivo.
- La prueba lógica del código no confirma el movimiento físico del servo
  ni del carro; validar en el TXT real antes de la exposición.
