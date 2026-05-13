# ============================================================
# voice_input.py — Gerenciador de Microfone (Zerachiel v3.3)
#
# CORREÇÃO v3.3: usa CALIBRATION_DURATION do config.py (0.2s)
# em vez do valor fixo anterior (0.5s), reduzindo a latência
# acumulada no loop de standby de até 60s para < 10s.
# ============================================================

import speech_recognition as sr
import logging
import threading

from config import VOICE_LANGUAGE, PAUSE_THRESHOLD, CALIBRATION_DURATION

logger = logging.getLogger("VoiceAssistant")

_mic_lock = threading.Lock()


def listen(
    pause_threshold: float = None,
    timeout_wait: int = 7,
    phrase_limit: int = 120,
) -> str | None:
    _pause = pause_threshold if pause_threshold is not None else PAUSE_THRESHOLD

    with _mic_lock:
        recognizer = sr.Recognizer()
        recognizer.pause_threshold          = _pause
        recognizer.non_speaking_duration    = min(_pause, 0.6)
        recognizer.phrase_threshold         = 0.3
        recognizer.dynamic_energy_threshold = True

        with sr.Microphone() as source:
            try:
                # Calibração curta — CALIBRATION_DURATION=0.2s padrão
                recognizer.adjust_for_ambient_noise(source, duration=CALIBRATION_DURATION)
                logger.debug("Microfone ativo — aguardando fala...")

                audio = recognizer.listen(
                    source,
                    timeout=timeout_wait,
                    phrase_time_limit=phrase_limit,
                )

                text = recognizer.recognize_google(audio, language=VOICE_LANGUAGE)
                text = text.strip()
                logger.info(f"Reconhecido: '{text}'")
                return text

            except sr.WaitTimeoutError:
                logger.debug("Timeout: nenhuma fala detectada.")
                return None
            except sr.UnknownValueError:
                logger.debug("Áudio não compreendido.")
                return None
            except sr.RequestError as e:
                logger.error(f"Erro no Google STT: {e}")
                return None
            except Exception as e:
                logger.error(f"Erro inesperado no listen(): {e}", exc_info=True)
                return None


def listen_for_interrupt(timeout_wait: int = 4) -> str | None:
    """Escuta comandos curtos de controle durante a fala do assistente."""
    return listen(
        pause_threshold=0.8,
        timeout_wait=timeout_wait,
        phrase_limit=8,
    )
