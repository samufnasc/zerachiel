# ============================================================
# screen_capture.py — Captura de Tela / Visão (Zerachiel v4.2)
# ============================================================

import base64
import logging

logger = logging.getLogger("VoiceAssistant")


def _encode_png(shot) -> bytes:
    """Converte a captura em PNG (compatível com mss 6+ e 10+)."""
    import mss.tools
    try:
        return mss.tools.to_png(shot, output=None)
    except TypeError:
        return mss.tools.to_png(shot.raw, (shot.width, shot.height))


def capture_screen_png_base64(monitor: int = 1) -> str:
    """Captura o monitor atual e retorna a imagem em PNG codificada em base64."""
    import mss
    with mss.mss() as sct:
        shot = sct.grab(sct.monitors[monitor])
        png_bytes = _encode_png(shot)
    logger.info(f"Captura de tela: {shot.width}x{shot.height} ({len(png_bytes)} bytes)")
    return base64.b64encode(png_bytes).decode("ascii")