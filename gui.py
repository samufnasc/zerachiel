# ============================================================
# gui.py — Interface Cyberpunk v4.1 (Zerachiel Final)
# ============================================================

import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk
import threading
import queue
import random
import math
import logging
import sys
import time
import os
from datetime import datetime
from gui_theme import COLORS, apply_ctk_theme
from config import ASSISTANT_NAME

logger = logging.getLogger("VoiceAssistant")

class ScrollingMarquee(tk.Canvas):
    def __init__(self, master, text, color="#00f5a0"):
        super().__init__(master, height=30, bg=COLORS["bg_panel"], highlightthickness=0)
        self.text_str = text
        self.color = color
        self.text_id = self.create_text(850, 15, text=self.text_str, font=("Consolas", 11, "bold"), fill=self.color, anchor="w")
        self._scroll()

    def _scroll(self):
        self.move(self.text_id, -1, 0)
        pos = self.coords(self.text_id)
        if pos[0] < -500:
            self.coords(self.text_id, 850, 15)
        self.after(25, self._scroll)

class VolumeBars(tk.Canvas):
    def __init__(self, master, num_bars=30):
        super().__init__(master, height=80, bg=COLORS["bg_panel"], highlightthickness=0)
        self.num_bars = num_bars
        self.bars = []
        self.is_animating = False
        self.bind("<Configure>", self._draw_bars)

    def _draw_bars(self, event=None):
        self.delete("all")
        self.bars = []
        w = self.winfo_width()
        h = self.winfo_height()
        bar_w = (w - 40) / self.num_bars
        for i in range(self.num_bars):
            x = 20 + i * bar_w
            bar = self.create_rectangle(x + 2, h - 5, x + bar_w - 2, h - 10, fill=COLORS["cyan"], outline="", tags="bar")
            self.bars.append(bar)

    def animate(self, active=True):
        self.is_animating = active
        if active: self._update_bars()
        else: self._reset_bars()

    def _update_bars(self):
        if not self.is_animating: return
        h = self.winfo_height()
        for bar in self.bars:
            target_h = random.randint(10, 60)
            self.coords(bar, self.coords(bar)[0], h - target_h, self.coords(bar)[2], h - 5)
            # Gradiente de cor baseado na altura
            color = COLORS["cyan"] if target_h < 40 else COLORS["blue"] if target_h < 55 else COLORS["purple"]
            self.itemconfig(bar, fill=color)
        self.after(80, self._update_bars)

    def _reset_bars(self):
        h = self.winfo_height()
        for bar in self.bars:
            self.coords(bar, self.coords(bar)[0], h - 10, self.coords(bar)[2], h - 5)
            self.itemconfig(bar, fill=COLORS["cyan"])

class PulseIndicator(tk.Canvas):
    def __init__(self, master, size=60):
        super().__init__(master, width=size, height=size, bg=COLORS["bg_panel"], highlightthickness=0)
        self._cx, self._cy = size//2, size//2
        self._phase = 0.0
        self._state = "waiting"
        self._animate()

    def set_state(self, s): self._state = s

    def _animate(self):
        cfg = {
            "waiting": (COLORS["green"], 50, 2, "🦾"), 
            "listening": (COLORS["red"], 20, 10, "👂"), 
            "thinking": (COLORS["blue"], 15, 6, "⚙️"), 
            "speaking": (COLORS["cyan"], 30, 8, "🤖"),
            "paused": (COLORS["amber"], 100, 0, "⏸")
        }[self._state]
        
        self._phase = (self._phase + 0.15) % (2 * math.pi)
        r_outer = 15 + int(cfg[2] * abs(math.sin(self._phase)))
        r_inner = 10
        
        self.delete("all")
        self.create_oval(self._cx-r_outer, self._cy-r_outer, self._cx+r_outer, self._cy+r_outer, outline=cfg[0], width=1)
        self.create_oval(self._cx-r_inner, self._cy-r_inner, self._cx+r_inner, self._cy+r_inner, outline=cfg[0], width=3)
        self.create_text(self._cx, self._cy, text=cfg[3], font=("Segoe UI Emoji", 12))
        
        self.after(cfg[1], self._animate)

class AssistantGUI(ctk.CTk):
    def __init__(self, ai_engine, voice_output):
        apply_ctk_theme()
        super().__init__()
        self.ai = ai_engine
        self.voice = voice_output
        self.command_queue = queue.Queue()
        self.msg_queue = queue.Queue()
        self.stop_event = threading.Event()
        self.pause_listening_event = threading.Event()
        self.pause_speaking_event = threading.Event()
        self.attached_files = []

        self.title(f"🤖 {ASSISTANT_NAME} NEURAL INTERFACE")
        self.geometry("900x980")
        self.configure(fg_color=COLORS["bg_root"])
        self._setup_ui()
        threading.Thread(target=self._process_msg_queue, daemon=True).start()
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def _setup_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(4, weight=1)
        
        self.marquee = ScrollingMarquee(self, "Desenvolvido por Samuel com ajuda do Espírito Santo.")
        self.marquee.grid(row=0, column=0, sticky="ew")

        # Header
        self.header = tk.Canvas(self, height=100, bg=COLORS["bg_panel"], highlightthickness=0)
        self.header.grid(row=1, column=0, sticky="ew")
        self.header.create_line(0, 99, 900, 99, fill=COLORS["cyan"], width=2)
        
        self.header.create_text(30, 50, text=f"🦾 ASSISTENTE {ASSISTANT_NAME.upper()}", font=("Syne", 32, "bold"), fill=COLORS["cyan"], anchor="w")
        self.engine_tag = self.header.create_text(870, 50, text="SYSTEM: READY", font=("Consolas", 11, "bold"), fill=COLORS["blue"], anchor="e")

        # Painel de Controle
        cp = ctk.CTkFrame(self, fg_color=COLORS["bg_panel"], corner_radius=0, height=100)
        cp.grid(row=2, column=0, sticky="ew")
        
        self.pulse = PulseIndicator(cp, size=80)
        self.pulse.pack(side="left", padx=20)
        
        self.status_label = ctk.CTkLabel(cp, text="NÚCLEO ONLINE", font=("Consolas", 16, "bold"), text_color=COLORS["green"])
        self.status_label.pack(side="left")

        btn_f = ctk.CTkFrame(cp, fg_color="transparent")
        btn_f.pack(side="right", padx=20)
        
        self.btn_attach = ctk.CTkButton(btn_f, text="📎 ANEXAR", width=110, height=35, fg_color=COLORS["blue"], text_color=COLORS["bg_root"], font=("Consolas", 12, "bold"), command=self.attach_file)
        self.btn_attach.pack(side="left", padx=5)

        self.btn_screen = ctk.CTkButton(btn_f, text="👁 TELA", width=90, height=35, fg_color=COLORS["green"], text_color=COLORS["bg_root"], font=("Consolas", 12, "bold"), command=self.capture_screen_action)
        self.btn_screen.pack(side="left", padx=5)

        self.btn_listen = ctk.CTkButton(btn_f, text="⏸ ESCUTA", width=110, height=35, fg_color="transparent", border_width=2, border_color=COLORS["amber"], text_color=COLORS["amber"], font=("Consolas", 12, "bold"), command=self.toggle_listen)
        self.btn_listen.pack(side="left", padx=5)
        
        self.btn_speak = ctk.CTkButton(btn_f, text="⏸ FALA", width=110, height=35, fg_color="transparent", border_width=2, border_color=COLORS["purple"], text_color=COLORS["purple"], font=("Consolas", 12, "bold"), command=self.toggle_speak)
        self.btn_speak.pack(side="left", padx=5)

        # Área de Anexos (Scrollable)
        self.attach_frame = ctk.CTkScrollableFrame(self, height=60, fg_color=COLORS["bg_panel"], border_width=1, border_color=COLORS["border_dim"], label_text="ARQUIVOS ANEXADOS", label_font=("Consolas", 10, "bold"), label_text_color=COLORS["blue"])
        self.attach_frame.grid(row=3, column=0, sticky="ew", padx=25, pady=(10, 0))
        self.attach_frame.grid_remove() # Escondido até ter anexos

        # Chat
        self.chat = ctk.CTkTextbox(self, font=("Consolas", 14), fg_color=COLORS["bg_card"], text_color=COLORS["text_primary"], border_width=1, border_color=COLORS["border_dim"], corner_radius=15)
        self.chat.grid(row=4, column=0, padx=25, pady=15, sticky="nsew")
        self.chat.configure(state="disabled")

        # Barras de Volume
        self.vol_bars = VolumeBars(self)
        self.vol_bars.grid(row=5, column=0, sticky="ew", padx=25, pady=5)

        # Input
        inf = ctk.CTkFrame(self, fg_color=COLORS["bg_panel"], height=80, corner_radius=15)
        inf.grid(row=6, column=0, sticky="ew", padx=25, pady=(5, 25))
        inf.grid_columnconfigure(0, weight=1)
        
        self.entry = ctk.CTkEntry(inf, placeholder_text="🤖 Comando neural...", font=("Consolas", 14), height=50, fg_color=COLORS["bg_input"], border_color=COLORS["border_dim"])
        self.entry.grid(row=0, column=0, padx=15, pady=15, sticky="ew")
        self.entry.bind("<Return>", lambda e: self._send())
        
        self.send_btn = ctk.CTkButton(inf, text="TRANSMITIR ⚡", width=140, height=50, fg_color=COLORS["cyan"], text_color=COLORS["bg_root"], font=("Consolas", 13, "bold"), command=self._send)
        self.send_btn.grid(row=0, column=1, padx=(0, 15), pady=15)

    def attach_file(self):
        path = filedialog.askopenfilename()
        if path:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                filename = os.path.basename(path)
                self.attached_files.append(path)
                
                # Mostrar painel de anexos
                self.attach_frame.grid()
                lbl = ctk.CTkLabel(self.attach_frame, text=f"📎 {path}", font=("Consolas", 10), text_color=COLORS["text_primary"], anchor="w")
                lbl.pack(fill="x", padx=5)
                
                self.add_message("user", f"[ARQUIVO ANEXADO: {filename}]")
                self.command_queue.put(f"Analise este arquivo '{filename}':\n\n{content}")
            except Exception as e:
                messagebox.showerror("Erro", f"Não foi possível ler o arquivo: {e}")

    def capture_screen_action(self):
        self.add_message("user", "👁 Captura de tela solicitada")
        self.command_queue.put("Captura de tela: descreva o que está aparecendo na tela agora, resuma e aponte qualquer problema visível.")

    def toggle_listen(self):
        if self.pause_listening_event.is_set():
            self.pause_listening_event.clear()
            self.btn_listen.configure(text="⏸ ESCUTA", text_color=COLORS["amber"], border_color=COLORS["amber"])
            self.set_status("waiting", "NÚCLEO ONLINE", COLORS["green"])
        else:
            self.pause_listening_event.set()
            self.btn_listen.configure(text="▶ ESCUTA", text_color=COLORS["red"], border_color=COLORS["red"])
            self.set_status("paused", "ESCUTA PAUSADA", COLORS["amber"])

    def toggle_speak(self):
        if self.pause_speaking_event.is_set():
            self.pause_speaking_event.clear()
            self.btn_speak.configure(text="⏸ FALA", text_color=COLORS["purple"], border_color=COLORS["purple"])
            self.set_status("waiting", "NÚCLEO ONLINE", COLORS["green"])
        else:
            self.pause_speaking_event.set()
            self.btn_speak.configure(text="▶ FALA", text_color=COLORS["red"], border_color=COLORS["red"])
            self.set_status("paused", "FALA PAUSADA", COLORS["purple"])
            if hasattr(self.voice, "stop"): self.voice.stop()

    def update_engine(self, name):
        self.header.itemconfig(self.engine_tag, text=f"ENGINE: {name}")

    def set_status(self, mode, text, color):
        self.status_label.configure(text=text, text_color=color)
        self.pulse.set_state(mode)
        self.vol_bars.animate(mode == "speaking")

    def add_message(self, role, text): self.msg_queue.put((role, text))

    def _process_msg_queue(self):
        while not self.stop_event.is_set():
            try:
                r, t = self.msg_queue.get(timeout=0.1)
                self.after(0, self._update_chat, r, t)
            except queue.Empty: pass

    def _update_chat(self, role, text):
        self.chat.configure(state="normal")
        icon = "👤" if role == "user" else "🤖"
        ts = datetime.now().strftime("%H:%M")
        self.chat.insert("end", f"[{ts}] {icon} {'VOCÊ' if role=='user' else ASSISTANT_NAME}:\n{text}\n\n")
        self.chat.see("end")
        self.chat.configure(state="disabled")

    def _send(self):
        t = self.entry.get().strip()
        if t:
            self._update_chat("user", t)
            self.command_queue.put(t)
            self.entry.delete(0, "end")

    def on_closing(self):
        self.stop_event.set()
        self.destroy()
        sys.exit(0)
