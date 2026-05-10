# ============================================================
# main_gui.py — Orquestrador Principal do Zerachiel
# Conecta: Interface (GUI) ↔ Motor de IA ↔ Voz (entrada/saída)
#
# MÁQUINA DE ESTADOS:
#   SLEEPING  → aguarda wake word; ignora todo o resto
#   AWAKE     → processa comandos; monitora inatividade
#   SPEAKING  → assistente falando; escuta em paralelo por
#               pausa, interrupção ou novo comando
# ============================================================

import sys
import os
import threading
import time
import logging
import queue
from datetime import datetime

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
from voice_input import listen, listen_short
from config import (
    WAKE_WORDS,
    WAKE_RESPONSE,
    ASSISTANT_NAME,
    INTERRUPT_PHRASES,
    PAUSE_PHRASES,
    RESUME_PHRASES,
    SLEEP_AFTER_IDLE,
)


# ── Helpers de Classificação de Comandos ─────────────────────

def _normalize(text: str) -> str:
    """Remove espaços extras e converte para minúsculas."""
    return text.lower().strip()


def is_interrupt_command(text: str) -> bool:
    """Retorna True se o texto for um comando de parada total."""
    if not text:
        return False
    t = _normalize(text)
    return any(p in t for p in INTERRUPT_PHRASES)


def is_pause_command(text: str) -> bool:
    """Retorna True se o texto for um comando de pausa temporária."""
    if not text:
        return False
    t = _normalize(text)
    return any(p in t for p in PAUSE_PHRASES)


def is_resume_command(text: str) -> bool:
    """Retorna True se o texto for um comando para retomar."""
    if not text:
        return False
    t = _normalize(text)
    return any(p in t for p in RESUME_PHRASES)


def is_exit_command(text: str) -> bool:
    """Retorna True se o texto for um comando de encerramento do sistema."""
    if not text:
        return False
    t = _normalize(text)
    return "pode finalizar zerachiel" in t or "finalizar zerachiel" in t


def extract_wake_word_match(text: str):
    """
    Verifica se o texto contém alguma wake word.
    Retorna (wake_word_encontrada, comando_restante) ou (None, None).
    O comando_restante é o que o usuário disse APÓS a wake word —
    permite processar "Zerachiel, que horas são?" em um único turno.
    """
    t = _normalize(text)
    for wake in sorted(WAKE_WORDS, key=len, reverse=True):  # testa frases mais longas primeiro
        if wake in t:
            # Remove a wake word e obtém o restante
            remainder = t.replace(wake, "", 1).strip(" .,!?")
            return wake, remainder
    return None, None


# ── Função Principal ─────────────────────────────────────────

def main():
    try:
        # ── Inicialização dos Componentes ────────────────────
        logger.info(f"Iniciando {ASSISTANT_NAME}...")
        ai    = AIEngine()
        voice = VoiceOutput()
        app   = AssistantGUI(ai_engine=ai, voice_output=voice)

        # ── Callback de Interrupção Total ────────────────────
        def do_interrupt():
            """Para a fala imediatamente e volta ao modo aguardando."""
            voice.stop()
            app.set_status("waiting", "Interrompido — pode falar", "yellow")
            logger.info("Interrupção executada.")

        # ── Processamento de Comando pela IA ─────────────────
        def process_command(user_text: str):
            """
            Envia o texto para a IA, recebe (spoken, display),
            exibe na GUI e fala a resposta com escuta paralela.
            """
            if not user_text or not user_text.strip():
                return

            # Comando especial de saída
            if is_exit_command(user_text):
                final_msg = "Encerrando o sistema. Até logo!"
                app.add_message("assistant", final_msg)
                app.set_status("speaking", "Saindo...", "red")
                voice.speak(final_msg)
                time.sleep(2)
                app.on_closing()
                return

            app.add_message("user", user_text)
            app.set_status("thinking", f"{ASSISTANT_NAME} pensando...", "blue")

            def run_ai():
                try:
                    spoken, display = ai.process(user_text)
                    display_text = display or spoken

                    # Exibe na GUI
                    app.add_message("assistant", display_text)
                    app.set_status("speaking", f"{ASSISTANT_NAME} falando...", "purple")

                    # Fala com escuta paralela por interrupção/pausa/novo comando
                    speak_with_listener(spoken)

                    # Registra no histórico da IA
                    ai.add_to_history(user_text, spoken)
                    app.set_status("waiting", "Pode falar...", "green")

                except Exception as e:
                    logger.error(f"Erro na IA: {e}", exc_info=True)
                    app.set_status("waiting", "Erro no processamento", "red")

            threading.Thread(target=run_ai, daemon=True).start()

        # ── Fala com Escuta Paralela (Etapa 2) ───────────────
        def speak_with_listener(spoken_text: str):
            """
            Fala o texto enquanto uma thread paralela escuta por:
              - Comando de PAUSA  → para o áudio, mantém AWAKE, aguarda instrução
              - Comando de INTERRUPT → para o áudio e limpa estado
              - Novo COMANDO      → para o áudio e processa o novo pedido

            Diferença pausa vs interrupção:
              - Pausa:       para a fala, aguarda "continue" ou novo comando
              - Interrupção: para a fala e DESCARTA o contexto (como antes)
            """
            stop_speaking   = threading.Event()
            new_cmd_buffer  = []   # armazena novo comando capturado durante a fala

            def voice_thread():
                """Reproduz o áudio e verifica stop_speaking a cada 0.1s."""
                voice.speak_raw(spoken_text, stop_event=stop_speaking)

            def listener_thread():
                """Escuta com timeout curto enquanto o assistente fala."""
                while not stop_speaking.is_set():
                    snippet = listen_short(timeout_wait=2)
                    if not snippet:
                        continue

                    logger.info(f"[Escuta paralela] Capturado: '{snippet}'")

                    if is_interrupt_command(snippet):
                        stop_speaking.set()
                        voice.stop()
                        do_interrupt()
                        return

                    if is_pause_command(snippet):
                        stop_speaking.set()
                        voice.stop()
                        app.set_status("waiting", "⏸ Pausado — pode perguntar", "yellow")
                        app.add_message("status", "Fala pausada. Pode fazer outra pergunta.")
                        logger.info("Fala pausada pelo usuário.")
                        # Fica aguardando um novo comando (sem sair do loop principal)
                        return

                    # Novo comando durante a fala: para e processa
                    if len(snippet) > 3:
                        stop_speaking.set()
                        voice.stop()
                        new_cmd_buffer.append(snippet)
                        return

            t_voice    = threading.Thread(target=voice_thread,    daemon=True)
            t_listener = threading.Thread(target=listener_thread, daemon=True)

            t_voice.start()
            t_listener.start()
            t_voice.join()      # espera o áudio terminar (ou ser interrompido)
            stop_speaking.set() # garante que listener_thread encerra junto

            # Se um novo comando foi capturado durante a fala, processa agora
            if new_cmd_buffer:
                process_command(new_cmd_buffer[0])

        # ── Loop Principal de Escuta ──────────────────────────
        def assistant_loop():
            """
            Thread permanente que gerencia a máquina de estados:
              SLEEPING → AWAKE → processa comandos → auto-sleep
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

                # ── Auto-sleep por inatividade ────────────────
                if is_awake and (time.time() - last_activity > SLEEP_AFTER_IDLE):
                    is_awake = False
                    logger.info("Zerachiel voltou ao modo standby (inatividade).")
                    app.set_status("waiting", f"Diga '{WAKE_WORDS[0]}'...", "green")

                # ── Verifica se botão GUI foi clicado ─────────
                # O botão "Iniciar Zerachiel" chama activate_assistant(),
                # que define o status para "Zerachiel: Pronto".
                # Isso acorda o assistente sem precisar da wake word.
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

                # ── Escuta um turno de fala ───────────────────
                # Bloqueia até detectar pausa longa ou timeout
                recognized = listen()

                if not recognized:
                    # Ninguém falou — atualiza status e volta ao topo do loop
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

                        # Verifica se há comando junto com a wake word
                        # Ex: "Zerachiel, que horas são?" → processa "que horas são?"
                        if remainder and len(remainder) > 3:
                            logger.info(f"Comando junto à wake word: '{remainder}'")
                            # Responde brevemente e já processa o comando
                            app.add_message("assistant", WAKE_RESPONSE)
                            def greet_and_process(cmd=remainder):
                                voice.speak(WAKE_RESPONSE)
                                process_command(cmd)
                            threading.Thread(target=greet_and_process, daemon=True).start()
                        else:
                            # Só wake word, sem comando: responde e aguarda
                            app.add_message("assistant", WAKE_RESPONSE)
                            threading.Thread(
                                target=lambda: voice.speak(WAKE_RESPONSE),
                                daemon=True
                            ).start()
                    else:
                        # Texto captado mas sem wake word — ignora silenciosamente
                        logger.debug(f"Ignorado (modo dormindo, sem wake word): '{recognized}'")
                    continue

                # ── MODO ACORDADO: processa qualquer comando ──
                last_activity = time.time()
                process_command(recognized)

        # ── Inicia Threads e GUI ──────────────────────────────
        threading.Thread(target=assistant_loop, daemon=True).start()
        app.mainloop()

    except Exception as e:
        logger.critical(f"FALHA CRÍTICA NO SISTEMA: {e}", exc_info=True)
    finally:
        logger.info("Aplicação finalizada.")


if __name__ == "__main__":
    main()
