"""Paleta y hoja de estilos del rediseño AgroTech."""

from __future__ import annotations

from PySide6.QtWidgets import QWidget


COLORS = {
    "fondo": "#F4F1E8",
    "superficie": "#FFFFFF",
    "verde_bosque": "#163B2B",
    "verde_bosque_2": "#20523B",
    "verde_profundo": "#123B2B",
    "verde_panel": "#1B4A36",
    "verde_suave": "#DFE9D8",
    "lima": "#B7E36A",
    "lima_fuerte": "#8FCB3B",
    "texto": "#1E2B24",
    "texto_suave": "#647067",
    "texto_claro": "#EAF2EC",
    "texto_claro_suave": "#BFD3C4",
    "borde": "#E2DED2",
    "rojo": "#B23A2E",
    "rojo_suave": "#F5DCD8",
    "ambar": "#A86913",
    "ambar_suave": "#F8ECCF",
    "verde_estado": "#2F7D4A",
    "verde_estado_suave": "#DFF0E4",
    "azul": "#3D7E9A",
    "azul_suave": "#E8F2F6",
    "violeta": "#5B5AA6",
    "violeta_suave": "#EEEDF8",
    "naranja": "#C56A3D",
    "naranja_suave": "#FBEDE4",
    "oliva": "#5E8C3D",
    "oliva_suave": "#EDF5E4",
}


def repolish(widget: QWidget) -> None:
    """Reaplica la hoja de estilos tras cambiar una propiedad dinámica."""
    estilo = widget.style()
    estilo.unpolish(widget)
    estilo.polish(widget)
    widget.update()


def stylesheet() -> str:
    """Hoja de estilos global, sin imágenes ni dependencias externas."""
    c = COLORS
    return f"""
    QWidget {{
        font-family: "Segoe UI", "Noto Sans", sans-serif;
        font-size: 13px;
        color: {c["texto"]};
    }}
    QWidget#raiz {{
        background: {c["fondo"]};
    }}
    QScrollArea#scroll {{
        border: none;
        background: transparent;
    }}
    QScrollArea#scroll > QWidget > QWidget {{
        background: transparent;
    }}
    QScrollBar:vertical {{
        background: transparent;
        width: 10px;
        margin: 4px 2px;
    }}
    QScrollBar::handle:vertical {{
        background: #C9D1C4;
        border-radius: 4px;
        min-height: 28px;
    }}
    QScrollBar::add-line:vertical,
    QScrollBar::sub-line:vertical,
    QScrollBar::add-page:vertical,
    QScrollBar::sub-page:vertical {{
        height: 0;
        background: transparent;
    }}

    QFrame#cabecera {{
        background: {c["verde_bosque"]};
        border: none;
    }}
    QLabel#marca {{
        color: #FFFFFF;
        font-size: 21px;
        font-weight: 700;
    }}
    QLabel#subtituloMarca {{
        color: {c["texto_claro_suave"]};
        font-size: 11px;
    }}
    QLabel#navSeccion {{
        color: {c["texto_claro_suave"]};
        font-size: 10px;
        font-weight: 700;
        letter-spacing: 1px;
    }}
    QPushButton#nav {{
        background: transparent;
        color: #D7E3DA;
        border: none;
        border-bottom: 3px solid transparent;
        padding: 8px 12px;
        font-weight: 600;
        text-align: left;
    }}
    QPushButton#nav:hover {{
        color: #FFFFFF;
        background: {c["verde_bosque_2"]};
    }}
    QPushButton#nav:checked {{
        color: #FFFFFF;
        border-bottom: 3px solid {c["lima"]};
    }}
    QPushButton#nav:focus {{
        background: {c["verde_bosque_2"]};
    }}

    QFrame#badgeVivo {{
        border-radius: 14px;
    }}
    QFrame#badgeVivo[estado="en_vivo"] {{
        background: {c["verde_estado_suave"]};
    }}
    QFrame#badgeVivo[estado="sin_datos"] {{
        background: {c["ambar_suave"]};
    }}
    QFrame#badgeVivo[estado="sin_conexion"] {{
        background: {c["rojo_suave"]};
    }}
    QLabel#badgeTexto {{
        font-size: 10px;
        font-weight: 700;
        letter-spacing: 1px;
    }}
    QLabel#badgeTexto[estado="en_vivo"] {{
        color: {c["verde_estado"]};
    }}
    QLabel#badgeTexto[estado="sin_datos"] {{
        color: {c["ambar"]};
    }}
    QLabel#badgeTexto[estado="sin_conexion"] {{
        color: {c["rojo"]};
    }}

    QLabel#tituloSeccion {{
        color: {c["verde_bosque"]};
        font-size: 24px;
        font-weight: 700;
    }}
    QLabel#subtituloSeccion {{
        color: {c["texto_suave"]};
        font-size: 11px;
    }}

    QFrame[tarjeta="true"] {{
        background: {c["superficie"]};
        border: 1px solid {c["borde"]};
        border-radius: 16px;
    }}
    QFrame[categoria="temperatura"] {{
        background: {c["naranja_suave"]};
        border: 1px solid #F2D8C8;
        border-radius: 16px;
    }}
    QFrame[categoria="humedad"] {{
        background: {c["azul_suave"]};
        border: 1px solid #D5E5EC;
        border-radius: 16px;
    }}
    QFrame[categoria="presion"] {{
        background: {c["violeta_suave"]};
        border: 1px solid #DBD9EF;
        border-radius: 16px;
    }}
    QFrame[categoria="gas"] {{
        background: {c["oliva_suave"]};
        border: 1px solid #DCE8CF;
        border-radius: 16px;
    }}
    QFrame#tarjetaDatos {{
        background: {c["verde_profundo"]};
        border: 1px solid #1E4A36;
        border-radius: 18px;
    }}
    QFrame#tarjetaLanzador {{
        background: #EFF7DF;
        border: 1px solid #DCE8C8;
        border-radius: 16px;
    }}
    QFrame#bannerRobot {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
            stop:0 {c["verde_bosque"]}, stop:1 {c["verde_bosque_2"]});
        border: none;
        border-radius: 18px;
    }}

    QLabel#tituloTarjeta {{
        color: {c["texto"]};
        font-size: 14px;
        font-weight: 700;
    }}
    QLabel#valorSensor {{
        color: {c["texto"]};
        font-size: 34px;
        font-weight: 700;
    }}
    QLabel#unidadSensor {{
        color: {c["texto_suave"]};
        font-size: 12px;
        font-weight: 600;
    }}
    QLabel#detalleTarjeta {{
        color: {c["texto_suave"]};
        font-size: 10px;
    }}
    QLabel#tituloConexion {{
        color: {c["texto"]};
        font-size: 13px;
        font-weight: 700;
    }}
    QLabel#detalleConexion {{
        color: {c["texto_suave"]};
        font-size: 10px;
    }}
    QLabel#tituloDatos {{
        color: #FFFFFF;
        font-size: 18px;
        font-weight: 700;
    }}
    QLabel#subtituloDatos {{
        color: {c["texto_claro_suave"]};
        font-size: 10px;
    }}
    QLabel#sinActividad {{
        color: {c["texto_claro_suave"]};
        font-size: 11px;
    }}
    QLabel#actividadTitulo {{
        color: #FFFFFF;
        font-size: 11px;
        font-weight: 600;
    }}
    QLabel#actividadDetalle {{
        color: {c["texto_claro_suave"]};
        font-size: 10px;
    }}
    QLabel#actividadHora {{
        color: #9DB5A6;
        font-size: 9px;
    }}
    QFrame#filaActividad {{
        background: {c["verde_panel"]};
        border-radius: 10px;
    }}
    QLabel#tituloAlertas {{
        color: #FFFFFF;
        font-size: 13px;
        font-weight: 700;
    }}
    QLabel#sinAlertas {{
        color: {c["texto_claro_suave"]};
        font-size: 10px;
    }}
    QListWidget#listaAlertas {{
        background: #173F2E;
        color: #F2F7F3;
        border: 1px solid #2A5A43;
        border-radius: 10px;
        padding: 4px;
        font-size: 10px;
    }}
    QListWidget#listaAlertas::item {{
        padding: 4px;
        border-bottom: 1px solid #24503C;
    }}

    QLabel[estado="normal"] {{
        color: {c["verde_estado"]};
    }}
    QLabel[estado="conectado"] {{
        color: {c["verde_estado"]};
    }}
    QLabel[estado="alerta"] {{
        color: {c["rojo"]};
    }}
    QLabel[estado="desconectado"] {{
        color: {c["rojo"]};
    }}
    QLabel[estado="vencido"] {{
        color: {c["ambar"]};
    }}
    QLabel[estado="conectando"] {{
        color: {c["ambar"]};
    }}
    QLabel[estado="sin_datos"] {{
        color: {c["texto_suave"]};
    }}
    QLabel[estado="no_disponible"] {{
        color: {c["texto_suave"]};
    }}

    QLabel#notaBloqueada {{
        background: {c["ambar_suave"]};
        color: #7A5310;
        border-radius: 10px;
        padding: 8px 10px;
        font-size: 10px;
    }}
    QLabel#notaInfo {{
        background: #F1F4EB;
        color: {c["texto_suave"]};
        border-radius: 9px;
        padding: 7px 9px;
        font-size: 10px;
    }}
    QLabel#notaExito {{
        background: {c["verde_estado_suave"]};
        color: {c["verde_estado"]};
        border-radius: 9px;
        padding: 7px 9px;
        font-size: 10px;
        font-weight: 600;
    }}
    QLabel#notaError {{
        background: {c["rojo_suave"]};
        color: {c["rojo"]};
        border-radius: 9px;
        padding: 7px 9px;
        font-size: 10px;
        font-weight: 600;
    }}
    QLabel#textoBanner {{
        color: #FFFFFF;
        font-size: 22px;
        font-weight: 700;
    }}
    QLabel#subtextoBanner {{
        color: {c["texto_claro_suave"]};
        font-size: 11px;
    }}
    QLabel#etiquetaBanner {{
        background: {c["lima"]};
        color: {c["verde_bosque"]};
        border-radius: 10px;
        padding: 4px 9px;
        font-size: 9px;
        font-weight: 700;
        letter-spacing: 1px;
    }}
    QLabel#tituloPanel {{
        color: {c["texto"]};
        font-size: 14px;
        font-weight: 700;
    }}
    QLabel#subtituloPanel {{
        color: {c["texto_suave"]};
        font-size: 10px;
    }}
    QLabel#ultimoEvento {{
        color: {c["texto_suave"]};
        font-size: 11px;
    }}
    QLabel#ultimoEvento[estado="activo"] {{
        color: {c["verde_bosque"]};
        font-weight: 700;
    }}
    QLabel#velocidadValor {{
        color: {c["verde_bosque"]};
        font-size: 30px;
        font-weight: 700;
    }}
    QLabel#velocidadUnidad {{
        color: {c["texto_suave"]};
        font-size: 11px;
    }}

    QPushButton#direccion {{
        background: {c["superficie"]};
        color: {c["texto"]};
        border: 1px solid #D9DED4;
        border-radius: 14px;
        min-width: 64px;
        min-height: 52px;
    }}
    QPushButton#direccion:hover {{
        background: #F7F9F3;
    }}
    QPushButton#direccion:disabled {{
        background: #F2F0E8;
        color: #A3AAA2;
        border-color: #E4E0D5;
    }}
    QPushButton#detener {{
        background: {c["rojo"]};
        color: #FFFFFF;
        border: none;
        border-radius: 36px;
        min-width: 72px;
        min-height: 72px;
    }}
    QPushButton#detener:disabled {{
        background: #D9B9B4;
        color: #72514C;
    }}
    QPushButton#lanzar {{
        background: {c["lima_fuerte"]};
        color: {c["verde_bosque"]};
        border: none;
        border-radius: 16px;
        padding: 13px;
        font-weight: 700;
    }}
    QPushButton#lanzar:disabled {{
        background: #DCE8C8;
        color: #727D62;
    }}
    QPushButton#lanzar:focus {{
        border: 2px solid {c["verde_bosque"]};
    }}
    QSlider::groove:horizontal {{
        height: 8px;
        background: #E5E9DF;
        border-radius: 4px;
    }}
    QSlider::sub-page:horizontal {{
        background: #B7C9A8;
        border-radius: 4px;
    }}
    QSlider::handle:horizontal {{
        background: #7D8B76;
        width: 18px;
        margin: -5px 0;
        border-radius: 9px;
    }}
    QSlider::handle:horizontal:disabled {{
        background: #7D8B76;
    }}

    QFrame#configTarjeta {{
        background: {c["superficie"]};
        border: 1px solid {c["borde"]};
        border-radius: 16px;
    }}
    QLabel#configTitulo {{
        color: {c["verde_bosque"]};
        font-size: 13px;
        font-weight: 700;
    }}
    QLabel#configClave {{
        color: {c["texto_suave"]};
        font-size: 10px;
    }}
    QLabel#configValor {{
        color: {c["texto"]};
        font-size: 11px;
        font-weight: 600;
    }}
    QLabel#configValor[estado="conectado"] {{
        color: {c["verde_estado"]};
    }}
    QLabel#configValor[estado="desconectado"] {{
        color: {c["rojo"]};
    }}
    QLabel#configValor[estado="sin_datos"] {{
        color: {c["texto_suave"]};
    }}
    QLabel#configValor[estado="conectando"] {{
        color: {c["ambar"]};
    }}
    QLabel#pie {{
        color: {c["texto_suave"]};
        font-size: 10px;
    }}
    """
