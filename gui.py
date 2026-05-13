# ============================================================
# gui.py - Interface Cyberpunk Neon-Dark
# ============================================================

import tkinter as tk
import customtkinter as ctk
import threading
import queue
import random
import math
import logging
import sys
from datetime import datetime
from gui_theme import COLORS, apply_ctk_theme
from config import ASSISTANT_NAME

logger = logging.getLogger("VoiceAssistant")

class PulseIndicator(tk.Canvas):
    """Círculo pulsante animado que muda de cor conforme o estado."""
    STATES = {
        "waiting":   {"color": COLORS["green"],  "speed": 60, "amp": 4},
        "listening": {"color": COLORS["red"],    "speed": 30, "amp": 8},
        "thinking":  {"color": COLORS["blue"],   "speed": 20, "amp": 6},
        "speaking":  {"color": COLORS["cyan"],   "speed": 40, "amp": 5},
    }

    def __init__(self, master, size=44, **kwargs):
        super().__init__(master, width=size, height=size, bg=COLORS["bg_panel"], highlightthickness=0)
        self._size = size
        self._cx = size // 2
        self._cy = size // 2
        self._phase = 0.0
        self._state = "waiting"
        self._animate()

    def set_state(self, state):
        if state in self.STATES: self._state = state

    def _animate(self):
        cfg = self.STATES[self._state]
        self._phase = (self._phase + 0.2) % (2 * math.pi)
        pulse = int(cfg["amp"] * abs(math.sin(self._phase)))
        r = 10 + pulse
        
        self.delete("all")
        # Glow simples
        self.create_oval(self._cx-r-2, self._cy-r-2, self._cx+r+2, self._cy+r+2, outline=cfg["color"], width=1)
        self.create_oval(self._cx-r, self._cy-r, self._cx+r, self._cy+r, outline=cfg["color"], width=2)
        self.create_oval(self._cx-3, self._cy-3, self._cx+3, self._cy+3, fill=cfg["color"], outline="")
        
        self.after(cfg["speed"], self._animate)

class AssistantGUI(ctk.CTk):
    def __init__(self, ai_engine, voice_output):
        super().__init__()
        apply_ctk_theme()

        self.ai = ai_engine
        self.voice = voice_output
        self.command_queue = queue.Queue()
        self.msg_queue = queue.Queue()
        self.stop_event = threading.Event()
        self.is_animating = False

        self.title("ZERACHIEL AI — CORE SYSTEM")
        self.geometry("720x860")
        self.configure(fg_color=COLORS["bg_root"])
        
        self._setup_ui()
        self._update_clock()
        threading.Thread(target=self._process_msg_queue, daemon=True).start()
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def _setup_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        # 1. HEADER CANVAS
        self.header_canvas = tk.Canvas(self, height=60, bg=COLORS["bg_panel"], highlightthickness=0)
        self.header_canvas.grid(row=0, column=0, sticky="ew")
        self.header_canvas.create_text(20, 30, text="Z E R A C H I E L", font=(COLORS["font_mono"], 18, "bold"), fill=COLORS["cyan"], anchor="w")
        self._clock_item = self.header_canvas.create_text(700, 30, text="00:00:00", font=(COLORS["font_mono"], 10), fill=COLORS["text_dim"], anchor="e")
        self.header_canvas.create_line(0, 59, 1000, 59, fill=COLORS["cyan"], width=1)

        # 2. STATUS BAR
        self.status_frame = ctk.CTkFrame(self, fg_color=COLORS["bg_panel"], corner_radius=0)
        self.status_frame.grid(row=1, column=0, sticky="ew", padx=2, pady=2)
        
        self.pulse_indicator = PulseIndicator(self.status_frame)
        self.pulse_indicator.pack(side="left", padx=10)

        self.status_label = ctk.CTkLabel(self.status_frame, text="Sistema Offline", font=(COLORS["font_mono"], 14, "bold"), text_color=COLORS["text_dim"])
        self.status_label.pack(side="left", padx=5)

        self.start_button = ctk.CTkButton(
            self.status_frame, text="▶ INICIAR", font=(COLORS["font_mono"], 11, "bold"),
            fg_color="transparent", border_color=COLORS["green"], border_width=1,
            text_color=COLORS["green"], hover_color=COLORS["green"], command=self.activate_assistant
        )
        self.start_button.pack(side="right", padx=20)

        # 3. CHAT DISPLAY
        self.chat_display = ctk.CTkTextbox(
            self, font=(COLORS["font_mono"], 13), fg_color=COLORS["bg_card"],
            text_color=COLORS["text_primary"], border_color=COLORS["border_dim"], border_width=1,
            corner_radius=0, state="disabled", wrap="word"
        )
        self.chat_display.grid(row=2, column=0, padx=20, pady=10, sticky="nsew")
        self._configure_chat_tags()

        # 4. WAVEFORM CANVAS
        self.wave_canvas = tk.Canvas(self, height=60, bg=COLORS["bg_panel"], highlightthickness=0)
        self.wave_canvas.grid(row=3, column=0, sticky="ew", padx=20, pady=5)
        self._animate_wave()

        # 5. INPUT FRAME
        self.input_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.input_frame.grid(row=4, column=0, sticky="ew", padx=20, pady=20)
        
        ctk.CTkLabel(self.input_frame, text=">>>", text_color=COLORS["cyan"], font=(COLORS["font_mono"], 14, "bold")).pack(side="left", padx=5)
        
        self.entry = ctk.CTkEntry(
            self.input_frame, placeholder_text="Aguardando inicialização...",
            fg_color=COLORS["bg_input"], border_color=COLORS["border_dim"], text_color=COLORS["text_primary"],
            font=(COLORS["font_mono"], 13), state="disabled"
        )
        self.entry.pack(side="left", fill="x", expand=True, padx=5)
        self.entry.bind("<Return>", lambda e: self._send_command())

        self.send_btn = ctk.CTkButton(
            self.input_frame, text="ENVIAR", width=80, state="disabled",
            fg_color="transparent", border_color=COLORS["cyan"], border_width=1,
            text_color=COLORS["cyan"], command=self._send_command
        )
        self.send_btn.pack(side="left", padx=5)

    def _update_clock(self):
        now = datetime.now().strftime("%H:%M:%S")
        self.header_canvas.itemconfig(self._clock_item, text=now)
        self.after(1000, self._update_clock)

    def _configure_chat_tags(self):
        # Acesso ao widget interno para tags de cores no CTkTextbox
        widget = self.chat_display._textbox
        widget.tag_configure("user_prefix", foreground=COLORS["amber"], font=(COLORS["font_mono"], 13, "bold"))
        widget.tag_configure("ai_prefix", foreground=COLORS["cyan"], font=(COLORS["font_mono"], 13, "bold"))
        widget.tag_configure("status_tag", foreground=COLORS["text_dim"], font=(COLORS["font_mono"], 11, "italic"))

    def activate_assistant(self):
        """API Requerida: Chamado pelo botão para ligar o sistema."""
        self.start_button.configure(state="disabled", text="◉ ATIVO", text_color=COLORS["cyan"], border_color=COLORS["cyan"])
        self.set_status("waiting", "Zerachiel: Pronto", COLORS["green"])
        self.entry.configure(state="normal", placeholder_text="Digite um comando...")
        self.send_btn.configure(state="normal")
        self.add_message("status", "Sistema HUD Inicializado. Link estabelecido.")

        def greet():
            msg = f"Olá! Sou {ASSISTANT_NAME}. Sistema online. Como posso ajudar?"
            self.add_message("assistant", msg)
            self.voice.speak(msg)
        threading.Thread(target=greet, daemon=True).start()

    def set_status(self, mode, text, color):
        """API Requerida: Atualiza indicador e rótulo de status."""
        def update():
            self.status_label.configure(text=text, text_color=color)
            self.pulse_indicator.set_state(mode)
            self.is_animating = mode in ("listening", "speaking")
        self.after(0, update)

    def _animate_wave(self):
        """Animação de barras estilizada no Canvas."""
        self.wave_canvas.delete("wave_bar")
        w = self.winfo_width() if self.winfo_width() > 1 else 720
        n_bars = 40
        bar_w = 8
        gap = 4
        x_start = (w // 2) - (n_bars * (bar_w + gap) // 2)
        
        for i in range(n_bars):
            h = random.randint(5, 45) if self.is_animating else 5
            x0 = x_start + i * (bar_w + gap)
            y0 = 30 - (h // 2)
            y1 = 30 + (h // 2)
            color = COLORS["cyan"] if self.is_animating else COLORS["border_dim"]
            self.wave_canvas.create_rectangle(x0, y0, x0 + bar_w, y1, fill=color, outline="", tags="wave_bar")
        
        self.after(80, self._animate_wave)

    def add_message(self, role, text):
        """API Requerida: Adiciona mensagem ao chat com formatação neon."""
        self.msg_queue.put((role, text))

    def _process_msg_queue(self):
        while not self.stop_event.is_set():
            try:
                role, text = self.msg_queue.get(timeout=0.1)
                self.after(0, self._update_chat_ui, role, text)
            except queue.Empty: continue

    def _update_chat_ui(self, role, text):
        self.chat_display.configure(state="normal")
        ts = datetime.now().strftime("[%H:%M]")
        
        if role == "user":
            self.chat_display.insert("end", f"\n▸ VOCÊ {ts}: ", "user_prefix")
            self.chat_display.insert("end", f"{text}\n")
        elif role == "assistant":
            self.chat_display.insert("end", f"\n◈ {ASSISTANT_NAME} {ts}: ", "ai_prefix")
            self.chat_display.insert("end", f"{text}\n")
        elif role == "status":
            self.chat_display.insert("end", f"\n--- {text} ---\n", "status_tag")
        
        self.chat_display.see("end")
        self.chat_display.configure(state="disabled")

    def _send_command(self):
        text = self.entry.get()
        if text.strip():
            self.command_queue.put(text)
            self.entry.delete(0, 'end')

    def on_closing(self):
        """API Requerida: Encerra o sistema."""
        self.stop_event.set()
        self.destroy()
        sys.exit(0)