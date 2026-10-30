# Broker dedicado PC↔TXT (Fase 5B) — procedimiento del usuario

El broker dedicado está preparado pero **no operativo**: falta crear la
contraseña real (no se inventó ninguna) y la comunicación del TXT sigue
pendiente. Este documento no contiene secretos.

## Estado dejado por OpenCode

- `mosquitto-expo.local.conf` (privado, no versionado): listener `1884`
  solo en `192.168.137.1`, `allow_anonymous false`, persistencia
  desactivada, logs a consola. Validado con `--test-config`: OK.
- `mosquitto-expo.passwd` (privado, no versionado): creado **vacío** a la
  espera de la contraseña real. Sin ella, el broker rechaza todo.
- Verificado: escucha solo en `192.168.137.1:1884`; conexión anónima
  rechazada (`not authorised`) en `agrotech/prueba/conexion`. Aceptación
  autenticada pendiente de la contraseña real.
- `mosquitto-local.conf` (`127.0.0.1:1883`) intacto. Proceso Mosquitto del
  puerto 1883 no tocado.

## Paso 1 — crear la contraseña (la escribe el usuario, interactivo)

En PowerShell, en la carpeta del proyecto (la contraseña se escribe en el
prompt de la herramienta, no queda en argumentos ni logs):

```powershell
& "C:\Program Files\mosquitto\mosquitto_passwd.exe" -c mosquitto-expo.passwd agrotech_txt
```

Usuario dedicado: `agrotech_txt`. No reutilizar otras credenciales. No
enviar la contraseña por chat ni guardarla en archivos versionados.

## Paso 2 — configurar la app (privado)

Copiar `config.example.ini` como `config.ini` (excluido de versiones) y
agregar, con los valores reales:

```ini
[broker_txt]
host = 192.168.137.1
port = 1884
user = agrotech_txt
password = (la creada en el paso 1)
```

## Paso 3 — arrancar el broker dedicado

```powershell
& "C:\Program Files\mosquitto\mosquitto.exe" -c mosquitto-expo.local.conf -v
```

Dejar la terminal abierta. Si la IP Wi-Fi de la PC cambió, actualizar la
línea `listener` del `.conf` a la IP actual (nunca `0.0.0.0`).

## Paso 4 — firewall (solo si el TXT no alcanza el puerto)

No se creó ninguna regla. Estado observado: sin regla previa para 1884.
Si hiciera falta, crear (con privilegios del equipo) una regla entrante
mínima: perfil privado solamente, TCP puerto local 1884, origen limitado
a la subred local actual, sin abrir otros puertos.

## Paso 5 — TXT

Según `txt/LEEME_TXT.md`: verificar Paho, copiar el bundle por el flujo
oficial, completar `broker_privado.ini` en el TXT con host
`192.168.137.1`, puerto `1884`, usuario `agrotech_txt` y la contraseña
del paso 1, y ejecutar `python3 txt_estado.py`.

## Paso 6 — comprobar

Arrancar la app (`python src/main.py`): el distintivo debe pasar a
`TXT: Conectado` solo con el `ONLINE` real del TXT (heartbeat cada 15 s;
timeout 45 s). No publicar `ONLINE` de prueba desde la PC.
