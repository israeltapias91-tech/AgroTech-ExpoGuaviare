# Lista final de archivos del repositorio

## Incluidos (versionados)

- `README.md` — instrucciones en español para Windows.
- `.gitignore` — exclusión de secretos, respaldos, logs y artefactos de build.
- `.env.example` — variables de entorno de ejemplo (sin secretos).
- `requirements.txt` — dependencias Python con versiones reales (PySide6 6.11.1, paho-mqtt 2.1.0).
- `config.example.ini` — plantilla de configuración de la app (sin secretos reales).
- `src/` — aplicación de Windows (app, UI, MQTT, contrato de mensajes).
- `txt/txt_estado.py`, `txt/controlador_motores.py`, `txt/servo.py` — scripts del TXT (compatibles con Python antiguo).
- `txt/broker_privado.example.ini` — plantilla de configuración del TXT (sin credenciales).
- `txt/LEEME_TXT.md` — instrucciones físicas para el TXT.
- `firmware/nodo_esp32_1/nodo_esp32_1.ino` — sketch del nodo.
- `firmware/gateway_esp32_2/gateway_esp32_2.ino` — sketch del gateway.
- `firmware/gateway_esp32_2/config.example.h` — plantilla de configuración del gateway (sin secretos).
- `firmware/README.md` — documentación del firmware.
- `lib/` — copias de referencia de los scripts del TXT.
- `docs/` — guías (ROBO Pro Coding, firmware ESP32, versiones, lista de archivos, protocolo, broker dedicado, inspección TXT, inicio).
- `mosquitto-local.conf` — broker local de prueba solo localhost (no secreto).
- `mosquitto-remoto-propuesta.conf` — propuesta inactiva documentada (no secreto).
- `Untitled.py` — heartbeat autocontenido para el TXT.

## Excluidos (no versionados) y motivos

- `config.ini` — contraseñas reales y host del broker (texto claro). Nunca a GitHub.
- `txt/broker_privado.ini` — contraseña real del TXT (texto claro). Nunca a GitHub.
- `data/broker_privado.json` — contraseña real del broker del TXT (texto claro). Nunca a GitHub.
- `mosquitto-expo.local.conf` — listener con IP real de la PC y ruta de password_file. Privado.
- `mosquitto-expo.passwd` — archivo de contraseñas de Mosquitto. Nunca a GitHub.
- `firmware/**/config.h`, `secrets.h`, `*.passwd` — Wi-Fi y credenciales MQTT del gateway. Nunca a GitHub.
- `*.backup_*` — respaldos de edición sin valor para el repositorio.
- `__pycache__/`, `*.py[cod]` — bytecode generado.
- `.venv/`, `venv/`, `.env` — entornos virtuales y variables locales.
- `*.log` — registros de ejecución.
- `build/`, `dist/`, `*.spec`, `*.exe`, `*.msi` — artefactos de empaquetado.

## Comprobación con Git

Tras inicializar el repositorio, ejecutar:

```powershell
git status --porcelain
git check-ignore config.ini txt/broker_privado.ini data/broker_privado.json mosquitto-expo.local.conf mosquitto-expo.passwd firmware/gateway_esp32_2/config.h
```

Ninguno de los archivos excluidos debe aparecer preparado (`git add`) ni en el
commit. Las plantillas `*.example` sí se versionan porque no contienen secretos.
