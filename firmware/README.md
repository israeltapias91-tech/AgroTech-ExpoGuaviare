# Firmware ESP32 — ExpoGuaviare (nodo + gateway LoRa)

Dos ESP32: el nodo (#1) mide y transmite sensores, botones de dirección y
el pulsador de pelotas por LoRa; el gateway (#2) valida y publica por MQTT.
El TXT reconoce `PELOTA`; el movimiento de S1 sigue pendiente. Estos cambios
no se han flasheado ni probado físicamente.

## Archivos

- `nodo_esp32_1/nodo_esp32_1.ino` — sensores + botones → LoRa.
- `gateway_esp32_2/gateway_esp32_2.ino` — LoRa → MQTT (valida antes).
- `gateway_esp32_2/config.example.h` — plantilla SIN secretos; copiar
  como `config.h` y completar Wi-Fi/MQTT. `config.h` está ignorado por
  Git (ver `.gitignore`: `firmware/**/config.h`, `secrets.h`, `*.passwd`).

## Pines

Nodo #1 (fijos): BME680 SDA 21/SCL 22; DHT11 GPIO 4; LED GPIO 25
(instalado); botones a GND con pull-up externo 10 kΩ a 3.3 V como
`INPUT` normal: adelante 32, atrás 33, izquierda 34, derecha 35
(pulsado = LOW, sin 5 V); pulsador de pelotas GPIO15 a GND con pull-up
externo 10 kΩ a 3.3 V (suelto al arrancar: GPIO15 es pin de arranque);
LoRa NSS 5/SCK 18/MOSI 23/MISO 19/RST 14/DIO0 26.

Gateway #2: LoRa con los mismos 6 pines (verificado igual en ambos
sketches). LED: **GPIO25 candidato SIN CONFIRMAR**.

### LED del gateway: GPIO25 CONFIRMADO (2026-10-14)

El usuario confirmó el LED testigo en GPIO25: `USA_LED_GATEWAY` vale 1.
Convención usada: HIGH = encendido (igual que el nodo). Si el montaje
resulta activo en LOW, invertir `led_fijar()` (ver comentario en el sketch).

## Protocolo LoRa (versión AG1, ASCII, < 96 bytes)

- Sensores: `AG1:<seq>:S:<T>,<H>,<P>,<G>,<A_TH>,<A_PG>` (los 6 campos del
  CSV de la app, `,` decimal con punto).
- Botones: `AG1:<seq>:B:<TOKEN>` (`ADELANTE|ATRAS|IZQUIERDA|DERECHA|LIBERADO`).
- Pelotas: `AG1:<seq>:E:PELOTA`.
- Ping de enlace: `AG1:<seq>:P:PING` (solo si 10 s sin transmitir nada).
- Confirmación del gateway: `AG1:<seq_gw>:A:<T>:<seq_orig>` con T=S/B/P/E.
- `<seq>` uint32 incremental por tipo. El gateway valida sin avanzar la
  secuencia; en B/E solo confirma después de que `mqtt.publish()` tenga
  éxito. Si un B/E ya entregado se repite (misma seq y contenido, ventana
  de 6 s), reenvía el ACK sin republicar. Los reintentos del nodo (misma
  trama y seq, 1.5 s, máx. 3) no duplican publicaciones MQTT. El ping se
  confirma pero jamás se publica.
- Parámetros idénticos en ambos: 433 MHz (módulos SX1278 433MHz v4.0
  instalados), SF7, BW 125 kHz, CR 4/5, sync `0xA6`, TX 17 dBm.

## Sensores y contrato MQTT (sin inventos)

- Umbrales de `config.example.ini` (`[umbrales]`): temp alta 35.0 °C,
  hum baja 20.0 %, presión baja 950.0 hPa, gas alto 500.0 kΩ. `A_TH=1`
  si T>35 o H<20; `A_PG=1` si P<950 o G>500 (documentado aquí como
  interpretación de los flags; la app solo valida 0/1).
- BME680 se inicializa antes de usarse (prueba 0x77 y 0x76, sin asumir
  dirección); conversiones: Pa→hPa (/100), ohm→kΩ (/1000).
- Respaldo DHT11: T/H reales, `P=0,G=0,A_PG=1` (marcador del contrato,
  no ceros reales). Si ambos fallan, ese ciclo no publica sensores
  (botones siguen fluyendo); nada se inventa.
- Gateway valida versión, secuencia numérica, 6 campos exactos, rangos
  espejo de la app y tokens permitidos; reconstruye el CSV tal cual y
  publica con `retained=false`. Trama inválida = descarte sin publicar ni confirmar.
- Botones: antirrebote 40 ms; cambio → envío inmediato; mantenido →
  repetición cada 2 s (< timeout visual 5 s de la app); al soltar →
  `LIBERADO` inmediato; ninguno o varios → `LIBERADO`.
- Gateway publica `ONLINE` al conectar y LWT `OFFLINE` (el broker lo
  envía solo si cae la conexión; no es un estado fingido). Jamás
  `comandos/txt` ni `ack/txt` (sin rutas de código hacia ellos).

## LED (patrones documentados)

- Nodo (GPIO 25, instalado): **fijo** = ACK válido en los últimos 30 s
  (enlace confirmado); **parpadeo** 100 ms cada 2 s = sin confirmación
  reciente. Fijo encendido al arrancar con LoRa caído = falla visible.
- Gateway (GPIO25 confirmado): rápido = sin Wi-Fi/MQTT; fijo =
  conectado; apagón 120 ms = RX LoRa válida. Sin LoRa al inicio =
  parpadeo rápido permanente.

## Compilación

La compilación anotada anteriormente (14-10-2026) corresponde a la versión
previa al evento `PELOTA`; estos cambios todavía no se han compilado ni
flasheado. La configuración del gateway usa `config.h` privado.

## Configuración local (usuario, sin secretos en repos)

1. `gateway_esp32_2/config.h` desde el ejemplo: SSID/clave, broker
   (host configurable, no asumir IP), usuario/clave MQTT, topics.
2. Confirmar banda ISM local y GPIO25 del gateway antes de una instalación nueva.

## Pasos para integrar el pulsador de pelotas

1. Con el ESP32 #1 apagado, conecta el pulsador entre GPIO15 y GND.
2. Añade una resistencia de 10 kΩ entre GPIO15 y 3.3 V. No conectes el pin
   a 5 V. Suelta el pulsador antes de encender o reiniciar la placa porque
   GPIO15 participa en el modo de arranque.
3. Compila y carga primero el nodo y después el gateway. El pulsador debe
   producir una sola trama `E:PELOTA` por cada toque; mantenerlo pulsado no
   debe repetir el evento.
4. El gateway publica `PELOTA` sin retención en `agrotech/botones`.
   El TXT lo reconoce como evento separado y no cambia el movimiento.
5. Falta completar la llamada de servo S1 en el TXT. No se ha habilitado el
   movimiento físico del lanzador hasta verificar la API de servos que genera
   ROBO Pro Coding.

## Pruebas físicas necesarias

Continuidad y niveles de botones, lectura BME680/DHT reales, alcance
LoRa nodo↔gateway, recepción en app (CSV + botones + ONLINE gateway),
LEDs según patrones, y timeout Neutral de 5 s con botón mantenido.
