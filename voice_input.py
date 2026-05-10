# ============================================================
# voice_input.py — Captura de Áudio (Zerachiel)
# Lógica baseada em PAUSA DE SILÊNCIO (estilo Speakly):
#   - Grava enquanto o usuário fala
#   - Finaliza o turno quando detecta pausa longa (pause_threshold)
#   - Suporta frases longas sem corte por tempo fixo
# ============================================================

import speech_recognition as sr
import logging

from config import VOICE_LANGUAGE, PAUSE_THRESHOLD

logger = logging.getLogger("VoiceAssistant")


def listen(
    pause_threshold: float = None,
    timeout_wait: int = 8,
    phrase_limit: int = 120,
) -> str | None:
    """
    Grava áudio do microfone e retorna o texto reconhecido.

    Comportamento:
    - Aguarda até `timeout_wait` segundos para o usuário começar a falar.
    - Uma vez que o usuário começa, grava até detectar `pause_threshold`
      segundos de silêncio contínuo — NÃO há corte por tempo fixo.
    - Frases longas (como explicações detalhadas) funcionam normalmente.
    - Retorna None se ninguém falar ou se o áudio for ininteligível.

    Args:
        pause_threshold: segundos de silêncio que indicam fim do turno.
                         Se None, usa o valor de config.py (PAUSE_THRESHOLD).
        timeout_wait:    segundos esperando início da fala (retorna None se expirar).
        phrase_limit:    teto de segurança em segundos (evita gravação infinita).
    """
    # Usa o valor do config.py se não for passado explicitamente
    _pause = pause_threshold if pause_threshold is not None else PAUSE_THRESHOLD

    recognizer = sr.Recognizer()

    # Configuração baseada em silêncio (chave da lógica Speakly)
    recognizer.pause_threshold = _pause          # pausa longa = fim do turno
    recognizer.phrase_threshold = 0.3            # mínimo para considerar fala
    recognizer.non_speaking_duration = 0.3       # ajuste fino de ruído
    recognizer.dynamic_energy_threshold = True   # adapta automaticamente ao ambiente

    with sr.Microphone() as source:
        try:
            # Calibração rápida (0.3s) — suficiente sem bloquear muito a GUI
            logger.debug("Calibrando ruído ambiente...")
            recognizer.adjust_for_ambient_noise(source, duration=0.3)
            logger.debug("Microfone ativo — aguardando fala...")

            # Aguarda início de fala; se ninguém falar em timeout_wait → retorna None
            audio = recognizer.listen(
                source,
                timeout=timeout_wait,
                phrase_time_limit=phrase_limit,   # teto de segurança, não corte fixo
            )

            # Envia para Google STT (gratuito, sem API key, excelente em pt-BR)
            text = recognizer.recognize_google(audio, language=VOICE_LANGUAGE)
            text = text.strip()
            logger.info(f"Reconhecido: '{text}'")
            return text

        except sr.WaitTimeoutError:
            # Ninguém falou dentro do timeout — comportamento normal, não é erro
            logger.debug("Timeout: nenhuma fala detectada.")
            return None

        except sr.UnknownValueError:
            # Áudio captado mas ininteligível (barulho, voz baixa, etc.)
            logger.debug("Reconhecimento: áudio não compreendido.")
            return None

        except sr.RequestError as e:
            # Erro de conexão com o Google STT
            logger.error(f"Erro no serviço de reconhecimento: {e}")
            return None

        except Exception as e:
            logger.error(f"Erro inesperado no listen(): {e}")
            return None


def listen_short(timeout_wait: int = 3) -> str | None:
    """
    Versão rápida para detectar interrupções durante a fala do assistente.
    Usa pause_threshold menor (0.6s) para resposta mais ágil.
    Usada pela thread de escuta paralela em main_gui.py.
    """
    return listen(
        pause_threshold=0.6,
        timeout_wait=timeout_wait,
        phrase_limit=10,    # comandos de pausa são curtos
    )
