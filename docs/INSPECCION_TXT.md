# Inspección TXT 4.0 — Fase 4 (solo inspección, sin control)

Fecha: 2026-10-13. No se movieron actuadores, no se publicó ningún
comando, no se instaló nada y no se alteró red ni broker.

## 1. Qué se pudo inspeccionar y con qué evidencia

- Proyecto ExpoGuaviare (`C:\Users\israe\Videos\proyecto IDE\`):
  `README.md`, `docs/PROTOCOLO.md` (estado Fase 3), `mosquitto-local.conf`
  (`listener 1883 127.0.0.1`, solo localhost), sin repositorio Git
  (`git status`: no es repositorio). El control del TXT sigue
  deshabilitado (`btn_orden.setEnabled(False)`, etiqueta `Control
  pendiente de validación de hardware`); `agrotech/comandos/txt` solo
  existe como constante reservada, sin llamadas `.publish(` en `src/`.
- Conexión física del TXT a la PC: `serial.tools.list_ports` (pyserial
  3.5) reporta **0 puertos COM**; `Win32_SerialPort` vacío; filtro
  `Win32_PnPEntity` por fischer/TTL/FTDI/CH340/CP210/Arduino/STM sin
  coincidencias. Evidencia: el TXT **no está conectado por USB** a esta PC.
- Software de fischertechnik en la PC: barrido de `C:\Program Files` por
  `ischer|ROBO|TXT` solo encuentra `Mosquitto`. No hay entorno ROBOPro
  ni utilidades del TXT instaladas en la PC.
- Librerías Python de la PC (`pip list`): `paho-mqtt 2.1.0`, `pyserial
  3.5`, `PySide6 6.11.1`. **No hay** `ftrobopy` ni ninguna librería de
  fischertechnik. No se instaló nada.
- Broker: proceso Mosquitto preexistente (PID 7472) solo observado, no
  detenido ni alterado. Configuración del proyecto intacta y enlazada a
  `127.0.0.1`: un TXT en otro dispositivo **no puede** conectarse a ese
  broker; no se cambió por regla de fase.

## 2. Entorno y librerías confirmados

- Entorno Python del TXT y su versión: **no verificable** desde esta PC
  (sin USB, sin IP conocida del TXT, sin documentación aportada).
- Cliente MQTT en el TXT: **no verificable** (no se puede observar el
  equipo; nada instalado en la PC).
- Origen de cada dato: comandos citados arriba; ninguna especificación
  del TXT 4.0 fue consultada ni asumida.

## 3. Actuadores/puertos confirmados

**No verificable.** No se observó ningún actuador, puerto, motor ni
salida. No se inventan pines, modelos ni APIs.

## 4. Acción manual recomendada

**Ninguna.** Sin actuador confirmado ni método de parada confirmado, no
existe base técnica para aprobar una acción. Recomendar un movimiento
sería inventar capacidades del equipo.

## 5. Método de parada/estado seguro

**No confirmado.** Queda pendiente de la verificación física del usuario.

## 6. Lista breve de verificaciones físicas para el usuario

Anotar y entregar estos datos para desbloquear la Fase 5:

1. ¿El TXT 4.0 enciende y qué muestra su pantalla (IP, modo USB/WLAN)?
2. ¿Qué actuador está físicamente conectado y a qué puerto/salida
   exactos (p. ej. motor a M1, lámpara a O3)? Modelo del actuador.
3. ¿Qué entorno corre en el TXT (versión indicada en su pantalla o
   documentación del equipo) y admite un cliente MQTT sin instalar nada?
4. ¿Cómo se detiene la acción (orden de parada, timeout, apagado) y cuál
   es el estado seguro ante desconexión?
5. Conectar el TXT por USB a la PC y avisar para re-inspeccionar puertos
   COM y diálogo con el equipo.

## 7. Bloqueo documentado

Falta hardware accionable confirmado (actuador + puerto + parada). El
control permanece deshabilitado y visible como pendiente. La Fase 5 solo
podrá implementarse tras recibir los 5 puntos anteriores.

## 8. Nota de red (2026-10-13, solo inspección, sin cambios)

- Pantalla del TXT (`Info → Dirección WiFi`, foto del usuario): IP
  `10.183.218.207`, máscara `255.255.255.0`, gateway y DNS
  `10.183.218.170` (DHCP; la IP puede cambiar al renovarse).
- PC (interfaz Wi-Fi, `Get-NetIPConfiguration`, sin SSID ni claves):
  IPv4 `10.183.218.152`, gateway `10.183.218.170`.
- PC y TXT están en la misma subred `10.183.218.0/24` con el mismo gateway.
- Ping ICMP (`Test-Connection`, 2 intentos): 2/2 respuestas (300 ms,
  182 ms). Demuestra alcanzabilidad básica de red; **no** demuestra
  comunicación MQTT ni control del robot, y no se probó ningún
  puerto/servicio del TXT.
- Sin cambios: no se tocó DHCP, IP, firewall, Mosquitto (proceso
  preexistente intacto) ni `mosquitto-local.conf` (sigue en `127.0.0.1`,
  por lo que el TXT aún no puede usar ese broker). La IP dinámica no se
  guardó en configuración, código ni documentación permanente.

## 9. Servicios documentados del TXT (2026-10-13, solo lectura)

- Ping repetido: 1/1 respuesta (172 ms). Conectividad básica vigente.
- TCP 80 (servidor web documentado): **abierto**. Un único `GET /` sin
  credenciales devolvió HTTP 200, título `TXT Webserver` (~819 bytes).
  Dato no sensible confirmado: el servidor web del TXT está activo.
  No se inició sesión ni se tocó nada más.
- TCP 3883 (broker MQTT integrado según firmware): **cerrado/filtrado**
  (`TcpTestSucceeded=False`). No se afirma broker integrado en este
  equipo; o no lo incluye su firmware o no está activo.
- La página inicial no contiene versión de firmware visible. Pendiente:
  foto del usuario de `Info → Versión del software`.
- Opciones de integración futura (sin elegir): servidor web del TXT
  (solo lectura pública confirmada) o broker MQTT de la PC si el TXT
  admitiera cliente MQTT (no verificado; requeriría credenciales y
  decisión de red fuera de esta fase). Ninguna implica control de
  motores todavía.
- Sin mensajes MQTT, sin órdenes, sin cambios de red/Mosquitto/código.

## 10. Fase 5A — estado MQTT del TXT (2026-10-13, sin control)

- Datos del equipo (informados por el usuario): TXT 4.0, firmware
  3.1.10, TXT-API 6.4.2, Linux 4.19.49, sin programa de usuario cargado.
  Plataforma móvil de cuatro ruedas observada en fotos, sin mapeo
  salida↔motor confirmado.
- Paho en el TXT: **no verificado** (sin método de solo lectura
  confirmado en el equipo). El bundle `txt/` no depende de APIs del TXT.
- App: suscrita a `agrotech/estado/txt`; solo `ONLINE` marca Conectado;
  timeout configurable (45 s) vuelve a Desconectado. Gateway y TXT
  separados. Control del robot sigue deshabilitado.
- Broker: el listener `127.0.0.1:1883` no acepta al TXT; propuesta
  separada e inactiva en `mosquitto-remoto-propuesta.conf` (requiere
  decisión del usuario: perfil autenticado + credenciales fuera del
  repositorio). Sin cambios aplicados.
- Comunicación real del TXT: **pendiente** (script preparado en `txt/`,
  no cargado ni ejecutado).

## 11. Fase 5B — broker dedicado (2026-10-13, sin control)

- IP de la PC confirmada de nuevo: `10.183.218.152` (sin cambios).
  TXT con ping vigente (117 ms).
- `mosquitto-expo.local.conf` (privado): listener `1884` solo en la IP
  Wi-Fi de la PC, auth obligatoria, sin persistencia, logs a consola.
  Validado (`--test-config` OK) y probado en vivo: escucha solo en
  `10.183.218.152:1884`; anónimo rechazado (`not authorised`) en topic
  de diagnóstico `agrotech/prueba/conexion`. Aceptación autenticada
  pendiente de contraseña real (no inventada; procedimiento en
  `docs/BROKER_DEDICADO.md`).
- Firewall: sin regla previa para 1884; ninguna creada (sin elevación);
  especificación mínima documentada por si hiciera falta.
- Puerto 1883 ocupado por el Mosquitto preexistente (PID 7472), no
  tocado. `mosquitto-local.conf` intacto.
- TXT: Paho y transferencia/ejecución siguen sin método confirmado;
  script compatible Paho 1.x/2.x. Enlace físico PC↔TXT no probado.

## 12. Fase 5C — intento de heartbeat real (2026-10-13, sin control)

- Red reconfirmada: PC `10.183.218.152`, TXT `10.183.218.207` con ping
  2/2 (139/197 ms). Sin cambios de red, DHCP ni firewall.
- Broker dedicado re-verificado en vivo (PID propio, ya detenido):
  escucha solo en `10.183.218.152:1884`; anónimo rechazado en topic de
  diagnóstico. Sin publicaciones a `estado/txt` desde la PC.
- Contraseña: `mosquitto-expo.passwd` sigue vacío (0 bytes); no se creó
  ni inventó ninguna. Sin ella no hay prueba de aceptación autenticada.
- Firewall: existen reglas previas que permiten `mosquitto.exe`
  (TCP/UDP, perfil privado y público); ninguna regla nueva creada ni
  necesaria por ahora.
- TXT: sin software ROBO Pro/Coding en la PC y sin método confirmado de
  transferencia/ejecución; Paho en el equipo sigue no verificado.
  Script `txt_estado.py` re-revisado: solo `ONLINE` cada 15 s, sin
  suscripciones, sin comandos, sin hardware.
- Heartbeat real: **no logrado en esta sesión** (bloqueado en contraseña
  + carga/ejecución en el TXT, ambas acciones físicas del usuario).
  Pasos exactos en `docs/BROKER_DEDICADO.md` y `txt/LEEME_TXT.md`.
- Limpieza: broker propio detenido, 1884 libre; Mosquitto preexistente
  (PID 7472) intacto; `py_compile` OK sin modificar código.

## 13. Contraseña creada + broker listo (2026-10-13, sin control)

- `mosquitto-expo.passwd`: existe, no vacío (199 bytes), con entrada
  `agrotech_txt` (verificado por booleano; contenido jamás mostrado).
- Creados `config.ini` y `txt/broker_privado.ini` (privados, ignorados
  por Git) con usuario/host/puerto y contraseña **vacía**: solo el
  usuario puede completarla localmente. Límite explicado: ambos formatos
  exigen la clave en texto claro; mitigación = archivos privados,
  nunca versionados ni compartidos.
- Conf re-validada con el pwfile real (`--test-config` OK). Puerto 1884
  libre; listener intacto (`10.183.218.152`, auth obligatoria).
  Broker **no arrancado**: queda listo para inicio manual del usuario.
- `txt_estado.py` re-revisado por búsqueda: sin `subscribe`, sin
  publicación a comandos, sin hardware (solo mención en comentarios).
- App parsea `[broker_txt]` (host/puerto/usuario OK; contraseña
  pendiente de completar por el usuario; timeout 45 intacto).
- Pendiente físico: completar ambas contraseñas, arrancar broker
  dedicado, transferir/ejecutar en el TXT por método oficial y observar
  `TXT: Conectado` + timeout. Sin heartbeat real hasta entonces.

## 14. Contraseña colocada + circuito autenticado OK (2026-10-13)

- Contraseña colocada por orden del usuario solo en `config.ini` y
  `txt/broker_privado.ini` (privados, ignorados por Git). Jamás impresa,
  ni en consola, logs, informes o versionados. Respaldos previos de esos
  archivos (sin secreto) intactos.
- Broker dedicado arrancado (PID propio, ya detenido): escucha solo en
  `10.183.218.152:1884`.
- Aceptación autenticada verificada en proceso (credenciales leídas del
  archivo, nunca en comandos): pub/sub OK en topic de diagnóstico
  `agrotech/prueba/conexion`. Anónimo rechazado (`not authorised`).
- App abierta 12 s con `[broker_txt]` activo contra 1884: sin bloqueos
  ni cierres. Cero publicaciones a `estado/txt` desde la PC.
- Limpieza: broker propio detenido, 1884 libre; Mosquitto preexistente
  (PID 7472) intacto.
- Pendiente: transferir/ejecutar en el TXT y observar heartbeat real +
  timeout de 45 s en vivo.

## 15. Cliente principal al broker LAN (2026-10-14)

- `agrotech_app` agregado al pwfile (append sin `-c`; formato PBKDF2
  verificado empíricamente en entorno aislado; jamas expuesto).
- `config.ini [mqtt]` → `10.183.218.152:1884` + `agrotech_app` (clave en
  privado). `[broker_txt]` intacto. Respaldos nuevos sin sobrescribir.
- Broker dedicado verificado en vivo y app abierta con auth: sin
  bloqueos. Cero publicaciones de prueba y cero órdenes.
- Tráfico del gateway: ausente en 1884 y 1883 al momento de la prueba
  (el ESP32 publicaba según registro anterior; probablemente apagado o
  apuntando a otro broker). La PC queda lista: al publicar el gateway,
  la app muestra lecturas/botones/estado sin más cambios.
- Procesos ajenos (7472 en 1883; broker dedicado iniciado por el usuario
  en 1884) observados, nunca alterados.
