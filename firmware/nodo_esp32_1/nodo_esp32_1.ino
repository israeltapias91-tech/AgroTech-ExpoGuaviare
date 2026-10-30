/* Nodo ESP32 #1 — ExpoGuaviare (sensores + botones por LoRa).
 *
 * Lee BME680 (principal) con respaldo DHT11, cuatro botones con
 * antirrebote y transmite tramas versionadas por LoRa al gateway.
 * Enlace bidireccional: el gateway confirma (ACK) cada trama válida y
 * el LED indica enlace reciente. NO usa WiFi/MQTT.
 * NO controla TXT, motores ni actuadores.
 *
 * Pines (fijos por cableado, no cambiar):
 *   BME680: SDA 21, SCL 22 (se prueban direcciones 0x77 y 0x76).
 *   DHT11: GPIO 4.
 *   LED testigo instalado: GPIO 25.
 *   Botones a GND con pull-up externo 10k a 3.3V (pulsado = LOW):
 *     adelante 32, atras 33, izquierda 34, derecha 35. Solo INPUT.
 *   Pulsador de pelotas: GPIO15 a GND con pull-up externo 10k a 3.3V.
 *     GPIO15 es pin de arranque: mantener el pulsador suelto al encender.
 *   LoRa: NSS 5, SCK 18, MOSI 23, MISO 19, RST 14, DIO0 26.
 *
 * Librerías Arduino requeridas (no incluidas, ver firmware/README.md):
 *   LoRa (Sandeep Mistry), Adafruit BME680, Adafruit Unified Sensor, DHT.
 */

#include <SPI.h>
#include <LoRa.h>
#include <Wire.h>
#include <Adafruit_Sensor.h>
#include <Adafruit_BME680.h>
#include <DHT.h>

// ---------- Pines ----------
#define PIN_BOTON_ADELANTE  32
#define PIN_BOTON_ATRAS     33
#define PIN_BOTON_IZQUIERDA 34
#define PIN_BOTON_DERECHA   35
#define PIN_BOTON_PELOTA    15 // Pin de arranque; pull-up externo de 10k.
#define PIN_DHT             4
#define PIN_LED             25
#define LORA_NSS  5
#define LORA_RST  14
#define LORA_DIO0 26

// ---------- Parámetros LoRa compartidos con el gateway ----------
#define LORA_FREQ 433E6   // Módulos SX1278 433MHz instalados.
#define LORA_SF   7
#define LORA_BW   125E3
#define LORA_CR   5       // Coding rate 4/5.
#define LORA_SYNC 0xA6
#define LORA_TXDBM 17

// ---------- Tiempos (ms) ----------
#define PERIODO_SENSORES 10000UL
#define ANTIRREBOTE      40UL
#define REPETIR_BOTON    2000UL  // < timeout visual app (5 s).
#define LED_PULSO        100UL
#define LED_PERIODO      2000UL
// Enlace LoRa: ACK válido en los últimos 30 s = LED fijo; si no, parpadeo.
#define UMBRAL_ENLACE    30000UL
// Reintento de la MISMA trama (misma seq; el gateway descarta duplicados,
// así no se publica dos veces en MQTT): cada 1.5 s, máximo 3 intentos.
#define REINTENTO_ACK    1500UL
#define MAX_REINTENTOS   3
// Ping de enlace (trama P, nunca va a MQTT) si todo está callado 10 s.
#define PERIODO_PING     10000UL

// Umbrales documentados en config.example.ini ([umbrales]); no inventados.
#define UMBRAL_TEMP_ALTA    35.0
#define UMBRAL_HUM_BAJA     20.0
#define UMBRAL_PRESION_BAJA 950.0
#define UMBRAL_GAS_ALTO     500.0

Adafruit_BME680 bme;
DHT dht(PIN_DHT, DHT11);
bool bme_ok = false;

uint32_t seq_sensores = 0;
uint32_t seq_botones = 0;
uint32_t seq_ping = 0;
uint32_t seq_eventos = 0;
unsigned long t_sensores = 0;
unsigned long t_led = 0;
bool led_encendido = false;
// Último ACK válido recibido (0 = ninguno todavía).
unsigned long t_ultimo_ack = 0;
unsigned long t_ultima_tx = 0;
// Trama pendiente de confirmación (una sola; reintentos con misma seq).
struct TramaPendiente {
  bool activa = false;
  String trama;
  String tipo; // "S", "B", "E" o "P".
  uint32_t seq = 0;
  unsigned long t_envio = 0;
  int intentos = 0;
};
TramaPendiente pendiente;

// Pulsador de disparo: un evento por pulsación estable (antirrebote 40 ms).
bool pelota_lectura_anterior = false;
bool pelota_estado_estable = false;
unsigned long pelota_t_cambio = 0;
uint8_t eventos_pelota_en_cola = 0;

// Estado de botones (índice 0..3 = adelante/atras/izq/der).
const uint8_t pines_botones[4] = {
  PIN_BOTON_ADELANTE, PIN_BOTON_ATRAS, PIN_BOTON_IZQUIERDA, PIN_BOTON_DERECHA
};
const char *nombres_botones[4] = {"ADELANTE", "ATRAS", "IZQUIERDA", "DERECHA"};
bool estable[4] = {false, false, false, false};
bool anterior_leido[4] = {false, false, false, false};
unsigned long t_cambio[4] = {0, 0, 0, 0};
String ultimo_tx = "LIBERADO";
unsigned long t_ultimo_tx_boton = 0;

void lora_emitir(const String &trama) {
  LoRa.beginPacket();
  LoRa.print(trama);
  LoRa.endPacket(); // Espera breve de TX (~decenas de ms); el loop sigue.
}

// Envía trama nueva "AG1:<seq>:<tipo>:<cuerpo>" y la deja pendiente de ACK.
void enviar_trama(const String &tipo, const String &cuerpo, uint32_t &seq) {
  seq++;
  String trama = "AG1:" + String(seq) + ":" + tipo + ":" + cuerpo;
  lora_emitir(trama);
  pendiente.activa = true;
  pendiente.trama = trama;
  pendiente.tipo = tipo;
  pendiente.seq = seq;
  pendiente.t_envio = millis();
  pendiente.intentos = 1;
  t_ultima_tx = millis();
}

// ACK esperado: "AG1:<seq_gw>:A:<T>:<seq_orig>" con T en S/B/P.
// Solo vale si coincide tipo+seq con la trama pendiente.
bool procesar_ack(const String &trama) {
  int p1 = trama.indexOf(':');
  int p2 = trama.indexOf(':', p1 + 1);
  int p3 = trama.indexOf(':', p2 + 1);
  int p4 = trama.indexOf(':', p3 + 1);
  if (p1 < 0 || p2 < 0 || p3 < 0 || p4 < 0) return false;
  if (trama.substring(0, p1) != "AG1") return false;
  if (trama.substring(p2 + 1, p3) != "A") return false;
  String tipo = trama.substring(p3 + 1, p4);
  String sseq = trama.substring(p4 + 1);
  if (tipo != "S" && tipo != "B" && tipo != "P" && tipo != "E") return false;
  for (unsigned i = 0; i < sseq.length(); i++) {
    if (!isDigit(sseq[i])) return false;
  }
  if (sseq.length() == 0) return false;
  uint32_t seq_orig = (uint32_t)strtoul(sseq.c_str(), nullptr, 10);
  if (!pendiente.activa || tipo != pendiente.tipo || seq_orig != pendiente.seq) {
    return false;
  }
  pendiente.activa = false;
  t_ultimo_ack = millis();
  return true;
}

// Recepción no bloqueante + reintento + ping de enlace. Todo por millis().
void gestionar_enlace(unsigned long ahora) {
  int tam = LoRa.parsePacket();
  if (tam > 0 && tam < 96) {
    String rx = "";
    while (LoRa.available()) rx += (char)LoRa.read();
    rx.trim();
    procesar_ack(rx); // Lo que no sea ACK válido se ignora.
  }
  // Reintento de la MISMA trama y seq (sin duplicar en MQTT).
  if (pendiente.activa && ahora - pendiente.t_envio >= REINTENTO_ACK) {
    if (pendiente.intentos < MAX_REINTENTOS) {
      lora_emitir(pendiente.trama);
      pendiente.intentos++;
      pendiente.t_envio = ahora;
      t_ultima_tx = ahora;
    } else {
      pendiente.activa = false; // Se rinde; el próximo ciclo usa seq nueva.
    }
  }
  // Ping de enlace si lleva 10 s sin transmitir nada (nunca va a MQTT).
  if (!pendiente.activa && ahora - t_ultima_tx >= PERIODO_PING) {
    enviar_trama("P", "PING", seq_ping);
  }
}

String direccion_actual() {
  int n = 0;
  int cual = -1;
  for (int i = 0; i < 4; i++) {
    if (estable[i]) { n++; cual = i; }
  }
  // Ninguno o más de uno pulsado -> LIBERADO.
  if (n == 1) return String(nombres_botones[cual]);
  return String("LIBERADO");
}

void leer_botones(unsigned long ahora) {
  for (int i = 0; i < 4; i++) {
    bool pulsado = (digitalRead(pines_botones[i]) == LOW);
    if (pulsado != anterior_leido[i]) {
      anterior_leido[i] = pulsado;
      t_cambio[i] = ahora;
    } else if ((ahora - t_cambio[i]) >= ANTIRREBOTE) {
      estable[i] = pulsado;
    }
  }
}

void leer_boton_pelota(unsigned long ahora) {
  bool pulsado = (digitalRead(PIN_BOTON_PELOTA) == LOW);
  if (pulsado != pelota_lectura_anterior) {
    pelota_lectura_anterior = pulsado;
    pelota_t_cambio = ahora;
  } else if ((ahora - pelota_t_cambio) >= ANTIRREBOTE &&
             pulsado != pelota_estado_estable) {
    pelota_estado_estable = pulsado;
    if (pelota_estado_estable) {
      // Cola acotada por seguridad; un botón mantenido solo genera un evento.
      if (eventos_pelota_en_cola < 3) eventos_pelota_en_cola++;
      Serial.println(F("Pulsador PELOTA: evento en cola"));
    }
  }
}

void enviar_evento_pelota() {
  if (pendiente.activa || eventos_pelota_en_cola == 0) return;
  enviar_trama("E", "PELOTA", seq_eventos);
  eventos_pelota_en_cola--;
}

void publicar_botones(unsigned long ahora, bool forzar) {
  String dir = direccion_actual();
  bool cambio = (dir != ultimo_tx);
  bool toca_repetir = (dir != "LIBERADO") && (ahora - t_ultimo_tx_boton >= REPETIR_BOTON);
  if (!(forzar || cambio || toca_repetir)) return;
  // LIBERADO puede adelantar tramas B/S/P; no reemplaza un evento E de pelota
  // para conservar su confirmación y evitar perder la pulsación.
  if (pendiente.activa &&
      !(dir == "LIBERADO" && cambio && pendiente.tipo != "E")) return;
  enviar_trama("B", dir, seq_botones);
  ultimo_tx = dir;
  t_ultimo_tx_boton = ahora;
}

bool leer_sensores(float &t, float &h, float &p, float &g) {
  if (bme_ok && bme.performReading()) {
    t = bme.temperature;
    h = bme.humidity;
    p = bme.pressure / 100.0;        // Pa -> hPa.
    g = bme.gas_resistance / 1000.0; // ohm -> kohm.
    return true;
  }
  return false;
}

void publicar_sensores() {
  // Sin pisar una trama pendiente de ACK (el próximo periodo reintenta).
  if (pendiente.activa) return;
  float t, h, p, g;
  int a_th, a_pg;
  if (leer_sensores(t, h, p, g)) {
    a_th = (t > UMBRAL_TEMP_ALTA || h < UMBRAL_HUM_BAJA) ? 1 : 0;
    a_pg = (p < UMBRAL_PRESION_BAJA || g > UMBRAL_GAS_ALTO) ? 1 : 0;
  } else {
    // Respaldo DHT11: T/H reales; presión y gas NO disponibles (contrato).
    float td = dht.readTemperature();
    float hd = dht.readHumidity();
    if (isnan(td) || isnan(hd)) return; // Sin datos: no se inventa nada.
    t = td; h = hd; p = 0; g = 0;
    a_th = (t > UMBRAL_TEMP_ALTA || h < UMBRAL_HUM_BAJA) ? 1 : 0;
    a_pg = 1; // Marcador DHT del contrato (P=0,G=0,A_PG=1).
  }
  String cuerpo = String(t, 1) + "," + String(h, 1) + ","
    + String(p, 1) + "," + String(g, 0) + ","
    + String(a_th) + "," + String(a_pg);
  enviar_trama("S", cuerpo, seq_sensores); // "AG1:<seq>:S:<CSV6>".
}

void setup() {
  for (int i = 0; i < 4; i++) pinMode(pines_botones[i], INPUT); // Pull-up externo.
  pinMode(PIN_BOTON_PELOTA, INPUT); // GPIO15: pull-up externo instalado.
  pinMode(PIN_LED, OUTPUT);
  digitalWrite(PIN_LED, LOW);
  dht.begin();
  Wire.begin(21, 22);
  // La dirección I2C del módulo no se asume: se prueban 0x77 y 0x76.
  bme_ok = bme.begin(0x77);
  if (!bme_ok) bme_ok = bme.begin(0x76);
  if (bme_ok) {
    bme.setTemperatureOversampling(BME680_OS_8X);
    bme.setHumidityOversampling(BME680_OS_2X);
    bme.setPressureOversampling(BME680_OS_4X);
    bme.setGasHeater(320, 150); // Valores del ejemplo de la librería.
  }
  LoRa.setPins(LORA_NSS, LORA_RST, LORA_DIO0);
  LoRa.setSpreadingFactor(LORA_SF);
  LoRa.setSignalBandwidth(LORA_BW);
  LoRa.setCodingRate4(LORA_CR);
  LoRa.setSyncWord(LORA_SYNC);
  LoRa.setTxPower(LORA_TXDBM);
  // Si LoRa no inicia, el nodo queda detenido con LED fijo (falla visible).
  if (!LoRa.begin(LORA_FREQ)) {
    digitalWrite(PIN_LED, HIGH);
    while (true) { delay(1000); }
  }
  t_sensores = millis();
  pelota_lectura_anterior = (digitalRead(PIN_BOTON_PELOTA) == LOW);
  pelota_estado_estable = pelota_lectura_anterior;
  pelota_t_cambio = millis();
  publicar_botones(millis(), true); // Estado inicial LIBERADO.
}

void loop() {
  unsigned long ahora = millis();
  // LED de enlace (no bloqueante): fijo con ACK en los últimos 30 s;
  // parpadeo si no hay confirmación reciente.
  bool enlace = (t_ultimo_ack != 0) && (ahora - t_ultimo_ack <= UMBRAL_ENLACE);
  if (enlace) {
    if (!led_encendido) {
      led_encendido = true;
      digitalWrite(PIN_LED, HIGH);
    }
  } else if (ahora - t_led >= (led_encendido ? LED_PULSO : LED_PERIODO)) {
    led_encendido = !led_encendido;
    digitalWrite(PIN_LED, led_encendido ? HIGH : LOW);
    t_led = ahora;
  }
  gestionar_enlace(ahora); // RX de ACK + reintentos + ping (sin bloquear).
  leer_botones(ahora);
  leer_boton_pelota(ahora);
  enviar_evento_pelota(); // Prioridad sobre telemetría y repetición de dirección.
  publicar_botones(ahora, false);
  if (ahora - t_sensores >= PERIODO_SENSORES) {
    t_sensores = ahora;
    publicar_sensores();
  }
}
