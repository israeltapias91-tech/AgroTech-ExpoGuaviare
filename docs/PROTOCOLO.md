# Protocolo de mensajes (Fase 1, contrato inicial)

## Topics propuestos

| Topic | Uso |
|---|---|
| `agrotech/sensores` | Mediciones CSV del gateway (6 campos, intacto) |
| `agrotech/estado/gateway` | Estado del gateway (`ONLINE`/`OFFLINE`) |
| `agrotech/botones` | Eventos de botones del gateway (tokens, sin retención) |
| `agrotech/comandos/txt` | Órdenes al TXT (reservado; prohibido publicar) |
| `agrotech/estado/txt` | Estado del TXT (solo `ONLINE` real lo conecta) |
| `agrotech/ack/txt` | Confirmaciones del TXT (reservado) |
| `agrotech/robot/velocidad/set` | Fijar velocidad del TXT (entero 0..512, sin retención) |
| `agrotech/ack/velocidad` | Confirmación de velocidad aplicada por el TXT |
| `agrotech/simulacion/txt` | Simulación futura del TXT (separada; jamás estado real) |

Los mensajes ambientales, el estado de dispositivos y los comandos
del robot se mantienen separados. Si se propone cambiar un topic o
formato, se justifica y se actualizan todos los consumidores.

## Formato CSV de sensores

Seis campos exactos: `T,H,P,G,A_TH,A_PG`.

Ejemplo: `24.5,60.2,1013.1,150,0,1`

- Se aceptan espacios alrededor de los campos y decimales válidos.
- `A_TH` y `A_PG` deben ser `0` o `1`.
- Se rechazan campos vacíos, no numéricos, `NaN`, infinitos,
  campos faltantes o adicionales, con un motivo legible.

## Rangos de validación

- Temperatura: −40 a 80 °C.
- Humedad: 0 a 100 %.
- Presión: 300 a 1100 hPa.
- Gas: 0 a 2000 kΩ.

## Estados

`ONLINE` y `OFFLINE` son estados de dispositivo; nunca se aceptan
como lectura ambiental.

## Marcador DHT sin dato

`P=0,G=0,A_PG=1` significa presión y gas sin dato (fallback DHT),
no una medición de cero. La validación lo acepta y devuelve presión
y gas como no disponibles en el resultado normalizado, sin cambiar
el CSV de seis campos.

## Eventos de botones

Topic independiente `agrotech/botones`, un token por mensaje:
`ADELANTE`, `ATRAS`, `IZQUIERDA`, `DERECHA` o `LIBERADO`
(`LIBERADO` = botón suelto/detener, a prueba de fallos).
El publicador debe enviar sin retención (`retained=false`); la app
muestra la última dirección y vuelve a `Neutral` a los 5 s sin eventos.
Ese timeout es solo visual, no seguridad para movimientos. Cualquier
otro payload se rechaza con motivo y no reemplaza el último evento.

El evento discreto `PELOTA` viaja por el mismo topic desde el pulsador
conectado al ESP32 #1 y desde el botón «Lanzar pelota» de la app. No
representa una dirección ni debe cambiar la dirección mostrada por la
app. El TXT lo acepta como evento independiente y alterna el servomotor
S1 entre RECARGADO (512) y DISPARADO (250 → 0) según la máquina de
estados documentada en `txt/controlador_motores.py`.

## Control de velocidad del TXT

Topic `agrotech/robot/velocidad/set`: el publicador (app de la PC) envía un
entero entre 0 y 512 como payload. No se usa retención (`retained=false`).
El TXT se suscribe a este topic y aplica la velocidad con la API de motores
de ROBO Pro Coding:

- Valor 0: detiene los cuatro motores. Después de detenerse, no arranca
  solo por mensajes repetidos de una dirección mantenida; espera una orden
  de movimiento nueva.
- Valor 1..512 mientras los motores están en movimiento: actualiza el PWM
  de los cuatro motores conservando la dirección actual.
- Valor 1..512 mientras los motores están detenidos: guarda el valor para
  el próximo movimiento; no arranca los motores por sí solo.

Topic `agrotech/ack/velocidad`: el TXT publica una confirmación (el entero
aplicado) cada vez que acepta un valor de velocidad. La app lo usa para
mostrar el valor realmente aplicado. Sin retención.

## Usuarios y ACL (requisito previo a órdenes)

El broker dedicado exige usuarios distintos (`agrotech_txt`,
`agrotech_gateway`, app), pero usuarios distintos **no** restringen
topics si Mosquitto no tiene ACL: hoy cualquier usuario autenticado
podría publicar en cualquier topic. **No se habilitarán órdenes al TXT
hasta definir ACL por topic** (p. ej. solo app→`comandos/txt`, solo
TXT→suscripción de comandos). Esta fase no crea ACL ni órdenes.

## Estado actual

La app recibe sensores, estado del gateway, direcciones y el evento `PELOTA`.
El gateway reenvía el evento LoRa `E:PELOTA` como payload `PELOTA` en
`agrotech/botones` sin retención. El TXT procesa `PELOTA` con una máquina
de estados que alterna S1 entre RECARGADO (512) y DISPARADO (250 → 0),
además de aplicar velocidad por `agrotech/robot/velocidad/set` y confirmar
en `agrotech/ack/velocidad`. `comandos/txt` y `ack/txt` siguen reservados
sin uso. Está prohibido publicar `ONLINE` de prueba en el topic del TXT
y publicar en `comandos/txt`.
