# ============================================================
# voice_input.py — Gerenciador de Microfone (Zerachiel v3.1)
#
# ARQUITETURA: FILA ÚNICA DE MICROFONE
#   Problema anterior: listen() no loop principal + listen_short()
#   na escuta paralela rodavam SIMULTANEAMENTE, competindo pelo
#   mesmo microfone → cortes, transcrições quebradas, comandos
#   capturados pela thread errada.
#
#   Solução: _mic_lock (threading.Lock) garante que APENAS UMA
#   thread grava por vez. listen_for_interrupt() usa o mesmo lock —
#   enquanto o loop principal escuta, ela aguarda. Nunca há conflito.
#
# LÓGICA DE FIM DE TURNO (inspirada no Speakly / Copilot):
#   - Grava enquanto há fala (dynamic_energy_threshold adapta ao ambiente)
#   - Para quando detecta PAUSE_THRESHOLD segundos de silêncio
#   - Sem phrase_time_limit fixo → frases longas funcionam normalmente
# ============================================================

import speech_recognition as sr
import logging
import threading

from config import VOICE_LANGUAGE, PAUSE_THRESHOLD

logger = logging.getLogger("VoiceAssistant")

# ── Semáforo global — garante UMA SÓ gravação por vez ──────────
# Elimina o conflito entre loop principal e escuta paralela.
_mic_lock = threading.Lock()


def listen(
    pause_threshold: float = None,
    timeout_wait: int = 8,
    phrase_limit: int = 120,
) -> str | None:
    """
    Captura um turno completo de fala e retorna o texto reconhecido.

    COMO FUNCIONA:
    - Adquire _mic_lock (acesso exclusivo ao microfone).
    - Aguarda até `timeout_wait` segundos para o usuário começar a falar.
    - Grava continuamente enquanto há fala.
    - Para quando detecta `pause_threshold` segundos de silêncio contínuo.
    - Frases longas (explanações, comandos detalhados) funcionam normalmente.
    - Retorna None se ninguém falar ou se o áudio for ininteligível.

    Args:
        pause_threshold : segundos de silêncio = fim do turno.
                          None -> usa PAUSE_THRESHOLD do config.py (2.5s)
        timeout_wait    : segundos aguardando início de fala antes de desistir.
        phrase_limit    : teto de segurança em segundos (120s padrão).
    """
    _pause = pause_threshold if pause_threshold is not None else PAUSE_THRESHOLD

    with _mic_lock:  # acesso exclusivo; qualquer outra chamada aguarda aqui
        recognizer = sr.Recognizer()

        # Configuração baseada em detecção de silêncio
        recognizer.pause_threshold          = _pause
        recognizer.non_speaking_duration    = min(_pause, 0.8)
        recognizer.phrase_threshold         = 0.3
        recognizer.dynamic_energy_threshold = True

        with sr.Microphone() as source:
            try:
                # Calibração ao ruído ambiente (0.5s melhora muito a precisão)
                recognizer.adjust_for_ambient_noise(source, duration=0.5)
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
    """
    Escuta um comando curto de controle DURANTE a fala do assistente.

    DIFERENÇAS do listen() principal:
    - pause_threshold = 0.8s  (mais curto — "pare", "espera" são palavras únicas)
    - phrase_limit    = 8s    (comandos de controle são sempre curtos)
    - USA O MESMO _mic_lock: se o loop principal estiver escutando,
      aguarda. NUNCA há gravações simultâneas.

    FLUXO DE USO:
    - Chamada apenas por speak_with_listener() em main_gui.py.
    - O loop principal PARA de chamar listen() durante SPEAKING,
      então na prática _mic_lock sempre está livre aqui.
    """
    return listen(
        pause_threshold=0.8,
        timeout_wait=timeout_wait,
        phrase_limit=8,
    )
