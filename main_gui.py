# ============================================================
# main_gui.py — Orquestrador Neural v4.1 (Final)
# ============================================================

import sys
import os
import threading
import time
import logging
import queue
import asyncio

# Configuração de Logs
log_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assistant_debug.log")
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(log_file, encoding="utf-8"), logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("VoiceAssistant")

from gui import AssistantGUI
from ai_engine import AIEngine
from voice_output import VoiceOutput
from voice_input import listen, listen_for_interrupt
from config import WAKE_WORDS, WAKE_RESPONSE, ASSISTANT_NAME, INTERRUPT_PHRASES

_is_speaking_flag = threading.Event()

def main():
    try:
        if sys.platform == 'win32':
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

        ai = AIEngine()
        voice = VoiceOutput()
        app = AssistantGUI(ai_engine=ai, voice_output=voice)

        def speak_with_listener(text):
            if app.pause_speaking_event.is_set(): return
            
            stop_ev = threading.Event()
            _is_speaking_flag.set()
            app.set_status("speaking", "SISTEMA TRANSMITINDO...", "#00f5ff")

            def v_thread():
                try:
                    voice.speak_raw(text, stop_event=stop_ev)
                finally:
                    stop_ev.set()
                    _is_speaking_flag.clear()
                    if not app.pause_listening_event.is_set():
                        app.set_status("waiting", "NÚCLEO ONLINE", "#00ff88")
                    else:
                        app.set_status("paused", "ESCUTA PAUSADA", "#ff9900")

            def l_thread():
                while not stop_ev.is_set():
                    if app.pause_listening_event.is_set():
                        time.sleep(0.5); continue
                    snip = listen_for_interrupt()
                    if snip and any(p in snip.lower() for p in INTERRUPT_PHRASES + ["ok assistente", "pare"]):
                        stop_ev.set()
                        voice.stop()
                        break

            threading.Thread(target=v_thread, daemon=True).start()
            threading.Thread(target=l_thread, daemon=True).start()

        def process_command(txt, from_typing=False):
            if not txt: return
            if not from_typing: app.add_message("user", txt)
            app.set_status("thinking", "PROCESSANDO NEURAL...", "#4488ff")
            
            def run():
                try:
                    spoken, display = ai.process(txt)
                    app.update_engine(ai.current_engine)
                    app.add_message("assistant", display or spoken)
                    speak_with_listener(spoken)
                    ai.add_to_history(txt, spoken)
                except Exception as e:
                    logger.error(f"Erro no processamento: {e}")
                    app.add_message("assistant", "ERRO DE CONEXÃO NEURAL.")
            
            threading.Thread(target=run, daemon=True).start()

        def background_loop():
            is_awake = False
            while not app.stop_event.is_set():
                try:
                    # Comandos da Fila (Texto ou Anexo)
                    try:
                        t = app.command_queue.get_nowait()
                        if t: 
                            is_awake = True
                            process_command(t, from_typing=True)
                            continue
                    except queue.Empty: pass

                    if _is_speaking_flag.is_set():
                        time.sleep(0.1); continue

                    # Escuta por Voz
                    if not app.pause_listening_event.is_set():
                        app.set_status("listening" if is_awake else "waiting", "ESCUTANDO..." if is_awake else "AGUARDANDO...", "#ff003c" if is_awake else "#00ff88")
                        rec = listen()
                        if rec:
                            if not is_awake:
                                if any(w in rec.lower() for w in WAKE_WORDS):
                                    is_awake = True
                                    app.add_message("assistant", WAKE_RESPONSE)
                                    voice.speak(WAKE_RESPONSE)
                            else:
                                process_command(rec)
                    else:
                        # Se pausado, apenas aguarda
                        time.sleep(0.5)
                except Exception as e:
                    logger.error(f"Erro no loop: {e}")
                    time.sleep(0.5)

        threading.Thread(target=background_loop, daemon=True).start()
        app.mainloop()
    except Exception as e:
        logger.critical(f"FALHA CRÍTICA: {e}")

if __name__ == "__main__":
    main()
