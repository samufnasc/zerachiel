# ============================================================
# main_gui.py — Orquestrador Principal do Zerachiel v3.1
#
# MÁQUINA DE ESTADOS:
#   SLEEPING  → aguarda wake word; ignora todo o resto
#   AWAKE     → processa comandos do usuário
#   SPEAKING  → assistente falando; loop principal PARA listen();
#               escuta paralela assume com listen_for_interrupt()
#
# CORREÇÃO v3.1:
#   O loop principal agora usa _is_speaking_flag para saber quando
#   o assistente está falando e SUSPENDE listen() nesse período.
#   Isso elimina o conflito de duas threads gravando ao mesmo tempo,
#   que causava cortes e transcrições quebradas.
# ============================================================

import sys
import os
import threading
import time
import logging
import queue

# ── Configuração de Logs ─────────────────────────────────────
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

# ── Importações do Projeto ───────────────────────────────────
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
    SLEEP_AFTER_IDLE,
)


# ── Estado global de fala ─────────────────────────────────────
# Quando True, o loop principal NÃO chama listen() e cede o
# microfone para a escuta paralela de listen_for_interrupt().
_is_speaking_flag = threading.Event()


# ── Helpers de Classificação ──────────────────────────────────

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
    if not text:
        return False
    t = _normalize(text)
    return "pode finalizar zerachiel" in t or "finalizar zerachiel" in t


def extract_wake_word_match(text: str):
    """
    Verifica se o texto contém alguma wake word.
    Retorna (wake_word_encontrada, comando_restante) ou (None, None).
    Testa frases mais longas primeiro para evitar match parcial.
    Ex: "olá zerachiel me diga a hora" → wake='olá zerachiel', remainder='me diga a hora'
    """
    t = _normalize(text)
    for wake in sorted(WAKE_WORDS, key=len, reverse=True):
        if wake in t:
            remainder = t.replace(wake, "", 1).strip(" .,!?-")
            return wake, remainder
    return None, None


# ── Função Principal ──────────────────────────────────────────

def main():
    try:
        logger.info(f"Iniciando {ASSISTANT_NAME}...")

        ai    = AIEngine()
        voice = VoiceOutput()
        app   = AssistantGUI(ai_engine=ai, voice_output=voice)

        # ─────────────────────────────────────────────────────
        # INTERRUPÇÃO TOTAL
        # ─────────────────────────────────────────────────────
        def do_interrupt():
            """Para a fala imediatamente e sinaliza fim do SPEAKING."""
            voice.stop()
            _is_speaking_flag.clear()
            app.set_status("waiting", "Interrompido — pode falar", "yellow")
            logger.info("Interrupção executada.")

        # ─────────────────────────────────────────────────────
        # FALA COM ESCUTA PARALELA
        # Chamada dentro de run_ai() (thread separada).
        # O loop principal verifica _is_speaking_flag e suspende
        # listen() enquanto esta função estiver ativa.
        # ─────────────────────────────────────────────────────
        def speak_with_listener(spoken_text: str):
            """
            Fala o texto com escuta paralela para comandos de controle.

            ESTADOS durante esta função:
              _is_speaking_flag = SET   → loop principal não chama listen()
              _is_speaking_flag = CLEAR → loop principal volta a ouvir

            COMANDOS reconhecidos durante a fala:
              - Interrupção ("pare", "chega"...) → para e descarta
              - Pausa ("espera", "aguarda"...)    → para, mantém AWAKE
              - Novo comando (qualquer outra coisa > 3 chars) → para e processa
            """
            stop_speaking  = threading.Event()
            new_cmd_buffer = []

            # Sinaliza: estou falando, loop principal suspende listen()
            _is_speaking_flag.set()

            def voice_thread():
                voice.speak_raw(spoken_text, stop_event=stop_speaking)
                stop_speaking.set()          # garante encerramento da listener_thread

            def listener_thread():
                """
                Escuta por comandos de controle enquanto o assistente fala.
                Usa listen_for_interrupt() que tem pause_threshold=0.8s
                para reagir rapidamente a palavras únicas como "pare".
                """
                while not stop_speaking.is_set():
                    snippet = listen_for_interrupt(timeout_wait=4)
                    if not snippet:
                        continue

                    logger.info(f"[Escuta paralela] Capturado: '{snippet}'")

                    # Interrupção total
                    if is_interrupt_command(snippet):
                        stop_speaking.set()
                        voice.stop()
                        do_interrupt()
                        return

                    # Pausa temporária — para a fala mas mantém AWAKE
                    if is_pause_command(snippet):
                        stop_speaking.set()
                        voice.stop()
                        _is_speaking_flag.clear()
                        app.set_status("waiting", "⏸ Pausado — pode perguntar", "yellow")
                        app.add_message("status", "Pausado. Pode fazer outra pergunta.")
                        logger.info("Fala pausada pelo usuário.")
                        return

                    # Novo comando durante a fala → interrompe e processa
                    if len(snippet) > 3:
                        stop_speaking.set()
                        voice.stop()
                        new_cmd_buffer.append(snippet)
                        logger.info(f"[Escuta paralela] Novo comando: '{snippet}'")
                        return

            t_voice    = threading.Thread(target=voice_thread,    daemon=True)
            t_listener = threading.Thread(target=listener_thread, daemon=True)

            t_voice.start()
            t_listener.start()
            t_voice.join()          # aguarda fim do áudio ou interrupção
            stop_speaking.set()     # encerra listener_thread se ainda estiver rodando

            # Libera o microfone para o loop principal
            _is_speaking_flag.clear()
            logger.debug("SPEAKING encerrado — microfone devolvido ao loop principal.")

            # Se um novo comando foi capturado durante a fala, processa
            if new_cmd_buffer:
                process_command(new_cmd_buffer[0])

        # ─────────────────────────────────────────────────────
        # PROCESSAMENTO DE COMANDO
        # ─────────────────────────────────────────────────────
        def process_command(user_text: str):
            """
            Envia o comando para a IA e fala a resposta.
            Roda em thread separada para não bloquear o loop principal.
            """
            if not user_text or not user_text.strip():
                return

            # Comando de saída
            if is_exit_command(user_text):
                msg = "Encerrando o sistema. Até logo!"
                app.add_message("assistant", msg)
                app.set_status("speaking", "Saindo...", "red")
                voice.speak(msg)
                time.sleep(2)
                app.on_closing()
                return

            app.add_message("user", user_text)
            app.set_status("thinking", f"{ASSISTANT_NAME} pensando...", "blue")

            def run_ai():
                try:
                    spoken, display = ai.process(user_text)
                    display_text = display or spoken

                    app.add_message("assistant", display_text)
                    app.set_status("speaking", f"{ASSISTANT_NAME} falando...", "purple")

                    # Fala com escuta paralela (suspende loop principal via flag)
                    speak_with_listener(spoken)

                    ai.add_to_history(user_text, spoken)
                    app.set_status("waiting", "Pode falar...", "green")

                except Exception as e:
                    logger.error(f"Erro na IA: {e}", exc_info=True)
                    _is_speaking_flag.clear()
                    app.set_status("waiting", "Erro — pode falar novamente", "red")

            threading.Thread(target=run_ai, daemon=True).start()

        # ─────────────────────────────────────────────────────
        # LOOP PRINCIPAL DE ESCUTA
        # ─────────────────────────────────────────────────────
        def assistant_loop():
            """
            Máquina de estados principal.
            SLEEPING → aguarda wake word.
            AWAKE    → processa comandos.
            SPEAKING → suspende listen(); escuta paralela assume.
            """
            logger.info("Thread de monitoramento iniciada.")

            is_awake      = False
            last_activity = time.time()

            while not app.stop_event.is_set():

                # ── Prioridade 1: texto digitado na GUI ──────
                try:
                    cmd_text = app.command_queue.get_nowait()
                    if cmd_text and cmd_text.strip():
                        is_awake      = True
                        last_activity = time.time()
                        process_command(cmd_text)
                        continue
                except queue.Empty:
                    pass

                # ── Suspende durante SPEAKING ─────────────────
                # O loop principal não chama listen() enquanto o assistente
                # fala — cede o microfone para listen_for_interrupt().
                if _is_speaking_flag.is_set():
                    time.sleep(0.1)   # poll leve, não bloqueia a GUI
                    continue

                # ── Auto-sleep por inatividade ────────────────
                if is_awake and (time.time() - last_activity > SLEEP_AFTER_IDLE):
                    is_awake = False
                    logger.info("Zerachiel voltou ao modo standby (inatividade).")
                    app.set_status("waiting", f"Diga '{WAKE_WORDS[0]}'...", "green")

                # ── Verifica ativação via botão GUI ───────────
                try:
                    current_status = app.status_label.cget("text")
                    if "Zerachiel: Pronto" in current_status and not is_awake:
                        is_awake      = True
                        last_activity = time.time()
                        logger.info("Zerachiel acordado via botão GUI.")
                except Exception:
                    pass

                # ── Atualiza status visual ────────────────────
                if is_awake:
                    app.set_status("listening", "Ouvindo...", "red")
                else:
                    app.set_status("waiting", f"Diga '{WAKE_WORDS[0]}'...", "green")

                # ── Escuta um turno completo ──────────────────
                # listen() usa pause_threshold=2.5s → aguarda pausa longa
                # para considerar o turno encerrado.
                recognized = listen()

                if not recognized:
                    status_txt = "Pode falar..." if is_awake else f"Diga '{WAKE_WORDS[0]}'..."
                    app.set_status("waiting", status_txt, "green")
                    continue

                logger.info(f"Microfone captou: '{recognized}'")

                # ── Interrupção tem prioridade máxima ─────────
                if is_interrupt_command(recognized):
                    do_interrupt()
                    continue

                # ── MODO DORMINDO: procura wake word ──────────
                if not is_awake:
                    matched_wake, remainder = extract_wake_word_match(recognized)

                    if matched_wake:
                        is_awake      = True
                        last_activity = time.time()
                        logger.info(f"Wake word detectada: '{matched_wake}'")

                        if remainder and len(remainder) > 3:
                            # Wake word + comando na mesma fala → processa tudo
                            logger.info(f"Comando junto à wake word: '{remainder}'")
                            app.add_message("assistant", WAKE_RESPONSE)
                            def _greet_and_process(cmd=remainder):
                                voice.speak(WAKE_RESPONSE)
                                process_command(cmd)
                            threading.Thread(target=_greet_and_process, daemon=True).start()
                        else:
                            # Só wake word → responde e aguarda próximo turno
                            app.add_message("assistant", WAKE_RESPONSE)
                            threading.Thread(
                                target=lambda: voice.speak(WAKE_RESPONSE),
                                daemon=True
                            ).start()
                    else:
                        logger.debug(f"Ignorado (modo dormindo, sem wake word): '{recognized}'")
                    continue

                # ── MODO ACORDADO: processa o comando ─────────
                last_activity = time.time()
                process_command(recognized)

        # ── Inicia tudo ───────────────────────────────────────
        threading.Thread(target=assistant_loop, daemon=True).start()
        app.mainloop()

    except Exception as e:
        logger.critical(f"FALHA CRÍTICA NO SISTEMA: {e}", exc_info=True)
    finally:
        logger.info("Aplicação finalizada.")


if __name__ == "__main__":
    main()
