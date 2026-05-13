# ============================================================
# gui.py — Interface Cyberpunk Neon-Dark (Zerachiel v3.3)
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

# ─────────────────────────────────────────────────────────────
# COMPONENTE: Indicador Pulsante
# ─────────────────────────────────────────────────────────────
class PulseIndicator(tk.Canvas):
    """
    Círculo animado via .after() — muda cor e velocidade
    conforme o estado: waiting/listening/thinking/speaking.
    """
    STATES = {
        "waiting":   {"color": COLORS["green"],  "speed": 55,  "amp": 4},
        "listening": {"color": COLORS["red"],    "speed": 25,  "amp": 9},
        "thinking":  {"color": COLORS["blue"],   "speed": 18,  "amp": 6},
        "speaking":  {"color": COLORS["cyan"],   "speed": 38,  "amp": 5},
    }

    def __init__(self, master, size=48, **kwargs):
        super().__init__(
            master, width=size, height=size,
            bg=COLORS["bg_panel"], highlightthickness=0
        )
        self._cx    = size // 2
        self._cy    = size // 2
        self._phase = 0.0
        self._state = "waiting"
        self._after_id = None
        self._animate()

    def set_state(self, state: str):
        if state in self.STATES:
            self._state = state

    def _animate(self):
        cfg   = self.STATES[self._state]
        self._phase = (self._phase + 0.18) % (2 * math.pi)
        pulse = int(cfg["amp"] * abs(math.sin(self._phase)))
        r     = 11 + pulse
        color = cfg["color"]
        cx, cy = self._cx, self._cy

        self.delete("all")

        # Anel externo — glow simulado com cor escurecida
        r2 = r + 5
        self.create_oval(cx-r2, cy-r2, cx+r2, cy+r2,
                         outline=self._dim(color, 0.25), width=1)
        r3 = r + 2
        self.create_oval(cx-r3, cy-r3, cx+r3, cy+r3,
                         outline=self._dim(color, 0.5), width=1)
        # Anel principal
        self.create_oval(cx-r, cy-r, cx+r, cy+r,
                         outline=color, width=2)
        # Ponto central
        self.create_oval(cx-3, cy-3, cx+3, cy+3,
                         fill=color, outline="")
        # Cruz de mira (detalhe robótico)
        self.create_line(cx-r-4, cy, cx-r+2, cy, fill=color, width=1)
        self.create_line(cx+r-2, cy, cx+r+4, cy, fill=color, width=1)
        self.create_line(cx, cy-r-4, cx, cy-r+2, fill=color, width=1)
        self.create_line(cx, cy+r-2, cx, cy+r+4, fill=color, width=1)

        self._after_id = self.after(cfg["speed"], self._animate)

    @staticmethod
    def _dim(hex_color: str, factor: float) -> str:
        h = hex_color.lstrip("#")
        r, g, b = (int(h[i:i+2], 16) for i in (0, 2, 4))
        return f"#{int(r*factor):02x}{int(g*factor):02x}{int(b*factor):02x}"

    def destroy(self):
        if self._after_id:
            self.after_cancel(self._after_id)
        super().destroy()


# ─────────────────────────────────────────────────────────────
# GUI PRINCIPAL
# ─────────────────────────────────────────────────────────────
class AssistantGUI(ctk.CTk):

    def __init__(self, ai_engine, voice_output):
        apply_ctk_theme()
        super().__init__()

        self.ai           = ai_engine
        self.voice        = voice_output
        self.command_queue = queue.Queue()
        self.msg_queue     = queue.Queue()
        self.stop_event    = threading.Event()
        self.is_animating  = False
        self._after_ids    = []   # rastreia todos os .after() para cancelar no fechamento

        self.title("ZERACHIEL — AI CORE SYSTEM v3.3")
        self.geometry("740x900")
        self.minsize(580, 660)
        self.configure(fg_color=COLORS["bg_root"])

        self._setup_ui()
        self._update_clock()
        self._start_scan_line()
        threading.Thread(target=self._process_msg_queue, daemon=True).start()
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        # Mensagem inicial — sem precisar clicar em Iniciar
        self.add_message("status", "SISTEMA PRONTO  //  DIGITE OU DIGA 'OLÁ ASSISTENTE'")

    # ─── Layout ──────────────────────────────────────────────
    def _setup_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)   # chat expande

        self._build_header()     # row 0
        self._build_status()     # row 1
        self._build_scan()       # row 2 (linha decorativa)
        self._build_chat()       # row 3
        self._build_waveform()   # row 4
        self._build_input()      # row 5
        self._build_footer()     # row 6

    # ─── HEADER ──────────────────────────────────────────────
    def _build_header(self):
        self.header_canvas = tk.Canvas(
            self, height=64,
            bg=COLORS["bg_panel"],
            highlightthickness=0,
        )
        self.header_canvas.grid(row=0, column=0, sticky="ew")

        # Borda inferior neon
        self.header_canvas.create_line(0, 63, 2000, 63, fill=COLORS["cyan"], width=1)
        # Borda inferior fina (efeito duplo)
        self.header_canvas.create_line(0, 61, 2000, 61, fill=self._dim_color(COLORS["cyan"], 0.3), width=1)

        # Título com efeito espaçado
        self.header_canvas.create_text(
            22, 32,
            text="Z E R A C H I E L",
            font=(COLORS["font_mono"], 20, "bold"),
            fill=COLORS["cyan"],
            anchor="w",
        )
        # Subtítulo
        self.header_canvas.create_text(
            22, 50,
            text="AI VOICE SYSTEM  //  CORE v3.3",
            font=(COLORS["font_mono"], 8),
            fill=self._dim_color(COLORS["cyan"], 0.5),
            anchor="w",
        )
        # Badge engine
        self._engine_item = self.header_canvas.create_text(
            710, 22,
            text="[ GROQ ]",
            font=(COLORS["font_mono"], 9, "bold"),
            fill=COLORS["purple"],
            anchor="e",
        )
        # Relógio
        self._clock_item = self.header_canvas.create_text(
            710, 42,
            text="00:00:00",
            font=(COLORS["font_mono"], 11),
            fill=COLORS["text_dim"],
            anchor="e",
        )
        # Redesenha posições ao redimensionar
        self.header_canvas.bind("<Configure>", self._on_header_resize)

    def _on_header_resize(self, event):
        w = event.width - 10
        self.header_canvas.coords(self._clock_item, w, 42)
        self.header_canvas.coords(self._engine_item, w, 22)
        # Atualiza a linha de borda
        self.header_canvas.coords(
            self.header_canvas.find_withtag("border_line")[0] if
            self.header_canvas.find_withtag("border_line") else 1,
            0, 63, event.width, 63
        )

    # ─── STATUS BAR ──────────────────────────────────────────
    def _build_status(self):
        self.status_frame = ctk.CTkFrame(
            self,
            fg_color=COLORS["bg_panel"],
            corner_radius=0,
            border_width=0,
        )
        self.status_frame.grid(row=1, column=0, sticky="ew", padx=0, pady=0)
        self.status_frame.grid_columnconfigure(1, weight=1)

        # Indicador pulsante
        self.pulse_indicator = PulseIndicator(self.status_frame, size=48)
        self.pulse_indicator.grid(row=0, column=0, padx=(14, 8), pady=8)

        # Bloco central: label de status + barra de progresso decorativa
        center = tk.Frame(self.status_frame, bg=COLORS["bg_panel"])
        center.grid(row=0, column=1, sticky="ew", padx=4)

        self.status_label = ctk.CTkLabel(
            center,
            text="■ SISTEMA OFFLINE",
            font=(COLORS["font_mono"], 13, "bold"),
            text_color=COLORS["text_dim"],
            anchor="w",
        )
        self.status_label.pack(fill="x")

        # Linha decorativa abaixo do status
        self._status_bar_canvas = tk.Canvas(
            center, height=3,
            bg=COLORS["bg_panel"],
            highlightthickness=0,
        )
        self._status_bar_canvas.pack(fill="x", pady=(2, 0))
        self._status_bar_phase = 0.0
        self._animate_status_bar()

        # Botão iniciar
        self.start_button = ctk.CTkButton(
            self.status_frame,
            text="▶  INICIAR",
            font=(COLORS["font_mono"], 11, "bold"),
            fg_color="transparent",
            border_color=COLORS["green"],
            border_width=1,
            text_color=COLORS["green"],
            hover_color=COLORS["green"],
            corner_radius=2,
            width=120,
            command=self.activate_assistant,
        )
        self.start_button.grid(row=0, column=2, padx=(8, 16), pady=8)
        self.start_button.bind("<Enter>",
            lambda e: self.start_button.configure(text_color=COLORS["bg_root"]))
        self.start_button.bind("<Leave>",
            lambda e: self.start_button.configure(text_color=COLORS["green"]))

    def _animate_status_bar(self):
        """Linha que desliza da esquerda para a direita — detalhe de HUD."""
        if not self.stop_event.is_set():
            try:
                w = self._status_bar_canvas.winfo_width() or 300
                self._status_bar_phase = (self._status_bar_phase + 2) % (w + 60)
                self._status_bar_canvas.delete("all")
                x = self._status_bar_phase - 30
                color = COLORS["cyan"] if self.is_animating else COLORS["border_dim"]
                # Segmento deslizante
                self._status_bar_canvas.create_line(
                    max(0, x), 1, min(w, x + 60), 1,
                    fill=color, width=2
                )
                # Fundo da linha
                self._status_bar_canvas.create_line(
                    0, 1, w, 1,
                    fill=self._dim_color(color, 0.2), width=1
                )
            except Exception:
                pass
            self.after(30, self._animate_status_bar)

    # ─── SCAN LINE DECORATIVA ─────────────────────────────────
    def _build_scan(self):
        """Linha horizontal com texto de sistema — puro detalhe visual."""
        self._scan_canvas = tk.Canvas(
            self, height=18,
            bg=COLORS["bg_root"],
            highlightthickness=0,
        )
        self._scan_canvas.grid(row=2, column=0, sticky="ew", padx=20)
        self._scan_texts = [
            "SYS.INIT ── VOICE_ENGINE: EDGE-TTS ── STT: GOOGLE ── AI: GROQ/LLAMA ── STATUS: ONLINE",
        ]
        self._scan_offset = 0
        self._scan_line_anim()

    def _start_scan_line(self):
        pass  # já iniciado em _build_scan

    def _scan_line_anim(self):
        if not self.stop_event.is_set():
            try:
                w = self._scan_canvas.winfo_width() or 700
                self._scan_canvas.delete("all")
                full_text = self._scan_texts[0] + "  ·  "
                self._scan_offset = (self._scan_offset + 1) % (len(full_text) * 7)
                # Texto deslizante de sistema
                self._scan_canvas.create_text(
                    w // 2 - self._scan_offset, 9,
                    text=full_text * 3,
                    font=(COLORS["font_mono"], 7),
                    fill=self._dim_color(COLORS["cyan"], 0.4),
                    anchor="w",
                )
            except Exception:
                pass
            self.after(40, self._scan_line_anim)

    # ─── CHAT DISPLAY ─────────────────────────────────────────
    def _build_chat(self):
        # Frame wrapper com borda neon
        chat_wrapper = tk.Frame(
            self,
            bg=COLORS["border_dim"],
            padx=1, pady=1,
        )
        chat_wrapper.grid(row=3, column=0, padx=18, pady=(4, 0), sticky="nsew")

        self.chat_display = ctk.CTkTextbox(
            chat_wrapper,
            font=(COLORS["font_mono"], 13),
            fg_color=COLORS["bg_card"],
            text_color=COLORS["text_primary"],
            border_width=0,
            corner_radius=0,
            state="disabled",
            wrap="word",
            scrollbar_button_color=COLORS["border_dim"],
            scrollbar_button_hover_color=COLORS["cyan"],
        )
        self.chat_display.pack(fill="both", expand=True)
        self._configure_chat_tags()

    def _configure_chat_tags(self):
        w = self.chat_display._textbox
        w.tag_configure("user_prefix",
            foreground=COLORS["amber"],
            font=(COLORS["font_mono"], 13, "bold"))
        w.tag_configure("user_text",
            foreground=COLORS["text_primary"])
        w.tag_configure("ai_prefix",
            foreground=COLORS["cyan"],
            font=(COLORS["font_mono"], 13, "bold"))
        w.tag_configure("ai_text",
            foreground=COLORS["text_primary"])
        w.tag_configure("status_tag",
            foreground=COLORS["text_dim"],
            font=(COLORS["font_mono"], 10, "italic"))

    # ─── WAVEFORM ─────────────────────────────────────────────
    def _build_waveform(self):
        wave_wrapper = tk.Frame(self, bg=COLORS["border_dim"], padx=1, pady=1)
        wave_wrapper.grid(row=4, column=0, padx=18, pady=(6, 0), sticky="ew")

        self.wave_canvas = tk.Canvas(
            wave_wrapper, height=54,
            bg=COLORS["bg_panel"],
            highlightthickness=0,
        )
        self.wave_canvas.pack(fill="x")
        self._animate_wave()

    def _animate_wave(self):
        if self.stop_event.is_set():
            return
        self.wave_canvas.delete("wave_bar")
        w = self.wave_canvas.winfo_width() or 700
        n_bars = 42
        bar_w  = 7
        gap    = 3
        total  = n_bars * (bar_w + gap)
        x0_base = (w - total) // 2
        cy     = 27

        for i in range(n_bars):
            if self.is_animating:
                h = random.randint(4, 48)
            else:
                # Onda senoidal suave no standby
                h = int(4 + 3 * abs(math.sin(i * 0.25 + (self._wave_phase if hasattr(self, '_wave_phase') else 0))))
            x  = x0_base + i * (bar_w + gap)
            y0 = cy - h // 2
            y1 = cy + h // 2

            # Gradiente: centro cyan, bordas dim
            dist   = abs(i - n_bars // 2) / (n_bars // 2)
            color  = self._interpolate(COLORS["cyan"], COLORS["border_dim"], dist * 0.75) \
                     if self.is_animating else \
                     self._interpolate(COLORS["border_dim"], COLORS["bg_panel"], dist * 0.5)

            self.wave_canvas.create_rectangle(
                x, y0, x + bar_w, y1,
                fill=color, outline="", tags="wave_bar"
            )

        if not hasattr(self, '_wave_phase'):
            self._wave_phase = 0.0
        self._wave_phase = (self._wave_phase + 0.08) % (2 * math.pi)
        self.after(75, self._animate_wave)

    # ─── INPUT ────────────────────────────────────────────────
    def _build_input(self):
        input_wrapper = tk.Frame(self, bg=COLORS["border_dim"], padx=1, pady=1)
        input_wrapper.grid(row=5, column=0, padx=18, pady=(6, 0), sticky="ew")

        inner = tk.Frame(input_wrapper, bg=COLORS["bg_panel"])
        inner.pack(fill="x")
        inner.grid_columnconfigure(1, weight=1)

        # Prefixo ">>>"
        tk.Label(
            inner, text=" >>> ",
            font=(COLORS["font_mono"], 14, "bold"),
            fg=COLORS["cyan"],
            bg=COLORS["bg_panel"],
        ).grid(row=0, column=0, padx=(8, 0))

        self.entry = ctk.CTkEntry(
            inner,
            placeholder_text="Digite um comando ou diga 'Olá assistente'...",
            font=(COLORS["font_mono"], 13),
            fg_color=COLORS["bg_input"],
            text_color=COLORS["text_primary"],
            placeholder_text_color=COLORS["text_dim"],
            border_color=COLORS["border_dim"],
            border_width=1,
            corner_radius=2,
            state="normal",   # ← habilitado por padrão
        )
        self.entry.grid(row=0, column=1, padx=6, pady=8, sticky="ew")
        self.entry.bind("<Return>",   lambda e: self._send_command())
        self.entry.bind("<FocusIn>",  lambda e: self.entry.configure(border_color=COLORS["cyan"]))
        self.entry.bind("<FocusOut>", lambda e: self.entry.configure(border_color=COLORS["border_dim"]))

        self.send_btn = ctk.CTkButton(
            inner,
            text="ENVIAR",
            font=(COLORS["font_mono"], 11, "bold"),
            fg_color="transparent",
            border_color=COLORS["cyan"],
            border_width=1,
            text_color=COLORS["cyan"],
            hover_color=COLORS["cyan"],
            corner_radius=2,
            width=85,
            state="normal",   # ← habilitado por padrão
            command=self._send_command,
        )
        self.send_btn.grid(row=0, column=2, padx=(0, 8), pady=8)
        self.send_btn.bind("<Enter>",
            lambda e: self.send_btn.configure(text_color=COLORS["bg_root"]))
        self.send_btn.bind("<Leave>",
            lambda e: self.send_btn.configure(text_color=COLORS["cyan"]))

    # ─── FOOTER ──────────────────────────────────────────────
    def _build_footer(self):
        footer = tk.Frame(self, bg=COLORS["bg_root"])
        footer.grid(row=6, column=0, sticky="ew", pady=(4, 8))

        # Linha decorativa superior
        tk.Canvas(footer, height=1, bg=COLORS["border_dim"],
                  highlightthickness=0).pack(fill="x", padx=18)

        tk.Label(
            footer,
            text=f"  ZERACHIEL SYSTEM  //  DIGA '{WAKE_WORDS_HINT()}' PARA ATIVAR",
            font=(COLORS["font_mono"], 8),
            fg=self._dim_color(COLORS["text_dim"], 0.7),
            bg=COLORS["bg_root"],
            anchor="w",
        ).pack(fill="x", padx=18, pady=(2, 0))


    # ─── API PÚBLICA ──────────────────────────────────────────

    def activate_assistant(self):
        """API requerida por main_gui.py."""
        self.start_button.configure(
            state="disabled",
            text="◉  ATIVO",
            text_color=COLORS["cyan"],
            border_color=COLORS["cyan"],
        )
        # OBRIGATÓRIO: main_gui.py verifica este texto exato
        self.set_status("waiting", "Zerachiel: Pronto", COLORS["green"])
        # Entry já está habilitado — só atualiza o placeholder
        self.entry.configure(placeholder_text="Digite um comando...")
        self.add_message("status", "SISTEMA ONLINE  //  LINK ESTABELECIDO")

        def greet():
            msg = f"Sistema online. Sou {ASSISTANT_NAME}. Como posso ajudar?"
            self.add_message("assistant", msg)
            self.voice.speak(msg)
        threading.Thread(target=greet, daemon=True).start()

    def set_status(self, mode: str, text: str, color: str):
        """API requerida por main_gui.py."""
        def _update():
            self.status_label.configure(text=text, text_color=color)
            self.pulse_indicator.set_state(mode)
            self.is_animating = mode in ("listening", "speaking")
        self.after(0, _update)

    def add_message(self, role: str, text: str):
        """API requerida por main_gui.py."""
        self.msg_queue.put((role, text))

    def on_closing(self):
        """API requerida por main_gui.py — cancela animações antes de destruir."""
        logger.info("Fechando aplicativo...")
        self.stop_event.set()

        # Cancela todos os loops de animação (.after()) pendentes.
        # Sem isso, os callbacks continuam tentando acessar widgets
        # já destruídos → TclError: invalid command name.
        for after_id in self._after_ids:
            try:
                self.after_cancel(after_id)
            except Exception:
                pass

        # Para animações dos Canvas filhos
        try:
            self.pulse_indicator.destroy()
        except Exception:
            pass

        try:
            self.after(100, self._do_destroy)   # pequeno delay para threads finalizarem
        except Exception:
            self._do_destroy()

    def _do_destroy(self):
        try:
            self.destroy()
        except Exception:
            pass
        sys.exit(0)

    # ─── Processamento de Mensagens ───────────────────────────

    def _process_msg_queue(self):
        while not self.stop_event.is_set():
            try:
                role, text = self.msg_queue.get(timeout=0.1)
                self.after(0, self._update_chat_ui, role, text)
            except queue.Empty:
                continue

    def _update_chat_ui(self, role: str, text: str):
        self.chat_display.configure(state="normal")
        ts = datetime.now().strftime("%H:%M")

        if role == "user":
            self.chat_display.insert("end", f"\n▸ VOCÊ [{ts}]: ", "user_prefix")
            self.chat_display.insert("end", f"{text}\n", "user_text")
        elif role == "assistant":
            self.chat_display.insert("end", f"\n◈ {ASSISTANT_NAME} [{ts}]: ", "ai_prefix")
            self.chat_display.insert("end", f"{text}\n", "ai_text")
        elif role == "status":
            self.chat_display.insert("end", f"\n ── {text} ──\n", "status_tag")

        self.chat_display.see("end")
        self.chat_display.configure(state="disabled")

    def _send_command(self):
        text = self.entry.get()
        if text.strip():
            self.command_queue.put(text.strip())
            self.entry.delete(0, "end")

    # ─── Relógio ──────────────────────────────────────────────

    def _update_clock(self):
        if not self.stop_event.is_set():
            now = datetime.now().strftime("%H:%M:%S")
            try:
                self.header_canvas.itemconfig(self._clock_item, text=now)
            except Exception:
                pass
            self.after(1000, self._update_clock)

    # ─── Utilitários ─────────────────────────────────────────

    @staticmethod
    def _dim_color(hex_color: str, factor: float) -> str:
        h = hex_color.lstrip("#")
        r, g, b = (int(h[i:i+2], 16) for i in (0, 2, 4))
        return f"#{int(r*factor):02x}{int(g*factor):02x}{int(b*factor):02x}"

    @staticmethod
    def _interpolate(c1: str, c2: str, t: float) -> str:
        h1, h2 = c1.lstrip("#"), c2.lstrip("#")
        r = int(int(h1[0:2],16)*(1-t) + int(h2[0:2],16)*t)
        g = int(int(h1[2:4],16)*(1-t) + int(h2[2:4],16)*t)
        b = int(int(h1[4:6],16)*(1-t) + int(h2[4:6],16)*t)
        return f"#{r:02x}{g:02x}{b:02x}"


def WAKE_WORDS_HINT():
    try:
        from config import WAKE_WORDS
        return WAKE_WORDS[1].upper()   # "OLÁ ASSISTENTE"
    except Exception:
        return "OLÁ ASSISTENTE"
