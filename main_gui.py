# ============================================================
# main_gui.py — Orquestrador Principal do Zerachiel v3.3
#
# CORREÇÕES v3.3:
#   1. is_exit_command usa EXIT_PHRASES do config — frases completas
#      exigidas para evitar encerramento acidental ao mencionar
#      "encerrar" em qualquer contexto de conversa.
#   2. listener_thread na escuta paralela NÃO processa comandos
#      muito curtos (< 6 chars) capturados pelo microfone ambiente.
#   3. Fragmentos capturados durante SPEAKING são descartados se
#      contiverem palavras de comando parciais sem contexto.
# ============================================================

import sys
import os
import threading
import time
import logging
import queue

log_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assistant_debug.log")
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(log_file, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("VoiceAssistant")

from gui import AssistantGUI
from ai_engine import AIEngine
from voice_output import VoiceOutput
from voice_input import listen, listen_for_interrupt
from config import (
    WAKE_WORDS,
    WAKE_RESPONSE,
    ASSISTANT_NAME,
    INTERRUPT_PHRASES,
    PAUSE_PHRASES,
    EXIT_PHRASES,
    SLEEP_AFTER_IDLE,
)

# Flag global: True = assistente falando, loop principal suspende listen()
_is_speaking_flag = threading.Event()


# ── Helpers ──────────────────────────────────────────────────

def _normalize(text: str) -> str:
    return text.lower().strip()


def is_interrupt_command(text: str) -> bool:
    if not text:
        return False
    t = _normalize(text)
    return any(p in t for p in INTERRUPT_PHRASES)


def is_pause_command(text: str) -> bool:
    if not text:
        return False
    t = _normalize(text)
    return any(p in t for p in PAUSE_PHRASES)


def is_exit_command(text: str) -> bool:
    """
    CORRIGIDO v3.3: exige frases completas de EXIT_PHRASES.
    Antes: checava só 'encerrar' ou 'finalizar' → encerrava ao
    falar 'escreva um programa para encerrar processo' etc.
    Agora: só encerra com 'ok assistente encerrar', 'finalizar zerachiel', etc.
    """
    if not text:
        return False
    t = _normalize(text)
    return any(phrase in t for phrase in EXIT_PHRASES)


def extract_wake_word_match(text: str):
    t = _normalize(text)
    for wake in sorted(WAKE_WORDS, key=len, reverse=True):
        if wake in t:
            remainder = t.replace(wake, "", 1).strip(" .,!?-")
            return wake, remainder
    return None, None


# ── Main ──────────────────────────────────────────────────────

def main():
    try:
        logger.info(f"Iniciando {ASSISTANT_NAME}...")

        ai    = AIEngine()
        voice = VoiceOutput()
        app   = AssistantGUI(ai_engine=ai, voice_output=voice)

        def do_interrupt():
            voice.stop()
            _is_speaking_flag.clear()
            app.set_status("waiting", "Interrompido — pode falar", "#ff9900")
            logger.info("Interrupção executada.")

        # ── Fala com escuta paralela ──────────────────────────
        def speak_with_listener(spoken_text: str):
            stop_speaking  = threading.Event()
            new_cmd_buffer = []
            _is_speaking_flag.set()

            def voice_thread():
                voice.speak_raw(spoken_text, stop_event=stop_speaking)
                stop_speaking.set()

            def listener_thread():
                while not stop_speaking.is_set():
                    snippet = listen_for_interrupt(timeout_wait=4)
                    if not snippet:
                        continue

                    logger.info(f"[Escuta paralela] Capturado: '{snippet}'")

                    # Descarta fragmentos muito curtos — ruído ou eco do alto-falante
                    if len(snippet) < 4:
                        logger.debug(f"[Escuta paralela] Descartado (muito curto): '{snippet}'")
                        continue

                    if is_interrupt_command(snippet):
                        stop_speaking.set()
                        voice.stop()
                        do_interrupt()
                        return

                    if is_pause_command(snippet):
                        stop_speaking.set()
                        voice.stop()
                        _is_speaking_flag.clear()
                        app.set_status("waiting", "⏸ Pausado — pode perguntar", "#ff9900")
                        app.add_message("status", "Pausado. Pode fazer outra pergunta.")
                        logger.info("Fala pausada pelo usuário.")
                        return

                    # Novo comando durante fala: mínimo 8 chars para evitar
                    # fragmentos aleatórios do áudio ambiente serem processados
                    if len(snippet) >= 8:
                        stop_speaking.set()
                        voice.stop()
                        new_cmd_buffer.append(snippet)
                        logger.info(f"[Escuta paralela] Novo comando: '{snippet}'")
                        return
                    else:
                        logger.debug(f"[Escuta paralela] Descartado (fragmento curto): '{snippet}'")

            t_voice    = threading.Thread(target=voice_thread,    daemon=True)
            t_listener = threading.Thread(target=listener_thread, daemon=True)
            t_voice.start()
            t_listener.start()
            t_voice.join()
            stop_speaking.set()
            _is_speaking_flag.clear()
            logger.debug("SPEAKING encerrado — microfone devolvido ao loop principal.")

            if new_cmd_buffer:
                process_command(new_cmd_buffer[0])

        # ── Processamento de Comando ──────────────────────────
        def process_command(user_text: str):
            if not user_text or not user_text.strip():
                return

            if is_exit_command(user_text):
                msg = "Encerrando o sistema. Até logo!"
                app.add_message("assistant", msg)
                app.set_status("speaking", "Saindo...", "#ff003c")
                voice.speak(msg)
                time.sleep(2)
                app.on_closing()
                return

            app.add_message("user", user_text)
            app.set_status("thinking", f"{ASSISTANT_NAME} processando...", "#4488ff")

            def run_ai():
                try:
                    spoken, display = ai.process(user_text)
                    display_text = display or spoken
                    app.add_message("assistant", display_text)
                    app.set_status("speaking", f"{ASSISTANT_NAME} falando...", "#bf00ff")
                    speak_with_listener(spoken)
                    ai.add_to_history(user_text, spoken)
                    app.set_status("waiting", "Pode falar...", "#00ff88")
                except Exception as e:
                    logger.error(f"Erro na IA: {e}", exc_info=True)
                    _is_speaking_flag.clear()
                    app.set_status("waiting", "Erro — pode falar novamente", "#ff003c")

            threading.Thread(target=run_ai, daemon=True).start()

        # ── Loop Principal ────────────────────────────────────
        def assistant_loop():
            logger.info("Thread de monitoramento iniciada.")
            is_awake      = False
            last_activity = time.time()

            while not app.stop_event.is_set():

                # Prioridade 1: texto digitado na GUI
                # Digitar qualquer coisa acorda o assistente automaticamente
                # sem precisar clicar no botão Iniciar ou falar wake word
                try:
                    cmd_text = app.command_queue.get_nowait()
                    if cmd_text and cmd_text.strip():
                        if not is_awake:
                            is_awake = True
                            logger.info("Zerachiel acordado via texto digitado.")
                            app.set_status("waiting", "Zerachiel: Pronto", "#00ff88")
                            # Atualiza botão se ainda não foi clicado
                            try:
                                app.after(0, lambda: app.start_button.configure(
                                    state="disabled",
                                    text="◉  ATIVO",
                                    text_color="#00f5ff",
                                    border_color="#00f5ff",
                                ))
                            except Exception:
                                pass
                        last_activity = time.time()
                        process_command(cmd_text)
                        continue
                except queue.Empty:
                    pass

                # Suspende durante SPEAKING
                if _is_speaking_flag.is_set():
                    time.sleep(0.1)
                    continue

                # Auto-sleep
                if is_awake and (time.time() - last_activity > SLEEP_AFTER_IDLE):
                    is_awake = False
                    logger.info("Zerachiel voltou ao modo standby.")
                    app.set_status("waiting", f"Diga '{WAKE_WORDS[0]}'...", "#00ff88")

                # Ativação via botão GUI
                try:
                    if "Zerachiel: Pronto" in app.status_label.cget("text") and not is_awake:
                        is_awake      = True
                        last_activity = time.time()
                        logger.info("Zerachiel acordado via botão GUI.")
                except Exception:
                    pass

                # Status visual
                if is_awake:
                    app.set_status("listening", "Ouvindo...", "#ff003c")
                else:
                    app.set_status("waiting", f"Diga '{WAKE_WORDS[0]}'...", "#00ff88")

                # Escuta turno completo
                recognized = listen()

                if not recognized:
                    status_txt = "Pode falar..." if is_awake else f"Diga '{WAKE_WORDS[0]}'..."
                    app.set_status("waiting", status_txt, "#00ff88")
                    continue

                logger.info(f"Microfone captou: '{recognized}'")

                # Interrupção tem prioridade
                if is_interrupt_command(recognized):
                    do_interrupt()
                    continue

                # MODO DORMINDO
                if not is_awake:
                    matched_wake, remainder = extract_wake_word_match(recognized)
                    if matched_wake:
                        is_awake      = True
                        last_activity = time.time()
                        logger.info(f"Wake word detectada: '{matched_wake}'")
                        if remainder and len(remainder) > 3:
                            logger.info(f"Comando junto à wake word: '{remainder}'")
                            app.add_message("assistant", WAKE_RESPONSE)
                            def _greet_and_process(cmd=remainder):
                                voice.speak(WAKE_RESPONSE)
                                process_command(cmd)
                            threading.Thread(target=_greet_and_process, daemon=True).start()
                        else:
                            app.add_message("assistant", WAKE_RESPONSE)
                            threading.Thread(
                                target=lambda: voice.speak(WAKE_RESPONSE),
                                daemon=True
                            ).start()
                    else:
                        logger.debug(f"Ignorado (dormindo, sem wake word): '{recognized}'")
                    continue

                # MODO ACORDADO
                last_activity = time.time()
                process_command(recognized)

        threading.Thread(target=assistant_loop, daemon=True).start()
        app.mainloop()

    except Exception as e:
        logger.critical(f"FALHA CRÍTICA: {e}", exc_info=True)
    finally:
        logger.info("Aplicação finalizada.")


if __name__ == "__main__":
    main()
