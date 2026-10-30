# ExpoGuaviare — AgroTech

Aplicación de escritorio para Windows (Python + PySide6) que muestra mediciones
ambientales en vivo por MQTT y el estado del gateway ESP32 y del TXT 4.0
(Fischertechnik). Proyecto independiente, sin base de datos ni persistencia.

## Versiones realmente usadas en este proyecto

- **Python:** versión del entorno que ejecuta la app. Confirmar con `python --version`.
- **PySide6:** `6.11.1` (ver `requirements.txt`).
- **paho-mqtt:** `2.1.0` (ver `requirements.txt`).
- **OpenCV (opencv-python):** opcional, solo para la cámara del TXT. Se importa de forma
  opcional en `txt/controlador_motores.py`; versión no determinada en este repositorio.
  Confirmar en el TXT con `python -c "import cv2; print(cv2.__version__)"`.
- **Arduino IDE / CLI y paquete de placas ESP32:** no determinados en el repositorio.
  Confirmar con `arduino-cli version` o Ayuda > Acerca de en Arduino IDE.

Si alguna versión no se puede determinar, no se inventa: se confirma en el equipo
antes de replicar el entorno en otro PC.

## Estructura del repositorio

```
src/                 App de Windows (PySide6 + Paho MQTT, solo lectura)
  main.py            Punto de entrada: python src/main.py
  app_config.py      Carga config.ini (o config.example.ini) sin secretos
  app_state.py       Estado en memoria de la sesión
  mqtt_client.py     Cliente MQTT de solo lectura (señales Qt)
  messages.py        Contrato de mensajes y validación
  ui/                Interfaz (ventana, tarjetas, iconos, tema)
txt/                 Scripts para el TXT 4.0 (ROBO Pro Coding)
  txt_estado.py      Heartbeat ONLINE + control por botones (servo S1)
  controlador_motores.py  Control M1..M4, S1 y cámara (idéntico a lib/)
  servo.py           Calibración del servomotor S1 (idéntico a lib/)
  broker_privado.example.ini   Plantilla de configuración del TXT (sin secretos)
firmware/            Firmware ESP32 (nodo #1 y gateway #2 por LoRa/MQTT)
  gateway_esp32_2/   Sketch + config.example.h (plantilla sin secretos)
  nodo_esp32_1/      Sketch del nodo sensores/botones por LoRa
  README.md
lib/                 Copias de los scripts del TXT (referencia)
data/                broker_privado.json (privado, excluido de versiones)
docs/                Documentación y guías
requirements.txt     Dependencias Python con versiones reales
.env.example         Variables de entorno de ejemplo (sin secretos)
```

## Requisitos (Windows)

- Windows con Python 3.10 o superior.
- Dependencias de `requirements.txt` (PySide6 + paho-mqtt).
- Mosquitto instalado para pruebas con broker local (ruta típica:
  `C:\Program Files\mosquitto\mosquitto.exe`).
- No se necesita SIMA ni reutiliza código de otros proyectos.

## 1. Clonar el repositorio

```powershell
git clone <URL_DEL_REPOSITORIO_PRIVADO>
cd "proyecto IDE"
```

## 2. Instalar lo necesario

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

OpenCV solo se necesita si se usa la cámara del TXT; no es obligatorio para la app.

## 3. Configurar la aplicación

Copiar la plantilla de configuración y ajustar los valores locales (archivo privado,
no se sube):

```powershell
copy config.example.ini config.ini
```

Editar `config.ini`:
- `[mqtt]` `host` = IP del PC que hospeda Mosquitto en la red local
  (ejemplo `192.168.1.100`, no la IP real de este equipo).
- `[mqtt]` `port` = `1883` (broker local de prueba) o `1884` (broker dedicado).
- `user` / `password` solo si el broker exige autenticación; los valores reales
  se escriben directamente en este archivo privado y **nunca se suben**.

La aplicación funciona sin `config.ini` (usa valores por defecto equivalentes al
ejemplo: `127.0.0.1:1883`, anónimo).

## 4. Configurar Mosquitto

### Broker local de prueba (solo localhost, desarrollo)

```powershell
& "C:\Program Files\mosquitto\mosquitto.exe" -c mosquitto-local.conf -v
```

Escucha en `127.0.0.1:1883`. El TXT y el gateway **no alcanzan** este broker
desde otros dispositivos.

### Broker dedicado PC ↔ TXT (red local, fase 5B)

Usar `mosquitto-expo.local.conf` (archivo privado, excluido de versiones):
- Listener `1884` solo en la IP Wi-Fi actual de la PC (nunca `0.0.0.0`).
- `allow_anonymous false` y `password_file` con `mosquitto-expo.passwd`.

Crear la contraseña (la escribe el usuario, interactiva):

```powershell
& "C:\Program Files\mosquitto\mosquitto_passwd.exe" -c mosquitto-expo.passwd agrotech_txt
```

Agregar en `config.ini` la sección `[broker_txt]` con host, puerto, usuario y
contraseña reales (archivo privado).

### Firewall (solo si el TXT no alcanza el puerto)

Crear una regla entrante mínima: perfil privado solamente, TCP puerto local
`1884`, origen limitado a la subred local actual. No abrir otros puertos y no
exponer el broker a internet.

**Importante:** la IP del PC que hospeda Mosquitto puede cambiar al usar otra
red. Antes de ejecutar la app, compilar o cargar el firmware, actualizar la IP
del PC en:
- `config.ini` de la app (`[mqtt]` y opcional `[broker_txt]`),
- `broker_privado.ini` del TXT,
- `config.h` del firmware del gateway (antes de compilar/cargar).

## 5. Configurar la IP del PC en app, gateway y TXT

- App: `config.ini` → `[mqtt]` `host` (y `[broker_txt]` `host` si aplica).
- TXT: `broker_privado.ini` junto a `txt_estado.py` en el TXT → `[broker]` `host`.
- Gateway ESP32: `config.h` junto al sketch → `MQTT_HOST`. Recompilar y cargar
  tras cambiar la IP.

## 6. Ejecutar en el orden correcto

1. Iniciar Mosquitto (broker local o dedicado) y dejar la terminal abierta.
2. Ejecutar la app:

   ```powershell
   python src/main.py
   ```

3. (Opcional) Ejecutar el gateway ESP32 y el nodo para recibir lecturas reales.
4. (Opcional) Cargar y ejecutar `txt_estado.py` en el TXT (ver `docs/GUIA_TXT_ROBO_PRO_CODING.md`).

La ventana debe abrir con las tarjetas en `Sin dato`, gateway y TXT en
`Desconectado`, y el broker en `Conectando`. Al llegar lecturas válidas se
actualizan tarjetas y hora.

## 7. Diagnosticar fallos comunes

| Síntoma | Causa probable | Acción |
|---|---|---|
| Ventana no abre | Falta PySide6 | `pip install -r requirements.txt` |
| Broker `Desconectado` | Mosquitto no iniciado o IP equivocada | Iniciar Mosquitto; revisar `host` en `config.ini` |
| Tarjetas en `Sin dato` | No hay publicador de sensores | Iniciar gateway/nodo; usar `mosquitto_pub` para prueba |
| TXT `Desconectado` | No llegó `ONLINE` real del TXT | Ejecutar `txt_estado.py` en el TXT; revisar timeout 45 s |
| IP del broker inalcanzable | IP del PC cambió | Actualizar `host` en todos los `config.*` y recompilar gateway |
| Puerto 1884 cerrado | Firewall o listener en IP antigua | Revisar regla de firewall y `listener` del `.conf` |

No publicar `ONLINE` de prueba en `agrotech/estado/txt` desde la PC: solo un
`ONLINE` real del TXT lo marca conectado.

## Documentación adicional

- `docs/GUIA_TXT_ROBO_PRO_CODING.md` — llevar y ejecutar el programa en el TXT.
- `docs/GUIA_FIRMWARE_ESP32.md` — compilar y cargar el firmware ESP32.
- `docs/LISTA_ARCHIVOS_REPO.md` — archivos incluidos y excluidos con motivos.
- `docs/VERSIONES.md` — versiones usadas y cómo confirmar las no determinadas.
- `docs/PROTOCOLO.md` — contrato de topics y mensajes.
- `docs/BROKER_DEDICADO.md` — procedimiento del broker dedicado PC ↔ TXT.
- `docs/INSPECCION_TXT.md` — inspección del TXT 4.0 (sin control).
