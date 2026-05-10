# ============================================================
# main_gui.py - Ponto de Entrada Principal (Orquestrador)
# Responsável por conectar Interface, IA e Voz.
# ============================================================

import sys
import os
import threading
import time
import logging
import queue
from datetime import datetime

# Configuração de Logs
log_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assistant_debug.log")
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(log_file, encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("VoiceAssistant")

# Importações do Projeto
from gui import AssistantGUI
from ai_engine import AIEngine
from voice_output import VoiceOutput
from voice_input import listen
from config import (
    WAKE_WORDS, 
    WAKE_RESPONSE, 
    ASSISTANT_NAME, 
    VOICE_LANGUAGE
)

# Comandos de Interrupção
INTERRUPT_PHRASES = ["certo assistente", "pode parar", "pare", "chega", "silêncio", "stop", "para"]

def is_interrupt_command(text):
    if not text: return False
    txt = text.lower().strip()
    return any(p in txt for p in INTERRUPT_PHRASES)

def main():
    try:
        # Inicialização dos Componentes
        ai = AIEngine()
        voice = VoiceOutput()
        app = AssistantGUI(ai_engine=ai, voice_output=voice)

        def do_interrupt():
            """Para a fala do assistente imediatamente."""
            voice.stop()
            app.set_status("waiting", "Interrompido", "yellow")
            logger.info("Interrupção via voz executada.")

        def process_command(user_text):
            """Processa a lógica de IA para texto ou voz."""
            if not user_text: return

            # Comando para fechar o programa
            if "pode finalizar zerachiel" in user_text.lower():
                final_msg = f"Encerrando o sistema. Até logo!"
                app.add_message("assistant", final_msg)
                app.set_status("speaking", "Saindo...", "red")
                voice.speak(final_msg)
                time.sleep(2)
                app.on_closing()
                return

            app.add_message("user", user_text)
            app.set_status("thinking", "Zerachiel pensando...", "blue")

            def run_ai():
                try:
                    spoken, display = ai.process(user_text)
                    app.add_message("assistant", display or spoken)
                    
                    app.set_status("speaking", "Zerachiel falando...", "purple")
                    voice.speak(spoken)
                    
                    ai.add_to_history(user_text, spoken)
                    app.set_status("waiting", "Pode falar...", "green")
                except Exception as e:
                    logger.error(f"Erro na IA: {e}")
                    app.set_status("waiting", "Erro no processamento", "red")

            threading.Thread(target=run_ai, daemon=True).start()

        def assistant_loop():
            """Loop principal de monitoramento (Fila de Texto e Microfone)."""
            logger.info("Thread de monitoramento iniciada.")
            
            # Mudança fundamental: O assistente começa "dormindo"
            # mas vamos monitorar o status da GUI para saber se ele deve acordar
            is_awake = False 

            while not app.stop_event.is_set():
                # 1. PRIORIDADE: Texto digitado sempre funciona
                try:
                    cmd_text = app.command_queue.get_nowait()
                    if cmd_text:
                        process_command(cmd_text)
                        is_awake = True # Se digitou, ele acorda para voz também
                        continue 
                except queue.Empty:
                    pass

                # 2. VERIFICAÇÃO DE STATUS
                current_status = app.status_label.cget("text")
                
                # Se o botão foi clicado (Zerachiel: Pronto), nós forçamos o "is_awake"
                if "Zerachiel: Pronto" in current_status and not is_awake:
                    is_awake = True
                    logger.info("Zerachiel acordado via clique no botão.")

                if "Offline" in current_status:
                    time.sleep(0.5)
                    continue

                # 3. ESCUTA ATIVA
                # Se estiver acordado, o status fica VERMELHO (ouvindo pergunta)
                # Se estiver dormindo, fica VERDE (esperando comando inicial)
                app.set_status("listening", "Ouvindo..." if is_awake else "Diga 'Olá Assistente'", "red" if is_awake else "green")
                recognized = listen()

                if recognized:
                    logger.info(f"Microfone captou: {recognized}")
                    
                    if is_interrupt_command(recognized):
                        do_interrupt()
                        continue
                    
                    # Lógica de ativação/processamento
                    if not is_awake:
                        if any(wake.lower() in recognized.lower() for wake in WAKE_WORDS):
                            is_awake = True
                            resp = "Sim? Estou ouvindo. O que deseja?"
                            app.add_message("assistant", resp)
                            voice.speak(resp)
                        # Se não for a palavra de ativação e ele estiver "dormindo", ignora.
                    else:
                        # SE ESTIVER ACORDADO, PROCESSA TUDO!
                        process_command(recognized)
                else:
                    # Sem som captado
                    status_txt = "Pode falar..." if is_awake else "Diga 'Olá Assistente, Iniciar'"
                    app.set_status("waiting", status_txt, "green")

        # Inicia a thread do assistente
        threading.Thread(target=assistant_loop, daemon=True).start()

        # Inicia a Interface
        app.mainloop()

    except Exception as e:
        logger.critical(f"FALHA NO SISTEMA: {e}", exc_info=True)
    finally:
        logger.info("Aplicação finalizada.")

if __name__ == "__main__":
    main()