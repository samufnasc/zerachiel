# ============================================================
# config.py — Configurações Centrais do Zerachiel v3.3
# ============================================================

import os
from dotenv import load_dotenv

load_dotenv()

# ─────────────────────────────────────────────
# Identidade
# ─────────────────────────────────────────────
ASSISTANT_NAME = "Zerachiel"
VOICE_LANGUAGE = "pt-BR"

# ─────────────────────────────────────────────
# Wake Words
# ─────────────────────────────────────────────
WAKE_WORDS = [
    # ── Variações simples — reconhecidas perfeitamente pelo STT ──
    "olá assistente",           # ← mais confiável, use este
    "oi assistente",
    "ei assistente",
    "assistente",               # ← fallback curto e direto

    # ── Nome completo ─────────────────────────────────────────
    "zerachiel",
    "olá zerachiel",
    "oi zerachiel",
    "ei zerachiel",
    "hey zerachiel",
    "olá assistente zerachiel",
    "olá assistente iniciar",

    # ── Aproximações fonéticas do STT para "Zerachiel" ────────
    # O Google STT transcreve o nome de formas variadas dependendo
    # do sotaque e do ruído. Mapeamos as mais comuns:
    "tirar shell",      # ← exatamente o que apareceu no log
    "zero chiel",
    "zeração",
    "zero shil",
    "zero xiel",
    "sera chiel",
    "cerashiel",
    "tirar chiel",
    "zero cel",
]

WAKE_RESPONSE = "Estou aqui. Pode falar."

# ─────────────────────────────────────────────
# Captura de Voz
# ─────────────────────────────────────────────
# AJUSTE v3.3: pause_threshold reduzido de 2.5 → 1.8s
# O valor 2.5s era muito generoso e causava ciclos lentos.
# 1.8s equilibra bem pausas naturais sem acumular latência.
PAUSE_THRESHOLD = 1.8

# Calibração reduzida: 0.2s é suficiente em ambientes normais.
# O valor anterior (0.5s) acumulava 0.5s por ciclo no loop de
# standby → até 60s para reconhecer quando há ruído de fundo.
CALIBRATION_DURATION = 0.2

# Timeout esperando início de fala (segundos)
LISTEN_TIMEOUT = 7

# Teto de segurança por turno (segundos)
PHRASE_TIME_LIMIT = 120

# Inatividade antes de dormir (segundos)
SLEEP_AFTER_IDLE = 120

# ─────────────────────────────────────────────
# Comandos de Controle
# ─────────────────────────────────────────────
# ─────────────────────────────────────────────
# Comandos de Controle
# ─────────────────────────────────────────────
# IMPORTANTE: usar frases com 2+ palavras para evitar que ruído
# ambiente ou palavras comuns na conversa disparem acidentalmente.
# "para", "pare", "stop" sozinhos são perigosos — aparecem em
# contextos normais ("escreva um programa para imprimir...").
INTERRUPT_PHRASES = [
    "pode parar",
    "pare agora",
    "para tudo",
    "silêncio",
    "para de falar",
    "cala boca",
    "interromper",
]

PAUSE_PHRASES = [
    "espera aí",
    "espere um momento",
    "aguarda",
    "aguarde",
    "um momento",
    "pausa",
    "calma aí",
]

RESUME_PHRASES = [
    "pode continuar",
    "continue",
    "prossiga",
    "vai",
]

# Comandos de encerramento — exigem frase COMPLETA para evitar
# encerramento acidental ao falar sobre "encerrar" um arquivo, etc.
EXIT_PHRASES = [
    "pode finalizar zerachiel",
    "finalizar zerachiel",
    "encerrar zerachiel",
    "desligar zerachiel",
    "ok assistente encerrar",      # frase completa exigida
    "zerachiel encerrar sistema",
]

# ─────────────────────────────────────────────
# Motor de IA
# ─────────────────────────────────────────────
AI_ENGINE       = "groq"
GROQ_API_KEY    = os.getenv("GROQ_API_KEY")
GROQ_MODEL      = "llama-3.1-8b-instant"
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL    = "llama3.2"

# ─────────────────────────────────────────────
# Sandbox de Arquivos
# ─────────────────────────────────────────────
BASE_SANDBOX = os.path.join(os.path.expanduser("~"), "AssistantFiles")
if not os.path.exists(BASE_SANDBOX):
    os.makedirs(BASE_SANDBOX)

_DESKTOP   = os.path.join(os.path.expanduser("~"), "Desktop")
_DOCUMENTS = os.path.join(os.path.expanduser("~"), "Documents")
_DOWNLOADS = os.path.join(os.path.expanduser("~"), "Downloads")

ALLOWED_DIRS = {
    "desktop":                _DESKTOP,
    "área de trabalho":       _DESKTOP,
    "area de trabalho":       _DESKTOP,
    "area_de_trabalho":       _DESKTOP,
    "areadetrabalho":         _DESKTOP,
    "área_de_trabalho":       _DESKTOP,
    "minha área de trabalho": _DESKTOP,
    "minha area de trabalho": _DESKTOP,
    "documentos":             _DOCUMENTS,
    "documents":              _DOCUMENTS,
    "meus documentos":        _DOCUMENTS,
    "downloads":              _DOWNLOADS,
    "sandbox":                BASE_SANDBOX,
    "assistantfiles":         BASE_SANDBOX,
    "padrão":                 BASE_SANDBOX,
}

# ─────────────────────────────────────────────
# Tools (Function Calling)
# ─────────────────────────────────────────────
TOOLS_DEFINITION = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": (
                "Busca informações em tempo real na internet. "
                "Use quando o usuário perguntar sobre eventos recentes, notícias, "
                "preços, dados atuais ou qualquer coisa que exija informação atualizada."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "O termo ou pergunta a ser pesquisado"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "file_manager",
            "description": (
                "Gerencia arquivos no computador do usuário. "
                "Use quando o usuário pedir para salvar, criar, ler, editar, "
                "copiar ou listar arquivos."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["create", "read", "list", "edit", "append", "save_last_response"],
                        "description": (
                            "create=criar arquivo, read=ler, list=listar pasta, "
                            "edit=sobrescrever, append=adicionar ao final, "
                            "save_last_response=salvar última resposta"
                        )
                    },
                    "filename": {
                        "type": "string",
                        "description": "Nome do arquivo com extensão. Opcional para 'list'."
                    },
                    "content": {
                        "type": "string",
                        "description": "Conteúdo a escrever (para create, edit, append)"
                    },
                    "directory": {
                        "type": "string",
                        "description": "'documentos', 'desktop', 'downloads' ou 'sandbox' (padrão)"
                    }
                },
                "required": ["action"]
            }
        }
    }
]

# ─────────────────────────────────────────────
# Prompt do Sistema
# ─────────────────────────────────────────────
SYSTEM_PROMPT = (
    f"Você é o {ASSISTANT_NAME}, um assistente de voz pessoal inteligente, "
    "prestativo e conciso. Sempre responda em português do Brasil. "
    "Suas respostas devem ser claras e diretas — evite respostas excessivamente longas. "
    "Quando o conteúdo for código ou texto extenso, avise que está exibindo na tela. "
    "Use web_search para dados atuais. "
    "Use file_manager quando o usuário pedir para salvar, criar ou ler arquivos. "
    "REGRA CRÍTICA para file_manager: quando o usuário disser 'área de trabalho', "
    "'desktop', 'área de trabalho do computador' ou qualquer variação, "
    "use SEMPRE directory='desktop'. "
    "Quando disser 'documentos' ou 'meus documentos', use directory='documentos'. "
    "Quando disser 'downloads', use directory='downloads'. "
    "Em caso de dúvida sobre o diretório, use directory='desktop'."
)
