// PLANTILLA sin secretos — gateway ESP32 #2, ExpoGuaviare.
// Copiar como config.h junto al sketch y completar. config.h está
// ignorado por Git (ver .gitignore). Nunca subir claves a repos.

#pragma once

// Wi-Fi del hotspot del celular (valores de ejemplo; completar con los
// reales del celular en config.h privado).
#define WIFI_SSID "TU_HOTSPOT_SSID"
#define WIFI_PASS "TU_HOTSPOT_CONTRASENA"

// Broker MQTT local (PC con Mosquitto). No usar IP local cambiante del
// celular; usar la IP fija del PC o 127.0.0.1 si el gateway y el PC
// comparten la misma red local.
#define MQTT_HOST "192.168.137.1"
#define MQTT_PORT 1884
#define MQTT_USER "agrotech_gateway"
#define MQTT_PASS "TU_CONTRASENA_MQTT"

// Topics (deben coincidir con la app: docs/PROTOCOLO.md).
#define TOPIC_SENSORES "agrotech/sensores"
#define TOPIC_BOTONES  "agrotech/botones"
#define TOPIC_ESTADO_GW "agrotech/estado/gateway"
