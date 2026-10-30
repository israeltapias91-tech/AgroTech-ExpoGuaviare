# Guía de inicio (fase gateway/botones)

## Requisitos

- Windows con Python 3.10 o superior.
- Dependencias de `requirements.txt` (PySide6 + paho-mqtt).
- Un broker MQTT local para recibir lecturas (ver abajo). Sin broker,
  la ventana abre igual pero queda en espera y reintenta en segundo plano.
- No se necesita SIMA en esta fase. ESP32/LoRa/TXT físicos: pendientes.

## Pasos

1. Abrir una terminal en la carpeta del proyecto (`proyecto IDE/`).
2. Crear y activar un entorno virtual (recomendado):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

3. Instalar dependencias:

```powershell
pip install -r requirements.txt
```

4. Arrancar la ventana (conecta al broker local en segundo plano, sin bloquear):

```powershell
python src/main.py
```

Debe abrirse la ventana `ExpoGuaviare — AgroTech` con las cuatro
tarjetas en `Sin dato`, gateway y TXT en `Desconectado`, dirección en
`Neutral` y el botón de orden deshabilitado. Al conectar con el broker,
el indicador superior lo anuncia; con cada lectura válida se actualizan
tarjetas y hora; con cada botón válido, la dirección. Si una lectura se
vence (30 s sin datos), se muestra `Sin datos recientes` en vez de
valores antiguos; sin botones por 5 s, la dirección vuelve a `Neutral`.

## Broker MQTT local (Mosquitto, solo localhost)

La aplicación usa la configuración central (`config.example.ini` o
`config.ini` local): broker `127.0.0.1:1883`, topics `agrotech/sensores`
y `agrotech/estado/gateway`. No hay credenciales.

Verificar disponibilidad en Windows (ruta confirmada en este equipo):

```powershell
& "C:\Program Files\mosquitto\mosquitto.exe" -h
Test-NetConnection -ComputerName 127.0.0.1 -Port 1883
```

Si el puerto 1883 responde, el broker ya está activo. Si no, iniciar
una instancia local de prueba enlazada SOLO a `127.0.0.1` con el
archivo `mosquitto-local.conf` del proyecto (no cambia servicios ni
configuración de Windows):

```powershell
& "C:\Program Files\mosquitto\mosquitto.exe" -c mosquitto-local.conf -v
```

Dejar esa terminal abierta mientras se usa la aplicación.

## Publicación manual desde consola (DATOS DE PRUEBA, no hardware)

Los siguientes mensajes sirven para probar la recepción MQTT. Son
pruebas generadas desde consola: **no son lecturas de sensores físicos**
ni indican ESP32, LoRa o TXT conectados.

Lectura de prueba en `agrotech/sensores`:

```powershell
& "C:\Program Files\mosquitto\mosquitto_pub.exe" -h 127.0.0.1 -t agrotech/sensores -m "24.5,60.2,1013.1,150,0,1"
```

Estado de prueba en `agrotech/estado/gateway`:

```powershell
& "C:\Program Files\mosquitto\mosquitto_pub.exe" -h 127.0.0.1 -t agrotech/estado/gateway -m "ONLINE"
```

Otros ejemplos de prueba:

```powershell
# Fallback DHT: presión y gas deben verse como "Sin dato", no como cero.
& "C:\Program Files\mosquitto\mosquitto_pub.exe" -h 127.0.0.1 -t agrotech/sensores -m "25.0,50.0,0,0,0,1"
# Inválido: debe rechazarse con motivo y conservar el último dato válido.
& "C:\Program Files\mosquitto\mosquitto_pub.exe" -h 127.0.0.1 -t agrotech/sensores -m "esto,no,es,valido"
# Gateway fuera de línea.
& "C:\Program Files\mosquitto\mosquitto_pub.exe" -h 127.0.0.1 -t agrotech/estado/gateway -m "OFFLINE"
# Botón de prueba: la dirección debe mostrarse y volver a Neutral a los 5 s.
& "C:\Program Files\mosquitto\mosquitto_pub.exe" -h 127.0.0.1 -t agrotech/botones -m "ADELANTE"
# Botón inválido: debe rechazarse con motivo, sin cambiar la dirección.
& "C:\Program Files\mosquitto\mosquitto_pub.exe" -h 127.0.0.1 -t agrotech/botones -m "ARRIBA"
```

## Broker LAN y usuarios separados (gateway)

El gateway ESP32 no alcanza el broker de desarrollo (`127.0.0.1`); debe
usar el broker dedicado en la IP LAN de la PC (`mosquitto-expo.local.conf`,
puerto 1884, auth obligatoria). La app puede apuntar su `[mqtt]` a ese
broker con usuario/clave **privados** en `config.ini` (nunca en el ejemplo
ni en docs). Usuarios distintos por rol:

- `agrotech_txt`: solo estado del TXT.
- `agrotech_gateway`: publica sensores, botones y su ONLINE (crearlo con
  `mosquitto_passwd` **sin** `-c` para agregar sin borrar; la clave la
  escribe el usuario en el prompt, no va a archivos versionados).
- App en LAN: usuario propio con solo lectura (pendiente de alta).

Límite documentado: sin ACL en Mosquitto, usuarios distintos no restringen
topics. No habrá órdenes al TXT hasta definir ACL por topic
(ver `docs/PROTOCOLO.md`).

## Configuración

- `config.example.ini` trae valores no secretos de ejemplo.
- Para uso local opcional: copiar a `config.ini` y ajustar (no se sube).
- La aplicación funciona sin `config.ini` (usa defaults equivalentes).

## Notas

- No se publica nada a `agrotech/comandos/txt` ni se tocan los topics
  reservados del TXT en esta fase.
- Prohibido publicar `ONLINE` de prueba en `agrotech/estado/txt` desde
  la PC o scripts locales: solo un `ONLINE` real del TXT puede marcarlo
  conectado. La comunicación del TXT sigue pendiente (ver
  `txt/LEEME_TXT.md`).
- No publicar a direcciones externas ni a la red compartida.
