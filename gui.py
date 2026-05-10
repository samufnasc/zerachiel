# ============================================================
# gui.py - Interface Gráfica (CustomTkinter)
# Responsável pelo visual: Chat, Status e Ondas de Voz.
# ============================================================

import customtkinter as ctk
import threading
import queue
import random
import logging
import sys
from config import ASSISTANT_NAME  # Importado para usar no botão

logger = logging.getLogger("VoiceAssistant")

class AssistantGUI(ctk.CTk):
    def __init__(self, ai_engine, voice_output):
        super().__init__()

        self.ai = ai_engine
        self.voice = voice_output

        # Controle de Threads e Filas
        self.command_queue = queue.Queue()
        self.msg_queue = queue.Queue()
        self.stop_event = threading.Event()
        self.is_animating = False

        # Configurações de Janela
        self.title(f"{ASSISTANT_NAME} — Inteligência Artificial")
        self.geometry("640x800")
        self.minsize(500, 600)
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self._setup_ui()
        
        # Thread para atualizar o chat log de forma assíncrona
        threading.Thread(target=self._process_msg_queue, daemon=True).start()

        # Evento de fechamento
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def _setup_ui(self):
        """Monta os widgets da interface gráfica."""
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Cabeçalho de Status
        self.status_frame = ctk.CTkFrame(self)
        self.status_frame.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="ew")

        self.status_indicator = ctk.CTkLabel(self.status_frame, text="●", font=("Arial", 24))
        self.status_indicator.pack(side="left", padx=10)

        self.status_label = ctk.CTkLabel(self.status_frame, text="Sistema Offline", font=("Segoe UI", 16, "bold"))
        self.status_label.pack(side="left", padx=5)

        # Botão de Iniciar Assistente (Botão de Ativação Manual)
        self.start_button = ctk.CTkButton(
            self.status_frame, 
            text="▶ INICIAR ZERACHIEL", 
            fg_color="green", 
            hover_color="darkgreen",
            command=self.activate_assistant,
            font=("Roboto", 13, "bold"),
            width=160
        )
        self.start_button.pack(side="right", padx=10, pady=5)

        # Área do Chat (Histórico)
        self.chat_display = ctk.CTkTextbox(self, font=("Consolas", 14), state="disabled", wrap="word")
        self.chat_display.grid(row=1, column=0, padx=20, pady=10, sticky="nsew")

        # Animação de Ondas (Barras dinâmicas)
        self.wave_frame = ctk.CTkFrame(self, height=60, fg_color="transparent")
        self.wave_frame.grid(row=2, column=0, padx=20, pady=5)
        self.wave_bars = []
        for _ in range(20):
            bar = ctk.CTkFrame(self.wave_frame, width=8, height=5, fg_color="#3b8ed0")
            bar.pack(side="left", padx=2)
            self.wave_bars.append(bar)

        # Entrada de Texto Inferior
        self.input_frame = ctk.CTkFrame(self)
        self.input_frame.grid(row=3, column=0, padx=20, pady=(5, 20), sticky="ew")

        self.entry = ctk.CTkEntry(self.input_frame, placeholder_text="Aguardando inicialização...", state="disabled")
        self.entry.pack(side="left", fill="x", expand=True, padx=(10, 5), pady=10)
        self.entry.bind("<Return>", lambda e: self._send_command())

        self.send_btn = ctk.CTkButton(self.input_frame, text="Enviar", width=80, state="disabled", command=self._send_command)
        self.send_btn.pack(side="left", padx=(5, 10), pady=10)

    def activate_assistant(self):
        """Callback para o botão de iniciar."""
        self.start_button.configure(state="disabled", text="ZERACHIEL ATIVO", fg_color="#2c3e50")
        self.set_status("waiting", "Zerachiel: Pronto", "green") # Esta frase deve bater com o allowed_statuses do main_gui
        self.entry.configure(state="normal", placeholder_text="Digite sua mensagem...")
        self.send_btn.configure(state="normal")
        
        self.add_message("status", "Motor de áudio e voz inicializado.")
        
        # Define o status que libera o microfone no main_gui.py
        self.set_status("waiting", "Zerachiel: Pronto", "green")
        
        # Saudação inicial em thread para não travar a UI
        def greet():
            msg = f"Olá! Eu sou {ASSISTANT_NAME}. Como posso te ajudar hoje?"
            self.add_message("assistant", msg)
            self.voice.speak(msg)
        
        threading.Thread(target=greet, daemon=True).start()

    def _send_command(self):
        """Envia o texto da caixa de entrada para a fila de comandos."""
        text = self.entry.get()
        if text.strip():
            self.command_queue.put(text)
            self.entry.delete(0, 'end')

    def add_message(self, role, text):
        """Adiciona mensagens à fila de exibição (seguro para threads)."""
        self.msg_queue.put((role, text))

    def _process_msg_queue(self):
        """Monitora a fila de mensagens e atualiza a interface."""
        while not self.stop_event.is_set():
            try:
                # Espera por mensagens na fila
                role, text = self.msg_queue.get(timeout=0.1)
                # agenda a atualização na thread principal do Tkinter
                self.after(0, self._update_chat_ui, role, text)
            except queue.Empty:
                continue

    def _update_chat_ui(self, role, text):
        """Insere o texto no componente visual do chat com formatação."""
        self.chat_display.configure(state="normal")
        
        if role == "user":
            self.chat_display.insert("end", f"\n➤ VOCÊ: ", "user_tag")
            self.chat_display.insert("end", f"{text}\n")
        elif role == "assistant":
            self.chat_display.insert("end", f"\n🤖 {ASSISTANT_NAME}: ", "ai_tag")
            self.chat_display.insert("end", f"{text}\n")
        elif role == "status":
            self.chat_display.insert("end", f"\n [ {text} ] \n", "status_tag")
        else:
            self.chat_display.insert("end", f"\n⚠️ {text}\n")
        
        self.chat_display.see("end")
        self.chat_display.configure(state="disabled")

    def set_status(self, mode, text, color):
        """Atualiza visualmente o status atual (Ouvindo, Falando, etc)."""
        def update():
            self.status_label.configure(text=text)
            self.status_indicator.configure(text_color=color)
            
            # Gerencia a animação das ondas
            animating = mode in ("listening", "speaking")
            if animating and not self.is_animating:
                self.is_animating = True
                self._animate_waves()
            elif not animating:
                self.is_animating = False

        self.after(0, update)

    def _animate_waves(self):
        """Cria o efeito visual de oscilação das barras."""
        if not self.is_animating:
            for bar in self.wave_bars: 
                bar.configure(height=5)
            return
            
        for bar in self.wave_bars:
            # Altura aleatória para simular som
            h = random.randint(5, 45)
            bar.configure(height=h)
            
        self.after(100, self._animate_waves)

    def on_closing(self):
        """Finaliza o programa corretamente ao fechar a janela."""
        logger.info("Fechando aplicativo...")
        self.stop_event.set()
        self.destroy()
        sys.exit(0)