# ============================================================
# gui_theme.py - Configurações Visuais Cyberpunk (Corrigido)
# ============================================================

COLORS = {
    # Fundos
    "bg_root":       "#050510",   # preto profundo
    "bg_panel":      "#0a0a1a",   # painéis internos
    "bg_card":       "#0d0d22",   # chat e histórico
    "bg_input":      "#08081a",   # campo de entrada

    # Neons
    "cyan":          "#00f5ff",   # dominante
    "purple":        "#bf00ff",   # especial
    "green":         "#00ff88",   # aguardando
    "red":           "#ff003c",   # ouvindo
    "amber":         "#ff9900",   # usuário
    "blue":          "#4488ff",   # pensando

    # Texto
    "text_primary":  "#d0d0ff",
    "text_dim":      "#3a3a6a",
    
    # Bordas (AS CHAVES QUE ESTAVAM FALTANDO)
    "border_cyan":   "#00f5ff",
    "border_dim":    "#1a1a3a",

    # Fontes
    "font_mono":     "Consolas"
}

def apply_ctk_theme():
    import customtkinter as ctk
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")