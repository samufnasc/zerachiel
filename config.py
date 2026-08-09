# ============================================================
# config.py — Configurações Zerachiel v3.7
# ============================================================

import os
from dotenv import load_dotenv

load_dotenv()

ASSISTANT_NAME = "Zerachiel"
VOICE_LANGUAGE = "pt-BR"

WAKE_WORDS = ["olá assistente", "oi assistente", "zerachiel", "assistente"]
WAKE_RESPONSE = "🤖 Núcleo ativado. Pode falar."

PAUSE_THRESHOLD = 0.8
CALIBRATION_DURATION = 0.1
LISTEN_TIMEOUT = 7
PHRASE_TIME_LIMIT = 15

INTERRUPT_PHRASES = ["pare", "pode parar", "silêncio", "espera", "pausa"]

# Frases que ativam a visão/captura de tela
SCREEN_REQUEST_KEYWORDS = [
    "veja a tela",
    "olhe a tela",
    "veja o monitor",
    "olhe o monitor",
    "capture a tela",
    "captura de tela",
    "o que está na tela",
    "o que esta na tela",
    "o que tem na tela",
    "o que aparece na tela",
    "o que esta aparecendo na tela",
    "ver a tela",
]

# Motores de IA
AI_ENGINE = "gemini"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Modelos Gemini disponíveis (rotação por quota diária gratuita).
# Ordem de uso: quanto menor o índice, mais prioritário.
GEMINI_MODELS = [
    "gemini-flash-latest",
    "gemma-4-26b-a4b-it",
    "gemma-4-31b-it",
    "gemini-3.5-flash",
    "gemini-flash-lite-latest",
    "gemini-3-flash-preview",
    "gemini-3.1-flash-lite-preview",
    "gemini-3.1-flash-lite",
    "gemini-3.5-flash-lite",
    "gemini-3.6-flash",
    "gemini-robotics-er-1.6-preview",
    "gemini-robotics-er-2-preview",
]
GEMINI_MODEL = GEMINI_MODELS[0]  # alias retrocompatível

# Prioridade da VISÃO: sempre os modelos gemma primeiro (multimodal),
# depois os demais como fallback caso o gemma atinja a cota diária.
GEMINI_VISION_MODELS = [m for m in GEMINI_MODELS if m.startswith("gemma-")] + [m for m in GEMINI_MODELS if not m.startswith("gemma-")]

# Guarda quais modelos Gemini atingiram a quota diária (persistido por dia)
GEMINI_QUOTA_STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".gemini_quota_state.json")

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = "llama-3.1-8b-instant"

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = "llama3.2"
OLLAMA_TIMEOUT = 20
OLLAMA_SLOW_THRESHOLD = 12

# Diretórios
BASE_SANDBOX = os.path.join(os.path.expanduser("~"), "ZerachielFiles")
ALLOWED_DIRS = {
    "desktop": os.path.join(os.path.expanduser("~"), "Desktop"),
    "documentos": os.path.join(os.path.expanduser("~"), "Documents"),
    "downloads": os.path.join(os.path.expanduser("~"), "Downloads"),
    "sandbox": BASE_SANDBOX,
}

# CORREÇÃO CRÍTICA: Adicionado "type": "function" para compatibilidade com Groq
TOOLS_DEFINITION = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Busca informações na internet.",
            "parameters": {
                "type": "object", 
                "properties": {
                    "query": {"type": "string", "description": "Termo de busca"}
                }, 
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "file_manager",
            "description": "Gerencia arquivos (create, read, list, edit, append).",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["create", "read", "list", "edit", "append"]},
                    "filename": {"type": "string", "description": "Nome do arquivo com extensão"},
                    "content": {"type": "string", "description": "Conteúdo do arquivo"},
                    "directory": {"type": "string", "enum": ["desktop", "documentos", "downloads", "sandbox"]}
                },
                "required": ["action", "filename"]
            }
        }
    }
]

SYSTEM_PROMPT = f"Você é o {ASSISTANT_NAME}, uma IA futurista. Seja conciso e prestativo. Use ferramentas quando necessário."
