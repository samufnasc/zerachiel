# ============================================================
# voice_input.py — Captura de Áudio Estável (Zerachiel v3.4)
# ============================================================

import speech_recognition as sr
import logging
import threading
from config import VOICE_LANGUAGE, PAUSE_THRESHOLD, CALIBRATION_DURATION

logger = logging.getLogger("VoiceAssistant")
_mic_lock = threading.Lock()

def listen(timeout_wait=7, phrase_limit=120):
    """Ouve o microfone de forma segura usando um lock global."""
    recognizer = sr.Recognizer()
    recognizer.pause_threshold = PAUSE_THRESHOLD
    recognizer.dynamic_energy_threshold = True

    try:
        with _mic_lock:
            with sr.Microphone() as source:
                # Calibração ultrarrápida para evitar lentidão
                recognizer.adjust_for_ambient_noise(source, duration=CALIBRATION_DURATION)
                logger.debug("Microfone pronto.")
                
                audio = recognizer.listen(source, timeout=timeout_wait, phrase_time_limit=phrase_limit)
                text = recognizer.recognize_google(audio, language=VOICE_LANGUAGE)
                return text.strip()
    except sr.WaitTimeoutError:
        return None
    except sr.UnknownValueError:
        return None
    except Exception as e:
        if "Audio source must be entered" not in str(e):
            logger.debug(f"Aviso microfone: {e}")
        return None

def listen_for_interrupt(timeout_wait=4):
    """Escuta curta para detectar interrupções durante a fala."""
    return listen(timeout_wait=timeout_wait, phrase_limit=5)
