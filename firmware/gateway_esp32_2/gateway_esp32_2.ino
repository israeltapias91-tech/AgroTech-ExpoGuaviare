/* Gateway ESP32 #2 — ExpoGuaviare (LoRa -> MQTT).
 *
 * Recibe tramas del nodo por LoRa, las VALIDA y publica por MQTT:
 *   sensores -> agrotech/sensores (CSV de 6 campos, retained=false).
 *   botones  -> agrotech/botones  (token permitido, retained=false).
 *   pelotas  -> agrotech/botones  ("PELOTA", retained=false).
 * Confirma con ACK LoRa "AG1:<seq>:A:<T>:<seq_orig>".
 *   - B/E: solo despues de que mqtt.publish() devuelva true.
 *   - S/P: se mantiene la logica existente (no se modifica).
 * Si un B/E ya entregado se repite (misma seq y contenido) se reenvia el
 * ACK sin volver a publicar en MQTT, para cubrir un ACK LoRa perdido.
 * Publica ONLINE al conectar y deja LWT OFFLINE en agrotech/estado/gateway.
 * JAMAS publica en agrotech/comandos/txt ni agrotech/ack/txt.
 * NO controla TXT, motores ni actuadores.
 *
 * Pines LoRa (iguales que el nodo): NSS 5, SCK 18, MOSI 23, MISO 19,
 * RST 14, DIO0 26.
 *
 * LED testigo en GPIO25 (confirmado por el usuario): rapido = sin
 * Wi-Fi/MQTT; fijo = conectado; apagon breve = RX LoRa valida.
 *
 * Secretos (WiFi/MQTT) solo desde config.h local (ignorado por Git).
 * Librerias Arduino requeridas (ver firmware/README.md):
 *   LoRa (Sandeep Mistry), WiFi (core ESP32), PubSubClient.
 */

#include <SPI.h>
#include <LoRa.h>
#include <WiFi.h>
#include <PubSubClient.h>
#include "config.h"

// ---------- Pines ----------
#define LORA_NSS  5
#define LORA_RST  14
#define LORA_DIO0 26
#define PIN_LED_CANDIDATO 25
// GPIO25 confirmado por el usuario como LED testigo (2026-10-14).
// Convencion: HIGH = encendido (ánodo vía resistencia al GPIO, cátodo a
// GND, igual que el nodo). Si tu LED está cableado a 3.3 V (activo en LOW),
// invierte led_fijar() a (encendido ? LOW : HIGH).
#define USA_LED_GATEWAY 1

// ---------- Parámetros LoRa (idénticos al nodo) ----------
#define LORA_FREQ 433E6
#define LORA_SF   7
#define LORA_BW   125E3
#define LORA_CR   5
#define LORA_SYNC 0xA6

// ---------- Tiempos (ms) ----------
#define REINTENTO_MQTT   2000UL
// WiFi: solo se reintenta tras 10 s continuos desconectado; nunca se
// interrumpe un intento de conexion en curso (causaba conecta/desconecta).
#define REINTENTO_WIFI   10000UL
#define LED_RAPIDO       250UL
#define LED_RX_APAGADO   120UL
// El nodo reintenta la MISMA seq cada 1.5 s, maximo 3 transmisiones
// (inicial + 2 reintentos, ~4.5 s hasta rendirse). 6 s cubre un ACK LoRa
// perdido y reduce el riesgo de confundir un reinicio del nodo (que
// reinicia sus contadores) con un duplicado antiguo.
#define VENTANA_DUPLICADO_MS 6000UL

// Rangos espejo de la app (docs/PROTOCOLO.md); lo demás se descarta.
#define R_TEMP_MIN -40.0
#define R_TEMP_MAX 80.0
#define R_HUM_MIN  0.0
#define R_HUM_MAX  100.0
#define R_PRE_MIN  300.0
#define R_PRE_MAX  1100.0
#define R_GAS_MIN  0.0
#define R_GAS_MAX  2000.0

WiFiClient wifi;
PubSubClient mqtt(wifi);

uint32_t ultima_seq_sensores = 0;
// Solo se avanzan cuando la publicación MQTT de B/E tuvo éxito.
uint32_t ultima_seq_botones_entregada = 0;
String ultimo_token_botones = "";
uint32_t ultima_seq_eventos_entregada = 0;
unsigned long t_ultima_entrega_botones = 0;
unsigned long t_ultima_entrega_evento = 0;

uint32_t seq_ack = 0; // Secuencia propia de confirmaciones.
unsigned long t_mqtt = 0;
unsigned long t_led = 0;
bool led_estado = false;
unsigned long t_rx = 0; // Ventana de parpadeo por recepción LoRa válida.
unsigned long t_sin_wifi = 0; // Momento en que se perdió el Wi-Fi.
bool wifi_aviso_ok = false;   // true tras avisar conexión (evita spam).

// Diagnóstico de enlaces (sin secretos).
int wifi_estado_anterior = WL_IDLE_STATUS;
bool mqtt_estaba_conectado = false;
unsigned long t_mqtt_conectado = 0;
uint32_t mqtt_intentos = 0;
uint32_t mqtt_conexiones = 0;
uint32_t wifi_intentos = 0;

void led_fijar(bool encendido) {
#if USA_LED_GATEWAY
  digitalWrite(PIN_LED_CANDIDATO, encendido ? HIGH : LOW);
#endif
  led_estado = encendido;
}

const char *wifi_estado_texto(int estado) {
  switch (estado) {
    case WL_IDLE_STATUS: return "IDLE";
    case WL_NO_SSID_AVAIL: return "SIN_SSID";
    case WL_SCAN_COMPLETED: return "SCAN_OK";
    case WL_CONNECTED: return "CONECTADO";
    case WL_CONNECT_FAILED: return "FALLO";
    case WL_CONNECTION_LOST: return "PERDIDA";
    case WL_DISCONNECTED: return "DESCONECTADO";
    default: return "OTRO";
  }
}

const char *mqtt_estado_texto(int estado) {
  switch (estado) {
    case MQTT_CONNECTED: return "CONECTADO";
    case MQTT_DISCONNECTED: return "DESCONECTADO";
    case MQTT_CONNECTION_TIMEOUT: return "TIMEOUT";
    case MQTT_CONNECTION_LOST: return "PERDIDA";
    case MQTT_CONNECT_FAILED: return "FALLO_CONEXION";
    case MQTT_CONNECT_BAD_PROTOCOL: return "PROTOCOLO";
    case MQTT_CONNECT_BAD_CLIENT_ID: return "CLIENT_ID";
    case MQTT_CONNECT_UNAVAILABLE: return "NO_DISPONIBLE";
    case MQTT_CONNECT_BAD_CREDENTIALS: return "CREDENCIALES";
    case MQTT_CONNECT_UNAUTHORIZED: return "NO_AUTORIZADO";
    default: return "OTRO";
  }
}

bool numero_valido(const String &s) {
  if (s.length() == 0) return false;
  char *fin = nullptr;
  strtod(s.c_str(), &fin);
  return fin != nullptr && *fin == '\0';
}

// Valida trama "AG1:<seq>:S:<6 campos>" y reconstruye el CSV exacto.
bool trama_sensores(const String &trama, String &csv, uint32_t &seq) {
  // Formato: AG1:<seq>:S:t,h,p,g,a_th,a_pg
  int p1 = trama.indexOf(':');
  int p2 = trama.indexOf(':', p1 + 1);
  int p3 = trama.indexOf(':', p2 + 1);
  if (p1 < 0 || p2 < 0 || p3 < 0) return false;
  if (trama.substring(0, p1) != "AG1") return false;
  if (trama.substring(p2 + 1, p3) != "S") return false;
  String sseq = trama.substring(p1 + 1, p2);
  for (unsigned i = 0; i < sseq.length(); i++) {
    if (!isDigit(sseq[i])) return false;
  }
  seq = (uint32_t)strtoul(sseq.c_str(), nullptr, 10);
  if (seq == ultima_seq_sensores) return false; // Duplicado.
  String cuerpo = trama.substring(p3 + 1);
  // Seis campos exactos.
  float v[6];
  int ini = 0;
  for (int i = 0; i < 6; i++) {
    int coma = (i < 5) ? cuerpo.indexOf(',', ini) : (int)cuerpo.length();
    if (i < 5 && coma < 0) return false;
    String campo = cuerpo.substring(ini, (i < 5) ? coma : cuerpo.length());
    campo.trim();
    if (!numero_valido(campo)) return false;
    v[i] = strtod(campo.c_str(), nullptr);
    ini = coma + 1;
  }
  if (cuerpo.indexOf(',', ini) >= 0) return false; // Séptimo campo.
  if (!(v[0] >= R_TEMP_MIN && v[0] <= R_TEMP_MAX)) return false;
  if (!(v[1] >= R_HUM_MIN && v[1] <= R_HUM_MAX)) return false;
  String a4 = String((int)v[4]);
  String a5 = String((int)v[5]);
  if ((a4 != "0" && a4 != "1") || (a5 != "0" && a5 != "1")) return false;
  bool dht = (v[2] == 0 && v[3] == 0 && a5 == "1"); // Marcador del contrato.
  if (!dht) {
    if (!(v[2] >= R_PRE_MIN && v[2] <= R_PRE_MAX)) return false;
    if (!(v[3] >= R_GAS_MIN && v[3] <= R_GAS_MAX)) return false;
  }
  ultima_seq_sensores = seq;
  csv = cuerpo; // CSV de seis campos tal cual (formato de la app).
  return true;
}

// Valida trama "AG1:<seq>:B:<TOKEN>" contra la lista permitida.
// NO modifica ultima_seq_botones_entregada: eso solo ocurre tras publicar.
bool trama_boton(const String &trama, String &token, uint32_t &seq) {
  int p1 = trama.indexOf(':');
  int p2 = trama.indexOf(':', p1 + 1);
  int p3 = trama.indexOf(':', p2 + 1);
  if (p1 < 0 || p2 < 0 || p3 < 0) return false;
  if (trama.substring(0, p1) != "AG1") return false;
  if (trama.substring(p2 + 1, p3) != "B") return false;
  String sseq = trama.substring(p1 + 1, p2);
  if (sseq.length() == 0) return false;
  for (unsigned i = 0; i < sseq.length(); i++) {
    if (!isDigit(sseq[i])) return false;
  }
  seq = (uint32_t)strtoul(sseq.c_str(), nullptr, 10);
  token = trama.substring(p3 + 1);
  token.trim();
  token.toUpperCase();
  if (token != "ADELANTE" && token != "ATRAS" && token != "IZQUIERDA"
      && token != "DERECHA" && token != "LIBERADO") return false;
  return true;
}

// Valida evento "AG1:<seq>:E:PELOTA" del pulsador de pelotas (estricto).
// NO modifica ultima_seq_eventos_entregada: eso solo ocurre tras publicar.
bool trama_evento(const String &trama, uint32_t &seq) {
  int p1 = trama.indexOf(':');
  int p2 = trama.indexOf(':', p1 + 1);
  int p3 = trama.indexOf(':', p2 + 1);
  if (p1 < 0 || p2 < 0 || p3 < 0) return false;
  if (trama.substring(0, p1) != "AG1") return false;
  if (trama.substring(p2 + 1, p3) != "E") return false;
  String sseq = trama.substring(p1 + 1, p2);
  if (sseq.length() == 0) return false;
  for (unsigned i = 0; i < sseq.length(); i++) {
    if (!isDigit(sseq[i])) return false;
  }
  seq = (uint32_t)strtoul(sseq.c_str(), nullptr, 10);
  String cuerpo = trama.substring(p3 + 1);
  cuerpo.trim();
  if (cuerpo != "PELOTA") return false;
  return true;
}

// Valida ping de enlace "AG1:<seq>:P:PING" (estricto). Nunca va a MQTT.
bool trama_ping(const String &trama, uint32_t &seq) {
  int p1 = trama.indexOf(':');
  int p2 = trama.indexOf(':', p1 + 1);
  int p3 = trama.indexOf(':', p2 + 1);
  if (p1 < 0 || p2 < 0 || p3 < 0) return false;
  if (trama.substring(0, p1) != "AG1") return false;
  if (trama.substring(p2 + 1, p3) != "P") return false;
  String sseq = trama.substring(p1 + 1, p2);
  if (sseq.length() == 0) return false;
  for (unsigned i = 0; i < sseq.length(); i++) {
    if (!isDigit(sseq[i])) return false;
  }
  String cuerpo = trama.substring(p3 + 1);
  cuerpo.trim();
  if (cuerpo != "PING") return false;
  seq = (uint32_t)strtoul(sseq.c_str(), nullptr, 10);
  return true;
}

// Confirmación "AG1:<seq_ack>:A:<T>:<seq_orig>" al nodo (T = S/B/P/E).
void enviar_ack(const String &tipo, uint32_t seq_orig) {
  seq_ack++;
  LoRa.beginPacket();
  LoRa.print("AG1:" + String(seq_ack) + ":A:" + tipo + ":" + String(seq_orig));
  LoRa.endPacket();
  Serial.print("LoRa: ACK ");
  Serial.print(tipo);
  Serial.print(" seq=");
  Serial.print(seq_orig);
  Serial.print(" ack=");
  Serial.println(seq_ack);
}

bool mqtt_listo() {
  return WiFi.status() == WL_CONNECTED && mqtt.connected();
}

// Publica B/E y devuelve true solo si MQTT la aceptó. No hay cola: si no
// hay conexión o publish falla, el nodo reintenta la misma seq.
bool publicar_en_botones(const String &tipo, const String &token, uint32_t seq) {
  if (!mqtt_listo()) {
    Serial.print("MQTT: ");
    Serial.print(tipo);
    Serial.print(" seq=");
    Serial.print(seq);
    Serial.print(" token=");
    Serial.print(token);
    Serial.print(" sin conexion (WiFi=");
    Serial.print(wifi_estado_texto(WiFi.status()));
    Serial.print(", MQTT=");
    Serial.print(mqtt_estado_texto(mqtt.state()));
    Serial.println("); NO se envia ACK");
    return false;
  }
  bool ok = mqtt.publish(TOPIC_BOTONES, token.c_str(), false);
  Serial.print("MQTT: ");
  Serial.print(tipo);
  Serial.print(" seq=");
  Serial.print(seq);
  Serial.print(" token=");
  Serial.print(token);
  Serial.print(" publish=");
  Serial.println(ok ? "OK" : "FALLO");
  if (!ok) {
    int estado = mqtt.state();
    Serial.print("MQTT: publish fallo estado=");
    Serial.print(mqtt_estado_texto(estado));
    Serial.print(" (");
    Serial.print(estado);
    Serial.println("); NO se envia ACK");
  }
  return ok;
}

bool es_duplicado_boton(const String &token, uint32_t seq, unsigned long ahora) {
  return ultima_seq_botones_entregada != 0
         && seq == ultima_seq_botones_entregada
         && token == ultimo_token_botones
         && (ahora - t_ultima_entrega_botones) <= VENTANA_DUPLICADO_MS;
}

bool es_duplicado_evento(uint32_t seq, unsigned long ahora) {
  return ultima_seq_eventos_entregada != 0
         && seq == ultima_seq_eventos_entregada
         && (ahora - t_ultima_entrega_evento) <= VENTANA_DUPLICADO_MS;
}

void mqtt_conectar() {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.print("MQTT: intento omitido; WiFi=");
    Serial.println(wifi_estado_texto(WiFi.status()));
    return;
  }
  mqtt_intentos++;
  Serial.print("MQTT: intento #");
  Serial.print(mqtt_intentos);
  Serial.print(" estado_previo=");
  Serial.print(mqtt_estado_texto(mqtt.state()));
  Serial.print(" (");
  Serial.print(mqtt.state());
  Serial.print(") IP=");
  Serial.print(WiFi.localIP());
  Serial.print(" MAC=");
  Serial.println(WiFi.macAddress());

  // LWT honesto: el broker publica OFFLINE solo si se cae la conexión.
  unsigned long t_inicio = millis();
  if (mqtt.connect("agrotech_gateway", MQTT_USER, MQTT_PASS,
                   TOPIC_ESTADO_GW, 0, false, "OFFLINE")) {
    mqtt_conexiones++;
    mqtt_estaba_conectado = true;
    t_mqtt_conectado = millis();
    Serial.print("MQTT: conectado #");
    Serial.print(mqtt_conexiones);
    Serial.print(" IP=");
    Serial.print(WiFi.localIP());
    Serial.print(" MAC=");
    Serial.print(WiFi.macAddress());
    Serial.print(" RSSI=");
    Serial.print(WiFi.RSSI());
    Serial.print(" intento_ms=");
    Serial.println(millis() - t_inicio);
    bool online_ok = mqtt.publish(TOPIC_ESTADO_GW, "ONLINE", false);
    Serial.print("MQTT: ONLINE ");
    Serial.println(online_ok ? "OK" : "FALLO");
  } else {
    int rc = mqtt.state();
    Serial.print("MQTT: fallo rc=");
    Serial.print(rc);
    Serial.print(" (");
    Serial.print(mqtt_estado_texto(rc));
    Serial.print(") WiFi=");
    Serial.print(wifi_estado_texto(WiFi.status()));
    Serial.print(" IP=");
    Serial.print(WiFi.localIP());
    Serial.print(" intento_ms=");
    Serial.println(millis() - t_inicio);
  }
}

void setup() {
  Serial.begin(115200);
  Serial.println("Gateway ExpoGuaviare: arranque");
#if USA_LED_GATEWAY
  pinMode(PIN_LED_CANDIDATO, OUTPUT);
#endif
  led_fijar(false);
  LoRa.setPins(LORA_NSS, LORA_RST, LORA_DIO0);
  LoRa.setSpreadingFactor(LORA_SF);
  LoRa.setSignalBandwidth(LORA_BW);
  LoRa.setCodingRate4(LORA_CR);
  LoRa.setSyncWord(LORA_SYNC);
  if (!LoRa.begin(LORA_FREQ)) {
    Serial.println("LoRa: fallo de inicio (revisar cableado y pines)");
    // Sin LoRa no hay gateway: parpadeo rápido permanente.
    while (true) {
      led_fijar(!led_estado);
      delay(LED_RAPIDO);
    }
  }
  Serial.println("LoRa: inicio correcto");
  WiFi.mode(WIFI_STA);
  wifi_estado_anterior = WiFi.status();
  Serial.print("Gateway: client_id=agrotech_gateway MAC=");
  Serial.println(WiFi.macAddress());
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  Serial.println("WiFi: conectando...");
  mqtt.setServer(MQTT_HOST, MQTT_PORT);
  mqtt.setKeepAlive(30);
  mqtt.setSocketTimeout(5); // Acota cada intento MQTT; connect() puede bloquear hasta 5 s.
}

void loop() {
  unsigned long ahora = millis();

  int wifi_estado = WiFi.status();
  if (wifi_estado != wifi_estado_anterior) {
    Serial.print("WiFi: estado ");
    Serial.print(wifi_estado_texto(wifi_estado_anterior));
    Serial.print(" (");
    Serial.print(wifi_estado_anterior);
    Serial.print(") -> ");
    Serial.print(wifi_estado_texto(wifi_estado));
    Serial.print(" (");
    Serial.print(wifi_estado);
    Serial.println(")");
    wifi_estado_anterior = wifi_estado;
  }

  // WiFi: el begin() de setup hace el primer intento. Aquí solo se
  // reintenta tras 10 s continuos desconectado; jamás se interrumpe un
  // intento en curso (eso causaba el ciclo conecta/desconecta).
  if (wifi_estado != WL_CONNECTED) {
    if (mqtt_estaba_conectado) {
      unsigned long duracion = (ahora - t_mqtt_conectado) / 1000UL;
      mqtt.connected(); // Actualiza el estado interno a PERDIDA si el socket cayó.
      int estado_mqtt = mqtt.state();
      mqtt_estaba_conectado = false;
      Serial.print("MQTT: conexion perdida por WiFi; estado=");
      Serial.print(mqtt_estado_texto(estado_mqtt));
      Serial.print(" (");
      Serial.print(estado_mqtt);
      Serial.print(") duracion=");
      Serial.print(duracion);
      Serial.println(" s");
    }
    if (wifi_aviso_ok) {
      wifi_aviso_ok = false;
      t_sin_wifi = ahora;
      Serial.print("WiFi: desconectado; estado=");
      Serial.print(wifi_estado_texto(wifi_estado));
      Serial.print(" (");
      Serial.print(wifi_estado);
      Serial.println(")");
    }
    if (ahora - t_sin_wifi >= REINTENTO_WIFI) {
      t_sin_wifi = ahora;
      wifi_intentos++;
      Serial.print("WiFi: reintento #");
      Serial.print(wifi_intentos);
      Serial.print(" estado=");
      Serial.println(wifi_estado_texto(WiFi.status()));
      WiFi.disconnect();
      WiFi.begin(WIFI_SSID, WIFI_PASS);
    }
  } else {
    if (!wifi_aviso_ok) {
      wifi_aviso_ok = true;
      Serial.print("WiFi: conectado, IP=");
      Serial.print(WiFi.localIP());
      Serial.print(" MAC=");
      Serial.print(WiFi.macAddress());
      Serial.print(" RSSI=");
      Serial.print(WiFi.RSSI());
      Serial.print(" canal=");
      Serial.println(WiFi.channel());
    }
    if (!mqtt.connected()) {
      if (mqtt_estaba_conectado) {
        unsigned long duracion = (ahora - t_mqtt_conectado) / 1000UL;
        int estado_mqtt = mqtt.state();
        mqtt_estaba_conectado = false;
        Serial.print("MQTT: conexion perdida; estado=");
        Serial.print(mqtt_estado_texto(estado_mqtt));
        Serial.print(" (");
        Serial.print(estado_mqtt);
        Serial.print(") WiFi=");
        Serial.print(wifi_estado_texto(WiFi.status()));
        Serial.print(" duracion=");
        Serial.print(duracion);
        Serial.println(" s");
      }
      if (ahora - t_mqtt >= REINTENTO_MQTT) {
        t_mqtt = ahora;
        mqtt_conectar();
      }
    } else {
      mqtt.loop();
    }
  }

  // Recepción LoRa: validar, publicar (sin retención) y confirmar (ACK).
  int tam = LoRa.parsePacket();
  if (tam > 0 && tam < 96) {
    String trama = "";
    while (LoRa.available()) trama += (char)LoRa.read();
    trama.trim();
    String csv, token;
    uint32_t seq = 0;
    if (trama_sensores(trama, csv, seq)) {
      // Sensores: se conserva la lógica existente (ACK tras intento).
      if (mqtt_listo()) mqtt.publish(TOPIC_SENSORES, csv.c_str(), false);
      enviar_ack("S", seq);
      t_rx = ahora;
    } else if (trama_boton(trama, token, seq)) {
      t_rx = ahora;
      if (es_duplicado_boton(token, seq, ahora)) {
        Serial.print("LoRa B: duplicado entregado seq=");
        Serial.print(seq);
        Serial.print(" token=");
        Serial.print(token);
        Serial.println("; re-ACK sin republicar");
        enviar_ack("B", seq);
      } else if (publicar_en_botones("B", token, seq)) {
        ultima_seq_botones_entregada = seq;
        ultimo_token_botones = token;
        t_ultima_entrega_botones = ahora;
        enviar_ack("B", seq);
      }
    } else if (trama_evento(trama, seq)) {
      t_rx = ahora;
      if (es_duplicado_evento(seq, ahora)) {
        Serial.print("LoRa E: duplicado entregado seq=");
        Serial.print(seq);
        Serial.println("; re-ACK sin republicar");
        enviar_ack("E", seq);
      } else if (publicar_en_botones("E", "PELOTA", seq)) {
        ultima_seq_eventos_entregada = seq;
        t_ultima_entrega_evento = ahora;
        enviar_ack("E", seq);
      }
    } else if (trama_ping(trama, seq)) {
      enviar_ack("P", seq); // Ping de enlace: se confirma, no se publica.
      t_rx = ahora;
    } else {
      Serial.print("LoRa: trama descartada len=");
      Serial.print(trama.length());
      if (trama.startsWith("AG1:")) {
        Serial.print(" trama=");
        Serial.print(trama);
      }
      Serial.println();
    }
  }

  // LED (solo si GPIO25 confirmado): rápido = sin WiFi/MQTT;
  // fijo = conectado; apagón breve = RX LoRa válida.
  bool ok = mqtt_listo();
  if (!ok) {
    if (ahora - t_led >= LED_RAPIDO) {
      t_led = ahora;
      led_fijar(!led_estado);
    }
  } else if (ahora - t_rx < LED_RX_APAGADO) {
    led_fijar(false);
  } else {
    led_fijar(true);
  }
}
