# Versiones usadas en este proyecto

Versiones determinadas inspeccionando los archivos y la configuración actual:

| Componente | Versión | Origen |
|---|---|---|
| Python | No determinada en el repositorio | Confirmar con `python --version` |
| PySide6 | 6.11.1 | `requirements.txt` |
| paho-mqtt | 2.1.0 | `requirements.txt` |
| OpenCV / opencv-python | No determinada (opcional, solo cámara del TXT) | `python -c "import cv2; print(cv2.__version__)"` |
| Arduino IDE / CLI | No determinada | `arduino-cli version` o Ayuda > Acerca de |
| Paquete de placas ESP32 | No determinada | Administrador de placas / `arduino-cli` |
| Mosquitto | No determinada como versión de paquete | `mosquitto.exe -h` |

Si una versión no se puede determinar, no se inventa: se confirma en el equipo
antes de replicar el entorno en otro PC. Los scripts del TXT (`txt/`) mantienen
compatibilidad con intérpretes Python antiguos (sin f-strings, sin `pathlib`,
sin anotaciones de tipo).
