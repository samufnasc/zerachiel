# ============================================================
# gui.py — Interface Cyberpunk Advanced (Zerachiel v3.9)
# ============================================================

import tkinter as tk
import customtkinter as ctk
import threading
import queue
import random
import math
import logging
import sys
import time
from datetime import datetime
from gui_theme import COLORS, apply_ctk_theme
from config import ASSISTANT_NAME

logger = logging.getLogger("VoiceAssistant")

class ScrollingMarquee(tk.Canvas):
    def __init__(self, master, text, color="#87CEFA"):
        super().__init__(master, height=30, bg=COLORS["bg_panel"], highlightthickness=0)
        self.text_str = text
        self.color = color
        self.text_id = self.create_text(800, 15, text=self.text_str, font=("Consolas", 11, "italic", "bold"), fill=self.color, anchor="w")
        self._scroll()

    def _scroll(self):
        self.move(self.text_id, -1, 0)
        pos = self.coords(self.text_id)
        if pos[0] < -500:
            self.coords(self.text_id, 800, 15)
        self.after(25, self._scroll)

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
            "speaking": (COLORS["cyan"], 30, 8, "🤖")
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
        self.is_animating = False

        self.title(f"🤖 {ASSISTANT_NAME} NEURAL INTERFACE")
        self.geometry("800x950")
        self.configure(fg_color=COLORS["bg_root"])
        self._setup_ui()
        threading.Thread(target=self._process_msg_queue, daemon=True).start()
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def _setup_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(4, weight=1)
        
        self.marquee = ScrollingMarquee(self, "Desenvolvido por Samuel com ajuda do Espírito Santo.")
        self.marquee.grid(row=0, column=0, sticky="ew")

        self.header = tk.Canvas(self, height=80, bg=COLORS["bg_panel"], highlightthickness=0)
        self.header.grid(row=1, column=0, sticky="ew")
        self.header.create_line(0, 79, 800, 79, fill=COLORS["cyan"], width=2)
        
        self.header.create_text(30, 40, text=f"🦾 {ASSISTANT_NAME.upper()} CORE", font=("Consolas", 24, "bold"), fill=COLORS["cyan"], anchor="w")
        self.engine_tag = self.header.create_text(770, 40, text="SYSTEM: READY", font=("Consolas", 11, "bold"), fill=COLORS["purple"], anchor="e")

        cp = ctk.CTkFrame(self, fg_color=COLORS["bg_panel"], corner_radius=0, height=100)
        cp.grid(row=2, column=0, sticky="ew")
        
        self.pulse = PulseIndicator(cp, size=80)
        self.pulse.pack(side="left", padx=20)
        
        self.status_label = ctk.CTkLabel(cp, text="SYSTEM ONLINE", font=("Consolas", 16, "bold"), text_color=COLORS["green"])
        self.status_label.pack(side="left")

        btn_f = ctk.CTkFrame(cp, fg_color="transparent")
        btn_f.pack(side="right", padx=20)
        
        self.btn_listen = ctk.CTkButton(btn_f, text="⏸ ESCUTA", width=110, height=35, fg_color="transparent", border_width=2, border_color=COLORS["amber"], text_color=COLORS["amber"], font=("Consolas", 12, "bold"), command=self.toggle_listen)
        self.btn_listen.pack(side="top", pady=5)
        
        self.btn_speak = ctk.CTkButton(btn_f, text="⏸ FALA", width=110, height=35, fg_color="transparent", border_width=2, border_color=COLORS["purple"], text_color=COLORS["purple"], font=("Consolas", 12, "bold"), command=self.toggle_speak)
        self.btn_speak.pack(side="top", pady=5)

        self.chat = ctk.CTkTextbox(self, font=("Consolas", 14), fg_color=COLORS["bg_card"], text_color=COLORS["text_primary"], border_width=1, border_color=COLORS["border_dim"], corner_radius=10)
        self.chat.grid(row=4, column=0, padx=25, pady=15, sticky="nsew")
        self.chat.configure(state="disabled")

        self.wave = tk.Canvas(self, height=80, bg=COLORS["bg_panel"], highlightthickness=0)
        self.wave.grid(row=5, column=0, sticky="ew", padx=25, pady=5)
        self._animate_wave()

        inf = ctk.CTkFrame(self, fg_color=COLORS["bg_panel"], height=80, corner_radius=15)
        inf.grid(row=6, column=0, sticky="ew", padx=25, pady=(5, 25))
        inf.grid_columnconfigure(0, weight=1)
        
        self.entry = ctk.CTkEntry(inf, placeholder_text="🤖 Digite um comando neural...", font=("Consolas", 14), height=50, fg_color=COLORS["bg_input"], border_color=COLORS["border_dim"])
        self.entry.grid(row=0, column=0, padx=15, pady=15, sticky="ew")
        self.entry.bind("<Return>", lambda e: self._send())
        
        self.send_btn = ctk.CTkButton(inf, text="TRANSMITIR ⚡", width=140, height=50, fg_color=COLORS["cyan"], text_color=COLORS["bg_root"], font=("Consolas", 13, "bold"), command=self._send)
        self.send_btn.grid(row=0, column=1, padx=(0, 15), pady=15)

    def toggle_listen(self):
        if self.pause_listening_event.is_set():
            self.pause_listening_event.clear()
            self.btn_listen.configure(text="⏸ ESCUTA", text_color=COLORS["amber"], border_color=COLORS["amber"])
            self.set_status("waiting", "ESCUTA REATIVADA", COLORS["green"])
        else:
            self.pause_listening_event.set()
            self.btn_listen.configure(text="▶ ESCUTA", text_color=COLORS["red"], border_color=COLORS["red"])
            self.set_status("waiting", "ESCUTA PAUSADA", COLORS["amber"])

    def toggle_speak(self):
        if self.pause_speaking_event.is_set():
            self.pause_speaking_event.clear()
            self.btn_speak.configure(text="⏸ FALA", text_color=COLORS["purple"], border_color=COLORS["purple"])
            self.set_status("waiting", "FALA REATIVADA", COLORS["green"])
        else:
            self.pause_speaking_event.set()
            self.btn_speak.configure(text="▶ FALA", text_color=COLORS["red"], border_color=COLORS["red"])
            self.set_status("waiting", "FALA PAUSADA", COLORS["purple"])
            if hasattr(self.voice, "stop"): self.voice.stop()

    def _animate_wave(self):
        if self.stop_event.is_set(): return
        self.wave.delete("wave_line")
        w, h = self.wave.winfo_width(), 80
        cy = h // 2
        if self.is_animating:
            pts = []
            for x in range(0, w or 750, 8):
                offset = random.randint(-25, 25) * math.sin(x*0.04 + time.time()*12)
                pts.append((x, cy + offset))
            if len(pts) > 1: self.wave.create_line(pts, fill=COLORS["cyan"], width=3, tags="wave_line", smooth=True)
        self.after(40, self._animate_wave)

    def update_engine(self, name):
        self.header.itemconfig(self.engine_tag, text=f"ENGINE: {name}")

    def set_status(self, mode, text, color):
        self.status_label.configure(text=text, text_color=color)
        self.pulse.set_state(mode)
        self.is_animating = (mode == "speaking")

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
            self._update_chat("user", t) # CORREÇÃO: Digitação instantânea
            self.command_queue.put(t)
            self.entry.delete(0, "end")

    def on_closing(self):
        self.stop_event.set()
        self.destroy()
        sys.exit(0)
