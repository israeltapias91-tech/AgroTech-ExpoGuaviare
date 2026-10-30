# Guía — compilar y cargar firmware ESP32 (gateway y nodo)

Este documento explica cómo compilar y cargar el firmware ESP32 si el otro PC se
utilizará para actualizar el gateway. No se modifican topics MQTT, protocolos ni
firmware de operación.

## Archivos de firmware

- `firmware/nodo_esp32_1/nodo_esp32_1.ino` — sensores + botones por LoRa.
- `firmware/gateway_esp32_2/gateway_esp32_2.ino` — LoRa → MQTT (valida antes).
- `firmware/gateway_esp32_2/config.example.h` — plantilla SIN secretos.

## Librerías Arduino requeridas

Instalar desde el Administrador de librerías de Arduino IDE:

- LoRa (Sandeep Mistry)
- PubSubClient
- Adafruit BME680
- Adafruit Unified Sensor
- DHT

WiFi es parte del core ESP32.

## Paquete de placas ESP32

Instalar el paquete de placas ESP32 en Arduino IDE (versión usada en este
proyecto: no determinada; confirmar con `arduino-cli version` o Ayuda >
Acerca de en Arduino IDE).

## Configuración local del gateway (sin secretos en el repositorio)

1. Copiar `firmware/gateway_esp32_2/config.example.h` como
   `firmware/gateway_esp32_2/config.h` junto al sketch.
2. Completar `config.h` con los valores reales de la red local:

   ```cpp
   #define WIFI_SSID "TU_SSID"
   #define WIFI_PASS "TU_CONTRASENA"
   #define MQTT_HOST "IP_DEL_PC_BROKER"
   #define MQTT_PORT 1884
   #define MQTT_USER "agrotech_gateway"
   #define MQTT_PASS "TU_CONTRASENA_MQTT"
   ```

3. `config.h` está excluido de versiones (`.gitignore`). Nunca subir claves.

## IP del PC variable

La IP del PC que hospeda Mosquitto puede cambiar al usar otra red. Antes de
compilar y cargar el gateway, actualizar `MQTT_HOST` en `config.h` con la IP
actual del PC en la red local compartida con el TXT y el gateway.

## Compilar y cargar (Arduino IDE)

1. Abrir el sketch correspondiente (`nodo_esp32_1.ino` o
   `gateway_esp32_2.ino`).
2. Seleccionar la placa ESP32 y el puerto COM del dispositivo.
3. Verificar/compilar (`Ctrl+R` o Sketch > Verificar/Compilar).
4. Cargar (`Ctrl+U` o Sketch > Cargar).
5. Abrir el Monitor Serie a 115200 para observar el arranque y los diagnósticos.

## Compilar y cargar (Arduino CLI)

Ejemplo (ajustar puerto y FQBN):

```powershell
arduino-cli compile --fqbn esp32:esp32:esp32 "firmware\gateway_esp32_2\gateway_esp32_2.ino"
arduino-cli upload -p COM3 --fqbn esp32:esp32:esp32 "firmware\gateway_esp32_2\gateway_esp32_2.ino"
```

Confirmar el FQBN exacto de la placa instalada antes de ejecutar.

## Pines (no cambiar)

Nodo #1: BME680 SDA 21/SCL 22; DHT11 GPIO 4; LED GPIO 25; botones 32/33/34/35;
pulsador pelotas GPIO15 (suelto al arrancar); LoRa NSS 5/SCK 18/MOSI 23/MISO 19/
RST 14/DIO0 26.
Gateway #2: LoRa con los mismos 6 pines; LED testigo GPIO25 (confirmado).

## Pruebas físicas necesarias

Continuidad y niveles de botones, lectura BME680/DHT reales, alcance LoRa
nodo↔gateway, recepción en app (CSV + botones + ONLINE gateway), LEDs según
patrones documentados, y timeout Neutral de 5 s con botón mantenido.
