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

# Motores de IA
AI_ENGINE = "gemini"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = "gemini-2.0-flash"

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = "llama-3.1-8b-instant"

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = "llama3.2"

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
