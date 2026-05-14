# ============================================================
# gui_theme.py — Cores e Estética Cyberpunk (Zerachiel v4.0)
# ============================================================

import customtkinter as ctk

COLORS = {
    "bg_root": "#0a0a0f",      # Fundo ultra escuro (baseado no seu site)
    "bg_panel": "#12121a",     # Painéis e cabeçalho
    "bg_card": "#161622",      # Área do chat
    "bg_input": "#1a1a2e",     # Campo de digitação
    "border_dim": "#1e1e2e",   # Bordas discretas
    "cyan": "#00f5a0",         # Verde Neon (Acento Principal)
    "blue": "#00d4ff",         # Azul Neon (Acento Secundário)
    "purple": "#7d5fff",       # Roxo futurista
    "red": "#ff4757",          # Alerta/Perigo
    "green": "#00f5a0",        # Sucesso
    "amber": "#ffdd57",        # Aviso
    "text_primary": "#e0e0f0", # Texto claro
    "text_muted": "#555577",   # Texto secundário
    "font_mono": "Consolas",
}

def apply_ctk_theme():
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
