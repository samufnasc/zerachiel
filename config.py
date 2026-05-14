# ============================================================
# config.py — Configurações Centrais do Zerachiel v3.3 + Gemini
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
    "olá assistente",
    "oi assistente",
    "ei assistente",
    "assistente",
    "zerachiel",
    "olá zerachiel",
    "oi zerachiel",
    "ei zerachiel",
    "hey zerachiel",
    "olá assistente zerachiel",
    "tirar shell",
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
PAUSE_THRESHOLD = 1.8
CALIBRATION_DURATION = 0.2
LISTEN_TIMEOUT = 7
PHRASE_TIME_LIMIT = 120
SLEEP_AFTER_IDLE = 120

# ─────────────────────────────────────────────
# Comandos de Controle
# ─────────────────────────────────────────────
INTERRUPT_PHRASES = [
    "pode parar", "pare agora", "para tudo", "silêncio",
    "para de falar", "cala boca", "interromper",
]

PAUSE_PHRASES = [
    "espera aí", "espere um momento", "aguarda", "aguarde",
    "um momento", "pausa", "calma aí",
]

RESUME_PHRASES = ["pode continuar", "continue", "prossiga", "vai"]

EXIT_PHRASES = [
    "pode finalizar zerachiel", "finalizar zerachiel",
    "encerrar zerachiel", "desligar zerachiel",
    "ok assistente encerrar", "zerachiel encerrar sistema",
]

# ─────────────────────────────────────────────
# Motor de IA
# ─────────────────────────────────────────────
AI_ENGINE       = "groq"          # ← alterado (pode voltar para "groq")
AI_ENGINE       = "gemini"          # Primário: Gemini → Groq fallback

GROQ_API_KEY    = os.getenv("GROQ_API_KEY")
GROQ_MODEL      = "llama-3.1-8b-instant"
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL    = "llama3.2"

# Gemini (já existe)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL   = "gemini-2.0-flash"

# ─────────────────────────────────────────────
# Gemini (novo)
# ─────────────────────────────────────────────
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL   = "gemini-2.0-flash"

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
            "description": "Busca informações em tempo real na internet.",
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
            "description": "Gerencia arquivos no computador do usuário.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["create", "read", "list", "edit", "append", "save_last_response"],
                        "description": "create, read, list, edit, append, save_last_response"
                    },
                    "filename": {"type": "string", "description": "Nome do arquivo"},
                    "content": {"type": "string", "description": "Conteúdo a escrever"},
                    "directory": {"type": "string", "description": "'desktop', 'documentos', 'downloads' ou 'sandbox'"}
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
    "Você é o {ASSISTANT_NAME}, um assistente de voz pessoal inteligente, "
    "prestativo e conciso. Sempre responda em português do Brasil. "
    "Suas respostas devem ser claras e diretas — evite respostas excessivamente longas. "
    "Quando o conteúdo for código ou texto extenso, avise que está exibindo na tela. "
    "Use Gemini para pesquisas e geração de conteúdo de alta qualidade. "
    "Use Gemini como principal. "
    "Use web_search para dados atuais. "
    "Use file_manager quando o usuário pedir para salvar, criar ou ler arquivos. "
    "REGRA CRÍTICA para file_manager: quando o usuário disser 'área de trabalho', "
    "'desktop' ou variações, use directory='desktop'. "
    "Quando disser 'documentos', use 'documentos'. Quando disser 'downloads', use 'downloads'."
)