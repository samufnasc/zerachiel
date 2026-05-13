# ============================================================
# gui_theme.py — Paleta Cyberpunk Neon-Dark (Zerachiel v3.3)
# Para trocar o tema, edite apenas este arquivo.
# ============================================================

COLORS = {
    # ── Fundos ────────────────────────────────────────────────
    "bg_root":       "#050510",   # janela principal
    "bg_panel":      "#08081a",   # header, status, waveform
    "bg_card":       "#0a0a1f",   # chat
    "bg_input":      "#06060f",   # campo de texto

    # ── Neons ─────────────────────────────────────────────────
    "cyan":          "#00f5ff",   # cor dominante
    "purple":        "#bf00ff",   # destaques / engine badge
    "green":         "#00ff88",   # waiting / OK
    "red":           "#ff003c",   # listening / alerta
    "amber":         "#ff9900",   # mensagens do usuário
    "blue":          "#4488ff",   # thinking / processando

    # ── Texto ─────────────────────────────────────────────────
    "text_primary":  "#c8c8f0",   # texto principal
    "text_dim":      "#2e2e55",   # timestamps, texto secundário

    # ── Bordas ────────────────────────────────────────────────
    "border_cyan":   "#00f5ff",
    "border_dim":    "#14142a",

    # ── Fonte monospace ───────────────────────────────────────
    "font_mono":     "Consolas",
}


def apply_ctk_theme():
    """
    Configura o CustomTkinter.
    DEVE ser chamado ANTES de instanciar qualquer widget CTk.
    Em gui.py: chamado no início de AssistantGUI.__init__(),
    antes de super().__init__().
    """
    import customtkinter as ctk
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("dark-blue")
